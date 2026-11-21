import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import agents
from judges import letter_orders, order_agreement, ranking_in_set_letters, set_text

PAIRWISE_DIR = Path(__file__).resolve().parents[1]
LETTERS = ["A", "B", "C", "D", "E"]
SETS = [
    {
        "set_id": str(n),
        "doc_type": "README section",
        "reader": "Ana",
        "passages": {letter: f"Passage {letter}{n}." for letter in LETTERS},
    }
    for n in (1, 2, 3)
]


def judge(
    tmp_path: Path, fake_claude: Path, fake_codex: Path, *extra: str, sets: list[dict] = SETS
) -> subprocess.CompletedProcess:
    """Run judges.py from tmp_path with relative paths, as a person would, on the fakes."""
    (tmp_path / "sets.jsonl").write_text("".join(json.dumps(s) + "\n" for s in sets))
    (tmp_path / "SKILL.md").write_text("Write plainly.\n")
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    (home / ".codex" / "review.config.toml").write_text('sandbox_mode = "read-only"\n')
    command = [
        sys.executable, str(PAIRWISE_DIR / "judges.py"), "--sets", "sets.jsonl",
        "--skill", "SKILL.md", "--out", "judges", "--seed", "5", "--effort", "low",
        "--claude-bin", str(fake_claude), "--codex-bin", str(fake_codex), *extra,
    ]  # fmt: skip
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        command, cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )


def recorded(out_dir: Path, judge_name: str, order: str) -> dict[str, dict]:
    records = [
        json.loads(path.read_text()) for path in out_dir.glob(f"{judge_name}-{order}-set*.json")
    ]
    return {record["set_id"]: record for record in records}


class TestCommand:
    def test_both_judges_rank_every_set_in_both_orders_in_the_sets_file_letters(
        self, tmp_path: Path, fake_claude: Path, fake_codex: Path, claude_calls
    ) -> None:
        completed = judge(tmp_path, fake_claude, fake_codex)
        assert completed.returncode == 0, completed.stderr
        out_dir = tmp_path / "judges"
        for passage_set in SETS:
            orders = letter_orders(passage_set["set_id"], LETTERS, seed=5)
            opus = {o: recorded(out_dir, "opus", o)[passage_set["set_id"]] for o in orders}
            codex = {o: recorded(out_dir, "codex", o)[passage_set["set_id"]] for o in orders}
            for order, shown in orders.items():
                # the fake claude ranks in the order shown, the fake codex in reverse
                assert opus[order]["ranking"] == "".join(shown)
                assert codex[order]["ranking"] == "".join(reversed(shown))
        assert len(claude_calls()) == 6  # three sets, two orders
        assert all("--safe-mode" in call["arguments"] for call in claude_calls())
        skill_line = f"- {(tmp_path / 'SKILL.md').resolve()}\n"
        assert all(skill_line in call["prompt"] for call in claude_calls())
        assert "opus: Kendall tau between the two orders' rankings, mean -1.00" in completed.stderr

    def test_a_rerun_skips_sets_already_ranked(
        self, tmp_path: Path, fake_claude: Path, fake_codex: Path, claude_calls
    ) -> None:
        judge(tmp_path, fake_claude, fake_codex)
        completed = judge(tmp_path, fake_claude, fake_codex)
        assert completed.returncode == 0, completed.stderr
        assert len(claude_calls()) == 6

    def test_a_ranked_set_on_disk_that_differs_from_the_set_stops_the_run(
        self, tmp_path: Path, fake_claude: Path, fake_codex: Path
    ) -> None:
        judge(tmp_path, fake_claude, fake_codex)
        edited = [{**SETS[0], "passages": {**SETS[0]["passages"], "A": "Edited."}}, *SETS[1:]]
        completed = judge(tmp_path, fake_claude, fake_codex, sets=edited)
        assert completed.returncode != 0 and "RuntimeError" in completed.stderr

    def test_an_opus_judge_that_skips_the_guidance_stops_the_run(
        self,
        tmp_path: Path,
        fake_claude: Path,
        fake_codex: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("FAKE_CLAUDE_SKIP_READS", "You are ranking")
        completed = judge(tmp_path, fake_claude, fake_codex, "--judges", "opus")
        assert completed.returncode != 0 and "RuntimeError" in completed.stderr
        assert not list((tmp_path / "judges").glob("*.json"))


class TestOrders:
    def test_the_second_order_reverses_the_first(self) -> None:
        orders = letter_orders("1", LETTERS, seed=5)
        assert sorted(orders["drawn"]) == LETTERS
        assert orders["reversed"] == orders["drawn"][::-1]

    def test_the_judge_sees_each_passage_under_its_shown_letter(self) -> None:
        text = set_text(SETS[0], ["C", "A", "B", "E", "D"])
        assert text.index("### Passage A\n\nPassage C1.") < text.index(
            "### Passage B\n\nPassage A1."
        )
        assert "Intended reader: Ana" in text

    def test_a_ranking_in_shown_letters_maps_back_to_set_letters(self) -> None:
        shown = ["C", "A", "B", "E", "D"]
        assert ranking_in_set_letters("AB=CED", shown) == "CA=BDE"

    def test_a_ranking_that_misses_a_passage_is_refused(self) -> None:
        with pytest.raises(ValueError):
            ranking_in_set_letters("ABCD", ["C", "A", "B", "E", "D"])


class TestOrderAgreement:
    def test_one_tied_judgment_written_in_two_within_tie_orders_is_identical(self) -> None:
        orders = letter_orders("1", LETTERS, seed=5)
        records = [
            {"set_id": "1", "order": order, "shown": orders[order], "ranking": ranking}
            for order, ranking in (("drawn", "CA=BDE"), ("reversed", "CB=ADE"))
        ]
        assert order_agreement(records) == ([pytest.approx(1.0)], 1)


class TestCodex:
    def test_codex_refuses_to_run_without_the_read_only_profile(
        self, tmp_path: Path, fake_codex: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(agents, "CODEX_REVIEW_PROFILE", tmp_path / "missing.toml")
        with pytest.raises(FileNotFoundError):
            agents.run_codex("prompt", tmp_path, tmp_path / "out.txt", str(fake_codex), 60)
