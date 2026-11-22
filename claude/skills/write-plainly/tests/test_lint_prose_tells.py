from __future__ import annotations

import lint_prose
from conftest import rule_lines


class TestBorrowedJargon:
    def test_flags_scientific_terms_used_for_weight(self) -> None:
        text = (
            "Parking is orthogonal to the question of opening hours.\n"
            "The new branch was an inflection point for the library.\n"
            "There is a non-zero chance that the roof leaks again.\n"
            "Self-checkout was a paradigm shift for the staff.\n"
        )
        assert rule_lines("borrowed-jargon", text) == [1, 2, 3, 4]

    def test_leaves_measured_quantities_alone(self) -> None:
        text = "The gradient is non-zero only at the input.\nThe curve has no inflection.\n"
        assert rule_lines("borrowed-jargon", text) == []


class TestChatPhrasing:
    def test_flags_phrasing_addressed_to_the_requester(self) -> None:
        text = (
            "Let me know if you would like a longer version.\n"
            "Would you like me to add a map?\n"
            "I hope this helps.\n"
            "Feel free to reach out with questions.\n"
            "Happy to iterate!\n"
        )
        assert rule_lines("chat-phrasing", text) == [1, 2, 3, 4, 5]

    def test_leaves_reported_preferences_alone(self) -> None:
        text = "Readers would like longer opening hours, and the survey asked what they hope for.\n"
        assert rule_lines("chat-phrasing", text) == []


class TestWrappedLines:
    def test_a_phrase_wrapped_across_lines_still_matches(self) -> None:
        text = (
            "The branch lends 4,000 books a week. Let me know\n"
            "if the count looks low. More\n"
            "importantly, the lift works.\n"
        )
        findings = [(f.rule, f.line, f.column) for f in lint_prose.lint_text(text)]
        assert ("chat-phrasing", 1, 38) in findings
        assert not any(rule == "stock-emphasis" for rule, _, _ in findings)


class TestSectionLabel:
    def test_flags_stock_labels_in_headings_and_run_ins(self) -> None:
        text = (
            "## Key takeaways\n\n"
            "**Why it matters.** Late buses strand readers.\n\n"
            "Bottom line: the branch should open at eight.\n\n"
            "## Final thoughts.\n"
        )
        assert rule_lines("section-label", text) == [1, 3, 5, 7]

    def test_leaves_template_headings_and_ordinary_sentences_alone(self) -> None:
        text = (
            "## Summary\n\n## Next steps\n\n## Conclusion\n\n"
            "The bottom line of the form asks for a signature.\n"
        )
        assert rule_lines("section-label", text) == []


class TestIntensifier:
    def test_flags_intensifiers_after_two_per_section(self) -> None:
        text = (
            "## Opening hours\n\n"
            "The branch is very busy on Saturdays.\n"
            "The queue is extremely long at noon.\n"
            "The staff are incredibly patient.\n"
            "The café is truly small.\n\n"
            "## Parking\n\n"
            "The car park is very small, and the bus is very slow.\n"
        )
        assert rule_lines("intensifier", text) == [5, 6]

    def test_leaves_the_very_and_quoted_speech_alone(self) -> None:
        text = (
            "The queue is very long. The lift is extremely slow."
            " The very first reader arrived at nine, in this very room."
            ' A reader said the café was "very, very, very good."\n'
        )
        assert rule_lines("intensifier", text) == []


class TestPassiveByAgent:
    def test_flags_a_passive_that_names_its_actor(self) -> None:
        text = (
            "The new shelves were built by volunteers.\n"
            "Opening hours are set by the council.\n"
            "Loan numbers were strongly affected by the bus strike.\n"
            "The banner was designed by Ming.\n"
        )
        assert rule_lines("passive-by-agent", text) == [1, 2, 3, 4]

    def test_leaves_means_measures_and_feelings_alone(self) -> None:
        text = (
            "The roof was fixed by replacing two tiles.\n"
            "Loans rose by 12% and were sorted by date.\n"
            "Readers were surprised by the new layout, and the shelf was unaffected by the leak.\n"
            "The volunteers built the new shelves.\n"
        )
        assert rule_lines("passive-by-agent", text) == []


class TestFormalWord:
    def test_flags_formal_words_with_everyday_synonyms(self) -> None:
        text = (
            "The branch will utilize a new scanner.\n"
            "Work will commence in May, prior to the audit.\n"
            "Staff endeavor to ascertain which repairs come first.\n"
            "The plan necessitates a second lift, and the trustees are cognizant of it.\n"
        )
        assert rule_lines("formal-word", text) == [1, 2, 2, 3, 3, 4, 4]

    def test_leaves_plain_words_and_the_noun_endeavor_alone(self) -> None:
        text = "The branch will use a new scanner, a long endeavor that starts in May.\n"
        assert rule_lines("formal-word", text) == []


class TestWordyPhrase:
    def test_flags_phrases_with_a_short_form(self) -> None:
        text = (
            "We added a desk in order to shorten the queue.\n"
            "When it comes to parking, the council has a plan.\n"
            "With regard to hours, the branch opens at nine.\n"
            "Due to the fact that the lift broke, the café moved.\n"
            "In the event that it rains, the fair moves inside.\n"
        )
        assert rule_lines("wordy-phrase", text) == [1, 2, 3, 4, 5]

    def test_leaves_terms_of_art_alone(self) -> None:
        text = "We took the gradient with respect to the weights, in terms of loss per token.\n"
        assert rule_lines("wordy-phrase", text) == []


class TestFinanceWord:
    def test_flags_finance_words_for_plain_ideas(self) -> None:
        text = (
            "The branch has foregone late fees this year.\n"
            "The café recoups its outlay by spring.\n"
            "The scanner repays its cost within a year.\n"
            "Students carry 30% of weekend loans.\n"
        )
        assert rule_lines("finance-word", text) == [1, 2, 3, 4]

    def test_leaves_idioms_and_loads_alone(self) -> None:
        text = (
            "The result was a foregone conclusion.\n"
            "The borrower repays the loan monthly, and the van carries 30 boxes.\n"
            "We recouple the spins, and the borrower repays the costly repair.\n"
        )
        assert rule_lines("finance-word", text) == []


class TestMetaphor:
    def test_flags_images_and_stock_idioms(self) -> None:
        text = (
            "The new desk raises the bar for returns.\n"
            "The survey is a yardstick for the branch.\n"
            "The budget is a ledger of tradeoffs.\n"
            "The late opening bridges the gap to night-shift workers.\n"
            "We read the loans through the lens of the bus timetable.\n"
            "Loans bounce back after the holiday.\n"
            "The café is the low-hanging fruit, and the lift is the tip of the iceberg.\n"
        )
        assert rule_lines("metaphor", text) == [1, 2, 3, 4, 5, 6, 7, 7]

    def test_leaves_literal_bars_ledgers_and_levers_alone(self) -> None:
        text = (
            "The café has a bar and a ledger, and the jaw works as a lever.\n"
            "The staff work the floor on Tuesdays.\n"
        )
        assert rule_lines("metaphor", text) == []


class TestSignposting:
    def test_flags_signposts_and_recap_openers(self) -> None:
        text = (
            "In this section, we will explain the returns desk.\n"
            "Let's dive in.\n"
            "The scanner reads each barcode, as shown below.\n"
            "In summary, readers wait less.\n"
        )
        assert rule_lines("signposting", text) == [1, 2, 3, 4]

    def test_leaves_plain_references_alone(self) -> None:
        text = (
            "The table below lists the hours.\n"
            "The guide has a section on parking, and in short weeks the café closes early.\n"
            "Loans rose, in short, because the bus returned.\n"
            "In short weeks the café closes early.\n"
            "In this guide, we willingly keep the old format.\n"
        )
        assert rule_lines("signposting", text) == []


class TestSymbolInProse:
    def test_flags_emoji_and_arrows_in_headings_and_prose(self) -> None:
        text = "## 📚 Hours\n\nThe queue fell → the desk worked.\n\nA cache miss -> a slow read.\n"
        assert rule_lines("symbol-in-prose", text) == [1, 3, 5]

    def test_leaves_code_tables_and_footnote_returns_alone(self) -> None:
        text = (
            "Run `a -> b` here, and $f: X → Y$ is a map.\n\n"
            "| From | To |\n| --- | --- |\n| A | → B |\n\n"
            'See the note.↩ The guide says "✨ new".\n'
            "The synthesizer plays C♯, and the build shows ✓.\n"
        )
        assert rule_lines("symbol-in-prose", text) == []
