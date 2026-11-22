from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

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

    def test_an_aside_that_ends_in_a_hyphen_is_read_like_any_other(self) -> None:
        text = (
            "The scheduler pins work to CPUs (single- and multi-) when the queue is long.\n"
            "The ABC (all bakers -) list goes up on Friday.\n"
        )
        assert _lines("undefined-acronym", text) == [2]


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
        assert _lines("em-dash", text) == [1, 5, 11]

    def test_a_pipe_in_prose_makes_a_table_only_above_a_matching_delimiter_row(self) -> None:
        text = (
            "We sift the flour | sugar mix — twice.\n\n"
            "Flour | sugar — one to one.\n---\n\n"
            "Flour | sugar | salt — in that order.\n--- | ---\n"
        )
        assert _lines("em-dash", text) == [1, 3, 6]


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
