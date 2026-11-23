"""The pipeline config: one dataclass per stage kind, loading, and the checks that run before any
call, so a config error stops the run before it pays for a stage."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, get_args

from agents import ClaudeSettings

AGENT_SEES = ("passage", "doc_type", "reader", "question", "left_to_other_documents", "notes")


@dataclass(frozen=True)
class LintLoop:
    lint: str
    score_key: str
    until: float
    max_rounds: int


@dataclass(frozen=True)
class DraftStage:
    """Starts the author conversation from the guidance files in `read`."""

    kind: ClassVar[str] = "draft"
    name: str
    read: tuple[str, ...]
    instructions: str = ""

    def __post_init__(self) -> None:
        if not self.read:
            raise ValueError(f"stage {self.name}: a draft reads at least one file")


@dataclass(frozen=True)
class BareDraftStage:
    """The model's own draft: no guidance files, no path note and no tools."""

    kind: ClassVar[str] = "bare_draft"
    name: str
    instructions: str = ""


@dataclass(frozen=True)
class CopiedDraftStage:
    """Another pipeline's draft and author session, so two pipelines share a draft; no call."""

    kind: ClassVar[str] = "copied_draft"
    name: str
    from_pipeline: str


@dataclass(frozen=True)
class AgentStage:
    kind: ClassVar[str] = "agent"
    name: str
    agent_file: str | None = None
    brief: str = ""
    model: str | None = None
    read: tuple[str, ...] = ()
    sees: tuple[str, ...] = ()
    group: str | None = None

    def __post_init__(self) -> None:
        if bool(self.agent_file) == bool(self.brief):
            raise ValueError(
                f"stage {self.name}: an agent stage takes exactly one of agent_file, brief"
            )
        if not set(self.sees) <= set(AGENT_SEES):
            raise ValueError(f"stage {self.name}: sees must be a subset of {AGENT_SEES}")


@dataclass(frozen=True)
class AuthorStage:
    kind: ClassVar[str] = "author"
    name: str
    instructions: str = ""
    read: tuple[str, ...] = ()
    inputs: tuple[str, ...] = ()
    lint: tuple[str, ...] = ()
    loop: LintLoop | None = None

    def __post_init__(self) -> None:
        if self.loop and self.loop.lint not in self.lint:
            raise ValueError(
                f"stage {self.name}: the loop's lint {self.loop.lint!r} is not in lint"
            )


@dataclass(frozen=True)
class FidelityGate:
    kind: ClassVar[str] = "fidelity_gate"
    name: str
    compare_to: str
    agent_file: str
    instructions: str = ""
    model: str | None = None
    min_changed_sentences: int = 4


DRAFT_STAGES = DraftStage | BareDraftStage | CopiedDraftStage
Stage = DRAFT_STAGES | AgentStage | AuthorStage | FidelityGate
STAGE_TYPES = {kind.kind: kind for kind in get_args(Stage)}


@dataclass(frozen=True)
class Pipeline:
    name: str
    override: str
    stages: tuple[Stage, ...]


@dataclass(frozen=True)
class LintCommand:
    command: tuple[str, ...]
    ok_exit_codes: tuple[int, ...]


@dataclass(frozen=True)
class AgentDefinition:
    model: str
    tools: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class Config:
    author_model: str
    effort: str
    seed: int
    path_note: str
    readable_dirs: tuple[Path, ...]
    lints: dict[str, LintCommand]
    pipelines: tuple[Pipeline, ...]
    fidelity_agent_file: str
    fidelity_model: str
    claude: ClaudeSettings

    def pipeline(self, name: str) -> Pipeline:
        return next(pipeline for pipeline in self.pipelines if pipeline.name == name)


def parse_stage(entry: dict) -> Stage:
    """Build the stage's own kind, so a key that kind does not take raises TypeError."""
    fields = {
        key: tuple(value) if isinstance(value, list) else value for key, value in entry.items()
    }
    kind = fields.pop("kind")
    if kind not in STAGE_TYPES:
        raise ValueError(
            f"stage {fields['name']}: unknown kind {kind!r}, not one of {list(STAGE_TYPES)}"
        )
    if "loop" in fields:
        fields["loop"] = LintLoop(**fields["loop"])
    return STAGE_TYPES[kind](**fields)


def load_config(config_file: Path, claude_bin: str) -> Config:
    raw = tomllib.loads(config_file.read_text())
    pipelines = tuple(
        Pipeline(
            name=entry["name"],
            override=entry.get("override", "").strip(),
            stages=tuple(parse_stage(stage) for stage in entry["stage"]),
        )
        for entry in raw["pipeline"]
    )
    config = Config(
        author_model=raw["run"]["author_model"],
        effort=raw["run"]["effort"],
        seed=raw["run"]["seed"],
        path_note=raw["run"].get("path_note", "").strip(),
        readable_dirs=tuple(Path(path) for path in raw["run"]["readable_dirs"]),
        lints={
            name: LintCommand(tuple(entry["command"]), tuple(entry["ok_exit_codes"]))
            for name, entry in raw.get("lint", {}).items()
        },
        pipelines=pipelines,
        fidelity_agent_file=raw["fidelity"]["agent_file"],
        fidelity_model=raw["fidelity"]["model"],
        claude=ClaudeSettings(
            claude_bin=claude_bin,
            timeout_s=raw["run"]["timeout_s"],
            max_budget_usd=raw["run"]["max_budget_usd"],
        ),
    )
    validate_config(config)
    return config


def validate_config(config: Config) -> None:
    names = [pipeline.name for pipeline in config.pipelines]
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate pipeline names: {names}")
    for pipeline in config.pipelines:
        validate_stages(pipeline, config.lints)
    copied_drafts = {
        pipeline.name: pipeline.stages[0].from_pipeline
        for pipeline in config.pipelines
        if isinstance(pipeline.stages[0], CopiedDraftStage)
    }
    for name, source in copied_drafts.items():
        if source not in names or source in copied_drafts:
            raise ValueError(f"pipeline {name}: draft source {source!r} must draft itself")


def validate_stages(pipeline: Pipeline, lints: dict[str, LintCommand]) -> None:
    first, *rest = pipeline.stages
    if not isinstance(first, DRAFT_STAGES) or any(isinstance(s, DRAFT_STAGES) for s in rest):
        raise ValueError(f"pipeline {pipeline.name}: the first stage, and only it, is a draft")
    stage_names = [stage.name for stage in pipeline.stages]
    if len(set(stage_names)) != len(stage_names):
        raise ValueError(f"pipeline {pipeline.name}: duplicate stage names")
    for index, stage in enumerate(pipeline.stages):
        where = f"{pipeline.name}/{stage.name}"
        missing_files = [path for path in named_files(stage) if not Path(path).is_file()]
        if missing_files:
            raise FileNotFoundError(f"{where}: missing {missing_files}")
        earlier = {earlier_stage.name: earlier_stage for earlier_stage in pipeline.stages[:index]}
        match stage:
            case AuthorStage():
                not_agents = [
                    name for name in stage.inputs if not isinstance(earlier.get(name), AgentStage)
                ]
                unknown_lints = [lint for lint in stage.lint if lint not in lints]
                if not_agents or unknown_lints:
                    raise ValueError(
                        f"{where}: inputs {not_agents} are not earlier agent stages, "
                        f"or lints {unknown_lints} are not defined"
                    )
            case FidelityGate() if not isinstance(
                earlier.get(stage.compare_to), DRAFT_STAGES | AuthorStage | FidelityGate
            ):
                raise ValueError(f"{where}: compare_to {stage.compare_to!r} is no earlier passage")


def named_files(stage: Stage) -> list[str]:
    """The files a stage's model is told to read, or takes its agent definition from."""
    match stage:
        case DraftStage() | AuthorStage():
            return list(stage.read)
        case BareDraftStage() | CopiedDraftStage():
            return []
        case AgentStage():
            return [*stage.read, *([stage.agent_file] if stage.agent_file else [])]
        case FidelityGate():
            return [stage.agent_file]


def load_agent_definition(agent_file: Path) -> AgentDefinition:
    """Read a Claude Code subagent file: YAML-style frontmatter between `---` lines, then the prompt."""
    _, frontmatter, body = agent_file.read_text().split("---\n", 2)
    fields = dict(line.split(": ", 1) for line in frontmatter.strip().splitlines())
    return AgentDefinition(
        model=fields["model"].strip(),
        tools=tuple(tool.strip() for tool in fields["tools"].split(",")),
        body=body.strip(),
    )
