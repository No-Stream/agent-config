import math

import pytest

from common import kendall_tau_b, word_count


class TestWordCount:
    def test_contractions_decimals_and_hyphenated_words_count_once(self) -> None:
        assert word_count("The model's error fell 3.5% — a well-known drop.") == 8


class TestKendallTau:
    def test_identical_orders_give_one_and_reversed_orders_minus_one(self) -> None:
        assert kendall_tau_b([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == 1.0
        assert kendall_tau_b([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0

    def test_counts_concordant_and_discordant_pairs(self) -> None:
        assert kendall_tau_b([1, 2, 3], [3, 1, 2]) == pytest.approx(-1 / 3)

    def test_ties_shrink_the_denominator_as_in_tau_b(self) -> None:
        tau = kendall_tau_b([1, 2, 3, 4, 5], [1, 2.5, 2.5, 4, 5])
        assert tau == pytest.approx(9 / math.sqrt(10 * 9))

    def test_a_constant_ranking_has_no_tau(self) -> None:
        with pytest.raises(ValueError):
            kendall_tau_b([1, 2, 3], [2, 2, 2])
