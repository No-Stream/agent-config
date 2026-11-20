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
    chunk_spans,
    chunk_texts,
    prepare_text,
    read_manifest,
    score_record,
    split_pending,
    text_sha256,
    write_manifest,
    write_scores,
)


def word_offsets(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in re.finditer(r"\S+", text)]


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


class TestAggregate:
    def test_token_weighted_mean_and_extremes(self):
        result = aggregate([ChunkScore(300, 2.0), ChunkScore(100, -2.0)])
        assert result["score"] == pytest.approx(1.0)
        assert (result["chunk_max"], result["chunk_min"], result["tokens"]) == (2.0, -2.0, 400)
        assert result["chunk_scores"] == [2.0, -2.0] and result["chunk_tokens"] == [300, 100]

    def test_no_chunks_is_an_error(self):
        with pytest.raises(ValueError):
            aggregate([])


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
        write_manifest(texts, tmp_path / "m.jsonl")
        assert read_manifest(tmp_path / "m.jsonl") == texts

    def test_duplicate_ids_are_refused(self, tmp_path):
        with pytest.raises(ValueError):
            write_manifest([make_text("a"), make_text("a")], tmp_path / "m.jsonl")

    def test_unknown_fields_are_refused(self, tmp_path):
        row = {**make_text("a").__dict__, "extra": 1}
        (tmp_path / "m.jsonl").write_text(json.dumps(row) + "\n")
        with pytest.raises(ValueError, match="fields"):
            read_manifest(tmp_path / "m.jsonl")


class TestRescoring:
    def test_only_new_or_changed_texts_or_a_changed_window_are_rescored(self, tmp_path):
        detector = DETECTORS["desklib"]
        scores_file = tmp_path / "desklib.jsonl"
        old = {"same": "unchanged text", "edited": "old text", "gone": "removed text"}
        records = {
            text_id: score_record(
                text_id, text_sha256(text), detector.name, detector.window, [ChunkScore(3, 1.0)]
            )
            for text_id, text in old.items()
        }
        write_scores(scores_file, old, records)
        now = {"same": "unchanged text", "edited": "new text", "added": "brand new text"}
        kept, pending = split_pending(now, scores_file, detector)
        assert set(kept) == {"same"} and set(pending) == {"edited", "added"}

        rewindowed = dataclasses.replace(detector, window=512)
        _, pending = split_pending(now, scores_file, rewindowed)
        assert set(pending) == set(now)

    def test_write_scores_keeps_manifest_order_and_reports_unscored(self, tmp_path):
        records = {"b": {"id": "b"}, "a": {"id": "a"}, "gone": {"id": "gone"}}
        unscored = write_scores(tmp_path / "s.jsonl", ["a", "b", "c"], records)
        rows = [json.loads(line) for line in (tmp_path / "s.jsonl").read_text().splitlines()]
        assert [row["id"] for row in rows] == ["a", "b"] and unscored == ["c"]
