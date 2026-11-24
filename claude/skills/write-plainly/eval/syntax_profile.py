#!/usr/bin/env -S uv run --upgrade --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["nltk", "spacy", "spacy-curated-transformers", "torch"]
#
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# ///
"""The syntactic feature profile of a set of documents, measured against a reference corpus.

The measures are those of Clark, Martin and Mahowald, "Why is AI-generated language so hard to
understand?" (arXiv:2610.29162, Section 3.1 and Appendix B), read from `syntax_features.py`:
object relatives with and without a relativizer and noun stacks per 1,000 words, inanimate-subject
and denominal-verb candidates per 1,000 sentences, dependency length standardized over the
paper's five sentence-length bins with the reference corpus's arc shares as weights (B.3), and
word pairs the reference never has per 1,000 pairs (B.2). A word is a non-punctuation token other
than the code placeholder, and a pair is two adjacent words, lowercased, with no punctuation or
placeholder in it. The reference also supplies the noun-dominant lemmas that make a verb
denominal. `lint_syntax.names_people` splits the inanimate-subject candidates into person
subjects, nouns such as "researchers" that name people though the parser tagged no person, and
thing subjects, the rest. Object relatives whose relativizer follows a preposition ("on which"),
which cannot drop it, and those whose subject is as long as the dropped-relativizer lint asks are
also counted apart. The paper's trigram perplexity is not measured.

`reference_profile` reads the reference corpus, `document_totals` gives one document's counts, and
`summed`, `rates` and `standardized_dependency_length` turn the counts of any set of documents into
the profile. As a script, `reference` saves what the profile needs from the reference corpus (plain
text, one paragraph per line), and `profile` reads a manifest of documents (JSON lines with `path`,
`corpus` and `arm`; other fields are carried through), writes each document's counts and the verbs
of its person and thing subjects as JSON lines, and prints the pooled profile of each corpus and
arm. Both parse in chunks of `PARSE_CHUNK_TEXTS` texts, the reference one paragraph per text, and
log the texts done, the total and the elapsed seconds after each chunk:

    uv run --upgrade syntax_profile.py reference --text ref.txt --out reference.json
    uv run --upgrade syntax_profile.py profile --manifest docs.jsonl --reference reference.json \
        --out totals.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import syntax_features
from lint_syntax import DROPPED_RELATIVIZER_SUBJECT_WORDS, load_wordnet, names_people
from spacy.language import Language
from syntax_features import LENGTH_BINS, InanimateSubject, Sentence, length_bin

logger: logging.Logger = logging.getLogger(__name__)

PER_THOUSAND = 1000.0
PARSE_CHUNK_TEXTS = 100
COUNT_FIELDS = (
    "words",
    "sentences",
    "object_relatives_with_relativizer",
    "object_relatives_without_relativizer",
    "object_relatives_after_preposition",
    "object_relatives_without_relativizer_long_subject",
    "object_relatives_kept_long_subject",
    "noun_stacks",
    "person_subject_candidates",
    "thing_subject_candidates",
    "denominal_verb_candidates",
    "word_pairs",
    "unattested_pairs",
)
# name, numerator, denominator: rates per 1,000 of the denominator, as the paper reports them.
RATES = (
    (
        "object relatives with a relativizer per 1,000 words",
        "object_relatives_with_relativizer",
        "words",
    ),
    (
        "object relatives without a relativizer per 1,000 words",
        "object_relatives_without_relativizer",
        "words",
    ),
    ("noun stacks per 1,000 words", "noun_stacks", "words"),
    ("thing-subject candidates per 1,000 sentences", "thing_subject_candidates", "sentences"),
    ("person-subject candidates per 1,000 sentences", "person_subject_candidates", "sentences"),
    ("denominal-verb candidates per 1,000 sentences", "denominal_verb_candidates", "sentences"),
    ("unattested word pairs per 1,000 pairs", "unattested_pairs", "word_pairs"),
)
STANDARDIZED_DEPENDENCY_LENGTH = "standardized dependency length in words"


@dataclass(frozen=True)
class Reference:
    """What the reference corpus supplies: its word pairs, the share of its dependency arcs in
    each sentence-length bin, its noun-dominant lemmas, and its size."""

    pairs: frozenset[tuple[str, str]]
    bin_weights: tuple[float, ...]
    noun_lemmas: frozenset[str]
    words: int
    sentences: int


def word_pairs(sentence: Sentence) -> list[tuple[str, str]]:
    """Adjacent words of the sentence, lowercased, with neither of them the code placeholder."""
    doc = sentence.doc
    return [
        (left.lower_, right.lower_)
        for left, right in pairwise(doc)
        if not (left.is_punct or left.is_space or right.is_punct or right.is_space)
        and left.i not in sentence.placeholders
        and right.i not in sentence.placeholders
    ]


def _bin_arcs(sentences: Iterable[Sentence]) -> tuple[list[int], list[int]]:
    """Arc counts and summed arc lengths per sentence-length bin; longer sentences are dropped."""
    counts, sums = [0] * len(LENGTH_BINS), [0] * len(LENGTH_BINS)
    for sentence in sentences:
        index = length_bin(len(sentence.words))
        if index is None:
            continue
        counts[index] += len(sentence.arc_lengths)
        sums[index] += sum(sentence.arc_lengths)
    return counts, sums


def analyze_in_chunks(
    texts: Sequence[str], nlp: Language, noun_lemmas: frozenset[str], unit: str
) -> list[list[Sentence]]:
    """`syntax_features.analyze_texts` over the texts in chunks, logging progress after each."""
    started = time.monotonic()
    analyzed: list[list[Sentence]] = []
    for start in range(0, len(texts), PARSE_CHUNK_TEXTS):
        chunk = texts[start : start + PARSE_CHUNK_TEXTS]
        analyzed.extend(syntax_features.analyze_texts(chunk, nlp, noun_lemmas))
        done, total = len(analyzed), len(texts)
        elapsed_seconds = round(time.monotonic() - started)
        logger.info(f"parsed {unit}: {done=} {total=} {elapsed_seconds=}")
    return analyzed


def reference_profile(text: str, nlp: Language) -> Reference:
    """Analyze the reference corpus, plain text with one paragraph per line."""
    paragraphs = [line for line in text.splitlines() if line.strip()]
    sentences = [
        sentence
        for analyzed in analyze_in_chunks(paragraphs, nlp, frozenset(), "reference paragraphs")
        for sentence in analyzed
    ]
    arc_counts, _ = _bin_arcs(sentences)
    total_arcs = sum(arc_counts)
    if total_arcs == 0:
        raise ValueError("the reference corpus has no dependency arcs in sentences of 1-30 words")
    return Reference(
        pairs=frozenset(pair for sentence in sentences for pair in word_pairs(sentence)),
        bin_weights=tuple(count / total_arcs for count in arc_counts),
        noun_lemmas=syntax_features.noun_dominant_lemmas(sentences),
        words=sum(len(s.words) - len(s.placeholders) for s in sentences),
        sentences=len(sentences),
    )


def save_reference(reference: Reference, path: Path) -> None:
    """Write the reference profile as JSON, so many manifests can share one parse of it."""
    path.write_text(
        json.dumps(
            {
                "pairs": sorted(reference.pairs),
                "bin_weights": list(reference.bin_weights),
                "noun_lemmas": sorted(reference.noun_lemmas),
                "words": reference.words,
                "sentences": reference.sentences,
            }
        )
        + "\n"
    )


def load_reference(path: Path) -> Reference:
    saved = json.loads(path.read_text())
    return Reference(
        pairs=frozenset(tuple(pair) for pair in saved["pairs"]),
        bin_weights=tuple(saved["bin_weights"]),
        noun_lemmas=frozenset(saved["noun_lemmas"]),
        words=saved["words"],
        sentences=saved["sentences"],
    )


def split_subjects(
    sentences: Sequence[Sentence],
) -> tuple[list[InanimateSubject], list[InanimateSubject]]:
    """The inanimate-subject candidates whose subject names people, and the rest, the things."""
    wordnet = load_wordnet()
    people: list[InanimateSubject] = []
    things: list[InanimateSubject] = []
    for candidate in (c for s in sentences for c in s.inanimate_subjects):
        (people if names_people(candidate, wordnet) else things).append(candidate)
    return people, things


def document_totals(sentences: Sequence[Sentence], reference: Reference) -> dict[str, int]:
    """One document's feature counts, its words, sentences and word pairs, and its arc counts and
    summed arc lengths per sentence-length bin (`arcs_<bin>`, `arc_length_<bin>`)."""
    pairs = [pair for sentence in sentences for pair in word_pairs(sentence)]
    relatives = [r for s in sentences for r in s.object_relatives]
    people, things = split_subjects(sentences)
    totals = {
        "words": sum(len(s.words) - len(s.placeholders) for s in sentences),
        "sentences": len(sentences),
        "object_relatives_with_relativizer": sum(r.relativizer is not None for r in relatives),
        "object_relatives_without_relativizer": sum(r.relativizer is None for r in relatives),
        "object_relatives_after_preposition": sum(r.preposition is not None for r in relatives),
        "object_relatives_without_relativizer_long_subject": sum(
            r.relativizer is None and r.subject_words >= DROPPED_RELATIVIZER_SUBJECT_WORDS
            for r in relatives
        ),
        "object_relatives_kept_long_subject": sum(
            r.relativizer is not None
            and r.preposition is None
            and r.subject_words >= DROPPED_RELATIVIZER_SUBJECT_WORDS
            for r in relatives
        ),
        "noun_stacks": sum(len(s.noun_stacks) for s in sentences),
        "person_subject_candidates": len(people),
        "thing_subject_candidates": len(things),
        "denominal_verb_candidates": sum(len(s.denominal_verbs) for s in sentences),
        "word_pairs": len(pairs),
        "unattested_pairs": sum(pair not in reference.pairs for pair in pairs),
    }
    arc_counts, arc_sums = _bin_arcs(sentences)
    for index, (count, length) in enumerate(zip(arc_counts, arc_sums)):
        totals[f"arcs_{index}"] = count
        totals[f"arc_length_{index}"] = length
    return totals


def empty_bins(totals: dict[str, int]) -> list[int]:
    """The sentence-length bins with no arcs, where a bin mean, and so the standardized length,
    is undefined."""
    return [index for index in range(len(LENGTH_BINS)) if totals[f"arcs_{index}"] == 0]


def subject_verbs(sentences: Sequence[Sentence]) -> dict[str, dict[str, int]]:
    """How often each verb lemma has a person subject and a thing subject, so a reader can keep
    only the verbs that normally take a person, as the paper's classifier does."""
    people, things = split_subjects(sentences)
    return {
        "person_subject_verbs": dict(Counter(candidate.verb_lemma for candidate in people)),
        "thing_subject_verbs": dict(Counter(candidate.verb_lemma for candidate in things)),
    }


def standardized_dependency_length(totals: dict[str, int], bin_weights: Sequence[float]) -> float:
    """Each bin's mean arc length, averaged with the reference's arc shares as weights (B.3)."""
    if len(bin_weights) != len(LENGTH_BINS):
        raise ValueError(f"expected {len(LENGTH_BINS)} bin weights, got {len(bin_weights)}")
    if empty := empty_bins(totals):
        raise ValueError(f"no arcs in sentence-length bins {empty}, so the bin mean is undefined")
    return sum(
        weight * totals[f"arc_length_{index}"] / totals[f"arcs_{index}"]
        for index, weight in enumerate(bin_weights)
    )


def summed(rows: Iterable[dict[str, int]]) -> dict[str, int]:
    """The counts of several documents added up, the pooled totals the profile is read from."""
    keys = COUNT_FIELDS + tuple(
        f"{name}_{index}" for index in range(len(LENGTH_BINS)) for name in ("arcs", "arc_length")
    )
    rows = list(rows)
    return {key: sum(row[key] for row in rows) for key in keys}


def rates(totals: dict[str, int]) -> dict[str, float]:
    """The profile's rates per 1,000 words, sentences or pairs of documents summed into `totals`."""
    return {
        name: PER_THOUSAND * totals[numerator] / totals[denominator]
        for name, numerator, denominator in RATES
    }


def _profile_table(rows: list[dict], bin_weights: Sequence[float]) -> str:
    groups: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        groups.setdefault((row["corpus"], row["arm"]), []).append(row)
    names = [name for name, _, _ in RATES]
    lines = [
        "| corpus | arm | documents | words | "
        + " | ".join([*names, STANDARDIZED_DEPENDENCY_LENGTH])
        + " |",
        "|---" * (5 + len(names)) + "|",
    ]
    for (corpus, arm), members in sorted(groups.items()):
        totals = summed(members)
        values = [f"{value:.2f}" for value in rates(totals).values()]
        empty = empty_bins(totals)
        values.append(
            f"undefined: no arcs in bins {empty}"
            if empty
            else f"{standardized_dependency_length(totals, bin_weights):.2f}"
        )
        row = [corpus, arm, str(len(members)), str(totals["words"]), *values]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _write_reference(options: argparse.Namespace) -> None:
    reference = reference_profile(options.text.read_text(), syntax_features.load_model())
    logger.info(
        f"reference: {reference.words} words, {reference.sentences} sentences, "
        f"{len(reference.pairs)} distinct pairs, bin weights {reference.bin_weights}"
    )
    save_reference(reference, options.out)


def _write_profile(options: argparse.Namespace) -> None:
    entries = [json.loads(line) for line in options.manifest.read_text().splitlines() if line]
    reference = load_reference(options.reference)
    texts = [Path(entry["path"]).read_text() for entry in entries]
    analyzed = analyze_in_chunks(
        texts, syntax_features.load_model(), reference.noun_lemmas, "documents"
    )
    rows = [
        {
            **entry,
            **document_totals(sentences, reference),
            **subject_verbs(sentences),
        }
        for entry, sentences in zip(entries, analyzed, strict=True)
    ]
    with options.out.open("w") as out:
        for row in rows:
            out.write(json.dumps(row) + "\n")
    sys.stdout.write(_profile_table(rows, reference.bin_weights) + "\n")


def main(argv: Sequence[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    reference = commands.add_parser("reference", help="parse the reference corpus once")
    reference.add_argument("--text", type=Path, required=True, help="one paragraph per line")
    reference.add_argument("--out", type=Path, required=True, help="reference profile, JSON")
    reference.set_defaults(run=_write_reference)
    profile = commands.add_parser("profile", help="profile the documents of a manifest")
    profile.add_argument("--manifest", type=Path, required=True, help="documents, JSON lines")
    profile.add_argument("--reference", type=Path, required=True, help="from `reference`")
    profile.add_argument("--out", type=Path, required=True, help="per-document counts")
    profile.set_defaults(run=_write_profile)
    options = parser.parse_args(argv)
    options.run(options)


if __name__ == "__main__":
    main()
