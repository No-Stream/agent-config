"""Manifest records, text preparation, chunking and score records shared by every detector.

Standard library only: the SageMaker job imports this module inside a stock container.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from itertools import pairwise
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[5]
EVAL_DIR = Path(__file__).resolve().parents[1]
PRIVATE_DETECTORS = REPO_ROOT / ".private" / "eval" / "detectors"
MANIFEST_FILE = PRIVATE_DETECTORS / "manifest.jsonl"
SCORES_DIR = PRIVATE_DETECTORS / "scores"
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.%-]*")  # the word rule of pairwise/common.py
TYPOGRAPHY = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u2032": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2033": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "\u202f": " ",
    }
)
TABLE_ROW = re.compile(r"^\s*\|")
HEADING = re.compile(r"^#+\s+", re.MULTILINE)
LIST_MARKER = re.compile(r"^[ \t]*(?:[-*+]|\d+\.)[ \t]+", re.MULTILINE)
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
STRONG = re.compile(r"(\*\*|__)(.+?)\1")
EMPHASIS = re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])")
EXTRA_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True, kw_only=True)
class Detector:
    """`window` is the model's input length in tokens, special tokens included."""

    name: str
    model: str
    revision: str
    window: int
    higher_is_ai: bool
    unit: str
    threshold: float | None
    threshold_source: str


FALCON = ("tiiuae/falcon-7b", "ec89142b67d748a1865ea4451372db8313ada0d8")
FALCON_INSTRUCT = ("tiiuae/falcon-7b-instruct", "8782b5c5d8c9290412416618f36a133653e85285")
DETECTORS = {
    detector.name: detector
    for detector in (
        Detector(
            name="desklib",
            model="desklib/ai-text-detector-v1.01",
            revision="5fdea974cd4287c61674951ec78803aa274e2fb7",
            window=768,
            higher_is_ai=True,
            unit="log-odds of P(AI)",
            threshold=0.0,
            threshold_source="P(AI) = 0.5, the model card's cut-off",
        ),
        Detector(
            name="gpttrace",
            model="nakas/gpttrace-v8s-1b",
            revision="ac748e32ca8c90bb8858fadc427757728e27b063",
            window=512,
            higher_is_ai=True,
            unit="machine logit minus human logit",
            threshold=9.3,
            threshold_source="the model card's 1% false-positive cut-off",
        ),
        Detector(
            name="binoculars",
            model=f"{FALCON[0]} observer, {FALCON_INSTRUCT[0]} performer",
            revision=f"{FALCON[1][:12]}, {FALCON_INSTRUCT[1][:12]}",
            window=512,
            higher_is_ai=False,
            unit="log-perplexity over cross-perplexity",
            threshold=0.8536432310785527,
            threshold_source="the reference code's low false-positive cut-off; AI below it",
        ),
        Detector(
            name="fast-detectgpt",
            model=f"{FALCON[0]} sampling, {FALCON_INSTRUCT[0]} scoring",
            revision=f"{FALCON[1][:12]}, {FALCON_INSTRUCT[1][:12]}",
            window=512,
            higher_is_ai=True,
            unit="analytic sampling discrepancy",
            threshold=None,
            threshold_source=(
                "none published; the reference fit puts human texts near 0 and AI near 2.9"
            ),
        ),
    )
}
CPU_DETECTORS = ("desklib", "gpttrace")
GPU_DETECTORS = ("binoculars", "fast-detectgpt")

BHEIJDEN, PAIRWISE, VOICE_CORPUS = "bheijden", "pairwise", "human-private"
BHEIJDEN_ARMS = {"human": "human", "ai": "corpus-claude-opus-5"}  # pairs.json side: arm
BHEIJDEN_CORPUS_DIR = EVAL_DIR / ".cache" / "bheijden-slop" / "data" / "corpus"
VOICE_ARM = "human-jan"
NO_SKILL, SKILL_DRAFT = "no-skill", "skill-draft"
DEGRADED, TELLS_INJECTED, NEUTRAL_REWRITE = "degraded", "tells-injected", "neutral-rewrite"


@dataclass(frozen=True)
class Text:
    """One manifest row; `path` is relative to the repo root."""

    id: str
    corpus: str
    arm: str
    topic: str
    register: str
    words: int
    path: str


@dataclass(frozen=True)
class ChunkScore:
    tokens: int
    score: float


def word_count(text: str) -> int:
    return len(WORD.findall(text))


def prepare_text(markdown: str) -> str:
    """Plain prose for a detector: markdown syntax and table rows removed, typography folded.

    Curly quotes, the ellipsis character and no-break spaces come from the editor or publisher,
    not the author, so every text gets ASCII forms. Dashes are left alone.
    """
    text = "\n".join(line for line in markdown.splitlines() if not TABLE_ROW.match(line))
    text = HEADING.sub("", text)
    text = LIST_MARKER.sub("", text)
    text = LINK.sub(r"\1", text)
    text = STRONG.sub(r"\2", text)
    text = EMPHASIS.sub(r"\1", text)
    text = text.replace("`", "")
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    text = text.translate(TYPOGRAPHY)
    return EXTRA_BLANK_LINES.sub("\n\n", text).strip()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_manifest(path: Path, texts: Sequence[Text]) -> None:
    check_unique_ids(texts)
    write_jsonl(path, (asdict(text) for text in texts))


def read_manifest(path: Path) -> list[Text]:
    expected = {field.name for field in fields(Text)}
    texts = []
    for row in read_jsonl(path):
        if set(row) != expected:
            raise ValueError(f"{path}: row {row.get('id')!r} has fields {sorted(row)}")
        texts.append(Text(**row))
    check_unique_ids(texts)
    return texts


def bheijden_pairs(corpus_dir: Path) -> list[dict]:
    return json.loads((corpus_dir / "pairs.json").read_text())["pairs"]


def check_unique_ids(texts: Sequence[Text]) -> None:
    ids = [text.id for text in texts]
    duplicates = sorted({text_id for text_id in ids if ids.count(text_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate text ids: {duplicates}")


def chunk_spans(n_tokens: int, window: int) -> list[tuple[int, int]]:
    """Split n tokens into the fewest chunks of at most `window` tokens, of nearly equal size.

    Equal sizes keep a short tail chunk, whose score is noisy, from deciding the per-chunk extremes.
    """
    if n_tokens < 1 or window < 1:
        raise ValueError(
            f"need at least one token and a positive window, got {n_tokens=} {window=}"
        )
    count = -(-n_tokens // window)
    bounds = [index * n_tokens // count for index in range(count + 1)]
    return list(pairwise(bounds))


def chunk_texts(
    text: str, offsets: Sequence[tuple[int, int]], window: int
) -> list[tuple[str, int]]:
    """Cut `text` at token boundaries into chunks of at most `window` tokens, with their sizes.

    `offsets` are the (start, end) character offsets of the text's tokens, without special tokens.
    """
    return [
        (text[offsets[start][0] : offsets[end - 1][1]], end - start)
        for start, end in chunk_spans(len(offsets), window)
    ]


def chunk_encodings(
    tokenizer: Callable[..., Mapping[str, Any]], text_id: str, text: str, window: int
) -> list[tuple[Mapping[str, Any], int]]:
    """Each chunk's model input from a `transformers` tokenizer, with the chunk's size in tokens.

    A chunk holds at most `window` tokens less the tokenizer's special tokens. A chunk that
    tokenizes on its own to more than `window` tokens raises rather than lose its tail.
    """
    content_window = window - len(tokenizer("")["input_ids"])
    offsets = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)[
        "offset_mapping"
    ]
    encodings = []
    for chunk, size in chunk_texts(text, offsets, content_window):
        encoding = tokenizer(chunk, return_tensors="pt")
        length = len(encoding["input_ids"][0])
        if length > window:
            raise ValueError(
                f"{text_id}: a {size}-token chunk tokenizes to {length} tokens, over {window=}"
            )
        encodings.append((encoding, size))
    return encodings


def aggregate(chunks: Sequence[ChunkScore]) -> dict:
    """Token-weighted mean over chunks, plus the per-chunk extremes and the chunk scores."""
    if not chunks:
        raise ValueError("no chunks to aggregate")
    non_finite = [chunk.score for chunk in chunks if not math.isfinite(chunk.score)]
    if non_finite:
        raise ValueError(f"non-finite chunk scores: {non_finite}")
    total = sum(chunk.tokens for chunk in chunks)
    return {
        "score": sum(chunk.tokens * chunk.score for chunk in chunks) / total,
        "chunk_max": max(chunk.score for chunk in chunks),
        "chunk_min": min(chunk.score for chunk in chunks),
        "tokens": total,
        "chunk_scores": [chunk.score for chunk in chunks],
        "chunk_tokens": [chunk.tokens for chunk in chunks],
    }


def score_record(text_id: str, sha: str, detector: Detector, chunks: Sequence[ChunkScore]):
    return {
        "id": text_id,
        "sha256": sha,
        "detector": detector.name,
        "revision": detector.revision,
        "window": detector.window,
        **aggregate(chunks),
    }


def reusable_scores(
    existing: Sequence[dict], wanted: dict[str, str], detector: Detector
) -> dict[str, dict]:
    """Records still valid for the wanted {id: sha256}: same text, detector, revision and window."""
    return {
        row["id"]: row
        for row in existing
        if row["detector"] == detector.name
        and row["revision"] == detector.revision
        and row["window"] == detector.window
        and wanted.get(row["id"]) == row["sha256"]
    }


def scores_file(scores_dir: Path, detector_name: str) -> Path:
    return scores_dir / f"{detector_name}.jsonl"


def prepared_texts(texts: Sequence[Text], repo: Path) -> dict[str, str]:
    return {text.id: prepare_text((repo / text.path).read_text()) for text in texts}


def split_pending(
    prepared: dict[str, str], scores_path: Path, detector: Detector
) -> tuple[dict[str, dict], dict[str, str]]:
    """The score records still valid for these texts, and the texts that need scoring."""
    wanted = {text_id: text_sha256(text) for text_id, text in prepared.items()}
    existing = read_jsonl(scores_path) if scores_path.exists() else []
    kept = reusable_scores(existing, wanted, detector)
    return kept, {text_id: text for text_id, text in prepared.items() if text_id not in kept}


def write_scores(scores_path: Path, order: Iterable[str], records: dict[str, dict]) -> list[str]:
    """Write the records in manifest order, dropping texts no longer in it; return unscored ids."""
    order = list(order)
    write_jsonl(scores_path, (records[text_id] for text_id in order if text_id in records))
    return [text_id for text_id in order if text_id not in records]


def require_scored(unscored: dict[str, list[str]], context: str) -> None:
    """Raise naming every detector that left texts unscored, once all their scores are written."""
    missing = {name: text_ids for name, text_ids in unscored.items() if text_ids}
    if missing:
        raise RuntimeError(f"{context}: texts left unscored: {missing}")
