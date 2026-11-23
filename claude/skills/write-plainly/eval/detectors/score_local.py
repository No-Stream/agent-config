#!/usr/bin/env -S uv run --upgrade --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "torch>=2.9",
#   "transformers>=5.23",
#   "safetensors>=0.6",
#   "huggingface-hub>=1.0",
# ]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
"""Score every manifest text with the CPU classifiers, writing one JSONL per detector.

A text already scored with the same prepared text and window keeps its record, so a rerun scores
only new or changed texts. Each model loads at its latest revision on the Hugging Face Hub.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

import torch
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from scoring import (
    CPU_DETECTORS,
    DETECTORS,
    MANIFEST_FILE,
    REPO_ROOT,
    SCORES_DIR,
    ChunkScore,
    Detector,
    chunk_encodings,
    prepared_texts,
    read_manifest,
    require_scored,
    score_record,
    scores_file,
    split_pending,
    text_sha256,
    write_scores,
)
from transformers import AutoConfig, AutoModel, AutoModelForSequenceClassification, AutoTokenizer

logger: logging.Logger = logging.getLogger(__name__)

# Lookalike folding from normalize.py in the nakas/gpttrace-v8s-1b model repo.
HOMOGLYPHS = dict(
    zip(
        "аеорсухіјѕһԁԛԝӏАВЕКМНОРСТХІЈЅҮԀԚԜΑΒΕΖΗΙΚΜΝΟΡΤΥΧονικρτυχα",
        "aeopcyxijshdqwlABEKMHOPCTXIJSYDQWABEZHIKMNOPTYXovikptuxa",
        strict=True,
    )
)
LOOKALIKE = re.compile("[" + "".join(HOMOGLYPHS) + "]")
GREEK_CYRILLIC = re.compile("[Ͱ-ϿЀ-ԯ]")
VARIATION_SELECTORS = re.compile("[\ufe00-\ufe0f]")
LATIN = re.compile("[A-Za-z]")
LETTERS = re.compile(r"[^\W\d_]+")

Scorer = Callable[[dict[str, torch.Tensor]], float]


def gpttrace_normalize(text: str) -> str:
    """normalize_text from gpttrace's normalize.py; `prepare_text` already did the rest."""
    text = VARIATION_SELECTORS.sub("", text)
    lookalikes = LOOKALIKE.findall(text)
    if not lookalikes:
        return text
    foreign = len(GREEK_CYRILLIC.findall(text)) - len(lookalikes)
    if len(LATIN.findall(text)) <= foreign:
        return text

    def fold(word: str) -> str:
        return LOOKALIKE.sub(lambda match: HOMOGLYPHS[match.group(0)], word)

    return LETTERS.sub(
        lambda m: m.group(0) if GREEK_CYRILLIC.search(fold(m.group(0))) else fold(m.group(0)), text
    )


def load_desklib(detector: Detector) -> tuple[AutoTokenizer, Scorer, Callable[[str], str]]:
    """The model card's DesklibAIDetectionModel: DeBERTa-v3-large, masked mean pool, one logit."""
    config = AutoConfig.from_pretrained(detector.model)
    backbone = AutoModel.from_config(config).eval()
    weights = load_file(hf_hub_download(detector.model, "model.safetensors"))
    unknown = [key for key in weights if not key.startswith(("model.", "classifier."))]
    if unknown:
        raise ValueError(f"desklib weights have unexpected keys: {unknown}")
    backbone.load_state_dict(
        {
            key.removeprefix("model."): value
            for key, value in weights.items()
            if key.startswith("model.")
        }
    )
    head = torch.nn.Linear(config.hidden_size, 1)
    head.load_state_dict(
        {"weight": weights["classifier.weight"], "bias": weights["classifier.bias"]}
    )

    def score(encoding: dict[str, torch.Tensor]) -> float:
        hidden = backbone(
            input_ids=encoding["input_ids"], attention_mask=encoding["attention_mask"]
        ).last_hidden_state
        mask = encoding["attention_mask"].unsqueeze(-1).to(hidden.dtype)
        return head((hidden * mask).sum(1) / mask.sum(1)).item()

    tokenizer = AutoTokenizer.from_pretrained(detector.model)
    return tokenizer, score, lambda text: text


def load_gpttrace(detector: Detector) -> tuple[AutoTokenizer, Scorer, Callable[[str], str]]:
    model = AutoModelForSequenceClassification.from_pretrained(
        detector.model, subfolder="model"
    ).eval()

    def score(encoding: dict[str, torch.Tensor]) -> float:
        logits = model(
            input_ids=encoding["input_ids"], attention_mask=encoding["attention_mask"]
        ).logits[0]
        return (logits[1] - logits[0]).item()

    tokenizer = AutoTokenizer.from_pretrained(detector.model, subfolder="model")
    return tokenizer, score, gpttrace_normalize


LOADERS = {"desklib": load_desklib, "gpttrace": load_gpttrace}


@torch.inference_mode()
def score_texts(detector: Detector, pending: dict[str, str]) -> dict[str, dict]:
    tokenizer, score, normalize = LOADERS[detector.name](detector)
    records = {}
    for index, (text_id, text) in enumerate(pending.items(), 1):
        chunks = [
            ChunkScore(size, score(encoding))
            for encoding, size in chunk_encodings(
                tokenizer, text_id, normalize(text), detector.window
            )
        ]
        records[text_id] = score_record(text_id, text_sha256(text), detector, chunks)
        logger.info(
            f"{detector.name} {index}/{len(pending)} {text_id}: {records[text_id]['score']:.3f}"
        )
    return records


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=MANIFEST_FILE)
    parser.add_argument("--scores", type=Path, default=SCORES_DIR)
    parser.add_argument("--detectors", nargs="+", choices=CPU_DETECTORS, default=CPU_DETECTORS)
    parser.add_argument(
        "--threads", type=int, default=int(os.environ.get("TORCH_NUM_THREADS", "8"))
    )
    args = parser.parse_args()
    torch.set_num_threads(args.threads)
    texts = read_manifest(args.manifest)
    prepared = prepared_texts(texts, REPO_ROOT)
    unscored = {}
    for name in args.detectors:
        detector = DETECTORS[name]
        scores_path = scores_file(args.scores, name)
        kept, pending = split_pending(prepared, scores_path, detector)
        logger.info(f"{name}: {len(kept)} texts already scored, {len(pending)} to score")
        started = time.monotonic()
        new = score_texts(detector, pending) if pending else {}
        unscored[name] = write_scores(scores_path, prepared, {**kept, **new})
        logger.info(f"{name}: wrote {scores_path} in {time.monotonic() - started:.0f} s")
    require_scored(unscored, "score_local")


if __name__ == "__main__":
    main()
