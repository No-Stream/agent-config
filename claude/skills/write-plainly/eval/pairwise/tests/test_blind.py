import json
import subprocess
import sys
from pathlib import Path

import pytest

from blind import build_sets
from common import Task, passage_digest

PIPELINES = ["current", "merged", "merged-style-pass", "merged-loose-paragraphs", "no-skill"]
PAIRWISE_DIR = Path(__file__).resolve().parents[1]


def make_tasks(count: int) -> list[Task]:
    return [
        Task(f"task-{index}", "README section", f"Reader {index}", 200, "- a fact", ("[1] stub",))
        for index in range(count)
    ]


def make_passages(tasks: list[Task]) -> dict[tuple[str, str], str]:
    return {(t.task_id, p): f"{p} passage for {t.task_id}." for t in tasks for p in PIPELINES}


@pytest.fixture
def ten_task_design() -> tuple[list[dict], dict, list[Task]]:
    tasks = make_tasks(10)
    sets, key = build_sets(tasks, make_passages(tasks), PIPELINES, seed=11)
    return sets, key, tasks


class TestDesign:
    def test_each_task_is_one_set_holding_every_pipeline_once(self, ten_task_design) -> None:
        sets, key, tasks = ten_task_design
        assert sorted(entry["task_id"] for entry in key["sets"].values()) == sorted(
            task.task_id for task in tasks
        )
        for passage_set in sets:
            entry = key["sets"][passage_set["set_id"]]
            assert list(passage_set["passages"]) == ["A", "B", "C", "D", "E"]
            assert sorted(entry["pipelines"].values()) == sorted(PIPELINES)
            for letter, pipeline in entry["pipelines"].items():
                expected = f"{pipeline} passage for {entry['task_id']}."
                assert passage_set["passages"][letter] == expected
                assert entry["sha256"][letter] == passage_digest(expected)

    def test_letters_and_task_order_are_shuffled(self, ten_task_design) -> None:
        sets, key, tasks = ten_task_design
        letter_orders = {tuple(entry["pipelines"].values()) for entry in key["sets"].values()}
        assert len(letter_orders) > 1
        shown_tasks = [key["sets"][passage_set["set_id"]]["task_id"] for passage_set in sets]
        assert shown_tasks != [task.task_id for task in tasks]

    def test_the_seed_fixes_the_design(self) -> None:
        tasks = make_tasks(10)
        first = build_sets(tasks, make_passages(tasks), PIPELINES, seed=11)
        assert build_sets(tasks, make_passages(tasks), PIPELINES, seed=11) == first
        assert build_sets(tasks, make_passages(tasks), PIPELINES, seed=12) != first

    def test_what_the_labeler_sees_names_no_pipeline_or_task(self, ten_task_design) -> None:
        sets, _, _ = ten_task_design
        for passage_set in sets:
            assert set(passage_set) == {"set_id", "doc_type", "reader", "passages"}
        assert [passage_set["set_id"] for passage_set in sets] == [str(n) for n in range(1, 11)]


class TestCommand:
    def write_generation(self, tmp_path: Path) -> Path:
        generation = tmp_path / "generation"
        for task_id in ("stub-kettle", "stub-bridge"):
            for pipeline in ("merged", "current"):
                (generation / task_id / pipeline).mkdir(parents=True)
                (generation / task_id / pipeline / "final.md").write_text(
                    f"{pipeline} on {task_id}.\n"
                )
        return generation

    def blind(
        self, tmp_path: Path, stub_tasks_file: Path, generation: Path, *extra: str
    ) -> subprocess.CompletedProcess:
        command = [
            sys.executable, str(PAIRWISE_DIR / "blind.py"), "--generation", str(generation),
            "--tasks", str(stub_tasks_file), "--pipelines", "merged", "current",
            "--seed", "3", "--out", str(tmp_path / "eval"), *extra,
        ]  # fmt: skip
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def read_sets(self, tmp_path: Path) -> list[dict]:
        sets_file = tmp_path / "eval" / "sets.jsonl"
        return [json.loads(line) for line in sets_file.read_text().splitlines()]

    def test_writes_sets_and_a_separate_key(self, tmp_path: Path, stub_tasks_file: Path) -> None:
        completed = self.blind(tmp_path, stub_tasks_file, self.write_generation(tmp_path))
        assert completed.returncode == 0, completed.stderr
        key = json.loads((tmp_path / "eval" / "key.json").read_text())
        for passage_set in self.read_sets(tmp_path):
            task_id = key["sets"][passage_set["set_id"]]["task_id"]
            expected = [f"current on {task_id}.", f"merged on {task_id}."]
            assert sorted(passage_set["passages"].values()) == expected
        assert set(key["sets"]) == {"1", "2"}
        assert "estimated reading time" in completed.stderr

    def test_only_task_limits_the_sets(self, tmp_path: Path, stub_tasks_file: Path) -> None:
        generation = self.write_generation(tmp_path)
        completed = self.blind(tmp_path, stub_tasks_file, generation, "--only-task", "stub-bridge")
        assert completed.returncode == 0, completed.stderr
        (only_set,) = self.read_sets(tmp_path)
        assert sorted(only_set["passages"].values()) == [
            "current on stub-bridge.",
            "merged on stub-bridge.",
        ]
        key = json.loads((tmp_path / "eval" / "key.json").read_text())
        assert [entry["task_id"] for entry in key["sets"].values()] == ["stub-bridge"]

    def test_only_task_naming_an_unknown_task_writes_nothing(
        self, tmp_path: Path, stub_tasks_file: Path
    ) -> None:
        generation = self.write_generation(tmp_path)
        completed = self.blind(tmp_path, stub_tasks_file, generation, "--only-task", "stub-ferry")
        assert completed.returncode != 0 and "ValueError" in completed.stderr
        assert not (tmp_path / "eval").exists()

    def test_refuses_to_overwrite_sets_that_rankings_may_refer_to(
        self, tmp_path: Path, stub_tasks_file: Path
    ) -> None:
        generation = self.write_generation(tmp_path)
        self.blind(tmp_path, stub_tasks_file, generation)
        completed = self.blind(tmp_path, stub_tasks_file, generation)
        assert completed.returncode != 0 and "FileExistsError" in completed.stderr
