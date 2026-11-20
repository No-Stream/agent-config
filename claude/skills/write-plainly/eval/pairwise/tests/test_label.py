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

from label import (
    LEGEND,
    Console,
    latest_rankings,
    load_sets,
    parse_ranking,
    ranks,
    render_passage,
    render_ranking_screen,
    run_session,
    wrap_passage,
)

LABEL_SCRIPT = Path(__file__).resolve().parents[1] / "label.py"
LETTERS = ("A", "B", "C", "D", "E")
PASSAGE = (
    "The kettle switches off when the water boils.\n\n"
    "A bimetal strip bends when steam reaches it and opens the circuit, so the element stops heating."
)


def make_set(set_id: str) -> dict:
    return {
        "set_id": set_id,
        "doc_type": "README section",
        "reader": "Ana",
        "passages": {letter: f"Passage {letter} of set {set_id}." for letter in LETTERS},
    }


@pytest.fixture
def sets_file(tmp_path: Path) -> Path:
    path = tmp_path / "sets.jsonl"
    path.write_text("".join(json.dumps(make_set(set_id)) + "\n" for set_id in ("1", "2", "3")))
    return path


def scripted_session(
    sets_file: Path,
    keys: list[str],
    lines: tuple[str, ...] = (),
    clock: Callable[[], float] = time.monotonic,
) -> str:
    """Run one labeling session on scripted keys and typed lines; return everything it printed."""
    key_iterator, line_iterator = iter(keys), iter(lines)
    printed: list[str] = []
    console = Console(
        read_key=lambda: next(key_iterator),
        read_line=lambda prompt: next(line_iterator),
        write=printed.append,
        width=lambda: 80,
        clock=clock,
    )
    run_session(load_sets(sets_file), sets_file.parent / "rankings.jsonl", console)
    return "".join(printed)


def rankings(sets_file: Path) -> dict[str, str]:
    return {
        set_id: record["ranking"]
        for set_id, record in latest_rankings(sets_file.parent / "rankings.jsonl").items()
    }


class TestRanking:
    def test_letters_best_first_with_equals_joining_a_tie(self) -> None:
        assert parse_ranking("CA=EBD", LETTERS) == [["C"], ["A", "E"], ["B"], ["D"]]

    def test_lower_case_and_spaces_are_accepted(self) -> None:
        assert parse_ranking(" ca = e bd ", LETTERS) == [["C"], ["A", "E"], ["B"], ["D"]]

    @pytest.mark.parametrize(
        "typed",
        ["CAEB", "CAEBDD", "CAEBF", "=CAEBD", "CAEBD=", "CA==EBD", "A=B=C=D=E", "CA1EBD"],
    )
    def test_a_ranking_must_place_each_letter_once_in_at_least_two_places(self, typed: str) -> None:
        with pytest.raises(ValueError):
            parse_ranking(typed, LETTERS)

    def test_tied_letters_share_the_mean_of_their_places(self) -> None:
        assert ranks([["C"], ["A", "E"], ["B"], ["D"]]) == {
            "C": 1.0,
            "A": 2.5,
            "E": 2.5,
            "B": 4.0,
            "D": 5.0,
        }


class TestSession:
    def test_each_ranking_is_saved_before_the_next_task(self, sets_file: Path) -> None:
        output = scripted_session(sets_file, ["r", "q"], lines=("cabed", "", "q"))
        assert rankings(sets_file) == {"1": "CABED"}
        assert "Stopped with 1 of 3 tasks ranked" in output

    def test_passages_are_shown_one_at_a_time_and_page_both_ways(self, sets_file: Path) -> None:
        output = scripted_session(sets_file, ["n", "\x1b[C", "p", "\x1b[D", "q"])
        shown = [
            next(letter for letter in LETTERS if f"Passage {letter} of set 1." in screen)
            for screen in output.split("\x1b[2J")[1:]
        ]
        assert shown == ["A", "B", "C", "B", "A"]

    def test_next_on_the_last_passage_opens_the_ranking_prompt(self, sets_file: Path) -> None:
        scripted_session(sets_file, ["n"] * 5 + ["q"], lines=("ABCDE", "", "q"))
        assert rankings(sets_file) == {"1": "ABCDE"}

    def test_resume_starts_at_the_first_unranked_task(self, sets_file: Path) -> None:
        scripted_session(sets_file, ["r", "q"], lines=("ABCDE", ""))
        output = scripted_session(sets_file, ["r", "r", "q"], lines=("EDCBA", "", "B=ACDE", ""))
        assert "of set 1." not in output and "Passage A of set 2." in output
        assert rankings(sets_file) == {"1": "ABCDE", "2": "EDCBA", "3": "B=ACDE"}
        assert "All 3 tasks ranked" in output

    def test_an_invalid_ranking_is_refused_and_asked_again(self, sets_file: Path) -> None:
        scripted_session(sets_file, ["r", "q"], lines=("ABCD", "ABCDE", "", "q"))
        assert rankings(sets_file) == {"1": "ABCDE"}

    def test_an_empty_ranking_goes_back_to_reading(self, sets_file: Path) -> None:
        scripted_session(sets_file, ["r", "q"], lines=("",))
        assert rankings(sets_file) == {}

    def test_the_note_and_the_seconds_spent_are_stored_with_the_ranking(
        self, sets_file: Path
    ) -> None:
        clock = iter([10.0, 52.5, 60.0]).__next__  # set 1 shown, set 1 ranked, set 2 shown
        scripted_session(sets_file, ["r", "q"], lines=("ABCDE", "close call"), clock=clock)
        record = latest_rankings(sets_file.parent / "rankings.jsonl")["1"]
        assert record["note"] == "close call" and record["seconds"] == pytest.approx(42.5)

    def test_back_reopens_the_previous_task_and_the_new_ranking_wins(self, sets_file: Path) -> None:
        output = scripted_session(sets_file, ["r", "b", "r", "q"], lines=("ABCDE", "", "EDCBA", ""))
        lines = (sets_file.parent / "rankings.jsonl").read_text().splitlines()
        assert [json.loads(line)["ranking"] for line in lines] == ["ABCDE", "EDCBA"]
        assert rankings(sets_file) == {"1": "EDCBA"}
        assert output.rindex("Passage A of set 2.") > output.rindex("Passage A of set 1.")

    def test_back_after_the_last_task_reopens_it(self, sets_file: Path) -> None:
        typed = ("ABCDE", "", "ABCDE", "", "ABCDE", "", "EDCBA", "")
        output = scripted_session(sets_file, ["r", "r", "r", "x", "b", "r", "q"], lines=typed)
        assert output.count("All 3 tasks ranked") == 2
        assert rankings(sets_file) == {"1": "ABCDE", "2": "ABCDE", "3": "EDCBA"}

    def test_unknown_keys_and_back_on_the_first_task_are_ignored(self, sets_file: Path) -> None:
        scripted_session(sets_file, ["x", "b", "p", "r", "q"], lines=("ABCDE", ""))
        assert rankings(sets_file) == {"1": "ABCDE"}

    def test_q_at_the_ranking_prompt_quits(self, sets_file: Path) -> None:
        output = scripted_session(sets_file, ["r"], lines=("q",))
        assert rankings(sets_file) == {} and "Stopped with 0 of 3 tasks ranked" in output


class TestScreen:
    def set_with_long_passage(self) -> dict:
        return {**make_set("1"), "passages": dict.fromkeys(LETTERS, PASSAGE)}

    def test_a_passage_screen_names_the_task_letter_reader_and_document_type(self) -> None:
        screen = render_passage(self.set_with_long_passage(), "C", 2, 5, 60)
        header = screen.splitlines()[:3]
        assert "Task 2/5" in header[0] and "[C]" in header[0] and "README section" in header[0]
        assert "Reader: Ana" in header[1]
        assert LEGEND.split()[0] in screen
        assert max(len(line) for line in screen.splitlines()) <= 60

    def test_the_ranking_screen_reminds_each_passage_by_its_opening(self) -> None:
        screen = render_ranking_screen(self.set_with_long_passage(), 1, 5, 40)
        openings = [line for line in screen.splitlines() if line[:3] in {f"{x}  " for x in LETTERS}]
        assert len(openings) == 5 and all(len(line) <= 40 for line in openings)
        assert openings[0].startswith("A  The kettle switches off")

    def test_wrapping_keeps_paragraphs_and_list_items(self) -> None:
        lines = wrap_passage(
            "First paragraph\ncontinues here.\n\n- item one\n- item two is long enough", 16
        )
        assert lines[:2] == ["First paragraph", "continues here."]
        assert lines[2] == "" and lines[3] == "- item one" and lines[4].startswith("- item two")
        assert lines[5].startswith("  ")


class TestSetFile:
    def test_a_set_with_extra_fields_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "sets.jsonl"
        path.write_text(json.dumps({**make_set("1"), "task_id": "kettle"}) + "\n")
        with pytest.raises(ValueError):
            load_sets(path)


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

    def test_real_keypresses_in_a_terminal(self, sets_file: Path) -> None:
        master, worker = os.openpty()
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 100, 0, 0))
        process = subprocess.Popen(
            [sys.executable, str(LABEL_SCRIPT), str(sets_file)],
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
            self.read_until(master, screen, "Passage A of set 1.", 1)
            os.write(master, b"\x1b[C")
            self.read_until(master, screen, "Passage B of set 1.", 1)
            os.write(master, b"r")
            self.read_until(master, screen, "Ranking, best first", 1)
            os.write(master, b"ba=cde\r")
            self.read_until(master, screen, "Note", 1)
            os.write(master, b"close call\r")
            self.read_until(master, screen, "Passage A of set 2.", 1)
            os.write(master, b"q")
            self.read_until(master, screen, "Stopped with 1 of 3 tasks ranked", 1)
            assert process.wait(timeout=10) == 0
        finally:
            process.kill()
            process.wait()
            os.close(master)
        record = latest_rankings(sets_file.parent / "rankings.jsonl")["1"]
        assert record["ranking"] == "BA=CDE" and record["note"] == "close call"
