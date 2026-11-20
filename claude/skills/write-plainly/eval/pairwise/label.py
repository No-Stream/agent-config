#!/usr/bin/env python3
"""Rank blind passage sets: read each task's passages one at a time, then rank them best first.

Run it in a terminal: python3 label.py SETS_FILE
Each ranking is appended to the rankings file at once, so you can quit at any point and run the
same command again to continue. Standard library only, Python 3.9 or newer.
"""

from __future__ import annotations

import argparse
import json
import os
import select
import shutil
import sys
import termios
import textwrap
import time
import tty
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SET_FIELDS = {"set_id", "doc_type", "reader", "passages"}
NEXT_KEYS = {"n", "\x1b[C", "next"}
PREVIOUS_KEYS = {"p", "\x1b[D", "previous"}
RANK_KEYS = {"r", "rank"}
BACK_KEYS = {"b", "back"}
QUIT_KEYS = {"q", "quit", "\x03", "\x04", ""}
LEGEND = "n/→ next   p/← previous   r rank   b previous task   q quit"
RANKING_PROMPT = "Ranking, best first, = for a tie (CA=EBD); Enter reads again, q quits: "
NOTE_PROMPT = "Note (optional, Enter to skip): "
MAX_TEXT_WIDTH = 100
CLEAR_SCREEN = "\x1b[2J\x1b[H"


@dataclass(frozen=True)
class Console:
    """How a session reads keys and lines, writes the screen, and measures width and time."""

    read_key: Callable[[], str]
    read_line: Callable[[str], str]
    write: Callable[[str], None]
    width: Callable[[], int]
    clock: Callable[[], float] = time.monotonic


def load_sets(sets_file: Path) -> list[dict]:
    sets = [json.loads(line) for line in sets_file.read_text().splitlines() if line.strip()]
    for passage_set in sets:
        if set(passage_set) != SET_FIELDS:
            raise ValueError(
                f"set {passage_set.get('set_id')} has fields {sorted(passage_set)}, "
                f"expected {sorted(SET_FIELDS)}"
            )
    return sets


def latest_rankings(labels_file: Path) -> dict[str, dict]:
    """The last ranking given for each set; a later ranking replaces an earlier one."""
    if not labels_file.exists():
        return {}
    records = [json.loads(line) for line in labels_file.read_text().splitlines() if line.strip()]
    return {record["set_id"]: record for record in records}


def parse_ranking(typed: str, letters: Sequence[str]) -> list[list[str]]:
    """Places best first, each a list of tied letters: "CA=EBD" is C, then A tied with E, B, D."""
    text = "".join(typed.split()).upper()
    groups: list[list[str]] = []
    joining = False
    for position, character in enumerate(text):
        if character == "=":
            if joining or not groups or position == len(text) - 1:
                raise ValueError("= goes between two letters, as in CA=EBD")
            joining = True
        elif character in letters:
            if joining:
                groups[-1].append(character)
            else:
                groups.append([character])
            joining = False
        else:
            raise ValueError(f"{character} is not one of the letters {''.join(letters)}")
    placed = [letter for group in groups for letter in group]
    repeated = sorted({letter for letter in placed if placed.count(letter) > 1})
    if repeated:
        raise ValueError(f"{', '.join(repeated)} placed more than once")
    missing = [letter for letter in letters if letter not in placed]
    if missing:
        raise ValueError(f"{', '.join(missing)} missing")
    if len(groups) < 2:
        raise ValueError("a ranking needs at least two places")
    return groups


def format_ranking(groups: list[list[str]]) -> str:
    return "".join("=".join(group) for group in groups)


def ranks(groups: list[list[str]]) -> dict[str, float]:
    """Each letter's place, 1 for the best; tied letters share the mean of the places they span."""
    result: dict[str, float] = {}
    place = 1
    for group in groups:
        for letter in group:
            result[letter] = place + (len(group) - 1) / 2
        place += len(group)
    return result


def is_list_marker(word: str) -> bool:
    return word in {"-", "*"} or (word[:-1].isdigit() and word.endswith("."))


def wrap_passage(text: str, width: int) -> list[str]:
    """Wrap each paragraph and list item to `width`, keeping blank lines between paragraphs."""
    lines: list[str] = []
    for paragraph in text.strip().split("\n\n"):
        items: list[str] = []
        for source_line in paragraph.splitlines():
            stripped = source_line.strip()
            if not items or is_list_marker(stripped.split(" ", 1)[0]):
                items.append(stripped)
            else:
                items[-1] += " " + stripped
        if lines:
            lines.append("")
        for item in items:
            marker = item.split(" ", 1)[0]
            indent = " " * (len(marker) + 1) if is_list_marker(marker) else ""
            lines += textwrap.wrap(item, width=width, subsequent_indent=indent)
    return lines


def header(passage_set: dict, title: str, width: int) -> list[str]:
    lines = textwrap.wrap(f"{title} · {passage_set['doc_type']}", width=width)
    return lines + textwrap.wrap(f"Reader: {passage_set['reader']}", width=width) + ["─" * width]


def render_passage(passage_set: dict, letter: str, position: int, total: int, width: int) -> str:
    width = min(width, MAX_TEXT_WIDTH)
    strip = " ".join(f"[{x}]" if x == letter else x for x in sorted(passage_set["passages"]))
    lines = header(passage_set, f"Task {position}/{total} · {strip}", width)
    lines += wrap_passage(passage_set["passages"][letter], width)
    lines += ["─" * width] + textwrap.wrap(LEGEND, width=width, break_on_hyphens=False)
    return CLEAR_SCREEN + "\n".join(lines) + "\n"


def render_ranking_screen(passage_set: dict, position: int, total: int, width: int) -> str:
    """Each passage's opening words beside its letter, as a reminder while ranking."""
    width = min(width, MAX_TEXT_WIDTH)
    lines = header(passage_set, f"Task {position}/{total} · rank", width)
    for letter in sorted(passage_set["passages"]):
        line = f"{letter}  {' '.join(passage_set['passages'][letter].split())}"
        lines.append(line if len(line) <= width else line[: width - 1] + "…")
    return CLEAR_SCREEN + "\n".join(lines + ["─" * width]) + "\n"


def rank_one_set(
    passage_set: dict,
    position: int,
    total: int,
    can_go_back: bool,
    console: Console,
) -> tuple[str, dict | None]:
    """("ranked", record), ("back", None) or ("quit", None)."""
    letters = sorted(passage_set["passages"])
    shown = 0
    started = console.clock()
    redraw = True
    while True:
        if redraw:
            console.write(
                render_passage(passage_set, letters[shown], position, total, console.width())
            )
        key = console.read_key()
        redraw = True
        if key in QUIT_KEYS:
            return "quit", None
        if key in BACK_KEYS and can_go_back:
            return "back", None
        if key in PREVIOUS_KEYS and shown > 0:
            shown -= 1
        elif key in NEXT_KEYS and shown < len(letters) - 1:
            shown += 1
        elif key in RANK_KEYS or key in NEXT_KEYS:
            console.write(render_ranking_screen(passage_set, position, total, console.width()))
            while True:
                typed = console.read_line(RANKING_PROMPT).strip()
                if not typed:
                    break
                if typed.lower() in QUIT_KEYS:
                    return "quit", None
                try:
                    groups = parse_ranking(typed, letters)
                except ValueError as error:
                    console.write(f"  {error}\n")
                    continue
                note = console.read_line(NOTE_PROMPT).strip()
                return "ranked", {
                    "set_id": passage_set["set_id"],
                    "ranking": format_ranking(groups),
                    "note": note,
                    "seconds": round(console.clock() - started, 1),
                    "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
        else:
            redraw = False


def next_unranked(sets: list[dict], rankings: dict[str, dict], after: int) -> int | None:
    """The first unranked set after position `after`, wrapping round; None when all are ranked."""
    order = list(range(after + 1, len(sets))) + list(range(after + 1))
    return next((index for index in order if sets[index]["set_id"] not in rankings), None)


def run_session(sets: list[dict], labels_file: Path, console: Console) -> None:
    rankings = latest_rankings(labels_file)
    index = next_unranked(sets, rankings, after=-1)
    while True:
        if index is None:
            console.write(
                f"\nAll {len(sets)} tasks ranked. Rankings are in {labels_file}.\n"
                "b reopens the last task, q quits.\n"
            )
            key = console.read_key()
            while key not in QUIT_KEYS | BACK_KEYS:
                key = console.read_key()
            if key in QUIT_KEYS:
                return
            index = len(sets) - 1
        action, record = rank_one_set(sets[index], index + 1, len(sets), index > 0, console)
        if action == "quit":
            console.write(
                f"\nStopped with {len(rankings)} of {len(sets)} tasks ranked. "
                "Run the same command to continue.\n"
            )
            return
        if action == "back":
            index -= 1
            continue
        with labels_file.open("a") as labels_handle:
            labels_handle.write(json.dumps(record) + "\n")
        rankings[record["set_id"]] = record
        index = next_unranked(sets, rankings, after=index)


def read_terminal_key() -> str:
    """One keypress from a terminal in raw mode; arrow keys arrive as three-byte sequences."""
    descriptor = sys.stdin.fileno()
    saved_settings = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor, termios.TCSANOW)
        key = os.read(descriptor, 1).decode(errors="replace")
        if key == "\x1b" and select.select([descriptor], [], [], 0.05)[0]:
            key += os.read(descriptor, 2).decode(errors="replace")
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, saved_settings)
    return key


def read_piped_key() -> str:
    """One key per line when stdin is not a terminal, as in scripted runs."""
    return sys.stdin.readline().strip()


def read_typed_line(prompt: str) -> str:
    sys.stdout.write(prompt)
    sys.stdout.flush()
    return sys.stdin.readline()


def write_out(text: str) -> None:
    sys.stdout.write(text)
    sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("sets_file", type=Path)
    parser.add_argument("--labels", type=Path, help="default: rankings.jsonl beside the sets file")
    args = parser.parse_args()
    console = Console(
        read_key=read_terminal_key if sys.stdin.isatty() else read_piped_key,
        read_line=read_typed_line,
        write=write_out,
        width=lambda: shutil.get_terminal_size().columns,
    )
    run_session(
        load_sets(args.sets_file), args.labels or args.sets_file.parent / "rankings.jsonl", console
    )


if __name__ == "__main__":
    main()
