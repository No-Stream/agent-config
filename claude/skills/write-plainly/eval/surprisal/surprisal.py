"""Surprisal hotspots and pair association under a causal language model on the CPU.

`token_surprisals` scores every model token once, in windows of at most `window` tokens that
advance by `stride`, so every token sees at least `window - stride` tokens of context once the
text is longer than one window. `word_bits` sums the model tokens of each word token from
`prose.tokens`. `hotspots` standardizes one score per content word against the document's own
median and MAD and flags each content word above the threshold, or only those that end a
content pair. `slot_terms` reads a pair's terms: how likely its second word is after its first
and in its first word's place, and how likely the space or hyphen that joins them is.
"""

from __future__ import annotations

import bisect
import functools
import itertools
import math
import statistics
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import torch

from prose import Span, Token, content_pairs, is_content_word, merge_spans

MAD_TO_SD = 1.4826


@dataclass(frozen=True)
class TokenScore:
    """A model token's character span in the scored text and its surprisal in bits."""

    start: int
    end: int
    bits: float


@dataclass(frozen=True)
class PairTerms:
    """A content pair's terms in bits: the second word's characters after all the text before
    them (`after_first`) and in the first word's place (`in_place`), and the space or hyphen
    between the words right after the first word (`joiner`)."""

    after_first: float
    in_place: float
    joiner: float

    @property
    def association(self) -> float:
        """Positive when the first word makes the second less likely, as a coined pair's does."""
        return self.after_first - self.in_place


@dataclass(frozen=True)
class _PairReads:
    """Where a pair's terms are read. `left_first` and `right_first` index the first token of each
    word's pre-token in the text's ids, `left_last` and `right_last` the last token holding each
    word's last character; each lead is its pre-token's characters before the word; `separator`
    is the text between the words; `slot` is the ids of the left lead and the second word, which
    stand in the first word's place."""

    left_first: int
    left_last: int
    right_first: int
    right_last: int
    left_lead: str
    right_lead: str
    separator: str
    slot: tuple[int, ...]


def _encode(text: str, tokenizer) -> tuple[torch.Tensor, list[tuple[int, int]]]:
    """The text's token ids after the end-of-text token, which separates documents in training
    text, and the character offsets of every id after it."""
    if tokenizer.eos_token_id is None:
        raise ValueError("the tokenizer has no end-of-text token to start the text after")
    encoding = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids = torch.tensor([tokenizer.eos_token_id, *encoding["input_ids"]])
    return ids, encoding["offset_mapping"]


def _windows(length: int, *, window: int, stride: int) -> list[tuple[int, int, int]]:
    """(begin, start, end) of each pass over `length` ids: it reads ids[begin : end - 1] and
    scores positions start to end - 1, so each position after the first is scored once."""
    if not 0 < stride <= window:
        raise ValueError(f"need 0 < stride <= window, got {stride=} {window=}")
    windows = []
    for start in range(1, length, stride):
        end = min(start + stride, length)
        windows.append((max(0, end - 1 - window), start, end))
    return windows


def _log_probs(
    model, ids: torch.Tensor, branches: Sequence[tuple[int, Sequence[int]]]
) -> tuple[torch.Tensor, list[torch.Tensor]]:
    """Next-token log-probabilities after each of `ids`, and after each token of each branch, in
    one pass. A branch (attach, tokens) continues ids[:attach] with its tokens in place of
    ids[attach:]: they sit at positions attach onward and attend only to that prefix and to
    each other."""
    length = len(ids)
    total = length + sum(len(tokens) for _, tokens in branches)
    allowed = torch.zeros(total, total, dtype=torch.bool)
    allowed[:length, :length] = torch.ones(length, length, dtype=torch.bool).tril()
    positions = list(range(length))
    rows = []
    offset = length
    for attach, tokens in branches:
        span = slice(offset, offset + len(tokens))
        allowed[span, :attach] = True
        allowed[span, span] = torch.ones(len(tokens), len(tokens), dtype=torch.bool).tril()
        positions += range(attach, attach + len(tokens))
        rows.append(span)
        offset += len(tokens)
    mask = torch.zeros(total, total, dtype=model.dtype)
    mask.masked_fill_(~allowed, torch.finfo(model.dtype).min)
    extra = torch.tensor([token for _, tokens in branches for token in tokens], dtype=torch.long)
    logits = model(
        torch.cat([ids, extra]).unsqueeze(0),
        attention_mask=mask[None, None],
        position_ids=torch.tensor([positions]),
    ).logits[0]
    log_probs = torch.log_softmax(logits.float(), -1)
    return log_probs[:length], [log_probs[span] for span in rows]


@functools.cache
def _vocabulary(tokenizer) -> tuple[str, ...]:
    return tuple(
        tokenizer.batch_decode(
            [[index] for index in range(len(tokenizer))], clean_up_tokenization_spaces=False
        )
    )


@functools.cache
def _starting_with(tokenizer, lead: str) -> torch.Tensor:
    """Ids of the tokens whose text starts with `lead`."""
    vocabulary = _vocabulary(tokenizer)
    return torch.tensor([index for index, piece in enumerate(vocabulary) if piece.startswith(lead)])


def _lead_log_prob(row: torch.Tensor, lead: str, tokenizer) -> torch.Tensor:
    """Log-probability that the next characters are `lead`: the mass of the tokens starting with
    it, exact for one character."""
    if not lead:
        return torch.tensor(0.0)
    return torch.logsumexp(row[_starting_with(tokenizer, lead)], 0)


@torch.inference_mode()
def token_surprisals(text: str, tokenizer, model, *, window: int, stride: int) -> list[TokenScore]:
    ids, offsets = _encode(text, tokenizer)
    bits: list[float] = []
    for begin, start, end in _windows(len(ids), window=window, stride=stride):
        logits = model(ids[begin : end - 1].unsqueeze(0)).logits[0]
        log_probs = torch.log_softmax(logits.float(), -1)
        positions = torch.arange(start, end)
        bits += (-log_probs[positions - 1 - begin, ids[start:end]] / math.log(2)).tolist()
    return [
        TokenScore(start, end, value) for (start, end), value in zip(offsets, bits, strict=True)
    ]


def _pair_reads(
    text: str,
    words: Sequence[Token],
    pairs: Sequence[tuple[int, int]],
    offsets: Sequence[tuple[int, int]],
    tokenizer,
) -> list[_PairReads]:
    ends = [0, *(end for _, end in offsets)]
    pieces = tokenizer.backend_tokenizer.pre_tokenizer.pre_tokenize_str(text)
    piece_starts = [start for _, (start, _) in pieces]

    def first_token(word: Token) -> tuple[int, str]:
        """The id index of the first token of the pre-token holding the word, and that
        pre-token's characters before the word."""
        start = piece_starts[bisect.bisect_right(piece_starts, word.start) - 1]
        index = bisect.bisect_right(ends, start)
        if ends[index - 1] != start:
            raise ValueError(f"no model token starts where the pre-token of {word.text!r} does")
        if word.start - start > 1:
            raise ValueError(
                f"{word.text!r} starts inside the model's word {text[start : word.end]!r}"
            )
        return index, text[start : word.start]

    def last_token(word: Token) -> int:
        """The id index of the last token holding the word's last character."""
        reaching = bisect.bisect_right(ends, word.end - 1)
        # the byte tokens of a character split into bytes all end where the character does
        return bisect.bisect_right(ends, ends[reaching]) - 1

    reads = []
    for left, right in pairs:
        left_first, left_lead = first_token(words[left])
        right_first, right_lead = first_token(words[right])
        right_last = last_token(words[right])
        unit = text[words[right].start : ends[right_last]]
        slot = tokenizer(left_lead + unit, add_special_tokens=False)["input_ids"]
        separator = text[words[left].end : words[right].start]
        reads.append(
            _PairReads(
                left_first,
                last_token(words[left]),
                right_first,
                right_last,
                left_lead,
                right_lead,
                separator,
                tuple(slot),
            )
        )
    return reads


@torch.inference_mode()
def slot_terms(
    text: str,
    words: Sequence[Token],
    pairs: Sequence[tuple[int, int]],
    tokenizer,
    model,
    *,
    window: int,
    stride: int,
) -> list[PairTerms]:
    """Each pair's terms. Both word terms score the second word's own characters after all the
    text before them, so they score the same unit whatever the tokenizer merges. Each reads the
    tokens from the start of the model's pre-token holding the word, less the probability of
    that pre-token's one character before the word, a joining space or hyphen. The joiner is
    read from the tokens that start with the separator, after the first word's last token. All
    three come from the one pass that scores the second word's last token, so they share a
    context.
    """
    ids, offsets = _encode(text, tokenizer)
    reads = _pair_reads(text, words, pairs, offsets, tokenizer)
    windows = _windows(len(ids), window=window, stride=stride)
    starts = [start for _, start, _ in windows]
    by_window = defaultdict(list)
    for number, pair in enumerate(reads):
        by_window[bisect.bisect_right(starts, pair.right_last) - 1].append(number)
    nats = torch.zeros(len(reads), 3)
    for index, numbers in by_window.items():
        begin, _, end = windows[index]
        if any(reads[number].left_first - 1 < begin for number in numbers):
            raise ValueError(f"a pair spans more than {window=} - {stride=} tokens")
        branched = [number for number in numbers if len(reads[number].slot) > 1]
        log_probs, branch_rows = _log_probs(
            model,
            ids[begin : end - 1],
            [(reads[number].left_first - begin, reads[number].slot[:-1]) for number in branched],
        )
        continuations = dict(zip(branched, branch_rows, strict=True))
        for number in numbers:
            pair = reads[number]
            positions = torch.arange(pair.right_first, pair.right_last + 1)
            after_row = log_probs[pair.right_first - 1 - begin]
            after = -log_probs[positions - 1 - begin, ids[positions]].sum() + _lead_log_prob(
                after_row, pair.right_lead, tokenizer
            )
            slot_row = log_probs[pair.left_first - 1 - begin]
            in_place = -slot_row[pair.slot[0]] + _lead_log_prob(slot_row, pair.left_lead, tokenizer)
            if number in continuations:
                rest = torch.tensor(pair.slot[1:])
                in_place -= continuations[number][torch.arange(len(rest)), rest].sum()
            joiner_row = log_probs[pair.left_last - begin]
            joiner = -_lead_log_prob(joiner_row, pair.separator, tokenizer)
            nats[number] = torch.stack([after, in_place, joiner])
    return list(itertools.starmap(PairTerms, (nats / math.log(2)).tolist()))


def word_bits(text: str, words: Sequence[Token], scores: Sequence[TokenScore]) -> list[float]:
    """Each word's surprisal: the bits of the model tokens it starts in, or for a token no word
    starts in, of the word holding its first word character. A token over several word starts
    counts for each of them."""
    word_at = {
        index: number for number, word in enumerate(words) for index in range(word.start, word.end)
    }
    starts = {word.start: number for number, word in enumerate(words)}
    totals = [0.0] * len(words)
    counted = [False] * len(words)
    for score in scores:
        span = range(score.start, score.end)
        owners = [starts[index] for index in span if index in starts]
        if not owners:
            owners = [next((word_at[index] for index in span if index in word_at), None)]
        for number in owners:
            if number is not None:
                totals[number] += score.bits
                counted[number] = True
    missing = [words[number].text for number, seen in enumerate(counted) if not seen]
    if missing:
        raise ValueError(f"no model token covers the start of the words {missing}")
    return totals


def robust_z(values: Sequence[float]) -> list[float]:
    median = statistics.median(values)
    scale = MAD_TO_SD * statistics.median(abs(value - median) for value in values)
    if scale == 0:
        raise ValueError(f"the scores have no spread around their median {median}")
    return [(value - median) / scale for value in values]


def content_z(
    words: Sequence[Token], scores: Sequence[float], *, min_content_words: int
) -> dict[int, float]:
    """Each content word's robust z among the document's content words, by token index; empty
    when the document has fewer content words than the floor."""
    content = [index for index, word in enumerate(words) if is_content_word(word.text)]
    if len(content) < min_content_words:
        return {}
    return dict(zip(content, robust_z([scores[index] for index in content]), strict=True))


def hotspots(
    words: Sequence[Token],
    scores: Sequence[float],
    *,
    threshold: float,
    min_content_words: int,
    pairs_only: bool,
) -> list[Span]:
    """Content words whose robust z exceeds the threshold, each with the word joined before it.

    With `pairs_only`, a word counts only as the second word of a content pair.
    """
    z = content_z(words, scores, min_content_words=min_content_words)
    if not z:
        return []
    if pairs_only:
        index_pairs = [
            (left, right) for left, right in content_pairs(words) if z[right] > threshold
        ]
    else:
        index_pairs = [
            (index - 1 if index and words[index].joined else index, index)
            for index, value in z.items()
            if value > threshold
        ]
    return merge_spans(words, index_pairs)
