import pytest
import torch
from job_entry import falcon_scores

OBSERVER = [[1.0, 0.0, -1.0], [0.5, 1.5, -0.5], [-1.0, 0.0, 2.0], [0.0, 0.3, 0.1]]
PERFORMER = [[0.2, -0.4, 1.1], [1.0, 0.0, 0.5], [0.3, 1.2, -0.7], [-0.5, 0.8, 0.0]]
LABELS = [2, 1, 2]  # input ids [0, 2, 1, 2] shifted by one


def scores(observer: list[list[float]], performer: list[list[float]]) -> dict[str, float]:
    return falcon_scores(
        torch.tensor(observer, dtype=torch.float64),
        torch.tensor(performer, dtype=torch.float64),
        torch.tensor(LABELS),
    )


class TestFalconScores:
    """Expected values from the reference code run on the same logits: Binoculars `metrics.py`
    and `detector.py` at ahans30/Binoculars c8ae2f90, `get_sampling_discrepancy_analytic` at
    baoguangsheng/fast-detect-gpt 971b0520."""

    def test_matches_the_reference_implementations(self):
        assert scores(OBSERVER, PERFORMER) == pytest.approx(
            {"binoculars": 0.9854137350915522, "fast-detectgpt": 0.48911178631951996}, rel=1e-12
        )

    def test_swapping_observer_and_performer_changes_both_scores(self):
        assert scores(PERFORMER, OBSERVER) == pytest.approx(
            {"binoculars": 0.6050029435704768, "fast-detectgpt": 1.8775865246217143}, rel=1e-12
        )
