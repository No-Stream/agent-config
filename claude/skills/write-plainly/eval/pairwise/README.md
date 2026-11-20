# Blind pairwise evaluation of writing pipelines

These scripts settle which writing pipeline produces passages a person prefers. Each pipeline writes a short passage (150 to 250 words) from the same task; a person reads the passages in blind pairs and picks the better one, and two LLM judges see the same pairs in both orders. The tables at the end report the person's preference share per comparison with an interval, the checks for position and length bias, each judge's agreement with the person, and a fidelity count per pipeline.

| File | What it does |
| --- | --- |
| `tasks/public.toml` | Five tasks built from public sources, each fact cited |
| `run_pipelines.py` | Runs every pipeline on every task (`plan` prints the agent count first) |
| `blind.py` | Builds the blind pairs and a separate key |
| `label.py` | The labeling command a person runs in a terminal |
| `judges.py` | Gives the same pairs to an Opus judge and a codex judge |
| `pipeline_config.py`, `prompts.py`, `fidelity.py`, `budget.py` | The runner's config format and checks, its prompt templates, its reading of the fidelity checker's output, and its agent count and cost totals |
| `agents.py`, `common.py` | Headless Claude Code and codex calls; task and file formats, parallel jobs |

The analysis that unblinds the labels is not in this repo; it runs beside the private evaluation data. Private task runs write under `.private/eval/pairwise/` at the repo root.

## Running it

`run_pipelines.py`, `blind.py` and `judges.py` need Python 3.11 or newer (for `tomllib`); their script headers say so, and `uv run` picks a Python that fits. `label.py` needs only the standard library and runs on the system `python3`, 3.9 or newer.

1. Write tasks (format below) and a pipeline config.
2. Check the agent count: `uv run run_pipelines.py plan --config pipelines.toml --tasks tasks/public.toml more-tasks.toml`.
3. Generate, in tmux, since a full run takes hours: `uv run run_pipelines.py run --config pipelines.toml --tasks ... --out generation/ --jobs 8`. A rerun skips every stage whose output file exists, so after a failure the same command continues where it stopped. `--only-task` and `--only-pipeline` limit a run; the per-task fidelity measurement runs only when all pipelines ran.
4. Blind: `uv run blind.py --generation generation/ --tasks ... --base merged --others current merged-style-pass merged-loose-paragraphs --seed 20261120 --out eval/`. It refuses to overwrite an existing `pairs.jsonl`, since labels refer to its pair ids.
5. Label: `python3 label.py eval/pairs.jsonl`.
6. Judge: `uv run judges.py --pairs eval/pairs.jsonl --skill ../../SKILL.md --out eval/judges --seed 20261120`. The judge calls run four at a time; `--jobs` changes that. A rerun skips batches already judged; a judged batch on disk that holds other pairs (from a run with `--only`, another batch size or another seed) stops the run, so a different pair set needs a fresh `--out`.

Tests: `uv run --no-project --with pytest python -m pytest tests` from this directory. The runner and judge tests use stand-in `claude` and `codex` executables from `tests/fakes/`; the labeling tests include one that drives `label.py` through a pseudo-terminal.

## Labeling

The screen shows the document type, the intended reader and the two passages, side by side when the terminal is at least 100 columns wide and stacked otherwise. Keys: `1` or the left arrow picks left, `2` or the right arrow picks right, `t` is a tie, `s` skips, `n` adds a one-line note to the current pair before you pick, `u` goes back one pair, `q` quits. After the last pair the command waits for `u`, to change the last answer, or `q`. Each answer is appended to `labels.jsonl` at once, with the seconds spent on the pair; running the command again starts at the first unanswered pair, then shows skipped pairs again. A second answer to the same pair replaces the first.

The labeling command reads only `pairs.jsonl`, which holds no pipeline or task names. `key.json` maps each pair id to its task and to the pipeline on each side, with a hash of each passage so the analysis can confirm nothing changed after blinding.

## How the pairs are arranged

Every task gets one pair for each comparison (the base pipeline against each other pipeline), so with ten tasks and three comparisons there are thirty pairs. The base passage of a task appears in three pairs, so the order is built in rounds: each task's pairs land in different rounds, no task appears twice within four positions, and every task's first showing comes before any repeat. Within a comparison the base passage is on the left in half of the tasks. The seed fixes all of it.

The analysis reports the base pipeline's share on first showings and on repeat showings separately, because a reader who sees a passage for the second time can tell it is the common one.

## Pipeline config

A TOML file with a `[run]` table, named linters, a `[fidelity]` table and one `[[pipeline]]` per pipeline. Each pipeline is a list of stages:

| Stage kind | What it runs |
| --- | --- |
| `draft` | Starts the author conversation: reads the files in `read`, follows `instructions`, returns the passage. With `from_pipeline`, it reuses that pipeline's draft and session instead, so two pipelines can share a draft. |
| `agent` | A fresh reviewer conversation. It takes either `agent_file` (a Claude Code subagent definition: its body is the system prompt, its frontmatter sets the model and tools) or a `brief`. `sees` picks what it gets: `passage`, `doc_type`, `reader`, `notes`; `read` lists files it must read first, and `model` overrides the model. Consecutive agent stages with the same `group` run in parallel. |
| `author` | One more turn of the author conversation: `instructions`, the files in `read`, the output of the earlier agent stages named in `inputs`, and the output of the linters named in `lint`, run on the current passage. With `loop` (`lint`, `score_key`, `until`, `max_rounds`), the linter runs again after each turn until its score reaches `until` or the turns reach `max_rounds`. |
| `fidelity_gate` | Counts the sentences changed since the earlier draft, author or gate stage named in `compare_to` (required). At `min_changed_sentences` (default 4) or more it runs the fidelity checker named in `agent_file` (required), and if that reports an unsupported change, one author turn with `instructions` fixes it. `model` overrides the checker's model. |

`[run]` sets the author model, the effort level, the seed, a per-call timeout and budget, the directories agents may read, and a `path_note` added to every prompt (for example, to point agents at a skill's working copy). A pipeline's `override` text is added to every prompt in that pipeline, which is how a variant relaxes one rule without a second copy of the skill. Linters are commands with `{file}` standing for the passage; an exit code outside `ok_exit_codes` stops the run.

A stage takes only the keys its kind lists above (and `name`); any other key, a missing required key, a name that no earlier stage of the right kind has, or a file that does not exist stops the config load before any call.

After all pipelines finish a task, one more call runs the fidelity checker on every pipeline's final passage against the task's notes, with the passages under neutral letters.

Each call is `claude -p --safe-mode`: no CLAUDE.md, skills, hooks, plugins or MCP servers, so a pipeline sees only the files its prompt names. Agents get the Read tool and the directories the config lists. The author is one conversation; each author stage resumes it with `--fork-session`, so a failed turn reruns from the same starting point. Every call checks that the model it asked for is the one that served it.

## Agent count

`run_pipelines.py plan` prints, for each pipeline, the fewest and most fresh agents (new conversations) and author turns (resumed conversations) per task, and the totals for the task list. The two numbers differ where a stage is conditional: a fidelity gate runs only when enough sentences changed, and a lint loop stops early when the score clears.

Judges make one call per judge, order and batch: with thirty pairs and batches of ten, that is twelve calls.

## Task format

```toml
[[task]]
id = "pub-example"
doc_type = "README section"
reader = "Ana, a new contributor who wants to know why the tool skips some files"
target_words = 200
notes = """
- a fact, as a short note [1]
"""
sources = ["[1] where the fact comes from"]
```

`doc_type` is one of: Section of a research readout, Proposal paragraph, README section, Pull request description, Design-doc explanation. Citation markers like `[1]` or `[1, 2]` are stripped before the notes reach a writer.

## Limits of the design

Passages of about 200 words cannot show document-level structure (headings, section count), so the evaluation says nothing about it. With ten pairs per comparison the intervals are wide, and the readout gives counts and intervals and leaves the call to the person reading it.

The judges are told to apply one pipeline's own guidance, so the readout measures each judge against the person and never against the other judge. A judge sees ten pairs per call and may balance its picks across a batch; the order-flip rate shows how much its picks depend on position, and a pick that flips with the order counts as a tie. `judges.py` stops if the Opus judge did not open the guidance file; codex leaves no record of the files it read, so whether the codex judge read the guidance is not checked.
