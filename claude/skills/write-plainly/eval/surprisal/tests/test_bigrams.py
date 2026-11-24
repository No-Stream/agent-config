import math

import pytest

from bigrams import count_reference, unattested_phrases
from prose import tokens

REFERENCE = [
    "The old lighthouse keeper rowed to the rocky shore every morning.",
    "A rocky shore and a calm harbour sheltered the fishing fleet.",
    "The keeper rowed back at dusk, tired.",
]


class TestCountReference:
    def test_counts_attested_content_pairs_and_words(self):
        counts = count_reference(REFERENCE)
        assert ("rocky", "shore") in counts.pairs
        assert ("fishing", "fleet") in counts.pairs
        assert ("dusk", "tired") not in counts.pairs
        assert counts.words["rowed"] == 2
        assert counts.total_words == 29
        assert counts.distinct_pairs == len(counts.pairs)

    def test_wanted_limits_the_pairs_and_words_kept_but_not_the_totals(self):
        counts = count_reference(
            REFERENCE, wanted_pairs={("rocky", "shore"), ("tide", "pool")}, wanted_words={"keeper"}
        )
        assert counts.pairs == {("rocky", "shore")}
        assert dict(counts.words) == {"keeper": 2}
        assert counts.total_words == 29
        assert counts.distinct_pairs == len(count_reference(REFERENCE).pairs)

    def test_unigram_surprisal_is_add_one_smoothed_over_the_whole_reference(self):
        counts = count_reference(REFERENCE)
        assert (counts.total_words, counts.distinct_words) == (29, 21)
        assert counts.unigram_bits("Rowed") == pytest.approx(math.log2(50 / 3))
        assert counts.unigram_bits("glacier") == pytest.approx(math.log2(50))
        small = count_reference(["calm harbour"])
        assert small.unigram_bits("calm") == pytest.approx(1.0)
        assert small.unigram_bits("glacier") == pytest.approx(2.0)

    def test_unigram_surprisal_of_limited_counts_keeps_the_whole_reference_denominator(self):
        limited = count_reference(REFERENCE, wanted_words={"rowed"})
        assert limited.unigram_bits("rowed") == pytest.approx(math.log2(50 / 3))


class TestUnattestedPhrases:
    @pytest.fixture
    def counts(self):
        return count_reference(REFERENCE)

    def test_flags_unattested_pairs_and_merges_chains(self, counts):
        text = "On the rocky shore: a lighthouse-keeper patience budget."
        phrases = unattested_phrases(tokens(text), counts.pairs)
        assert [text[phrase.start : phrase.end] for phrase in phrases] == ["keeper patience budget"]

    def test_attested_and_function_word_pairs_are_not_flagged(self, counts):
        assert (
            unattested_phrases(tokens("The keeper rowed to the rocky shore."), counts.pairs) == []
        )

    def test_separate_chains_stay_separate(self, counts):
        text = "Calm glacier, rocky shore, tidal moraine."
        phrases = unattested_phrases(tokens(text), counts.pairs)
        assert [text[phrase.start : phrase.end] for phrase in phrases] == [
            "Calm glacier",
            "tidal moraine",
        ]
