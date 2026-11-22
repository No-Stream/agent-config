#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["scipy>=1.14"]
# ///
"""Summarize detector scores: distributions by arm, two paired checks on the bheijden matched
topics, and the spread of scores among model drafts and between the chunks of one draft.

Writes markdown to stdout. `--corpus bheijden` limits it to the public matched corpus.
"""

from __future__ import annotations

import argparse
import statistics
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from scipy import stats
from scoring import (
    BHEIJDEN,
    BHEIJDEN_ARMS,
    BHEIJDEN_CORPUS_DIR,
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
    bheijden_pairs,
    prepared_texts,
    read_manifest,
    scores_file,
    split_pending,
)

HUMAN, CORPUS_MODEL = BHEIJDEN_ARMS["human"], BHEIJDEN_ARMS["ai"]
HUMAN_ARMS = {HUMAN, VOICE_ARM}
PLANTED_ARMS = {DEGRADED, TELLS_INJECTED, NEUTRAL_REWRITE}
PLANTED_CONTRASTS = (
    (DEGRADED, NEUTRAL_REWRITE),
    (TELLS_INJECTED, SKILL_DRAFT),
    (NEUTRAL_REWRITE, SKILL_DRAFT),
)
SKILL_CONTRASTS = ((SKILL_DRAFT, NO_SKILL),)
PROVENANCE_CONTRAST = (CORPUS_MODEL, HUMAN)
MIN_PAIRED_TOPICS = 2  # the fewest that give a paired interval
OLD_TEXT_YEAR = 1930
CPU_RESCORE, GPU_RESCORE = "./rescore.sh", "heavy --light -- uv run sagemaker_job.py run"
ByArm = dict[str, dict[str, float]]
Pairs = list[tuple[str, float, float]]
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


def bheijden_scores(texts: Sequence[Text], scores: dict[str, dict]) -> ByArm:
    """Scores on the bheijden corpus by arm, then topic."""
    by_arm: ByArm = defaultdict(dict)
    for text in texts:
        if text.corpus == BHEIJDEN and text.id in scores:
            by_arm[text.arm][text.topic] = scores[text.id]["score"]
    return dict(by_arm)


def bheijden_words(texts: Sequence[Text]) -> dict[tuple[str, str], int]:
    return {(text.arm, text.topic): text.words for text in texts if text.corpus == BHEIJDEN}


def paired(by_arm: ByArm, first: str, second: str) -> Pairs:
    """(topic, first score, second score) for each topic both arms scored, in topic order.

    Fewer than MIN_PAIRED_TOPICS shared topics count as no pairing, here and in every table.
    """
    first_scores, second_scores = by_arm.get(first, {}), by_arm.get(second, {})
    topics = sorted(set(first_scores) & set(second_scores))
    if len(topics) < MIN_PAIRED_TOPICS:
        return []
    return [(topic, first_scores[topic], second_scores[topic]) for topic in topics]


def more_ai_like_topics(detector: Detector, pairs: Pairs) -> set[str]:
    return {topic for topic, first, second in pairs if more_ai_like(detector, first, second)}


def differences(pairs: Pairs) -> list[float]:
    return [first - second for _, first, second in pairs]


def table(columns: Sequence[str], rows: Sequence[str]) -> str:
    return "\n".join(["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns), *rows])


def share_cells(count: int, n: int) -> str:
    share = stats.binomtest(count, n).proportion_ci(confidence_level=0.95, method="wilson")
    return f"{count}/{n} | {share.low:.2f} to {share.high:.2f}"


def difference_cells(values: Sequence[float]) -> str:
    mean = stats.ttest_1samp(values, 0).confidence_interval(0.95)
    return (
        f"{statistics.median(values):.3f} | {statistics.fmean(values):.3f} "
        f"({mean.low:.3f} to {mean.high:.3f})"
    )


def overview_table(by_arm_by_detector: dict[str, ByArm]) -> str:
    contrasts = [PROVENANCE_CONTRAST, *PLANTED_CONTRASTS]
    rows = []
    for name, by_arm in by_arm_by_detector.items():
        cells = []
        for first, second in contrasts:
            pairs = paired(by_arm, first, second)
            more = more_ai_like_topics(DETECTORS[name], pairs)
            cells.append(f"{len(more)}/{len(pairs)}" if pairs else "not scored")
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    return table(["detector", *(f"{first} against {second}" for first, second in contrasts)], rows)


def distribution_table(detector: Detector, texts: Sequence[Text], scores: dict[str, dict]) -> str:
    groups: dict[tuple[str, str], list[Text]] = defaultdict(list)
    for text in texts:
        if text.id in scores:
            groups[text.corpus, text.arm].append(text)
    rows = []
    for (corpus, arm), group in sorted(groups.items()):
        values = sorted(scores[text.id]["score"] for text in group)
        q1, median, q3 = quartiles(values)
        words = statistics.median(text.words for text in group)
        rows.append(
            f"| {corpus} | {arm} | {len(values)} | {words:.0f} | {values[0]:.3f} | {q1:.3f} | "
            f"{median:.3f} | {q3:.3f} | {values[-1]:.3f} | {past_cutoff(detector, values)} |"
        )
    columns = ["corpus", "arm", "n", "median words", "min", "Q1", "median", "Q3", "max"]
    return table([*columns, "past cut-off"], rows)


def provenance_table(detector: Detector, by_arm: ByArm, human_years: dict[str, int]) -> str:
    """Paired by topic: each model arm that is not a planted control minus the human text."""
    rows = []
    for arm in sorted(set(by_arm) - HUMAN_ARMS - PLANTED_ARMS):
        pairs = paired(by_arm, arm, HUMAN)
        if not pairs:
            continue
        more = more_ai_like_topics(detector, pairs)
        old = {topic for topic, _, _ in pairs if human_years[topic] < OLD_TEXT_YEAR}
        recent = {topic for topic, _, _ in pairs} - old
        rows.append(
            f"| {arm} | {len(pairs)} | {share_cells(len(more), len(pairs))} | "
            f"{len(more & old)}/{len(old)} | {len(more & recent)}/{len(recent)} | "
            f"{difference_cells(differences(pairs))} |"
        )
    if not rows:
        return "No model arm shares two or more scored topics with the human texts."
    columns = [
        "model arm",
        "topics",
        "model more AI-like",
        "95% interval",
        f"human text before {OLD_TEXT_YEAR}",
        f"human text from {OLD_TEXT_YEAR}",
        "median model minus human",
        "mean model minus human (95% interval)",
    ]
    return table(columns, rows)


def contrast_table(
    detector: Detector,
    by_arm: ByArm,
    words: dict[tuple[str, str], int],
    contrasts: Sequence[tuple[str, str]],
) -> str:
    """Paired by topic: the first arm of each contrast minus the second."""
    rows = []
    for first, second in contrasts:
        pairs = paired(by_arm, first, second)
        if not pairs:
            continue
        more = more_ai_like_topics(detector, pairs)
        values = differences(pairs)
        first_words = statistics.median(words[first, topic] for topic, _, _ in pairs)
        second_words = statistics.median(words[second, topic] for topic, _, _ in pairs)
        rows.append(
            f"| {first} minus {second} | {len(pairs)} | {share_cells(len(more), len(pairs))} | "
            f"{difference_cells(values)} | {statistics.stdev(values):.3f} | "
            f"{first_words:.0f} / {second_words:.0f} |"
        )
    if not rows:
        return "No contrast has two or more topics scored in both arms."
    columns = [
        "contrast",
        "topics",
        "first more AI-like",
        "95% interval",
        "median difference",
        "mean difference (95% interval)",
        "standard deviation of the difference",
        "median words, first / second",
    ]
    return table(columns, rows)


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
    by_arm: ByArm,
    human_years: dict[str, int],
) -> str:
    words = bheijden_words(texts)
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
            "### Provenance: model texts against the human text on the same topic",
            provenance_table(detector, by_arm, human_years),
            f"### The skill: {SKILL_DRAFT} against {NO_SKILL} on the same topic",
            contrast_table(detector, by_arm, words, SKILL_CONTRASTS),
            "### Planted bad writing",
            contrast_table(detector, by_arm, words, PLANTED_CONTRASTS),
            "### Spread among model drafts and between the chunks of one draft",
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
    by_arm_by_detector = {
        name: bheijden_scores(texts, scores) for name, scores in scores_by_detector.items()
    }
    sections = [
        "## Overview",
        OVERVIEW,
        overview_table(by_arm_by_detector),
        *(
            detector_section(DETECTORS[name], texts, scores, by_arm_by_detector[name], human_years)
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
