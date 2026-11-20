#!/usr/bin/env python3
"""Label blind passage pairs one at a time: left, right, tie or skip, with an optional note.

Run it in a terminal: python3 label.py PAIRS_FILE
Each answer is appended to the labels file at once, so you can quit at any point and run the
same command again to continue. Skipped pairs come back after the unanswered ones. Standard
library only, Python 3.9 or newer.
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
from collections.abc import Callable
from datetime import datetime, timezone
from itertools import zip_longest
from pathlib import Path

PAIR_FIELDS = {"pair_id", "doc_type", "reader", "left", "right"}
CHOICE_KEYS = {
    "1": "left",
    "h": "left",
    "\x1b[D": "left",
    "left": "left",
    "2": "right",
    "l": "right",
    "\x1b[C": "right",
    "right": "right",
    "t": "tie",
    "tie": "tie",
    "s": "skip",
    "skip": "skip",
}
NOTE_KEYS = {"n", "note"}
BACK_KEYS = {"u", "back"}
QUIT_KEYS = {"q", "quit", "\x03", "\x04", ""}
LEGEND = "1/← left   2/→ right   t tie   s skip   n note   u back   q quit"
SIDE_BY_SIDE_MIN_WIDTH = 100
CLEAR_SCREEN = "\x1b[2J\x1b[H"


def load_pairs(pairs_file: Path) -> list[dict]:
    pairs = [json.loads(line) for line in pairs_file.read_text().splitlines() if line.strip()]
    for pair in pairs:
        if set(pair) != PAIR_FIELDS:
            raise ValueError(
                f"pair {pair.get('pair_id')} has fields {sorted(pair)}, expected {sorted(PAIR_FIELDS)}"
            )
    return pairs


def latest_labels(labels_file: Path) -> dict[str, dict]:
    """The last answer given for each pair; a later answer replaces an earlier one."""
    if not labels_file.exists():
        return {}
    records = [json.loads(line) for line in labels_file.read_text().splitlines() if line.strip()]
    return {record["pair_id"]: record for record in records}


def pairs_to_show(pairs: list[dict], labels: dict[str, dict]) -> list[dict]:
    unanswered = [pair for pair in pairs if pair["pair_id"] not in labels]
    skipped_ids = {pair_id for pair_id, record in labels.items() if record["choice"] == "skip"}
    skipped = [pair for pair in pairs if pair["pair_id"] in skipped_ids]
    return unanswered + skipped


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


def render(pair: dict, answered: int, total: int, note: str, width: int) -> str:
    rule = "─" * width
    header = textwrap.wrap(f"{answered}/{total} done · {pair['doc_type']}", width=width)
    header += textwrap.wrap(f"Reader: {pair['reader']}", width=width)
    if width >= SIDE_BY_SIDE_MIN_WIDTH:
        column_width = (width - 3) // 2
        left_lines = ["LEFT", ""] + wrap_passage(pair["left"], column_width)
        right_lines = ["RIGHT", ""] + wrap_passage(pair["right"], column_width)
        body = [
            f"{left.ljust(column_width)} │ {right}"
            for left, right in zip_longest(left_lines, right_lines, fillvalue="")
        ]
    else:
        body = ["LEFT", ""] + wrap_passage(pair["left"], width) + [rule, "RIGHT", ""]
        body += wrap_passage(pair["right"], width)
    note_lines = textwrap.wrap(f"note: {note}", width=width) if note else []
    footer = [rule] + note_lines
    footer += textwrap.wrap(LEGEND, width=width, break_on_hyphens=False)
    return CLEAR_SCREEN + "\n".join(header + [rule] + body + footer) + "\n"


def run_session(
    pairs: list[dict],
    labels_file: Path,
    read_key: Callable[[], str],
    read_line: Callable[[str], str],
    write: Callable[[str], None],
    terminal_width: Callable[[], int],
    clock: Callable[[], float] = time.monotonic,
) -> None:
    labels = latest_labels(labels_file)
    queue = pairs_to_show(pairs, labels)
    shown_this_session: list[dict] = []
    position = 0
    while True:
        if position == len(queue):
            skipped = sum(1 for record in labels.values() if record["choice"] == "skip")
            write(
                f"\nAll {len(pairs)} pairs answered ({skipped} skipped). "
                f"Labels are in {labels_file}.\nu goes back to the last pair, q quits.\n"
            )
            key = read_key()
            while key not in QUIT_KEYS and not (key in BACK_KEYS and shown_this_session):
                key = read_key()
            if key in QUIT_KEYS:
                return
            queue.insert(position, shown_this_session.pop())
        pair = queue[position]
        note = ""
        answered = sum(1 for record in labels.values() if record["choice"] != "skip")
        write(render(pair, answered, len(pairs), note, terminal_width()))
        started = clock()
        while True:
            key = read_key()
            if key in QUIT_KEYS:
                write(
                    f"\nStopped with {answered} of {len(pairs)} answered. "
                    "Run the same command to continue.\n"
                )
                return
            if key in NOTE_KEYS:
                note = read_line("note: ").strip()
                write(render(pair, answered, len(pairs), note, terminal_width()))
                continue
            if key in BACK_KEYS and shown_this_session:
                previous = shown_this_session.pop()
                queue.insert(position, previous)
                break
            if key in CHOICE_KEYS:
                record = {
                    "pair_id": pair["pair_id"],
                    "choice": CHOICE_KEYS[key],
                    "note": note,
                    "seconds": round(clock() - started, 1),
                    "answered_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
                with labels_file.open("a") as labels_handle:
                    labels_handle.write(json.dumps(record) + "\n")
                labels[pair["pair_id"]] = record
                shown_this_session.append(pair)
                position += 1
                break


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
    """One answer per line when stdin is not a terminal, as in scripted runs."""
    return sys.stdin.readline().strip()


def read_note(prompt: str) -> str:
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
    parser.add_argument("pairs_file", type=Path)
    parser.add_argument("--labels", type=Path, help="default: labels.jsonl beside the pairs file")
    args = parser.parse_args()
    labels_file = args.labels or args.pairs_file.parent / "labels.jsonl"
    run_session(
        pairs=load_pairs(args.pairs_file),
        labels_file=labels_file,
        read_key=read_terminal_key if sys.stdin.isatty() else read_piped_key,
        read_line=read_note,
        write=write_out,
        terminal_width=lambda: shutil.get_terminal_size().columns,
    )


if __name__ == "__main__":
    main()
