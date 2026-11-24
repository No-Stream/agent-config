"""Tests for syntax_features.py on short passages, parsed with the real spaCy model."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
import spacy
from spacy.language import Language
from spacy.tokens import Doc
from spacy.util import get_minor_version, is_compatible_version
from spacy.vocab import Vocab

import syntax_features
from lint_prose_markdown import PLACEHOLDER
from syntax_features import Sentence, analyze, analyze_texts, length_bin


@pytest.fixture(scope="module")
def nlp() -> Language:
    return syntax_features.load_model()


def _one(text: str, nlp: Language, noun_lemmas: frozenset[str] = frozenset()) -> Sentence:
    (sentence,) = analyze(text, nlp, noun_lemmas)
    return sentence


class TestLoadModel:
    def test_loads_the_transformer_english_model_for_the_installed_spacy(
        self, nlp: Language
    ) -> None:
        assert (nlp.meta["lang"], nlp.meta["name"]) == ("en", "core_web_trf")
        assert is_compatible_version(spacy.about.__version__, nlp.meta["spacy_version"])
        assert {"transformer", "tagger", "parser", "lemmatizer", "ner"} <= set(nlp.pipe_names)

    def test_takes_the_newest_version_the_compatibility_table_lists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        minor = get_minor_version(spacy.about.__version__)
        table = {"spacy": {minor: {"en_core_web_trf": ["9.1.0", "9.0.0"]}}}
        monkeypatch.setattr(
            syntax_features.urllib.request,
            "urlopen",
            lambda url, timeout: io.BytesIO(json.dumps(table).encode()),
        )
        assert syntax_features._latest_compatible_version() == "9.1.0"

    def test_a_spacy_the_table_does_not_list_is_an_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        table = {"spacy": {"0.1": {"en_core_web_trf": ["0.1.0"]}}}
        monkeypatch.setattr(
            syntax_features.urllib.request,
            "urlopen",
            lambda url, timeout: io.BytesIO(json.dumps(table).encode()),
        )
        with pytest.raises(LookupError):
            syntax_features._latest_compatible_version()

    def test_unpacks_the_wheel_into_the_cache_and_leaves_no_scratch(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        wheel = io.BytesIO()
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr("en_core_web_trf/en_core_web_trf-9.1.0/meta.json", "{}")
        urls: list[str] = []

        def serve(url: str, timeout: int) -> io.BytesIO:
            urls.append(url)
            return io.BytesIO(wheel.getvalue())

        monkeypatch.setattr(syntax_features.urllib.request, "urlopen", serve)
        model_dir = tmp_path / "en_core_web_trf-9.1.0"
        syntax_features._fetch_model("9.1.0", model_dir)
        release = "en_core_web_trf-9.1.0"
        assert urls == [f"{spacy.about.__download_url__}/{release}/{release}-py3-none-any.whl"]
        assert (model_dir / "en_core_web_trf" / release / "meta.json").is_file()
        assert [path.name for path in tmp_path.iterdir()] == [model_dir.name]


class TestPreparation:
    def test_code_urls_and_paths_become_one_word_and_markup_goes(self, nlp: Language) -> None:
        sentence = _one(
            "Run `make test` and read [the guide](https://example.org/guide) in"
            " ~/notes/todo.md before **every** release.\n",
            nlp,
        )
        assert sentence.words == (
            *("Run", PLACEHOLDER, "and", "read", "the", "guide", "in", PLACEHOLDER),
            *("before", "every", "release"),
        )
        assert len(sentence.placeholders) == 2

    def test_identifiers_are_placeholders_and_word_pairs_are_not(self, nlp: Language) -> None:
        first, second = analyze(
            "Set max_rows or call reset() on os.path before launch. Use one and/or two.\n", nlp
        )
        assert first.words.count(PLACEHOLDER) == 3
        assert PLACEHOLDER not in second.words

    def test_reads_only_prose_blocks(self, nlp: Language) -> None:
        text = (
            "# A heading with several words\n\nThe cat sat.\n\n```\nThe dog ran far away.\n```\n\n"
            "| a | b |\n|---|---|\n| The bird flew. | x |\n\n> The fish swam.\n"
        )
        assert [sentence.span.text for sentence in analyze(text, nlp)] == ["The cat sat."]

    def test_list_markers_are_not_words_and_items_split_into_sentences(self, nlp: Language) -> None:
        sentences = analyze("- First item here.\n- Second item. It has two sentences.\n", nlp)
        assert [sentence.words[0] for sentence in sentences] == ["First", "Second", "It"]
        assert [(s.span.line, s.span.column) for s in sentences] == [(1, 3), (2, 3), (2, 16)]

    def test_an_arrow_ends_the_sentence(self, nlp: Language) -> None:
        sentences = analyze("Load the data → train the model.\n", nlp)
        assert [sentence.span.text for sentence in sentences] == [
            "Load the data",
            "train the model.",
        ]

    def test_spans_index_the_analyzed_text(self, nlp: Language) -> None:
        text = "Intro line.\n\nThe second paragraph has `code` in it.\n"
        sentence = analyze(text, nlp)[1]
        span = sentence.span
        assert (span.line, span.column) == (3, 1)
        assert span.text == text[span.start : span.end] == "The second paragraph has `code` in it."

    def test_many_texts_parse_as_each_alone(self, nlp: Language) -> None:
        texts = ["The museum ticket price rose.\n", "We ate the bread the baker sold.\n"]
        assert analyze_texts(texts, nlp) == [analyze(text, nlp) for text in texts]


class TestNounStacks:
    def test_finds_a_chain_of_compound_nouns(self, nlp: Language) -> None:
        sentence = _one("The county library volunteer training schedule changed in March.", nlp)
        (stack,) = sentence.noun_stacks
        assert (stack.span.text, stack.nouns, stack.proper_nouns) == (
            "county library volunteer training schedule",
            5,
            0,
        )
        assert stack.span.column == 5

    def test_three_nouns_are_a_stack_and_two_are_not(self, nlp: Language) -> None:
        stacked, plain = analyze("The museum ticket price rose. The page size changed.", nlp)
        assert [stack.nouns for stack in stacked.noun_stacks] == [3]
        assert plain.noun_stacks == ()

    def test_code_does_not_count_as_a_noun(self, nlp: Language) -> None:
        assert _one("The `max_rows` page size changed.", nlp).noun_stacks == ()

    def test_a_hyphenated_compound_is_one_word_of_the_stack(self, nlp: Language) -> None:
        (stack,) = _one("Long error-message string literals stay.", nlp).noun_stacks
        assert (stack.span.text, stack.nouns, stack.common_words) == (
            "error-message string literals",
            4,
            3,
        )

    def test_a_slash_compound_is_one_word_and_the_slash_no_noun(self, nlp: Language) -> None:
        (stack,) = _one("We tuned the I/O buffer pool size.", nlp).noun_stacks
        assert (stack.span.text, stack.nouns, stack.common_words) == ("I/O buffer pool size", 5, 4)

    def test_proper_nouns_are_not_common_words(self, nlp: Language) -> None:
        (stack,) = _one("The Boston harbor ferry schedule changed.", nlp).noun_stacks
        assert (stack.nouns, stack.proper_nouns, stack.common_words) == (4, 1, 3)


class TestObjectRelatives:
    def test_a_dropped_relativizer(self, nlp: Language) -> None:
        (relative,) = _one("We ate the bread the baker sold.", nlp).object_relatives
        assert (relative.head, relative.verb, relative.relativizer) == ("bread", "sold", None)
        assert relative.span.text == "bread the baker sold"

    def test_a_kept_relativizer(self, nlp: Language) -> None:
        (relative,) = _one("We ate the bread that the baker sold.", nlp).object_relatives
        assert relative.relativizer == "that"
        assert relative.span.text == "bread that the baker sold"

    def test_a_stranded_preposition_is_an_object_gap(self, nlp: Language) -> None:
        (relative,) = _one("We visited the parks they care about.", nlp).object_relatives
        assert (relative.relativizer, relative.span.text) == (None, "parks they care about")

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("We repaired the bench on which the children sat.", ("which", "on")),
            ("We met the colleague by whom I sat.", ("whom", "by")),
            ("We ate the bread which the baker sold.", ("which", None)),
            ("We ate the bread that the baker sold.", ("that", None)),
            ("We kept the tool which I rely on.", ("which", None)),
            ("We ate the bread the baker sold.", (None, None)),
        ],
        ids=["on-which", "by-whom", "which", "that", "stranded", "dropped"],
    )
    def test_names_a_preposition_only_when_it_comes_before_the_relativizer(
        self, nlp: Language, text: str, expected: tuple[str | None, str | None]
    ) -> None:
        (relative,) = _one(text, nlp).object_relatives
        assert (relative.relativizer, relative.preposition) == expected

    def test_counts_the_words_of_the_clause_subject(self, nlp: Language) -> None:
        long_subject, pronoun = analyze(
            "We ate the bread the old baker sold. We ate the bread you sold.", nlp
        )
        assert [relative.subject_words for relative in long_subject.object_relatives] == [3]
        assert [relative.subject_words for relative in pronoun.object_relatives] == [1]

    @pytest.mark.parametrize(
        ("text", "head", "verb"),
        [
            ("The ferry cuts the number of trips the old bridge must carry.", "trips", "carry"),
            ("We counted the birds the old lighthouse keeper had seen.", "birds", "seen"),
        ],
        ids=["clause-attached-to-another-noun", "clause-read-as-a-complement"],
    )
    def test_reads_a_noun_right_before_a_clause_subject_as_its_head(
        self, nlp: Language, text: str, head: str, verb: str
    ) -> None:
        (relative,) = _one(text, nlp).object_relatives
        assert (relative.head, relative.verb, relative.relativizer) == (head, verb, None)
        assert relative.span.text.startswith(head)

    @pytest.mark.parametrize(
        "text",
        [
            "The bread that was sold by the baker was warm.",
            "I like the way she paints.",
            "That was the reason he left the club.",
            "The policy covers every case where the old rule failed.",
            "We studied the groups whose members joined later.",
            "She told the team the old build failed.",
            "She told us the old bridge closed.",
            "We left early, and in the morning the old baker arrived.",
            "We left early, and among people with small boats the news spread.",
            "Ask the florist which shelf each of the old plants came from.",
            "Avoid noun stacks whose grouping a careful reader has to guess.",
        ],
        ids=[
            *("passive", "adverbial-head", "object-filled", "where", "whose"),
            *("told-someone", "told-pronoun", "opening-phrase", "nested-opening-phrase"),
            *("question", "whose-noun"),
        ],
    )
    def test_other_relative_clauses_are_not_object_relatives(
        self, nlp: Language, text: str
    ) -> None:
        assert _one(text, nlp).object_relatives == ()


class TestSubjectVerbGaps:
    def test_counts_the_words_between_subject_and_verb(self, nlp: Language) -> None:
        sentence = _one(
            "The garden behind the old stone house at the end of the lane needs water.", nlp
        )
        (gap,) = sentence.subject_verb_gaps
        assert (gap.subject, gap.verb, gap.words_between) == ("garden", "needs", 11)

    def test_an_auxiliary_is_where_the_verb_starts(self, nlp: Language) -> None:
        (gap,) = _one("The report from the last board meeting has arrived.", nlp).subject_verb_gaps
        assert (gap.verb, gap.words_between) == ("has", 5)
        assert gap.span.text == "report from the last board meeting has"
        assert not gap.crosses_clause

    def test_a_colon_between_subject_and_verb_crosses_a_clause(self, nlp: Language) -> None:
        sentence = _one(
            "The plan: three steps, each with a long list of owners and dates for every single"
            " task we have, starts today.",
            nlp,
        )
        (gap,) = [gap for gap in sentence.subject_verb_gaps if gap.subject == "plan"]
        assert (gap.verb, gap.crosses_clause) == ("starts", True)


def _hand_parsed(rows: list[tuple[str, int, str, str]]) -> Doc:
    """A Doc from (word, head index, dependency, part of speech) rows, with no model."""
    words, heads, deps, pos = (list(column) for column in zip(*rows))
    return Doc(Vocab(), words=words, heads=heads, deps=deps, pos=pos)


class TestCrossesClause:
    def test_a_semicolon_crosses_a_clause(self) -> None:
        doc = _hand_parsed(
            [
                ("The", 1, "det", "DET"),
                ("garden", 5, "nsubj", "NOUN"),
                ("grew", 5, "parataxis", "VERB"),
                (";", 5, "punct", "PUNCT"),
                ("it", 2, "dep", "PRON"),
                ("needs", 5, "ROOT", "VERB"),
                ("water", 5, "dobj", "NOUN"),
            ]
        )
        assert syntax_features._crosses_clause(doc, doc[1], doc[5])

    def test_an_and_that_joins_two_verbs_crosses_a_clause(self) -> None:
        doc = _hand_parsed(
            [
                ("The", 1, "det", "DET"),
                ("garden", 6, "nsubj", "NOUN"),
                ("grew", 6, "advcl", "VERB"),
                ("and", 2, "cc", "CCONJ"),
                ("the", 5, "det", "DET"),
                ("shed", 2, "conj", "NOUN"),
                ("needs", 6, "ROOT", "VERB"),
                ("paint", 6, "dobj", "NOUN"),
            ]
        )
        assert syntax_features._crosses_clause(doc, doc[1], doc[6])

    def test_an_and_inside_the_subject_does_not(self) -> None:
        doc = _hand_parsed(
            [
                ("The", 1, "det", "DET"),
                ("garden", 5, "nsubj", "NOUN"),
                ("and", 1, "cc", "CCONJ"),
                ("the", 4, "det", "DET"),
                ("shed", 1, "conj", "NOUN"),
                ("need", 5, "ROOT", "VERB"),
                ("paint", 5, "dobj", "NOUN"),
            ]
        )
        assert not syntax_features._crosses_clause(doc, doc[1], doc[5])

    def test_an_and_inside_a_phrase_on_the_verb_does_not(self) -> None:
        doc = _hand_parsed(
            [
                ("The", 1, "det", "DET"),
                ("committee", 8, "nsubj", "NOUN"),
                (",", 8, "punct", "PUNCT"),
                ("after", 8, "prep", "ADP"),
                ("weeks", 3, "pobj", "NOUN"),
                ("and", 4, "cc", "CCONJ"),
                ("votes", 4, "conj", "NOUN"),
                (",", 8, "punct", "PUNCT"),
                ("approved", 8, "ROOT", "VERB"),
                ("the", 10, "det", "DET"),
                ("budget", 8, "dobj", "NOUN"),
            ]
        )
        assert not syntax_features._crosses_clause(doc, doc[1], doc[8])

    def test_a_long_phrase_on_the_verb_is_a_gap_that_crosses_nothing(self, nlp: Language) -> None:
        sentence = _one(
            "The committee, after weeks of heated debate and two failed votes in the late spring"
            " of that year, approved the budget.",
            nlp,
        )
        (gap,) = [gap for gap in sentence.subject_verb_gaps if gap.subject == "committee"]
        assert (gap.verb, gap.words_between, gap.crosses_clause) == ("approved", 16, False)


class TestArcLengths:
    def test_arcs_are_counted_in_words_without_punctuation_or_root(self, nlp: Language) -> None:
        sentence = _one("The bread that was sold by the baker was warm.", nlp)
        assert len(sentence.words) == 10
        assert len(sentence.arc_lengths) == 9
        assert max(sentence.arc_lengths) == 7

    @pytest.mark.parametrize(
        ("words", "expected"), [(1, 0), (5, 0), (6, 1), (20, 3), (30, 4), (31, None)]
    )
    def test_length_bins_follow_the_paper(self, words: int, expected: int | None) -> None:
        assert length_bin(words) == expected


class TestCandidates:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("The report shows a steady rise in visitors.", ("report", "show", "noun")),
            ("It expects a list of names.", ("It", "expect", "pronoun")),
            ("`parse` returns a list.", (PLACEHOLDER, "return", "code")),
            ("We kept the tool that breaks often.", ("tool", "break", "noun")),
            ("PostgreSQL rejects the old transaction.", ("PostgreSQL", "reject", "name")),
        ],
        ids=["noun", "pronoun", "code", "relative-pronoun", "product-name"],
    )
    def test_inanimate_subject_candidates(
        self, nlp: Language, text: str, expected: tuple[str, str, str]
    ) -> None:
        sentence = _one(text, nlp)
        found = [(c.subject, c.verb_lemma, c.subject_kind) for c in sentence.inanimate_subjects]
        assert found == [expected]

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("The businesses want lower taxes.", ("business", "want", None)),
            ("Every reading list hopes to reach more members.", ("list", "hope", "reach")),
            ("The coming weekend promises to be dry.", ("weekend", "promise", "be")),
            ("The audit carries out three checks a year.", ("audit", "carry out", None)),
            ("Many species eat hard seeds.", ("species", "eat", None)),
        ],
        ids=[
            *("plural-subject", "hopes-is-not-hop", "infinitive-complement", "phrasal-verb"),
            "species-is-not-specie",
        ],
    )
    def test_reads_the_subject_lemma_and_the_verbs_complement(
        self, nlp: Language, text: str, expected: tuple[str, str, str | None]
    ) -> None:
        (candidate,) = _one(text, nlp).inanimate_subjects
        assert (candidate.subject_lemma, candidate.verb_lemma, candidate.complement_lemma) == (
            expected
        )

    def test_reads_the_noun_after_of_in_the_subject(self, nlp: Language) -> None:
        (candidate,) = _one("The rest of the choir wants a longer break.", nlp).inanimate_subjects
        assert (candidate.subject_lemma, candidate.of_lemma) == ("rest", "choir")

    def test_a_participle_without_an_auxiliary_has_no_subject(self, nlp: Language) -> None:
        sentence = _one("The gaps were listed and their existence known.", nlp)
        assert [c.verb_lemma for c in sentence.inanimate_subjects] == []

    def test_a_coordinated_verb_shares_the_active_subject_before_it(self, nlp: Language) -> None:
        shared, passive = analyze(
            "The chart shows the result and explains the change. The chart shows the result and"
            " the change is explained.",
            nlp,
        )
        assert [(c.subject, c.verb_lemma, c.subject_kind) for c in shared.inanimate_subjects] == [
            ("chart", "show", "noun"),
            ("chart", "explain", "noun"),
        ]
        assert [(c.subject, c.verb_lemma) for c in passive.inanimate_subjects] == [
            ("chart", "show")
        ]

    @pytest.mark.parametrize(
        "text",
        [
            "She shows the visitors around the garden.",
            "Maria shows the visitors around the garden.",
            "Americans want lower taxes.",
        ],
        ids=["pronoun", "person-name", "nationality"],
    )
    def test_a_person_is_not_an_inanimate_subject(self, nlp: Language, text: str) -> None:
        assert _one(text, nlp).inanimate_subjects == ()

    def test_denominal_verbs_come_from_the_reference_lemmas(self, nlp: Language) -> None:
        text = "They bottle the cider in October."
        assert _one(text, nlp).denominal_verbs == ()
        (verb,) = _one(text, nlp, frozenset({"bottle"})).denominal_verbs
        assert (verb.lemma, verb.span.text) == ("bottle", "bottle")

    def test_noun_dominant_lemmas_count_noun_and_verb_tags(self, nlp: Language) -> None:
        reference = analyze("The bottle is green. A bottle broke. We bottle cider.", nlp)
        lemmas = syntax_features.noun_dominant_lemmas(reference)
        assert {"bottle", "cider"} <= lemmas
        assert "break" not in lemmas
