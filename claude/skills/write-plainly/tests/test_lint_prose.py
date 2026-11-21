from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lint_prose


def _lines(rule: str, text: str) -> list[int]:
    return [finding.line for finding in lint_prose.lint_text(text) if finding.rule == rule]


class TestEmDash:
    def test_flags_prose_and_ignores_markdown_exclusions(self) -> None:
        text = (
            "An em dash — interrupts this sentence.\n> quoted — text\n| table — cell |\n"
            "`inline — code`\n```\ncode — block\n```\n[link](https://example.com/a-b)\n"
        )
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [("em-dash", 1)]


class TestDashSubstitute:
    def test_flags_pauses_but_keeps_ranges_lists_and_compounds(self) -> None:
        text = (
            "Use this – then that.\nWords - more words\nWords--more words\nWords -- more words\n"
            "3–5 and pp. 10–12 and 2020–2024\n- list marker\nA well-known phrase.\n"
            "`inline – code`\n```\ncode – block\n```\n> quoted – text\n| table – cell |\n"
            "See https://example.com/a-b.\n"
        )
        rules = [finding.rule for finding in lint_prose.lint_text(text)]
        assert rules == ["dash-substitute"] * 4


class TestCoinedLabel:
    def test_flags_labeled_work_phases_only(self) -> None:
        text = (
            "We completed step 4 and Option B.\n"
            "A step function works; the option to wait is available.\n"
            "A run of tests passed. Run the script. Use an A/B test.\n"
            "`phase 2`\n```\nround 3\n```\n> arm A\n| tier B |\nhttps://example.com/phase-2\n"
        )
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("coined-label", 1),
            ("coined-label", 1),
        ]

    def test_does_not_treat_a_pronoun_as_a_label(self) -> None:
        text = "The approach I like to take is simple.\nEvery plan I have tried failed.\n"
        assert _lines("coined-label", text) == []

    def test_flags_a_roman_numeral_label(self) -> None:
        assert _lines("coined-label", "Phase I is done, so we start the survey.\n") == [1]

    def test_ignores_references_to_the_sections_own_numbered_steps(self) -> None:
        text = (
            "## Repot a fern\n\n"
            "1. Water the fern the day before.\n"
            "2. Loosen the root ball with a knife.\n"
            "3. If step 2 tears the roots, trim the torn ends.\n\n"
            "Repeat step 3 for each pot.\n"
        )
        assert _lines("coined-label", text) == []

    def test_flags_other_labels_inside_a_numbered_procedure(self) -> None:
        text = (
            "## Repot a fern\n\n"
            "1. Water the fern the day before.\n"
            "2. Loosen the root ball with a knife.\n"
            "3. Lift the fern into the new pot.\n\n"
            "We chose option 2, and variant 1 lost to arm 3.\n"
        )
        assert _lines("coined-label", text) == [7, 7, 7]

    def test_flags_step_numbers_beyond_the_sections_own_list(self) -> None:
        text = (
            "## Repot a fern\n\n"
            "1. Water the fern the day before.\n"
            "2. Loosen the root ball with a knife.\n\n"
            "This finishes step 5 of the greenhouse move.\n\n"
            "## Next season\n\n"
            "We start step 1 in March.\n"
        )
        assert _lines("coined-label", text) == [6, 10]

    def test_ignores_references_to_the_sections_own_numbered_items(self) -> None:
        text = (
            "## Open the branch\n\n"
            "1. Unlock the front door.\n"
            "2. Turn on the lights.\n\n"
            "Item 2 comes first in winter.\n"
        )
        assert _lines("coined-label", text) == []

    def test_flags_tracker_ids_hash_numbers_and_short_codes(self) -> None:
        text = (
            "C3 is late, and the LIB-8.3 permit has not arrived.\n"
            "#014 is late too, and G14 needs a new lock.\n"
        )
        assert _lines("coined-label", text) == [1, 1, 2, 2]

    def test_flags_more_label_words_once_each(self) -> None:
        text = (
            "Beat 6 goes to the printer on Monday.\n"
            "Route C skips the north branch.\n"
            "Decision 7 moved the book sale.\n"
            "The leak is the subject of task #42.\n"
        )
        assert _lines("coined-label", text) == [1, 2, 3, 4]

    def test_passes_an_id_that_follows_a_plain_description(self) -> None:
        text = (
            "The council funds the roof repair (LIB-12).\n"
            "The second reading room (RM2) opens in May, and RM2 seats forty people.\n"
            "The fix for the broken lock (#31) shipped on Friday.\n"
        )
        assert _lines("coined-label", text) == []

    def test_leaves_public_names_alone(self) -> None:
        text = (
            "The scans live in S3 and the text model ran on an A100.\n"
            "The files are UTF-8, the checksums are SHA-256 and the summary came from GPT-4.\n"
            "Fixing the heating is our #1 job for Q3.\n"
            "The style guide is in Issue 9 of the journal.\n"
        )
        assert _lines("coined-label", text) == []

    def test_flags_ids_in_backticks_quotes_and_hyphenated_labels(self) -> None:
        text = (
            "The leak report is `#017`, and the permit waits on `REPAIR-40`.\n"
            "The phase-3 rota is ready, and Track C's notice repeats.\n"
            "Amendment 5 passed the board.\n"
            'Press "Open REPAIR-41" to begin, or answer req-7c21be.\n'
        )
        assert _lines("coined-label", text) == [1, 1, 2, 2, 3, 4, 4]

    def test_leaves_commands_in_backticks_and_hex_like_words_alone(self) -> None:
        text = (
            "Run `make all` and `git status`, then check the re-added rows.\n"
            "The weights `W1` and `W2` are two matrices.\n"
        )
        assert _lines("coined-label", text) == []


class TestBoldRunIn:
    def test_flags_line_initial_run_ins(self) -> None:
        text = (
            "**How accurate the clock is.** The clock drifts.\n- **Latency:** 40 ms\n"
            "**Standalone bold.**\nThis **mid-sentence:** stays unflagged.\n`**inline:** code`\n"
            "```\n**code:** text\n```\n> **quote:** text\n| **table:** cell |\n"
        )
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("bold-run-in", 1),
            ("bold-run-in", 2),
        ]


class TestThinH2Section:
    def test_counts_lists_tables_and_fenced_code_as_body_blocks(self) -> None:
        text = (
            "## Thin\nOne paragraph.\n## List only\n- one\n- two\n## Two blocks\nA paragraph.\n\n"
            "```\ncode\n```\n## Table\n| a | b |\n| --- | --- |\n## End\n"
        )
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("thin-h2-section", 1),
            ("thin-h2-section", 3),
            ("thin-h2-section", 12),
            ("thin-h2-section", 15),
        ]

    def test_exempts_summary_sections(self) -> None:
        text = (
            "## TL;DR\nThe comet returns in 2061.\n"
            "## TLDR\nThe comet returns in 2061.\n"
            "## Summary\nThe comet returns in 2061.\n"
            "## Abstract\nThe comet returns in 2061.\n"
            "## Orbit\nThe orbit takes about 76 years.\n"
        )
        assert _lines("thin-h2-section", text) == [9]

    def test_exempts_a_references_list(self) -> None:
        text = (
            "## Further reading\n\n"
            "- [The bread baker's guide](https://example.com/guide): shaping and proofing.\n"
            "- Ortiz and Lee, [Crumb structure](https://example.com/crumb) (2021): oven steam.\n"
            "- See https://example.com/flour for flour grades.\n\n"
            "  The grades changed in 2020, so older guides use other names.\n"
            "## Tools\n\n"
            "- a scale\n"
            "- a [lame](https://example.com/lame)\n"
        )
        assert _lines("thin-h2-section", text) == [8]

    def test_a_list_of_wrapped_or_spaced_items_is_one_list(self) -> None:
        text = (
            "## Tools\n\n"
            "- a scale that reads to the gram, so the salt\n"
            "  and the yeast are weighed exactly\n"
            "- a lame for scoring the loaf\n\n"
            "- a banneton lined with a linen cloth\n\n"
            "---\n"
        )
        assert _lines("thin-h2-section", text) == [1]


class TestShortParagraphRun:
    def test_flags_three_consecutive_short_paragraphs(self) -> None:
        text = (
            "First short sentence.\n\nSecond short sentence.\n\nThird short sentence.\n\n"
            "A longer paragraph has one sentence. It connects two thoughts.\n\n"
            "Dr. Smith arrived.\n\nThe value is 3.14.\n\nThis is etc. useful.\n"
        )
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("short-paragraph-run", 1)
        ]

    def test_wrapped_list_items_are_not_paragraphs(self) -> None:
        text = (
            "1. Read the recipe from start to finish before you\n"
            "   buy anything.\n"
            "2. Weigh the flour and the sugar into separate\n"
            "   bowls.\n\n"
            "   Keep the bowls covered.\n"
            "- Sift the flour twice so the cake\n"
            "  rises evenly.\n\n"
            "Preheat the oven while you mix.\n\n"
            "Grease the tin with butter.\n"
        )
        assert _lines("short-paragraph-run", text) == []

    def test_nonparagraph_blocks_break_the_run(self) -> None:
        text = (
            "One sentence.\n\n- list item.\n\nSecond sentence.\n\n> quote.\n\nThird sentence.\n\n"
            "| cell |\n"
        )
        assert _lines("short-paragraph-run", text) == []


class TestTitleCaseHeading:
    def test_flags_title_case_and_ignores_sentence_case_or_short_headings(self) -> None:
        text = (
            "## Building Better Writing Habits\n## Building better writing habits\n"
            "## API and URL Design Guide\n## Simple Guide\n"
        )
        findings = lint_prose.lint_text(text)
        assert [
            (finding.rule, finding.line)
            for finding in findings
            if finding.rule == "title-case-heading"
        ] == [("title-case-heading", 1)]

    def test_does_not_count_inline_code_words(self) -> None:
        text = "## `Making Every Word Title Case` in this heading\n"
        assert "title-case-heading" not in [finding.rule for finding in lint_prose.lint_text(text)]


class TestStackedHedge:
    def test_flags_a_modal_stacked_on_a_hedging_adverb(self) -> None:
        text = (
            "Frost may possibly damage the tomatoes.\n"
            "A cover could\npotentially help.\n"
            "- Mulch might perhaps keep the roots warm.\n"
        )
        assert _lines("stacked-hedge", text) == [1, 2, 4]

    def test_leaves_single_hedges_and_masked_text_alone(self) -> None:
        text = (
            "Frost may damage the tomatoes.\n"
            "Possibly the cover helps.\n"
            "The potential gain is small.\n"
            "`may possibly` is a stock phrase.\n"
            "> It could potentially rain.\n"
        )
        assert _lines("stacked-hedge", text) == []


class TestNominalizationOf:
    def test_flags_an_action_noun_followed_by_of(self) -> None:
        text = (
            "The implementation of the bike lane took two years.\n"
            "After completion of the survey, the city held a vote.\n"
            "Residents asked for an investigation\nof the delays.\n"
        )
        assert _lines("nominalization-of", text) == [1, 2, 3]

    def test_leaves_terms_of_art_plurals_and_verbs_alone(self) -> None:
        text = (
            "The distribution of commute times is skewed.\n"
            "Travel time is a function of distance.\n"
            "Two implementations of the signal timing exist.\n"
            "The city implemented the lane in two years.\n"
        )
        assert _lines("nominalization-of", text) == []


class TestInvertedAnimacy:
    def test_flags_a_persons_verb_on_an_artifact_subject(self) -> None:
        text = (
            "The model wants more rainfall data.\n"
            "When the test knows the answer, it passes.\n"
            "The forecast is good, but the data tells us little about hail.\n"
            "This script will\ntell you the station name.\n"
            "We found that the trained network is trying to memorize the coast.\n"
            "The numbers tell a different story about the coast.\n"
        )
        assert _lines("inverted-animacy", text) == [1, 2, 3, 4, 6, 7]

    def test_leaves_measurement_verbs_people_and_objects_alone(self) -> None:
        text = (
            "The model shows a clear warming trend.\n"
            "The test needs a fixture with three stations.\n"
            "The benchmark measures forecast error.\n"
            "Whoever runs the experiment wants a clean baseline.\n"
            "The team wants faster tests.\n"
            "The paper says the trend is real.\n"
            "The model is thought to overfit.\n"
            "A large number said they had never seen the coast.\n"
        )
        assert _lines("inverted-animacy", text) == []

    def test_leaves_plural_noun_uses_of_the_verb_alone(self) -> None:
        text = (
            "It runs sloplint (rhetorical model tells, high precision).\n"
            "Two model tells and three style rules fire on this draft.\n"
            "When the data claims are stored, the table grows.\n"
        )
        assert _lines("inverted-animacy", text) == []


class TestInvertedAnimacyCheck:
    def test_flags_things_that_earn_hold_win_or_buy(self) -> None:
        text = (
            "The window display earns most of the new members.\n"
            "Every reading group held a third of the seats.\n"
            "The designs that won the vote stay up.\n"
            "A small fee buys quicker returns.\n"
            "A shelf layout that crowds the doorway slows everyone.\n"
        )
        assert _lines("inverted-animacy-check", text) == [1, 2, 3, 4, 5]

    def test_leaves_people_and_plain_verbs_alone(self) -> None:
        text = (
            "The library splits visitors across the groups.\n"
            "The table shows the loans for each group.\n"
            "We gave each group half of the visitors.\n"
            "The shelf has room for forty books.\n"
        )
        assert _lines("inverted-animacy-check", text) == []


class TestBackReference:
    def test_flags_pointers_back_to_earlier_text(self) -> None:
        text = (
            "As discussed, the north branch opens first.\n"
            "I sent the rota in my previous message.\n"
            "Use the ladder fix above for the top shelf.\n"
            "See above for the rota.\n"
            "The earlier proposal had two shifts.\n"
            "The board meets again with the same three open questions.\n"
            "Per the rule, the branch closes at six.\n"
            "The shelf count is finished as reported.\n"
            "That clashes with your earlier instruction on opening times.\n"
            "The repairs wait until spring, per the board's own rule.\n"
            "The two questions about parking are still open.\n"
            "The shorter route list from earlier still applies.\n"
            "The rooms I suggested to the board earlier are free.\n"
        )
        assert _lines("back-reference", text) == list(range(1, 14))

    def test_leaves_restated_and_attributed_text_alone(self) -> None:
        text = (
            "We discussed the opening hours with the council on Monday.\n"
            "The earlier bus leaves at seven.\n"
            "The same staff cover both branches.\n"
            "As noted by the librarian, the roof leaks.\n"
            "As reported by the council, the library is still open on Sundays.\n"
            "As discussed below, the roof needs work.\n"
            'The guide says "as discussed" too often.\n'
        )
        assert _lines("back-reference", text) == []


class TestAnnouncingSentence:
    def test_flags_sentences_that_only_name_what_follows(self) -> None:
        text = (
            "Two changes help wheelchair users: a ramp and a wider door.\n\n"
            "We wanted to know whether late opening helps.\n\n"
            "Here is the plan:\n\n"
            "- Fix the ramp first.\n"
        )
        assert _lines("announcing-sentence", text) == [1, 3, 5]

    def test_leaves_sentences_that_carry_the_point_alone(self) -> None:
        text = (
            "The ramp, the lift and the wide door make the branch accessible.\n\n"
            "We asked the council whether a second lift fits the budget, and it does.\n\n"
            "The lift has one job: it carries wheelchairs to the first floor.\n"
        )
        assert _lines("announcing-sentence", text) == []


class TestStockEmphasis:
    def test_flags_stock_emphasis_phrases(self) -> None:
        text = (
            "Honestly, the queue is short.\n"
            "To be honest, the roof leaks.\n"
            "Frankly, the opening hours are too short.\n"
            "Parking near the branch is scarce, and that matters.\n"
            "Late fees are table stakes.\n"
            "The new layout is a big win.\n"
            "An honest count of visitors is hard.\n"
        )
        assert _lines("stock-emphasis", text) == [1, 2, 3, 4, 5, 6, 7]

    def test_leaves_plain_uses_of_the_words_alone(self) -> None:
        text = (
            "The staff value honesty in the rota.\n"
            "It does not matter which door you use.\n"
            "The matter went to the council.\n"
            "Nobody can win the raffle twice.\n"
        )
        assert _lines("stock-emphasis", text) == []


class TestHistoryInDocument:
    def test_flags_edit_history_and_corrections(self) -> None:
        text = (
            "The chart was changed from bars to dots.\n"
            "This note, unlike the earlier draft, covers both branches.\n"
            "Membership was 2.5 dollars, now it is free.\n"
            "This revision corrects the opening hours.\n"
            "The report now counts loans instead of visits.\n"
            "The field was previously called branch name.\n"
            "Unlike the last version, the map shows the car park.\n"
        )
        assert _lines("history-in-document", text) == [1, 2, 3, 4, 5, 6, 7]

    def test_leaves_changes_in_the_world_alone(self) -> None:
        text = (
            "Visitors who saw the poster no longer asked for directions.\n"
            "We compared the new catalogue with the previous catalogue.\n"
            "The loan rate changed from 4% to 6% after the reopening.\n"
            "The branch was previously a post office.\n"
            "The survey took its figures from an earlier version of the census.\n"
        )
        assert _lines("history-in-document", text) == []


class TestAmericanSpelling:
    def test_flags_british_spellings(self) -> None:
        text = (
            "The colour of each line marks its branch.\n"
            "Staff organised the reading lists and are personalising them.\n"
            "We will optimise the rota so the centre opens on time.\n"
            "The volunteers analysed the loans, and the modelling took a week.\n"
            "Each labelled box holds behaviour notes, a licence and a programme.\n"
        )
        assert _lines("american-spelling", text) == [1, 2, 2, 3, 3, 4, 4, 5, 5, 5, 5]

    def test_leaves_american_spellings_and_other_ise_words_alone(self) -> None:
        text = (
            "We advertise the exercise class with a precise timetable.\n"
            "The analyses cover two weeks, and the catalogue lists every organism.\n"
            "An optimist would call the characteristic delay realistic.\n"
            "We organized the center, analyzed the loans and practice programming.\n"
            'The British sign said "colour" and the `colour` field stays.\n'
        )
        assert _lines("american-spelling", text) == []


class TestAllCapsEmphasis:
    def test_flags_ordinary_words_in_capitals_once_per_run(self) -> None:
        text = (
            "Return the books VERY carefully.\n"
            "Do NOT leave the door open.\n"
            "This is IMPORTANT FOR EVERYONE on the rota.\n"
        )
        assert _lines("all-caps-emphasis", text) == [1, 2, 3]

    def test_leaves_acronyms_defined_terms_code_and_quotes_alone(self) -> None:
        text = (
            "The API returns JSON over HTTPS.\n"
            "We measured time to first page (TTFP), and TTFP fell.\n"
            "The ASPP FPN model ran on NASA hardware.\n"
            'The sign said "DO NOT ENTER" and the label said `NOT FOR LOAN`.\n'
        )
        assert _lines("all-caps-emphasis", text) == []

    def test_a_word_spelled_out_in_parentheses_is_an_acronym(self) -> None:
        text = (
            "The WHO (World Health Organization) published new guidance on clean water this"
            " spring.\nThe WHO also pays for village wells.\n"
        )
        assert _lines("all-caps-emphasis", text) == []
        assert _lines("undefined-acronym", text) == []

    def test_an_aside_in_parentheses_does_not_excuse_emphasis(self) -> None:
        text = "Do NOT (under any circumstances) leave the door open.\n"
        assert _lines("all-caps-emphasis", text) == [1]


class TestRatherThan:
    def test_flags_contrasts_the_other_linters_miss(self) -> None:
        text = (
            "We count loans rather than visits.\n"
            "The fee rose 2%, not 5%.\n"
            "Use `due_date`, not `return_date`.\n"
        )
        assert _lines("rather-than", text) == [1, 2, 3]

    def test_leaves_comparisons_and_the_form_slop_guard_flags_alone(self) -> None:
        text = (
            "I would rather wait for the full count than guess.\n"
            "The count was higher than we expected.\n"
            "The branch is open, not closed.\n"
        )
        assert _lines("rather-than", text) == []


class TestCannotRuleOut:
    def test_flags_conclusions_read_off_an_interval_edge(self) -> None:
        text = (
            "A small drop in loans cannot be ruled out.\n"
            "We can't rule out a 3% rise.\n"
            "We cannot exclude a seasonal effect.\n"
        )
        assert _lines("cannot-rule-out", text) == [1, 2, 3]

    def test_leaves_estimates_and_other_exclusions_alone(self) -> None:
        text = (
            "Loans rose 2% (95% interval 1% to 3%).\n"
            "The filter can exclude archived records.\n"
            "The council ruled out a second branch.\n"
        )
        assert _lines("cannot-rule-out", text) == []


class TestCleftSentence:
    def test_flags_cleft_and_pseudo_cleft_sentences(self) -> None:
        text = (
            "What keeps the queue short is the second desk.\n"
            "It is the narrow door that causes the delay.\n"
        )
        assert _lines("cleft-sentence", text) == [1, 2]

    def test_leaves_questions_extraposition_and_plain_clauses_alone(self) -> None:
        text = (
            "What should we do next?\n"
            "It is likely that the lift was broken.\n"
            "The narrow door slows the queue.\n"
            "What-if planning helps the rota.\n"
        )
        assert _lines("cleft-sentence", text) == []


THREE_SERIES = (
    "The branch lends books, films and games. ",
    "Visitors come on foot, by bus or by bike. ",
    "The staff shelve, label and repair the stock. ",
)


class TestTriadDensity:
    def test_flags_the_third_list_of_three_in_a_section(self) -> None:
        text = "## Services\n\n" + "\n".join(THREE_SERIES) + "\n"
        assert _lines("triad-density", text) == [5]

    def test_counts_a_series_with_a_serial_comma(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n"
            "The café sells tea, coffee, and cake.\n"
        )
        assert _lines("triad-density", text) == [5]

    def test_a_longer_list_is_not_a_list_of_three(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n"
            "The café sells tea, coffee, cake, soup and bread.\n"
            "The shop sells maps, pens, cards, and stamps.\n"
            "Tea gets a shelf, and coffee or cocoa gets a cupboard.\n"
            "The desk lends laptops, chargers and headphones.\n"
        )
        assert _lines("triad-density", text) == [8]

    def test_an_opening_clause_before_a_list_of_three_hides_it(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n"
            "In winter, the branch lends sledges, skates and scarves.\n"
        )
        assert _lines("triad-density", text) == []

    def test_counts_each_section_and_skips_list_items(self) -> None:
        text = (
            "## Services\n\n" + "\n".join(THREE_SERIES[:2]) + "\n\n"
            "## Visits\n\n" + "\n".join(THREE_SERIES[:2]) + "\n\n"
            "- Loans cover books, films and games.\n"
        )
        assert _lines("triad-density", text) == []


REOPENING = (
    "The branch reopens in spring. The roof is fixed. The lift works again. The ramp is wider."
    " The reading room has new chairs. The café stays closed. The garden has benches. The staff"
    " rota is longer. The opening hours are later. The council pays for all of it."
)


class TestTldrShape:
    def test_flags_a_long_summary(self) -> None:
        assert _lines("tldr-shape", f"## TL;DR\n\n{REOPENING}\n") == [1]

    def test_flags_a_summary_with_more_than_the_headline_numbers(self) -> None:
        text = (
            "# Reopening\n\n## Summary\n\n"
            "Loans rose 2.1% (95% interval 1.0% to 3.2%) and visits rose 4.0%"
            " (95% interval 2.5% to 5.5%).\n"
        )
        assert _lines("tldr-shape", text) == [3]

    def test_leaves_a_short_summary_and_body_sections_alone(self) -> None:
        text = (
            "## TL;DR\n\n"
            "The branch reopens in spring with a working lift. Loans rose 2% and visits rose 4%."
            " The roof is fixed. The ramp is wider. The council pays for the work. We ask for a"
            " later closing time.\n\n"
            f"## Results\n\n{REOPENING}\n"
        )
        assert _lines("tldr-shape", text) == []


class TestUndefinedAcronym:
    def test_flags_the_first_use_before_any_definition(self) -> None:
        text = (
            "The branch tracks TTFP for each visit. We define time to first page (TTFP) here.\n\n"
            "The CMS stores the catalogue, and the CMS is old.\n\n"
            "NASA's grant paid for the roof.\n\n"
            "The loan counts are FDR-controlled, and COVID-19 shut the branch.\n"
        )
        assert _lines("undefined-acronym", text) == [1, 3, 5, 7]

    def test_leaves_defined_universal_linked_and_code_acronyms_alone(self) -> None:
        text = (
            "We measured time to first page (TTFP), and TTFP fell.\n"
            "TTFB (time to first byte) also fell.\n"
            "NASA (National Aeronautics and Space Administration) and the AUC (area under the"
            " curve) both use the CRDT (Conflict-free Replicated Data Type) format.\n"
            "The API returns JSON, and the GPUs and CPUs sit idle.\n"
            "See [the RFC](https://example.com/rfc) and the `CMS` notes.\n"
            "Chapter II covers the TL;DR format. Do NOT skip it.\n"
            "The scans take 60 MB.\n"
        )
        assert _lines("undefined-acronym", text) == []

    def test_an_aside_that_does_not_spell_the_acronym_is_not_a_definition(self) -> None:
        text = "The CMS (the old catalogue software) stores every loan.\n"
        assert _lines("undefined-acronym", text) == [1]


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
        assert _lines("long-sentence", text) == []

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
        assert _lines("long-sentence", text) == []


class TestComplexSentence:
    def test_flags_each_forty_word_sentence_after_the_first(self) -> None:
        text = f"{STARTER_SENTENCE}\n\n{CRUST_SENTENCE}\n\n{CRUST_SENTENCE}\n"
        assert _lines("complex-sentence", text) == [3, 5]

    def test_one_long_sentence_is_free_and_run_ons_are_not_charged_twice(self) -> None:
        run_on = RIVER_RUN_ON.replace("early on Monday", "early on Monday or Tuesday")
        text = f"{run_on}\n\n{STARTER_SENTENCE}\n"
        findings = [(f.rule, f.line) for f in lint_prose.lint_text(text)]
        assert ("long-sentence", 1) in findings
        assert [rule for rule, _ in findings if rule == "complex-sentence"] == []

    def test_a_list_of_names_is_not_a_sentence(self) -> None:
        names = [f"[Baker Number{index}](/team/baker-{index}/)," for index in range(21)]
        text = f"{STARTER_SENTENCE}\n\n**Authors**\n\n" + "\n".join(names) + "\n"
        assert _lines("complex-sentence", text) == []


TREE_SURVEY = (
    "Our street counts its trees every spring.\n\n"
    "The oak by the school grew 40 centimeters this year and now shades 12 parked cars on sunny"
    " afternoons in June.\n\n"
    "Some of the young maples lost their leaves early, and the council replaced {maples} of them"
    " with {hornbeams} hornbeams in autumn.\n\n"
    "The plane trees along the main road are {height} meters tall and drop {bags} bags of bark"
    " each week.\n\n"
    "A survey found {hedge} bird nests in the hedges and {cherry} in the cherry trees near the"
    " corner shop on the hill.\n\n"
    "Residents planted {bulbs} bulbs under the lime tree and watered them {days} a week until the"
    " first frost came in.\n"
)


class TestNumberDensity:
    def test_flags_a_paragraph_with_more_than_two_numbers(self) -> None:
        text = (
            "# Bread sales\n\n"
            "The bakery tracks how many loaves it sells each day.\n\n"
            "## Weekdays\n\n"
            "The bakery sold 340 loaves on Monday, 410 on Tuesday and 380 on Wednesday.\n\n"
            "- The oven heats seven times faster, uses 30% less gas and costs $400.\n"
            "- Sales rose 3x in spring and fell by -12 loaves after a 1.5 hour outage.\n\n"
            "Each loaf weighs 800 g and costs $4.\n"
        )
        assert _lines("number-density", text) == [7, 9, 10]

    def test_does_not_count_years_dates_references_names_or_labels(self) -> None:
        text = (
            "# Sprint club\n\n"
            "The club trains on the track behind the school.\n\n"
            "In 2019 the club moved its 15-second sprint drills to March 3, as Figure 4 and Table 2"
            " show, after the V3 timer and the GPT-4 notes arrived on 2024-05-01 for the 2nd time"
            " [12]. Section 5 covers the 1990s.\n"
        )
        assert _lines("number-density", text) == []

    def test_exempts_summary_back_matter_captions_tables_code_footnotes_and_arithmetic(
        self,
    ) -> None:
        text = (
            "# Oven test\n\n"
            "## TL;DR\n\n"
            "The oven reached 220 C in 9 minutes and used 1.4 kWh.\n\n"
            "## Method\n\n"
            "We heated the oven three times and timed each heating.\n\n"
            "![Temperature curve](curve.png)\n\n"
            "The curve rises 40 degrees per minute for 5 minutes and then flattens at 220.\n\n"
            "Figure 2: Gas use was 1.1, 1.3 and 1.4 kWh across the 3 heatings.\n\n"
            "The average is (1.1 + 1.3 + 1.4) / 3 = 1.27 kWh, so we report 1.3 kWh.\n\n"
            "| heating | kWh | minutes |\n"
            "| 1 | 1.1 | 9 |\n\n"
            "`python heat.py --runs 3 --target 220 --step 5`\n\n"
            "The timer agreed with the logger to the second.[^1]\n\n"
            "[^1]: The logger samples at 10 Hz with 2 ms jitter on 4 channels.\n\n"
            "## Appendix A: raw data\n\n"
            "The first heating took 9 minutes, the second took 10 and the third took 9.\n\n"
            "### Calibration\n\n"
            "The probe read 0.3, 0.2 and 0.4 degrees high.\n\n"
            "## Footnotes\n\n"
            "1. The probe was calibrated at 0, 100 and 200 C.\n\n"
            "## Results\n\n"
            "The oven heats evenly.\n"
        )
        assert _lines("number-density", text) == []

    def test_flags_dense_body_prose_once_even_when_no_paragraph_is_over(self) -> None:
        dense = TREE_SURVEY.format(
            maples=3, hornbeams=5, height=20, bags=8, hedge=14, cherry=6, bulbs=25, days="2 times"
        )
        sparse = TREE_SURVEY.format(
            maples="most",
            hornbeams="young",
            height="many",
            bags="several",
            hedge="many",
            cherry="a few",
            bulbs="spring",
            days="several times",
        )
        assert _lines("number-density", dense) == [3]
        assert _lines("number-density", sparse) == []

    def test_counts_spelled_out_numbers_from_ten_up_and_multiples(self) -> None:
        spelled = TREE_SURVEY.format(
            maples="eleven",
            hornbeams="fifteen",
            height="twenty",
            bags="thirty",
            hedge="fourteen",
            cherry="sixty",
            bulbs="twenty-five",
            days="three times",
        )
        assert _lines("number-density", spelled) == [3]

    def test_leaves_small_spelled_out_counts_alone(self) -> None:
        text = (
            "The bakery tracks how many loaves it sells each day.\n\n"
            "The complaints came from two directions: three regulars wrote four letters about the"
            " two rye loaves.\n"
        )
        assert _lines("number-density", text) == []

    def test_counts_a_compound_spelled_out_number_once(self) -> None:
        text = (
            "The bakery tracks how many loaves it sells each day.\n\n"
            "The bakery sold two hundred and fifty loaves on Monday and ninety-two on Tuesday.\n\n"
            "Thursday brought three hundred loaves, forty cakes and twelve pies.\n"
        )
        assert _lines("number-density", text) == [5]

    def test_exempts_emphasized_captions(self) -> None:
        text = (
            "The oven was tested in March.\n\n"
            "*Table 1. Median heating time was 9, 10 and 12 minutes.*\n\n"
            "_Figure 2: Gas use was 1.1, 1.3 and 1.4 kWh._\n\n"
            "**Figure 3:** Peak temperatures were 210, 220 and 230 C.\n"
        )
        assert _lines("number-density", text) == []

    def test_does_not_count_version_numbers(self) -> None:
        text = (
            "We checked the linters on public essays.\n\n"
            "We ran the parser 2.10.0 and the formatter 0.5.1 on 32,000 words from 2 machines.\n"
        )
        assert _lines("number-density", text) == []

    def test_does_not_count_footnote_references(self) -> None:
        text = (
            "The bakery opened in spring.\n\n"
            "Each loaf weighs 800 g and costs $4.[^1] The recipe has not changed.[^2]\n\n"
            "[^1]: Prices from the spring menu.\n"
            "[^2]: The owner confirmed this.\n"
        )
        assert _lines("number-density", text) == []

    def test_opening_paragraph_stands_in_for_a_missing_summary(self) -> None:
        text = (
            "The bakery sold 340 loaves on Monday, 410 on Tuesday and 380 on Wednesday.\n\n"
            "Thursday brought 290 loaves, 35 cakes and 60 pies.\n"
        )
        assert _lines("number-density", text) == [3]


CROPS = ("Tomatoes", "Beans", "Potatoes", "Onions", "Lettuce", "Carrots", "Peppers", "Squash")
GARDEN_PARAGRAPH = (
    "The beds along the fence get the most sun, so we plant the crops that need heat there and"
    " keep the shady corner for leafy greens. We water early in the morning, weed on weekends and"
    " add compost each autumn. Slugs are the main pest, and a ring of crushed shells keeps most of"
    " them away."
)


def _garden(marker: str, crops: tuple[str, ...], body: str) -> str:
    return "".join(f"{marker} {crop}\n\n{body}\n\n" for crop in crops)


class TestHeadingDensity:
    def test_flags_the_first_top_level_section_past_the_budget(self) -> None:
        text = "# Garden notes\n\n" + _garden("##", CROPS, "The beds need water in dry weeks.")
        assert _lines("heading-density", text) == [27]

    def test_counts_h1_sections_when_there_is_no_lone_title(self) -> None:
        text = _garden("#", CROPS, "The beds need water in dry weeks.")
        assert _lines("heading-density", text) == [25]

    def test_leaves_six_sections_nested_headings_and_long_documents_alone(self) -> None:
        short_body = "The beds need water in dry weeks."
        six_sections = "# Garden notes\n\n" + _garden("##", CROPS[:6], short_body)
        nested = "# Garden notes\n\n## Beds\n\n" + _garden("###", CROPS, short_body)
        long_body = f"{GARDEN_PARAGRAPH}\n\n{GARDEN_PARAGRAPH}"
        long_document = "# Garden notes\n\n" + _garden("##", CROPS, long_body)
        assert _lines("heading-density", six_sections) == []
        assert _lines("heading-density", nested) == []
        assert _lines("heading-density", long_document) == []


class TestMasking:
    def test_rules_skip_code_quotes_tables_and_links(self) -> None:
        triggers = (
            "The model wants the implementation of a cache that may possibly cost 3, 4 or 5"
            f" dollars. {RIVER_RUN_ON} {STARTER_SENTENCE} {CRUST_SENTENCE} As discussed, honestly,"
            " the CMS was previously called B7 and is VERY slow rather than fast. What keeps it"
            " slow is the disk. Two things matter: speed and cost. We can't rule out a fault."
            f" The window display wins most visitors. {' '.join(THREE_SERIES)}"
        )
        text = (
            "# Masking\n\n"
            f"```\n{triggers}\n```\n\n"
            f"> {triggers}\n\n"
            f"| {triggers} |\n\n"
            f"`{triggers}`\n\n"
            "[A plain link](https://example.com/the-model-wants/may-possibly/1/2/3)\n"
        )
        assert lint_prose.lint_text(text) == []


class TestEndToEnd:
    def test_realistic_readme_finds_exact_issues(self) -> None:
        readme = """# Project Notes

This small service processes events and stores them for later review.
It includes a command line interface and a compact local database.

## Getting Started

Install the package and run `python app.py` from the project directory.
The service writes logs to `./logs` and uses SQLite by default.

## Design Decisions

We finished step 3 — then measured the results.
The baseline covers versions 3–5 and 2020–2024.

The service accepts JSON and CSV input formats.

Requests are validated before they enter the queue.

The worker stores completed jobs in the local database.

## Configuration

Set the `APP_ENV` variable before starting the service.
The default value is `development`.

| Name | Purpose |
| --- | --- |
| APP_ENV | Runtime mode |

## **Deployment Guide**

Use the following command to build a container image.
The image contains the application and its dependencies.

## Troubleshooting

See [the issue tracker](https://example.com/project-with-hyphens/issues).
Run `python app.py --help` to list command line options.

## Further Reading

The API reference describes every supported endpoint.
The examples folder contains requests for common workflows.
"""
        assert len(readme.splitlines()) >= 40
        findings = lint_prose.lint_text(readme)
        assert {(finding.rule, finding.line) for finding in findings} == {
            ("coined-label", 13),
            ("em-dash", 13),
            ("short-paragraph-run", 13),
            ("thin-h2-section", 6),
            ("thin-h2-section", 31),
            ("thin-h2-section", 36),
            ("thin-h2-section", 41),
        }


class TestExcerpt:
    def test_excerpt_of_a_hit_late_in_a_long_line_shows_the_hit(self) -> None:
        opening = "The garden club meets on the first Saturday of each month in the library. " * 4
        finding = next(
            f
            for f in lint_prose.lint_text(f"{opening}Frost may possibly damage the tomatoes.\n")
            if f.rule == "stacked-hedge"
        )
        assert "may possibly" in finding.excerpt


class TestCli:
    def test_exit_codes_and_json_output(self, tmp_path: Path) -> None:
        script_path = Path(lint_prose.__file__).resolve()
        clean_path = tmp_path / "clean.md"
        flagged_path = tmp_path / "flagged.md"
        clean_path.write_text("A clear sentence.\n", encoding="utf-8")
        flagged_path.write_text("An em dash — here.\n", encoding="utf-8")

        clean_result = subprocess.run(
            [sys.executable, str(script_path), str(clean_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        flagged_result = subprocess.run(
            [sys.executable, str(script_path), "--json", str(flagged_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert clean_result.returncode == 0
        assert flagged_result.returncode == 1
        json_findings = json.loads(flagged_result.stdout)
        assert [(finding["path"], finding["rule"]) for finding in json_findings] == [
            (str(flagged_path), "em-dash")
        ]
