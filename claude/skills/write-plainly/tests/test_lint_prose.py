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
        text = "An em dash — interrupts this sentence.\n> quoted — text\n| table — cell |\n`inline — code`\n```\ncode — block\n```\n[link](https://example.com/a-b)\n"
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [("em-dash", 1)]


class TestDashSubstitute:
    def test_flags_pauses_but_keeps_ranges_lists_and_compounds(self) -> None:
        text = "Use this – then that.\nWords - more words\nWords--more words\nWords -- more words\n3–5 and pp. 10–12 and 2020–2024\n- list marker\nA well-known phrase.\n`inline – code`\n```\ncode – block\n```\n> quoted – text\n| table – cell |\nSee https://example.com/a-b.\n"
        rules = [finding.rule for finding in lint_prose.lint_text(text)]
        assert rules == ["dash-substitute"] * 4


class TestCoinedLabel:
    def test_flags_labeled_work_phases_only(self) -> None:
        text = "We completed step 4 and Option B.\nA step function works; the option to wait is available.\nA run of tests passed. Run the script. Use an A/B test.\n`phase 2`\n```\nround 3\n```\n> arm A\n| tier B |\nhttps://example.com/phase-2\n"
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


class TestBoldRunIn:
    def test_flags_line_initial_run_ins(self) -> None:
        text = "**How accurate the clock is.** The clock drifts.\n- **Latency:** 40 ms\n**Standalone bold.**\nThis **mid-sentence:** stays unflagged.\n`**inline:** code`\n```\n**code:** text\n```\n> **quote:** text\n| **table:** cell |\n"
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("bold-run-in", 1),
            ("bold-run-in", 2),
        ]


class TestThinH2Section:
    def test_counts_lists_tables_and_fenced_code_as_body_blocks(self) -> None:
        text = "## Thin\nOne paragraph.\n## List only\n- one\n- two\n## Two blocks\nA paragraph.\n\n```\ncode\n```\n## Table\n| a | b |\n| --- | --- |\n## End\n"
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
        text = "First short sentence.\n\nSecond short sentence.\n\nThird short sentence.\n\nA longer paragraph has one sentence. It connects two thoughts.\n\nDr. Smith arrived.\n\nThe value is 3.14.\n\nThis is etc. useful.\n"
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
        text = "One sentence.\n\n- list item.\n\nSecond sentence.\n\n> quote.\n\nThird sentence.\n\n| cell |\n"
        assert "short-paragraph-run" not in [finding.rule for finding in lint_prose.lint_text(text)]


class TestTitleCaseHeading:
    def test_flags_title_case_and_ignores_sentence_case_or_short_headings(self) -> None:
        text = "## Building Better Writing Habits\n## Building better writing habits\n## API and URL Design Guide\n## Simple Guide\n"
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
    "The oak by the school grew 40 centimetres this year and now shades 12 parked cars on sunny"
    " afternoons in June.\n\n"
    "Some of the young maples lost their leaves early, and the council replaced {maples} of them"
    " with {hornbeams} hornbeams in autumn.\n\n"
    "The plane trees along the main road are {height} metres tall and drop {bags} bags of bark"
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
            f" dollars. {RIVER_RUN_ON} {STARTER_SENTENCE} {CRUST_SENTENCE}"
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
