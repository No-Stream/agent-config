#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Assemble blind ranking sets: one set per task, holding every pipeline's passage once.

Writes `sets.jsonl` (what the labeler and the judges see: document type, reader and the passages
under letters A, B, C and so on) and `key.json` (which pipeline wrote the passage under each
letter). The labeler never reads the key. The seed shuffles the task order and, separately for
each task, which pipeline gets which letter.
"""

from __future__ import annotations

import argparse
import logging
import random
import string
from pathlib import Path

from common import Task, load_tasks, passage_digest, word_count, write_json, write_jsonl

logger: logging.Logger = logging.getLogger(__name__)

READING_WORDS_PER_MINUTE = 250
RANKING_SECONDS_PER_SET = 30


def build_sets(
    tasks: list[Task], passages: dict[tuple[str, str], str], pipelines: list[str], seed: int
) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    letters = string.ascii_uppercase[: len(pipelines)]
    shown_tasks = list(tasks)
    rng.shuffle(shown_tasks)
    sets, key_sets = [], {}
    for position, task in enumerate(shown_tasks, start=1):
        set_id = str(position)
        shuffled = list(pipelines)
        rng.shuffle(shuffled)
        by_letter = dict(zip(letters, shuffled))
        texts = {letter: passages[task.task_id, pipeline] for letter, pipeline in by_letter.items()}
        if len(set(texts.values())) < len(texts):
            logger.warning(f"{task.task_id}: two pipelines wrote identical passages")
        sets.append(
            {"set_id": set_id, "doc_type": task.doc_type, "reader": task.reader, "passages": texts}
        )
        key_sets[set_id] = {
            "task_id": task.task_id,
            "pipelines": by_letter,
            "sha256": {letter: passage_digest(text) for letter, text in texts.items()},
        }
    return sets, {"seed": seed, "pipelines": pipelines, "sets": key_sets}


def reading_minutes(passages: dict[tuple[str, str], str], set_count: int) -> float:
    words = sum(word_count(text) for text in passages.values())
    return words / READING_WORDS_PER_MINUTE + set_count * RANKING_SECONDS_PER_SET / 60


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", type=Path, required=True, help="runner output directory")
    parser.add_argument("--tasks", type=Path, nargs="+", required=True)
    parser.add_argument("--pipelines", nargs="+", required=True)
    parser.add_argument("--only-task", nargs="+", help="use only these task ids")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--out", type=Path, required=True, help="directory for sets.jsonl and key.json"
    )
    args = parser.parse_args()
    sets_file, key_file = args.out / "sets.jsonl", args.out / "key.json"
    if sets_file.exists() or key_file.exists():
        raise FileExistsError(f"{args.out} already holds sets; rankings may refer to them")
    tasks = load_tasks(args.tasks)
    if args.only_task:
        unknown = set(args.only_task) - {task.task_id for task in tasks}
        if unknown:
            raise ValueError(f"--only-task names tasks not in the task files: {sorted(unknown)}")
        tasks = [task for task in tasks if task.task_id in args.only_task]
    passages = {
        (task.task_id, pipeline): (args.generation / task.task_id / pipeline / "final.md")
        .read_text()
        .strip()
        for task in tasks
        for pipeline in args.pipelines
    }
    sets, key = build_sets(tasks, passages, args.pipelines, args.seed)
    key["generation_dir"] = str(args.generation.resolve())
    write_jsonl(sets_file, sets)
    write_json(key_file, key)
    for pipeline in args.pipelines:
        counts = [word_count(passages[task.task_id, pipeline]) for task in tasks]
        logger.info(
            f"{pipeline}: words min {min(counts)}, mean {sum(counts) / len(counts):.0f}, "
            f"max {max(counts)}"
        )
    logger.info(
        f"wrote {len(sets)} sets to {sets_file}; estimated reading time "
        f"{reading_minutes(passages, len(sets)):.0f} minutes"
    )


if __name__ == "__main__":
    main()
