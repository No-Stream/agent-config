from pathlib import Path

import pytest
from conftest import STUB_TASKS

from common import load_tasks, parse_ranking, ranks, word_count

LETTERS = ("A", "B", "C", "D", "E")


class TestWordCount:
    def test_contractions_decimals_and_hyphenated_words_count_once(self) -> None:
        assert word_count("The model's error fell 3.5% — a well-known drop.") == 8


class TestLoadTasks:
    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ('question = "Why does the kettle switch itself off?"', 'question = ""'),
            (
                'left_to_other_documents = "how to descale the kettle"',
                'left_to_other_documents = " "',
            ),
        ],
        ids=["empty-question", "blank-left-to-other-documents"],
    )
    def test_a_task_must_state_its_question_and_what_it_leaves_out(
        self, tmp_path: Path, old: str, new: str
    ) -> None:
        tasks_file = tmp_path / "tasks.toml"
        tasks_file.write_text(STUB_TASKS.replace(old, new))
        with pytest.raises(ValueError):
            load_tasks([tasks_file])


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
