from __future__ import annotations

import lint_prose
from conftest import rule_lines

PR_SUMMARY = (
    "This change lets members reserve a tool a week ahead. The reservation page lists each tool"
    " with its free days. A reserved tool is held at the desk for two days. Members get an email"
    " the day before pickup."
)
PR_MORE_SENTENCES = (
    "Staff can cancel a hold from the desk. Holds expire at closing time. Staff can extend a hold"
    " once."
)
PAPER_LIST = (
    "the desk also keeps a paper list of holds for members who have no email address and staff"
    " read it out each morning before the branch opens to the public"
)
PR_APPENDIX = "## Details\n\n- The page reads the loans table.\n- Emails go out at eight.\n"


def _findings(rule: str, text: str, **options: object) -> list[tuple[int, str]]:
    """Return the line and excerpt of each finding of one rule, linted with the options."""
    return [
        (finding.line, finding.excerpt)
        for finding in lint_prose.lint_text(text, **options)
        if finding.rule == rule
    ]


class TestThinSection:
    def test_counts_lists_tables_and_fenced_code_as_body_blocks(self) -> None:
        text = (
            "## Thin\nOne paragraph.\n## List only\n- one\n- two\n## Two blocks\nA paragraph.\n\n"
            "```\ncode\n```\n## Table\n| a | b |\n| --- | --- |\n## End\n"
        )
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("thin-section", 1),
            ("thin-section", 3),
            ("thin-section", 12),
            ("thin-section", 15),
        ]

    def test_exempts_summary_sections(self) -> None:
        text = (
            "## TL;DR\nThe comet returns in 2061.\n"
            "## TLDR\nThe comet returns in 2061.\n"
            "## Summary\nThe comet returns in 2061.\n"
            "## Abstract\nThe comet returns in 2061.\n"
            "## Orbit\nThe orbit takes about 76 years.\n"
        )
        assert rule_lines("thin-section", text) == [9]

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
        assert rule_lines("thin-section", text) == [8]

    def test_a_list_of_wrapped_or_spaced_items_is_one_list(self) -> None:
        text = (
            "## Tools\n\n"
            "- a scale that reads to the gram, so the salt\n"
            "  and the yeast are weighed exactly\n"
            "- a lame for scoring the loaf\n\n"
            "- a banneton lined with a linen cloth\n\n"
            "---\n"
        )
        assert rule_lines("thin-section", text) == [1]

    def test_a_lower_heading_needs_a_full_paragraph(self) -> None:
        full = (
            "The ferry leaves the north pier at seven. It crosses in about forty minutes. Bikes"
            " ride free on the lower deck. The café opens once the ferry clears the harbor."
        )
        text = (
            "# Island guide\n\n"
            f"## Getting there\n\n{full}\n\n"
            "### Tickets\n\nBuy tickets at the pier. The office opens at six.\n\n"
            f"### Bikes\n\n{full}\n\n"
            "#### Parking\n\n- the north lot\n- the harbor lot\n\n"
            "### Luggage\n\n"
            "### Pets\n\nDogs ride on the open deck.\n\n"
            f"{full}\n"
        )
        assert rule_lines("thin-section", text) == [7, 15, 20]

    def test_skips_a_heading_whose_next_block_is_a_deeper_heading(self) -> None:
        text = (
            "# Island guide\n\n"
            "## Getting there\n\n"
            "### Tickets\n\nBuy tickets at the pier. The office opens at six.\n\n"
            "## Staying over\n\nThe inn has six rooms.\n\n"
            "### Booking\n\nBook a room by phone.\n"
        )
        assert rule_lines("thin-section", text) == [5, 13]

    def test_checks_h1_sections_when_there_is_no_lone_title(self) -> None:
        text = (
            "# Getting there\n\nThe ferry leaves the north pier at seven.\n\n"
            "# Staying over\n\nThe inn has six rooms.\n\nBook a room by phone.\n"
        )
        assert rule_lines("thin-section", text) == [1]

    def test_skips_back_matter_sections(self) -> None:
        template = "## Test plan\n\n- Ran the tests.\n\n## Checklist\n\n- Updated the docs.\n"
        description = f"# Tool holds\n\n{PR_SUMMARY}\n\n---\n\n{template}"
        report = (
            f"# Tool holds\n\n## Holds\n\n{PR_SUMMARY}\n\n{PR_MORE_SENTENCES}\n\n"
            "## Appendix\n\n### Data\n\n- The page reads the loans table.\n"
        )
        assert rule_lines("thin-section", description) == [7, 11]
        assert _findings("thin-section", description, pr=True) == []
        assert rule_lines("thin-section", report) == []


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
        assert rule_lines("short-paragraph-run", text) == []

    def test_nonparagraph_blocks_break_the_run(self) -> None:
        text = (
            "One sentence.\n\n- list item.\n\nSecond sentence.\n\n> quote.\n\nThird sentence.\n\n"
            "| cell |\n"
        )
        assert rule_lines("short-paragraph-run", text) == []


REOPENING = (
    "The branch reopens in spring. The roof is fixed. The lift works again. The ramp is wider."
    " The reading room has new chairs. The café stays closed. The garden has benches. The staff"
    " rota is longer. The opening hours are later. The council pays for all of it."
)


class TestTldrShape:
    def test_flags_a_long_summary(self) -> None:
        assert rule_lines("tldr-shape", f"## TL;DR\n\n{REOPENING}\n") == [1]

    def test_flags_a_summary_with_more_than_the_headline_numbers(self) -> None:
        text = (
            "# Reopening\n\n## Summary\n\n"
            "Loans rose 2.1% (95% interval 1.0% to 3.2%) and visits rose 4.0%"
            " (95% interval 2.5% to 5.5%).\n"
        )
        assert rule_lines("tldr-shape", text) == [3]

    def test_leaves_a_short_summary_and_body_sections_alone(self) -> None:
        text = (
            "## TL;DR\n\n"
            "The branch reopens in spring with a working lift. Loans rose 2% and visits rose 4%."
            " The roof is fixed. The ramp is wider. The council pays for the work. We ask for a"
            " later closing time.\n\n"
            f"## Results\n\n{REOPENING}\n"
        )
        assert rule_lines("tldr-shape", text) == []


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
TWO_MORE_NUMBERS = " The bakery also sold 40 loaves and 12 buns."


def _paragraph_flags(sentence: str, more: str = TWO_MORE_NUMBERS) -> bool:
    """Whether a paragraph of the sentence and more numbers, after a short opening, has too many."""
    text = f"The bakery tracks how many loaves it sells each day.\n\n{sentence}{more}\n"
    return rule_lines("number-density", text) == [3]


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
        assert rule_lines("number-density", text) == [7, 9, 10]

    def test_does_not_count_years_dates_references_names_or_labels(self) -> None:
        text = (
            "# Sprint club\n\n"
            "The club trains on the track behind the school.\n\n"
            "In 2019 the club moved its 15-second sprint drills to March 3, as Figure 4 and Table 2"
            " show, after the V3 timer and the GPT-4 notes arrived on 2024-05-01 for the 2nd time"
            " [12]. Section 5 covers the 1990s.\n"
        )
        assert rule_lines("number-density", text) == []

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
        assert rule_lines("number-density", text) == []

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
        assert rule_lines("number-density", dense) == [3]
        assert rule_lines("number-density", sparse) == []

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
        assert rule_lines("number-density", spelled) == [3]

    def test_leaves_small_spelled_out_counts_alone(self) -> None:
        text = (
            "The bakery tracks how many loaves it sells each day.\n\n"
            "The complaints came from two directions: three regulars wrote four letters about the"
            " two rye loaves. All but four of the breads are rye, and four of the five ovens run"
            " at night.\n"
        )
        assert rule_lines("number-density", text) == []

    def test_counts_a_dozen_and_the_large_magnitudes(self) -> None:
        for counted in (
            "Rye sold a dozen loaves.",
            "Rye sold two dozen loaves.",
            "The oven toasted a million crumbs.",
            "The town ate two billion crumbs.",
        ):
            assert _paragraph_flags(counted), counted
        for vague in (
            "Rye sold half a dozen loaves.",
            "Rye sold dozens of loaves.",
            "Rye sold hundreds of loaves.",
            "The multi-million rebuild finished.",
        ):
            assert not _paragraph_flags(vague), vague

    def test_counts_a_magnitude_word_after_digits_as_part_of_that_number(self) -> None:
        for sentence in (
            "The town ate 40 thousand crumbs.",
            "The rebuild cost $2 million.",
            "The town ate 1.5 billion crumbs.",
        ):
            assert not _paragraph_flags(sentence, more=" The bakery also sold 40 loaves."), sentence

    def test_counts_a_small_number_word_that_is_a_multiple_percentage_or_share(self) -> None:
        for counted in (
            "Rye sales rose fourfold.",
            "Rye sales rose two-fold.",
            "Rye sales rose three percent.",
            "Rye sales rose five percentage points.",
            "One in four loaves was rye.",
            "Two out of three buns were sweet.",
        ):
            assert _paragraph_flags(counted), counted
        assert not _paragraph_flags("Rye sold well in two shops.")

    def test_counts_multiples_written_without_a_number_word(self) -> None:
        for counted in (
            "Rye sold twice as many loaves.",
            "Rye cost twice the price of wheat.",
            "Rye sales doubled.",
            "Rye sales tripled.",
            "Rye sales halved.",
            "Rye sales rose 3-fold.",
            "Rye sales rose 10fold.",
        ):
            assert _paragraph_flags(counted), counted
        for repeat_or_name in ("We baked the rye twice.", "Rye sales have a doubling time."):
            assert not _paragraph_flags(repeat_or_name), repeat_or_name

    def test_counts_measured_amounts_and_fractions_written_in_words(self) -> None:
        for counted in (
            "A rye loaf costs three dollars.",
            "The price of rye rose three cents.",
            "The crust took five minutes longer.",
            "The oven ran seven degrees hot.",
            "The rye scored one point higher.",
            "The judges' rating rose a tenth of a point.",
            "Rye made up two-thirds of sales.",
            "Rye sold about a quarter more.",
            "Rye sold a third at the market.",
            "Half of the loaves were rye.",
            "Rye sold more than half on Saturday.",
            "The dough proofed for two and a half hours.",
            "Rye sales rose by three.",
            "The wait fell to under four.",
            "Rye sold nearly nine on Monday.",
        ):
            assert _paragraph_flags(counted), counted
        for count_of_things in (
            "Rye sold half a dozen loaves.",
            "We tested a third recipe.",
            "At one point the oven failed.",
            "The rye was judged by two bakers.",
            "Rye sold in two or three shops.",
            "Two of the five ovens run at night.",
        ):
            assert not _paragraph_flags(count_of_things), count_of_things

    def test_a_paragraph_reworded_into_words_and_fractions_still_counts(self) -> None:
        text = (
            "The city changed one bus route in March.\n\n"
            "The new route cut the trip by about a quarter, saving roughly three minutes at rush"
            " hour and twice that at night. Riders rose by more than half on weekdays and about a"
            " third on weekends. Roughly a tenth of riders still change buses, and fares cover one"
            " and a half times the old share.\n"
        )
        assert rule_lines("number-density", text) == [3]

    def test_counts_a_compound_spelled_out_number_once(self) -> None:
        text = (
            "The bakery tracks how many loaves it sells each day.\n\n"
            "The bakery sold two hundred and fifty loaves on Monday and ninety-two on Tuesday.\n\n"
            "Thursday brought three hundred loaves, forty cakes and twelve pies.\n"
        )
        assert rule_lines("number-density", text) == [5]

    def test_exempts_emphasized_captions(self) -> None:
        text = (
            "The oven was tested in March.\n\n"
            "*Table 1. Median heating time was 9, 10 and 12 minutes.*\n\n"
            "_Figure 2: Gas use was 1.1, 1.3 and 1.4 kWh._\n\n"
            "**Figure 3:** Peak temperatures were 210, 220 and 230 C.\n"
        )
        assert rule_lines("number-density", text) == []

    def test_does_not_count_version_numbers(self) -> None:
        text = (
            "We checked the linters on public essays.\n\n"
            "We ran the parser 2.10.0 and the formatter 0.5.1 on 32,000 words from 2 machines.\n"
        )
        assert rule_lines("number-density", text) == []

    def test_does_not_count_footnote_references(self) -> None:
        text = (
            "The bakery opened in spring.\n\n"
            "Each loaf weighs 800 g and costs $4.[^1] The recipe has not changed.[^2]\n\n"
            "[^1]: Prices from the spring menu.\n"
            "[^2]: The owner confirmed this.\n"
        )
        assert rule_lines("number-density", text) == []

    def test_superscript_footnotes_are_footnotes(self) -> None:
        text = (
            "The bakery opened in spring.\n\n"
            "Each loaf weighs 800 g and costs $4.¹ The recipe has not changed.²\n\n"
            "¹ Prices from the spring menu, at 3 stores, 12 stalls and 40 carts.\n\n"
            "² The owner confirmed this.\n"
        )
        assert rule_lines("number-density", text) == []
        assert rule_lines("short-paragraph-run", text) == []

    def test_opening_paragraph_stands_in_for_a_missing_summary(self) -> None:
        text = (
            "The bakery sold 340 loaves on Monday, 410 on Tuesday and 380 on Wednesday.\n\n"
            "Thursday brought 290 loaves, 35 cakes and 60 pies.\n"
        )
        assert rule_lines("number-density", text) == [3]

    def test_an_opening_is_body_prose_when_the_document_has_a_summary(self) -> None:
        text = (
            "The bakery sold 340 loaves on Monday, 410 on Tuesday and 380 on Wednesday.\n\n"
            "## Summary\n\n"
            "Sales held steady.\n"
        )
        assert rule_lines("number-density", text) == [1]

    def test_an_opening_longer_than_a_summary_is_body_prose(self) -> None:
        text = (
            "The library lends tools as well as books. Members borrow drills, ladders and sewing"
            " machines. The shed behind the branch holds 140 tools. Loans run for a week. A late"
            " tool costs $2 a day. Volunteers check each tool when it comes back. Broken tools go"
            " to a repair night. The council pays for new tools. Last spring it bought 30 of them.\n"
        )
        assert rule_lines("number-density", text) == [1]

    def test_an_opening_with_more_than_the_headline_numbers_is_body_prose(self) -> None:
        text = (
            "The bakery sold 340 loaves on Monday, 410 on Tuesday, 380 on Wednesday and 290 on"
            " Thursday, and 35 cakes on Friday.\n"
        )
        assert rule_lines("number-density", text) == [1]


OVEN_OPENING = "We tested whether the new oven bakes bread faster than the old one.\n\n"


class TestSupportingStatistic:
    def test_flags_each_kind_of_supporting_statistic_in_body_prose(self) -> None:
        sentences = (
            "The new oven baked faster, with a t of 3.10.",
            "The Welch test ran on 9.73 df.",
            "Loaves rose higher in it (p = 0.02).",
            "The crust darkened, with a p-value of 0.04.",
            "Sales rose 4.0% [2.5%, 5.5%] after the move.",
            "The 95% interval runs from 1.0 to 3.2 minutes.",
            "- Each loaf lost 2.1 ± 0.4 grams of water.",
            "The new probe read within 0.92 of the true heat, against 0.97 for the old one.",
            "The new tin browned 0.62 of the crust, vs. 0.71 for the old tin.",
            "The share of burnt loaves had a 95% Wilson interval of 0.12 to 0.19.",
            "The 95% confidence interval is [12, 18] minutes.",
            "The loaves rose higher, t(22) = 2.10.",
            "The oven factor had an F of 3.1.",
            "The z-score was 2.3.",
            "The chi-squared was 4.2.",
            "Sales rose 4.0% (95% CI 2.5–5.5%).",
            "Visits rose 3.1% (90% CI 1.2-5.0%).",
            "Each loaf lost 2.1 +/- 0.4 grams.",
            "The Welch test had df = 9.7.",
            "The test ran on 14 degrees of freedom.",
            "The credible interval runs from 0.1 to 0.4.",
            "The new probe read 0.92 versus 0.97 for the old one.",
            "The new probe read 0.92 while the old one read 0.97.",
            "The new probe read 0.92 compared with 0.97 for the old one.",
            "The Welch test ran on fourteen degrees of freedom.",
            "Sales rose 4.0% (95 percent CI 2.5% to 5.5%).",
            "The ninety-five percent interval runs from 1.0 to 3.2 minutes.",
            "The 95% interval runs between 1.0 and 3.2 minutes.",
            "Each loaf lost 2.1 plus or minus 0.4 grams.",
            "The crust darkened, with a p-value below 0.05.",
            "The crust darkened, with a p-value that was less than 0.05.",
            "Loaves rose higher in it (p under 0.05).",
            "The probe reads the heat to within ±1.1% at the back of the oven.",
        )
        text = OVEN_OPENING + "\n\n".join(sentences) + "\n"
        paragraph_lines = [3 + 2 * index for index in range(len(sentences))]
        assert rule_lines("supporting-statistic", text) == paragraph_lines

    def test_flags_a_summary_and_an_opening_paragraph_too(self) -> None:
        summary = "## TL;DR\n\nThe new oven bakes bread faster (p < 0.01).\n"
        opening = "The new oven bakes bread faster, with a t of 3.10.\n"
        assert rule_lines("supporting-statistic", summary) == [3]
        assert rule_lines("supporting-statistic", opening) == [1]

    def test_leaves_headline_numbers_arithmetic_and_exempt_blocks_alone(self) -> None:
        text = (
            OVEN_OPENING + "The new oven bakes a loaf in 25 minutes, 20% faster than the old one."
            " Its probe reads within 0.92 of the true heat while the oven warms up. The share is"
            " 0.25 * 0.4 = 0.1 of the day.\n\n"
            "The new tin browned 0.62 of the crust against 0.71 for the old tin, so the gap is"
            " 0.71 - 0.62 = 0.09.\n\n"
            "Its crust score rose from 0.81 to 0.84. The oven alarm sounds at humidity 0.05 and"
            " 0.2.\n\n"
            "The bakery spent most of its budget on flour ($14,200). Bread sales rose in both"
            " seasons (2023, 2024).\n\n"
            "CI takes 10 to 15 minutes on every pull request. Earlier ovens drifted the same way"
            " [3, 7].\n\n"
            "![Bake times](bake.png)\n\n"
            "The two probes read 0.92 against 0.97 of the true heat.\n\n"
            "| oven | t | p |\n| new | 3.10 | 0.01 |\n\n"
            "The new oven is faster.[^1]\n\n"
            "[^1]: A t of 3.10 on 14 df, p = 0.01.\n\n"
            "## Appendix\n\n"
            "The 95% interval runs from 1.0 to 3.2 minutes.\n"
        )
        assert rule_lines("supporting-statistic", text) == []


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
        assert rule_lines("heading-density", text) == [27]

    def test_counts_h1_sections_when_there_is_no_lone_title(self) -> None:
        text = _garden("#", CROPS, "The beds need water in dry weeks.")
        assert rule_lines("heading-density", text) == [25]

    def test_counts_headings_at_every_level_below_the_title(self) -> None:
        short_body = "The beds need water in dry weeks."
        nested = "# Garden notes\n\n## Beds\n\n" + _garden("###", CROPS, short_body)
        assert rule_lines("heading-density", nested) == [25]

    def test_leaves_six_sections_and_long_documents_alone(self) -> None:
        short_body = "The beds need water in dry weeks."
        six_sections = "# Garden notes\n\n## Beds\n\n" + _garden("###", CROPS[:5], short_body)
        long_body = f"{GARDEN_PARAGRAPH}\n\n{GARDEN_PARAGRAPH}"
        long_document = "# Garden notes\n\n" + _garden("##", CROPS, long_body)
        assert rule_lines("heading-density", six_sections) == []
        assert rule_lines("heading-density", long_document) == []

    def test_leaves_back_matter_headings_out_of_the_count(self) -> None:
        template = _garden("##", CROPS[:7], "- Checked.")
        description = f"# Tool holds\n\n{PR_SUMMARY}\n\n---\n\n{template}"
        appendix = _garden("###", CROPS[:7], "The beds need water in dry weeks.")
        report = f"# Garden notes\n\n## Beds\n\n{GARDEN_PARAGRAPH}\n\n## Appendix\n\n{appendix}"
        assert rule_lines("heading-density", description) == [31]
        assert _findings("heading-density", description, pr=True) == []
        assert rule_lines("heading-density", report) == []


TEN_WORDS = "The branch lends drills and ladders to members every week."


def _tool_library(paragraphs: int, appendix: int = 0) -> str:
    body = "\n\n".join([TEN_WORDS] * paragraphs)
    extras = (
        "| tool | loans |\n| --- | --- |\n| drill | 40 |\n\n"
        "![Loans by month](loans.png)\n\n"
        f"Figure 1: {TEN_WORDS}\n\n"
        f"```\n{TEN_WORDS}\n```\n\n"
        f"The ladders are new.[^1]\n\n[^1]: {TEN_WORDS}\n"
    )
    back = "\n\n".join([TEN_WORDS] * appendix)
    return f"# Tool library\n\n{body}\n\n{extras}\n## Appendix\n\n{back}\n"


class TestOverBudget:
    def test_flags_main_text_past_a_tenth_over_the_budget(self) -> None:
        within = _tool_library(paragraphs=10, appendix=30)
        over = _tool_library(paragraphs=11, appendix=30)
        assert _findings("over-budget", within, budget=96) == []
        assert _findings("over-budget", over, budget=96) == [
            (1, "main text has 114 words against a budget of 96")
        ]

    def test_runs_only_when_a_budget_is_given(self) -> None:
        assert _findings("over-budget", _tool_library(paragraphs=40)) == []


class TestRevisionGrowth:
    def test_flags_a_revision_whose_main_text_grew(self) -> None:
        old = _tool_library(paragraphs=3)
        new = _tool_library(paragraphs=4)
        assert _findings("revision-growth", new, against=old) == [
            (1, "main text has 44 words against 34 in the old version")
        ]
        assert _findings("appendix-growth", new, against=old) == []

    def test_reports_appendix_growth_on_its_own_line(self) -> None:
        old = _tool_library(paragraphs=4, appendix=1)
        new = _tool_library(paragraphs=3, appendix=2)
        assert _findings("revision-growth", new, against=old) == []
        assert _findings("appendix-growth", new, against=old) == [
            (1, "appendix and footnotes have 30 words against 20 in the old version")
        ]

    def test_leaves_a_shorter_or_unchanged_revision_alone(self) -> None:
        old = _tool_library(paragraphs=4, appendix=2)
        for new in (_tool_library(paragraphs=3, appendix=2), old):
            findings = lint_prose.lint_text(new, against=old)
            assert not {"revision-growth", "appendix-growth"} & {f.rule for f in findings}


class TestPrShape:
    def test_passes_a_short_summary_above_a_rule_with_one_leading_title(self) -> None:
        text = f"## Summary\n\n{PR_SUMMARY}\n\n![The page](page.png)\n\n---\n\n{PR_APPENDIX}"
        assert _findings("pr-shape", text, pr=True) == []

    def test_passes_a_short_description_with_no_rule(self) -> None:
        assert _findings("pr-shape", f"{PR_SUMMARY}\n", pr=True) == []

    def test_runs_only_for_a_pr_description(self) -> None:
        text = f"{PR_SUMMARY} {PR_MORE_SENTENCES}\n\n{PR_APPENDIX}"
        assert _findings("pr-shape", text) == []

    def test_flags_a_summary_past_six_sentences(self) -> None:
        text = f"{PR_SUMMARY} {PR_MORE_SENTENCES}\n\n---\n\n{PR_APPENDIX}"
        assert _findings("pr-shape", text, pr=True) == [
            (1, "summary above the first horizontal rule has 7 sentences and 58 words")
        ]

    def test_flags_a_summary_past_150_words(self) -> None:
        long_sentence = "In short, " + ", and ".join([PAPER_LIST] * 4) + "."
        text = f"{PR_SUMMARY} {long_sentence}\n\n---\n\n{PR_APPENDIX}"
        assert _findings("pr-shape", text, pr=True) == [
            (1, "summary above the first horizontal rule has 5 sentences and 164 words")
        ]

    def test_flags_lists_tables_code_bold_lead_ins_and_later_headings_in_the_summary(
        self,
    ) -> None:
        text = (
            f"## Summary\n\n**What:** {PR_SUMMARY}\n\n- holds\n- emails\n\n"
            "| page | change |\n| --- | --- |\n| holds | new |\n\n```\nreserve --days 7\n```\n\n"
            "## Testing\n\nWe ran the tests.\n\n---\n\nNotes for reviewers.\n"
        )
        problems = (
            "summary above the first horizontal rule has a list, a table, a code block,"
            " a bold lead-in and a heading after the title"
        )
        assert _findings("pr-shape", text, pr=True) == [(1, problems)]

    def test_a_diagram_in_the_summary_is_a_figure(self) -> None:
        diagram = "```mermaid\nflowchart LR\n    hold --> pickup\n```"
        text = f"## Summary\n\n{PR_SUMMARY}\n\n{diagram}\n\n---\n\n{PR_APPENDIX}"
        assert _findings("pr-shape", text, pr=True) == []

    def test_the_part_below_the_rule_is_the_appendix(self) -> None:
        numbers = "The page served 340 holds on Monday, 410 on Tuesday and 380 on Wednesday.\n"
        text = f"{PR_SUMMARY}\n\n---\n\n{numbers}"
        longer = f"{PR_SUMMARY}\n\n---\n\n{numbers}\n{PR_MORE_SENTENCES}\n"
        assert rule_lines("number-density", text) == [5]
        assert _findings("number-density", text, pr=True) == []
        growth = {f.rule for f in lint_prose.lint_text(longer, against=text, pr=True)}
        assert {"revision-growth", "appendix-growth"} & growth == {"appendix-growth"}

    def test_without_a_rule_the_whole_description_is_the_summary(self) -> None:
        text = f"{PR_SUMMARY} {PR_MORE_SENTENCES}\n\n{PR_APPENDIX}"
        problems = (
            "no horizontal rule, and the whole description has 7 sentences and 58 words,"
            " a list and a heading after the title"
        )
        assert _findings("pr-shape", text, pr=True) == [(1, problems)]


LOAN_SENTENCES = (
    "Each bar is one month of loans.",
    "Drills led with 340 loans in May, 410 in June and 380 in July.",
    "Ladders rose from 90 to 150.",
)


class TestCaptionAfterImage:
    @staticmethod
    def _after_image(block: str) -> str:
        return (
            "# Tool loans\n\nThe branch lends tools to its members.\n\n"
            f"![Loans by month](loans.png)\n\n{block}\n"
        )

    def test_two_sentences_after_an_image_are_its_caption(self) -> None:
        caption = " ".join(LOAN_SENTENCES[:2])
        assert rule_lines("number-density", self._after_image(caption)) == []

    def test_a_longer_paragraph_after_an_image_is_body_text(self) -> None:
        paragraph = " ".join(LOAN_SENTENCES)
        assert rule_lines("number-density", self._after_image(paragraph)) == [7]
