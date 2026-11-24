"""Tests for lint_syntax.py, parsed with the real spaCy model."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from spacy.language import Language

import lint_syntax
import syntax_features


@pytest.fixture(scope="module")
def nlp() -> Language:
    return syntax_features.load_model()


def _rules(text: str, nlp: Language) -> list[tuple[str, int, int]]:
    return [(f.rule, f.line, f.column) for f in lint_syntax.lint_text(text, nlp)]


class TestDroppedRelativizer:
    def test_flags_a_clause_without_that_before_a_noun_phrase_subject(self, nlp: Language) -> None:
        assert _rules("We ate the bread the old baker sold.\n", nlp) == [
            ("dropped-relativizer", 1, 12)
        ]

    @pytest.mark.parametrize(
        "text",
        [
            "We ate the bread you sold.\n",
            "We ate the bread that the old baker sold.\n",
            "The policy covers every case where the old rule failed.\n",
            "That is not something one small survey can show.\n",
            "Nearly everything the new library needs is already built.\n",
            "Avoid noun stacks whose grouping a careful reader has to guess.\n",
        ],
        ids=[
            *("pronoun-subject", "kept-that", "where-clause", "something", "everything"),
            "whose-noun",
        ],
    )
    def test_passes_other_relative_clauses(self, nlp: Language, text: str) -> None:
        assert _rules(text, nlp) == []

    def test_passes_a_clause_inside_a_quotation(self, nlp: Language) -> None:
        assert _rules('The sign read "the bread the old baker sold" in chalk.\n', nlp) == []

    def test_reports_the_line_and_column_in_the_source(self, nlp: Language) -> None:
        text = "# Market notes\n\nIntro line.\n\n- We ate the bread the old baker sold.\n"
        (finding,) = lint_syntax.lint_text(text, nlp)
        assert (finding.line, finding.column) == (5, 14)
        assert finding.excerpt == "- We ate the bread the old baker sold."


class TestNounStack:
    def test_flags_four_common_nouns_in_one_stack(self, nlp: Language) -> None:
        text = "The county library volunteer training schedule changed in March.\n"
        assert _rules(text, nlp) == [("noun-stack", 1, 5)]

    @pytest.mark.parametrize(
        "text",
        [
            "The museum ticket price rose.\n",
            "Long error-message string literals stay.\n",
            "The Boston harbor ferry schedule changed.\n",
        ],
        ids=["three-nouns", "hyphenated-compound", "proper-noun"],
    )
    def test_passes_stacks_of_three_words(self, nlp: Language, text: str) -> None:
        assert _rules(text, nlp) == []


class TestSubjectVerbGap:
    def test_flags_a_subject_far_from_its_verb(self, nlp: Language) -> None:
        text = (
            "The garden behind the old stone house at the end of the long and narrow lane by the"
            " old mill needs water.\n"
        )
        assert _rules(text, nlp) == [("subject-verb-gap", 1, 5)]

    def test_an_and_inside_a_phrase_on_the_verb_does_not_hide_the_gap(self, nlp: Language) -> None:
        text = (
            "The committee, after weeks of heated debate and two failed votes in the late spring"
            " of that year, approved the budget.\n"
        )
        assert _rules(text, nlp) == [("subject-verb-gap", 1, 5)]

    @pytest.mark.parametrize(
        "text",
        [
            "The garden behind the old stone house at the end of the lane needs water.\n",
            (
                "The plan: three steps, each with a long list of owners and dates for every single"
                " task we have, starts today.\n"
            ),
        ],
        ids=["shorter-gap", "colon-between"],
    )
    def test_passes_short_gaps_and_gaps_across_a_clause(self, nlp: Language, text: str) -> None:
        assert _rules(text, nlp) == []


class TestInanimateSubject:
    @pytest.mark.parametrize(
        "text",
        [
            "The cache knows which pages are stale.\n",
            "Every new reading list hopes to reach more members.\n",
            "The weather station knew the storm was coming.\n",
            "Our second shelf layout wants more light.\n",
            "The tide table, printed every spring for the harbor, wants a new layout.\n",
            "The old tide gauge promised a dry weekend.\n",
            "The ferry timetable promises to run every hour.\n",
            "The overnight backup ate most of the disk.\n",
            "Second, the parking objection misunderstands how the ferry timetable works.\n",
            "The long thread is eating the whole afternoon.\n",
            "The ferry queue wants a second ramp.\n",
            "The interpreter knows which names are defined.\n",
            "The late corrections promise a cleaner table.\n",
        ],
        ids=[
            *("knows", "hopes", "knew", "wants", "wants-after-a-long-subject", "promised"),
            *("promises-to-act", "ate", "misunderstands", "is-eating", "group-of-things"),
            *("technical-noun", "plural-read-by-its-lemma"),
        ],
    )
    def test_flags_a_thing_that_wants_knows_promises_or_eats(
        self, nlp: Language, text: str
    ) -> None:
        assert [rule for rule, _, _ in _rules(text, nlp)] == ["inanimate-subject"]

    @pytest.mark.parametrize(
        "text",
        [
            "The appendix carries the full list of stations.\n",
            "Every quiet reading room earns its heating budget.\n",
            "The new night timetable buys the buses more riders.\n",
            "We kept the index, because the index repays the hour it took to build.\n",
            "Drop the banners that crowd the doorway.\n",
            "The old appendix carried every station.\n",
            "The tracker carries the launch checklist.\n",
            "The tagger buys speed with a smaller vocabulary.\n",
            "The audit of the new residents carries most of the cost.\n",
            "The printing press carried the old texts to every town.\n",
        ],
        ids=[
            *("carries", "earns", "buys", "repays", "crowd", "carried"),
            *("technical-noun", "algorithm", "head-before-of-people", "printing-press"),
        ],
    )
    def test_asks_about_a_thing_that_carries_earns_or_buys(self, nlp: Language, text: str) -> None:
        assert [rule for rule, _, _ in _rules(text, nlp)] == ["inanimate-subject-check"]

    @pytest.mark.parametrize(
        "text",
        [
            "Their high hopes faded.\n",
            "The big crowd cheered.\n",
            "The businesses want lower taxes.\n",
            "The universities want more funding.\n",
            "The wives knew the answer.\n",
            "The librarian knows every regular.\n",
            "The Rovers want a new pitch.\n",
            "The residents want a new park.\n",
            "The experts know the risk.\n",
            "The rest of the choir wants a longer break.\n",
            "The volunteers carry the boxes upstairs.\n",
            "The new API promises to be faster.\n",
            "The coming weekend promises to become a washout.\n",
            "It might want a bigger buffer.\n",
            "No one knows the answer yet.\n",
            "Thousands bought tickets on the first day.\n",
            "The audit carries out three checks a year.\n",
            "The choir hopes to tour in May.\n",
            "Species that eat hard seeds have strong jaws.\n",
            "Product development wants a longer beta.\n",
            "A server carries the same plates to every table.\n",
            "The reviewer wants a shorter summary.\n",
            "A large share of the households can buy faster broadband.\n",
            "None of us knows the answer yet.\n",
        ],
        ids=[
            *("noun-hopes", "noun-crowd", "es-plural", "ies-plural", "ves-plural", "librarian"),
            *("team-name", "residents", "experts", "partitive", "people-carry"),
            *("promise-to-be", "promise-to-become", "pronoun", "no-one", "count", "phrasal"),
            *("social-group", "species", "department", "server-as-waiter", "reviewer"),
            *("share-of-people", "none-of-us"),
        ],
    )
    def test_passes_people_nouns_and_likely_outcomes(self, nlp: Language, text: str) -> None:
        assert _rules(text, nlp) == []

    @pytest.mark.parametrize(
        "text",
        [
            "The model wants more rainfall data.\n",
            "The docstring promises sorted output.\n",
            "A small fee buys quicker returns.\n",
        ],
        ids=["artifact-wants", "document-promises", "abstract-buys"],
    )
    def test_leaves_the_nouns_lint_prose_reads_to_lint_prose(
        self, nlp: Language, text: str
    ) -> None:
        assert _rules(text, nlp) == []


class TestMain:
    def test_prints_findings_and_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "market.md"
        path.write_text("We ate the bread the old baker sold.\n", encoding="utf-8")
        assert lint_syntax.main([str(path)]) == 1
        message = lint_syntax.MESSAGES["dropped-relativizer"]
        assert capsys.readouterr().out == (
            f"{path}:1:12: dropped-relativizer: {message} | We ate the bread the old baker sold.\n"
        )

    def test_writes_json(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = tmp_path / "market.md"
        path.write_text("We ate the bread the old baker sold.\n", encoding="utf-8")
        assert lint_syntax.main(["--json", str(path)]) == 1
        (finding,) = json.loads(capsys.readouterr().out)
        assert (finding["rule"], finding["path"], finding["line"]) == (
            "dropped-relativizer",
            str(path),
            1,
        )

    def test_a_clean_file_exits_0(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = tmp_path / "market.md"
        path.write_text("The baker sold the bread.\n", encoding="utf-8")
        assert lint_syntax.main([str(path)]) == 0
        assert capsys.readouterr().out == ""

    def test_a_missing_file_exits_2(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exit_info:
            lint_syntax.main([str(tmp_path / "missing.md")])
        assert exit_info.value.code == 2
