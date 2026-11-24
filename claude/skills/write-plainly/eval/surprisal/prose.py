"""The words and word pairs of a markdown document's prose, as both checks read them.

`plain_text` is a markdown document's prose as `lint_prose_markdown.stretches` prepares it for
the syntax parse too (paper's A.5): markup dropped, and inline code, URLs, paths, identifiers and
math as the word `PLACEHOLDER`. Blocks are joined by a blank line and the stretches of one block,
which an arrow or emoji separates, by a line break. `tokens` splits any plain text, a document's
or the reference corpus's, into word tokens: the linter's word rule, which keeps letters in any
script ("jardinière"), with a hyphenated word split into its parts and the placeholder always a
token of its own, with a possessive at most. Two tokens are joined when one space or a hyphen
separates them, and only joined content words form a pair, so no pair crosses punctuation, a
placeholder or a stretch.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from lint_prose_markdown import PLACEHOLDER, WORD, WORD_RUN, prose_blocks, stretches

# No word joins the placeholder across a period, comma, apostrophe or hyphen ("back.Xyzzy").
TOKEN_WORD = re.compile(
    rf"{PLACEHOLDER}(?:['’]s)?(?![^\W_])"
    rf"|{WORD_RUN}(?:['’.,-](?!{PLACEHOLDER}(?![^\W_])){WORD_RUN})*"
)
POSSESSIVE = re.compile(r"'s$")
FUNCTION_WORD_LIST = (
    "a about above across after again against all almost along also although always am among "
    "an and another any anyone anything are around as at be because been before being below "
    "between both but by can cannot could did do does doing done down during each either "
    "else enough etc even ever every few for from further had has have having he her here "
    "hers herself him himself his how however i if in into is it its itself just least less "
    "let like many may me might more most much must my myself neither no nor not now of off "
    "often on once one only onto or other others otherwise our ours ourselves out over own "
    "per quite rather same several shall she should since so some something such than that "
    "the their theirs them themselves then there these they this those though through thus "
    "to too toward towards under until up upon us very via was we were what whatever when "
    "where whether which while who whom whose why will with within without would yet you "
    "your yours yourself yourselves"
)
FUNCTION_WORDS = set(FUNCTION_WORD_LIST.split())


@dataclass(frozen=True)
class Token:
    """One word, or one part of a hyphenated word; offsets index the text it came from."""

    text: str
    start: int
    end: int
    joined: bool


@dataclass(frozen=True)
class Span:
    """A flagged phrase; offsets index the text its tokens came from."""

    start: int
    end: int


@dataclass(frozen=True)
class PlainText:
    """A document's prose as plain text; `sources` maps each token's start to its source
    (line, column), and `words` counts words as the linter does."""

    text: str
    sources: dict[int, tuple[int, int]]
    words: int


def tokens(text: str) -> list[Token]:
    found: list[Token] = []
    previous_end = None
    for match in TOKEN_WORD.finditer(text):
        joined = previous_end is not None and text[previous_end : match.start()] == " "
        offset = match.start()
        for part in match.group().split("-"):
            found.append(Token(part, offset, offset + len(part), joined))
            offset += len(part) + 1
            joined = True
        previous_end = match.end()
    return found


def word_key(word: str) -> str:
    return POSSESSIVE.sub("", word.lower().replace("’", "'"))


def pair_key(left: str, right: str) -> tuple[str, str]:
    return word_key(left), word_key(right)


def is_content_word(word: str) -> bool:
    key = word_key(word)
    return (
        len(key) > 1
        and key not in FUNCTION_WORDS
        and key != PLACEHOLDER.lower()
        and not any(character.isdigit() or character in ".,'" for character in key)
    )


def content_pairs(found: Sequence[Token]) -> list[tuple[int, int]]:
    """Indices of each joined pair of adjacent content words."""
    content = [is_content_word(token.text) for token in found]
    return [
        (index - 1, index)
        for index in range(1, len(found))
        if found[index].joined and content[index - 1] and content[index]
    ]


def merge_spans(found: Sequence[Token], index_pairs: Sequence[tuple[int, int]]) -> list[Span]:
    """One span per run of (first, last) token index pairs, in order, where each starts at or
    before the end of the one before it."""
    merged: list[list[int]] = []
    for first, last in index_pairs:
        if merged and first <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], last)
        else:
            merged.append([first, last])
    return [Span(found[first].start, found[last].end) for first, last in merged]


def plain_text(markdown: str) -> PlainText:
    sources: dict[int, tuple[int, int]] = {}
    paragraphs: list[str] = []
    start = 0
    words = 0
    for block in prose_blocks(markdown):
        if not WORD.search(block.text):
            continue
        parts: list[str] = []
        for stretch in stretches(block):
            offset = start + sum(len(part) + 1 for part in parts)
            for token in tokens(stretch.text):
                sources[offset + token.start] = block.position(stretch.starts[token.start])
            parts.append(stretch.text)
        paragraph = "\n".join(parts)
        paragraphs.append(paragraph)
        start += len(paragraph) + 2
        words += len(WORD.findall(block.text))
    return PlainText("\n\n".join(paragraphs), sources, words)
