import ast
import fcntl
import json
import os
import select
import struct
import subprocess
import sys
import termios
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from label import LEGEND, latest_labels, render, run_session, wrap_passage

LABEL_SCRIPT = Path(__file__).resolve().parents[1] / "label.py"
PASSAGE = (
    "The kettle switches off when the water boils.\n\n"
    "A bimetal strip bends when steam reaches it and opens the circuit, so the element stops heating."
)


@pytest.fixture
def pairs_file(tmp_path: Path) -> Path:
    pairs = [
        {
            "pair_id": f"0{n}",
            "doc_type": "README section",
            "reader": "Ana",
            "left": f"Left {n}.",
            "right": f"Right {n}.",
        }
        for n in (1, 2, 3)
    ]
    path = tmp_path / "pairs.jsonl"
    path.write_text("".join(json.dumps(pair) + "\n" for pair in pairs))
    return path


def scripted_session(
    pairs_file: Path,
    keys: list[str],
    notes: tuple[str, ...] = (),
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Run one labeling session on scripted keys and return everything it printed."""
    key_iterator, note_iterator = iter(keys), iter(notes)
    printed: list[str] = []
    pairs = [json.loads(line) for line in pairs_file.read_text().splitlines()]
    run_session(
        pairs=pairs,
        labels_file=pairs_file.parent / "labels.jsonl",
        read_key=lambda: next(key_iterator),
        read_line=lambda prompt: next(note_iterator),
        write=printed.append,
        terminal_width=lambda: 120,
        clock=clock,
    )
    return "".join(printed)


def choices(pairs_file: Path) -> dict[str, str]:
    return {
        pair_id: record["choice"]
        for pair_id, record in latest_labels(pairs_file.parent / "labels.jsonl").items()
    }


class TestSession:
    def test_each_answer_is_saved_before_the_next_pair(self, pairs_file: Path) -> None:
        output = scripted_session(pairs_file, ["1", "q"])
        assert choices(pairs_file) == {"01": "left"}
        assert "Stopped with 1 of 3 answered" in output

    def test_resume_starts_at_the_first_unanswered_pair(self, pairs_file: Path) -> None:
        scripted_session(pairs_file, ["1", "q"])
        output = scripted_session(pairs_file, ["\x1b[C", "t", "q"])
        assert "Left 1." not in output and "Left 2." in output
        assert choices(pairs_file) == {"01": "left", "02": "right", "03": "tie"}
        assert "All 3 pairs answered (0 skipped)" in output

    def test_a_note_and_the_seconds_spent_are_stored_with_the_answer(
        self, pairs_file: Path
    ) -> None:
        clock = iter([10.0, 12.5, 20.0]).__next__  # pair 1 shown, pair 1 answered, pair 2 shown
        scripted_session(pairs_file, ["n", "2", "q"], notes=("close call\n",), clock=clock)
        record = latest_labels(pairs_file.parent / "labels.jsonl")["01"]
        assert record["choice"] == "right" and record["note"] == "close call"
        assert record["seconds"] == 2.5

    def test_back_reopens_the_previous_pair_and_the_new_answer_wins(self, pairs_file: Path) -> None:
        scripted_session(pairs_file, ["1", "u", "2", "q"])
        lines = (pairs_file.parent / "labels.jsonl").read_text().splitlines()
        assert [json.loads(line)["choice"] for line in lines] == ["left", "right"]
        assert choices(pairs_file) == {"01": "right"}

    def test_skipped_pairs_come_back_after_unanswered_ones(self, pairs_file: Path) -> None:
        scripted_session(pairs_file, ["s", "1", "q"])
        output = scripted_session(pairs_file, ["2", "1", "q"])
        assert output.index("Left 3.") < output.index("Left 1.")
        assert choices(pairs_file) == {"01": "left", "02": "left", "03": "right"}

    def test_back_after_the_last_pair_reopens_it_and_the_new_answer_wins(
        self, pairs_file: Path
    ) -> None:
        output = scripted_session(pairs_file, ["1", "2", "t", "x", "u", "2", "q"])
        assert output.count("All 3 pairs answered") == 2
        assert output.rindex("Left 3.") > output.index("All 3 pairs answered")
        assert choices(pairs_file) == {"01": "left", "02": "right", "03": "right"}

    def test_unknown_keys_are_ignored(self, pairs_file: Path) -> None:
        scripted_session(pairs_file, ["x", "u", "1", "q"])
        assert choices(pairs_file) == {"01": "left"}


class TestScreen:
    def test_wide_terminals_show_the_passages_side_by_side(self) -> None:
        pair = {
            "pair_id": "01",
            "doc_type": "README section",
            "reader": "Ana",
            "left": PASSAGE,
            "right": PASSAGE,
        }
        screen = render(pair, 0, 30, "", 120)
        assert "LEFT" in screen and "│ RIGHT" in screen
        assert max(len(line) for line in screen.splitlines()) <= 120

    def test_narrow_terminals_stack_the_passages(self) -> None:
        pair = {
            "pair_id": "01",
            "doc_type": "README section",
            "reader": "Ana",
            "left": PASSAGE,
            "right": PASSAGE,
        }
        screen = render(pair, 0, 30, "a note", 60)
        assert "│" not in screen and screen.index("LEFT") < screen.index("RIGHT")
        assert "note: a note" in screen and max(len(line) for line in screen.splitlines()) <= 60

    def test_wrapping_keeps_paragraphs_and_list_items(self) -> None:
        lines = wrap_passage(
            "First paragraph\ncontinues here.\n\n- item one\n- item two is long enough", 16
        )
        assert lines[:2] == ["First paragraph", "continues here."]
        assert lines[2] == "" and lines[3] == "- item one" and lines[4].startswith("- item two")
        assert lines[5].startswith("  ")


class TestCommand:
    def test_parses_as_python_3_9(self) -> None:
        ast.parse(LABEL_SCRIPT.read_text(), feature_version=(3, 9))

    def read_until(
        self, master: int, buffer: bytearray, text: str, occurrences: int, timeout_s: float = 10
    ) -> None:
        deadline = time.monotonic() + timeout_s
        while buffer.decode(errors="replace").count(text) < occurrences:
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"waited for {text!r} x{occurrences}; screen so far:\n{buffer.decode()[-500:]}"
                )
            if select.select([master], [], [], 0.1)[0]:
                buffer.extend(os.read(master, 65536))

    def test_real_keypresses_in_a_terminal(self, pairs_file: Path) -> None:
        master, worker = os.openpty()
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))
        process = subprocess.Popen(
            [sys.executable, str(LABEL_SCRIPT), str(pairs_file)],
            stdin=worker,
            stdout=worker,
            stderr=worker,
            env={
                key: value for key, value in os.environ.items() if key not in {"COLUMNS", "LINES"}
            },
        )
        os.close(worker)
        screen = bytearray()
        try:
            self.read_until(master, screen, LEGEND, 1)
            os.write(master, b"1")
            self.read_until(master, screen, LEGEND, 2)
            os.write(master, b"n")
            self.read_until(master, screen, "note: ", 1)
            os.write(master, b"close call\r")
            self.read_until(master, screen, "note: close call", 1)
            os.write(master, b"\x1b[C")
            self.read_until(master, screen, "Left 3.", 1)
            os.write(master, b"q")
            self.read_until(master, screen, "Stopped with 2 of 3 answered", 1)
            assert process.wait(timeout=10) == 0
        finally:
            process.kill()
            process.wait()
            os.close(master)
        assert "│ RIGHT" in screen.decode()
        records = latest_labels(pairs_file.parent / "labels.jsonl")
        assert records["01"]["choice"] == "left"
        assert records["02"]["choice"] == "right" and records["02"]["note"] == "close call"
