import pytest
from scoring import DETECTORS, Text
from summarize import control_table, past_cutoff


def paired_texts(human: list[float], model: list[float]) -> tuple[list[Text], dict[str, dict]]:
    texts, scores = [], {}
    for arm, values in (("human", human), ("no-skill", model)):
        for index, value in enumerate(values):
            text = Text(f"bheijden/{arm}/t{index}", "bheijden", arm, f"t{index}", "r", 100, "p")
            texts.append(text)
            scores[text.id] = {"score": value}
    return texts, scores


@pytest.mark.parametrize(
    ("detector", "human_wins"),
    [("desklib", "3/4 | 0.30 to 0.95"), ("binoculars", "1/4 | 0.05 to 0.70")],
)
def test_human_less_ai_like_follows_the_detector_direction(detector, human_wins):
    texts, scores = paired_texts(human=[0.1, 0.2, 0.3, 0.9], model=[0.5, 0.6, 0.7, 0.8])
    row = control_table(DETECTORS[detector], texts, scores).splitlines()[-1]
    assert row == f"| no-skill | 4 | {human_wins} | -0.400 | -0.275 (-0.673 to 0.123) |"


@pytest.mark.parametrize(
    ("detector", "values", "flagged"),
    [
        ("binoculars", [0.80, 0.86, 0.90], "1/3"),
        ("gpttrace", [9.0, 9.5, 12.0], "2/3"),
        ("desklib", [-1.0, 1.0, 2.0], "2/3"),
        ("fast-detectgpt", [-1.0, 1.0, 2.0], "n/a"),
    ],
)
def test_past_cutoff_counts_on_the_detectors_ai_side(detector, values, flagged):
    assert past_cutoff(DETECTORS[detector], values) == flagged
