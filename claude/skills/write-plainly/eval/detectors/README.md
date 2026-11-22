# AI-text detector scores

These scripts give every text in the writing evaluation a continuous score from four open AI-text detectors. The scores answer two questions: does a higher detector score go with worse writing among model-drafted texts, and does the write-plainly skill move a model's text toward careful human writing? Two separate checks on the matched bheijden/slop corpus say what a detector can be used for. The provenance check asks whether it scores the published human text on a topic as less AI-like than the model text on the same topic. The planted check asks whether its score rises when the same model draft is made worse, read against a neutral rewording of the same sentences, or given inserted AI tells. Only the planted check tests the first question; passing the provenance check shows that a detector can tell these published human texts from model text, which is a different claim.

## Detectors

| name | model | license | runs on | score | more AI-like | window |
|---|---|---|---|---|---|---|
| `desklib` | [desklib/ai-text-detector-v1.01](https://huggingface.co/desklib/ai-text-detector-v1.01), DeBERTa-v3-large fine-tuned on RAID | MIT | CPU | log-odds of P(AI) | higher | 768 tokens |
| `gpttrace` | [nakas/gpttrace-v8s-1b](https://huggingface.co/nakas/gpttrace-v8s-1b), Ettin-1B fine-tuned on RAID, MAGE and 2026 model text | CC BY-SA 4.0 | CPU | machine logit minus human logit | higher | 512 tokens |
| `binoculars` | [Binoculars](https://github.com/ahans30/Binoculars), Falcon-7B observer and Falcon-7B-Instruct performer | BSD-3 (code), Apache-2.0 (models) | GPU | log-perplexity over cross-perplexity | lower | 512 tokens |
| `fast-detectgpt` | [Fast-DetectGPT](https://github.com/baoguangsheng/fast-detect-gpt) analytic criterion, Falcon-7B sampling and Falcon-7B-Instruct scoring | MIT (code), Apache-2.0 (models) | GPU | sampling discrepancy | higher | 512 tokens |

`desklib` is the most downloaded open classifier, but its training data is RAID, whose generators date from 2023. `gpttrace` is the only open classifier found whose training data includes frontier models from 2026; its card names rewrites by Claude Opus 5.5 and GPT-6.x. Its card reports near-perfect accuracy on a 2026 benchmark and few false positives on old web pages, all measured by its author, and it was published this November with no independent evaluation yet. `binoculars` and `fast-detectgpt` are zero-shot methods that need no training data. Both come from the same forward pass of the two Falcon models, so the second costs nothing extra. Their published tests use older generators, and on text that o1-Pro wrote and then humanized they caught few articles (Russell et al., ACL 2025). Each model is pinned to a revision in `scoring.py`.

Two candidates were left out. Open Pangram (EditLens) is CC BY-NC-SA, which rules out commercial use. SuperAnnotate's detector is under its own copyleft license and needs its own package to run.

## The texts on the bheijden topics

The bheijden/slop corpus pairs a published human text with a model text on each of 24 topics. The other arms were made for this evaluation from the same briefs, and every model call in them was Claude Opus 5.5.

| arm | what it is |
|---|---|
| `human` | the published human text, 8 from before 1930 and 16 from 2002 to 2021 |
| `corpus-claude-opus-5` | the corpus's own model text |
| `no-skill` | a draft from the brief alone |
| `skill-draft` | a draft from the brief with the write-plainly skill |
| `degraded` | the skill draft after one more model call rewrote about a third of its sentences worse and added padding and a recap |
| `neutral-rewrite` | the skill draft with the same sentences reworded plainly by one model call, every name, number and claim kept |
| `tells-injected` | the skill draft with tells inserted by code: em dashes, announcing phrases, "not X but Y" sentences, a rule-of-three sentence and a stock moral |

The last three are the planted controls. `degraded` minus `neutral-rewrite` isolates the drop in quality from the fact that a model reworded a third of the sentences, and `neutral-rewrite` minus `skill-draft` shows what the rewording alone does.

## How a text is scored

`scoring.prepare_text` turns each text into plain prose before any detector sees it. It drops every line that starts with a pipe, the form of every markdown table in these texts, and removes heading and list markers, bold and italic markers, link targets and backticks. It also removes invisible format characters and folds curly quotes, the ellipsis character and no-break spaces to ASCII. Those typographic forms come from the editor or publisher, so leaving them in would let a detector score the typesetting. Dashes stay. `gpttrace` also gets its card's normalization, which drops variation selectors and folds lookalike letters; it changes nothing in these texts.

A text longer than a detector's window is split at token boundaries into the fewest chunks that fit, all of nearly equal size, so a short last chunk never gets a score of its own. Each chunk is scored on its own, and a chunk whose own tokenization runs past the window stops the run, since cutting it would drop its tail. The text's `score` is the token-weighted mean of its chunk scores, and the record also keeps `chunk_max`, `chunk_min` and every chunk's score and token count. Texts here run from about 40 to 1,300 words, so they get one to four chunks.

The Binoculars and Fast-DetectGPT formulas follow the reference code; `tests/test_job_entry.py` checks them on fixed logits against values from both reference implementations.

## Running it

From this directory:

```sh
./rescore.sh
```

It rebuilds the manifest, scores every new or changed text with `desklib` and `gpttrace` on the CPU, and writes the summaries to `.private/eval/detectors/` at the repo root. A text keeps its old score when its prepared text, the model revision and the detector's window are unchanged, so adding texts and rerunning scores only the new ones. The CPU step runs under `heavy`, a local job wrapper that caps threads, memory and run time, and the other steps run under `heavy --light`; set `CPU_LAUNCHER=""` or `LIGHT_LAUNCHER=""` to run those steps directly. Scoring many new texts on the CPU takes a while, so start the script in tmux:

```sh
tmux new-session -d -s rescore "set -o pipefail; ./rescore.sh 2>&1 | tee ~/logs/rescore.log; echo EXITCODE=\$? >> ~/logs/rescore.log"
```

Binoculars and Fast-DetectGPT need a GPU, so they run on their own, in a SageMaker Processing job that takes 10 to 30 minutes. Rerun `./rescore.sh` afterwards to put their scores in the summaries. Their last run, on 2026-11-20, came before the pairwise passages were regenerated, so those passages have no current Binoculars or Fast-DetectGPT score. `summarize.py` leaves out any score of an earlier version of a text, and each detector's section says how many texts have a current score. The skill itself runs no detector, and the pairwise analysis compares the person's grades with `desklib` and `gpttrace` scores only, so nothing waits on this job.

```sh
heavy --light -- uv run sagemaker_job.py run
```

The steps, each also runnable alone with `uv run`:

| script | what it does |
|---|---|
| `manifest.py` | Lists every text with its id, corpus, arm, topic, register, word count and path in `manifest.jsonl` |
| `score_local.py` | Scores the texts with `desklib` and `gpttrace` on the CPU, one JSONL per detector |
| `sagemaker_job.py run` | Sends the texts that need Binoculars and Fast-DetectGPT scores to a SageMaker Processing job, waits, and merges the scores; `fetch --job <name>` merges a finished job's scores |
| `job_entry.py` | The code that runs inside the job |
| `summarize.py` | Prints an overview of both checks, then for each detector how many texts have a current score, the distributions by arm, the provenance check split by the human text's date, the skill against no skill, the planted contrasts, and the spread among model drafts and between the chunks of one draft; `--corpus bheijden` limits it to the public corpus |

The manifest's sources are the bheijden/slop corpus (fetched into `../.cache/` by `../false_flags.py`), and, where they exist, the voice samples in `.private/eval/human-private/`, the pairwise passages in `.private/eval/pairwise/generation/<task>/<pipeline>/final.md`, and new texts on the bheijden topics in `.private/eval/detector-texts/bheijden/<pair id>/<arm>.md`.

`sagemaker_job.py` reads its account settings from `.private/eval/detectors/sagemaker.toml`, a gitignored file with these keys: `profile`, `region`, `role_arn`, `s3_prefix`, `image_uri` (an AWS Hugging Face PyTorch training image with transformers 4.56 or newer), `instance_type` (one GPU with 40 GB or more holds both models at bfloat16), `volume_gb` and `max_runtime_s`. The texts go only to that account's S3 and SageMaker.

The tests cover the manifest, the chunking, which texts get rescored, the summary tables and their direction for each detector, how a finished SageMaker job's scores are merged, and the Binoculars and Fast-DetectGPT formulas. They need CPU torch, transformers and boto3:

```sh
uv run --no-project --python 3.12 --with pytest --with scipy --with boto3 --with torch \
  --with transformers==5.23.0 --index https://download.pytorch.org/whl/cpu python -m pytest tests
```

## Results on the public corpus

The two checks pick different detectors. `gpttrace` is the only detector that scores the human text as less AI-like than the model text on most topics, but its score barely moves when the same draft is made worse. `desklib` gets provenance backwards, yet its score rises on all 24 topics when the draft is degraded or given inserted tells, and not when the same sentences are reworded neutrally. So on the planted control, `desklib` tracks bad writing and `gpttrace` tracks it only weakly. `binoculars` and `fast-detectgpt` have scores only for the human texts, the corpus model texts and the first 4 `no-skill` texts, so they appear in the provenance check alone. The runs are from 2026-11-20, and `summarize.py --corpus bheijden` prints the full tables.

| detector | provenance: human less AI-like than the corpus model text | `degraded` more AI-like than `neutral-rewrite` | `tells-injected` more AI-like than `skill-draft` | `neutral-rewrite` more AI-like than `skill-draft` |
|---|---|---|---|---|
| `desklib` | 5/24 | 24/24, +6.38 (5.40 to 7.36) | 24/24, +1.63 (1.34 to 1.91) | 10/24, +0.27 (-0.16 to 0.69) |
| `gpttrace` | 21/24 | 15/24, +0.63 (0.21 to 1.05) | 19/24, +0.36 (0.10 to 0.63) | 7/24, -0.23 (-0.53 to 0.07) |
| `binoculars` | 9/24 | not scored | not scored | not scored |
| `fast-detectgpt` | 9/24 | not scored | not scored | not scored |

Each cell counts topics, and the planted columns add the mean paired difference in the detector's own units with its 95% paired t interval. The size of a move matters as much as its count. `desklib`'s rise from `neutral-rewrite` to `degraded` is about twice the standard deviation of its scores among ordinary model drafts and six times the noise of a neutral rewording. `gpttrace`'s is about a quarter of its standard deviation among drafts and smaller than the noise of a neutral rewording; both figures are in the spread table below.

### Provenance

| detector | human less AI-like (95% interval) | human text before 1930 | human text from 2002 to 2021 | mean model minus human score (95% interval) | model texts past the cut-off | human texts past the cut-off |
|---|---|---|---|---|---|---|
| `gpttrace` | 21/24 (0.69 to 0.96) | 8/8 | 13/16 | +4.61 (2.70 to 6.51) | 4/24 | 2/24 |
| `desklib` | 5/24 (0.09 to 0.40) | 1/8 | 4/16 | -1.71 (-2.84 to -0.57) | 1/24 | 6/24 |
| `binoculars` | 9/24 (0.21 to 0.57) | 6/8 | 3/16 | +0.029 (0.011 to 0.047) | 0/24 | 0/24 |
| `fast-detectgpt` | 9/24 (0.21 to 0.57) | 6/8 | 3/16 | -0.78 (-1.27 to -0.28) | no cut-off | no cut-off |

The model text here is `corpus-claude-opus-5`. The share interval is Wilson's, and the mean interval is a paired t interval. Score units differ by detector, as in the detector table. For `binoculars` a lower score is more AI-like, so its positive mean difference also points the wrong way. Each cut-off is the detector's published one. `gpttrace` still separates on the modern texts, with a smaller margin than on the old ones.

### The skill

| detector | human less AI-like than `no-skill` | human less AI-like than `skill-draft` | `skill-draft` more AI-like than `no-skill` | mean `skill-draft` minus `no-skill` (95% interval) |
|---|---|---|---|---|
| `gpttrace` | 24/24 | 20/24 | 11/24 | +0.06 (-0.79 to 0.90) |
| `desklib` | 14/24 | 11/24 | 10/24 | -1.03 (-2.11 to 0.05) |

Against today's drafts `gpttrace` separates the human text on every topic for `no-skill` and on all but four for `skill-draft`, about as often as against the corpus model text, where it misses three. Paired by topic, neither detector separates the skill drafts from the drafts written without the skill. The skill drafts are also shorter, with a median of 949 words against 994.

### Spread and noise

| detector | standard deviation among ordinary model drafts | ordinary drafts past the cut-off | noise of a neutral rewording | the same on 250-word passages | spread between the chunks of one draft |
|---|---|---|---|---|---|
| `gpttrace` | 2.80 (72 drafts) | 16/72 | 0.71 | 0.62 | 1.05 |
| `desklib` | 3.03 (72 drafts) | 7/72 | 1.00 | 0.38 | 0.83 |
| `binoculars` | 0.026 (28 drafts) | 0/28 | not scored | not scored | 0.021 |
| `fast-detectgpt` | 0.74 (28 drafts) | no cut-off | not scored | not scored | 0.58 |

The ordinary drafts are `corpus-claude-opus-5`, `no-skill` and `skill-draft`, and the first two columns and the last cover them alone, with the planted controls and the human texts left out. The rewording column is the standard deviation over the 24 topics of `neutral-rewrite` minus `skill-draft`, which is how far a score moves when one model call rewords about a third of a draft's sentences plainly, with every fact kept. It measures the noise of a fact-preserving rewording. The next column is the same measure on the 25 blind pairwise passages, each one chunk, reworded the same way. The chunk column is the median, over ordinary drafts with two or more chunks, of the standard deviation between a draft's chunk scores. That spread also holds real differences between the sections of one text, so it overstates the noise in a single chunk's score. `gpttrace` and `desklib` both spread model drafts well beyond all three figures, so either has room to rank one draft against another. For `binoculars` and `fast-detectgpt`, the spread between chunks is most of the spread among model texts, and with no rewording scores there is no measure of their noise to set against it, so their ranking of one model text against another may be mostly noise.

### Threats

- Detector training data can contain the human texts. These are published texts from before 2022, and `gpttrace` lists Wikipedia, PubMed Central, Project Gutenberg and pre-2022 web pages in its training data, so its provenance result may be partly memory of these exact texts. The Falcon models were trained on a web crawl, and the Binoculars authors report that text the model has memorized scores as machine-written, which would push `binoculars` and `fast-detectgpt` toward the inversion seen here. Texts written after the detectors were trained, such as unpublished human writing, are the check on both.
- The degraded texts are longer than the neutral rewrites, with medians of 1,093 and 962 words. The degrading call also added padding and a recap of its own, so `degraded` minus `neutral-rewrite` carries some extra model-written text on top of the drop in quality. The degraded texts picked up announcing phrases too, so they overlap `tells-injected`. `tells-injected` changes only the inserted phrases and has neither problem, and `desklib` rises on it on every topic.
- The planted bad writing is one kind of bad writing: one prompt for the degrading call and one fixed set of inserted tells. A detector that tracks it may miss other ways a draft goes wrong.
- One model family wrote every model text, and every human text is a published excerpt. The pairwise passages are about 250 words, a quarter of the length of the bheijden texts, so each gets one chunk; the spread table gives the noise of a neutral rewording at that length.
- The human and corpus model texts on a topic have similar lengths (medians of 1,048 and 1,000 words), so length does not explain the provenance differences.
- Only its author has measured `gpttrace`'s published accuracy.
