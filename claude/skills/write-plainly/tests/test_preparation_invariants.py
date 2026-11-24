"""The shared text preparation's invariants, stated on realistic documents for every consumer,
with the bugs that broke them as regression cases; preparation_invariants.py defines the checks."""

from __future__ import annotations

import functools
import re

import preparation_invariants as invariants
import prose
import pytest
import reference
from spacy.language import Language

import lint_prose_markdown
import syntax_features
from lint_prose_markdown import PLACEHOLDER, masked_lines, parse_blocks, prose_blocks, stretches

TIDE_NOTES = """---
title: Tide station notes
---

# Tide station notes

The station at Pointe-à-Callière logs the tide every six minutes. Each reading goes
through `tide_reader`, which calls `parse_frame()` and appends to ~/tides/raw.csv; see
[the station guide](https://example.org/guide) for the wiring[^1] and os.path for paths.

**Note**: a sensor that reads $V_s > 5$ volts is saturated, and a spare costs $40 at the
dock store and $15 by mail.<!-- check the mail price --> The café's naïve jardinière
→ a fern ✅ thrives beside the gauge.

- The .NET port and the .263 release both drop the `{`*n*`,`*m*`}` form.
- A counted repetition operator
  `{`
  matches a range of counts, and `Gauge`'s reading is in metres.

> A quoted passage that no consumer reads.

| column | meaning |
|---|---|
| depth | metres |

![The gauge at low water](gauge.png)

[^1]: The guide is kept by the harbour office at <https://example.org/office>.
"""
WIKITEXT_ROWS = (
    (
        " The 1 @,@ 200 @-@ tonne ship was launched at Belfast in 1911 , and its crew did n't"
        " expect the storm . \n"
    ),
    " Microsoft released .NET in 2002 ; the .263 codec followed ( see below ) . \n",
    " The café at Pointe-à-Callière , opened in 1992 , serves 40 @.@ 5 % of visitors . \n",
)


@pytest.fixture(scope="module")
def nlp() -> Language:
    return syntax_features.load_model()


def _blocks(markdown: str) -> list[lint_prose_markdown.Block]:
    return parse_blocks(*masked_lines(markdown))


def _found(violations: list[invariants.Violation]) -> set[tuple[str, str]]:
    return {(violation.invariant, violation.cause) for violation in violations}


def _linter_violations(markdown: str) -> list[invariants.Violation]:
    return [
        violation
        for block in _blocks(markdown)
        if block.kind in (*lint_prose_markdown.PROSE_KINDS, "masked")
        for violation in invariants.linter_violations(block)
    ]


def _stretch_violations(markdown: str) -> list[invariants.Violation]:
    blocks = _blocks(markdown)
    found = invariants.document_violations(markdown, blocks)
    for block in prose_blocks(markdown):
        found.extend(invariants.stretch_violations(block, stretches(block)))
    return found


class TestSharedPreparation:
    def test_the_paper_preparation_of_a_full_document_breaks_no_invariant(self) -> None:
        assert _stretch_violations(TIDE_NOTES) == []

    def test_its_text_keeps_every_kind_of_word(self) -> None:
        texts = " ".join(
            stretch.text for block in prose_blocks(TIDE_NOTES) for stretch in stretches(block)
        )
        assert "Pointe-à-Callière logs the tide" in texts
        assert "The .NET port and the .263 release" in texts
        assert f"Each reading goes through {PLACEHOLDER}, which calls {PLACEHOLDER}" in texts
        assert "costs $40 at the dock store and $15 by mail." in texts
        assert "A counted repetition operator Xyzzy matches" in texts

    def test_a_url_glued_to_the_word_before_it_starts_at_its_scheme(self) -> None:
        markdown = "The tide table is athttps://example.org/tides for anyone.\n"
        assert _stretch_violations(markdown) == [] and _linter_violations(markdown) == []
        (block,) = prose_blocks(markdown)
        assert stretches(block)[0].text == f"The tide table is at {PLACEHOLDER} for anyone."

    def test_a_word_that_only_markup_separates_is_still_one_word(self) -> None:
        assert _stretch_violations("The **tide**s and [gauge](https://example.org)s rose.\n") == []


class TestLinter:
    def test_the_linter_text_of_a_full_document_breaks_no_invariant(self) -> None:
        assert _linter_violations(TIDE_NOTES) == []


class TestParse:
    def test_the_parsed_sentences_of_a_full_document_break_no_invariant(
        self, nlp: Language
    ) -> None:
        tokenize = functools.partial(syntax_features._tokenized, nlp)
        assert invariants.parse_violations(TIDE_NOTES, tokenize) == []

    def test_a_span_quotes_its_source_with_the_markup_inside_it(self, nlp: Language) -> None:
        markdown = "Notes first.\n\nThe **old** tide gauge wants `fresh_paint` by May.\n"
        _, sentence = syntax_features.analyze(markdown, nlp)
        span = sentence.span
        assert (span.text, span.line, span.column) == (
            "The **old** tide gauge wants `fresh_paint` by May.",
            3,
            1,
        )
        (subject,) = sentence.inanimate_subjects
        assert (subject.span.text, subject.span.line, subject.span.column) == ("gauge wants", 3, 18)


class TestSurprisal:
    def test_the_plain_text_and_tokens_of_a_full_document_break_no_invariant(self) -> None:
        assert invariants.surprisal_violations(TIDE_NOTES) == []


class TestReferenceRepair:
    @pytest.mark.parametrize("row", WIKITEXT_ROWS)
    def test_the_repaired_rows_keep_their_words(self, row: str) -> None:
        assert invariants.clean_row_violations(row) == []


class TestRegressions:
    """Each case passes now, and the check reports it again once the old behaviour is restored."""

    def test_a_word_starting_with_a_period_keeps_the_space_before_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        row = " Microsoft released .NET in 2002 . \n"
        assert invariants.clean_row_violations(row) == []
        monkeypatch.setattr(reference, "SPACE_BEFORE_PUNCTUATION", re.compile(r" +(?=[,.;:!?)\]])"))
        assert _found(invariants.clean_row_violations(row)) == {
            (invariants.INVENTED, "joined-across-space")
        }

    def test_a_word_starting_with_a_period_in_any_script_keeps_the_space_before_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        row = " Income per head was .د.ب 308 in 1995 , or $ 819 . \n"
        assert invariants.clean_row_violations(row) == []
        ascii_lookahead = re.compile(r" +(?=[,.;:!?)\]](?![A-Za-z0-9]))")
        monkeypatch.setattr(reference, "SPACE_BEFORE_PUNCTUATION", ascii_lookahead)
        assert _found(invariants.clean_row_violations(row)) == {
            (invariants.INVENTED, "joined-across-space")
        }

    def test_letters_outside_ascii_stay_inside_a_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markdown = "A jardinière stood by the Médico door.\n"
        assert invariants.surprisal_violations(markdown) == []
        monkeypatch.setattr(
            prose, "TOKEN_WORD", re.compile(r"[A-Za-z0-9]+(?:['’.,-][A-Za-z0-9]+)*")
        )
        assert _found(invariants.surprisal_violations(markdown)) == {
            (invariants.SPLIT, "token-rule")
        }

    def test_a_placeholder_never_fuses_with_emphasized_letters(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markdown = "Use `{`*n*`,`*m*`}` to bound a repeat.\n"
        assert invariants.surprisal_violations(markdown) == []

        def joined_placeholder(builder, start: int, end: int) -> None:
            builder.placeholder_starts.add(len(builder.text))
            for character in PLACEHOLDER:
                builder._append(character, start, end)

        monkeypatch.setattr(
            lint_prose_markdown._StretchBuilder, "add_placeholder", joined_placeholder
        )
        assert (invariants.INVENTED, "placeholder-joined") in _found(
            invariants.surprisal_violations(markdown)
        )

    def test_a_line_of_only_inline_code_stays_in_its_paragraph(self) -> None:
        markdown = "A counted repetition operator\n`{n,m}`\nmatches a range of counts.\n"
        assert invariants.document_violations(markdown, _blocks(markdown)) == []
        original, visible, kinds = masked_lines(markdown)
        as_blank = [*original[:1], "", *original[2:]]
        old_blocks = parse_blocks(as_blank, [*visible[:1], "", *visible[2:]], kinds)
        assert _found(invariants.document_violations(markdown, old_blocks)) == {
            (invariants.DROPPED, "line-outside-blocks")
        }

    def test_a_code_span_closes_only_at_a_run_of_as_many_backticks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markdown = "Type ```python before the sample and three backticks after it, then `make`.\n"
        assert _stretch_violations(markdown) == [] and _linter_violations(markdown) == []
        (block,) = prose_blocks(markdown)
        assert stretches(block)[0].text == (
            "Type ```python before the sample and three backticks after it, then Xyzzy."
        )
        old_markup = lint_prose_markdown.INLINE_MARKUP.pattern.replace(
            lint_prose_markdown.CODE_SPAN, "`+[^`]*`+"
        )
        monkeypatch.setattr(lint_prose_markdown, "INLINE_MARKUP", re.compile(old_markup, re.DOTALL))
        assert (invariants.DROPPED, "code-span-overrun") in _found(_stretch_violations(markdown))

    def test_a_placeholder_is_a_token_of_its_own_in_the_parse(self, nlp: Language) -> None:
        markdown = "Call foo(`x`) and ping @`oncall` before the tide turns.\n"
        tokenize = functools.partial(syntax_features._tokenized, nlp)
        assert invariants.parse_violations(markdown, tokenize) == []
        (sentence,) = syntax_features.analyze(markdown, nlp)
        assert sentence.words.count(PLACEHOLDER) == len(sentence.placeholders) == 2
        tokenizer_only = invariants.parse_violations(markdown, lambda part: nlp.make_doc(part.text))
        assert (invariants.INVENTED, "placeholder-joined") in _found(tokenizer_only)

    def test_no_word_joins_a_placeholder_across_a_period_or_comma(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markdown = (
            "Commit or roll them back.`pg_stat_activity` lists them, e.g.`VACUUM`,`ANALYZE`.\n"
        )
        assert invariants.surprisal_violations(markdown) == []
        words = [token.text for token in prose.tokens(prose.plain_text(markdown).text)]
        assert words[4:] == ["back", PLACEHOLDER, "lists", "them", "e.g", PLACEHOLDER, PLACEHOLDER]
        monkeypatch.setattr(prose, "TOKEN_WORD", re.compile(r"[^\W_]+(?:['’.,-][^\W_]+)*"))
        assert (invariants.INVENTED, "placeholder-joined") in _found(
            invariants.surprisal_violations(markdown)
        )

    def test_a_word_of_letters_in_any_script_is_one_word_for_every_consumer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markdown = "Deirdré read p\u0302 aloud and wrote हिन्दी and Москва on the board.\n"
        assert (
            _linter_violations(markdown) == [] and invariants.surprisal_violations(markdown) == []
        )
        (block,) = prose_blocks(markdown)
        assert len(lint_prose_markdown.WORD.findall(block.text)) == 12
        ascii_word = re.compile(r"[A-Za-z0-9]+(?:['’.,-][A-Za-z0-9]+)*")
        monkeypatch.setattr(lint_prose_markdown, "WORD", ascii_word)
        assert _found(_linter_violations(markdown)) == {(invariants.SPLIT, "word-rule")}

    def test_an_escaped_character_is_literal_and_its_backslash_goes(
        self, nlp: Language, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markdown = (
            "Rabin and Scott described NFAs in 1959 \\[7\\], and vacuum\\_freeze\\_min\\_age and"
            " ext3\\_mark\\_inode\\_dirty() decide when \\*every\\* page is read.\n"
        )
        assert _stretch_violations(markdown) == [] and _linter_violations(markdown) == []
        tokenize = functools.partial(syntax_features._tokenized, nlp)
        assert invariants.parse_violations("A group (*e*).\\* repeats.\n", tokenize) == []
        (block,) = prose_blocks(markdown)
        assert stretches(block)[0].text == (
            f"Rabin and Scott described NFAs in 1959 [7], and {PLACEHOLDER} and {PLACEHOLDER}()"
            " decide when *every* page is read."
        )
        without_escapes = lint_prose_markdown.INLINE_MARKUP.pattern.split("|", 1)[1]
        monkeypatch.setattr(
            lint_prose_markdown, "INLINE_MARKUP", re.compile(without_escapes, re.DOTALL)
        )
        assert (invariants.INVENTED, "escape-kept") in _found(_stretch_violations(markdown))

    def test_a_bracket_that_opens_no_link_stays(self, monkeypatch: pytest.MonkeyPatch) -> None:
        markdown = (
            "The ledger gave the cost as $[unknown]K, filed the [sic]note, typed the rows as"
            " list[str] and kept a [linked](https://example.org) receipt.\n"
        )
        assert invariants.surprisal_violations(markdown) == []
        (block,) = prose_blocks(markdown)
        assert stretches(block)[0].text == (
            "The ledger gave the cost as $[unknown]K, filed the [sic]note, typed the rows as"
            " list[str] and kept a linked receipt."
        )
        every_bracket = lint_prose_markdown.PROSE_MARKUP.pattern.replace(
            r"_+(?![A-Za-z0-9])", r"_+(?![A-Za-z0-9])|[\[\]]"
        )
        monkeypatch.setattr(lint_prose_markdown, "PROSE_MARKUP", re.compile(every_bracket))
        assert (invariants.INVENTED, "joined-across-bracket") in _found(
            invariants.surprisal_violations(markdown)
        )

    def test_markup_goes_only_where_commonmark_reads_markup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markdown = (
            "Write to <harbour@example.org> about the <tide_level> field, read [6:40 PM](the"
            " evening reading) and keep a <b>bold</b> mark.\n"
        )
        assert _stretch_violations(markdown) == [] and _linter_violations(markdown) == []
        (block,) = prose_blocks(markdown)
        assert stretches(block)[0].text == (
            f"Write to {PLACEHOLDER} about the <{PLACEHOLDER}> field, read [6:40 PM](the"
            " evening reading) and keep a bold mark."
        )
        old_tags = lint_prose_markdown.PROSE_MARKUP.pattern.replace(
            lint_prose_markdown.HTML_TAG, r"</?[A-Za-z][^>\n]*>"
        )
        monkeypatch.setattr(lint_prose_markdown, "PROSE_MARKUP", re.compile(old_tags))
        old_targets = lint_prose_markdown.INLINE_MARKUP.pattern.replace(
            lint_prose_markdown.LINK_TAIL, r"\]\([^)]*\)"
        )
        monkeypatch.setattr(
            lint_prose_markdown, "INLINE_MARKUP", re.compile(old_targets, re.DOTALL)
        )
        assert {
            (invariants.DROPPED, "dropped-not-a-tag"),
            (invariants.DROPPED, "dropped-not-a-link"),
        } <= _found(_stretch_violations(markdown))

    def test_prose_between_two_dollar_amounts_is_not_math(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        markdown = "The painting sold for $ 1200. A later owner paid $ 14,722 for it.\n"
        assert _stretch_violations(markdown) == []
        old_math = lint_prose_markdown.PROSE_MARKUP.pattern.replace(
            lint_prose_markdown.INLINE_MATH.pattern, r"\$(?!\d)[^$\n]+\$"
        )
        monkeypatch.setattr(lint_prose_markdown, "PROSE_MARKUP", re.compile(old_math))
        assert (invariants.DROPPED, "math-not-pandoc") in _found(_stretch_violations(markdown))
