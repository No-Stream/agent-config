#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Assemble blind pairs: the base pipeline against each other pipeline, on every task.

Writes `pairs.jsonl` (what the labeler and the judges see: document type, reader and two
passages) and `key.json` (which pipeline wrote which side). The labeler never reads the key.

Order is built in rounds: each task's pairs land in different rounds, so the same base passage
is shown about one round apart, and every task's first showing comes before any repeat. Within a
comparison, the base passage is on the left in half the tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import logging
import random
from pathlib import Path

from common import Task, load_tasks, word_count, write_json, write_jsonl

logger: logging.Logger = logging.getLogger(__name__)

READING_WORDS_PER_MINUTE = 250
DECISION_SECONDS_PER_PAIR = 15
MAX_ORDER_ATTEMPTS = 10_000
MIN_POSITIONS_BETWEEN_TASK_REPEATS = 4


def passage_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def round_assignment(
    task_ids: list[str], others: list[str], rng: random.Random
) -> dict[str, list[str]]:
    """Each task's comparisons in round order, rotated so each round mixes the comparisons."""
    base_order = list(others)
    rng.shuffle(base_order)
    rotations = [index % len(others) for index in range(len(task_ids))]
    rng.shuffle(rotations)
    return {
        task_id: base_order[rotation:] + base_order[:rotation]
        for task_id, rotation in zip(task_ids, rotations)
    }


def base_on_left(
    task_ids: list[str], others: list[str], rng: random.Random
) -> set[tuple[str, str]]:
    """For each comparison, the tasks whose base passage goes on the left: half, chosen at random."""
    left = set()
    for other in others:
        shuffled = list(task_ids)
        rng.shuffle(shuffled)
        odd_one_left = len(shuffled) % 2 == 1 and rng.random() < 0.5
        left_count = len(shuffled) // 2 + int(odd_one_left)
        left |= {(task_id, other) for task_id in shuffled[:left_count]}
    return left


def presentation_order(
    rounds: dict[str, list[str]], rng: random.Random, min_gap: int
) -> list[tuple[str, str, int]]:
    """(task, comparison, round) in showing order; no task twice within `min_gap` positions."""
    round_count = len(next(iter(rounds.values())))
    for _ in range(MAX_ORDER_ATTEMPTS):
        order = []
        for round_index in range(round_count):
            task_ids = list(rounds)
            rng.shuffle(task_ids)
            order += [(task_id, rounds[task_id][round_index], round_index) for task_id in task_ids]
        positions: dict[str, list[int]] = {}
        for position, (task_id, _, _) in enumerate(order):
            positions.setdefault(task_id, []).append(position)
        if all(
            later - earlier >= min_gap
            for spots in positions.values()
            for earlier, later in itertools.pairwise(spots)
        ):
            return order
    raise RuntimeError(f"no order keeps each task's pairs {min_gap} apart; lower the gap")


def build_pairs(
    tasks: list[Task],
    passages: dict[tuple[str, str], str],
    base: str,
    others: list[str],
    seed: int,
) -> tuple[list[dict], dict]:
    rng = random.Random(seed)
    task_ids = [task.task_id for task in tasks]
    tasks_by_id = {task.task_id: task for task in tasks}
    rounds = round_assignment(task_ids, others, rng)
    left_tasks = base_on_left(task_ids, others, rng)
    min_gap = min(MIN_POSITIONS_BETWEEN_TASK_REPEATS, len(task_ids))
    order = presentation_order(rounds, rng, min_gap=min_gap)
    pairs, key_pairs = [], {}
    for position, (task_id, other, round_index) in enumerate(order, start=1):
        pair_id = f"{position:02d}"
        left_pipeline, right_pipeline = (
            (base, other) if (task_id, other) in left_tasks else (other, base)
        )
        left_text, right_text = passages[task_id, left_pipeline], passages[task_id, right_pipeline]
        if left_text == right_text:
            logger.warning(f"{task_id}: {base} and {other} wrote identical passages")
        task = tasks_by_id[task_id]
        pairs.append(
            {
                "pair_id": pair_id,
                "doc_type": task.doc_type,
                "reader": task.reader,
                "left": left_text,
                "right": right_text,
            }
        )
        key_pairs[pair_id] = {
            "task_id": task_id,
            "comparison": other,
            "round": round_index,
            "left_pipeline": left_pipeline,
            "right_pipeline": right_pipeline,
            "left_sha256": passage_digest(left_text),
            "right_sha256": passage_digest(right_text),
        }
    key = {"seed": seed, "base": base, "others": others, "pairs": key_pairs}
    return pairs, key


def reading_minutes(passages: dict[tuple[str, str], str], pair_count: int) -> float:
    """Reading time if each distinct passage is read once, plus a decision per pair."""
    distinct_words = sum(word_count(text) for text in set(passages.values()))
    return distinct_words / READING_WORDS_PER_MINUTE + pair_count * DECISION_SECONDS_PER_PAIR / 60


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generation", type=Path, required=True, help="runner output directory")
    parser.add_argument("--tasks", type=Path, nargs="+", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--others", nargs="+", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--out", type=Path, required=True, help="directory for pairs.jsonl and key.json"
    )
    args = parser.parse_args()
    pairs_file, key_file = args.out / "pairs.jsonl", args.out / "key.json"
    if pairs_file.exists() or key_file.exists():
        raise FileExistsError(f"{args.out} already holds pairs; labels may refer to them")
    tasks = load_tasks(args.tasks)
    passages = {
        (task.task_id, pipeline): (args.generation / task.task_id / pipeline / "final.md")
        .read_text()
        .strip()
        for task in tasks
        for pipeline in [args.base, *args.others]
    }
    pairs, key = build_pairs(tasks, passages, args.base, args.others, args.seed)
    key["generation_dir"] = str(args.generation.resolve())
    write_jsonl(pairs_file, pairs)
    write_json(key_file, key)
    for pipeline in [args.base, *args.others]:
        counts = [word_count(passages[task.task_id, pipeline]) for task in tasks]
        logger.info(
            f"{pipeline}: words min {min(counts)}, mean {sum(counts) / len(counts):.0f}, max {max(counts)}"
        )
    logger.info(
        f"wrote {len(pairs)} pairs to {pairs_file}; estimated reading time "
        f"{reading_minutes(passages, len(pairs)):.0f} minutes"
    )


if __name__ == "__main__":
    main()
