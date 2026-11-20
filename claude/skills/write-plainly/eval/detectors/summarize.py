#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["scipy>=1.14"]
# ///
"""Summarize detector scores: distributions by arm, the human-against-model positive control on the
bheijden matched topics, and the spread of scores among model-drafted texts.

Writes markdown to stdout. `--corpus bheijden` limits it to the public matched corpus.
"""

from __future__ import annotations

import argparse
import math
import statistics
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from scipy import stats
from scoring import DETECTORS, Detector, Text, read_jsonl, read_manifest

REPO = Path(__file__).resolve().parents[5]
PRIVATE_DETECTORS = REPO / ".private" / "eval" / "detectors"
HUMAN_ARMS = {"human", "human-jan"}
CONTROL_CORPUS, CONTROL_HUMAN = "bheijden", "human"
Z95 = statistics.NormalDist().inv_cdf(0.975)


def wilson(successes: int, n: int) -> tuple[float, float]:
    share = successes / n
    centre = (share + Z95**2 / (2 * n)) / (1 + Z95**2 / n)
    half = Z95 / (1 + Z95**2 / n) * math.sqrt(share * (1 - share) / n + Z95**2 / (4 * n**2))
    return centre - half, centre + half


def mean_interval(values: Sequence[float]) -> tuple[float, float, float]:
    mean = statistics.fmean(values)
    half = stats.t.ppf(0.975, len(values) - 1) * statistics.stdev(values) / math.sqrt(len(values))
    return mean, mean - half, mean + half


def quartiles(values: Sequence[float]) -> tuple[float, float, float]:
    if len(values) == 1:
        return values[0], values[0], values[0]
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, median, q3


def less_ai_like(detector: Detector, human: float, model: float) -> bool:
    return human < model if detector.higher_is_ai else human > model


def distribution_table(detector: Detector, texts: Sequence[Text], scores: dict[str, dict]) -> str:
    groups: dict[tuple[str, str], list[Text]] = defaultdict(list)
    for text in texts:
        if text.id in scores:
            groups[text.corpus, text.arm].append(text)
    lines = [
        "| corpus | arm | n | median words | min | Q1 | median | Q3 | max | past cut-off |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for (corpus, arm), group in sorted(groups.items()):
        values = sorted(scores[text.id]["score"] for text in group)
        q1, median, q3 = quartiles(values)
        words = statistics.median(text.words for text in group)
        lines.append(
            f"| {corpus} | {arm} | {len(values)} | {words:.0f} | {values[0]:.3f} | {q1:.3f} | "
            f"{median:.3f} | {q3:.3f} | {values[-1]:.3f} | {past_cutoff(detector, values)} |"
        )
    return "\n".join(lines)


def past_cutoff(detector: Detector, values: Sequence[float]) -> str:
    if detector.threshold is None:
        return "n/a"
    flagged = sum(
        (value > detector.threshold) if detector.higher_is_ai else (value < detector.threshold)
        for value in values
    )
    return f"{flagged}/{len(values)}"


def control_table(detector: Detector, texts: Sequence[Text], scores: dict[str, dict]) -> str:
    """Paired by topic: human minus each model arm on the bheijden corpus."""
    by_arm: dict[str, dict[str, float]] = defaultdict(dict)
    for text in texts:
        if text.corpus == CONTROL_CORPUS and text.id in scores:
            by_arm[text.arm][text.topic] = scores[text.id]["score"]
    human = by_arm.pop(CONTROL_HUMAN, {})
    lines = [
        (
            "| model arm | topics | human less AI-like | 95% interval | median human minus model | "
            "mean human minus model (95% interval) |"
        ),
        "|---|---|---|---|---|---|",
    ]
    for arm, model in sorted(by_arm.items()):
        topics = sorted(set(human) & set(model))
        if len(topics) < 2:
            continue
        differences = [human[topic] - model[topic] for topic in topics]
        wins = sum(less_ai_like(detector, human[topic], model[topic]) for topic in topics)
        low, high = wilson(wins, len(topics))
        mean, mean_low, mean_high = mean_interval(differences)
        lines.append(
            f"| {arm} | {len(topics)} | {wins}/{len(topics)} | {low:.2f} to {high:.2f} | "
            f"{statistics.median(differences):.3f} | {mean:.3f} ({mean_low:.3f} to {mean_high:.3f}) |"
        )
    return "\n".join(lines)


def spread_line(detector: Detector, texts: Sequence[Text], scores: dict[str, dict]) -> str:
    model_values = [
        scores[text.id]["score"]
        for text in texts
        if text.arm not in HUMAN_ARMS and text.id in scores
    ]
    human_values = [
        scores[text.id]["score"] for text in texts if text.arm in HUMAN_ARMS and text.id in scores
    ]
    if len(model_values) < 2 or len(human_values) < 2:
        return "Too few texts for a spread."
    q1, _, q3 = quartiles(sorted(model_values))
    return (
        f"Model-drafted texts (n = {len(model_values)}): standard deviation "
        f"{statistics.stdev(model_values):.3f}, interquartile range {q3 - q1:.3f}, range "
        f"{min(model_values):.3f} to {max(model_values):.3f}, "
        f"{past_cutoff(detector, model_values)} past the cut-off. Human texts "
        f"(n = {len(human_values)}): standard deviation {statistics.stdev(human_values):.3f}."
    )


def detector_section(detector: Detector, texts: Sequence[Text], scores: dict[str, dict]) -> str:
    direction = "higher" if detector.higher_is_ai else "lower"
    cutoff = "none" if detector.threshold is None else f"{detector.threshold:g}"
    return "\n\n".join(
        [
            f"### {detector.name}",
            (
                f"`{detector.model}`, revision {detector.revision}; score is the {detector.unit}, "
                f"{direction} is more AI-like; window {detector.window} tokens. Cut-off {cutoff}: "
                f"{detector.threshold_source}."
            ),
            distribution_table(detector, texts, scores),
            control_table(detector, texts, scores),
            spread_line(detector, texts, scores),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=PRIVATE_DETECTORS / "manifest.jsonl")
    parser.add_argument("--scores", type=Path, default=PRIVATE_DETECTORS / "scores")
    parser.add_argument("--corpus", help="limit to one corpus")
    args = parser.parse_args()
    texts = [t for t in read_manifest(args.manifest) if args.corpus in (None, t.corpus)]
    sections = []
    for name, detector in DETECTORS.items():
        scores_file = args.scores / f"{name}.jsonl"
        if scores_file.exists():
            scores = {row["id"]: row for row in read_jsonl(scores_file)}
            sections.append(detector_section(detector, texts, scores))
    print("\n\n".join(sections))


if __name__ == "__main__":
    main()
