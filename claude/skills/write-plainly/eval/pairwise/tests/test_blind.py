import json
import subprocess
import sys
from collections import Counter
from itertools import pairwise
from pathlib import Path

import pytest

from blind import build_pairs
from common import Task

BASE = "merged"
OTHERS = ["current", "merged-style-pass", "merged-loose-paragraphs"]
PAIRWISE_DIR = Path(__file__).resolve().parents[1]


def make_tasks(count: int) -> list[Task]:
    return [
        Task(f"task-{index}", "README section", f"Reader {index}", 200, "- a fact", ("[1] stub",))
        for index in range(count)
    ]


def make_passages(tasks: list[Task]) -> dict[tuple[str, str], str]:
    return {(t.task_id, p): f"{p} passage for {t.task_id}." for t in tasks for p in [BASE, *OTHERS]}


@pytest.fixture
def ten_task_design() -> tuple[list[dict], dict, list[Task]]:
    tasks = make_tasks(10)
    pairs, key = build_pairs(tasks, make_passages(tasks), BASE, OTHERS, seed=11)
    return pairs, key, tasks


class TestDesign:
    def test_every_task_has_one_pair_per_comparison(self, ten_task_design) -> None:
        pairs, key, tasks = ten_task_design
        assert len(pairs) == 30
        cells = Counter((entry["task_id"], entry["comparison"]) for entry in key["pairs"].values())
        assert set(cells) == {(t.task_id, other) for t in tasks for other in OTHERS}
        assert set(cells.values()) == {1}

    def test_each_pair_puts_the_base_against_its_comparison(self, ten_task_design) -> None:
        pairs, key, _ = ten_task_design
        for pair in pairs:
            entry = key["pairs"][pair["pair_id"]]
            assert {entry["left_pipeline"], entry["right_pipeline"]} == {BASE, entry["comparison"]}
            assert pair["left"] == f"{entry['left_pipeline']} passage for {entry['task_id']}."

    def test_base_is_on_the_left_in_half_of_each_comparison(self, ten_task_design) -> None:
        _, key, _ = ten_task_design
        left_counts = Counter(
            e["comparison"] for e in key["pairs"].values() if e["left_pipeline"] == BASE
        )
        assert left_counts == dict.fromkeys(OTHERS, 5)

    def test_a_tasks_pairs_are_spread_out_and_first_showings_come_first(
        self, ten_task_design
    ) -> None:
        pairs, key, _ = ten_task_design
        positions: dict[str, list[int]] = {}
        for position, pair in enumerate(pairs):
            positions.setdefault(key["pairs"][pair["pair_id"]]["task_id"], []).append(position)
        gaps = [
            later - earlier for spots in positions.values() for earlier, later in pairwise(spots)
        ]
        assert min(gaps) >= 4
        assert sorted(task_positions[0] for task_positions in positions.values()) == list(range(10))
        first_round = Counter(e["comparison"] for e in key["pairs"].values() if e["round"] == 0)
        assert sorted(first_round.values()) == [3, 3, 4]

    def test_the_seed_fixes_the_design(self) -> None:
        tasks = make_tasks(10)
        first = build_pairs(tasks, make_passages(tasks), BASE, OTHERS, seed=11)
        assert build_pairs(tasks, make_passages(tasks), BASE, OTHERS, seed=11) == first
        assert build_pairs(tasks, make_passages(tasks), BASE, OTHERS, seed=12) != first

    def test_what_the_labeler_sees_names_no_pipeline_or_task(self, ten_task_design) -> None:
        pairs, _, _ = ten_task_design
        for pair in pairs:
            assert set(pair) == {"pair_id", "doc_type", "reader", "left", "right"}
            assert pair["pair_id"].isdigit()
        shown_ids = [pair["pair_id"] for pair in pairs]
        assert shown_ids == sorted(shown_ids)


class TestCommand:
    def write_generation(self, tmp_path: Path, stub_tasks_file: Path) -> Path:
        generation = tmp_path / "generation"
        for task_id in ("stub-kettle", "stub-bridge"):
            for pipeline in (BASE, "current"):
                (generation / task_id / pipeline).mkdir(parents=True)
                (generation / task_id / pipeline / "final.md").write_text(
                    f"{pipeline} on {task_id}.\n"
                )
        return generation

    def blind(
        self, tmp_path: Path, stub_tasks_file: Path, generation: Path
    ) -> subprocess.CompletedProcess:
        command = [
            sys.executable, str(PAIRWISE_DIR / "blind.py"), "--generation", str(generation),
            "--tasks", str(stub_tasks_file), "--base", BASE, "--others", "current",
            "--seed", "3", "--out", str(tmp_path / "eval"),
        ]  # fmt: skip
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def test_writes_pairs_and_a_separate_key(self, tmp_path: Path, stub_tasks_file: Path) -> None:
        generation = self.write_generation(tmp_path, stub_tasks_file)
        completed = self.blind(tmp_path, stub_tasks_file, generation)
        assert completed.returncode == 0, completed.stderr
        pairs = [
            json.loads(line)
            for line in (tmp_path / "eval" / "pairs.jsonl").read_text().splitlines()
        ]
        key = json.loads((tmp_path / "eval" / "key.json").read_text())
        assert len(pairs) == 2 and set(key["pairs"]) == {"01", "02"}
        assert "estimated reading time" in completed.stderr

    def test_refuses_to_overwrite_pairs_that_labels_may_refer_to(
        self, tmp_path: Path, stub_tasks_file: Path
    ) -> None:
        generation = self.write_generation(tmp_path, stub_tasks_file)
        self.blind(tmp_path, stub_tasks_file, generation)
        completed = self.blind(tmp_path, stub_tasks_file, generation)
        assert completed.returncode != 0 and "FileExistsError" in completed.stderr
