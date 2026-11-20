import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import agents
from judges import batch_text, checked_verdicts

PAIRWISE_DIR = Path(__file__).resolve().parents[1]
PAIRS = [
    {
        "pair_id": f"0{n}",
        "doc_type": "README section",
        "reader": "Ana",
        "left": f"L{n}",
        "right": f"R{n}",
    }
    for n in (1, 2, 3)
]
RESULT_FILES = {
    f"{judge}-{order}-{batch:02d}.json"
    for judge in ("opus", "codex")
    for order in ("shown", "swapped")
    for batch in (0, 1)
}


def judge(
    tmp_path: Path, fake_claude: Path, fake_codex: Path, *extra: str
) -> subprocess.CompletedProcess:
    """Run judges.py from tmp_path with relative paths, as a person would, on the fakes."""
    (tmp_path / "pairs.jsonl").write_text("".join(json.dumps(pair) + "\n" for pair in PAIRS))
    (tmp_path / "SKILL.md").write_text("Write plainly.\n")
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    (home / ".codex" / "review.config.toml").write_text('sandbox_mode = "read-only"\n')
    command = [
        sys.executable, str(PAIRWISE_DIR / "judges.py"), "--pairs", "pairs.jsonl",
        "--skill", "SKILL.md", "--out", "judges", "--seed", "5", "--batch-size", "2",
        "--effort", "low", "--claude-bin", str(fake_claude), "--codex-bin", str(fake_codex),
        *extra,
    ]  # fmt: skip
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        command, cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )


def picks(out_dir: Path, judge_name: str, order: str) -> dict[str, str]:
    verdicts = [
        verdict
        for result_file in out_dir.glob(f"{judge_name}-{order}-*.json")
        for verdict in json.loads(result_file.read_text())["verdicts"]
    ]
    return {verdict["pair_id"]: verdict["pick"] for verdict in verdicts}


class TestCommand:
    def test_both_judges_see_both_orders_and_picks_are_in_the_pairs_file_orientation(
        self, tmp_path: Path, fake_claude: Path, fake_codex: Path, claude_calls
    ) -> None:
        completed = judge(tmp_path, fake_claude, fake_codex)
        assert completed.returncode == 0, completed.stderr
        out_dir = tmp_path / "judges"
        assert {path.name for path in out_dir.glob("*.json")} == RESULT_FILES
        assert picks(out_dir, "opus", "shown") == dict.fromkeys(("01", "02", "03"), "left")
        assert picks(out_dir, "opus", "swapped") == dict.fromkeys(("01", "02", "03"), "right")
        assert picks(out_dir, "codex", "shown") == dict.fromkeys(("01", "02", "03"), "right")
        assert picks(out_dir, "codex", "swapped") == dict.fromkeys(("01", "02", "03"), "left")
        assert len(claude_calls()) == 4  # two batches of at most two pairs, two orders
        assert all("--safe-mode" in call["arguments"] for call in claude_calls())
        skill_line = f"- {(tmp_path / 'SKILL.md').resolve()}\n"
        assert all(skill_line in call["prompt"] for call in claude_calls())

    def test_a_rerun_skips_batches_already_judged(
        self, tmp_path: Path, fake_claude: Path, fake_codex: Path, claude_calls
    ) -> None:
        judge(tmp_path, fake_claude, fake_codex)
        completed = judge(tmp_path, fake_claude, fake_codex)
        assert completed.returncode == 0, completed.stderr
        assert len(claude_calls()) == 4

    def test_a_judged_batch_holding_other_pairs_stops_the_run(
        self, tmp_path: Path, fake_claude: Path, fake_codex: Path
    ) -> None:
        judge(tmp_path, fake_claude, fake_codex, "--only", "01")
        completed = judge(tmp_path, fake_claude, fake_codex)
        assert completed.returncode != 0 and "RuntimeError" in completed.stderr

    def test_an_opus_judge_that_skips_the_guidance_stops_the_run(
        self,
        tmp_path: Path,
        fake_claude: Path,
        fake_codex: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("FAKE_CLAUDE_SKIP_READS", "You are judging")
        completed = judge(tmp_path, fake_claude, fake_codex, "--judges", "opus")
        assert completed.returncode != 0 and "RuntimeError" in completed.stderr
        assert not list((tmp_path / "judges").glob("*.json"))


class TestVerdicts:
    def test_the_swapped_batch_shows_each_pair_reversed(self) -> None:
        text = batch_text(PAIRS[:1], "swapped")
        assert text.index("### Left\n\nR1") < text.index("### Right\n\nL1")

    def test_verdicts_must_cover_exactly_the_batch(self) -> None:
        with pytest.raises(RuntimeError):
            checked_verdicts(
                [{"pair_id": "01", "choice": "left", "reason": ""}], ["01", "02"], "shown"
            )
        with pytest.raises(RuntimeError):
            checked_verdicts([{"pair_id": "01", "choice": "both", "reason": ""}], ["01"], "shown")


class TestCodex:
    def test_codex_refuses_to_run_without_the_read_only_profile(
        self, tmp_path: Path, fake_codex: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(agents, "CODEX_REVIEW_PROFILE", tmp_path / "missing.toml")
        with pytest.raises(FileNotFoundError):
            agents.run_codex("prompt", tmp_path, tmp_path / "out.txt", str(fake_codex), 60)
