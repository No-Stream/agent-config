import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from conftest import FAKES_DIR, STUB_TASKS, launcher

from budget import call_bounds, cost_summary, format_plan
from common import Task, load_tasks
from fidelity import changed_sentence_count, unsupported_by_passage, unsupported_count
from pipeline_config import load_config
from prompts import TASK_RULES, task_brief
from run_pipelines import Runner

SCORE_LINT = (
    "import json, sys, pathlib\n"
    "sys.stderr.write('Installed 1 package in 3ms\\n')\n"
    "counter = pathlib.Path(sys.argv[1]).parent / 'lint-count'\n"
    "count = int(counter.read_text()) if counter.exists() else 0\n"
    "counter.write_text(str(count + 1))\n"
    "scores = [float(s) for s in sys.argv[2].split(',')]\n"
    "print(json.dumps({'score': scores[min(count, len(scores) - 1)]}))\n"
)
CONFIG = """
[run]
author_model = "opus"
effort = "low"
seed = 7
timeout_s = 60
max_budget_usd = 1.0
path_note = "Path note for the test."
readable_dirs = ["{skill_dir}"]

[lint.plain]
command = ["{python}", "-c", "import sys; print('a finding'); sys.exit(1)", "{{file}}"]
ok_exit_codes = [0, 1]

[lint.score]
command = ["{python}", "-c", {score_lint}, "{{file}}", "{scores}"]
ok_exit_codes = [0]

[fidelity]
agent_file = "{skill_dir}/fidelity.md"
model = "opus"

[[pipeline]]
name = "base"
  [[pipeline.stage]]
  kind = "draft"
  name = "draft"
  read = ["{skill_dir}/guide.md"]
  instructions = "Draft it."
  [[pipeline.stage]]
  kind = "agent"
  name = "reviewer"
  agent_file = "{skill_dir}/reviewer.md"
  sees = ["passage", "reader", "doc_type", "notes"]
  group = "review"
  [[pipeline.stage]]
  kind = "agent"
  name = "reader-test"
  brief = "List the questions a cold reader would ask."
  sees = ["passage"]
  group = "review"
  [[pipeline.stage]]
  kind = "author"
  name = "apply-review"
  inputs = ["reviewer", "reader-test"]
  instructions = "Apply the findings you agree with."
  [[pipeline.stage]]
  kind = "fidelity_gate"
  name = "fidelity"
  compare_to = "draft"
  agent_file = "{skill_dir}/fidelity.md"
  instructions = "Fix the unsupported changes."

[[pipeline]]
name = "variant"
override = "Override for the variant."
  [[pipeline.stage]]
  kind = "copied_draft"
  name = "draft"
  from_pipeline = "base"
  [[pipeline.stage]]
  kind = "agent"
  name = "style"
  brief = "Style pass."
  read = ["{skill_dir}/guide.md"]
  sees = ["passage"]
  model = "sonnet"
  [[pipeline.stage]]
  kind = "author"
  name = "accept-style"
  read = ["{skill_dir}/guide.md"]
  inputs = ["style"]
  instructions = "Accept what you agree with."
  [[pipeline.stage]]
  kind = "author"
  name = "score-loop"
  lint = ["score"]
  loop = {{ lint = "score", score_key = "score", until = 80, max_rounds = 3 }}
  instructions = "Fix what the score flags."

[[pipeline]]
name = "solo"
  [[pipeline.stage]]
  kind = "draft"
  name = "draft"
  read = ["{skill_dir}/guide.md"]
  [[pipeline.stage]]
  kind = "author"
  name = "lint"
  lint = ["plain"]
  instructions = "Triage the findings once."
"""
BARE_PIPELINE = """
[[pipeline]]
name = "bare"
  [[pipeline.stage]]
  kind = "bare_draft"
  name = "draft"
"""
AGENT_FILE = "---\nname: {name}\ndescription: test agent\ntools: Read, Grep\nmodel: sonnet\n---\n\nYou {name}.\n"
CALLS_PER_TASK = 13
LAST_STAGES = {"base": "04-fidelity", "variant": "03-score-loop", "solo": "01-lint"}
GATE_CHECK = "The earlier version is the file"


def write_config(tmp_path: Path, scores: str = "50,60,90", extra: str = "") -> Path:
    """The test config, with `extra` pipelines appended."""
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir(exist_ok=True)
    (skill_dir / "guide.md").write_text("Write plainly.\n")
    for name in ("reviewer", "fidelity"):
        (skill_dir / f"{name}.md").write_text(AGENT_FILE.format(name=name))
    config_file = tmp_path / "pipelines.toml"
    config_file.write_text(
        CONFIG.format(
            skill_dir=skill_dir,
            python=sys.executable,
            score_lint=json.dumps(SCORE_LINT),
            scores=scores,
        )
        + extra
    )
    return config_file


def edited_config(tmp_path: Path, old: str, new: str) -> Path:
    """The test config with one edit, which must apply."""
    config_file = write_config(tmp_path)
    text = config_file.read_text()
    assert old in text
    config_file.write_text(text.replace(old, new, 1))
    return config_file


def make_runner(
    config_file: Path, fake_claude: Path, stub_tasks_file: Path, out_dir: Path
) -> Runner:
    return Runner(
        load_config(config_file, str(fake_claude)), load_tasks([stub_tasks_file]), out_dir
    )


def run_all(
    tmp_path: Path, fake_claude: Path, stub_tasks_file: Path, scores: str = "50,60,90"
) -> Path:
    config = load_config(write_config(tmp_path, scores), str(fake_claude))
    out_dir = tmp_path / "generation"
    runner = Runner(config, load_tasks([stub_tasks_file]), out_dir)
    runner.run(["stub-kettle", "stub-bridge"], ["base", "variant", "solo"], jobs=1)
    return out_dir


def stage(out_dir: Path, task_id: str, pipeline: str, file_name: str) -> dict:
    return json.loads((out_dir / task_id / pipeline / f"{file_name}.json").read_text())


def logged_model(call: dict) -> str:
    return call["arguments"][call["arguments"].index("--model") + 1]


def stub_task(tasks_file: Path, task_id: str) -> Task:
    return next(task for task in load_tasks([tasks_file]) if task.task_id == task_id)


class TestPlan:
    def test_bounds_follow_the_stage_kinds(self, tmp_path: Path, fake_claude: Path) -> None:
        config = load_config(write_config(tmp_path, extra=BARE_PIPELINE), str(fake_claude))
        assert call_bounds(config) == {
            "base": {"fresh_agents": (3, 4), "author_turns": (1, 2)},
            "variant": {"fresh_agents": (1, 1), "author_turns": (2, 4)},
            "solo": {"fresh_agents": (1, 1), "author_turns": (1, 1)},
            "bare": {"fresh_agents": (1, 1), "author_turns": (0, 0)},
        }

    def test_totals_scale_with_tasks_and_count_the_fidelity_measurement(
        self, tmp_path: Path, fake_claude: Path
    ) -> None:
        config = load_config(write_config(tmp_path, extra=BARE_PIPELINE), str(fake_claude))
        plan = format_plan(config, task_count=2)
        assert "| bare | 1 to 1 | 0 to 0 |" in plan
        assert "| **all, 2 tasks** | 14 to 16 | 8 to 14 |" in plan


@dataclass(frozen=True)
class FullRun:
    root: Path
    out_dir: Path
    calls: list[dict]

    def prompts_starting(self, text: str) -> list[str]:
        return [call["prompt"] for call in self.calls if call["prompt"].startswith(text)]


@pytest.fixture(scope="class")
def full_run(tmp_path_factory: pytest.TempPathFactory) -> FullRun:
    """Every pipeline on both stub tasks, once for the tests that only read its outputs."""
    root = tmp_path_factory.mktemp("full-run")
    log_file = root / "claude-calls.jsonl"
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log_file))
        tasks_file = root / "tasks.toml"
        tasks_file.write_text(STUB_TASKS)
        out_dir = run_all(root, launcher(root, "claude", FAKES_DIR / "fake_claude.py"), tasks_file)
    calls = [json.loads(line) for line in log_file.read_text().splitlines()]
    return FullRun(root=root, out_dir=out_dir, calls=calls)


class TestFullRun:
    def test_writes_every_output_and_makes_the_expected_calls(self, full_run: FullRun) -> None:
        out_dir = full_run.out_dir
        assert len(full_run.calls) == 2 * CALLS_PER_TASK
        for task_id in ("stub-kettle", "stub-bridge"):
            for pipeline, last_stage in LAST_STAGES.items():
                final = (out_dir / task_id / pipeline / "final.md").read_text()
                assert final == stage(out_dir, task_id, pipeline, last_stage)["passage"] + "\n"
            assert stage(out_dir, task_id, "base", "00-draft")["word_count"] == 20
            fidelity = json.loads((out_dir / task_id / "fidelity.json").read_text())
            assert sorted(fidelity["labels"].values()) == ["base", "solo", "variant"]
            assert fidelity["unsupported"] == {
                name: int(label == "A") for label, name in fidelity["labels"].items()
            }

    def test_author_turns_fork_the_previous_author_session(self, full_run: FullRun) -> None:
        resumed = [call["arguments"] for call in full_run.calls if "--resume" in call["arguments"]]
        assert resumed and all("--fork-session" in arguments for arguments in resumed)
        draft = stage(full_run.out_dir, "stub-kettle", "base", "00-draft")
        apply_review = stage(full_run.out_dir, "stub-kettle", "base", "03-apply-review")
        gate = stage(full_run.out_dir, "stub-kettle", "base", "04-fidelity")
        resumed_ids = [arguments[arguments.index("--resume") + 1] for arguments in resumed]
        assert draft["session_id"] in resumed_ids and apply_review["session_id"] in resumed_ids
        assert (
            gate["triggered"]
            and gate["unsupported"] == 1
            and gate["passage"] != apply_review["passage"]
        )

    def test_a_shared_draft_is_drafted_once(self, full_run: FullRun) -> None:
        variant_draft = stage(full_run.out_dir, "stub-kettle", "variant", "00-draft")
        base_draft = stage(full_run.out_dir, "stub-kettle", "base", "00-draft")
        assert variant_draft["copied_from"] == "base"
        assert variant_draft["passage"] == base_draft["passage"]
        assert len(full_run.prompts_starting("You are drafting")) == 4  # base and solo, two tasks

    def test_every_draft_states_the_task_and_the_rules_of_the_run(self, full_run: FullRun) -> None:
        drafts = full_run.prompts_starting("You are drafting")
        for task_id in ("stub-kettle", "stub-bridge"):
            brief = task_brief(stub_task(full_run.root / "tasks.toml", task_id))
            task_drafts = [prompt for prompt in drafts if brief in prompt]
            assert len(task_drafts) == 2 and all(TASK_RULES in p for p in task_drafts), task_id

    def test_reviewers_see_only_what_their_stage_names(self, full_run: FullRun) -> None:
        reader_tests = full_run.prompts_starting("List the questions")
        assert reader_tests and all("Intended reader" not in prompt for prompt in reader_tests)
        assert all(
            "bimetal" not in prompt and "suspension" not in prompt for prompt in reader_tests
        )
        reviewer_prompts = [
            call["prompt"]
            for call in full_run.calls
            if "--append-system-prompt" in call["arguments"]
            and "You reviewer." in call["arguments"]
        ]
        assert reviewer_prompts and all("Intended reader" in prompt for prompt in reviewer_prompts)
        (kettle_review,) = [prompt for prompt in reviewer_prompts if "kettle" in prompt]
        assert "Document type: README section" in kettle_review and "bimetal" in kettle_review
        assert "[1]" not in kettle_review
        style_prompts = full_run.prompts_starting("Style pass.")
        assert style_prompts and all("Override for the variant." in p for p in style_prompts)

    def test_review_outputs_reach_the_author_turn_that_names_them(self, full_run: FullRun) -> None:
        reviewer = stage(full_run.out_dir, "stub-kettle", "base", "01-reviewer")["text"]
        reader_test = stage(full_run.out_dir, "stub-kettle", "base", "02-reader-test")["text"]
        (apply_review,) = [
            prompt
            for prompt in full_run.prompts_starting("Next step: apply-review.")
            if reviewer in prompt
        ]
        assert reader_test in apply_review

    def test_each_call_runs_on_the_model_its_config_names(self, full_run: FullRun) -> None:
        models_by_prompt_start = {
            "Style pass.": "sonnet",  # the stage's model over the author model
            "The earlier version is the source notes": "opus",  # [fidelity] over the agent file
            GATE_CHECK: "sonnet",  # the agent file's model
            "You are drafting": "opus",
        }
        for prompt_start, model in models_by_prompt_start.items():
            calls = [call for call in full_run.calls if call["prompt"].startswith(prompt_start)]
            assert calls and {logged_model(call) for call in calls} == {model}, prompt_start

    def test_named_files_are_listed_in_agent_and_author_prompts(self, full_run: FullRun) -> None:
        guide_line = f"- {full_run.root / 'skill' / 'guide.md'}\n"
        for prompt_start in ("Style pass.", "Next step: accept-style."):
            prompts = full_run.prompts_starting(prompt_start)
            assert prompts and all(guide_line in prompt for prompt in prompts), prompt_start

    def test_costs_add_up_per_pipeline_without_counting_a_shared_draft_twice(
        self, full_run: FullRun
    ) -> None:
        assert cost_summary(full_run.out_dir) == pytest.approx(
            {"base": 0.12, "variant": 0.08, "solo": 0.04, "fidelity measurement": 0.02}
        )

    def test_lint_loop_stops_once_the_score_clears(self, full_run: FullRun) -> None:
        loop_stage = stage(full_run.out_dir, "stub-kettle", "variant", "03-score-loop")
        assert loop_stage["author_turns"] == 2 and loop_stage["final_score"] == 90
        first_run = loop_stage["lint_runs"][0][0]
        assert first_run["stderr"] == "Installed 1 package in 3ms\n"
        assert json.loads(first_run["stdout"]) == {"score": 50.0}

    def test_lint_output_reaches_the_author(self, full_run: FullRun) -> None:
        lint_turns = full_run.prompts_starting("Next step: lint.")
        assert lint_turns and all("a finding" in p and "exit code 1" in p for p in lint_turns)


class TestRun:
    def test_lint_loop_stops_at_the_round_cap(
        self, tmp_path: Path, fake_claude: Path, stub_tasks_file: Path
    ) -> None:
        out_dir = run_all(tmp_path, fake_claude, stub_tasks_file, scores="50")
        loop_stage = stage(out_dir, "stub-kettle", "variant", "03-score-loop")
        assert loop_stage["author_turns"] == 3 and loop_stage["final_score"] == 50

    def test_rerun_after_a_failure_redoes_only_unfinished_stages(
        self,
        tmp_path: Path,
        fake_claude: Path,
        stub_tasks_file: Path,
        claude_calls,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("FAKE_CLAUDE_FAIL_ONCE_ON", "Next step: apply-review.")
        with pytest.raises(RuntimeError):
            run_all(tmp_path, fake_claude, stub_tasks_file)
        calls_before_rerun = len(claude_calls())
        assert calls_before_rerun == 4  # draft, two reviewers, then the failed author turn
        run_all(tmp_path, fake_claude, stub_tasks_file)
        assert len(claude_calls()) - calls_before_rerun == 2 * CALLS_PER_TASK - 3
        run_all(tmp_path, fake_claude, stub_tasks_file)
        assert len(claude_calls()) - calls_before_rerun == 2 * CALLS_PER_TASK - 3

    def test_a_lint_that_crashes_stops_the_run(
        self, tmp_path: Path, fake_claude: Path, stub_tasks_file: Path
    ) -> None:
        config_file = edited_config(tmp_path, "sys.exit(1)", "sys.exit(2)")
        out_dir = tmp_path / "out"
        runner = make_runner(config_file, fake_claude, stub_tasks_file, out_dir)
        with pytest.raises(RuntimeError):
            runner.run(["stub-kettle"], ["solo"], jobs=1)
        assert (out_dir / "stub-kettle" / "solo" / "00-draft.json").is_file()
        assert not (out_dir / "stub-kettle" / "solo" / "01-lint.json").exists()
        assert not (out_dir / "stub-kettle" / "solo" / "final.md").exists()

    def test_a_gate_check_outside_the_checker_form_stops_the_run(
        self,
        tmp_path: Path,
        fake_claude: Path,
        stub_tasks_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("FAKE_CLAUDE_GATE_OUTPUT", "- **UNSUPPORTED**: x")
        out_dir = tmp_path / "out"
        runner = make_runner(write_config(tmp_path), fake_claude, stub_tasks_file, out_dir)
        with pytest.raises(RuntimeError):
            runner.run(["stub-kettle"], ["base"], jobs=1)
        assert (out_dir / "stub-kettle" / "base" / "03-apply-review.json").is_file()
        assert not (out_dir / "stub-kettle" / "base" / "04-fidelity.json").exists()

    def test_a_call_served_by_another_model_stops_the_run(
        self,
        tmp_path: Path,
        fake_claude: Path,
        stub_tasks_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("FAKE_CLAUDE_SERVED_MODEL", "claude-sonnet-5-5")
        out_dir = tmp_path / "out"
        runner = make_runner(write_config(tmp_path), fake_claude, stub_tasks_file, out_dir)
        with pytest.raises(RuntimeError):
            runner.run(["stub-kettle"], ["solo"], jobs=1)
        assert not (out_dir / "stub-kettle" / "solo" / "00-draft.json").exists()


class TestBareDraft:
    def test_a_bare_draft_gets_the_task_but_no_guidance_tools_or_path_note(
        self, tmp_path: Path, fake_claude: Path, stub_tasks_file: Path, claude_calls
    ) -> None:
        config_file = write_config(tmp_path, extra=BARE_PIPELINE)
        out_dir = tmp_path / "out"
        make_runner(config_file, fake_claude, stub_tasks_file, out_dir).run(
            ["stub-kettle"], ["bare"], jobs=1
        )
        (call,) = claude_calls()
        arguments, prompt = call["arguments"], call["prompt"]
        assert arguments[arguments.index("--tools") + 1] == ""
        assert logged_model(call) == "opus"
        assert task_brief(stub_task(stub_tasks_file, "stub-kettle")) in prompt
        assert TASK_RULES in prompt
        for absent in ("guidance", "files", "Later turns", "Path note for the test."):
            assert absent not in prompt, absent
        draft = stage(out_dir, "stub-kettle", "bare", "00-draft")
        assert (out_dir / "stub-kettle" / "bare" / "final.md").read_text() == (
            draft["passage"] + "\n"
        )


class TestFidelityGate:
    def gate_run(
        self, tmp_path: Path, fake_claude: Path, stub_tasks_file: Path, config_file: Path
    ) -> tuple[dict, dict]:
        out_dir = tmp_path / "out"
        make_runner(config_file, fake_claude, stub_tasks_file, out_dir).run(
            ["stub-kettle"], ["base"], jobs=1
        )
        return (
            stage(out_dir, "stub-kettle", "base", "03-apply-review"),
            stage(out_dir, "stub-kettle", "base", "04-fidelity"),
        )

    def test_a_gate_below_its_threshold_runs_no_check(
        self, tmp_path: Path, fake_claude: Path, stub_tasks_file: Path, claude_calls
    ) -> None:
        config_file = edited_config(
            tmp_path,
            'compare_to = "draft"\n',
            'compare_to = "draft"\n  min_changed_sentences = 5\n',
        )
        apply_review, gate = self.gate_run(tmp_path, fake_claude, stub_tasks_file, config_file)
        assert gate["changed_sentences"] == 4 and not gate["triggered"]
        assert gate["unsupported"] == 0 and gate["calls"] == []
        assert gate["passage"] == apply_review["passage"]
        assert not [call for call in claude_calls() if call["prompt"].startswith(GATE_CHECK)]

    def test_a_clean_check_leaves_the_passage_alone(
        self,
        tmp_path: Path,
        fake_claude: Path,
        stub_tasks_file: Path,
        claude_calls,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("FAKE_CLAUDE_GATE_OUTPUT", "No changes in meaning.")
        apply_review, gate = self.gate_run(
            tmp_path, fake_claude, stub_tasks_file, write_config(tmp_path)
        )
        assert gate["triggered"] and gate["unsupported"] == 0
        assert [call["role"] for call in gate["calls"]] == ["agent"]
        assert gate["passage"] == apply_review["passage"]
        assert claude_calls()[-1]["prompt"].startswith(GATE_CHECK)


DRAFT_NO_READ = 'kind = "draft"\n  name = "draft"'
READS_NOTHING = DRAFT_NO_READ + "\n  read = []"


class TestConfigChecks:
    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ('inputs = ["reviewer", "reader-test"]', 'inputs = ["reviewer", "fidelity"]'),
            ('lint = ["score"]', 'lint = ["plain"]'),
            (
                'kind = "author"\n  name = "lint"\n  lint = ["plain"]',
                'kind = "bare_draft"\n  name = "lint"',
            ),
            ('from_pipeline = "base"', 'from_pipeline = "variant"'),
            ('kind = "copied_draft"\n  name = "draft"\n  from_pipeline = "base"', READS_NOTHING),
            ('name = "reviewer"\n', 'name = "reviewer"\n  brief = "Review it."\n'),
            ('kind = "agent"\n  name = "style"', 'kind = "critic"\n  name = "style"'),
            ('sees = ["passage"]\n  group', 'sees = ["passage", "mood"]\n  group'),
            ('name = "reader-test"', 'name = "reviewer"'),
            ('name = "solo"', 'name = "base"'),
            ('inputs = ["style"]', 'inputs = ["draft"]'),
            ('compare_to = "draft"', 'compare_to = "reviewer"'),
        ],
        ids=[
            "input-names-a-later-stage",
            "loop-lint-not-run",
            "second-draft",
            "draft-copied-from-a-copy",
            "draft-reads-nothing",
            "agent-file-and-brief",
            "unknown-kind",
            "sees-outside-the-list",
            "duplicate-stage",
            "duplicate-pipeline",
            "input-is-not-an-agent-stage",
            "gate-compares-to-a-review",
        ],
    )
    def test_a_config_error_stops_the_load(
        self, tmp_path: Path, fake_claude: Path, old: str, new: str
    ) -> None:
        with pytest.raises(ValueError):
            load_config(edited_config(tmp_path, old, new), str(fake_claude))

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ('brief = "Style pass."\n', 'brief = "Style pass."\n  lint = ["plain"]\n'),
            ('from_pipeline = "base"\n', 'from_pipeline = "base"\n  read = ["guide.md"]\n'),
            ('from_pipeline = "base"\n', 'from_pipeline = "base"\n  instructions = "Draft."\n'),
            ('  from_pipeline = "base"\n', ""),
            ('kind = "copied_draft"\n  name = "draft"\n  from_pipeline = "base"', DRAFT_NO_READ),
        ],
        ids=[
            "agent-stage-with-lint",
            "copied-draft-also-reads",
            "copied-draft-with-instructions",
            "copied-draft-without-a-source",
            "draft-without-read",
        ],
    )
    def test_a_key_its_kind_does_not_take_or_a_missing_required_key_stops_the_load(
        self, tmp_path: Path, fake_claude: Path, old: str, new: str
    ) -> None:
        with pytest.raises(TypeError):
            load_config(edited_config(tmp_path, old, new), str(fake_claude))


CHECKED = '- UNSUPPORTED: "a" (was: absent). Reason.\n- SUPPORTED: "b" (was: "c"). Reason.\n'
TWO_PASSAGES = {"A": "base", "B": "solo"}


class TestFidelityOutput:
    def test_counts_the_unsupported_lines(self) -> None:
        assert unsupported_count(CHECKED) == 1
        assert unsupported_count("No changes in meaning.\n") == 0

    @pytest.mark.parametrize("line", ["- **UNSUPPORTED**: x", "1. UNSUPPORTED: x", "Changes:"])
    def test_a_line_outside_the_checker_form_raises(self, line: str) -> None:
        with pytest.raises(RuntimeError):
            unsupported_count(CHECKED + line)

    def test_the_measurement_counts_each_passage_under_its_heading(self) -> None:
        text = f"## Passage A\n{CHECKED}\n## Passage B\nNo changes in meaning.\n"
        assert unsupported_by_passage(text, TWO_PASSAGES) == {"base": 1, "solo": 0}

    @pytest.mark.parametrize(
        "text",
        [
            "Preamble.\n## Passage A\nNo changes in meaning.\n## Passage B\nNo changes in meaning.",
            "## Passage A\nNo changes in meaning.\n## Passage A\n" + CHECKED,
            "## Passage A\n" + CHECKED + "## Passage A\nNo changes in meaning.\n"
            "## Passage B\nNo changes in meaning.",
            "## Passage A\n- **UNSUPPORTED**: x\n## Passage B\nNo changes in meaning.",
        ],
    )
    def test_measurement_output_outside_its_form_raises(self, text: str) -> None:
        with pytest.raises(RuntimeError):
            unsupported_by_passage(text, TWO_PASSAGES)

    def test_changed_sentences_are_counted_on_the_longer_side(self) -> None:
        earlier = "One. Two. Three. Four."
        assert changed_sentence_count(earlier, earlier) == 0
        assert changed_sentence_count(earlier, "One. Two changed. Three. Four.") == 1
        assert changed_sentence_count(earlier, "One. New a. New b. New c. Four.") == 3


class TestGuidanceIsRead:
    def test_a_named_file_that_does_not_exist_stops_the_config(
        self, tmp_path: Path, fake_claude: Path
    ) -> None:
        config_file = write_config(tmp_path)
        (tmp_path / "skill" / "guide.md").unlink()
        with pytest.raises(FileNotFoundError):
            load_config(config_file, str(fake_claude))

    @pytest.mark.parametrize(
        ("pipeline", "prompt_start", "stage_file"),
        [
            ("solo", "You are drafting", "00-draft"),
            ("variant", "Style pass.", "01-style"),
            ("variant", "Next step: accept-style.", "02-accept-style"),
        ],
    )
    def test_a_stage_that_skips_its_files_stops_the_run(
        self,
        tmp_path: Path,
        fake_claude: Path,
        stub_tasks_file: Path,
        monkeypatch: pytest.MonkeyPatch,
        pipeline: str,
        prompt_start: str,
        stage_file: str,
    ) -> None:
        monkeypatch.setenv("FAKE_CLAUDE_SKIP_READS", prompt_start)
        out_dir = tmp_path / "out"
        runner = make_runner(write_config(tmp_path), fake_claude, stub_tasks_file, out_dir)
        stage_name = stage_file.split("-", 1)[1]
        with pytest.raises(RuntimeError, match=f"stage {stage_name} did not read"):
            runner.run(["stub-kettle"], [pipeline], jobs=1)
        assert not (out_dir / "stub-kettle" / pipeline / f"{stage_file}.json").exists()
        assert not (out_dir / "stub-kettle" / pipeline / "final.md").exists()
