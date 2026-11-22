# agent-config

This repo is my public configuration for Claude Code and codex, and this file covers working on the repo itself. My global instructions for agents are in `instructions/`: `core.md` loads on every machine I use, and `personal.md` is the layer for my personal machine.

## How the repo stays in sync with my live config

Most of `claude/` and `codex/` is copied from my live config by `python3 sync.py`, run on my personal machine. It copies only the allowlists `COPIED_FILES` and `COPIED_DIRS`, replaces home paths with `~`, applies the private replacements, and fails if any file git could publish matches a forbidden pattern. Don't edit a copied file here, since the next sync overwrites it; edit the live file and rerun the sync there. Run a full sync (`python3 sync.py` with no arguments) only on my personal machine: it copies from whichever machine runs it, so anywhere else it would pull that machine's config into the repo. `python3 sync.py --check` and `--check-commits` only scan, and are safe anywhere.

The paths in `REPO_OWNED` in `sync.py` are edited here instead: the instructions, the write-plainly and notebooks skills, and the `prose-*.md` agents. `REPO_OWNED` maps each repo path to its live path under `~`, `scripts/link-repo-owned.sh` symlinks each live path to the repo copy, and the sync never copies over them. A new repo-owned file needs a `REPO_OWNED` entry and a row in the README table. The link script refuses to run unless this checkout is on `main`, because the live paths link into it, so do feature work in a worktree under `.worktrees/`.

An entry whose live path is in `~/.claude/rules/` is a machine layer. Claude Code loads every file there in every session, so the link script links a layer only when `--layer` names it. Rules that hold on one machine only belong in that machine's layer, never in `core.md`, and the layers of my other machines stay on those machines and never enter this repo.

Codex reads a single global instructions file, so `scripts/build_codex_agents.py` generates `~/.codex/AGENTS.md` from the core and one layer, and the link script runs it when given `--layer`. Never edit the generated file; edit the sources and rerun the link script or the builder.

## Tests

Run these after any change, and keep them green:

```bash
uv run --no-project --with pytest python -m pytest tests
(cd claude/skills/write-plainly && uv run --no-project --with pytest python -m pytest tests)
(cd claude/skills/visualization && uv run --no-project --with pytest --with matplotlib --with numpy --with pandas --with pillow python -m pytest tests)
python3 sync.py --check
```

`tests/` runs `sync.py`, the link script and the codex builder end to end against a temporary home and repo, so no test touches the live config. `bash codex/hooks/test_guard_shell.sh codex/hooks/guard_shell_cases.tsv` tests the guard installed at `~/.codex/hooks/guard_shell.py`, so it runs only on a machine where that copy is installed.

`sync.py` and `scripts/` use only the standard library and run under the system `python3`, so keep them compatible with Python 3.9.

## Privacy

This repo is public, and every line committed to it is published.

- Nothing from a work machine, and nothing about my work, is ever committed: no employer, client, team, project, product, dataset, table, metric, host, account, internal tool, internal URL, work machine path or person's name other than my public handle. Write examples fresh, on public topics.
- `.private/` is gitignored and holds the private pattern list, the private replacements, plans and notes; `backlog/` holds task files and is kept out of git by `.git/info/exclude`. Never commit either, force-add them, or copy their contents into a tracked file.
- My clones' git hooks enforce part of this: the pre-commit hook refuses any author or committer email but my public one and runs `python3 sync.py --check`, and the pre-push hook also runs `python3 sync.py --check-commits` on every commit being pushed, so a leak that a later commit deleted still blocks the push. The scan only finds the names its pattern list knows, so read every line you add as well.
- Commit messages carry no AI attribution. Push only with my authorization.
