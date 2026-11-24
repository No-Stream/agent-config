# Coined word pairs: unattested bigrams and surprisal hotspots

These scripts test whether a deterministic check can find the coined word pairs that Clark, Martin and Mahowald ("Why is AI-generated language so hard to understand?", arXiv:2610.29162, 2026) find frontier models use more often than people do, such as "reader-patience budget" or "a gear trap". No word list can name such pairs in advance, so each check scores every pair of adjacent content words instead.

Each check is judged on two questions. Are the pairs it flags coined pairs that a reader would have to stop and decode? Does it find the phrases that the paper and the owner pointed to? How often it flags careful human writing is its cost, measured on the held-out public pages that "Rules for model tells from public catalogs" in `../README.md` describes. The unattested-bigram check and the plain surprisal checks fail on what they flag: most flags are ordinary phrases, names or identifiers. The pair association under a model of 0.6 billion parameters or more comes closest. None of its flags on human text are coined, and its coined flags on model text are all labels in the owner's passages. It rarely fires, though: it flags the held-out pages about half as often as the median house-style rule does, and it finds none of the phrases that the paper or the owner pointed to. A check on hyphenated compounds alone, the second part's surprisal after the first part and the hyphen, flags the owner's passages far more often than human text. A full second labeling found most of those flags to be established technical compounds, though, so it is not added either. A coined compound is judged in context by `prose-reviewer`, whose `shorthand` category covers a label or compressed noun phrase coined during the work.

## The checks

The unattested-bigram check looks each pair up in a reference corpus and flags a pair that the reference never contains. The paper reports the rate of such pairs against a sample of about 500,000 words (its Section 3.1 and Appendix B.2). Here each such pair is a candidate finding, checked against a sample of that size and against the whole reference.

The surprisal checks run an open language model on the CPU and give every word its surprisal in bits, given the text before it. One check flags a word whose surprisal is far above the document's own median, in robust standard deviations. Another subtracts the word's surprisal as a lone word in the reference first, so that a rare word scores low unless its context makes it even less likely.

The pair association asks how much the first word of a pair lowers the probability of the second. It takes the second word's surprisal after the first word, less the surprisal that the second word would have had in the first word's place. Both terms score the letters of the second word given all the text before them, including the space, hyphen or paragraph break in front of it. A model token that holds both a hyphen and the start of the word therefore adds the hyphen to neither term. Both terms read the same stretch of preceding text, and one pass over the text gives both, with the second word appended in the first word's place. A pair scores high when the first word makes the second unlikely, as "gear" might for "trap".

The hyphen checks read only the pairs that a hyphen joins, from the same pass. One takes the surprisal of the hyphen itself after the first part, from the model tokens that start with a hyphen. The other takes the second part's surprisal after the first part and the hyphen, which is the pair association's first term alone.

## Results

The runs are from 2026-11-23, with the code at commit f5abf7b and three base models of growing size: SmolLM2-135M, Qwen3-0.6B-Base and Qwen3-1.7B-Base. The surprisal rows use SmolLM2-135M; the larger models gave the same picture for surprisal. The reference is WikiText-103, English Wikipedia's Good and Featured articles.

The table gives flags per 1,000 words, counted as `../README.md` counts words, with the held-out pages flagged in parentheses. The median house-style rule flags those pages 0.13 times per 1,000 words.

- The in-sample human texts are the 31 of `../README.md`.
- The model drafts are 72 drafts on the matched corpus's topics: its own model texts and the evaluation's drafts with and without the skill.
- The owner's passages are 260 model-written passages that the owner commented on.
- A hand-read flag counts as coined when a reader would have to stop and decode the pair. The reader of the table's samples also counted a writer's own name for one of their artifacts, such as a check or a notebook, but not the public name of a product, tool, place or person. The samples hold about 30 flags from each side, or most or all of them when there were fewer.
- The paper marks 14 phrases in the example sentences of its Table 2 and Figure 1. The owner objected to 23 phrases as coined or opaque in his passages.

| check | held-out pages | in-sample human | model drafts | owner's passages | coined, of model flags read | coined, of human flags read | paper's phrases found | owner's phrases found |
|---|---|---|---|---|---|---|---|---|
| unattested pair, 500,000-word sample | 106.5 (14/14) | 108.6 | 108.2 | 123.3 | not read | not read | 11/14 | 16/23 |
| unattested pair, whole reference | 73.9 (14/14) | 62.9 | 66.8 | 103.0 | 6/29 | 0/29 | 11/14 | 14/23 |
| surprisal less unigram surprisal, z above 3 | 1.79 (13/14) | 2.06 | 1.06 | 2.54 | 0/28 | 0/33 | 0/14 | 0/23 |
| surprisal less unigram surprisal, z above 5 | 0.15 (5/14) | 0.09 | 0.04 | 0.16 | 0/7 | 0/10 | 0/14 | 0/23 |
| pair association above 8 bits, SmolLM2-135M | 0.35 (9/14) | 0.16 | 0.07 | 0.61 | not read | not read | 0/14 | 0/23 |
| pair association above 8 bits, Qwen3-0.6B-Base | 0.07 (3/14) | 0.11 | 0.07 | 0.37 | 5/12 | 0/8 | 0/14 | 0/23 |
| pair association above 8 bits, Qwen3-1.7B-Base | 0.07 (3/14) | 0.09 | 0.03 | 0.20 | 3/11 | 0/6 | 0/14 | 0/23 |
| the hyphen's own surprisal above 8 bits, SmolLM2-135M | 0.20 (7/14) | 0.18 | 0.07 | 0.69 | 12/23 | 0/18 | 0/14 | 0/23 |
| the hyphen's own surprisal above 8 bits, Qwen3-0.6B-Base | 0.18 (6/14) | 0.09 | 0.03 | 0.98 | 13/27 | 0/13 | 0/14 | 0/23 |
| the hyphen's own surprisal above 10 bits, Qwen3-1.7B-Base | 0.13 (5/14) | 0.07 | 0.01 | 0.04 | 1/2 | 0/9 | 0/14 | 0/23 |
| second part after the hyphen above 14 bits, SmolLM2-135M | 0.15 (6/14) | 0.18 | 0.10 | 4.09 | 12/30 | 0/14 | 2/14 | 2/23 |
| second part after the hyphen above 14 bits, Qwen3-0.6B-Base | 0.09 (4/14) | 0.21 | 0.22 | 3.07 | 10/30 | 0/13 | 1/14 | 2/23 |
| second part after the hyphen above 12 bits, Qwen3-1.7B-Base | 0.09 (3/14) | 0.25 | 0.21 | 4.34 | 19/30 | 0/15 | 2/14 | 4/23 |

All the coined pairs among the model flags came from the owner's passages, and most were a writer's internal labels. None came from the drafts on public topics, so the pair association finds working shorthand more than it finds a model's way of writing. Under Qwen3-1.7B-Base, 3 of the 5 flags on the owner's passages are coined.

Of all the checks, the second part's surprisal after the hyphen best tells the owner's passages from human writing. Under Qwen3-1.7B-Base, it flags his passages dozens of times as often as the held-out pages. Two readers, both models, disagreed on how many of those flags are coined. The first labeled the samples in the table and counted a writer's names for their own models, data, metrics and checks as coined. The second, reading as someone who knows machine learning, statistics and software engineering, labeled every flag under Qwen3-1.7B-Base, blind and in shuffled order. It called most of the first reader's coined flags established technical compounds or names, found all of its own coined flags in the owner's passages, and found their share rising little with the threshold:

| threshold | flags labeled | coined | coined or a writer's name for their own artifact |
|---|---|---|---|
| 12 bits | 174 | 9% | 20% |
| 14 bits | 97 | 6% | 18% |
| 16 bits | 46 | 11% | 24% |
| 18 bits | 22 | 14% | 27% |
| 20 bits | 9 | 22% | 44% |

Four of the second reader's 15 coined flags at 12 bits are phrases that the owner objected to, which its instructions gave as examples, so its share without them is lower still. The score does not separate coined labels from the field's own compounds, which also surprise a model after the hyphen, so it is not added. On the same documents, `hyphen-stack` fires on a few of its flags and `coined-label` on one. Neither rule finds any of the known phrases, while this check finds four of the owner's six hyphenated phrases and both of the paper's.

The hyphen's own surprisal is not added. Under the smaller models it flags the owner's passages several times as often as the held-out pages, but it flags those pages more often than the median house rule does. Under Qwen3-1.7B-Base it flags the owner's passages less often than the held-out pages, and under no model does it find any of the owner's phrases.

The unattested check finds most of the known phrases only because it flags a phrase in almost every sentence. A larger reference does not fix that, because Wikipedia rarely writes ordinary technical pairs such as "exact thing" or "improving availability". The share of content-word pairs that the reference lacks falls slowly as it grows:

| reference words | held-out pages | human texts on the matched topics | model drafts on the matched topics |
|---|---|---|---|
| 500,000 | 94% | 91% | 92% |
| 8 million | 79% | 69% | 74% |
| 84 million | 59% | 46% | 51% |

The model drafts lack more pairs than the human texts on the same topics, as the paper found. The gap is a rate over whole texts and is far too small to flag single phrases.

The surprisal checks miss the known phrases because a coinage built from common words does not surprise a language model. The most surprising word of each known phrase sits at about the 80th percentile of its document's words. Their flags above the house-rule rate are names, identifiers, typos and dialect. The pair association under the Qwen models ranks the known phrases' pairs at a median of the 73rd and 74th percentiles. The owner's phrases are opaque in meaning, while each of their words is likely after the one before it.

| step | CPU seconds per 1,000 words | download |
|---|---|---|
| pair association, SmolLM2-135M | 4.2 | 269 MB |
| pair association, Qwen3-0.6B-Base | 11.3 | 1.2 GB |
| pair association, Qwen3-1.7B-Base | 21.4 | 3.4 GB |
| unattested-pair lookup, once the reference is counted | under 0.01 | 314 MB of WikiText-103 |
| counting the whole reference's 6.0 million distinct content-word pairs, once | about 240 CPU seconds in all | |

Surprisal scoring alone takes about a fifth less CPU time than the pair association.

The results have these limits:

- A model labeled the sampled flags, and the samples are small. For the second part after the hyphen, a second model labeled every flag at one threshold and disagreed with the first. Neither reader saw the pool, but the context of one of the owner's passages shows where it came from.
- Each threshold comes from a grid tried on these same texts, and each hyphen threshold is the grid value whose held-out rate is nearest the median house rule's. The 8-bit threshold of the pair association comes from the same kind of grid. At that threshold the larger models flag the held-out pages about half as often as the median house rule. The next lower threshold flags them more often and still finds none of the owner's phrases.
- Only one reference was tried, and Wikipedia's register is far from technical writing. A web-scale reference would hold more ordinary pairs, but the share it lacks fell by little more than a third over a 170-fold increase in size.
- The surprisal checks skip a document too short for its own median and spread, under 25 content words. That skips a quarter of the owner's passages but few of their words.
- The CPU times come from a busy shared machine.
- The models run in bfloat16, their checkpoints' precision, which is about twice as fast on the CPU as float32. On a held-out page, the pair association moved by a small fraction of a bit between the two precisions, and no flag changed.

## Running it

| file | what it does |
|---|---|
| `prose.py` | The words and word pairs of a document's prose blocks, prepared as the syntax linter prepares them: markup dropped, inline code, URLs, paths, identifiers and math read as a placeholder word that is never a content word, and a line break at an arrow or emoji. Words follow the linter's word rule widened to letters in any script, a hyphenated word splits into its parts, and pairs join only content words that one space or a hyphen separates |
| `reference.py` | Reads WikiText-103 (`Salesforce/wikitext` on the Hugging Face Hub, CC BY-SA 3.0), undoes its tokenization markers, closes the space it puts before punctuation, and draws the 500,000-word sample of whole paragraphs |
| `bigrams.py` | Counts a reference's content pairs and words, and flags a document's unattested pairs |
| `surprisal.py` | Token surprisal in sliding windows, word scores, the pair terms (each pair's two word terms and the bits of the space or hyphen joining it), and hotspots against the document's median and median absolute deviation |
| `measure.py` | Builds the sample, scores documents under one model, and writes flag rates, recall on known phrases, every flag with its context, and the CPU cost |

From this directory, with each model and dataset at its latest revision on the Hub:

```sh
uv run --upgrade measure.py reference
uv run --upgrade measure.py score --manifest docs.jsonl --model Qwen/Qwen3-1.7B-Base --out ../.cache/surprisal/
uv run --upgrade measure.py analyze --manifest docs.jsonl --model Qwen/Qwen3-1.7B-Base --out ../.cache/surprisal/ \
  --targets targets.jsonl --pool "human=public/human" "model=public/model"
```

`reference` writes the sample to `../.cache/reference/`, and the example writes the scores and flags to `../.cache/surprisal/`. Both are gitignored, and the flags must stay there, because each one quotes its document. A manifest line names a document's `corpus`, `arm`, `doc` and `path`; a target line names a document `id` (`corpus/arm/doc`), a `phrase` in it and the phrase's `kind`. `score` keeps the scores it wrote before and scores only the documents that are new or whose words changed. It runs one single-threaded worker per process (`--workers`), so set `OMP_NUM_THREADS=1` and give the run as many CPU cores as workers. `analyze` counts the documents' pairs and words in the whole WikiText-103 train split once and caches the counts in `--out`.

The tests need CPU torch, transformers, tokenizers, pyarrow and the Hub client, and build small tokenizers and models offline with `tests/language_models.py`:

```sh
uv run --upgrade --no-project --python 3.12 --with pytest --with torch --with transformers --with tokenizers \
  --with pyarrow --with huggingface-hub --index https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match python -m pytest tests
```
