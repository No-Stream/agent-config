from __future__ import annotations

import lint_prose


def _lines(rule: str, text: str) -> list[int]:
    return [finding.line for finding in lint_prose.lint_text(text) if finding.rule == rule]


class TestAiVocabulary:
    def test_flags_words_models_overuse(self) -> None:
        text = (
            "We delve into the bakery's flour costs.\n"
            "Opening early was a pivotal choice for the shop.\n"
            "The interplay between oven heat and humidity sets the crust.\n"
            "The co-op leverages volunteer drivers for deliveries.\n"
            "Shared ovens foster trust between the bakers.\n"
            "The scheduler orchestrates the proofing times.\n"
            "The bread market is a competitive landscape.\n"
            "The guide helps bakers navigate the complexities of food permits.\n"
            "The shop boasts a stone oven.\n"
            "This is a deep dive into sourdough.\n"
        )
        assert _lines("ai-vocabulary", text) == list(range(1, 11))

    def test_leaves_literal_and_common_words_alone(self) -> None:
        text = (
            "The landscape around the mill is flat farmland.\n"
            "They became foster parents in 2019.\n"
            "The crucial step is a robust, significant rise, ensuring an even crumb.\n"
            "Overall, the bakery sold more bread, particularly rye.\n"
            "The bank's position is highly leveraged.\n"
            "The baker boasts about his rye, and we embarked on the ferry at nine.\n"
        )
        assert _lines("ai-vocabulary", text) == []

    def test_flags_a_word_in_a_heading(self) -> None:
        assert _lines("ai-vocabulary", "# A pivotal year for the bakery\n") == [1]


class TestPromotionalWord:
    def test_flags_sales_language(self) -> None:
        text = (
            "The new mixer will supercharge your mornings.\n"
            "Self-checkout is a game-changer for the library.\n"
            "The cutting-edge sensor installs in a minute.\n"
            "The app unlocks the full potential of your garden.\n"
            "The results were transformative.\n"
            "The future looks bright. Exciting times ahead.\n"
        )
        assert _lines("promotional-word", text) == [1, 2, 3, 4, 5, 6, 6]

    def test_leaves_literal_unlocking_alone(self) -> None:
        text = (
            "Unlock the screen with your PIN.\n"
            "The thread unlocks the mutex before it returns.\n"
            "Seamless cloning blends the two photos.\n"
            "The future of the branch depends on the council budget.\n"
        )
        assert _lines("promotional-word", text) == []


class TestBorrowedJargon:
    def test_flags_scientific_terms_used_for_weight(self) -> None:
        text = (
            "Parking is orthogonal to the question of opening hours.\n"
            "The new branch was an inflection point for the library.\n"
            "There is a non-zero chance that the roof leaks again.\n"
            "Self-checkout was a paradigm shift for the staff.\n"
        )
        assert _lines("borrowed-jargon", text) == [1, 2, 3, 4]

    def test_leaves_measured_quantities_alone(self) -> None:
        text = "The gradient is non-zero only at the input.\nThe curve has no inflection.\n"
        assert _lines("borrowed-jargon", text) == []


class TestStockConcession:
    def test_flags_a_concession_that_names_no_challenge(self) -> None:
        text = (
            "Despite these challenges, the garden opened on time.\n"
            "Despite its limitations, the survey is useful.\n"
            "The town faces several challenges in winter.\n"
            "Challenges remain, but the plan is sound.\n"
        )
        assert _lines("stock-concession", text) == [1, 2, 3, 4]

    def test_leaves_named_challenges_alone(self) -> None:
        text = (
            "Despite the rain, the garden opened on time.\n"
            "The team faced two challenges: frost and theft.\n"
        )
        assert _lines("stock-concession", text) == []


class TestEraFraming:
    def test_flags_openings_that_frame_the_times(self) -> None:
        text = (
            "In today's fast-paced world, libraries lend laptops.\n"
            "In an era of cheap e-books, the branch still lends paperbacks.\n"
            "Now more than ever, readers need quiet rooms.\n"
            "In the digital age, the catalog moved online.\n"
        )
        assert _lines("era-framing", text) == [1, 2, 3, 4]

    def test_leaves_dated_history_alone(self) -> None:
        text = (
            "In the age of steam, the mill ran on coal.\n"
            "In today's release, the catalog search returns JSON.\n"
        )
        assert _lines("era-framing", text) == []


class TestDeadTransition:
    def test_flags_filler_transitions(self) -> None:
        text = (
            "Moving forward, the branch opens at nine.\n"
            "We will track loans going forward.\n"
            "When all is said and done, readers want books.\n"
            "Last but not least, the café reopened.\n"
            "We will circle back on parking.\n"
        )
        assert _lines("dead-transition", text) == [1, 2, 3, 4, 5]

    def test_leaves_literal_motion_alone(self) -> None:
        text = (
            "The cart kept going forward down the ramp.\n"
            "Moving forward through the stacks takes time.\n"
            "Count the till at the end of the day.\n"
            "The iterator is moving forward. The robot circles backwards around the cone.\n"
        )
        assert _lines("dead-transition", text) == []


class TestInsightTeaser:
    def test_flags_insider_teasers(self) -> None:
        text = (
            "## The part everyone misses\n\n"
            "Conventional wisdom says you knead bread for ten minutes.\n"
            "Contrary to popular belief, salt does not kill yeast.\n"
            "Most people don't realize that flour goes stale.\n"
            "This is where things get interesting.\n"
        )
        assert _lines("insight-teaser", text) == [1, 3, 4, 5, 6]

    def test_leaves_sloplint_forms_and_plain_claims_alone(self) -> None:
        text = (
            "Here's what nobody tells you about bread.\n"
            "What most people get wrong is the water temperature.\n"
            "Most people know how to bake a simple loaf.\n"
            "We test whether conventional wisdom holds for rye flour.\n"
        )
        assert _lines("insight-teaser", text) == []


class TestEngagementBait:
    def test_flags_lines_that_perform_for_the_reader(self) -> None:
        text = (
            "The branch lends 4,000 books a week. Let that sink in.\n"
            "Think about it: would you shelve books by colour?\n"
            "What if I told you the catalog is free?\n"
            "Plot twist: it is.\n"
            "This changes everything about how we lend books.\n"
            "Make no mistake, the roof needs work.\n"
        )
        assert _lines("engagement-bait", text) == [1, 2, 3, 4, 5, 6]

    def test_leaves_plain_requests_to_think_alone(self) -> None:
        text = (
            "Think about the walk from the bus stop when you plan the entrance.\n"
            "Let this sink in water before you weigh it.\n"
            "What if I told the compiler to inline the function?\n"
        )
        assert _lines("engagement-bait", text) == []


class TestChatPhrasing:
    def test_flags_phrasing_addressed_to_the_requester(self) -> None:
        text = (
            "Let me know if you would like a longer version.\n"
            "Would you like me to add a map?\n"
            "I hope this helps.\n"
            "Feel free to reach out with questions.\n"
            "Happy to iterate!\n"
        )
        assert _lines("chat-phrasing", text) == [1, 2, 3, 4, 5]

    def test_leaves_reported_preferences_alone(self) -> None:
        text = "Readers would like longer opening hours, and the survey asked what they hope for.\n"
        assert _lines("chat-phrasing", text) == []


class TestVagueQuantifier:
    def test_flags_quantifiers_that_stand_in_for_a_count(self) -> None:
        text = (
            "A number of readers asked for later hours.\n"
            "The branch offers a wide array of classes.\n"
            "Myriad volunteers help on Saturdays.\n"
            "The move raised a host of questions.\n"
        )
        assert _lines("vague-quantifier", text) == [1, 2, 3, 4]

    def test_leaves_sized_quantities_alone(self) -> None:
        text = (
            "A small number of readers asked for later hours,"
            " and a large number of them were students.\n"
        )
        assert _lines("vague-quantifier", text) == []


class TestWrappedLines:
    def test_a_phrase_wrapped_across_lines_still_matches(self) -> None:
        text = (
            "The branch lends 4,000 books a week. Let that\n"
            "sink in. More\n"
            "importantly, the lift works.\n"
        )
        findings = [(f.rule, f.line, f.column) for f in lint_prose.lint_text(text)]
        assert ("engagement-bait", 1, 38) in findings
        assert not any(rule == "stock-emphasis" for rule, _, _ in findings)


class TestSectionLabel:
    def test_flags_stock_labels_in_headings_and_run_ins(self) -> None:
        text = (
            "## Key takeaways\n\n"
            "**Why it matters.** Late buses strand readers.\n\n"
            "Bottom line: the branch should open at eight.\n\n"
            "## Final thoughts.\n"
        )
        assert _lines("section-label", text) == [1, 3, 5, 7]

    def test_leaves_template_headings_and_ordinary_sentences_alone(self) -> None:
        text = (
            "## Summary\n\n## Next steps\n\n## Conclusion\n\n"
            "The bottom line of the form asks for a signature.\n"
        )
        assert _lines("section-label", text) == []


class TestStockEmphasisAnnouncing:
    def test_flags_importance_assertions_and_filler_openers(self) -> None:
        text = (
            "It is important to note that the branch closes early on Fridays.\n"
            "It should be noted that parking is free.\n"
            "It's worth noting that the café opens at eight.\n"
            "Needless to say, the raffle sold out.\n"
            "Importantly, the lift now reaches every floor.\n"
            "At its core, a library lends things.\n"
            "The reality is that most readers come by bus.\n"
            "Let me be clear: the branch stays open.\n"
        )
        assert _lines("stock-emphasis", text) == list(range(1, 9))

    def test_leaves_comparative_adverbs_and_plain_notes_alone(self) -> None:
        text = (
            "More importantly, the lift now reaches every floor.\n"
            "The staff noted that parking is free.\n"
            "The magnetic field peaks at its core.\n"
            "It is critical to note each failed request in the log.\n"
            "It is important to stress-test the lock.\n"
        )
        assert _lines("stock-emphasis", text) == []


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
        assert _lines("intensifier", text) == [5, 6]

    def test_leaves_the_very_and_quoted_speech_alone(self) -> None:
        text = (
            "The queue is very long. The lift is extremely slow."
            " The very first reader arrived at nine, in this very room."
            ' A reader said the café was "very, very, very good."\n'
        )
        assert _lines("intensifier", text) == []


class TestPassiveByAgent:
    def test_flags_a_passive_that_names_its_actor(self) -> None:
        text = (
            "The new shelves were built by volunteers.\n"
            "Opening hours are set by the council.\n"
            "Loan numbers were strongly affected by the bus strike.\n"
            "The banner was designed by Ming.\n"
        )
        assert _lines("passive-by-agent", text) == [1, 2, 3, 4]

    def test_leaves_means_measures_and_feelings_alone(self) -> None:
        text = (
            "The roof was fixed by replacing two tiles.\n"
            "Loans rose by 12% and were sorted by date.\n"
            "Readers were surprised by the new layout, and the shelf was unaffected by the leak.\n"
            "The volunteers built the new shelves.\n"
        )
        assert _lines("passive-by-agent", text) == []


class TestFormalWord:
    def test_flags_formal_words_with_everyday_synonyms(self) -> None:
        text = (
            "The branch will utilize a new scanner.\n"
            "Work will commence in May, prior to the audit.\n"
            "Staff endeavor to ascertain which repairs come first.\n"
            "The plan necessitates a second lift, and the trustees are cognizant of it.\n"
        )
        assert _lines("formal-word", text) == [1, 2, 2, 3, 3, 4, 4]

    def test_leaves_plain_words_and_the_noun_endeavor_alone(self) -> None:
        text = "The branch will use a new scanner, a long endeavor that starts in May.\n"
        assert _lines("formal-word", text) == []


class TestWordyPhrase:
    def test_flags_phrases_with_a_short_form(self) -> None:
        text = (
            "We added a desk in order to shorten the queue.\n"
            "When it comes to parking, the council has a plan.\n"
            "With regard to hours, the branch opens at nine.\n"
            "Due to the fact that the lift broke, the café moved.\n"
            "In the event that it rains, the fair moves inside.\n"
        )
        assert _lines("wordy-phrase", text) == [1, 2, 3, 4, 5]

    def test_leaves_terms_of_art_alone(self) -> None:
        text = "We took the gradient with respect to the weights, in terms of loss per token.\n"
        assert _lines("wordy-phrase", text) == []


class TestFinanceWord:
    def test_flags_finance_words_for_plain_ideas(self) -> None:
        text = (
            "The branch has foregone late fees this year.\n"
            "The café recoups its outlay by spring.\n"
            "The scanner repays its cost within a year.\n"
            "Students carry 30% of weekend loans.\n"
        )
        assert _lines("finance-word", text) == [1, 2, 3, 4]

    def test_leaves_idioms_and_loads_alone(self) -> None:
        text = (
            "The result was a foregone conclusion.\n"
            "The borrower repays the loan monthly, and the van carries 30 boxes.\n"
            "We recouple the spins, and the borrower repays the costly repair.\n"
        )
        assert _lines("finance-word", text) == []


class TestWhetherRange:
    def test_flags_a_range_that_pretends_to_cover_every_case(self) -> None:
        text = (
            "Whether it's a novel or a cookbook, the branch has it.\n"
            "Whether you're a student or a retiree, the hours suit you.\n"
        )
        assert _lines("whether-range", text) == [1, 2]

    def test_leaves_real_questions_alone(self) -> None:
        text = (
            "We asked whether it is open late or early, and nobody knew.\n"
            "Whether it's raining or not, the fair goes ahead.\n"
        )
        assert _lines("whether-range", text) == []


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
        assert _lines("metaphor", text) == [1, 2, 3, 4, 5, 6, 7, 7]

    def test_leaves_literal_bars_ledgers_and_levers_alone(self) -> None:
        text = (
            "The café has a bar and a ledger, and the jaw works as a lever.\n"
            "The staff work the floor on Tuesdays.\n"
        )
        assert _lines("metaphor", text) == []


class TestSignposting:
    def test_flags_signposts_and_recap_openers(self) -> None:
        text = (
            "In this section, we will explain the returns desk.\n"
            "Let's dive in.\n"
            "The scanner reads each barcode, as shown below.\n"
            "In summary, readers wait less.\n"
        )
        assert _lines("signposting", text) == [1, 2, 3, 4]

    def test_leaves_plain_references_alone(self) -> None:
        text = (
            "The table below lists the hours.\n"
            "The guide has a section on parking, and in short weeks the café closes early.\n"
            "In this guide, we willingly keep the old format.\n"
        )
        assert _lines("signposting", text) == []


class TestSymbolInProse:
    def test_flags_emoji_and_arrows_in_headings_and_prose(self) -> None:
        text = "## 📚 Hours\n\nThe queue fell → the desk worked.\n\nA cache miss -> a slow read.\n"
        assert _lines("symbol-in-prose", text) == [1, 3, 5]

    def test_leaves_code_tables_and_footnote_returns_alone(self) -> None:
        text = (
            "Run `a -> b` here, and $f: X → Y$ is a map.\n\n"
            "| From | To |\n| --- | --- |\n| A | → B |\n\n"
            'See the note.↩ The guide says "✨ new".\n'
            "The synthesizer plays C♯, and the build shows ✓.\n"
        )
        assert _lines("symbol-in-prose", text) == []


class TestRatherThanLessAbout:
    def test_flags_less_about_with_a_noun_subject(self) -> None:
        text = "The change is less about speed and more about trust.\n"
        assert _lines("rather-than", text) == [1]

    def test_leaves_comparisons_of_quantity_alone(self) -> None:
        text = "We learned less about convergence than expected. Do we know less about memory?\n"
        assert _lines("rather-than", text) == []

    def test_leaves_the_pronoun_form_to_sloplint(self) -> None:
        text = "It's less about speed and more about trust.\n"
        assert _lines("rather-than", text) == []
