#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Build the manifest of every text the detectors score.

Sources, all found by path so that new texts need only a rerun:
- the bheijden/slop matched corpus (`../.cache/bheijden-slop`, fetched by `../false_flags.py`);
- the user's voice samples, `.private/eval/human-private/*.md`;
- the pairwise passages, `.private/eval/pairwise/generation/<task>/<pipeline>/final.md`;
- new texts on the bheijden topics, `.private/eval/detector-texts/bheijden/<pair id>/<arm>.md`,
  written by `.private/eval/detector-texts/tools/detector_texts.py`.
"""

from __future__ import annotations

import argparse
import json
import logging
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from scoring import (
    BHEIJDEN,
    BHEIJDEN_ARMS,
    MANIFEST_FILE,
    PAIRWISE,
    REPO_ROOT,
    VOICE_ARM,
    VOICE_CORPUS,
    Text,
    prepare_text,
    word_count,
    write_manifest,
)

logger = logging.getLogger(__name__)

EVAL_DIR = Path(__file__).resolve().parents[1]
BHEIJDEN_CORPUS_DIR = EVAL_DIR / ".cache" / "bheijden-slop" / "data" / "corpus"
VOICE_REGISTER = "work-doc"


@dataclass(frozen=True)
class Sources:
    bheijden_corpus: Path
    voice_dir: Path
    pairwise_generation: Path
    pairwise_task_files: tuple[Path, ...]
    detector_texts: Path

    @classmethod
    def default(cls) -> Sources:
        private = REPO_ROOT / ".private" / "eval"
        return cls(
            bheijden_corpus=BHEIJDEN_CORPUS_DIR,
            voice_dir=private / "human-private",
            pairwise_generation=private / "pairwise" / "generation",
            pairwise_task_files=(
                EVAL_DIR / "pairwise" / "tasks" / "public.toml",
                private / "pairwise" / "tasks" / "work.toml",
            ),
            detector_texts=private / "detector-texts",
        )


def make_text(corpus: str, arm: str, topic: str, register: str, path: Path, repo: Path) -> Text:
    return Text(
        id=f"{corpus}/{arm}/{topic}",
        corpus=corpus,
        arm=arm,
        topic=topic,
        register=register,
        words=word_count(prepare_text(path.read_text())),
        path=str(path.relative_to(repo)),
    )


def bheijden_pairs(corpus_dir: Path) -> list[dict]:
    return json.loads((corpus_dir / "pairs.json").read_text())["pairs"]


def bheijden_registers(corpus_dir: Path) -> dict[str, str]:
    return {pair["id"]: pair["register"] for pair in bheijden_pairs(corpus_dir)}


def bheijden_texts(corpus_dir: Path, repo: Path) -> list[Text]:
    pairs = json.loads((corpus_dir / "pairs.json").read_text())["pairs"]
    return [
        make_text(
            BHEIJDEN, arm, pair["id"], pair["register"], corpus_dir / pair[side]["file"], repo
        )
        for pair in pairs
        for side, arm in BHEIJDEN_ARMS.items()
    ]


def pairwise_doc_types(task_files: Iterable[Path]) -> dict[str, str]:
    return {
        task["id"]: task["doc_type"]
        for task_file in task_files
        if task_file.exists()
        for task in tomllib.loads(task_file.read_text())["task"]
    }


def pairwise_texts(generation: Path, doc_types: dict[str, str], repo: Path) -> list[Text]:
    texts = []
    for final in sorted(generation.glob("*/*/final.md")):
        task, pipeline = final.parent.parent.name, final.parent.name
        if task not in doc_types:
            raise ValueError(f"{final}: task {task!r} is in no task file")
        texts.append(make_text(PAIRWISE, pipeline, task, doc_types[task], final, repo))
    return texts


def voice_texts(voice_dir: Path, repo: Path) -> list[Text]:
    return [
        make_text(VOICE_CORPUS, VOICE_ARM, path.stem, VOICE_REGISTER, path, repo)
        for path in sorted(voice_dir.glob("*.md"))
    ]


def detector_texts(root: Path, registers: dict[str, str], repo: Path) -> list[Text]:
    texts = []
    for path in sorted((root / BHEIJDEN).glob("*/*.md")):
        topic, arm = path.parent.name, path.stem
        if topic not in registers:
            raise ValueError(f"{path}: {topic!r} is not a bheijden pair id")
        texts.append(make_text(BHEIJDEN, arm, topic, registers[topic], path, repo))
    return texts


def build(sources: Sources, repo: Path = REPO_ROOT) -> list[Text]:
    doc_types = pairwise_doc_types(sources.pairwise_task_files)
    texts = [
        *bheijden_texts(sources.bheijden_corpus, repo),
        *detector_texts(sources.detector_texts, bheijden_registers(sources.bheijden_corpus), repo),
        *voice_texts(sources.voice_dir, repo),
        *pairwise_texts(sources.pairwise_generation, doc_types, repo),
    ]
    empty = [text.id for text in texts if text.words == 0]
    if empty:
        raise ValueError(f"texts with no words after preparation: {empty}")
    return texts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=MANIFEST_FILE)
    args = parser.parse_args()
    texts = build(Sources.default())
    write_manifest(texts, args.out)
    counts: dict[tuple[str, str], int] = {}
    for text in texts:
        counts[text.corpus, text.arm] = counts.get((text.corpus, text.arm), 0) + 1
    for (corpus, arm), count in sorted(counts.items()):
        logger.info(f"{corpus:16} {arm:26} {count:3}")
    logger.info(f"wrote {len(texts)} texts to {args.out}")


if __name__ == "__main__":
    main()
