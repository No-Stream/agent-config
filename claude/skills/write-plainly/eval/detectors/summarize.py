#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["scipy>=1.14"]
# ///
"""Summarize detector scores: distributions by arm, two paired checks on the bheijden matched
topics, and the spread and chunk noise of scores among model-drafted texts.

Writes markdown to stdout. `--corpus bheijden` limits it to the public matched corpus.
"""

from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from manifest import BHEIJDEN_CORPUS_DIR, bheijden_pairs
from scipy import stats
from scoring import (
    BHEIJDEN,
    BHEIJDEN_ARMS,
    DEGRADED,
    DETECTORS,
    GPU_DETECTORS,
    MANIFEST_FILE,
    NEUTRAL_REWRITE,
    NO_SKILL,
    REPO_ROOT,
    SCORES_DIR,
    SKILL_DRAFT,
    TELLS_INJECTED,
    VOICE_ARM,
    Detector,
    Text,
    prepared_texts,
    read_manifest,
    scores_file,
    split_pending,
)

HUMAN, CORPUS_MODEL = BHEIJDEN_ARMS["human"], BHEIJDEN_ARMS["ai"]
HUMAN_ARMS = frozenset({HUMAN, VOICE_ARM})
PLANTED_ARMS = frozenset({DEGRADED, TELLS_INJECTED, NEUTRAL_REWRITE})
PLANTED_CONTRASTS = (
    (DEGRADED, NEUTRAL_REWRITE),
    (TELLS_INJECTED, SKILL_DRAFT),
    (NEUTRAL_REWRITE, SKILL_DRAFT),
)
SKILL_CONTRASTS = ((SKILL_DRAFT, NO_SKILL),)
OLD_TEXT_YEAR = 1930
CPU_RESCORE, GPU_RESCORE = "./rescore.sh", "heavy --light -- uv run sagemaker_job.py run"
OVERVIEW = (
    "Two separate checks, each paired by topic on the bheijden corpus. Provenance: does the "
    "detector score the published human text as less AI-like than a model's text on the same "
    "topic? Planted bad writing: does the score move toward AI-like when the same skill draft is "
    f"made worse ({DEGRADED}, read against {NEUTRAL_REWRITE}, which rewords the same sentences "
    f"with every fact kept) or given planted tells ({TELLS_INJECTED})? {NEUTRAL_REWRITE} minus "
    f"{SKILL_DRAFT} is the null contrast. The planted check tests whether a higher score goes "
    "with worse writing; provenance shows only that a detector tells these published human texts "
    "from model text. Each cell counts the topics where the first text scores more AI-like."
)


def quartiles(values: Sequence[float]) -> tuple[float, float, float]:
    if len(values) == 1:
        return values[0], values[0], values[0]
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, median, q3


def more_ai_like(detector: Detector, first: float, second: float) -> bool:
    return first > second if detector.higher_is_ai else first < second


def past_cutoff(detector: Detector, values: Sequence[float]) -> str:
    if detector.threshold is None:
        return "n/a"
    flagged = sum(more_ai_like(detector, value, detector.threshold) for value in values)
    return f"{flagged}/{len(values)}"


def bheijden_scores(texts: Sequence[Text], scores: dict[str, dict]) -> dict[str, dict[str, float]]:
    """Scores on the bheijden corpus by arm, then topic."""
    by_arm: dict[str, dict[str, float]] = defaultdict(dict)
    for text in texts:
        if text.corpus == BHEIJDEN and text.id in scores:
            by_arm[text.arm][text.topic] = scores[text.id]["score"]
    return by_arm


def share_cells(count: int, n: int) -> str:
    share = stats.binomtest(count, n).proportion_ci(confidence_level=0.95, method="wilson")
    return f"{count}/{n} | {share.low:.2f} to {share.high:.2f}"


def difference_cells(differences: Sequence[float]) -> str:
    mean = stats.ttest_1samp(differences, 0).confidence_interval(0.95)
    return (
        f"{statistics.median(differences):.3f} | {statistics.fmean(differences):.3f} "
        f"({mean.low:.3f} to {mean.high:.3f})"
    )


def overview_table(texts: Sequence[Text], scores_by_detector: dict[str, dict[str, dict]]) -> str:
    contrasts = [(CORPUS_MODEL, HUMAN), *PLANTED_CONTRASTS]
    lines = [
        "| detector | "
        + " | ".join(f"{first} against {second}" for first, second in contrasts)
        + " |",
        "|---|" + "---|" * len(contrasts),
    ]
    for name, scores in scores_by_detector.items():
        by_arm = bheijden_scores(texts, scores)
        cells = []
        for first, second in contrasts:
            topics = set(by_arm[first]) & set(by_arm[second])
            more = sum(
                more_ai_like(DETECTORS[name], by_arm[first][topic], by_arm[second][topic])
                for topic in topics
            )
            cells.append(f"{more}/{len(topics)}" if topics else "not scored")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


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


def provenance_table(
    detector: Detector,
    texts: Sequence[Text],
    scores: dict[str, dict],
    human_years: dict[str, int],
) -> str:
    """Paired by topic: the human text minus each model arm that is not a planted control."""
    by_arm = bheijden_scores(texts, scores)
    human = by_arm.pop(HUMAN, {})
    lines = [
        (
            "| model arm | topics | human less AI-like | 95% interval | "
            f"human text before {OLD_TEXT_YEAR} | human text from {OLD_TEXT_YEAR} | "
            "median human minus model | mean human minus model (95% interval) |"
        ),
        "|---|---|---|---|---|---|---|---|",
    ]
    for arm, model in sorted(by_arm.items()):
        topics = sorted(set(human) & set(model))
        if arm in PLANTED_ARMS or len(topics) < 2:
            continue
        less = {topic for topic in topics if more_ai_like(detector, model[topic], human[topic])}
        old = {topic for topic in topics if human_years[topic] < OLD_TEXT_YEAR}
        recent = set(topics) - old
        lines.append(
            f"| {arm} | {len(topics)} | {share_cells(len(less), len(topics))} | "
            f"{len(less & old)}/{len(old)} | {len(less & recent)}/{len(recent)} | "
            f"{difference_cells([human[topic] - model[topic] for topic in topics])} |"
        )
    return "\n".join(lines)


def contrast_table(
    detector: Detector,
    texts: Sequence[Text],
    scores: dict[str, dict],
    contrasts: Sequence[tuple[str, str]],
) -> str:
    """Paired by topic: the first arm of each contrast minus the second."""
    by_arm = bheijden_scores(texts, scores)
    words = {(text.arm, text.topic): text.words for text in texts if text.corpus == BHEIJDEN}
    rows = []
    for first, second in contrasts:
        topics = sorted(set(by_arm[first]) & set(by_arm[second]))
        if len(topics) < 2:
            continue
        differences = [by_arm[first][topic] - by_arm[second][topic] for topic in topics]
        more = sum(
            more_ai_like(detector, by_arm[first][topic], by_arm[second][topic]) for topic in topics
        )
        first_words = statistics.median(words[first, topic] for topic in topics)
        second_words = statistics.median(words[second, topic] for topic in topics)
        rows.append(
            f"| {first} minus {second} | {len(topics)} | {share_cells(more, len(topics))} | "
            f"{difference_cells(differences)} | {statistics.stdev(differences):.3f} | "
            f"{first_words:.0f} / {second_words:.0f} |"
        )
    if not rows:
        return "No topic has scores in both arms of these contrasts."
    header = (
        "| contrast | topics | first more AI-like | 95% interval | median difference | "
        "mean difference (95% interval) | standard deviation of the difference | "
        "median words, first / second |"
    )
    return "\n".join([header, "|---|---|---|---|---|---|---|---|", *rows])


def spread_line(detector: Detector, texts: Sequence[Text], scores: dict[str, dict]) -> str:
    scored = [text for text in texts if text.id in scores]
    model_values = [
        scores[text.id]["score"]
        for text in scored
        if text.arm not in HUMAN_ARMS and text.arm not in PLANTED_ARMS
    ]
    human_values = [scores[text.id]["score"] for text in scored if text.arm in HUMAN_ARMS]
    if len(model_values) < 2 or len(human_values) < 2:
        return "Too few texts for a spread."
    q1, _, q3 = quartiles(sorted(model_values))
    return (
        f"Model-drafted texts, planted controls left out (n = {len(model_values)}): standard "
        f"deviation {statistics.stdev(model_values):.3f}, interquartile range {q3 - q1:.3f}, range "
        f"{min(model_values):.3f} to {max(model_values):.3f}, "
        f"{past_cutoff(detector, model_values)} past the cut-off. Human texts "
        f"(n = {len(human_values)}): standard deviation {statistics.stdev(human_values):.3f}."
    )


def chunk_noise_line(texts: Sequence[Text], scores: dict[str, dict]) -> str:
    deviations = [
        statistics.stdev(scores[text.id]["chunk_scores"])
        for text in texts
        if text.id in scores
        and text.arm not in HUMAN_ARMS
        and text.arm not in PLANTED_ARMS
        and len(scores[text.id]["chunk_scores"]) > 1
    ]
    if not deviations:
        return "No model draft outside the planted controls has two or more chunks."
    return (
        "Median standard deviation between the chunks of one text, over the "
        f"{len(deviations)} model drafts outside the planted controls with two or more chunks: "
        f"{statistics.median(deviations):.3f}."
    )


def coverage_line(detector: Detector, texts: Sequence[Text], scores: dict[str, dict]) -> str:
    if len(scores) == len(texts):
        return f"All {len(texts)} texts have a current score."
    command = GPU_RESCORE if detector.name in GPU_DETECTORS else CPU_RESCORE
    return f"{len(scores)} of {len(texts)} texts have a current score; `{command}` scores the rest."


def detector_section(
    detector: Detector,
    texts: Sequence[Text],
    scores: dict[str, dict],
    human_years: dict[str, int],
) -> str:
    direction = "higher" if detector.higher_is_ai else "lower"
    cutoff = "none" if detector.threshold is None else f"{detector.threshold:g}"
    return "\n\n".join(
        [
            f"## {detector.name}",
            (
                f"`{detector.model}`, revision {detector.revision}; score is the {detector.unit}, "
                f"{direction} is more AI-like; window {detector.window} tokens. Cut-off {cutoff}: "
                f"{detector.threshold_source}."
            ),
            coverage_line(detector, texts, scores),
            "### Scores by arm",
            distribution_table(detector, texts, scores),
            "### Provenance: the human text against model texts on the same topic",
            provenance_table(detector, texts, scores, human_years),
            f"### The skill: {SKILL_DRAFT} against {NO_SKILL} on the same topic",
            contrast_table(detector, texts, scores, SKILL_CONTRASTS),
            "### Planted bad writing",
            contrast_table(detector, texts, scores, PLANTED_CONTRASTS),
            "### Spread among model drafts and noise between chunks",
            spread_line(detector, texts, scores),
            chunk_noise_line(texts, scores),
        ]
    )


def summary(
    texts: Sequence[Text], prepared: dict[str, str], scores_dir: Path, human_years: dict[str, int]
) -> str:
    """Every section, from the score records that match each text's current prepared text."""
    scores_by_detector = {
        name: split_pending(prepared, scores_file(scores_dir, name), detector)[0]
        for name, detector in DETECTORS.items()
        if scores_file(scores_dir, name).exists()
    }
    sections = [
        "## Overview",
        OVERVIEW,
        overview_table(texts, scores_by_detector),
        *(
            detector_section(DETECTORS[name], texts, scores, human_years)
            for name, scores in scores_by_detector.items()
        ),
    ]
    return "\n\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=MANIFEST_FILE)
    parser.add_argument("--scores", type=Path, default=SCORES_DIR)
    parser.add_argument("--corpus", help="limit to one corpus")
    args = parser.parse_args()
    texts = [text for text in read_manifest(args.manifest) if args.corpus in (None, text.corpus)]
    human_years = {
        pair["id"]: int(pair["human"]["date"][:4]) for pair in bheijden_pairs(BHEIJDEN_CORPUS_DIR)
    }
    print(summary(texts, prepared_texts(texts, REPO_ROOT), args.scores, human_years))


if __name__ == "__main__":
    main()
