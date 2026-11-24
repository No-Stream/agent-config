#!/usr/bin/env -S uv run --upgrade --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "torch>=2.9",
#   "transformers>=5.23",
#   "huggingface-hub>=1.0",
#   "pyarrow",
# ]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Measure the unattested-bigram and surprisal-hotspot checks on manifests of documents.

`reference` writes the 500,000-word WikiText-103 sample; `score` writes every document's word
surprisals under one model; `analyze` writes flag rates per 1,000 words, recall on known phrases,
every flag with its sentence, and the CPU cost of each check. A manifest is JSONL with `corpus`,
`arm`, `doc` and `path` fields; a document's id is `corpus/arm/doc`.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import logging
import multiprocessing
import os
import time
from collections.abc import Iterable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as pq
import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

from bigrams import (
    ReferenceCounts,
    count_reference,
    document_pairs,
    document_words,
    unattested_phrases,
)
from prose import (
    WORD,
    PlainText,
    Span,
    Token,
    content_pairs,
    merge_spans,
    pair_key,
    plain_text,
    tokens,
)
from reference import (
    SAMPLE_FILE,
    SAMPLE_SEED,
    SAMPLE_WORDS,
    WIKITEXT_REPO,
    WIKITEXT_TRAIN_FILES,
    read_paragraphs,
    sample_paragraphs,
    wikitext_articles,
    write_sample,
)
from surprisal import (
    content_z,
    hotspots,
    robust_z,
    slot_terms,
    token_surprisals,
    word_bits,
)

logger: logging.Logger = logging.getLogger(__name__)

WINDOW = 1024
STRIDE = 512
MIN_CONTENT_WORDS = 25
THRESHOLDS = (2.5, 3.0, 3.5, 4.0, 5.0, 6.0)
ASSOCIATION_BITS = (6.0, 8.0, 10.0, 12.0, 14.0, 16.0)
HYPHEN_BITS = (4.0, 6.0, 8.0, 10.0, 12.0)
AFTER_HYPHEN_BITS = (8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0)
CONTEXT_CHARACTERS = 160


@dataclass(frozen=True)
class Document:
    id: str
    corpus: str
    arm: str
    file_words: int
    plain: PlainText

    @property
    def group(self) -> str:
        return f"{self.corpus}/{self.arm}"


def read_documents(manifests: Sequence[Path], include: set[str] | None) -> list[Document]:
    documents = []
    for manifest in manifests:
        for line in manifest.read_text().splitlines():
            row = json.loads(line)
            if include is not None and f"{row['corpus']}/{row['arm']}" not in include:
                continue
            markdown = Path(row["path"]).read_text()
            documents.append(
                Document(
                    id=f"{row['corpus']}/{row['arm']}/{row['doc']}",
                    corpus=row["corpus"],
                    arm=row["arm"],
                    file_words=len(WORD.findall(markdown)),
                    plain=plain_text(markdown),
                )
            )
    ids = [document.id for document in documents]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate document ids in {manifests}")
    return documents


def find_target(text: str, phrase: str) -> Span:
    start = text.lower().find(phrase.lower())
    if start < 0:
        raise ValueError(f"target {phrase!r} is not in the document's plain text")
    return Span(start, start + len(phrase))


def overlaps(target: Span, spans: Iterable[Span]) -> bool:
    return any(span.start < target.end and target.start < span.end for span in spans)


def flag_rates(
    documents: Sequence[Document], flags: dict[str, list[Span]], pools: dict[str, set[str]]
) -> list[dict]:
    """Flags per 1,000 words (counted over the whole file, as the house-rule tables count them)
    for each corpus and arm, and for each named pool of them."""
    groups = {document.group: {document.group} for document in documents} | pools
    rows = []
    for name, members in groups.items():
        chosen = [document for document in documents if document.group in members]
        counts = [len(flags.get(document.id, [])) for document in chosen]
        file_words = sum(document.file_words for document in chosen)
        rows.append(
            {
                "group": name,
                "docs": len(chosen),
                "file_words": file_words,
                "prose_words": sum(document.plain.words for document in chosen),
                "flags": sum(counts),
                "per_1000_words": 1000 * sum(counts) / file_words,
                "docs_flagged": f"{sum(count > 0 for count in counts)}/{len(chosen)}",
            }
        )
    return rows


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def write_tsv(path: Path, rows: Sequence[dict]) -> None:
    columns = list(rows[0])
    lines = ["\t".join(columns)]
    lines += [
        "\t".join(
            f"{row[column]:.3f}" if isinstance(row[column], float) else str(row[column])
            for column in columns
        )
        for row in rows
    ]
    path.write_text("\n".join(lines) + "\n")


def wikitext_rows() -> Iterator[str]:
    """Every row of the WikiText-103 raw train split, from its latest revision on the Hub."""
    for filename in WIKITEXT_TRAIN_FILES:
        path = hf_hub_download(WIKITEXT_REPO, filename, repo_type="dataset")
        with pq.ParquetFile(path) as parquet:
            for batch in parquet.iter_batches(columns=["text"]):
                yield from batch.column("text").to_pylist()


def build_sample(_: argparse.Namespace) -> None:
    articles = list(wikitext_articles(wikitext_rows()))
    sample = sample_paragraphs(articles, SAMPLE_WORDS, SAMPLE_SEED)
    write_sample(SAMPLE_FILE, sample)
    words = sum(len(WORD.findall(paragraph)) for paragraph in sample)
    logger.info(f"wrote {len(sample)} paragraphs of {len(articles)} articles, {words} words")


@functools.cache
def _loaded(model_name: str):
    """The tokenizer and model, once per worker process, at their latest Hub revision, in
    bfloat16, about twice as fast on the CPU as float32."""
    torch.set_num_threads(1)
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, dtype=torch.bfloat16)
    return tokenizer, model.eval()


def _score_one(item: tuple[str, str, str]) -> dict:
    model_name, document_id, text = item
    tokenizer, model = _loaded(model_name)
    started = time.process_time()
    words = tokens(text)
    scores = token_surprisals(text, tokenizer, model, window=WINDOW, stride=STRIDE)
    bits = word_bits(text, words, scores)
    surprisal_seconds = time.process_time() - started
    terms = slot_terms(
        text, words, content_pairs(words), tokenizer, model, window=WINDOW, stride=STRIDE
    )
    return {
        "id": document_id,
        "sha256": sha256(text),
        "bits": [round(value, 4) for value in bits],
        "association": [round(pair.association, 4) for pair in terms],
        "after_first": [round(pair.after_first, 4) for pair in terms],
        "joiner": [round(pair.joiner, 4) for pair in terms],
        "model_tokens": len(scores),
        "cpu_seconds": surprisal_seconds,
        "association_cpu_seconds": time.process_time() - started - surprisal_seconds,
    }


def scores_path(out: Path, model_name: str) -> Path:
    return out / f"scores-{model_name.replace('/', '--')}.jsonl"


def fits(row: dict, text: str) -> bool:
    """Whether a cached `score` row still scores this text: the same text, and one score for each
    of its words and content pairs, which a change to the word rule alone can move."""
    words = tokens(text)
    return (
        row["sha256"] == sha256(text)
        and len(row["bits"]) == len(words)
        and len(row["association"]) == len(content_pairs(words))
    )


def score(args: argparse.Namespace) -> None:
    documents = read_documents(args.manifest, set(args.include) if args.include else None)
    path = scores_path(args.out, args.model)
    kept = {row["id"]: row for row in read_jsonl(path)} if path.exists() else {}
    wanted = {document.id: document.plain.text for document in documents}
    kept = {key: row for key, row in kept.items() if key not in wanted or fits(row, wanted[key])}
    pending = [(args.model, key, text) for key, text in wanted.items() if key not in kept and text]
    logger.info(f"{args.model}: {len(kept)} documents already scored, {len(pending)} to score")
    pending.sort(key=lambda item: -len(item[2]))
    spawn = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(args.workers, mp_context=spawn) as pool:
        for index, row in enumerate(pool.map(_score_one, pending), 1):
            kept[row["id"]] = row
            logger.info(f"{index}/{len(pending)} {row['id']}: {row['cpu_seconds']:.1f} s")
            if index % 20 == 0:
                write_jsonl(path, kept.values())
    write_jsonl(path, kept.values())


def full_reference(documents: Sequence[Document], cache: Path) -> tuple[ReferenceCounts, float]:
    """Counts of the documents' pairs and words in the whole train split, cached by those wants."""
    found = [tokens(document.plain.text) for document in documents]
    wanted_pairs = set().union(*(document_pairs(words) for words in found))
    wanted_words = set().union(*(document_words(words) for words in found))
    if cache.exists():
        cached = json.loads(cache.read_text())
        if wanted_pairs <= {tuple(pair) for pair in cached["wanted_pairs"]} and wanted_words <= set(
            cached["wanted_words"]
        ):
            counts = ReferenceCounts(
                pairs={tuple(pair) for pair in cached["pairs"]},
                total_words=cached["total_words"],
                distinct_words=cached["distinct_words"],
                distinct_pairs=cached["distinct_pairs"],
            )
            counts.words.update(cached["words"])
            return counts, cached["cpu_seconds"]
    started = time.process_time()
    paragraphs = (
        paragraph for article in wikitext_articles(wikitext_rows()) for paragraph in article
    )
    counts = count_reference(paragraphs, wanted_pairs, wanted_words)
    cpu_seconds = time.process_time() - started
    cache.write_text(
        json.dumps(
            {
                "wanted_pairs": sorted(wanted_pairs),
                "wanted_words": sorted(wanted_words),
                "pairs": sorted(counts.pairs),
                "words": dict(counts.words),
                "total_words": counts.total_words,
                "distinct_words": counts.distinct_words,
                "distinct_pairs": counts.distinct_pairs,
                "cpu_seconds": cpu_seconds,
            }
        )
    )
    return counts, cpu_seconds


def adjusted_bits(
    words: Sequence[Token], bits: Sequence[float], full: ReferenceCounts
) -> list[float]:
    """Each word's surprisal in context less its unigram surprisal in the reference."""
    return [value - full.unigram_bits(word.text) for word, value in zip(words, bits, strict=True)]


def document_flags(
    text: str,
    words: Sequence[Token],
    scored: dict | None,
    sample: ReferenceCounts,
    full: ReferenceCounts,
) -> dict[str, list[Span]]:
    """Every variant's flags for one document, whose plain text is `text` and word tokens
    `words`; `scored` is its row from `score`, or None for a document with no prose. The hyphen
    variants read only hyphen-joined pairs: the hyphen's own bits after the first word, and the
    second word's bits after the first word and the hyphen."""
    flags = {
        "unattested-500k": unattested_phrases(words, sample.pairs),
        "unattested-full": unattested_phrases(words, full.pairs),
    }
    if scored is None:
        return flags
    pairs = content_pairs(words)
    unattested = [
        pair for pair in pairs if pair_key(*(words[i].text for i in pair)) not in full.pairs
    ]
    adjusted = adjusted_bits(words, scored["bits"], full)
    adjusted_z = content_z(words, adjusted, min_content_words=MIN_CONTENT_WORDS)
    association = dict(zip(pairs, scored["association"], strict=True))
    association_z = (
        dict(zip(pairs, robust_z(list(association.values())), strict=True))
        if len(pairs) >= MIN_CONTENT_WORDS
        else {}
    )
    for threshold in THRESHOLDS:
        for name, scores in (("raw", scored["bits"]), ("adjusted", adjusted)):
            for unit, pairs_only in (("pairs", True), ("words", False)):
                flags[f"surprisal-{name}-{unit}-z{threshold}"] = hotspots(
                    words,
                    scores,
                    threshold=threshold,
                    min_content_words=MIN_CONTENT_WORDS,
                    pairs_only=pairs_only,
                )
        both = [pair for pair in unattested if adjusted_z.get(pair[1], 0.0) > threshold]
        flags[f"unattested-full-and-adjusted-z{threshold}"] = merge_spans(words, both)
        flags[f"association-z{threshold}"] = merge_spans(
            words, [pair for pair in pairs if association_z.get(pair, 0.0) > threshold]
        )
    for bits in ASSOCIATION_BITS:
        flags[f"association-bits{bits}"] = merge_spans(
            words, [pair for pair in pairs if association[pair] > bits]
        )
    hyphened = [
        (pair, joiner, after)
        for pair, joiner, after in zip(pairs, scored["joiner"], scored["after_first"], strict=True)
        if text[words[pair[0]].end : words[pair[1]].start] == "-"
    ]
    for bits in HYPHEN_BITS:
        flags[f"hyphen-bits{bits}"] = merge_spans(
            words, [pair for pair, joiner, _ in hyphened if joiner > bits]
        )
    for bits in AFTER_HYPHEN_BITS:
        flags[f"after-hyphen-bits{bits}"] = merge_spans(
            words, [pair for pair, _, after in hyphened if after > bits]
        )
    return flags


def sentence_around(text: str, span: Span) -> str:
    start = max(0, span.start - CONTEXT_CHARACTERS)
    end = min(len(text), span.end + CONTEXT_CHARACTERS)
    window = (
        text[start : span.start] + "[[" + text[span.start : span.end] + "]]" + text[span.end : end]
    )
    return " ".join(window.split())


def recall_rows(
    flags: dict[str, dict[str, list[Span]]], targets: Sequence[dict], by_id: dict[str, Document]
) -> list[dict]:
    """For each variant and kind of target, how many target phrases a flag overlaps."""
    rows = []
    for variant, by_document in flags.items():
        for kind in sorted({target["kind"] for target in targets}):
            chosen = [target for target in targets if target["kind"] == kind]
            hits = [
                target["phrase"]
                for target in chosen
                if overlaps(
                    find_target(by_id[target["id"]].plain.text, target["phrase"]),
                    by_document[target["id"]],
                )
            ]
            rows.append(
                {
                    "variant": variant,
                    "kind": kind,
                    "targets": len(chosen),
                    "hits": len(hits),
                    "phrases": "; ".join(hits),
                }
            )
    return rows


def write_flags(
    out: Path, flags: dict[str, dict[str, list[Span]]], by_id: dict[str, Document]
) -> None:
    for variant, by_document in flags.items():
        write_jsonl(
            out / "flags" / f"{variant}.jsonl",
            (
                {
                    "id": document_id,
                    "group": by_id[document_id].group,
                    "phrase": by_id[document_id].plain.text[span.start : span.end],
                    "context": sentence_around(by_id[document_id].plain.text, span),
                }
                for document_id, spans in by_document.items()
                for span in spans
            ),
        )


def cost_row(step: str, cpu_seconds: float, words: int, *, per_1000_words: bool) -> dict:
    return {
        "step": step,
        "cpu_seconds": cpu_seconds,
        "words": words,
        "cpu_seconds_per_1000_words": 1000 * cpu_seconds / words if per_1000_words else "",
    }


def all_flags(
    documents: Sequence[Document],
    scored: dict[str, dict],
    sample: ReferenceCounts,
    full: ReferenceCounts,
) -> tuple[dict[str, dict[str, list[Span]]], float]:
    """Every variant's flags by document, and the CPU seconds of the full-reference lookups."""
    flags: dict[str, dict[str, list[Span]]] = {}
    lookup_seconds = 0.0
    for document in documents:
        words = tokens(document.plain.text)
        row = scored.get(document.id)
        if row is not None and row["sha256"] != sha256(document.plain.text):
            raise ValueError(f"{document.id}: scored text differs; rerun `score`")
        if row is None and document.plain.text:
            raise ValueError(f"{document.id}: no surprisal scores; run `score` first")
        started = time.process_time()
        unattested_phrases(words, full.pairs)
        lookup_seconds += time.process_time() - started
        for variant, spans in document_flags(document.plain.text, words, row, sample, full).items():
            flags.setdefault(variant, {})[document.id] = spans
    return flags, lookup_seconds


def analyze(args: argparse.Namespace) -> None:
    documents = read_documents(args.manifest, set(args.include) if args.include else None)
    by_id = {document.id: document for document in documents}
    pools = {
        name: set(members.split(","))
        for name, members in (pool.split("=", 1) for pool in args.pool or [])
    }
    scored = {row["id"]: row for row in read_jsonl(scores_path(args.out, args.model))}
    started = time.process_time()
    sample = count_reference(read_paragraphs(SAMPLE_FILE))
    sample_seconds = time.process_time() - started
    full, full_seconds = full_reference(documents, args.out / "reference-full.json")
    flags, lookup_seconds = all_flags(documents, scored, sample, full)
    rate_rows = [
        {"variant": variant, **rate}
        for variant, by_document in flags.items()
        for rate in flag_rates(documents, by_document, pools)
    ]
    write_tsv(args.out / "rates.tsv", rate_rows)
    if args.targets:
        targets = [row for path in args.targets for row in read_jsonl(path)]
        write_tsv(args.out / "recall.tsv", recall_rows(flags, targets, by_id))
    write_flags(args.out, flags, by_id)
    prose_words = sum(document.plain.words for document in documents)
    surprisal_seconds = sum(row["cpu_seconds"] for row in scored.values() if row["id"] in by_id)
    association_seconds = sum(
        row["association_cpu_seconds"] for row in scored.values() if row["id"] in by_id
    )
    write_tsv(
        args.out / "cost.tsv",
        [
            cost_row("surprisal scoring", surprisal_seconds, prose_words, per_1000_words=True),
            cost_row("pair association", association_seconds, prose_words, per_1000_words=True),
            cost_row(
                "full-reference pair lookup", lookup_seconds, prose_words, per_1000_words=True
            ),
            cost_row(
                "count the 500k sample", sample_seconds, sample.total_words, per_1000_words=False
            ),
            cost_row(
                "count the full train split", full_seconds, full.total_words, per_1000_words=False
            ),
        ],
    )
    logger.info(
        f"sample: {sample.total_words} words, {sample.distinct_pairs} distinct content pairs; "
        f"full: {full.total_words} words, {full.distinct_pairs} distinct content pairs"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(required=True)
    commands.add_parser("reference", help="write the 500,000-word sample").set_defaults(
        run=build_sample
    )
    for name, run in (("score", score), ("analyze", analyze)):
        command = commands.add_parser(name)
        command.set_defaults(run=run)
        command.add_argument("--manifest", type=Path, nargs="+", required=True)
        command.add_argument("--include", nargs="+", help="corpus/arm groups to keep")
        command.add_argument("--model", required=True)
        command.add_argument("--out", type=Path, required=True)
    commands.choices["score"].add_argument("--workers", type=int, default=os.cpu_count())
    commands.choices["analyze"].add_argument("--targets", type=Path, nargs="+")
    commands.choices["analyze"].add_argument(
        "--pool", nargs="+", help="NAME=corpus/arm,corpus/arm pools of groups to rate together"
    )
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
