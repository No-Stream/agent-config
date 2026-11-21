#!/usr/bin/env python3
"""Grade blind passage sets in a browser page, then record the grades the page hands back.

build writes one self-contained HTML page from a sets file: one screen per task, a letter grade
for each passage, and a result line to copy. record reads a result line on stdin, checks it
against the sets file and writes grades.jsonl beside it, one record per set. The line's notes are
JSON with double quotes and may hold apostrophes, so pass it in a quoted heredoc, never as an
argument. Standard library only, Python 3.9 or newer.

    python3 rater.py build eval/sets.jsonl --out eval/rater.html
    python3 rater.py record eval/sets.jsonl <<'EOF'
    wp1 1a2b3c4d 1:B+,A-,C,B,A notes={"1":"B's opening is padded"}
    EOF
"""

from __future__ import annotations

import argparse
import hashlib
import html
import itertools
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

LINE_VERSION = "wp1"
GRADE_POINTS = {
    "A+": 4.3, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0, "D-": 0.7,
    "F": 0.0,
}  # fmt: skip
GRADES_FILE_NAME = "grades.jsonl"
NOTES_MARKER = " notes="
NOTE_MAX_CHARS = 120
SET_FIELDS = {"set_id", "doc_type", "reader", "passages"}
TEMPLATE_FILE = Path(__file__).with_name("rater_page.html")
TEMPLATE_MARKER = re.compile(r"\{\{(NAV|TASKS|META)\}\}")
FENCE = "```"
INLINE_CODE = re.compile(r"`([^`\n]+)`")
LIST_MARKER = re.compile(r"(?:[-*]|\d+\.)\s+")
TABLE_SEPARATOR = re.compile(r"\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?")


class LineRefused(ValueError):
    """A result line that does not fit the sets file it is recorded against."""


def load_sets(sets_file: Path) -> list[dict]:
    lines = sets_file.read_text(encoding="utf-8").splitlines()
    sets = [json.loads(line) for line in lines if line.strip()]
    for passage_set in sets:
        if set(passage_set) != SET_FIELDS:
            raise ValueError(
                f"set {passage_set.get('set_id')} has fields {sorted(passage_set)}, "
                f"expected {sorted(SET_FIELDS)}"
            )
    return sets


def sets_digest(sets_file: Path) -> str:
    """Eight hex digits naming the sets file, so a line made from another one is refused."""
    return hashlib.sha256(sets_file.read_bytes()).hexdigest()[:8]


def letters(passage_set: dict) -> list[str]:
    """The order of a set's passages on the page and of its grades in a result line."""
    return sorted(passage_set["passages"])


def inline(text: str) -> str:
    """Escape HTML, and set `code` spans in a monospace font."""
    pieces = INLINE_CODE.split(text)
    return "".join(
        f"<code>{html.escape(piece)}</code>" if index % 2 else html.escape(piece)
        for index, piece in enumerate(pieces)
    )


def table_cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def render_table(rows: list[str]) -> str:
    """A header row, the separator row, then body rows; column alignment is ignored."""
    head = "".join(f"<th>{inline(cell)}</th>" for cell in table_cells(rows[0]))
    body = "".join(
        "<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in table_cells(row)) + "</tr>"
        for row in rows[2:]
    )
    return (
        f'<div class="table"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def render_block(lines: list[str]) -> str:
    """Lines between blank lines: a table, or a paragraph and list items in the order typed."""
    is_table = len(lines) > 1 and lines[0].lstrip().startswith("|")
    if is_table and TABLE_SEPARATOR.fullmatch(lines[1].strip()):
        return render_table(lines)
    items: list[tuple[str, str]] = []  # (tag, text), tag "p", "ul" or "ol"
    for line in lines:
        stripped = line.strip()
        marker = LIST_MARKER.match(stripped)
        if marker:
            items.append(("ol" if stripped[0].isdigit() else "ul", stripped[marker.end() :]))
        elif items:
            items[-1] = (items[-1][0], f"{items[-1][1]} {stripped}")
        else:
            items.append(("p", stripped))
    parts = []
    for tag, group in itertools.groupby(items, key=lambda item: item[0]):
        texts = [text for _, text in group]
        if tag == "p":
            parts += [f"<p>{inline(text)}</p>" for text in texts]
        else:
            parts.append(f"<{tag}>{''.join(f'<li>{inline(text)}</li>' for text in texts)}</{tag}>")
    return "".join(parts)


def render_passage(text: str) -> str:
    """Paragraphs, lists, tables, fenced code and inline code; anything else shows as typed."""
    parts: list[str] = []
    block: list[str] = []
    lines = iter(text.strip().splitlines())
    for line in lines:
        if line.strip().startswith(FENCE):
            parts.append(render_block(block))
            block = []
            code = itertools.takewhile(lambda inner: not inner.strip().startswith(FENCE), lines)
            code_text = "\n".join(code)
            parts.append(f"<pre><code>{html.escape(code_text)}</code></pre>")
        elif line.strip():
            block.append(line)
        else:
            parts.append(render_block(block))
            block = []
    parts.append(render_block(block))
    return "".join(parts)


def grade_picker(letter: str) -> str:
    groups = itertools.groupby(GRADE_POINTS, key=lambda grade: grade[0])
    buttons = "".join(
        '<div class="letter">'
        + "".join(
            f'<button type="button" data-grade="{grade}" aria-pressed="false">{grade}</button>'
            for grade in grades
        )
        + "</div>"
        for _, grades in groups
    )
    return (
        f'<div class="grades" role="group" aria-label="Grade for passage {letter}">{buttons}</div>'
    )


def render_task(passage_set: dict, position: int, total: int) -> str:
    passages = "".join(
        f'<article class="passage" data-letter="{html.escape(letter)}">'
        f'<h2>Passage {html.escape(letter)} <span class="chosen"></span></h2>'
        f'<div class="text">{render_passage(passage_set["passages"][letter])}</div>'
        f"{grade_picker(html.escape(letter))}</article>"
        for letter in letters(passage_set)
    )
    first = " disabled" if position == 1 else ""
    next_button = (
        '<button type="button" data-to-result>Go to the result</button>'
        if position == total
        else '<button type="button" data-step="1">Next task</button>'
    )
    return (
        f'<section class="task" data-set="{html.escape(passage_set["set_id"])}" hidden>'
        f"<h1>Task {position} of {total}</h1>"
        '<div class="brief">'
        f'<p><span class="label">Document type</span>{html.escape(passage_set["doc_type"])}</p>'
        f'<p><span class="label">Intended reader</span>{html.escape(passage_set["reader"])}</p>'
        "</div>"
        f"{passages}"
        '<label class="note">Note on this task (optional)'
        f'<input type="text" maxlength="{NOTE_MAX_CHARS}" autocomplete="off" data-note></label>'
        f'<div class="steps"><button type="button" data-step="-1"{first}>Previous task</button>'
        f"{next_button}</div>"
        "</section>"
    )


def build_page(sets: list[dict], digest: str) -> str:
    meta = {
        "version": LINE_VERSION,
        "digest": digest,
        "sets": [{"id": s["set_id"], "letters": letters(s)} for s in sets],
    }
    fills = {
        "NAV": "".join(
            f'<button type="button" data-go="{index}" aria-label="Task {index + 1}">'
            f"{index + 1}</button>"
            for index in range(len(sets))
        ),
        "TASKS": "\n".join(
            render_task(passage_set, position, len(sets))
            for position, passage_set in enumerate(sets, start=1)
        ),
        "META": json.dumps(meta).replace("<", "\\u003c"),
    }
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    markers = sorted(match.group(1) for match in TEMPLATE_MARKER.finditer(template))
    if markers != sorted(fills):
        raise ValueError(
            f"{TEMPLATE_FILE} holds markers {markers}, expected each of {sorted(fills)}"
        )
    return TEMPLATE_MARKER.sub(lambda match: fills[match.group(1)], template)


def parse_line(line: str, sets: list[dict], digest: str) -> dict[str, dict]:
    """Each set the line grades, by set id: its grades by letter and its note."""
    head, found, notes_text = line.strip().partition(NOTES_MARKER)
    if not found:
        raise LineRefused(f"no{NOTES_MARKER} part at the end; the line may be cut off")
    tokens = head.split()
    if not tokens or tokens[0] != LINE_VERSION:
        raise LineRefused(f"the line does not start with {LINE_VERSION}")
    if len(tokens) < 2 or tokens[1] != digest:
        raise LineRefused(f"the line is not for this sets file, whose digest is {digest}")
    sets_by_id = {passage_set["set_id"]: passage_set for passage_set in sets}
    graded: dict[str, dict] = {}
    for token in tokens[2:]:
        set_id, _, grade_text = token.partition(":")
        if set_id not in sets_by_id:
            raise LineRefused(f"{token}: the sets file has no set {set_id!r}")
        if set_id in graded:
            raise LineRefused(f"set {set_id} appears twice")
        set_letters = letters(sets_by_id[set_id])
        grades = grade_text.split(",")
        if len(grades) != len(set_letters):
            raise LineRefused(
                f"set {set_id} has {len(grades)} grades for {len(set_letters)} passages"
            )
        unknown = [grade for grade in grades if grade not in GRADE_POINTS]
        if unknown:
            raise LineRefused(
                f"set {set_id}: {unknown} are not grades; the grades are {' '.join(GRADE_POINTS)}"
            )
        graded[set_id] = {"grades": dict(zip(set_letters, grades)), "note": ""}
    if not graded:
        raise LineRefused("the line grades no task")
    try:
        notes = json.loads(notes_text)
    except json.JSONDecodeError as error:
        raise LineRefused(f"the notes are not JSON ({error}); the line may be cut off") from error
    if not isinstance(notes, dict) or not all(isinstance(note, str) for note in notes.values()):
        raise LineRefused(f"the notes are not an object of set id to text: {notes_text}")
    ungraded = sorted(set(notes) - set(graded))
    if ungraded:
        raise LineRefused(f"notes for sets the line does not grade: {ungraded}")
    for set_id, note in notes.items():
        graded[set_id]["note"] = note
    return graded


def latest_grades(grades_file: Path) -> dict[str, dict]:
    """The recorded grades by set id; empty before the first record."""
    if not grades_file.exists():
        return {}
    lines = grades_file.read_text(encoding="utf-8").splitlines()
    return {record["set_id"]: record for record in map(json.loads, filter(str.strip, lines))}


def record(sets_file: Path, line: str) -> list[str]:
    """Write the line's sets to grades.jsonl beside the sets file, replacing their earlier records."""
    sets = load_sets(sets_file)
    graded = parse_line(line, sets, sets_digest(sets_file))
    grades_file = sets_file.parent / GRADES_FILE_NAME
    records = latest_grades(grades_file)
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for set_id, answer in graded.items():
        records[set_id] = {"set_id": set_id, **answer, "recorded_at": recorded_at}
    position = {passage_set["set_id"]: index for index, passage_set in enumerate(sets)}
    ordered = sorted(records.values(), key=lambda record: position[record["set_id"]])
    grades_file.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in ordered),
        encoding="utf-8",
    )
    return list(graded)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build_command = commands.add_parser("build", help="write the grading page")
    build_command.add_argument("sets_file", type=Path)
    build_command.add_argument("--out", type=Path, required=True)
    record_command = commands.add_parser(
        "record", help=f"add the result line on stdin to {GRADES_FILE_NAME}"
    )
    record_command.add_argument("sets_file", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        sets = load_sets(args.sets_file)
        digest = sets_digest(args.sets_file)
        args.out.write_text(build_page(sets, digest), encoding="utf-8")
        print(f"wrote {args.out}: {len(sets)} tasks from sets file {digest}")
        return
    try:
        recorded = record(args.sets_file, sys.stdin.read())
    except LineRefused as error:
        sys.exit(f"refused: {error}")
    grades_file = args.sets_file.parent / GRADES_FILE_NAME
    print(
        f"recorded sets {', '.join(recorded)} in {grades_file}; "
        f"{len(latest_grades(grades_file))} of {len(load_sets(args.sets_file))} sets graded"
    )


if __name__ == "__main__":
    main()
