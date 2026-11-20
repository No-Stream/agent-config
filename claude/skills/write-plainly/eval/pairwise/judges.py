#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Ask LLM judges to pick the better passage of each blind pair, in both left-right orders.

Judges see exactly what the labeler shows: document type, reader and the two passages. Pairs go
to each judge in batches, one call per batch and order, so the two orders of a pair never share
a call, and the calls run in parallel. Each batch's verdicts are written as soon as the call
returns, and a rerun skips them; a rerun whose batch holds other pairs than the one on disk stops,
since its verdicts would not match.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from agents import ClaudeCall, ClaudeSettings, run_claude, run_codex
from common import read_jsonl, read_list, run_parallel, write_json, write_text_atomic

logger: logging.Logger = logging.getLogger(__name__)

ORDERS = ("shown", "swapped")
JUDGES = ("opus", "codex")
CHOICES = ("left", "right", "tie")
VERDICTS_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pair_id": {"type": "string"},
                    "choice": {"type": "string", "enum": list(CHOICES)},
                    "reason": {"type": "string"},
                },
                "required": ["pair_id", "choice", "reason"],
            },
        }
    },
    "required": ["verdicts"],
}
JUDGE_PROMPT = """\
You are judging pairs of short passages for a blind writing evaluation. The standard is the \
writing guidance in this file; read it completely first:
{skill_list}

Then read {batch_file}, which holds {pair_count} pairs. Each pair has a document type, an \
intended reader, and two passages written from the same source notes, labelled Left and Right.

For each pair, pick the passage that better serves its intended reader for its document type, \
judged by that guidance, or tie if neither is better. Judge each pair on its own. Length alone is \
not a reason to prefer a passage. You cannot see the source notes, so judge the writing, not which \
facts each passage chose.

{output_instructions}"""
OPUS_OUTPUT = "Return one verdict per pair in the `verdicts` field."
CODEX_OUTPUT = """\
Your final message is JSON lines and nothing else, one object per pair:
{"pair_id": "<id>", "choice": "left" | "right" | "tie", "reason": "<one sentence>"}"""
FLIPPED = {"left": "right", "right": "left", "tie": "tie"}


def batches(pair_ids: list[str], batch_size: int, seed: int, order: str) -> list[list[str]]:
    shuffled = list(pair_ids)
    random.Random(f"{seed}-{order}").shuffle(shuffled)
    return [shuffled[start : start + batch_size] for start in range(0, len(shuffled), batch_size)]


def batch_text(pairs: list[dict], order: str) -> str:
    sections = []
    for pair in pairs:
        left, right = (
            (pair["left"], pair["right"]) if order == "shown" else (pair["right"], pair["left"])
        )
        sections.append(
            f"## Pair {pair['pair_id']}\n\nDocument type: {pair['doc_type']}\n"
            f"Intended reader: {pair['reader']}\n\n### Left\n\n{left}\n\n### Right\n\n{right}\n"
        )
    return "# Pairs to judge\n\n" + "\n".join(sections)


def parse_codex_verdicts(text: str) -> list[dict]:
    return [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]


def checked_verdicts(verdicts: list[dict], batch_ids: list[str], order: str) -> list[dict]:
    """Validate one batch's verdicts and add each pick in the orientation of the pairs file."""
    if sorted(verdict["pair_id"] for verdict in verdicts) != sorted(batch_ids):
        raise RuntimeError(
            f"judge answered for {[v['pair_id'] for v in verdicts]}, asked for {batch_ids}"
        )
    bad_choices = [verdict for verdict in verdicts if verdict["choice"] not in CHOICES]
    if bad_choices:
        raise RuntimeError(f"judge gave choices outside {CHOICES}: {bad_choices}")
    return [
        {**verdict, "pick": verdict["choice"] if order == "shown" else FLIPPED[verdict["choice"]]}
        for verdict in verdicts
    ]


@dataclass(frozen=True)
class JudgeRun:
    """What every judge call of one run shares."""

    skill_file: Path
    out_dir: Path
    settings: ClaudeSettings
    codex_bin: str
    effort: str


def judge_batch(
    run: JudgeRun, judge: str, order: str, batch_index: int, batch_pairs: list[dict]
) -> None:
    result_file = run.out_dir / f"{judge}-{order}-{batch_index:02d}.json"
    batch_ids = [pair["pair_id"] for pair in batch_pairs]
    if result_file.is_file():
        judged_ids = json.loads(result_file.read_text())["pair_ids"]
        if judged_ids != batch_ids:
            raise RuntimeError(
                f"{result_file} judged pairs {judged_ids}, but this run's batch holds {batch_ids}; "
                "a different pair set, batch size or seed needs a fresh --out"
            )
        return
    batch_file = run.out_dir / "batches" / f"{order}-{batch_index:02d}.md"
    write_text_atomic(batch_file, batch_text(batch_pairs, order))
    prompt = JUDGE_PROMPT.format(
        skill_list=read_list([run.skill_file]),
        batch_file=batch_file,
        pair_count=len(batch_pairs),
        output_instructions=OPUS_OUTPUT if judge == "opus" else CODEX_OUTPUT,
    )
    cost_usd = None
    if judge == "opus":
        call = ClaudeCall(
            prompt=prompt,
            model="opus",
            effort=run.effort,
            tools=("Read",),
            readable_dirs=(run.skill_file.parent, batch_file.parent),
            cwd=batch_file.parent,
            json_schema=VERDICTS_SCHEMA,
        )
        result = run_claude(call, run.settings)
        if run.skill_file not in result.read_files:
            raise RuntimeError(f"the opus judge did not read {run.skill_file}")
        verdicts, cost_usd = result.structured["verdicts"], result.cost_usd
    else:
        raw_file = run.out_dir / "raw" / f"codex-{order}-{batch_index:02d}.txt"
        text = run_codex(prompt, batch_file.parent, raw_file, run.codex_bin, run.settings.timeout_s)
        verdicts = parse_codex_verdicts(text)
    record = {
        "judge": judge,
        "order": order,
        "batch": batch_index,
        "pair_ids": batch_ids,
        "verdicts": checked_verdicts(verdicts, batch_ids, order),
        "cost_usd": cost_usd,
    }
    write_json(result_file, record)
    logger.info(f"finished {result_file.name}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--skill", type=Path, required=True, help="the guidance judges apply")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--judges", nargs="+", choices=JUDGES, default=list(JUDGES))
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--only", nargs="*", default=None, help="judge only these pair ids")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--max-budget-usd", type=float, default=5.0)
    parser.add_argument("--jobs", type=int, default=4, help="judge calls run at once")
    args = parser.parse_args()
    pairs = {pair["pair_id"]: pair for pair in read_jsonl(args.pairs)}
    pair_ids = args.only or sorted(pairs)
    run = JudgeRun(
        skill_file=args.skill.resolve(),
        out_dir=args.out.resolve(),
        settings=ClaudeSettings(args.claude_bin, args.timeout_s, args.max_budget_usd),
        codex_bin=args.codex_bin,
        effort=args.effort,
    )
    jobs = [
        partial(judge_batch, run, judge, order, index, [pairs[pair_id] for pair_id in batch_ids])
        for judge in args.judges
        for order in ORDERS
        for index, batch_ids in enumerate(batches(pair_ids, args.batch_size, args.seed, order))
    ]
    run_parallel(jobs, args.jobs)


if __name__ == "__main__":
    main()
