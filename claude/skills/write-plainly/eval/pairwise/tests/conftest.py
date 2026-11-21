import json
import sys
from pathlib import Path

import pytest

PAIRWISE_DIR = Path(__file__).resolve().parents[1]
FAKES_DIR = Path(__file__).resolve().parent / "fakes"
sys.path.insert(0, str(PAIRWISE_DIR))
SET_LETTERS = ("A", "B", "C")
SET_PIPELINES = ("kestrel-pipeline", "osprey-pipeline", "plover-pipeline")

STUB_TASKS = '''
[[task]]
id = "stub-kettle"
doc_type = "README section"
reader = "Ana, a new contributor who wants to know why the kettle switches itself off"
target_words = 180
notes = """
- the kettle switches off when the water boils [1]
- a bimetal strip bends when steam reaches it and opens the circuit [1]
"""
sources = ["[1] stub source"]

[[task]]
id = "stub-bridge"
doc_type = "Design-doc explanation"
reader = "Ben, an engineer choosing between two bridge designs"
target_words = 200
notes = """
- a suspension bridge hangs its deck from cables [1]
- an arch bridge carries its load in compression [1]
"""
sources = ["[1] stub source"]
'''


def launcher(directory: Path, name: str, script: Path) -> Path:
    """A shell script that runs `script` with this interpreter, so tests control the binary path."""
    path = directory / name
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    path.chmod(0o755)
    return path


@pytest.fixture
def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(tmp_path / "claude-calls.jsonl"))
    return launcher(tmp_path, "claude", FAKES_DIR / "fake_claude.py")


@pytest.fixture
def fake_codex(tmp_path: Path) -> Path:
    return launcher(tmp_path, "codex", FAKES_DIR / "fake_codex.py")


@pytest.fixture
def claude_calls(tmp_path: Path):
    """Read the fake claude's call log: a list of {"arguments": [...], "prompt": "..."}."""

    def read() -> list[dict]:
        log_file = tmp_path / "claude-calls.jsonl"
        if not log_file.exists():
            return []
        return [json.loads(line) for line in log_file.read_text().splitlines()]

    return read


def make_set(set_id: str) -> dict:
    return {
        "set_id": set_id,
        "doc_type": "README section",
        "reader": "Ana, who asks <why> & how",
        "passages": {
            letter: f'Passage {letter} of set {set_id} says 5 < 6 & "quotes" stay.'
            for letter in SET_LETTERS
        },
    }


@pytest.fixture
def sets_file(tmp_path: Path) -> Path:
    """Three sets of three passages, with a key beside them naming the pipelines."""
    path = tmp_path / "sets.jsonl"
    path.write_text("".join(json.dumps(make_set(set_id)) + "\n" for set_id in ("1", "2", "3")))
    key = {"sets": {set_id: dict(zip(SET_LETTERS, SET_PIPELINES)) for set_id in ("1", "2", "3")}}
    (tmp_path / "key.json").write_text(json.dumps(key))
    return path


@pytest.fixture
def stub_tasks_file(tmp_path: Path) -> Path:
    path = tmp_path / "tasks.toml"
    path.write_text(STUB_TASKS)
    return path
