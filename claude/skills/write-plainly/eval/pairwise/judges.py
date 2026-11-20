#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Ask LLM judges to rank each blind passage set, twice, under two different letter orders.

Judges see what the labeler sees: document type, reader and the passages. For each set, the seed
draws one order of the passages and the second order is its reverse, so a passage shown early in
one is shown late in the other; the letters follow the order shown. Each judge ranks one set per
call, and the calls run in parallel. Each ranking is written as soon as its call returns, in the
sets file's letters, and a rerun skips it; a ranking on disk whose set or order differs from this
run's stops the run. At the end, each judge's agreement with itself across the two orders is
printed.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import statistics
import string
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from agents import ClaudeCall, ClaudeSettings, run_claude, run_codex
from common import (
    kendall_tau_b,
    passage_digest,
    read_jsonl,
    read_list,
    run_parallel,
    write_json,
    write_text_atomic,
)
from label import format_ranking, parse_ranking, ranks

logger: logging.Logger = logging.getLogger(__name__)

ORDERS = ("drawn", "reversed")
JUDGES = ("opus", "codex")
RANKING_SCHEMA = {
    "type": "object",
    "properties": {"ranking": {"type": "string"}, "reason": {"type": "string"}},
    "required": ["ranking", "reason"],
}
JUDGE_PROMPT = """\
You are ranking short passages for a blind writing evaluation. The standard is the writing \
guidance in this file; read it completely first:
{skill_list}

Then read {set_file}, which holds {count} passages labelled {letters}, written from the same \
source notes for one document type and intended reader.

Rank the passages from best to worst at serving that reader for that document type, judged by \
that guidance. Write the ranking as the letters, best first, and join passages you find equally \
good with =, as in CA=EBD. Every letter appears exactly once, and the ranking has at least two \
places. Length alone is not a reason to prefer a passage. You cannot see the source notes, so \
judge the writing, not which facts each passage chose.

{output_instructions}"""
OPUS_OUTPUT = "Return the ranking and a one-sentence reason in the `ranking` and `reason` fields."
CODEX_OUTPUT = """\
Your final message is one line of JSON and nothing else:
{"ranking": "<letters, best first>", "reason": "<one sentence>"}"""


def letter_orders(set_id: str, letters: list[str], seed: int) -> dict[str, list[str]]:
    """The sets file's letters in the order each judging call shows them."""
    drawn = list(letters)
    random.Random(f"{seed}-{set_id}").shuffle(drawn)
    return {"drawn": drawn, "reversed": drawn[::-1]}


def shown_letters(count: int) -> list[str]:
    return list(string.ascii_uppercase[:count])


def set_text(passage_set: dict, shown: list[str]) -> str:
    """The set as one judging call sees it: passage `shown[i]` under the i-th letter."""
    sections = [
        f"### Passage {letter}\n\n{passage_set['passages'][set_letter]}\n"
        for letter, set_letter in zip(shown_letters(len(shown)), shown)
    ]
    return (
        f"# Passages to rank\n\nDocument type: {passage_set['doc_type']}\n"
        f"Intended reader: {passage_set['reader']}\n\n" + "\n".join(sections)
    )


def ranking_in_set_letters(ranking: str, shown: list[str]) -> str:
    """A ranking given in the letters a call showed, rewritten in the sets file's letters."""
    to_set_letter = dict(zip(shown_letters(len(shown)), shown))
    groups = parse_ranking(ranking, shown_letters(len(shown)))
    return format_ranking([[to_set_letter[letter] for letter in group] for group in groups])


def parse_codex_answer(text: str) -> dict:
    answers = [line for line in text.splitlines() if line.strip().startswith("{")]
    if not answers:
        raise RuntimeError(f"codex gave no JSON line: {text[-500:]}")
    return json.loads(answers[-1])


@dataclass(frozen=True)
class JudgeRun:
    """What every judge call of one run shares."""

    skill_file: Path
    out_dir: Path
    settings: ClaudeSettings
    codex_bin: str
    effort: str


def judge_set(run: JudgeRun, judge: str, order: str, passage_set: dict, shown: list[str]) -> None:
    set_id = passage_set["set_id"]
    result_file = run.out_dir / f"{judge}-{order}-set{set_id}.json"
    digests = {letter: passage_digest(text) for letter, text in passage_set["passages"].items()}
    if result_file.is_file():
        on_disk = json.loads(result_file.read_text())
        if (on_disk["shown"], on_disk["sha256"]) != (shown, digests):
            raise RuntimeError(
                f"{result_file} ranked other passages or another order than this run's set "
                f"{set_id}; a different sets file or seed needs a fresh --out"
            )
        return
    set_file = run.out_dir / "sets" / f"{order}-set{set_id}.md"
    write_text_atomic(set_file, set_text(passage_set, shown))
    prompt = JUDGE_PROMPT.format(
        skill_list=read_list([run.skill_file]),
        set_file=set_file,
        count=len(shown),
        letters=", ".join(shown_letters(len(shown))),
        output_instructions=OPUS_OUTPUT if judge == "opus" else CODEX_OUTPUT,
    )
    cost_usd = None
    if judge == "opus":
        call = ClaudeCall(
            prompt=prompt,
            model="opus",
            effort=run.effort,
            tools=("Read",),
            readable_dirs=(run.skill_file.parent, set_file.parent),
            cwd=set_file.parent,
            json_schema=RANKING_SCHEMA,
        )
        result = run_claude(call, run.settings)
        if run.skill_file not in result.read_files:
            raise RuntimeError(f"the opus judge did not read {run.skill_file}")
        answer, cost_usd = result.structured, result.cost_usd
    else:
        raw_file = run.out_dir / "raw" / f"codex-{order}-set{set_id}.txt"
        text = run_codex(prompt, set_file.parent, raw_file, run.codex_bin, run.settings.timeout_s)
        answer = parse_codex_answer(text)
    record = {
        "judge": judge,
        "order": order,
        "set_id": set_id,
        "shown": shown,
        "sha256": digests,
        "ranking_as_shown": answer["ranking"],
        "ranking": ranking_in_set_letters(answer["ranking"], shown),
        "reason": answer["reason"],
        "cost_usd": cost_usd,
    }
    write_json(result_file, record)
    logger.info(f"finished {result_file.name}")


def order_agreement(records: list[dict]) -> tuple[list[float], int]:
    """Per set, Kendall's tau between its rankings in the two orders; and how many are identical."""
    by_set: dict[str, dict[str, dict]] = {}
    for record in records:
        by_set.setdefault(record["set_id"], {})[record["order"]] = record
    taus, identical = [], 0
    for by_order in by_set.values():
        letters = sorted(by_order["drawn"]["shown"])
        first, second = (
            ranks(parse_ranking(by_order[order]["ranking"], letters)) for order in ORDERS
        )
        taus.append(kendall_tau_b([first[x] for x in letters], [second[x] for x in letters]))
        identical += by_order["drawn"]["ranking"] == by_order["reversed"]["ranking"]
    return taus, identical


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sets", type=Path, required=True)
    parser.add_argument("--skill", type=Path, required=True, help="the guidance judges apply")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--judges", nargs="+", choices=JUDGES, default=list(JUDGES))
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--only", nargs="*", default=None, help="rank only these set ids")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--timeout-s", type=int, default=1800)
    parser.add_argument("--max-budget-usd", type=float, default=5.0)
    parser.add_argument("--jobs", type=int, default=4, help="judge calls run at once")
    args = parser.parse_args()
    sets = {passage_set["set_id"]: passage_set for passage_set in read_jsonl(args.sets)}
    set_ids = args.only or list(sets)
    run = JudgeRun(
        skill_file=args.skill.resolve(),
        out_dir=args.out.resolve(),
        settings=ClaudeSettings(args.claude_bin, args.timeout_s, args.max_budget_usd),
        codex_bin=args.codex_bin,
        effort=args.effort,
    )
    jobs = [
        partial(judge_set, run, judge, order, sets[set_id], shown)
        for judge in args.judges
        for set_id in set_ids
        for order, shown in letter_orders(
            set_id, sorted(sets[set_id]["passages"]), args.seed
        ).items()
    ]
    run_parallel(jobs, args.jobs)
    for judge in args.judges:
        records = [
            json.loads((run.out_dir / f"{judge}-{order}-set{set_id}.json").read_text())
            for set_id in set_ids
            for order in ORDERS
        ]
        taus, identical = order_agreement(records)
        logger.info(
            f"{judge}: Kendall tau between the two orders' rankings, mean "
            f"{statistics.mean(taus):.2f} over {len(taus)} sets (lowest {min(taus):.2f}); "
            f"identical rankings in {identical}"
        )


if __name__ == "__main__":
    main()
