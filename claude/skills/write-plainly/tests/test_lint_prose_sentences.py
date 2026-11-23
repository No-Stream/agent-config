"""Sentence-shape rules, and the markdown that every rule skips."""

from __future__ import annotations

import lint_prose
from conftest import rule_lines

THREE_SERIES = (
    "The branch lends books, films and games. ",
    "Visitors come on foot, by bus or by bike. ",
    "The staff shelve, label and repair the stock. ",
)


class TestTriadDensity:
    def test_flags_the_third_list_of_three_in_a_section(self) -> None:
        text = "## Services\n\n" + "\n".join(THREE_SERIES) + "\n"
        assert rule_lines("triad-density", text) == [5]

    def test_counts_a_series_with_a_serial_comma(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n"
            "The café sells tea, coffee, and cake.\n"
        )
        assert rule_lines("triad-density", text) == [5]

    def test_a_longer_list_is_not_a_list_of_three(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n"
            "The café sells tea, coffee, cake, soup and bread.\n"
            "The shop sells maps, pens, cards, and stamps.\n"
            "Tea gets a shelf, and coffee or cocoa gets a cupboard.\n"
            "The desk lends laptops, chargers and headphones.\n"
        )
        assert rule_lines("triad-density", text) == [8]

    def test_skips_an_opening_clause_before_a_list_of_three(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n"
            "In winter, the branch lends sledges, skates and scarves.\n"
        )
        assert rule_lines("triad-density", text) == [5]

    def test_an_opening_clause_before_a_pair_is_not_a_list_of_three(self) -> None:
        text = (
            "## Hours\n\n"
            "In winter, the branch opens late and closes early.\n"
            "However, the café stays open and serves soup.\n"
            "In 2024, the branch bought chairs and lamps.\n"
        )
        assert rule_lines("triad-density", text) == []

    def test_a_long_clause_before_the_first_comma_is_not_an_opening_phrase(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n"
            "For each loan we record the date, the reader and the branch.\n"
        )
        assert rule_lines("triad-density", text) == [5]

    def test_counts_captions_and_footnotes(self) -> None:
        free = "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n\n"
        caption = free + "Figure 2: loans, visits and renewals by month.\n"
        footnote = free + "[^1]: Loans, visits and renewals rose in May.\n"
        assert rule_lines("triad-density", caption) == [6]
        assert rule_lines("triad-density", footnote) == [6]

    def test_counts_each_section_and_skips_list_items(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n\n"
            "## Visits\n\n" + "\n".join(THREE_SERIES[:2]) + "\n\n"
            "- Loans cover books, films and games.\n"
        )
        assert rule_lines("triad-density", text) == []


RIVER_RUN_ON = (
    "The volunteers who walk the river path every weekend collect plastic bottles and old fishing"
    " line and broken glass and they sort all of it into bags that the town picks up from the"
    " bridge early on Monday morning."
)


STARTER_SENTENCE = (
    "Sourdough starters need regular feeding, and a baker who forgets for a week will usually find"
    " a layer of grey liquid on top, which is harmless alcohol that can be poured off before the"
    " next feeding with equal weights of flour and water."
)


CRUST_SENTENCE = (
    "A loaf baked in a cast iron pot develops a darker crust than one baked on a tray, because the"
    " lid traps steam during the first twenty minutes, keeps the surface soft while the dough"
    " expands, and only then lets the crust dry and brown."
)


class TestLongSentence:
    def test_flags_a_long_sentence_with_almost_no_punctuation(self) -> None:
        text = f"Litter piles up after storms. {RIVER_RUN_ON}\n"
        findings = [f for f in lint_prose.lint_text(text) if f.rule == "long-sentence"]
        assert [(f.line, f.column) for f in findings] == [(1, 31)]

    def test_leaves_punctuated_shorter_and_list_text_alone(self) -> None:
        punctuated = RIVER_RUN_ON.replace("bottles and", "bottles,").replace(
            "glass and", "glass, and"
        )
        text = (
            f"{punctuated}\n\n"
            "The volunteers who walk the river path every weekend collect plastic bottles and old"
            " fishing line and they sort all of it into bags that the town picks up on Monday.\n\n"
            "- flour from the mill on the hill near the old church\n"
            "- water from the tap in the kitchen of the bakery\n"
            "- salt from the jar on the shelf by the window\n"
            "- starter from the crock that sits beside the oven\n\n"
            "## A heading with quite a few words in it about bread and how people bake it at home\n"
            "Short text here that follows the heading without any punctuation at all\n"
        )
        assert rule_lines("long-sentence", text) == []

    def test_sentence_ends_survive_etc_links_and_footnote_links(self) -> None:
        van = (
            "The van leaves at dawn and drives along the coast road to the market in the next town"
            " before the shops open."
        )
        text = (
            f"We pack the flour and the sugar and the salt and the yeast etc. {van}\n\n"
            "We bake the bread and the rolls and the buns as described in"
            f" [the guide](https://example.com/guide). {van}\n\n"
            f"We bake the bread and the rolls and the buns as the guide says.[1](#note-1) {van}\n"
        )
        assert rule_lines("long-sentence", text) == []


class TestComplexSentence:
    def test_flags_each_forty_word_sentence_after_the_first(self) -> None:
        text = f"{STARTER_SENTENCE}\n\n{CRUST_SENTENCE}\n\n{CRUST_SENTENCE}\n"
        assert rule_lines("complex-sentence", text) == [3, 5]

    def test_one_long_sentence_is_free_and_run_ons_are_not_charged_twice(self) -> None:
        run_on = RIVER_RUN_ON.replace("early on Monday", "early on Monday or Tuesday")
        text = f"{run_on}\n\n{STARTER_SENTENCE}\n"
        findings = [(f.rule, f.line) for f in lint_prose.lint_text(text)]
        assert ("long-sentence", 1) in findings
        assert [rule for rule, _ in findings if rule == "complex-sentence"] == []

    def test_a_list_of_names_is_not_a_sentence(self) -> None:
        names = [f"[Baker Number{index}](/team/baker-{index}/)," for index in range(21)]
        text = f"{STARTER_SENTENCE}\n\n**Authors**\n\n" + "\n".join(names) + "\n"
        assert rule_lines("complex-sentence", text) == []


class TestStaccatoRun:
    def test_flags_three_short_sentences_that_open_on_the_same_word(self) -> None:
        text = (
            "The library opened a tool shed last spring.\n\n"
            "Members borrow drills on weekdays. Members return them on Saturday. Members pay"
            " nothing for a loan.\n"
        )
        assert rule_lines("staccato-run", text) == [3]

    def test_flags_three_short_sentences_that_each_open_on_a_determiner(self) -> None:
        text = (
            "A new member gets a short tour. The desk issues a card. Each card holds ten loans.\n"
        )
        assert rule_lines("staccato-run", text) == [1]

    def test_flags_a_longer_run_once(self) -> None:
        text = "We open at nine. We close at five. We shut on Sundays. We shut on holidays.\n"
        assert rule_lines("staccato-run", text) == [1]

    def test_a_long_sentence_or_another_opener_breaks_the_run(self) -> None:
        long_middle = (
            "Members borrow drills on weekdays. Members return them on Saturday, after the morning"
            " rush has passed and the staff have counted the week's tools. Members pay nothing.\n"
        )
        other_opener = "Members borrow drills. Staff check each drill. Members pay nothing.\n"
        assert rule_lines("staccato-run", long_middle) == []
        assert rule_lines("staccato-run", other_opener) == []

    def test_counts_the_words_of_quoted_titles(self) -> None:
        text = (
            'The next guide, "Sharpening and Honing a Plane Iron by Hand at Home," covers the'
            ' bevel. The third guide, "Choosing, Shaping and Fitting a New Ash Handle," covers'
            ' repairs. The last guide, "Storing Hand Tools Through a Long and Damp Winter," covers'
            " rust.\n"
        )
        assert rule_lines("staccato-run", text) == []

    def test_reads_only_the_sentences_of_one_paragraph(self) -> None:
        text = (
            "- The desk opens at nine.\n- The shed opens at ten.\n- The café opens at noon.\n\n"
            "![Loans](loans.png)\n\n"
            "Figure 1: The bars are loans. The line is returns. The dots are repairs. The stars are"
            " fines.\n\n"
            "The desk opens at nine.\n\nThe shed opens at ten.\n\nThe café opens at noon.\n\n"
            '"The desk opens. The shed opens. The café opens." That is the sign on the door.\n'
        )
        assert rule_lines("staccato-run", text) == []


MASKING_TRIGGERS = (
    "The model wants the implementation of a cache that may possibly cost 3, 4 or 5"
    f" dollars. {RIVER_RUN_ON} {STARTER_SENTENCE} {CRUST_SENTENCE} As discussed, honestly,"
    " the CMS was previously called B7 and is VERY slow rather than fast. What keeps it"
    " slow is the disk. Two things matter: speed and cost. We can't rule out a fault."
    f" The window display wins most visitors. {' '.join(THREE_SERIES)}"
)


class TestMasking:
    def test_rules_skip_code_quotes_tables_and_links(self) -> None:
        text = (
            "# Masking\n\n"
            f"```\n{MASKING_TRIGGERS}\n```\n\n"
            f"> {MASKING_TRIGGERS}\n\n"
            f"| {MASKING_TRIGGERS} |\n\n"
            f"`{MASKING_TRIGGERS}`\n\n"
            "[A plain link](https://example.com/the-model-wants/may-possibly/1/2/3)\n"
        )
        assert lint_prose.lint_text(text) == []


class TestTables:
    def test_rules_skip_tables_without_outer_pipes(self) -> None:
        text = (
            "# Bake times\n\n"
            f"Loaf | {MASKING_TRIGGERS}\n"
            ":--- | ---:\n"
            f"rye | {MASKING_TRIGGERS}\n"
            f"{MASKING_TRIGGERS}\n\n"
            "| Loaf | Oven |\n"
            "--- | ---\n"
            f"spelt | {MASKING_TRIGGERS}\n\n"
            "- Loaf | Oven\n"
            "  --- | ---\n"
            f"  barley | {MASKING_TRIGGERS}\n"
        )
        assert lint_prose.lint_text(text) == []

    def test_a_table_runs_from_its_header_to_a_blank_line_or_another_block(self) -> None:
        text = (
            "The bakery sets two ovens — one per loaf.\n"
            "Loaf | Oven\n--- | ---\nrye — dense | 220 C\n"
            "- The rye loaf bakes longest — about an hour.\n\n"
            "Loaf | Oven\n--- | ---\nspelt — light | 200 C\n\n"
            "The spelt loaf bakes fastest — about half an hour.\n"
        )
        assert rule_lines("em-dash", text) == [1, 5, 11]

    def test_a_pipe_in_prose_makes_a_table_only_above_a_matching_delimiter_row(self) -> None:
        text = (
            "We sift the flour | sugar mix — twice.\n\n"
            "Flour | sugar — one to one.\n---\n\n"
            "Flour | sugar | salt — in that order.\n--- | ---\n"
        )
        assert rule_lines("em-dash", text) == [1, 3, 6]
