import math

import pytest
import torch
from language_models import CORPUS, gpt2_style_model
from language_models import qwen_style_model as build_qwen_style_model

from prose import content_pairs, tokens
from surprisal import (
    TokenScore,
    content_z,
    hotspots,
    robust_z,
    slot_terms,
    token_surprisals,
    word_bits,
)

HOTSPOT_BITS = {"trap": 30.0, "gear": 9.0, "fishing": 6.5, "harbour": 5.5, "owe": 28.0}


@pytest.fixture(scope="module")
def tiny_model():
    return gpt2_style_model()


@pytest.fixture(scope="module")
def qwen_style_model():
    return build_qwen_style_model()


@pytest.fixture(params=["tiny_model", "qwen_style_model"])
def any_model(request):
    return request.getfixturevalue(request.param)


def full_pass_bits(text: str, tokenizer, model) -> list[float]:
    ids = [tokenizer.eos_token_id, *tokenizer(text, add_special_tokens=False)["input_ids"]]
    with torch.inference_mode():
        log_probs = torch.log_softmax(model(torch.tensor([ids])).logits[0], dim=-1)
    return [-log_probs[i - 1, ids[i]].item() / math.log(2) for i in range(1, len(ids))]


def window_layout(length: int, window: int, stride: int) -> list[tuple[int, int, int]]:
    """The windows `token_surprisals` documents: positions start to end - 1 are scored by a pass
    over ids[begin : end - 1], with begin at most `window` ids before end - 1."""
    layout = []
    for start in range(1, length, stride):
        end = min(start + stride, length)
        layout.append((max(0, end - 1 - window), start, end))
    return layout


def pre_token_start(text: str, character: int, tokenizer) -> int:
    """Where the model's pre-token holding the character starts."""
    pieces = tokenizer.backend_tokenizer.pre_tokenizer.pre_tokenize_str(text)
    return max(start for _, (start, _) in pieces if start <= character)


def after_tokens_ending_at(ends: list[int], position: int) -> int:
    """Index of the id after the last one ending at `position`; the byte tokens of a split
    character all end where the character does."""
    return max(index for index, end in enumerate(ends) if end == position) + 1


def lead_nats(log_probs: torch.Tensor, lead: str, tokenizer) -> float:
    """Log-probability that the next characters are `lead`, from the tokens that start with it."""
    if not lead:
        return 0.0
    vocabulary = tokenizer.batch_decode(
        [[index] for index in range(len(tokenizer))], clean_up_tokenization_spaces=False
    )
    starting = [index for index, piece in enumerate(vocabulary) if piece.startswith(lead)]
    return torch.logsumexp(log_probs[starting], dim=0).item()


def character_bits(context: str, unit: str, tokenizer, model) -> float:
    """Bits of the characters `unit` right after `context`, from one pass over the tokens of
    context + unit after the end-of-text token: the tokens from the start of the pre-token holding
    the unit's first character, less the bits of that pre-token's characters before the unit,
    which any token starting with them would give."""
    text = context + unit
    lead = text[pre_token_start(text, len(context), tokenizer) : len(context)]
    encoding = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids = [tokenizer.eos_token_id, *encoding["input_ids"]]
    ends = [0, *(end for _, end in encoding["offset_mapping"])]
    first = after_tokens_ending_at(ends, len(context) - len(lead))
    with torch.inference_mode():
        log_probs = torch.log_softmax(model(torch.tensor([ids])).logits[0].float(), dim=-1)
    nats = -sum(log_probs[index - 1, ids[index]].item() for index in range(first, len(ids)))
    return (nats + lead_nats(log_probs[first - 1], lead, tokenizer)) / math.log(2)


def associations(*arguments, **windows) -> list[float]:
    return [terms.association for terms in slot_terms(*arguments, **windows)]


def next_characters_bits(context: str, characters: str, tokenizer, model) -> float:
    """Bits of `characters` right after `context`, from the tokens that start with them."""
    ids = [tokenizer.eos_token_id, *tokenizer(context, add_special_tokens=False)["input_ids"]]
    with torch.inference_mode():
        log_probs = torch.log_softmax(model(torch.tensor([ids])).logits[0, -1].float(), dim=-1)
    return -lead_nats(log_probs, characters, tokenizer) / math.log(2)


def expected_association(text, words, pair, tokenizer, model) -> float:
    """The second word's characters after the text before them, less after the text before the
    first word."""
    left, right = (words[index] for index in pair)
    unit = text[right.start : right.end]
    after = character_bits(text[: right.start], unit, tokenizer, model)
    in_place = character_bits(text[: left.start], unit, tokenizer, model)
    return after - in_place


def bounded_association(text, words, pair, tokenizer, model, *, begin: int) -> float:
    """The same two terms from passes over the text's ids from `begin`: the second word's tokens
    after the ids before them, and the tokens of the second word in the first word's place after
    the ids before the first word's first token."""
    encoding = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    ids = [tokenizer.eos_token_id, *encoding["input_ids"]]
    ends = [0, *(end for _, end in encoding["offset_mapping"])]
    left, right = (words[index] for index in pair)

    def first_token(word) -> tuple[int, str]:
        start = pre_token_start(text, word.start, tokenizer)
        return after_tokens_ending_at(ends, start), text[start : word.start]

    def bits(context: list[int], unit: list[int], lead: str) -> float:
        with torch.inference_mode():
            logits = model(torch.tensor([context + unit[:-1]])).logits[0]
        log_probs = torch.log_softmax(logits.float(), dim=-1)
        rows = range(len(context) - 1, len(context) + len(unit) - 1)
        nats = -sum(log_probs[row, token].item() for row, token in zip(rows, unit, strict=True))
        return (nats + lead_nats(log_probs[len(context) - 1], lead, tokenizer)) / math.log(2)

    right_first, right_lead = first_token(right)
    starts = [-1, *(start for start, _ in encoding["offset_mapping"])]
    right_last = max(index for index, start in enumerate(starts) if start < right.end)
    left_first, left_lead = first_token(left)
    unit = text[right.start : right.end]
    slot = tokenizer(left_lead + unit, add_special_tokens=False)["input_ids"]
    after = bits(ids[begin:right_first], ids[right_first : right_last + 1], right_lead)
    return after - bits(ids[begin:left_first], slot, left_lead)


class TestTokenSurprisals:
    TEXT = "A calm harbour shelters the fishing fleet at low tide."

    def test_one_window_matches_a_full_pass(self, tiny_model):
        tokenizer, model = tiny_model
        scores = token_surprisals(self.TEXT, tokenizer, model, window=200, stride=100)
        assert [score.bits for score in scores] == pytest.approx(
            full_pass_bits(self.TEXT, tokenizer, model), abs=1e-4
        )
        assert all(score.bits > 0 for score in scores)

    def test_sliding_windows_score_every_token_once_on_its_bounded_context(self, any_model):
        tokenizer, model = any_model
        text = CORPUS[:600]
        scores = token_surprisals(text, tokenizer, model, window=32, stride=16)
        ids = [tokenizer.eos_token_id, *tokenizer(text, add_special_tokens=False)["input_ids"]]
        layout = window_layout(len(ids), 32, 16)
        assert layout[-1][2] - layout[-1][1] < 16 and sum(begin > 0 for begin, _, _ in layout) > 3
        expected = []
        for begin, start, end in layout:
            with torch.inference_mode():
                logits = model(torch.tensor([ids[begin : end - 1]])).logits[0]
            log_probs = torch.log_softmax(logits.float(), dim=-1)
            expected += [
                -log_probs[position - 1 - begin, ids[position]].item() / math.log(2)
                for position in range(start, end)
            ]
        assert [score.bits for score in scores] == pytest.approx(expected, abs=1e-4)
        assert "".join(text[score.start : score.end] for score in scores).replace(" ", "") == (
            text.replace(" ", "")
        )

    def test_a_stride_longer_than_the_window_is_refused(self, tiny_model):
        tokenizer, model = tiny_model
        with pytest.raises(ValueError):
            token_surprisals(self.TEXT, tokenizer, model, window=16, stride=32)


class TestSlotAssociation:
    TEXT = (
        "At low tide the harbour seal hauls out near the gear trap and a tide-pool budget.\n\n"
        "Spring tides flood the quayside moorings."
    )

    def test_reads_the_second_words_characters_after_the_first_less_in_its_place(self, any_model):
        tokenizer, model = any_model
        words = tokens(self.TEXT)
        pairs = content_pairs(words)
        found = associations(self.TEXT, words, pairs, tokenizer, model, window=200, stride=100)
        expected = [
            expected_association(self.TEXT, words, pair, tokenizer, model) for pair in pairs
        ]
        assert found == pytest.approx(expected, abs=1e-4)
        assert max(abs(value) for value in expected) > 0.5

    def test_the_joiner_and_the_second_word_are_read_after_the_first_word(self, any_model):
        tokenizer, model = any_model
        words = tokens(self.TEXT)
        pairs = content_pairs(words)
        terms = slot_terms(self.TEXT, words, pairs, tokenizer, model, window=200, stride=100)
        separators = [self.TEXT[words[left].end : words[right].start] for left, right in pairs]
        assert set(separators) == {" ", "-"}
        for (left, right), separator, found in zip(pairs, separators, terms, strict=True):
            first = self.TEXT[: words[left].end]
            joiner = next_characters_bits(first, separator, tokenizer, model)
            unit = self.TEXT[words[right].start : words[right].end]
            after = character_bits(self.TEXT[: words[right].start], unit, tokenizer, model)
            assert (found.joiner, found.after_first) == pytest.approx((joiner, after), abs=1e-4)

    def test_a_token_holding_a_hyphen_and_the_next_words_start_is_split_between_the_terms(
        self, qwen_style_model
    ):
        tokenizer, model = qwen_style_model
        words = tokens(self.TEXT)
        pool = next(index for index, word in enumerate(words) if word.text == "pool")
        encoding = tokenizer(self.TEXT, add_special_tokens=False, return_offsets_mapping=True)
        holding = next(
            tokenizer.decode([token])
            for token, (_, end) in zip(encoding["input_ids"], encoding["offset_mapping"])
            if end > words[pool].start
        )
        assert holding.startswith("-p")
        for pair in [(pool - 1, pool), (pool, pool + 1)]:
            found = associations(self.TEXT, words, [pair], tokenizer, model, window=200, stride=100)
            expected = expected_association(self.TEXT, words, pair, tokenizer, model)
            assert found == pytest.approx([expected], abs=1e-4)

    def test_a_pair_opening_a_later_paragraph_keeps_the_paragraph_break_before_its_slot(
        self, any_model
    ):
        tokenizer, model = any_model
        words = tokens(self.TEXT)
        spring = next(index for index, word in enumerate(words) if word.text == "Spring")
        found = associations(
            self.TEXT, words, [(spring, spring + 1)], tokenizer, model, window=200, stride=100
        )
        tides = words[spring + 1]
        expected = character_bits(
            self.TEXT[: tides.start], "tides", tokenizer, model
        ) - character_bits(self.TEXT[: words[spring].start], "tides", tokenizer, model)
        assert self.TEXT[: words[spring].start].endswith("budget.\n\n")
        assert found == pytest.approx([expected], abs=1e-4)

    def test_both_terms_of_a_pair_come_from_the_window_that_scores_its_second_word(self, any_model):
        tokenizer, model = any_model
        text = " ".join([self.TEXT.replace("\n\n", " ")] * 3)
        words = tokens(text)
        pairs = content_pairs(words)
        window, stride = 24, 8
        found = associations(text, words, pairs, tokenizer, model, window=window, stride=stride)
        encoding = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        ends = [0, *(end for _, end in encoding["offset_mapping"])]
        layout = window_layout(len(ends), window, stride)
        straddling = 0
        expected = []
        for left, right in pairs:
            first = next(index for index, end in enumerate(ends) if end > words[left].start)
            last = next(index for index, end in enumerate(ends) if end >= words[right].end)
            begin, start, _ = next(entry for entry in layout if entry[1] <= last < entry[2])
            straddling += first < start
            expected.append(
                bounded_association(text, words, (left, right), tokenizer, model, begin=begin)
            )
        assert straddling > 0 and layout[-1][0] > 0
        assert found == pytest.approx(expected, abs=1e-4)

    def test_sliding_windows_give_the_same_values_as_one_window_on_a_short_text(self, any_model):
        tokenizer, model = any_model
        words = tokens(self.TEXT)
        pairs = content_pairs(words)
        one = associations(self.TEXT, words, pairs, tokenizer, model, window=200, stride=200)
        many = associations(self.TEXT, words, pairs, tokenizer, model, window=200, stride=7)
        assert many == pytest.approx(one, abs=1e-4)
        assert len(one) == len(pairs)

    def test_a_pair_with_an_accented_word_is_scored_like_any_other(self, any_model):
        tokenizer, model = any_model
        text = "The quiet café terrace faces a naïve reader across the square."
        words = tokens(text)
        pairs = content_pairs(words)
        phrases = {text[words[left].start : words[right].end] for left, right in pairs}
        assert {"quiet café", "café terrace", "naïve reader"} <= phrases
        found = associations(text, words, pairs, tokenizer, model, window=200, stride=100)
        expected = [expected_association(text, words, pair, tokenizer, model) for pair in pairs]
        assert found == pytest.approx(expected, abs=1e-4)


class TestWordBits:
    def test_sums_model_tokens_into_words_and_ignores_punctuation(self):
        text = "calm harbour."
        scores = [TokenScore(0, 4, 1.0), TokenScore(5, 8, 2.0), TokenScore(8, 12, 0.5)]
        scores.append(TokenScore(12, 13, 9.0))
        assert word_bits(text, tokens(text), scores) == [1.0, 2.5]

    def test_a_model_token_that_starts_on_a_hyphen_goes_to_the_word_it_reaches(self):
        text = "tide-pool"
        scores = [TokenScore(0, 4, 1.0), TokenScore(4, 6, 2.0), TokenScore(6, 9, 0.5)]
        assert word_bits(text, tokens(text), scores) == [1.0, 2.5]

    def test_a_model_token_over_two_word_starts_counts_for_both(self):
        text = "tide-pool crab"
        scores = [TokenScore(0, 9, 3.0), TokenScore(9, 14, 1.0)]
        assert word_bits(text, tokens(text), scores) == [3.0, 3.0, 1.0]

    def test_a_word_no_model_token_starts_in_is_an_error(self):
        text = "calm harbour"
        with pytest.raises(ValueError):
            word_bits(text, tokens(text), [TokenScore(0, 4, 1.0)])


class TestHotspots:
    def test_robust_z_uses_median_and_scaled_mad(self):
        z = robust_z([1.0, 2.0, 3.0, 4.0, 100.0])
        assert z[2] == pytest.approx(0.0)
        assert z[4] == pytest.approx(97 / 1.4826)

    TEXT = "The calm harbour sheltered the fishing fleet and one gear trap overnight, as we owe."

    @pytest.fixture
    def scored(self):
        words = tokens(self.TEXT)
        return words, [
            HOTSPOT_BITS.get(word.text, 5.0 + 0.1 * index) for index, word in enumerate(words)
        ]

    def test_standardizes_content_words_only(self, scored):
        words, scores = scored
        z = content_z(words, scores, min_content_words=5)
        assert {words[index].text for index in z} == {
            "calm",
            "harbour",
            "sheltered",
            "fishing",
            "fleet",
            "gear",
            "trap",
            "overnight",
            "owe",
        }
        assert max(z, key=z.get) == [word.text for word in words].index("trap")

    def test_pair_hotspots_need_the_outlier_to_end_a_content_pair(self, scored):
        words, scores = scored
        found = hotspots(words, scores, threshold=3.0, min_content_words=5, pairs_only=True)
        assert [self.TEXT[spot.start : spot.end] for spot in found] == ["gear trap"]

    def test_word_hotspots_take_any_outlier_with_the_word_before_it(self, scored):
        words, scores = scored
        found = hotspots(words, scores, threshold=3.0, min_content_words=5, pairs_only=False)
        assert [self.TEXT[spot.start : spot.end] for spot in found] == ["gear trap", "we owe"]

    def test_a_document_below_the_content_word_floor_gets_no_hotspots(self):
        words = tokens("A gear trap.")
        assert content_z(words, [1.0, 2.0, 40.0], min_content_words=5) == {}
        for pairs_only in (True, False):
            found = hotspots(
                words, [1.0, 2.0, 40.0], threshold=3.0, min_content_words=5, pairs_only=pairs_only
            )
            assert found == []
