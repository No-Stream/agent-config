# Blind evaluation of writing pipelines

These scripts settle which writing pipeline produces passages a person prefers. Each pipeline writes a short passage (150 to 250 words) from the same task; a person reads one task's passages under neutral letters and ranks them, and two LLM judges rank the same sets twice, under two letter orders. The readout reports, for each comparison, how many tasks put one pipeline above the other, with an interval; each pipeline's mean rank; each judge's agreement with itself and with the person; checks for position and length bias; and a fidelity count per pipeline.

| File | What it does |
| --- | --- |
| `tasks/public.toml` | Five tasks built from public sources, each fact cited |
| `run_pipelines.py` | Runs every pipeline on every task (`plan` prints the agent count first) |
| `blind.py` | Builds one blind set per task and a separate key |
| `label.py` | The ranking command a person runs in a terminal |
| `judges.py` | Gives the same sets to an Opus judge and a codex judge |
| `pipeline_config.py`, `prompts.py`, `fidelity.py`, `budget.py` | The runner's config format and checks, its prompt templates, its reading of the fidelity checker's output, and its agent count and cost totals |
| `agents.py`, `common.py` | Headless Claude Code and codex calls; task and file formats, parallel jobs |

The analysis that unblinds the rankings is not in this repo; it runs beside the private evaluation data. Private task runs write under `.private/eval/pairwise/` at the repo root.

## Running it

`run_pipelines.py`, `blind.py` and `judges.py` need Python 3.11 or newer (for `tomllib`); their script headers say so, and `uv run` picks a Python that fits. `label.py` needs only the standard library and runs on the system `python3`, 3.9 or newer.

1. Write tasks (format below) and a pipeline config.
2. Check the agent count: `uv run run_pipelines.py plan --config pipelines.toml --tasks tasks/public.toml more-tasks.toml`.
3. Generate, in tmux, since a full run takes hours: `uv run run_pipelines.py run --config pipelines.toml --tasks ... --out generation/ --jobs 8`. A rerun skips every stage whose output file exists, so after a failure the same command continues where it stopped. `--only-task` and `--only-pipeline` limit a run; the per-task fidelity measurement runs only when all pipelines ran.
4. Blind: `uv run blind.py --generation generation/ --tasks ... --pipelines current merged merged-style-pass merged-loose-paragraphs no-skill --seed 20261120 --out eval/`. `--only-task` limits the sets to some tasks. It refuses to overwrite an existing `sets.jsonl` or `key.json`, since rankings refer to the set ids, and prints an estimate of the reading time.
5. Rank: `python3 label.py eval/sets.jsonl`.
6. Judge: `uv run judges.py --sets eval/sets.jsonl --skill ../../SKILL.md --out eval/judges --seed 20261120`. The judge calls run four at a time; `--jobs` changes that. A rerun skips sets already ranked; a ranking on disk of other passages or another letter order (from another sets file or seed) stops the run, so a different set needs a fresh `--out`. At the end it prints each judge's agreement with itself across the two orders.

Tests: `uv run --no-project --with pytest python -m pytest tests` from this directory. The runner and judge tests use stand-in `claude` and `codex` executables from `tests/fakes/`; the labeling tests include one that drives `label.py` through a pseudo-terminal.

## Ranking

A task's passages appear one per screen. The top of the screen gives the task number, the passage letters with the current one in brackets, the document type and the intended reader; below them is the passage, wrapped to the terminal (at most 100 columns). `n` or the right arrow shows the next passage, `p` or the left arrow the previous one. `r`, or `n` on the last passage, opens the ranking prompt, which lists each passage's opening words beside its letter. Type the letters best first, with `=` joining a tie: `CAEBD`, or `CA=EBD` for A and E tied in second place. Case and spaces don't matter; a ranking that leaves out a letter, repeats one, or ties all of them is refused and asked again. Enter on an empty prompt goes back to reading. An optional one-line note follows. `b` reopens the previous task, and `q` quits.

Each ranking is appended to `rankings.jsonl` beside the sets file at once, with the note and the seconds spent on the task. Running the command again starts at the first unranked task; after the last one it waits for `b`, to reopen the last task, or `q`. A second ranking of the same task replaces the first.

The ranking command reads only `sets.jsonl`, which holds no pipeline or task names. `key.json` maps each set id to its task and each letter to its pipeline, with a hash of each passage so the analysis can confirm nothing changed after blinding.

## Why one ranking per task

Blind pairs, the base pipeline's passage against each other pipeline's for every task, would show the base passage in every pair of its task. From the second pair on, the reader could tell which side is the base, so most pairs would not be blind. A ranking shows every passage exactly once. Every comparison between two pipelines is still there (on each task one ranks above, ties with or ranks below the other), and the reader reads each passage once instead of once per pair.

The seed shuffles the task order and, separately for each task, which pipeline gets which letter, so a pipeline's position changes at random from task to task. The analysis reports how the person's ranks relate to the position each passage was shown in and to its length.

Each judge ranks every set twice. The seed draws one order of the passages and the second order is its reverse, so a passage shown first in one call is shown last in the other, and the letters follow the order shown. Agreement between the two rankings (Kendall's tau, averaged over sets) measures how much a judge's ranking depends on position; the analysis compares the person with each judge's rank averaged over the two orders.

## Pipeline config

A TOML file with a `[run]` table, named linters, a `[fidelity]` table and one `[[pipeline]]` per pipeline. Each pipeline is a list of stages:

| Stage kind | What it runs |
| --- | --- |
| `draft` | Starts the author conversation: reads the files in `read`, follows `instructions`, returns the passage. With `from_pipeline`, it reuses that pipeline's draft and session instead, so two pipelines can share a draft. With no `read` files it is the model's own draft: the prompt names no guidance and carries no path note, and the call gets no tools. |
| `agent` | A fresh reviewer conversation. It takes either `agent_file` (a Claude Code subagent definition: its body is the system prompt, its frontmatter sets the model and tools) or a `brief`. `sees` picks what it gets: `passage`, `doc_type`, `reader`, `notes`; `read` lists files it must read first, and `model` overrides the model. Consecutive agent stages with the same `group` run in parallel. |
| `author` | One more turn of the author conversation: `instructions`, the files in `read`, the output of the earlier agent stages named in `inputs`, and the output of the linters named in `lint`, run on the current passage. With `loop` (`lint`, `score_key`, `until`, `max_rounds`), the linter runs again after each turn until its score reaches `until` or the turns reach `max_rounds`. |
| `fidelity_gate` | Counts the sentences changed since the earlier draft, author or gate stage named in `compare_to` (required). At `min_changed_sentences` (default 4) or more it runs the fidelity checker named in `agent_file` (required), and if that reports an unsupported change, one author turn with `instructions` fixes it. `model` overrides the checker's model. |

`[run]` sets the author model, the effort level, the seed, a per-call timeout and budget, the directories agents may read, and a `path_note` added to every prompt except a draft that reads no files (for example, to point agents at a skill's working copy). A pipeline's `override` text is added to every prompt in that pipeline, which is how a variant relaxes one rule without a second copy of the skill. Linters are commands with `{file}` standing for the passage; an exit code outside `ok_exit_codes` stops the run.

A stage takes only the keys its kind lists above (and `name`); any other key, a missing required key, a name that no earlier stage of the right kind has, or a file that does not exist stops the config load before any call.

After all pipelines finish a task, one more call runs the fidelity checker on every pipeline's final passage against the task's notes, with the passages under neutral letters.

Each call is `claude -p --safe-mode`: no CLAUDE.md, skills, hooks, plugins or MCP servers, so a pipeline sees only the files its prompt names. Agents get the Read tool and the directories the config lists. The author is one conversation; each author stage resumes it with `--fork-session`, so a failed turn reruns from the same starting point. Every call checks that the model it asked for is the one that served it.

## Agent count

`run_pipelines.py plan` prints, for each pipeline, the fewest and most fresh agents (new conversations) and author turns (resumed conversations) per task, and the totals for the task list. The two numbers differ where a stage is conditional: a fidelity gate runs only when enough sentences changed, and a lint loop stops early when the score clears.

Judges make one call per judge, order and set: with five tasks, two orders and two judges, that is twenty calls.

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

Passages of about 200 words cannot show document-level structure (headings, section count), so the evaluation says nothing about it. Each comparison gets one result per task, so with five to ten tasks the intervals are wide, and the readout gives counts and intervals and leaves the call to the person reading it.

Ranking five passages read one after another leans on memory more than picking from a pair side by side; the prompt's opening words are a reminder, and paging back costs one key. The four comparisons with the base pipeline come from the same rankings, so they are not independent of each other.

The judges are told to apply one pipeline's own guidance, so the readout measures each judge against the person and never against the other judge. `judges.py` stops if the Opus judge did not open the guidance file; codex leaves no record of the files it read, so whether the codex judge read the guidance is not checked.
