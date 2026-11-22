"""Shared pieces of the pairwise evaluation: tasks, JSONL records, word counts, parallel jobs."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import tomllib
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")

DOC_TYPES = (
    "Section of a research readout",
    "Proposal paragraph",
    "README section",
    "Pull request description",
    "Design-doc explanation",
)
CITATION_MARKER = re.compile(r"\s*\[\d+(?:,\s*\d+)*\]")
MIN_PASSAGE_WORDS = 150
MAX_PASSAGE_WORDS = 250
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.%-]*")


@dataclass(frozen=True)
class Task:
    task_id: str
    doc_type: str
    reader: str
    target_words: int
    notes: str
    sources: tuple[str, ...]

    @property
    def notes_for_writer(self) -> str:
        """The notes without citation markers, which are for checking facts, not for the writer."""
        return CITATION_MARKER.sub("", self.notes).strip()


def load_tasks(task_files: Iterable[Path]) -> list[Task]:
    tasks = []
    for task_file in task_files:
        for entry in tomllib.loads(task_file.read_text())["task"]:
            if entry["doc_type"] not in DOC_TYPES:
                raise ValueError(
                    f"{task_file}: task {entry['id']} has unknown doc_type {entry['doc_type']!r}"
                )
            if not MIN_PASSAGE_WORDS <= entry["target_words"] <= MAX_PASSAGE_WORDS:
                raise ValueError(
                    f"{task_file}: task {entry['id']} target_words outside "
                    f"{MIN_PASSAGE_WORDS}-{MAX_PASSAGE_WORDS}"
                )
            tasks.append(
                Task(
                    task_id=entry["id"],
                    doc_type=entry["doc_type"],
                    reader=entry["reader"],
                    target_words=entry["target_words"],
                    notes=entry["notes"].strip(),
                    sources=tuple(entry["sources"]),
                )
            )
    task_ids = [task.task_id for task in tasks]
    duplicate_ids = sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1})
    if duplicate_ids:
        raise ValueError(f"duplicate task ids: {duplicate_ids}")
    return tasks


def read_list(paths: Iterable[object]) -> str:
    """One `- path` line per file; agent calls are checked against reads of exactly these paths."""
    return "\n".join(f"- {path}" for path in paths)


def passage_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def word_count(text: str) -> int:
    return len(WORD.findall(text))


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


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    write_text_atomic(path, "".join(json.dumps(record) + "\n" for record in records))


def write_json(path: Path, payload: dict) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2) + "\n")


def run_parallel(jobs: list[Callable[[], T]], workers: int) -> list[T]:
    """Run jobs on a thread pool and return their results in order.

    After the first failure, jobs not yet started do not start, and the failure is raised.
    """
    failed = threading.Event()

    def guarded(job: Callable[[], T]) -> T | None:
        if failed.is_set():
            return None
        try:
            return job()
        except BaseException:
            failed.set()
            raise

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(guarded, job) for job in jobs]
    return [future.result() for future in futures]


def write_text_atomic(path: Path, text: str) -> None:
    """Write through a temporary file and rename, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(file_descriptor, "w") as temporary_file:
        temporary_file.write(text)
    os.replace(temporary_name, path)
