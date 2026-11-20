# AI-text detector scores

These scripts give every text in the writing evaluation a continuous score from four open AI-text detectors. The scores answer two questions: does a higher detector score go with worse writing among model-drafted texts, and does the write-plainly skill move a model's text toward careful human writing? Before either question, each detector has to pass a positive control: on the matched bheijden/slop corpus, does it score the human text on a topic as less AI-like than the model text on the same topic? A detector that cannot tell them apart says nothing about the rest.

## Detectors

| name | model | licence | runs on | score | more AI-like | window |
|---|---|---|---|---|---|---|
| `desklib` | [desklib/ai-text-detector-v1.01](https://huggingface.co/desklib/ai-text-detector-v1.01), DeBERTa-v3-large fine-tuned on RAID | MIT | CPU | log-odds of P(AI) | higher | 768 tokens |
| `gpttrace` | [nakas/gpttrace-v8s-1b](https://huggingface.co/nakas/gpttrace-v8s-1b), Ettin-1B fine-tuned on RAID, MAGE and 2026 model text | CC BY-SA 4.0 | CPU | machine logit minus human logit | higher | 512 tokens |
| `binoculars` | [Binoculars](https://github.com/ahans30/Binoculars), Falcon-7B observer and Falcon-7B-Instruct performer | BSD-3 (code), Apache-2.0 (models) | GPU | log-perplexity over cross-perplexity | lower | 512 tokens |
| `fast-detectgpt` | [Fast-DetectGPT](https://github.com/baoguangsheng/fast-detect-gpt) analytic criterion, Falcon-7B sampling and Falcon-7B-Instruct scoring | MIT (code), Apache-2.0 (models) | GPU | sampling discrepancy | higher | 512 tokens |

`desklib` is the most downloaded open classifier, but its training data is RAID, whose generators date from 2023. `gpttrace` is the only open classifier found whose training data includes frontier models from 2026; its card names rewrites by Claude Opus 5.5 and GPT-6.x. Its card reports near-perfect accuracy on a 2026 benchmark and few false positives on old web pages, all measured by its author, and it was published this November with no independent evaluation yet. `binoculars` and `fast-detectgpt` are zero-shot methods that need no training data. Both come from the same forward pass of the two Falcon models, so the second costs nothing extra. Their published tests use older generators, and on text that o1-Pro wrote and then humanized they caught few articles (Russell et al., ACL 2025). Each model is pinned to a revision in `scoring.py`.

Two candidates were left out. Open Pangram (EditLens) is CC BY-NC-SA, which rules out commercial use. SuperAnnotate's detector is under its own copyleft licence and needs its own package to run.

## How a text is scored

`scoring.prepare_text` turns each text into plain prose before any detector sees it. It drops markdown table rows, heading and list markers, bold and italic markers, link targets and backticks. It also removes invisible format characters and folds curly quotes, the ellipsis character and no-break spaces to ASCII. Those typographic forms come from the editor or publisher, so leaving them in would let a detector score the typesetting. Dashes stay. `gpttrace` also gets its card's lookalike-letter folding, which changes nothing in these texts.

A text longer than a detector's window is split at token boundaries into the fewest chunks that fit, all of nearly equal size, so a short last chunk never gets a score of its own. Each chunk is scored on its own. The text's `score` is the token-weighted mean of its chunk scores, and the record also keeps `chunk_max`, `chunk_min` and every chunk's score and token count. Texts here run from about 40 to 1,250 words, so they get one to three chunks.

The Binoculars and Fast-DetectGPT formulas follow the reference code; a check against both reference implementations on small models agreed to four decimal places.

## Running it

From this directory:

```sh
./rescore.sh
```

It rebuilds the manifest, scores every new or changed text with every detector, and writes the summaries to `.private/eval/detectors/` at the repo root. A text keeps its old score when its prepared text and the detector's window are unchanged, so adding texts and rerunning scores only the new ones. The SageMaker step waits for its job, which takes 10 to 30 minutes, so run the script in tmux. It runs the CPU step under `heavy`, a local job wrapper that caps threads and memory; set `CPU_LAUNCHER=""` to run it directly.

The steps, each also runnable alone with `uv run`:

| script | what it does |
|---|---|
| `manifest.py` | Lists every text with its id, corpus, arm, topic, register, word count and path in `manifest.jsonl` |
| `score_local.py` | Scores the texts with `desklib` and `gpttrace` on the CPU, one JSONL per detector |
| `sagemaker_job.py run` | Sends the texts that need Binoculars and Fast-DetectGPT scores to a SageMaker Processing job, waits, and merges the scores; `fetch --job <name>` merges a finished job's scores |
| `job_entry.py` | The code that runs inside the job |
| `summarize.py` | Prints the distributions by arm, the positive control and the spread among model texts; `--corpus bheijden` limits it to the public corpus |

The manifest's sources are the bheijden/slop corpus (fetched into `../.cache/` by `../false_flags.py`), and, where they exist, the voice samples in `.private/eval/human-private/`, the pairwise passages in `.private/eval/pairwise/generation/<task>/<pipeline>/final.md`, and new texts on the bheijden topics in `.private/eval/detector-texts/bheijden/<pair id>/<arm>.md`.

`sagemaker_job.py` reads its account settings from `.private/eval/detectors/sagemaker.toml`, a gitignored file with these keys: `profile`, `region`, `role_arn`, `s3_prefix`, `image_uri` (an AWS Hugging Face PyTorch training image with transformers 4.56 or newer), `instance_type` (one GPU with 40 GB or more holds both models at bfloat16), `volume_gb` and `max_runtime_s`. The texts go only to that account's S3 and SageMaker.

The tests cover the manifest, the chunking, which texts get rescored, and the direction of the positive control for each detector:

```sh
uv run --no-project --python 3.12 --with pytest --with scipy python -m pytest tests
```

## Results on the public corpus

Only `gpttrace` passes the positive control. On 21 of the 24 bheijden topics, it scores the human text as less AI-like than the `claude-opus-5` text on the same topic. The other three detectors put the human text on the more AI-like side on most topics, so the later questions cannot use them. The runs are from 2026-11-20, and `summarize.py --corpus bheijden` prints the full tables.

| detector | topics where the human text is less AI-like (95% interval) | mean human minus model score (95% interval) | model texts past the cut-off | human texts past the cut-off |
|---|---|---|---|---|
| `gpttrace` | 21/24 (0.69 to 0.96) | -4.61 (-6.51 to -2.70) | 4/24 | 2/24 |
| `desklib` | 5/24 (0.09 to 0.40) | 1.71 (0.57 to 2.84) | 1/24 | 6/24 |
| `binoculars` | 9/24 (0.21 to 0.57) | -0.029 (-0.047 to -0.011) | 0/24 | 0/24 |
| `fast-detectgpt` | 9/24 (0.21 to 0.57) | 0.78 (0.28 to 1.27) | no cut-off | no cut-off |

The share interval is Wilson's, and the mean interval is a paired t interval. Score units differ by detector, as in the detector table. For `binoculars` a lower score is more AI-like, so its negative mean difference also points the wrong way. Each cut-off is the detector's published one.

The next table splits the positive control by when the human text was published. It also gives the spread of scores among the 28 model texts, which are the 24 corpus texts plus the 4 that today's model has written so far from the same briefs. The last column is the median standard deviation between the chunks of one long text, which measures the noise in a single chunk's score.

| detector | human less AI-like, human text before 1930 | human less AI-like, human text from 2002 to 2021 | standard deviation among model texts | standard deviation between chunks of a text |
|---|---|---|---|---|
| `gpttrace` | 8/8 | 13/16 | 3.47 | 1.47 |
| `desklib` | 1/8 | 4/16 | 3.08 | 0.84 |
| `binoculars` | 6/8 | 3/16 | 0.026 | 0.022 |
| `fast-detectgpt` | 6/8 | 3/16 | 0.74 | 0.63 |

`gpttrace` still separates on the modern texts, with a smaller margin than on the old ones. Its scores of model texts are spread out, and only 6 of the 28 pass its 1% false-positive cut-off, so it has room to rank model texts against each other. For `binoculars` and `fast-detectgpt`, the noise between chunks is most of the spread among model texts. Their ranking of one model text against another would be mostly noise even if they had passed the control.

### Threats

- Detector training data can contain the human texts. These are published texts from before 2022, and `gpttrace` lists Wikipedia, PubMed Central, Project Gutenberg and pre-2022 web pages in its training data, so its separation may be partly memory of these exact texts. The Falcon models were trained on a web crawl, and the Binoculars authors report that text the model has memorized scores as machine-written, which would push `binoculars` and `fast-detectgpt` toward the inversion seen here. Texts written after the detectors were trained, such as unpublished human writing, are the check on both.
- One model family wrote every model text, and every human text is a published excerpt of 600 to 1,200 words. The pairwise passages are about 250 words, so each gets one chunk, and its score carries the full noise between chunks shown above.
- The human and model texts on a topic have similar lengths (medians of 1,048 and 1,000 words), so length does not explain the paired differences.
- `gpttrace`'s published accuracy is measured by its author only.
