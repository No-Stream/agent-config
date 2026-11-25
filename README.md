# agent-config

My configuration for Claude Code and OpenAI Codex: the instructions that both agents read, custom skills, subagents,
safety hooks and settings. Paths are shown as `~`, and per-project entries and auto-saved command approvals are removed.

| Path | What it is |
|---|---|
| `instructions/core.md` | The shared core of my global instructions for both agents, loaded on every machine I use as `~/.claude/CLAUDE.md` |
| `instructions/personal.md` | The layer for my personal machine, loaded as `~/.claude/rules/personal.md`: its token budget, model routing, review workflow and push rule. Each of my other machines keeps its own layer outside this repo |
| `AGENTS.md` | Instructions for agents working on this repo: how the sync works, how to run the tests, and what must never be committed |
| `claude/settings.json` | Claude Code settings: permission allow and deny lists, hooks, plugins, auto-mode rules |
| `claude/hooks/guard-bash.sh` | PreToolUse hook that blocks destructive or credential-reading shell commands |
| `claude/statusline-command.sh` | Status line: model, effort, directory, branch, context use, rate limits |
| `claude/agents/` | Subagents used by the review and write-plainly skills |
| `claude/skills/review/` | Multi-domain code review workflow (correctness, ML, stats, security, performance, ...) with a Codex second opinion |
| `claude/skills/paper-drafting/` | Turning research into a paper or blog post: narrative, claims ledger, evidence red-team, drafting order |
| `claude/skills/write-plainly/` | Rules for plain prose in documents other people read (READMEs, reports, posts), four prose linters that `check-prose.sh` runs (one of them parses sentences with spaCy), and three subagents: an Opus reviewer, an Opus reader test that checks whether the document answers the questions its reader would ask, and a fidelity checker for edits |
| `claude/skills/visualization/` | Plot choice, uncertainty, computed and asserted titles, light and dark themes, figure review; includes `vizstyle.py` and tests |
| `claude/skills/notebooks/` | Authoring, running and reviewing analysis notebooks: cell structure, results rendered from code, kernel state and long runs, memory and speed on large dataframes, and a pre-run review |
| `codex/config.toml` | Codex settings: permissions profiles, network allowlist, agents, hook registration |
| `codex/rules/default.rules` | Codex prefix rules that forbid the same destructive commands as the Claude deny list |
| `codex/hooks/` | Codex PreToolUse guard that reuses the Claude guard and checks compound shell commands, with test cases |
| `scripts/` | `link-repo-owned.sh`, which links the repo-owned paths into the live config, and `build_codex_agents.py`, which builds codex's single instructions file from the core and one layer |

## Installing

To use any of this, copy or symlink the pieces you want into `~/.claude/` and `~/.codex/`; skills go in
`~/.claude/skills/<name>/`. The hooks call `jq`, and the Codex guard runs under the system `python3`. The
write-plainly linters need [uv](https://docs.astral.sh/uv/), network access, and Ruby 3.3 or later with
`gem install sloplint` so that `sloplint` is on `PATH`. uv runs slop-guard, and runs the syntax linter
`lint_syntax.py` with spaCy, its transformer support, torch's CPU build and NLTK, resolving the newest release of each on
every run, and installs a Python that the script accepts if none is installed. On first use, the syntax linter downloads spaCy's
`en_core_web_trf` model, about 460 MB, and the Open English WordNet into `~/.cache/write-plainly`.

The paths in `REPO_OWNED` in `sync.py` are edited in this repo, and each machine uses them through symlinks at the
live paths that the dict maps them to. To set that up in a clone, run `scripts/link-repo-owned.sh --layer personal` on my
personal machine, or `scripts/link-repo-owned.sh` on a machine whose layer is kept outside this repo. On a machine set
up with the old layout, where `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` both linked to one `~/AGENTS.md`, run
`scripts/link-repo-owned.sh --replace --layer personal` and then move `~/AGENTS.md` into the backup directory that
the script printed, because Claude Code and Codex would otherwise load it as project instructions in directories under `~`.

Claude Code loads every file in `~/.claude/rules/` in every session, so a layer must be linked only on its own machine.
The script therefore links an entry whose live path is in `~/.claude/rules/` only when `--layer` names it. With
`--layer NAME`, it then runs `scripts/build_codex_agents.py NAME`, which writes `~/.codex/AGENTS.md` as a header naming
its two sources followed by `~/.claude/CLAUDE.md` and `~/.claude/rules/NAME.md`, because Codex reads a single global
instructions file and has no include syntax. The builder replaces a symlink at that path, never overwrites a file it did
not write, and rewrites its output only when a source changed. The script also installs a post-merge hook in the clone
that reruns the builder, so after a merge or pull into `main` Codex reads the same instructions as Claude Code. On a
machine whose layer is not in this repo, run the builder with that layer's name whenever the core or the layer changes:
`python3 scripts/build_codex_agents.py <layer>`.

When a live copy already exists, the script stops and prints the diff if it differs from the clone. If it matches, the
script moves it under `~/.local/state/agent-config-backups/<timestamp>/`, outside `~/.claude`, so Claude Code never
loads the backup. Once you have read the diff, rerun the script with `--replace` to move a differing live copy to that
backup directory as well and link the clone's copy in its place. A different post-merge hook already in the clone also
stops the script with the diff, and `--replace` leaves it alone: merge the two or move yours aside. Running the script
again leaves correct links and its own hook alone. The checkout that the live paths link to stays on `main`, so the script
refuses to run from any other branch, and feature work on the repo-owned files happens in a separate worktree.

I keep the rest of this repo in sync with my live config using `python3 sync.py`. The script copies an explicit
allowlist of files from `~/.claude` and `~/.codex`, replaces home-directory paths with `~`, drops per-project entries
and private names, and fails if any file git could publish matches a sensitive pattern. It never deletes or overwrites
the repo-owned paths, or any live path that is a symlink into the repo. My local pre-commit and pre-push hooks run that
scan alone with `python3 sync.py --check`. The pre-push hook also runs `python3 sync.py --check-commits` on every commit
being pushed, which scans each commit's author, committer, message and added lines, so a leak that a later commit deleted
still blocks the push, and `python3 sync.py --check-history` scans every commit in the clone the same way. The patterns
cover secrets and tokens, cloud account numbers and resource names, bucket addresses, internal hostnames and links, email
addresses, home directory paths and IP addresses, plus a list of private names kept in the gitignored
`.private/forbidden_patterns.txt`. The scan of the repo as it stands also fails on dates, history and ticket IDs in the
instruction and skill text, which states only the current rule.
