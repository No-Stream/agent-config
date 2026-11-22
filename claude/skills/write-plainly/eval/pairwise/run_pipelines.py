#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Generate one passage per task and writing pipeline, with each pipeline's own review steps.

A pipeline is a list of stages read from a TOML config (see README.md). The author of a passage
is one Claude conversation: the draft starts it and each later author stage forks it, so every
stage sees what the author saw. Reviewers are fresh conversations that see only what their stage
names. Every stage's output is written as soon as it finishes, and a rerun skips finished stages.
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import random
import subprocess
import threading
import uuid
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from agents import PASSAGE_SCHEMA, ClaudeCall, ClaudeResult, run_claude
from budget import cost_summary, format_plan
from common import (
    Task,
    load_tasks,
    read_list,
    run_parallel,
    word_count,
    write_json,
    write_text_atomic,
)
from fidelity import changed_sentence_count, unsupported_by_passage, unsupported_count
from pipeline_config import (
    AgentStage,
    AuthorStage,
    BareDraftStage,
    Config,
    CopiedDraftStage,
    DraftStage,
    FidelityGate,
    LintLoop,
    Pipeline,
    Stage,
    load_agent_definition,
    load_config,
)
from prompts import (
    AUTHOR_PROMPT,
    BARE_DRAFT_PROMPT,
    DRAFT_PROMPT,
    GATE_FIDELITY_PROMPT,
    MEASURE_FIDELITY_PROMPT,
    TASK_RULES,
    inputs_block,
    lint_block,
    quoted,
    read_first,
    task_brief,
)

logger: logging.Logger = logging.getLogger(__name__)


def steps(stages: tuple[Stage, ...]) -> list[list[int]]:
    """Stage indexes in the order they run; consecutive agent stages sharing a group run at once."""

    def group_key(index: int) -> str | int:
        match stages[index]:
            case AgentStage(group=str(group)):
                return group
            case _:
                return index

    return [list(members) for _, members in itertools.groupby(range(len(stages)), key=group_key)]


def latest(records: list[dict], key: str) -> str:
    return next(record[key] for record in reversed(records) if record.get(key) is not None)


def require_reads(stage: DraftStage | AgentStage | AuthorStage, result: ClaudeResult) -> None:
    """A stage whose model skipped a named file would quietly run without that guidance."""
    unread = [path for path in stage.read if Path(path).resolve() not in result.read_files]
    if unread:
        raise RuntimeError(f"stage {stage.name} did not read {unread}")


def loop_score(loop: LintLoop, lint_runs: list[dict]) -> float:
    output = next(run["stdout"] for run in lint_runs if run["lint"] == loop.lint)
    return float(json.loads(output)[loop.score_key])


def call_log(role: str, result: ClaudeResult) -> dict:
    return {
        "role": role,
        "session_id": result.session_id,
        "cost_usd": result.cost_usd,
        "served_models": list(result.served_models),
    }


def with_passage(record: dict, result: ClaudeResult, role: str) -> dict:
    passage = result.structured["passage"].strip()
    if not passage:
        raise RuntimeError(f"stage {record['stage']} returned an empty passage")
    record["calls"].append(call_log(role, result))
    record.update({"passage": passage, "session_id": result.session_id})
    return record


@dataclass(frozen=True)
class StageRun:
    """One stage of one task's pipeline, and the record it fills in."""

    task: Task
    pipeline: Pipeline
    stage: Stage
    stage_dir: Path
    record: dict


class Runner:
    def __init__(self, config: Config, tasks: list[Task], out_dir: Path) -> None:
        self.config = config
        self.tasks = {task.task_id: task for task in tasks}
        self.out_dir = out_dir.resolve()
        self.session_dir = out_dir / ".claude-cwd"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.locks: dict[Path, threading.Lock] = {}
        self.locks_guard = threading.Lock()

    def lock_for(self, path: Path) -> threading.Lock:
        with self.locks_guard:
            return self.locks.setdefault(path, threading.Lock())

    def stage_file(self, task_id: str, pipeline: Pipeline, index: int) -> Path:
        return (
            self.out_dir
            / task_id
            / pipeline.name
            / f"{index:02d}-{pipeline.stages[index].name}.json"
        )

    def context(self, pipeline: Pipeline) -> str:
        return "\n".join(part for part in (self.config.path_note, pipeline.override) if part)

    def claude(
        self,
        *,
        prompt: str,
        model: str,
        tools: tuple[str, ...],
        system_append: str | None = None,
        json_schema: dict | None = None,
        new_session_id: str | None = None,
        resume_session_id: str | None = None,
    ) -> ClaudeResult:
        call = ClaudeCall(
            prompt=prompt,
            model=model,
            effort=self.config.effort,
            tools=tools,
            readable_dirs=(*self.config.readable_dirs, self.out_dir),
            cwd=self.session_dir,
            system_append=system_append,
            new_session_id=new_session_id,
            resume_session_id=resume_session_id,
            json_schema=json_schema,
        )
        return run_claude(call, self.config.claude)

    def author_call(
        self, prompt: str, resume_session_id: str | None, tools: tuple[str, ...] = ("Read",)
    ) -> ClaudeResult:
        return self.claude(
            prompt=prompt,
            model=self.config.author_model,
            tools=tools,
            json_schema=PASSAGE_SCHEMA,
            new_session_id=None if resume_session_id else str(uuid.uuid4()),
            resume_session_id=resume_session_id,
        )

    def agent_call(self, prompt: str, agent_file: str | None, model: str | None) -> ClaudeResult:
        if agent_file:
            definition = load_agent_definition(Path(agent_file))
            return self.claude(
                prompt=prompt,
                model=model or definition.model,
                tools=definition.tools,
                system_append=definition.body,
            )
        return self.claude(prompt=prompt, model=model or self.config.author_model, tools=("Read",))

    def run_lints(self, lint_names: tuple[str, ...], passage: str, input_file: Path) -> list[dict]:
        write_text_atomic(input_file, passage.strip() + "\n")
        runs = []
        for lint_name in lint_names:
            lint = self.config.lints[lint_name]
            command = [part.replace("{file}", str(input_file)) for part in lint.command]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode not in lint.ok_exit_codes:
                raise RuntimeError(
                    f"lint {lint_name} exited {completed.returncode}: {completed.stderr[-2000:]}"
                )
            runs.append(
                {
                    "lint": lint_name,
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
        return runs

    def ensure_stage(
        self, task_id: str, pipeline: Pipeline, index: int, previous: list[dict]
    ) -> dict:
        stage_file = self.stage_file(task_id, pipeline, index)
        # A shared draft is ensured by its own pipeline and by every pipeline that copies it.
        with self.lock_for(stage_file):
            if stage_file.is_file():
                return json.loads(stage_file.read_text())
            record = self.compute_stage(self.tasks[task_id], pipeline, index, previous)
            if record.get("passage") is not None:
                record["word_count"] = word_count(record["passage"])
            write_json(stage_file, record)
            logger.info(f"finished {task_id}/{pipeline.name}/{pipeline.stages[index].name}")
            return record

    def compute_stage(
        self, task: Task, pipeline: Pipeline, index: int, previous: list[dict]
    ) -> dict:
        stage = pipeline.stages[index]
        run = StageRun(
            task=task,
            pipeline=pipeline,
            stage=stage,
            stage_dir=self.stage_file(task.task_id, pipeline, index).with_suffix(""),
            record={"stage": stage.name, "kind": stage.kind, "calls": []},
        )
        if isinstance(stage, DraftStage):
            return self.draft(run)
        if isinstance(stage, BareDraftStage):
            return self.bare_draft(run)
        if isinstance(stage, CopiedDraftStage):
            return self.copied_draft(run)
        passage, session_id = latest(previous, "passage"), latest(previous, "session_id")
        agent_outputs = {r["stage"]: r["text"] for r in previous if r["kind"] == AgentStage.kind}
        match stage:
            case AgentStage():
                return self.agent_stage(run, passage)
            case AuthorStage(loop=None):
                return self.author_stage(run, passage, session_id, agent_outputs)
            case AuthorStage():
                return self.lint_loop_stage(run, passage, session_id, agent_outputs)
            case FidelityGate():
                earlier = next(r["passage"] for r in previous if r["stage"] == stage.compare_to)
                return self.fidelity_gate(run, earlier, passage, session_id)

    def draft(self, run: StageRun) -> dict:
        stage, task = run.stage, run.task
        prompt = DRAFT_PROMPT.format(
            read_list=read_list(stage.read),
            instructions=stage.instructions.strip(),
            brief=task_brief(task),
            rules=TASK_RULES,
            context=self.context(run.pipeline),
        )
        result = self.author_call(prompt, resume_session_id=None)
        require_reads(stage, result)
        return with_passage(run.record, result, "author")

    def bare_draft(self, run: StageRun) -> dict:
        """The model's own draft: no path note to the skill and no tool to open it."""
        prompt = BARE_DRAFT_PROMPT.format(
            instructions=run.stage.instructions.strip(),
            brief=task_brief(run.task),
            rules=TASK_RULES,
            context=run.pipeline.override,
        )
        result = self.author_call(prompt, resume_session_id=None, tools=())
        return with_passage(run.record, result, "author")

    def copied_draft(self, run: StageRun) -> dict:
        source_pipeline = self.config.pipeline(run.stage.from_pipeline)
        source = self.ensure_stage(run.task.task_id, source_pipeline, 0, previous=[])
        return {**source, "copied_from": run.stage.from_pipeline}

    def agent_stage(self, run: StageRun, passage: str) -> dict:
        stage, task = run.stage, run.task
        lines = [stage.brief.strip()] if stage.brief else []
        if stage.read:
            lines.append(read_first(stage.read))
        if "passage" in stage.sees:
            document_file = run.stage_dir / "document.md"
            write_text_atomic(document_file, passage.strip() + "\n")
            lines.append(f"The document is the file {document_file}.")
        if "doc_type" in stage.sees:
            lines.append(f"Document type: {task.doc_type}")
        if "reader" in stage.sees:
            lines.append(f"Intended reader: {task.reader}")
        if "notes" in stage.sees:
            lines.append(
                "Source notes the document was written from:\n" + quoted(task.notes_for_writer)
            )
        lines.append(self.context(run.pipeline))
        result = self.agent_call(
            "\n\n".join(line for line in lines if line), stage.agent_file, stage.model
        )
        require_reads(stage, result)
        run.record["calls"].append(call_log("agent", result))
        run.record["text"] = result.text
        return run.record

    def author_turn(self, run: StageRun, instructions: str, blocks: str) -> ClaudeResult:
        """One author turn on the record's passage, forked from its session; updates both."""
        prompt = AUTHOR_PROMPT.format(
            stage_name=run.stage.name,
            instructions=instructions,
            blocks=blocks,
            passage=quoted(run.record["passage"]),
            context=self.context(run.pipeline),
        )
        result = self.author_call(prompt, resume_session_id=run.record["session_id"])
        with_passage(run.record, result, "author")
        return result

    def author_stage(
        self, run: StageRun, passage: str, session_id: str, agent_outputs: dict[str, str]
    ) -> dict:
        """One author turn on the stage's inputs and the output of its linters."""
        stage = run.stage
        lint_file = run.stage_dir / "lint-input-1.md"
        lint_runs = self.run_lints(stage.lint, passage, lint_file) if stage.lint else []
        run.record.update({"passage": passage, "session_id": session_id, "lint_runs": [lint_runs]})
        read_block = read_first(stage.read) + "\n" if stage.read else ""
        blocks = read_block + inputs_block(stage.inputs, agent_outputs) + lint_block(lint_runs)
        result = self.author_turn(run, stage.instructions.strip(), blocks)
        require_reads(stage, result)
        run.record["author_turns"] = 1
        return run.record

    def lint_loop_stage(
        self, run: StageRun, passage: str, session_id: str, agent_outputs: dict[str, str]
    ) -> dict:
        """The author stage's turn, then lint and another turn, until the score clears or the
        turns reach the loop's max_rounds."""
        stage, record = run.stage, run.record
        loop = stage.loop
        self.author_stage(run, passage, session_id, agent_outputs)
        for turns in range(1, loop.max_rounds + 1):
            lint_file = run.stage_dir / f"lint-input-{turns + 1}.md"
            lint_runs = self.run_lints(stage.lint, record["passage"], lint_file)
            record["lint_runs"].append(lint_runs)
            record["final_score"] = loop_score(loop, lint_runs)
            if record["final_score"] >= loop.until or turns == loop.max_rounds:
                break
            round_note = f"The score is still below {loop.until}; this is round {turns + 1}."
            self.author_turn(
                run, f"{stage.instructions.strip()}\n\n{round_note}", lint_block(lint_runs)
            )
            record["author_turns"] = turns + 1
        return record

    def fidelity_gate(self, run: StageRun, earlier: str, passage: str, session_id: str) -> dict:
        stage, record = run.stage, run.record
        changed = changed_sentence_count(earlier, passage)
        record.update(
            {
                "changed_sentences": changed,
                "triggered": changed >= stage.min_changed_sentences,
                "passage": passage,
                "session_id": session_id,
                "unsupported": 0,
            }
        )
        if not record["triggered"]:
            return record
        earlier_file, revision_file = run.stage_dir / "earlier.md", run.stage_dir / "revision.md"
        write_text_atomic(earlier_file, earlier.strip() + "\n")
        write_text_atomic(revision_file, passage.strip() + "\n")
        prompt = GATE_FIDELITY_PROMPT.format(
            earlier_file=earlier_file,
            revision_file=revision_file,
            notes=quoted(run.task.notes_for_writer),
            context=self.context(run.pipeline),
        )
        check = self.agent_call(prompt, stage.agent_file, stage.model)
        record["calls"].append(call_log("agent", check))
        record["text"] = check.text
        record["unsupported"] = unsupported_count(check.text)
        if record["unsupported"]:
            check_block = f"\nOutput of the fidelity check:\n{quoted(check.text)}\n"
            self.author_turn(run, stage.instructions.strip(), check_block)
        return record

    def run_chain(self, task_id: str, pipeline: Pipeline) -> str:
        records: list[dict] = []
        for step in steps(pipeline.stages):
            jobs = [
                partial(self.ensure_stage, task_id, pipeline, index, list(records))
                for index in step
            ]
            records += run_parallel(jobs, len(jobs))
        final_passage = latest(records, "passage")
        write_text_atomic(self.out_dir / task_id / pipeline.name / "final.md", final_passage + "\n")
        return final_passage

    def measure_fidelity(self, task_id: str) -> dict:
        """Check every pipeline's final passage for one task against the notes, in one call."""
        result_file = self.out_dir / task_id / "fidelity.json"
        if result_file.is_file():
            return json.loads(result_file.read_text())
        task = self.tasks[task_id]
        pipeline_names = [pipeline.name for pipeline in self.config.pipelines]
        random.Random(f"{self.config.seed}-{task_id}").shuffle(pipeline_names)
        labels = {chr(ord("A") + i): name for i, name in enumerate(pipeline_names)}
        passage_files = {}
        for label, name in labels.items():
            passage_files[label] = self.out_dir / task_id / "fidelity" / f"passage-{label}.md"
            write_text_atomic(
                passage_files[label], (self.out_dir / task_id / name / "final.md").read_text()
            )
        prompt = MEASURE_FIDELITY_PROMPT.format(
            count=len(labels),
            files=", ".join(f"{label}: {path}" for label, path in passage_files.items()),
            notes=quoted(task.notes_for_writer),
            context=self.config.path_note,
        )
        check = self.agent_call(prompt, self.config.fidelity_agent_file, self.config.fidelity_model)
        record = {
            "labels": labels,
            "text": check.text,
            "unsupported": unsupported_by_passage(check.text, labels),
            "calls": [call_log("agent", check)],
        }
        write_json(result_file, record)
        return record

    def run(self, task_ids: list[str], pipeline_names: list[str], jobs: int) -> None:
        chains = [
            partial(self.run_chain, task_id, self.config.pipeline(name))
            for task_id in task_ids
            for name in pipeline_names
        ]
        run_parallel(chains, jobs)
        if set(pipeline_names) == {pipeline.name for pipeline in self.config.pipelines}:
            run_parallel([partial(self.measure_fidelity, task_id) for task_id in task_ids], jobs)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run", "cost"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, help="generation directory (run, cost)")
    parser.add_argument("--jobs", type=int, default=4, help="task and pipeline chains run at once")
    parser.add_argument("--only-task", nargs="*", default=None)
    parser.add_argument("--only-pipeline", nargs="*", default=None)
    parser.add_argument("--claude-bin", default="claude")
    args = parser.parse_args()
    config = load_config(args.config, args.claude_bin)
    tasks = load_tasks(args.tasks)
    if args.command == "plan":
        print(format_plan(config, len(tasks)))
        return
    if args.command == "cost":
        print(json.dumps(cost_summary(args.out), indent=2))
        return
    task_ids = args.only_task or [task.task_id for task in tasks]
    pipeline_names = args.only_pipeline or [pipeline.name for pipeline in config.pipelines]
    Runner(config, tasks, args.out).run(task_ids, pipeline_names, args.jobs)
    print(json.dumps(cost_summary(args.out), indent=2))


if __name__ == "__main__":
    main()
