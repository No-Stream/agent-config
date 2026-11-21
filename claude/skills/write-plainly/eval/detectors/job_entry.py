"""Binoculars and Fast-DetectGPT scores inside a SageMaker Processing job.

Runs in the AWS Hugging Face PyTorch training container with `scoring.py` beside it. Reads
`texts.jsonl` (id, sha256, text), scores every text with both detectors from one forward pass of
each Falcon model per chunk, and writes `binoculars.jsonl` and `fast-detectgpt.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import torch
import transformers
from scoring import (
    DETECTORS,
    FALCON,
    FALCON_INSTRUCT,
    ChunkScore,
    chunk_encodings,
    read_jsonl,
    score_record,
    write_jsonl,
)
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

WINDOW = DETECTORS["binoculars"].window
if DETECTORS["fast-detectgpt"].window != WINDOW:
    raise ValueError("both Falcon detectors share one forward pass, so they need one window")


def load(name_and_revision: tuple[str, str], device: str) -> AutoModelForCausalLM:
    name, revision = name_and_revision
    return AutoModelForCausalLM.from_pretrained(
        name, revision=revision, dtype=torch.bfloat16, device_map={"": device}
    ).eval()


def falcon_scores(
    observer_logits: torch.Tensor, performer_logits: torch.Tensor, labels: torch.Tensor
) -> dict[str, float]:
    """Both scores of one chunk from each model's logits ([tokens, vocab]) and the next tokens.

    Binoculars as in ahans30/Binoculars `metrics.py`, Fast-DetectGPT's analytic criterion as in
    baoguangsheng/fast-detect-gpt `get_sampling_discrepancy_analytic`. The observer is
    Binoculars' observer and Fast-DetectGPT's sampling model; the performer is the other.
    """
    performer_log_probs = torch.log_softmax(performer_logits, dim=-1)
    observer_probs = torch.softmax(observer_logits, dim=-1)
    label_log_probs = performer_log_probs[:-1].gather(-1, labels[:, None]).squeeze(-1)
    # The reference averages cross-entropy over every position, the last one included.
    cross_entropy = -(observer_probs * performer_log_probs).sum(-1).mean()
    binoculars = -label_log_probs.mean() / cross_entropy

    reference_probs = observer_probs[:-1]
    scoring_log_probs = performer_log_probs[:-1]
    mean_reference = (reference_probs * scoring_log_probs).sum(-1)
    variance_reference = (reference_probs * scoring_log_probs.square()).sum(-1) - mean_reference**2
    fast_detectgpt = (
        label_log_probs.sum() - mean_reference.sum()
    ) / variance_reference.sum().sqrt()
    return {"binoculars": binoculars.item(), "fast-detectgpt": fast_detectgpt.item()}


@torch.inference_mode()
def chunk_scores(
    input_ids: torch.Tensor, observer: AutoModelForCausalLM, performer: AutoModelForCausalLM
) -> dict[str, float]:
    observer_logits = observer(input_ids=input_ids.to(observer.device)).logits[0].float()
    performer_logits = performer(input_ids=input_ids.to(performer.device)).logits[0].float()
    return falcon_scores(
        observer_logits,
        performer_logits.to(observer_logits.device),
        input_ids[0, 1:].to(observer_logits.device),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--texts", type=Path, default=Path("/opt/ml/processing/input/texts/texts.jsonl")
    )
    parser.add_argument("--out", type=Path, default=Path("/opt/ml/processing/output"))
    args = parser.parse_args()

    devices = [f"cuda:{index}" for index in range(torch.cuda.device_count())]
    if not devices:
        raise RuntimeError("no GPU visible; the Falcon pair needs one with about 30 GB free")
    started = time.monotonic()
    observer = load(FALCON, devices[0])
    performer = load(FALCON_INSTRUCT, devices[-1])
    tokenizer = AutoTokenizer.from_pretrained(FALCON[0], revision=FALCON[1])
    performer_tokenizer = AutoTokenizer.from_pretrained(
        FALCON_INSTRUCT[0], revision=FALCON_INSTRUCT[1]
    )
    if tokenizer.get_vocab() != performer_tokenizer.get_vocab():
        raise ValueError("observer and performer tokenizers differ")
    logger.info(f"loaded both models on {devices} in {time.monotonic() - started:.0f} s")

    records: dict[str, list[dict]] = {"binoculars": [], "fast-detectgpt": []}
    rows = read_jsonl(args.texts)
    for index, row in enumerate(rows, 1):
        binoculars_chunks, fast_chunks = [], []
        for encoding, size in chunk_encodings(tokenizer, row["id"], row["text"], WINDOW):
            scores = chunk_scores(encoding["input_ids"], observer, performer)
            binoculars_chunks.append(ChunkScore(size, scores["binoculars"]))
            fast_chunks.append(ChunkScore(size, scores["fast-detectgpt"]))
        for name, chunks in (("binoculars", binoculars_chunks), ("fast-detectgpt", fast_chunks)):
            records[name].append(score_record(row["id"], row["sha256"], DETECTORS[name], chunks))
        logger.info(
            f"{index}/{len(rows)} {row['id']}: binoculars {records['binoculars'][-1]['score']:.4f}"
            f" fast-detectgpt {records['fast-detectgpt'][-1]['score']:.3f}"
        )
    for name, rows_out in records.items():
        write_jsonl(rows_out, args.out / f"{name}.jsonl")
    (args.out / "job.json").write_text(
        json.dumps(
            {
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "gpu": torch.cuda.get_device_name(0),
                "texts": len(rows),
                "seconds": time.monotonic() - started,
            }
        )
    )
    logger.info(f"scored {len(rows)} texts in {time.monotonic() - started:.0f} s")


if __name__ == "__main__":
    main()
