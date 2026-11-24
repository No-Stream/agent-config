import pytest

from prose import (
    PLACEHOLDER,
    content_pairs,
    is_content_word,
    merge_spans,
    pair_key,
    plain_text,
    tokens,
)


def pair_texts(text: str) -> list[tuple[str, str]]:
    found = tokens(text)
    return [(found[left].text, found[right].text) for left, right in content_pairs(found)]


class TestTokens:
    def test_one_space_joins_words_and_punctuation_does_not(self):
        found = tokens("The kettle boiled, then cooled slowly.")
        assert [token.text for token in found] == [
            "The",
            "kettle",
            "boiled",
            "then",
            "cooled",
            "slowly",
        ]
        assert [token.joined for token in found] == [False, True, True, False, True, True]

    def test_hyphenated_word_splits_into_joined_parts(self):
        found = tokens("a well-known tide-pool crab")
        assert [token.text for token in found] == ["a", "well", "known", "tide", "pool", "crab"]
        assert all(token.joined for token in found[1:])

    def test_offsets_point_at_each_part(self):
        text = "old tide-pool"
        assert [text[token.start : token.end] for token in tokens(text)] == ["old", "tide", "pool"]

    def test_two_spaces_do_not_join(self):
        assert [token.joined for token in tokens("river  delta")] == [False, False]

    def test_letters_outside_ascii_stay_inside_a_word(self):
        found = tokens("a jardinière, Médico and a naïve guess")
        expected = ["a", "jardinière", "Médico", "and", "a", "naïve", "guess"]
        assert [token.text for token in found] == expected


class TestContentWords:
    @pytest.mark.parametrize(
        "word", ["the", "of", "Which", "would", "X", "3", "1990s", PLACEHOLDER, f"{PLACEHOLDER}'s"]
    )
    def test_function_words_numbers_and_letters_are_not_content(self, word):
        assert not is_content_word(word)

    @pytest.mark.parametrize("word", ["glacier", "Basalt", "erodes", "quickly", "ship's"])
    def test_other_words_are_content(self, word):
        assert is_content_word(word)

    def test_pair_key_lowercases_and_drops_possessive(self):
        assert pair_key("Ship’s", "Hull") == ("ship", "hull")

    def test_pairs_need_two_joined_content_words(self):
        assert pair_texts("The old lighthouse keeper rowed to the rocky shore.") == [
            ("old", "lighthouse"),
            ("lighthouse", "keeper"),
            ("keeper", "rowed"),
            ("rocky", "shore"),
        ]


class TestPlainText:
    def test_keeps_prose_blocks_and_drops_code_and_tables(self):
        markdown = (
            "# Tides\n\nThe moon pulls the sea.\n\n```\nprint('x')\n```\n\n"
            "| a | b |\n|---|---|\n| 1 | 2 |\n\n- Spring tides peak twice monthly.\n"
        )
        plain = plain_text(markdown)
        assert plain.text == "The moon pulls the sea.\n\nSpring tides peak twice monthly."
        assert plain.words == 10

    def test_inline_code_becomes_a_placeholder_that_breaks_pairs(self):
        plain = plain_text("Call the `tide_table` loader before the harbour report.\n")
        assert plain.text == f"Call the {PLACEHOLDER} loader before the harbour report."
        assert (PLACEHOLDER, "loader") not in pair_texts(plain.text)
        assert ("harbour", "report") in pair_texts(plain.text)

    def test_code_at_either_end_of_a_block_keeps_its_placeholder(self):
        assert plain_text("`tide_table` loads before the `report`.\n").text == (
            f"{PLACEHOLDER} loads before the {PLACEHOLDER}."
        )

    def test_a_path_and_a_snake_case_identifier_become_the_placeholder(self):
        plain = plain_text("Edit src/app/main.py and set tide_table before the harbour report.\n")
        assert plain.text == (
            f"Edit {PLACEHOLDER} and set {PLACEHOLDER} before the harbour report."
        )
        assert ("table", "before") not in pair_texts(plain.text)

    def test_code_beside_emphasis_stays_apart_from_its_letters(self):
        plain = plain_text("Write `{`*n*`,`*m*`}` for a counted repeat.\n")
        expected = f"Write {PLACEHOLDER} n {PLACEHOLDER} m {PLACEHOLDER} for a counted repeat."
        assert plain.text == expected
        assert all(token.start in plain.sources for token in tokens(plain.text))

    def test_an_arrow_breaks_pairs_with_a_line_break(self):
        plain = plain_text("Load the tide data → train the harbour model.\n")
        assert plain.text == "Load the tide data\ntrain the harbour model."
        assert ("data", "train") not in pair_texts(plain.text)

    def test_emphasis_and_line_wraps_do_not_break_pairs(self):
        plain = plain_text("The **storm\nsurge** flooded the *low* fields.\n")
        assert plain.text == "The storm surge flooded the low fields."
        assert ("storm", "surge") in pair_texts(plain.text)
        assert ("low", "fields") in pair_texts(plain.text)

    def test_links_keep_their_text(self):
        plain = plain_text("See the [harbour master's log](https://example.org/log) daily.\n")
        assert plain.text == "See the harbour master's log daily."

    def test_a_period_that_starts_a_word_keeps_the_space_before_it(self):
        plain = plain_text("We ported the .NET runtime, and she batted .263 last season.\n")
        assert plain.text == "We ported the .NET runtime, and she batted .263 last season."
        words = [token.text for token in tokens(plain.text)]
        assert ("the", "NET") == (words[2], words[3])

    def test_maps_a_word_that_starts_outside_ascii(self):
        plain = plain_text("The Écrins massif rises above Médico.\n")
        starts = [token.start for token in tokens(plain.text)]
        assert plain.sources[starts[1]] == (1, 5)
        assert all(start in plain.sources for start in starts)

    def test_maps_each_word_start_to_its_source_line_and_column(self):
        markdown = "# Heading\n\nA calm bay.\n\n- Rough  `code` seas ahead.\n"
        plain = plain_text(markdown)
        positions = {
            plain.text[token.start : token.end]: plain.sources[token.start]
            for token in tokens(plain.text)
            if token.start in plain.sources
        }
        assert positions["calm"] == (3, 3)
        assert positions["Rough"] == (5, 3)
        assert positions["seas"] == (5, 17)


class TestMergeSpans:
    def test_touching_index_pairs_merge_into_one_span(self):
        text = "storm surge barrier, calm bay"
        found = tokens(text)
        spans = merge_spans(found, [(0, 1), (1, 2), (3, 4)])
        assert [text[span.start : span.end] for span in spans] == [
            "storm surge barrier",
            "calm bay",
        ]

    def test_a_single_word_is_a_span(self):
        text = "storm surge"
        assert [text[span.start : span.end] for span in merge_spans(tokens(text), [(1, 1)])] == [
            "surge"
        ]
