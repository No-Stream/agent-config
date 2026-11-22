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
    GPU_DETECTORS,
    ChunkScore,
    chunk_encodings,
    read_jsonl,
    score_record,
    scores_file,
    write_jsonl,
)
from transformers import AutoModelForCausalLM, AutoTokenizer

logger: logging.Logger = logging.getLogger(__name__)

WINDOWS = {DETECTORS[name].window for name in GPU_DETECTORS}
if len(WINDOWS) != 1:
    raise ValueError(f"both Falcon detectors share one forward pass, so need one window: {WINDOWS}")
(WINDOW,) = WINDOWS


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
    parser.add_argument("--texts", type=Path, required=True, help="JSONL of id, sha256, text")
    parser.add_argument("--out", type=Path, required=True, help="directory for the score files")
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

    records: dict[str, list[dict]] = {name: [] for name in GPU_DETECTORS}
    rows = read_jsonl(args.texts)
    for index, row in enumerate(rows, 1):
        chunks: dict[str, list[ChunkScore]] = {name: [] for name in GPU_DETECTORS}
        for encoding, size in chunk_encodings(tokenizer, row["id"], row["text"], WINDOW):
            for name, score in chunk_scores(encoding["input_ids"], observer, performer).items():
                chunks[name].append(ChunkScore(size, score))
        for name in GPU_DETECTORS:
            records[name].append(
                score_record(row["id"], row["sha256"], DETECTORS[name], chunks[name])
            )
        scored = ", ".join(f"{name} {records[name][-1]['score']:.4f}" for name in GPU_DETECTORS)
        logger.info(f"{index}/{len(rows)} {row['id']}: {scored}")
    for name, detector_records in records.items():
        write_jsonl(scores_file(args.out, name), detector_records)
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
