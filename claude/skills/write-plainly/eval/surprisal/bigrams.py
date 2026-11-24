"""Unattested content-word pairs: pairs of a document that never occur in a reference corpus.

The paper (Clark, Martin and Mahowald 2026, Section 3.1 and Appendix B.2) reports the rate of
bigrams absent from a 500,000-word reference; here each absent content-word pair is a candidate
flag, and consecutive absent pairs merge into one phrase.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field

from prose import (
    Span,
    Token,
    content_pairs,
    is_content_word,
    merge_spans,
    pair_key,
    tokens,
    word_key,
)


@dataclass
class ReferenceCounts:
    """Attested content pairs and word counts of a reference; `pairs` and `words` hold only the
    wanted entries when the count was limited, while the totals cover the whole reference."""

    pairs: set[tuple[str, str]] = field(default_factory=set)
    words: Counter[str] = field(default_factory=Counter)
    total_words: int = 0
    distinct_words: int = 0
    distinct_pairs: int = 0

    def unigram_bits(self, word: str) -> float:
        """Add-one smoothed surprisal of a word in the reference, in bits."""
        count = self.words[word_key(word)]
        return -math.log2((count + 1) / (self.total_words + self.distinct_words))


def count_reference(
    paragraphs: Iterable[str],
    wanted_pairs: Collection[tuple[str, str]] | None = None,
    wanted_words: Collection[str] | None = None,
) -> ReferenceCounts:
    counts = ReferenceCounts()
    seen_pairs: set[int] = set()
    seen_words: set[str] = set()
    for paragraph in paragraphs:
        found = tokens(paragraph)
        counts.total_words += len(found)
        for token in found:
            key = word_key(token.text)
            seen_words.add(key)
            if wanted_words is None or key in wanted_words:
                counts.words[key] += 1
        for left, right in content_pairs(found):
            key = pair_key(found[left].text, found[right].text)
            seen_pairs.add(hash(key))
            if wanted_pairs is None or key in wanted_pairs:
                counts.pairs.add(key)
    counts.distinct_words = len(seen_words)
    counts.distinct_pairs = len(seen_pairs)
    return counts


def document_pairs(found: Sequence[Token]) -> set[tuple[str, str]]:
    return {pair_key(found[left].text, found[right].text) for left, right in content_pairs(found)}


def document_words(found: Sequence[Token]) -> set[str]:
    return {word_key(token.text) for token in found if is_content_word(token.text)}


def unattested_phrases(found: Sequence[Token], attested: Collection[tuple[str, str]]) -> list[Span]:
    pairs = [
        (left, right)
        for left, right in content_pairs(found)
        if pair_key(found[left].text, found[right].text) not in attested
    ]
    return merge_spans(found, pairs)
