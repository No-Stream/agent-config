"""The n-gram reference: WikiText-103 (English Wikipedia's Good and Featured articles), raw form.

The rows come from the `wikitext-103-raw-v1` train split of `Salesforce/wikitext` on the
Hugging Face Hub (CC BY-SA 3.0). `wikitext_articles` undoes the corpus's tokenization markers,
so its words split as a document's do, and closes the space the corpus puts before punctuation;
`sample_paragraphs` draws the paper-sized reference (Appendix B.2: a random sample of about
500,000 words).
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterable, Iterator, Sequence
from pathlib import Path

from prose import WORD

WIKITEXT_REPO = "Salesforce/wikitext"
WIKITEXT_TRAIN_FILES = tuple(
    f"wikitext-103-raw-v1/train-0000{index}-of-00002.parquet" for index in range(2)
)
REFERENCE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "reference"
SAMPLE_FILE = REFERENCE_DIR / "wikitext103-500k.txt"
SAMPLE_WORDS = 500_000
SAMPLE_SEED = 20261123
TITLE = re.compile(r"^ = [^=].* = $")
HEADING = re.compile(r"^ = = .* = = $")
MARKERS = ((" @-@ ", "-"), (" @,@ ", ","), (" @.@ ", "."))
CLITIC = re.compile(r" (?=(?:'s|'re|'ve|'ll|'d|'m|n't)\b)")
# A period or comma that starts a word, as in ".NET", ".263" or ".د.ب", keeps the space before it.
SPACE_BEFORE_PUNCTUATION = re.compile(r" +(?=[,.;:!?)\]](?![^\W_]))")


def clean_row(row: str) -> str:
    row = row.strip("\n").strip()
    for marker, replacement in MARKERS:
        row = row.replace(marker, replacement)
    return SPACE_BEFORE_PUNCTUATION.sub("", CLITIC.sub("", row))


def wikitext_articles(rows: Iterable[str]) -> Iterator[list[str]]:
    """Each article's paragraphs, in order; heading rows and blank rows are dropped."""
    article: list[str] = []
    for row in rows:
        line = row.rstrip("\n")
        if TITLE.match(line):
            if article:
                yield article
            article = []
        elif line.strip() and not HEADING.match(line):
            article.append(clean_row(line))
    if article:
        yield article


def sample_paragraphs(articles: Sequence[list[str]], words: int, seed: int) -> list[str]:
    """Whole paragraphs drawn in a seeded random order from every article, up to the first that
    reaches `words` words; paragraphs rather than articles, so one long article's topic does not
    fill the sample."""
    paragraphs = [paragraph for article in articles for paragraph in article]
    random.Random(seed).shuffle(paragraphs)
    sample: list[str] = []
    total = 0
    for paragraph in paragraphs:
        if total >= words:
            break
        sample.append(paragraph)
        total += len(WORD.findall(paragraph))
    if total < words:
        raise ValueError(f"the articles hold {total} words, fewer than the {words} wanted")
    return sample


def write_sample(path: Path, paragraphs: Sequence[str]) -> None:
    """One paragraph per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(paragraphs) + "\n")


def read_paragraphs(path: Path) -> list[str]:
    return [line for line in path.read_text().splitlines() if line.strip()]
