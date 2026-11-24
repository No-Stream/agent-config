import argparse
import json

import pytest

import measure
from bigrams import count_reference
from measure import (
    AFTER_HYPHEN_BITS,
    ASSOCIATION_BITS,
    HYPHEN_BITS,
    THRESHOLDS,
    Document,
    adjusted_bits,
    all_flags,
    document_flags,
    find_target,
    flag_rates,
    full_reference,
    read_documents,
    read_jsonl,
    recall_rows,
    score,
    scores_path,
    sha256,
    write_jsonl,
)
from prose import Span, content_pairs, plain_text, tokens

WIKITEXT_ROWS = [
    " = Harbour = \n",
    " The calm harbour shelters the fishing fleet , and the harbour seal hauls out . \n",
    " = Basalt = \n",
    " Basalt cools into columns on rocky shores . \n",
]


def document(document_id: str, markdown: str) -> Document:
    corpus, arm, _ = document_id.split("/")
    return Document(document_id, corpus, arm, len(markdown.split()), plain_text(markdown))


def scored_row(document_id: str, text: str) -> dict:
    """A `score` row for the text, with one score per word and per content pair."""
    words = tokens(text)
    pairs = [0.0] * len(content_pairs(words))
    return {
        "id": document_id,
        "sha256": sha256(text),
        "bits": [0.0] * len(words),
        "association": pairs,
        "after_first": pairs,
        "joiner": pairs,
    }


@pytest.fixture
def manifest(tmp_path):
    texts = {
        "human/a": "The harbour seal hauls out on rocky shores.\n",
        "human/b": "Basalt cools into columns.\n\n```\ncode words here\n```\n",
        "model/c": "The tide-pool budget verified red against the shore.\n",
    }
    rows = []
    for name, text in texts.items():
        path = tmp_path / f"{name.replace('/', '-')}.md"
        path.write_text(text)
        arm, doc = name.split("/")
        rows.append({"corpus": "public", "arm": arm, "doc": doc, "path": str(path)})
    manifest_path = tmp_path / "manifest.jsonl"
    manifest_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return manifest_path


class TestReadDocuments:
    def test_reads_rows_with_ids_word_counts_and_plain_text(self, manifest):
        documents = read_documents([manifest], include=None)
        assert [document.id for document in documents] == [
            "public/human/a",
            "public/human/b",
            "public/model/c",
        ]
        assert documents[1].file_words == 7
        assert documents[1].plain.words == 4

    def test_include_keeps_only_the_named_arms(self, manifest):
        documents = read_documents([manifest], include={"public/model"})
        assert [document.id for document in documents] == ["public/model/c"]


class TestScore:
    def test_scoring_one_group_keeps_the_other_groups_rows_and_drops_only_stale_ones(
        self, manifest, tmp_path
    ):
        texts = {document.id: document.plain.text for document in read_documents([manifest], None)}
        other_group = {"id": "public/model/c", "sha256": sha256(texts["public/model/c"])}
        current = scored_row("public/human/a", texts["public/human/a"])
        stale = scored_row("public/human/b", texts["public/human/b"])
        path = scores_path(tmp_path / "out", "org/model")
        write_jsonl(path, [other_group, current, stale])
        (tmp_path / "human-b.md").write_text("```\ncode only\n```\n")
        score(self.arguments(manifest, path))
        assert read_jsonl(path) == [other_group, current]

    def test_a_row_whose_scores_no_longer_match_the_texts_words_is_dropped(
        self, manifest, tmp_path
    ):
        texts = {document.id: document.plain.text for document in read_documents([manifest], None)}
        current = scored_row("public/human/a", texts["public/human/a"])
        (tmp_path / "human-b.md").write_text("```\ncode only\n```\n")
        earlier_words = dict(scored_row("public/human/b", ""), bits=[5.0])
        path = scores_path(tmp_path / "out", "org/model")
        write_jsonl(path, [current, earlier_words])
        score(self.arguments(manifest, path))
        assert read_jsonl(path) == [current]

    @staticmethod
    def arguments(manifest, path) -> argparse.Namespace:
        return argparse.Namespace(
            manifest=[manifest],
            include=["public/human"],
            model="org/model",
            out=path.parent,
            workers=1,
        )


class TestFullReference:
    def test_counts_once_reuses_the_cache_and_recounts_when_the_documents_need_more(
        self, manifest, tmp_path, monkeypatch
    ):
        documents = read_documents([manifest], None)
        cache = tmp_path / "reference-full.json"
        monkeypatch.setattr(measure, "wikitext_rows", lambda: iter(WIKITEXT_ROWS))
        cold, _ = full_reference(documents, cache)
        assert cold.words["harbour"] == 2 and ("rocky", "shores") in cold.pairs
        assert (cold.total_words, cold.distinct_words) == (20, 17)

        def unavailable():
            raise AssertionError("the cached counts cover these documents")

        monkeypatch.setattr(measure, "wikitext_rows", unavailable)
        cached, _ = full_reference(documents, cache)
        assert cached == cold
        monkeypatch.setattr(measure, "wikitext_rows", lambda: iter(WIKITEXT_ROWS))
        grown = [*documents, document("public/model/d", "The fishing fleet sails.\n")]
        recounted, _ = full_reference(grown, cache)
        assert recounted.words["fleet"] == 1 and ("fishing", "fleet") in recounted.pairs
        assert "fleet" not in cold.words


class TestAdjustedBits:
    def test_subtracts_each_words_unigram_bits(self):
        words = tokens("calm harbour")
        full = count_reference(["calm harbour"])
        assert adjusted_bits(words, [3.0, 5.0], full) == pytest.approx([2.0, 4.0])


class TestRecallRows:
    def test_a_flag_finds_a_target_it_overlaps_but_not_one_it_only_touches(self):
        documents = {
            "public/model/a": document(
                "public/model/a", "The gear trap sat by the tide pool near a calm harbour.\n"
            ),
            "public/model/b": document("public/model/b", "Seals rest on the rocky shore.\n"),
        }
        first = documents["public/model/a"].plain.text
        second = documents["public/model/b"].plain.text
        targets = [
            {"id": "public/model/a", "phrase": "gear trap", "kind": "paper"},
            {"id": "public/model/a", "phrase": "tide pool", "kind": "paper"},
            {"id": "public/model/a", "phrase": "calm harbour", "kind": "owner"},
            {"id": "public/model/b", "phrase": "rocky shore", "kind": "owner"},
        ]
        trap_sat = Span(first.index("trap"), first.index(" by"))
        before_tide = Span(first.index("by"), first.index("tide"))
        after_tide = Span(first.index(" near"), first.index("near") + 4)
        flags = {
            "found": {
                "public/model/a": [trap_sat, before_tide, after_tide],
                "public/model/b": [Span(second.index("the"), len(second))],
            },
            "silent": {"public/model/a": [], "public/model/b": []},
        }
        rows = {
            (row["variant"], row["kind"]): (row["targets"], row["hits"], row["phrases"])
            for row in recall_rows(flags, targets, documents)
        }
        assert rows == {
            ("found", "owner"): (2, 1, "rocky shore"),
            ("found", "paper"): (2, 1, "gear trap"),
            ("silent", "owner"): (2, 0, ""),
            ("silent", "paper"): (2, 0, ""),
        }


class TestAllFlags:
    TEXT = "The harbour seal hauls out on rocky shores.\n"

    @pytest.fixture
    def counts(self):
        return count_reference(["The harbour seal hauls out on rocky shores at low tide."])

    def test_scores_of_an_earlier_text_are_refused(self, counts):
        current = document("public/human/a", self.TEXT)
        words = tokens(current.plain.text)
        stale = {
            "id": current.id,
            "sha256": sha256("The harbour seal hauled out on rocky shores."),
            "bits": [5.0] * len(words),
            "association": [1.0] * len(content_pairs(words)),
        }
        with pytest.raises(ValueError):
            all_flags([current], {current.id: stale}, counts, counts)

    def test_a_document_with_prose_and_no_scores_is_refused(self, counts):
        with pytest.raises(ValueError):
            all_flags([document("public/human/a", self.TEXT)], {}, counts, counts)


class TestFindTarget:
    def test_finds_a_phrase_case_insensitively(self):
        text = "The Gear trap sat idle."
        assert find_target(text, "gear trap") == Span(4, 13)

    def test_a_missing_phrase_is_an_error(self):
        with pytest.raises(ValueError):
            find_target("The gear sat idle.", "gear trap")


class TestFlagRates:
    def test_rates_per_thousand_file_words_by_arm_and_pool(self, manifest):
        documents = read_documents([manifest], include=None)
        flags = {"public/human/a": [Span(0, 3)], "public/model/c": [Span(0, 3), Span(4, 8)]}
        rows = flag_rates(documents, flags, pools={"all human": {"public/human"}})
        by_group = {row["group"]: row for row in rows}
        assert by_group["public/human"]["flags"] == 1
        assert by_group["public/human"]["file_words"] == 15
        assert by_group["public/human"]["per_1000_words"] == pytest.approx(1000 / 15)
        assert by_group["public/human"]["docs_flagged"] == "1/2"
        assert by_group["public/model"]["flags"] == 2
        assert by_group["all human"]["flags"] == 1


class TestDocumentFlags:
    REFERENCE = ("The harbour seal hauls out on rocky shores at low tide every day.",)

    @pytest.mark.parametrize("repeats", [1, 13])
    def test_every_variant_runs_above_and_below_the_content_word_floor(self, repeats):
        text = " ".join(["The rocky shores held a gear trap."] * repeats)
        words = tokens(text)
        pairs = content_pairs(words)
        counts = count_reference(self.REFERENCE)
        scored = {
            "bits": [5.0 + (i % 7) + 20.0 * (word.text == "trap") for i, word in enumerate(words)],
            "association": [
                float(i % 5) + 15.0 * (words[r].text == "trap") for i, (_, r) in enumerate(pairs)
            ],
            "after_first": [1.0] * len(pairs),
            "joiner": [1.0] * len(pairs),
        }
        flags = document_flags(text, words, scored, counts, counts)
        hyphen_variants = len(HYPHEN_BITS) + len(AFTER_HYPHEN_BITS)
        assert len(flags) == 2 + 6 * len(THRESHOLDS) + len(ASSOCIATION_BITS) + hyphen_variants
        unattested = {text[span.start : span.end] for span in flags["unattested-500k"]}
        assert "rocky shores" not in unattested
        assert flags["unattested-500k"] == flags["unattested-full"]
        assert {text[span.start : span.end] for span in flags["association-bits12.0"]} == {
            "gear trap"
        }

    def test_the_unigram_adjustment_moves_the_flag_from_a_rare_word_to_a_common_one(self):
        text = (
            "Calm harbour waters shelter fishing boats, rocky shores guard quiet coves, and old "
            "lighthouse keepers count passing ships near the gear trap beside a blue glacier "
            "under grey northern skies."
        )
        words = tokens(text)
        ordinary = [word.text for word in words if word.text not in {"trap", "glacier"}]
        full = count_reference([" ".join(ordinary), "Trap, trap, trap, trap."])
        special = {"trap": 10.0, "glacier": 11.0}
        bits = [special.get(word.text, 4.0 + index % 5) for index, word in enumerate(words)]
        zeros = [0.0] * len(content_pairs(words))
        scored = {"bits": bits, "association": zeros, "after_first": zeros, "joiner": zeros}
        flags = document_flags(text, words, scored, full, full)

        def phrases(variant: str) -> list[str]:
            return [text[span.start : span.end] for span in flags[variant]]

        assert phrases("surprisal-raw-words-z3.0") == ["blue glacier"]
        assert phrases("surprisal-raw-pairs-z3.0") == ["blue glacier"]
        assert phrases("surprisal-adjusted-words-z3.0") == ["gear trap"]
        assert phrases("surprisal-adjusted-pairs-z3.0") == ["gear trap"]
        assert phrases("unattested-full-and-adjusted-z3.0") == ["gear trap"]

    def test_the_hyphen_checks_read_only_hyphen_joined_pairs_above_their_threshold(self):
        text = "The rocky shores held a gear trap and a tide-pool net."
        words = tokens(text)
        pairs = content_pairs(words)
        counts = count_reference(self.REFERENCE)
        high = [100.0] * len(pairs)
        scored = {"bits": [5.0] * len(words), "association": high, "after_first": high}

        def phrases(joiner: float) -> dict[str, list[str]]:
            flags = document_flags(
                text, words, dict(scored, joiner=[joiner] * len(pairs)), counts, counts
            )
            return {
                variant: [text[span.start : span.end] for span in spans]
                for variant, spans in flags.items()
                if "hyphen" in variant
            }

        top = f"hyphen-bits{HYPHEN_BITS[-1]}"
        assert phrases(HYPHEN_BITS[-1] + 1)[top] == ["tide-pool"]
        assert phrases(HYPHEN_BITS[-1] - 1)[top] == []
        assert phrases(0.0)[f"after-hyphen-bits{AFTER_HYPHEN_BITS[-1]}"] == ["tide-pool"]

    def test_a_document_without_prose_gets_only_the_reference_checks(self):
        counts = count_reference(self.REFERENCE)
        assert set(document_flags("", [], None, counts, counts)) == {
            "unattested-500k",
            "unattested-full",
        }
