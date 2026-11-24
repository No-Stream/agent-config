"""Tests for syntax_profile.py on short public-topic passages, parsed with the real spaCy model."""

from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_DIR))
sys.path.insert(0, str(EVAL_DIR.parent))

import syntax_features
from spacy.language import Language

import syntax_profile
from syntax_profile import (
    Reference,
    analyze_in_chunks,
    document_totals,
    load_reference,
    rates,
    reference_profile,
    save_reference,
    standardized_dependency_length,
    subject_verbs,
    summed,
    word_pairs,
)

REFERENCE_TEXT = (
    "The ferry crosses the bay twice a day. Most riders buy a ticket at the pier."
    " The bottle sits on the pier.\n\n"
    "The library opens at nine, and the reading room stays quiet.\n"
)
LONG_SENTENCE = (
    "The orchard on the hill behind the old mill grows apples, pears and plums, and every"
    " autumn the families from the valley walk up the narrow road to pick the fruit together"
    " before the first frost.\n"
)
# "Researchers" names people by WordNet, though the parser tags it neither a person nor a pronoun.
PEOPLE_AND_THINGS = "The researchers want more data. The cache wants more memory.\n"
PROGRESS = re.compile(r"done=(\d+) total=(\d+) elapsed_seconds=\d+")


@pytest.fixture(scope="module")
def nlp() -> Language:
    return syntax_features.load_model()


@pytest.fixture(scope="module")
def reference(nlp: Language) -> Reference:
    return reference_profile(REFERENCE_TEXT, nlp)


def _totals(text: str, nlp: Language, reference: Reference) -> dict[str, int]:
    return document_totals(syntax_features.analyze(text, nlp, reference.noun_lemmas), reference)


def _progress(caplog: pytest.LogCaptureFixture) -> list[tuple[int, int]]:
    """The (done, total) of each progress line syntax_profile logged."""
    found = (PROGRESS.search(record.getMessage()) for record in caplog.records)
    return [(int(match[1]), int(match[2])) for match in found if match]


class TestWordPairs:
    def test_pairs_are_adjacent_lowercased_words(self, nlp: Language) -> None:
        (sentence,) = syntax_features.analyze("The Ferry leaves early.", nlp)
        assert word_pairs(sentence) == [("the", "ferry"), ("ferry", "leaves"), ("leaves", "early")]

    def test_punctuation_between_words_breaks_the_pair(self, nlp: Language) -> None:
        (sentence,) = syntax_features.analyze("Cats sleep, dogs bark.", nlp)
        assert word_pairs(sentence) == [("cats", "sleep"), ("dogs", "bark")]

    def test_no_pair_contains_the_code_placeholder(self, nlp: Language) -> None:
        (sentence,) = syntax_features.analyze("Run `make check` before you push.", nlp)
        assert word_pairs(sentence) == [("before", "you"), ("you", "push")]


class TestReferenceProfile:
    def test_each_line_is_a_paragraph(self, nlp: Language) -> None:
        built = reference_profile("The pier opens at dawn\nRiders wait for the ferry\n", nlp)
        assert built.sentences == 2
        assert ("dawn", "riders") not in built.pairs

    def test_bin_weights_are_the_arc_shares_of_sentences_up_to_30_words(
        self, nlp: Language
    ) -> None:
        text = "Dogs bark.\n\n" + LONG_SENTENCE + "\nThe ferry crosses the bay twice a day.\n"
        built = reference_profile(text, nlp)
        sentences = syntax_features.analyze(text, nlp)
        short, _, ferry = sentences
        assert syntax_features.length_bin(len(sentences[1].words)) is None
        arcs = len(short.arc_lengths) + len(ferry.arc_lengths)
        assert built.bin_weights == pytest.approx(
            (len(short.arc_lengths) / arcs, len(ferry.arc_lengths) / arcs, 0.0, 0.0, 0.0)
        )

    def test_parsing_in_chunks_leaves_the_reference_unchanged(
        self, nlp: Language, reference: Reference, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(syntax_profile, "PARSE_CHUNK_TEXTS", 1)
        assert reference_profile(REFERENCE_TEXT, nlp) == reference

    def test_holds_the_reference_word_pairs(self, reference: Reference) -> None:
        assert {("the", "ferry"), ("reading", "room"), ("stays", "quiet")} <= reference.pairs
        assert ("the", "river") not in reference.pairs


class TestAnalyzeInChunks:
    def test_matches_one_parsing_pass_and_logs_each_chunk(
        self,
        nlp: Language,
        reference: Reference,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        texts = [
            "Dogs bark. They bottle the cider in October.\n",
            "The ferry crosses the river.\n",
            "We read the book the teacher chose.\n",
        ]
        monkeypatch.setattr(syntax_profile, "PARSE_CHUNK_TEXTS", 2)
        caplog.set_level(logging.INFO, logger=syntax_profile.__name__)
        chunked = analyze_in_chunks(texts, nlp, reference.noun_lemmas, "documents")
        whole = syntax_features.analyze_texts(texts, nlp, reference.noun_lemmas)
        assert [document_totals(sentences, reference) for sentences in chunked] == [
            document_totals(sentences, reference) for sentences in whole
        ]
        assert _progress(caplog) == [(2, 3), (3, 3)]


class TestDocumentTotals:
    def test_counts_words_without_punctuation_or_the_placeholder(
        self, nlp: Language, reference: Reference
    ) -> None:
        totals = _totals("Run `make check` before you push. Dogs bark.", nlp, reference)
        assert (totals["words"], totals["sentences"], totals["word_pairs"]) == (6, 2, 3)

    def test_counts_pairs_the_reference_never_has(
        self, nlp: Language, reference: Reference
    ) -> None:
        totals = _totals("The ferry crosses the river.", nlp, reference)
        assert (totals["word_pairs"], totals["unattested_pairs"]) == (4, 1)

    def test_splits_object_relatives_by_their_relativizer(
        self, nlp: Language, reference: Reference
    ) -> None:
        text = "We read the book the teacher chose. We read the book that the teacher chose.\n"
        totals = _totals(text, nlp, reference)
        assert totals["object_relatives_without_relativizer"] == 1
        assert totals["object_relatives_with_relativizer"] == 1

    def test_counts_relativizers_after_a_preposition_apart(
        self, nlp: Language, reference: Reference
    ) -> None:
        text = (
            "We repaired the bench on which the children sat. We read the book that the teacher"
            " chose. We read the book the teacher chose.\n"
        )
        totals = _totals(text, nlp, reference)
        assert totals["object_relatives_with_relativizer"] == 2
        assert totals["object_relatives_after_preposition"] == 1
        assert totals["object_relatives_without_relativizer"] == 1
        assert totals["object_relatives_kept_long_subject"] == 1

    def test_counts_relatives_with_a_noun_phrase_subject_apart(
        self, nlp: Language, reference: Reference
    ) -> None:
        text = (
            "We read the book she chose. We read the book the teacher chose. We read the book"
            " that the teacher chose.\n"
        )
        totals = _totals(text, nlp, reference)
        assert totals["object_relatives_without_relativizer"] == 2
        assert totals["object_relatives_without_relativizer_long_subject"] == 1
        assert totals["object_relatives_kept_long_subject"] == 1

    def test_counts_noun_stacks_inanimate_subjects_and_denominal_verbs(
        self, nlp: Language, reference: Reference
    ) -> None:
        text = (
            "The city bus route map changed in May. The report shows a steady rise in riders."
            " It expects a list of names. They bottle the cider in October.\n"
        )
        totals = _totals(text, nlp, reference)
        assert totals["noun_stacks"] == 1
        assert (totals["person_subject_candidates"], totals["thing_subject_candidates"]) == (0, 3)
        assert totals["denominal_verb_candidates"] == 1

    def test_splits_inanimate_subject_candidates_into_people_and_things(
        self, nlp: Language, reference: Reference
    ) -> None:
        totals = _totals(PEOPLE_AND_THINGS, nlp, reference)
        assert (totals["person_subject_candidates"], totals["thing_subject_candidates"]) == (1, 1)

    def test_counts_the_verbs_of_person_and_thing_subjects_apart(self, nlp: Language) -> None:
        text = "The report shows a rise. The chart shows a dip. " + PEOPLE_AND_THINGS
        assert subject_verbs(syntax_features.analyze(text, nlp)) == {
            "person_subject_verbs": {"want": 1},
            "thing_subject_verbs": {"show": 2, "want": 1},
        }

    def test_arcs_go_to_the_sentence_length_bin_and_long_sentences_are_dropped(
        self, nlp: Language, reference: Reference
    ) -> None:
        totals = _totals("Dogs bark.\n\n" + LONG_SENTENCE, nlp, reference)
        assert (totals["arcs_0"], totals["arc_length_0"]) == (1, 1)
        assert all(totals[f"arcs_{index}"] == 0 for index in range(1, 5))


WEIGHTS = (0.1, 0.2, 0.3, 0.2, 0.2)


@pytest.fixture
def pooled_totals() -> dict[str, int]:
    return {
        "words": 2000,
        "sentences": 100,
        "object_relatives_with_relativizer": 3,
        "object_relatives_without_relativizer": 5,
        "object_relatives_after_preposition": 1,
        "object_relatives_without_relativizer_long_subject": 2,
        "object_relatives_kept_long_subject": 2,
        "noun_stacks": 8,
        "person_subject_candidates": 4,
        "thing_subject_candidates": 8,
        "denominal_verb_candidates": 2,
        "word_pairs": 1600,
        "unattested_pairs": 40,
        **{f"arcs_{index}": 10 * (index + 1) for index in range(5)},
        **{f"arc_length_{index}": 20 * (index + 1) + 5 * index for index in range(5)},
    }


class TestPooledTotals:
    def test_rates_are_per_thousand_of_their_denominator(
        self, pooled_totals: dict[str, int]
    ) -> None:
        profile = rates(pooled_totals)
        assert profile["object relatives without a relativizer per 1,000 words"] == pytest.approx(
            2.5
        )
        assert profile["noun stacks per 1,000 words"] == pytest.approx(4.0)
        assert profile["thing-subject candidates per 1,000 sentences"] == pytest.approx(80.0)
        assert profile["person-subject candidates per 1,000 sentences"] == pytest.approx(40.0)
        assert profile["denominal-verb candidates per 1,000 sentences"] == pytest.approx(20.0)
        assert profile["unattested word pairs per 1,000 pairs"] == pytest.approx(25.0)

    def test_dependency_length_weights_each_bin_mean(self, pooled_totals: dict[str, int]) -> None:
        bin_means = [(20 * (i + 1) + 5 * i) / (10 * (i + 1)) for i in range(5)]
        expected = sum(weight * mean for weight, mean in zip(WEIGHTS, bin_means))
        assert standardized_dependency_length(pooled_totals, WEIGHTS) == pytest.approx(expected)

    def test_a_bin_with_no_arcs_is_an_error(self, pooled_totals: dict[str, int]) -> None:
        with pytest.raises(ValueError, match="no arcs"):
            standardized_dependency_length(
                {**pooled_totals, "arcs_4": 0, "arc_length_4": 0}, WEIGHTS
            )

    def test_summed_adds_documents(self, pooled_totals: dict[str, int]) -> None:
        total = summed([pooled_totals, pooled_totals])
        assert (total["words"], total["arcs_2"], total["unattested_pairs"]) == (4000, 60, 80)


class TestReferenceFile:
    def test_a_saved_reference_loads_back_unchanged(
        self, tmp_path: Path, reference: Reference
    ) -> None:
        path = tmp_path / "reference.json"
        save_reference(reference, path)
        assert load_reference(path) == reference


class TestScript:
    def test_profiles_each_document_against_a_saved_reference(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.INFO, logger=syntax_profile.__name__)
        documents = {
            "ferry": "The ferry crosses the river. Most riders buy a ticket at the pier.\n",
            "library": "The library opens at nine. We read the book the teacher chose.\n",
            "cider": "They bottle the cider in October.\n",
            "lab": PEOPLE_AND_THINGS,
        }
        manifest = tmp_path / "docs.jsonl"
        lines = []
        for name, text in documents.items():
            (tmp_path / f"{name}.md").write_text(text)
            entry = {"corpus": "town", "arm": name, "path": str(tmp_path / f"{name}.md")}
            lines.append(json.dumps(entry))
        manifest.write_text("\n".join(lines) + "\n")
        (tmp_path / "reference.txt").write_text(REFERENCE_TEXT)
        reference_file, out = tmp_path / "reference.json", tmp_path / "totals.jsonl"
        syntax_profile.main(
            ["reference", "--text", str(tmp_path / "reference.txt"), "--out", str(reference_file)]
        )
        syntax_profile.main(
            [
                "profile",
                "--manifest",
                str(manifest),
                "--reference",
                str(reference_file),
                "--out",
                str(out),
            ]
        )
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        assert [
            (row["arm"], row["words"], row["unattested_pairs"], row["denominal_verb_candidates"])
            for row in rows
        ] == [("ferry", 13, 1, 0), ("library", 12, 6, 0), ("cider", 6, 5, 1), ("lab", 10, 8, 0)]
        assert (rows[3]["person_subject_candidates"], rows[3]["thing_subject_candidates"]) == (1, 1)
        assert (rows[3]["person_subject_verbs"], rows[3]["thing_subject_verbs"]) == (
            {"want": 1},
            {"want": 1},
        )
        assert load_reference(reference_file).sentences == 4
        assert _progress(caplog) == [(2, 2), (4, 4)]
        table = capsys.readouterr().out
        assert "| town | library | 1 | 12 | 0.00 | 83.33 |" in table
        assert "undefined: no arcs in bins [2, 3, 4]" in table
