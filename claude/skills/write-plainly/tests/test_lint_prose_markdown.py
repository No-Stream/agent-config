"""Tests for lint_prose_markdown.py's text preparation and finding output, which need no parser."""

from __future__ import annotations

import json

import pytest

from lint_prose_markdown import (
    PLACEHOLDER,
    Finding,
    masked_lines,
    parse_blocks,
    prose_blocks,
    stretches,
    write_findings,
)


def _texts(markdown: str) -> list[str]:
    return [stretch.text for block in prose_blocks(markdown) for stretch in stretches(block)]


class TestStretches:
    def test_markup_goes_and_code_links_and_paths_become_one_word(self) -> None:
        markdown = (
            "Run `make test`, read [the guide](https://example.org/guide) and **every** note in"
            " ~/notes/todo.md before the HTTPS://EXAMPLE.ORG release.\n"
        )
        expected = (
            f"Run {PLACEHOLDER}, read the guide and every note in {PLACEHOLDER} before the"
            f" {PLACEHOLDER} release."
        )
        assert _texts(markdown) == [expected]

    def test_identifiers_calls_dotted_names_and_math_become_one_word(self) -> None:
        assert _texts("Set max_rows, call reset() on os.path and keep $x^2$ small.\n") == [
            f"Set {PLACEHOLDER}, call {PLACEHOLDER} on {PLACEHOLDER} and keep {PLACEHOLDER} small."
        ]

    def test_images_reference_links_footnotes_and_comments_go(self) -> None:
        markdown = (
            "The ![a gauge](gauge.png) tide [table][tides] rose[^1] <!-- check\nthis --> twice.\n"
        )
        assert _texts(markdown) == ["The tide table rose twice."]

    def test_a_placeholder_never_joins_the_letters_beside_it(self) -> None:
        expected = (
            f"Use {PLACEHOLDER} n {PLACEHOLDER} m {PLACEHOLDER} to bound a repeat, or"
            f" {PLACEHOLDER} n {PLACEHOLDER} for more."
        )
        assert _texts("Use `{`*n*`,`*m*`}` to bound a repeat, or `{`*n*`,}` for more.\n") == [
            expected
        ]

    def test_dollar_amounts_are_prose_and_math_is_one_word(self) -> None:
        markdown = (
            "The grant was $40 and the fee $15, and a gate keeps a value between $0$ and $1$.\n"
        )
        expected = (
            "The grant was $40 and the fee $15, and a gate keeps a value between"
            f" {PLACEHOLDER} and {PLACEHOLDER}."
        )
        assert _texts(markdown) == [expected]

    def test_math_padded_with_spaces_is_one_word_when_it_holds_a_tex_command(self) -> None:
        assert _texts("The gradient $ \\nabla_W \\log p $ points uphill.\n") == [
            f"The gradient {PLACEHOLDER} points uphill."
        ]

    def test_a_line_of_only_inline_code_stays_in_its_paragraph(self) -> None:
        markdown = "A counted repetition operator\n`{`\nmatches a range of counts.\n"
        assert _texts(markdown) == [
            f"A counted repetition operator {PLACEHOLDER} matches a range of counts."
        ]

    def test_an_arrow_or_emoji_ends_a_stretch(self) -> None:
        assert _texts("Load the data → train the model ✅ done.\n") == [
            "Load the data",
            "train the model",
            "done.",
        ]

    def test_a_list_marker_is_skipped_and_code_after_it_kept(self) -> None:
        assert _texts("- `tide_table` loads first.\n[^2]: The second note.\n") == [
            f"{PLACEHOLDER} loads first.",
            "The second note.",
        ]

    def test_each_character_maps_back_to_its_place_in_the_block(self) -> None:
        (block,) = prose_blocks("A calm bay.\nRough  `code` seas.\n")
        (stretch,) = stretches(block)
        seas = stretch.text.index("seas")
        assert block.position(stretch.starts[seas]) == (2, 15)
        placeholder = stretch.text.index(PLACEHOLDER)
        assert placeholder in stretch.placeholder_starts
        assert block.position(stretch.starts[placeholder]) == (2, 8)

    def test_a_part_keeps_its_own_placeholder_starts(self) -> None:
        (block,) = prose_blocks("First one. Then `code` here.\n")
        (stretch,) = stretches(block)
        second = stretch.part(11, len(stretch.text))
        assert second.text == f"Then {PLACEHOLDER} here."
        assert second.placeholder_starts == {5}


class TestBlocks:
    def test_a_paragraph_that_masking_leaves_blank_is_a_masked_block(self) -> None:
        markdown = "First paragraph.\n\n<!-- a note to the editor -->\n\nSecond paragraph.\n"
        kinds = [block.kind for block in parse_blocks(*masked_lines(markdown))]
        assert kinds == ["paragraph", "masked", "paragraph"]


class TestLinterMask:
    def test_blanks_code_links_urls_footnotes_and_comments_alike(self) -> None:
        _, visible, _ = masked_lines(
            "See `x` [1](https://a.org) at HTTP://b.org then[^n] <!-- hidden --> now.\n"
        )
        assert visible[0].split() == ["See", "at", "then", "now."]


MESSAGES = {"rule-a": "Message A."}


class TestWriteFindings:
    def test_writes_one_line_per_finding_and_returns_1(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        found = [Finding("rule-a", 3, 7, "the excerpt")]
        assert write_findings([("a.md", found), ("b.md", [])], MESSAGES, as_json=False) == 1
        assert capsys.readouterr().out == "a.md:3:7: rule-a: Message A. | the excerpt\n"

    def test_writes_json_with_the_message_and_path(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        found = [Finding("rule-a", 3, 7, "the excerpt")]
        write_findings([("a.md", found)], MESSAGES, as_json=True)
        assert json.loads(capsys.readouterr().out) == [
            {
                "rule": "rule-a",
                "line": 3,
                "column": 7,
                "excerpt": "the excerpt",
                "message": "Message A.",
                "path": "a.md",
            }
        ]

    def test_no_findings_write_nothing_and_return_0(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert write_findings([("a.md", [])], MESSAGES, as_json=False) == 0
        assert capsys.readouterr().out == ""
