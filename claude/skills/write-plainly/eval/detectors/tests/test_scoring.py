import dataclasses
import json
import re
from itertools import pairwise

import pytest
from scoring import (
    DETECTORS,
    ChunkScore,
    Text,
    aggregate,
    chunk_encodings,
    chunk_spans,
    chunk_texts,
    prepare_text,
    read_manifest,
    require_scored,
    score_record,
    split_pending,
    text_sha256,
    write_manifest,
    write_scores,
)


def word_offsets(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in re.finditer(r"\S+", text)]


@dataclasses.dataclass
class WordTokenizer:
    """One token per word, `special` tokens around each encoding, and `extra` more on a chunk."""

    special: int
    extra: int = 0

    def __call__(
        self,
        text: str,
        add_special_tokens: bool = True,
        return_offsets_mapping: bool = False,
        return_tensors: str | None = None,
    ) -> dict:
        offsets = word_offsets(text)
        ids = list(range(len(offsets) + self.special * add_special_tokens))
        if return_tensors:
            return {"input_ids": [ids + list(range(self.extra))]}
        return {"input_ids": ids, "offset_mapping": offsets}


class TestChunkSpans:
    @pytest.mark.parametrize("n_tokens", [1, 7, 511, 512, 513, 1000, 1024, 1537])
    def test_fewest_contiguous_chunks_within_window_and_near_equal(self, n_tokens):
        window = 512
        spans = chunk_spans(n_tokens, window)
        assert spans[0][0] == 0 and spans[-1][1] == n_tokens
        assert all(end == start for (_, end), (start, _) in pairwise(spans))
        sizes = [end - start for start, end in spans]
        assert len(sizes) == -(-n_tokens // window)
        assert max(sizes) <= window and max(sizes) - min(sizes) <= 1

    def test_long_text_has_no_short_tail(self):
        assert [end - start for start, end in chunk_spans(1030, 512)] == [343, 343, 344]

    @pytest.mark.parametrize(("n_tokens", "window"), [(0, 512), (10, 0)])
    def test_rejects_empty_text_and_empty_window(self, n_tokens, window):
        with pytest.raises(ValueError):
            chunk_spans(n_tokens, window)


class TestChunkTexts:
    def test_chunks_cut_at_token_boundaries_and_cover_the_text(self):
        text = " ".join(f"word{index}" for index in range(10))
        chunks = chunk_texts(text, word_offsets(text), window=4)
        assert [size for _, size in chunks] == [3, 3, 4]
        assert [chunk for chunk, _ in chunks] == [
            "word0 word1 word2",
            "word3 word4 word5",
            "word6 word7 word8 word9",
        ]

    def test_short_text_is_one_chunk(self):
        text = "one short text"
        assert chunk_texts(text, word_offsets(text), window=512) == [(text, 3)]


class TestChunkEncodings:
    def test_chunks_leave_room_for_special_tokens_and_fill_the_window(self):
        text = " ".join(f"word{index}" for index in range(12))
        chunks = chunk_encodings(WordTokenizer(special=2), "t", text, window=6)
        assert [size for _, size in chunks] == [4, 4, 4]
        assert [len(encoding["input_ids"][0]) for encoding, _ in chunks] == [6, 6, 6]

    def test_a_chunk_that_tokenizes_past_the_window_is_refused(self):
        text = " ".join(f"word{index}" for index in range(8))
        with pytest.raises(ValueError, match="t-long"):
            chunk_encodings(WordTokenizer(special=2, extra=1), "t-long", text, window=6)


class TestAggregate:
    def test_token_weighted_mean_and_extremes(self):
        result = aggregate([ChunkScore(300, 2.0), ChunkScore(100, -2.0)])
        assert result["score"] == pytest.approx(1.0)
        assert (result["chunk_max"], result["chunk_min"], result["tokens"]) == (2.0, -2.0, 400)
        assert result["chunk_scores"] == [2.0, -2.0] and result["chunk_tokens"] == [300, 100]

    def test_no_chunks_is_an_error(self):
        with pytest.raises(ValueError):
            aggregate([])

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_a_non_finite_chunk_score_is_an_error(self, bad):
        with pytest.raises(ValueError):
            aggregate([ChunkScore(3, 1.0), ChunkScore(3, bad)])


class TestPrepareText:
    def test_strips_markdown_and_tables_and_folds_typography(self):
        markdown = (
            "# Results\n\n"
            "| arm | AUC |\n| :-- | :-- |\n| base | .99 |\n\n"
            "The **new** model “wins” … see [the doc](https://x.y) and `fit()`.\n\n\n"
            "- first point\n1. second point\n"
            "It’s *fine* now — mostly."
        )
        assert prepare_text(markdown) == (
            "Results\n\n"
            'The new model "wins" ... see the doc and fit().\n\n'
            "first point\nsecond point\n"
            "It's fine now — mostly."
        )

    def test_leaves_multiplication_and_snake_case_alone(self):
        assert prepare_text("a * b and c * d in my_var_name") == "a * b and c * d in my_var_name"

    def test_drops_invisible_format_characters(self):
        assert prepare_text("zero\u200bwidth soft\u00adhyphen") == "zerowidth softhyphen"


def make_text(text_id: str) -> Text:
    return Text(text_id, "bheijden", "human", "t", "academic", 3, f"{text_id}.txt")


class TestManifestFile:
    def test_round_trip(self, tmp_path):
        texts = [make_text("a"), make_text("b")]
        write_manifest(tmp_path / "m.jsonl", texts)
        assert read_manifest(tmp_path / "m.jsonl") == texts

    def test_duplicate_ids_are_refused(self, tmp_path):
        with pytest.raises(ValueError):
            write_manifest(tmp_path / "m.jsonl", [make_text("a"), make_text("a")])

    def test_unknown_fields_are_refused(self, tmp_path):
        row = {**dataclasses.asdict(make_text("a")), "extra": 1}
        (tmp_path / "m.jsonl").write_text(json.dumps(row) + "\n")
        with pytest.raises(ValueError):
            read_manifest(tmp_path / "m.jsonl")


class TestRescoring:
    @pytest.mark.parametrize("change", [{"window": 512}, {"revision": "0" * 40}])
    def test_only_new_or_changed_texts_or_a_changed_detector_are_rescored(self, tmp_path, change):
        detector = DETECTORS["desklib"]
        scores_file = tmp_path / "desklib.jsonl"
        old = {"same": "unchanged text", "edited": "old text", "gone": "removed text"}
        records = {
            text_id: score_record(text_id, text_sha256(text), detector, [ChunkScore(3, 1.0)])
            for text_id, text in old.items()
        }
        write_scores(scores_file, old, records)
        now = {"same": "unchanged text", "edited": "new text", "added": "brand new text"}
        kept, pending = split_pending(now, scores_file, detector)
        assert set(kept) == {"same"} and set(pending) == {"edited", "added"}

        _, pending = split_pending(now, scores_file, dataclasses.replace(detector, **change))
        assert set(pending) == set(now)

    def test_write_scores_keeps_manifest_order_and_reports_unscored(self, tmp_path):
        records = {"b": {"id": "b"}, "a": {"id": "a"}, "gone": {"id": "gone"}}
        unscored = write_scores(tmp_path / "s.jsonl", ["a", "b", "c"], records)
        rows = [json.loads(line) for line in (tmp_path / "s.jsonl").read_text().splitlines()]
        assert [row["id"] for row in rows] == ["a", "b"] and unscored == ["c"]


class TestRequireScored:
    def test_names_every_detector_with_unscored_texts(self):
        with pytest.raises(RuntimeError, match="binoculars.*fast-detectgpt"):
            require_scored({"binoculars": ["a"], "fast-detectgpt": ["a", "b"]}, "job-1")

    def test_passes_when_every_text_is_scored(self):
        require_scored({"binoculars": [], "fast-detectgpt": []}, "job-1")
