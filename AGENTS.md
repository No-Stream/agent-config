# agent-config

This repo is my public configuration for Claude Code and codex, and this file covers working on the repo itself. My global instructions for agents are in `instructions/`: `core.md` loads on every machine I use, and `personal.md` is the layer for my personal machine.

## How the repo stays in sync with my live config

Most of `claude/` and `codex/` is copied from my live config by `python3 sync.py`, run on my personal machine. It copies only the allowlists `COPIED_FILES` and `COPIED_DIRS`, replaces home paths with `~`, applies the private replacements, and fails if any file git could publish matches a forbidden pattern. Don't edit a copied file here, since the next sync overwrites it; edit the live file and rerun the sync there. Run a full sync (`python3 sync.py` with no arguments) only on my personal machine: it copies from whichever machine runs it, so anywhere else it would pull that machine's config into the repo. `python3 sync.py --check`, `--check-commits` and `--check-history` only scan, and are safe anywhere.

The paths in `REPO_OWNED` in `sync.py` are edited in this repo instead, and each machine uses them through symlinks at the live paths the dict maps them to: `scripts/link-repo-owned.sh` makes the links, and the sync never copies over them. A new repo-owned file needs a `REPO_OWNED` entry and a row in the README table. Keep the main checkout on `main`, because the live paths link into it, and do each arc's work in a worktree under `.worktrees/`; the link script refuses to run from any other branch. Merge finished work into `main` yourself (`git merge --no-ff`) and push `main` under the machine's push rule; I don't open or merge pull requests here.

An entry whose live path is in `~/.claude/rules/` is a machine layer. Claude Code loads every file there in every session, so the link script links a layer only when `--layer` names it. `--layer personal` is only for my personal machine; on any other machine, run the link script without `--layer`. Rules that hold on one machine only belong in that machine's layer, never in `core.md`, and the layers of my other machines stay on those machines and never enter this repo.

Codex reads a single global instructions file, so `scripts/build_codex_agents.py` generates `~/.codex/AGENTS.md` from the core and one layer. On my personal machine the link script runs it when given `--layer personal`, and installs a post-merge hook in the clone that reruns it after every merge or pull; on any other machine, rebuild codex's file from that machine's own layer with `python3 scripts/build_codex_agents.py <layer>`, where `<layer>` is the layer's file name in `~/.claude/rules/` without `.md`. Never edit the generated file; edit the sources and rerun the link script or the builder.

## Tests

Run these after any change, and keep them green:

```bash
uv run --no-project --with pytest python -m pytest tests
(cd claude/skills/write-plainly && uv run --no-project --with pytest --with nltk --with spacy --with spacy-curated-transformers --with torch --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match python -m pytest tests)
(cd claude/skills/visualization && uv run --no-project --with pytest --with matplotlib --with numpy --with pandas --with pillow python -m pytest tests)
python3 sync.py --check
ruff check . && ruff format --check .
```

`tests/` runs `sync.py`, the link script and the codex builder end to end against a temporary home and repo, so no test touches the live config. `sync.py` and `scripts/` use only the standard library and run under the system `python3`, so keep them compatible with Python 3.9. Ruff reads `ruff.toml` at the root (and `claude/skills/write-plainly/ruff.toml` under that skill), so it gives the same answer from any directory; the copied directories are excluded there, because they are linted where they are edited.

After a change under `claude/skills/write-plainly/eval/`, also run that evaluation's four suites, whose commands are in `eval/README.md`, `eval/pairwise/README.md`, `eval/detectors/README.md` and `eval/surprisal/README.md`. `bash codex/hooks/test_guard_shell.sh codex/hooks/guard_shell_cases.tsv` tests the guard installed at `~/.codex/hooks/guard_shell.py`, so it runs only on a machine where that copy is installed.

## Privacy

This repo is public, and every line committed to it is published.

- Nothing from a work machine, and nothing about my work, is ever committed: no employer, client, team, project, product, dataset, table, metric, host, account, internal tool, internal URL, work machine path or person's name other than my public handle. Write examples fresh, on public topics.
- `.private/` is gitignored and holds the private pattern list, the private replacements, plans and notes; `backlog/` holds task files and is kept out of git by `.git/info/exclude`. Never commit either, force-add them, or copy their contents into a tracked file.
- My clones' git hooks enforce part of this. The pre-commit hook refuses any author or committer email but my public one and runs `python3 sync.py --check`. The pre-push hook also runs `python3 sync.py --check-commits` on every commit being pushed, which scans each commit's author, committer, message and added lines, so a leak that a later commit deleted still blocks the push. `python3 sync.py --check-history` scans every commit on any branch, remote-tracking branch or tag the same way.
- The scan has two parts. Generic patterns in `sync.py` catch secrets and tokens, cloud account numbers and resource names, storage bucket addresses, internal hostnames and intranet links, email addresses other than my public one and the reserved example domains, home directory paths, and IP addresses outside the documentation ranges. The private lists, `.private/forbidden_patterns.txt` and one file per class of name in `.private/forbidden_patterns.d/`, hold my employer's names and those of its products, tools, hosts, teams, datasets, repos and people. A name the lists don't hold still gets through, so read every line you add as well.
- Instruction and skill text states the current rule only, so `--check` also fails on a date, wording that tells what a rule was before or when it changed, a ticket or task ID, or a commit hash in `AGENTS.md`, `README.md`, `instructions/`, `claude/agents/`, and the Markdown files at the top of each skill or in its `references/`. Tests, fixtures, evaluation data and plans are exempt. A genuine exception goes in `.private/allowed_matches.tsv`, one `path<TAB>matched text<TAB>reason` per line.
- Commit messages carry no AI attribution.
