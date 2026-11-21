import math

import pytest

from common import kendall_tau_b, parse_ranking, ranks, word_count

LETTERS = ("A", "B", "C", "D", "E")


class TestWordCount:
    def test_contractions_decimals_and_hyphenated_words_count_once(self) -> None:
        assert word_count("The model's error fell 3.5% — a well-known drop.") == 8


class TestRanking:
    def test_letters_best_first_with_equals_joining_a_tie(self) -> None:
        assert parse_ranking("CA=EBD", LETTERS) == [["C"], ["A", "E"], ["B"], ["D"]]

    def test_lower_case_and_spaces_are_accepted(self) -> None:
        assert parse_ranking(" ca = e bd ", LETTERS) == [["C"], ["A", "E"], ["B"], ["D"]]

    @pytest.mark.parametrize(
        "typed",
        ["CAEB", "CAEBDD", "CAEBF", "=CAEBD", "CAEBD=", "CA==EBD", "A=B=C=D=E", "CA1EBD"],
    )
    def test_a_ranking_must_place_each_letter_once_in_at_least_two_places(self, typed: str) -> None:
        with pytest.raises(ValueError):
            parse_ranking(typed, LETTERS)

    def test_tied_letters_share_the_mean_of_their_places(self) -> None:
        assert ranks([["C"], ["A", "E"], ["B"], ["D"]]) == {
            "C": 1.0,
            "A": 2.5,
            "E": 2.5,
            "B": 4.0,
            "D": 5.0,
        }


class TestKendallTau:
    def test_identical_orders_give_one_and_reversed_orders_minus_one(self) -> None:
        assert kendall_tau_b([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == pytest.approx(1.0)
        assert kendall_tau_b([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == pytest.approx(-1.0)

    def test_counts_concordant_and_discordant_pairs(self) -> None:
        assert kendall_tau_b([1, 2, 3], [3, 1, 2]) == pytest.approx(-1 / 3)

    def test_ties_shrink_the_denominator_as_in_tau_b(self) -> None:
        tau = kendall_tau_b([1, 2, 3, 4, 5], [1, 2.5, 2.5, 4, 5])
        assert tau == pytest.approx(9 / math.sqrt(10 * 9))

    def test_a_constant_ranking_has_no_tau(self) -> None:
        with pytest.raises(ValueError):
            kendall_tau_b([1, 2, 3], [2, 2, 2])
