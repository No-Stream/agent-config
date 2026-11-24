"""Small causal language models, built offline, for the tests of code that scores text with one:
a GPT-2-style tokenizer and model, and one with Qwen's pre-tokenizer and architecture."""

from __future__ import annotations

import torch
from tokenizers import Regex, Tokenizer, decoders, models, pre_tokenizers, processors, trainers
from transformers import (
    GPT2Config,
    GPT2LMHeadModel,
    PreTrainedTokenizerFast,
    Qwen3Config,
    Qwen3ForCausalLM,
)

CORPUS = (
    "The harbour seal hauls out on rocky shores at low tide. A calm harbour shelters the "
    "fishing fleet, and the lighthouse keeper rows out each morning to check the moorings. "
) * 4
HYPHENATED = "The tide-pool count rose. Each tide-pool held crabs. " * 10
QWEN_SPLIT = (
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*"
    r"|\s*[\r\n]+|\s+(?!\S)|\s+"
)


def byte_level_tokenizer(pre_tokenizer, corpus: str, vocab_size: int) -> PreTrainedTokenizerFast:
    backend = Tokenizer(models.BPE())
    backend.pre_tokenizer = pre_tokenizer
    backend.decoder = decoders.ByteLevel()
    backend.post_processor = processors.ByteLevel(trim_offsets=True)
    trainer = trainers.BpeTrainer(
        vocab_size=vocab_size,
        special_tokens=["<s>"],
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
    )
    backend.train_from_iterator([corpus], trainer)
    return PreTrainedTokenizerFast(tokenizer_object=backend, eos_token="<s>")


def gpt2_style_model() -> tuple[PreTrainedTokenizerFast, GPT2LMHeadModel]:
    """A GPT-2-style byte-level BPE tokenizer, which splits a hyphen from the next word, and a
    one-layer GPT-2 with random weights large enough to make its predictions uneven."""
    tokenizer = byte_level_tokenizer(pre_tokenizers.ByteLevel(add_prefix_space=False), CORPUS, 320)
    torch.manual_seed(0)
    config = GPT2Config(
        vocab_size=len(tokenizer),
        n_positions=256,
        n_embd=16,
        n_layer=1,
        n_head=2,
        initializer_range=0.5,
    )
    return tokenizer, GPT2LMHeadModel(config).eval()


def qwen_style_model() -> tuple[PreTrainedTokenizerFast, Qwen3ForCausalLM]:
    """A tokenizer with Qwen's pre-tokenizer, which joins a hyphen or other mark to the letters
    after it, so a token can hold a hyphen and the start of the next word, and a one-layer Qwen3
    with random weights."""
    pre_tokenizer = pre_tokenizers.Sequence(
        [
            pre_tokenizers.Split(Regex(QWEN_SPLIT), behavior="isolated"),
            pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False),
        ]
    )
    tokenizer = byte_level_tokenizer(pre_tokenizer, CORPUS + HYPHENATED, 360)
    torch.manual_seed(0)
    config = Qwen3Config(
        vocab_size=len(tokenizer),
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=1,
        num_attention_heads=2,
        num_key_value_heads=1,
        head_dim=8,
        max_position_embeddings=256,
        initializer_range=0.5,
    )
    return tokenizer, Qwen3ForCausalLM(config).eval()
