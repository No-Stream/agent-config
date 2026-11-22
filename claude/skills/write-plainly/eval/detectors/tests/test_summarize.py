import pytest
from scoring import DETECTORS, ChunkScore, Text, score_record, scores_file, text_sha256, write_jsonl
from summarize import (
    PLANTED_CONTRASTS,
    chunk_noise_line,
    contrast_table,
    overview_table,
    past_cutoff,
    provenance_table,
    spread_line,
    summary,
)

YEARS = {"t0": 1900, "t1": 1900, "t2": 2010, "t3": 2010}
PLANTED = {
    "skill-draft": [1.0, 2.0, 3.0],
    "neutral-rewrite": [1.5, 1.5, 3.5],
    "degraded": [3.0, 2.0, 6.0],
    "tells-injected": [2.0, 2.5, 3.5],
}
WORDS = {"skill-draft": 100, "neutral-rewrite": 100, "degraded": 120, "tells-injected": 105}


def bheijden_texts(arms: dict[str, list[float]]) -> tuple[list[Text], dict[str, dict]]:
    """One text per topic t0, t1, ... in each arm, scored as given, each one chunk."""
    texts, scores = [], {}
    for arm, values in arms.items():
        for index, value in enumerate(values):
            words = WORDS.get(arm, 100)
            text = Text(f"bheijden/{arm}/t{index}", "bheijden", arm, f"t{index}", "r", words, "p")
            texts.append(text)
            scores[text.id] = {"score": value, "chunk_scores": [value]}
    return texts, scores


class TestProvenanceTable:
    @pytest.mark.parametrize(
        ("detector", "human_less_ai_like"),
        [
            ("desklib", "3/4 | 0.30 to 0.95 | 2/2 | 1/2"),
            ("binoculars", "1/4 | 0.05 to 0.70 | 0/2 | 1/2"),
        ],
    )
    def test_human_less_ai_like_follows_the_detector_direction(self, detector, human_less_ai_like):
        texts, scores = bheijden_texts(
            {"human": [0.1, 0.2, 0.3, 0.9], "no-skill": [0.5, 0.6, 0.7, 0.8]}
        )
        row = provenance_table(DETECTORS[detector], texts, scores, YEARS).splitlines()[-1]
        assert row == f"| no-skill | 4 | {human_less_ai_like} | -0.400 | -0.275 (-0.673 to 0.123) |"

    def test_planted_arms_are_left_out(self):
        texts, scores = bheijden_texts({"human": [0.1, 0.2, 0.3], **PLANTED})
        rows = provenance_table(DETECTORS["gpttrace"], texts, scores, YEARS).splitlines()[2:]
        assert [row.split(" | ")[0] for row in rows] == ["| skill-draft"]


class TestContrastTable:
    def test_each_contrast_is_paired_by_topic_with_its_word_counts(self):
        texts, scores = bheijden_texts(PLANTED)
        rows = contrast_table(DETECTORS["gpttrace"], texts, scores, PLANTED_CONTRASTS).splitlines()[
            2:
        ]
        assert rows[0] == (
            "| degraded minus neutral-rewrite | 3 | 3/3 | 0.44 to 1.00 | 1.500 | "
            "1.500 (-0.984 to 3.984) | 1.000 | 120 / 100 |"
        )
        assert [row.split(" | ")[2] for row in rows] == ["3/3", "3/3", "2/3"]

    def test_more_ai_like_follows_the_detector_direction(self):
        texts, scores = bheijden_texts(PLANTED)
        rows = contrast_table(
            DETECTORS["binoculars"], texts, scores, PLANTED_CONTRASTS
        ).splitlines()[2:]
        assert [row.split(" | ")[2] for row in rows] == ["0/3", "0/3", "1/3"]

    def test_says_so_when_no_contrast_is_scored(self):
        texts, scores = bheijden_texts({"human": [0.1, 0.2], "no-skill": [0.5, 0.6]})
        assert contrast_table(DETECTORS["gpttrace"], texts, scores, PLANTED_CONTRASTS).startswith(
            "No topic"
        )


class TestOverviewTable:
    def test_overview_counts_each_check_and_marks_unscored_ones(self):
        texts, scores = bheijden_texts(
            {"human": [0.1, 0.2, 0.9], "corpus-claude-opus-5": [0.5, 0.6, 0.7], **PLANTED}
        )
        unplanted = {text_id: row for text_id, row in scores.items() if "corpus" in text_id}
        table = overview_table(texts, {"gpttrace": scores, "binoculars": unplanted}).splitlines()
        assert table[2] == "| gpttrace | 2/3 | 3/3 | 3/3 | 2/3 |"
        assert table[3] == "| binoculars | not scored | not scored | not scored | not scored |"


class TestSpread:
    def test_planted_and_human_arms_stay_out_of_the_model_spread(self):
        texts, scores = bheijden_texts(
            {"human": [0.0, 1.0], "no-skill": [1.0, 3.0], "degraded": [50.0, 90.0]}
        )
        line = spread_line(DETECTORS["gpttrace"], texts, scores)
        assert line.startswith(
            "Model-drafted texts, planted controls left out (n = 2): standard deviation 1.414,"
        )

    def test_chunk_noise_is_the_median_deviation_over_model_drafts_with_several_chunks(self):
        texts, scores = bheijden_texts(
            {"no-skill": [1.0, 2.0, 3.0, 4.0], "degraded": [9.0], "human": [5.0]}
        )
        chunks = ([1.0, 3.0], [0.0, 4.0, 8.0], [5.0, 5.0], [7.0], [0.0, 100.0], [0.0, 50.0])
        for text_id, chunk_scores in zip(scores, chunks, strict=True):
            scores[text_id]["chunk_scores"] = chunk_scores
        assert chunk_noise_line(texts, scores) == (
            "Median standard deviation between the chunks of one text, over the 3 model drafts "
            "outside the planted controls with two or more chunks: 1.414."
        )


class TestPastCutoff:
    @pytest.mark.parametrize(
        ("detector", "values", "flagged"),
        [
            ("binoculars", [0.80, 0.86, 0.90], "1/3"),
            ("gpttrace", [9.0, 9.5, 12.0], "2/3"),
            ("desklib", [-1.0, 1.0, 2.0], "2/3"),
            ("fast-detectgpt", [-1.0, 1.0, 2.0], "n/a"),
        ],
    )
    def test_past_cutoff_counts_on_the_detectors_ai_side(self, detector, values, flagged):
        assert past_cutoff(DETECTORS[detector], values) == flagged


class TestSummary:
    def test_a_score_of_an_earlier_version_of_a_text_is_left_out_and_counted_as_missing(
        self, tmp_path
    ):
        texts = [
            Text(f"bheijden/{arm}/{topic}", "bheijden", arm, topic, "r", 100, "p")
            for arm in ("human", "corpus-claude-opus-5")
            for topic in YEARS
        ]
        texts.append(Text("pairwise/merged/task-1", "pairwise", "merged", "task-1", "r", 250, "p"))
        prepared = {text.id: f"The words of {text.id}." for text in texts}
        detector = DETECTORS["binoculars"]
        records = [
            score_record(
                text.id,
                text_sha256("An earlier draft." if text.arm == "merged" else prepared[text.id]),
                detector,
                [ChunkScore(10, 0.1 * index**2)],
            )
            for index, text in enumerate(texts)
        ]
        write_jsonl(scores_file(tmp_path, detector.name), records)
        markdown = summary(texts, prepared, tmp_path, YEARS)
        assert "| pairwise | merged |" not in markdown
        assert "| bheijden | human | 4 |" in markdown
        assert (
            "8 of 9 texts have a current score; "
            "`heavy --light -- uv run sagemaker_job.py run` scores the rest."
        ) in markdown
