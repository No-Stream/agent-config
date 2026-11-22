# agent-config

My configuration for Claude Code and OpenAI Codex: the instructions both agents read, custom skills, subagents,
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
| `claude/skills/write-plainly/` | Rules for plain prose in documents other people read (READMEs, reports, posts), three prose linters run by `check-prose.sh`, and an Opus reviewer subagent |
| `claude/skills/visualization/` | Plot choice, uncertainty, computed and asserted titles, light and dark themes, figure review; includes `vizstyle.py` and tests |
| `claude/skills/notebooks/` | Authoring, running and reviewing analysis notebooks: cell structure, results rendered from code, kernel state and long runs, memory and speed on large dataframes, and a pre-run review |
| `codex/config.toml` | Codex settings: permissions profiles, network allowlist, agents, hook registration |
| `codex/rules/default.rules` | Codex prefix rules that forbid the same destructive commands as the Claude deny list |
| `codex/hooks/` | Codex PreToolUse guard that reuses the Claude guard and checks compound shell commands, with test cases |
| `scripts/` | `link-repo-owned.sh`, which links the repo-owned paths into the live config, and `build_codex_agents.py`, which builds codex's single instructions file from the core and one layer |

## Installing

To use any of this, copy or symlink the pieces you want into `~/.claude/` and `~/.codex/`; skills go in
`~/.claude/skills/<name>/`. The hooks call `jq`, and the Codex guard runs under the system `python3`. The
write-plainly linters need [uv](https://docs.astral.sh/uv/) for slop-guard, and Ruby 3.3 or later with
`gem install sloplint` so that `sloplint` is on `PATH`.

The paths listed in `REPO_OWNED` in `sync.py` are edited in this repo, and each machine uses them through symlinks:
the two instruction files, the write-plainly and notebooks skills, and the three `prose-*.md` agents. `REPO_OWNED` maps
each repo path to its live path: `instructions/core.md` to `~/.claude/CLAUDE.md`, `instructions/personal.md` to
`~/.claude/rules/personal.md`, and each skill and agent to the same path under `~/.claude`. To set that up in a clone,
run `scripts/link-repo-owned.sh --layer personal` on my personal machine, or `scripts/link-repo-owned.sh` on a machine
whose layer is kept outside this repo.

Claude Code loads every file in `~/.claude/rules/` in every session, so a layer must be linked only on its own machine.
The script therefore links an entry whose live path is in `~/.claude/rules/` only when `--layer` names it. With
`--layer`, it then runs `scripts/build_codex_agents.py`, which writes `~/.codex/AGENTS.md` as a header naming its two
sources followed by `~/.claude/CLAUDE.md` and the layer, because Codex reads a single global instructions file and has
no include syntax. The builder replaces a symlink at that path, never overwrites a file it did not write, and rewrites
its output only when a source changed, so rerun the link script after pulling changes to `instructions/`. On a machine
whose layer is not in this repo, run the builder with that layer instead:
`python3 scripts/build_codex_agents.py ~/.claude/rules/<layer>.md`.

When a live copy already exists, the script stops and prints the diff if it differs from the clone. If it matches, the
script moves it under `~/.local/state/agent-config-backups/<timestamp>/`, outside `~/.claude`, so Claude Code never
loads the backup. Once you have read the diff, rerun the script with `--replace` to move a differing live copy to that
backup directory as well and link the clone's copy in its place. Running the script again leaves correct links alone.
The checkout the live paths link to stays on `main`, so the script refuses to run from any other branch, and feature
work on the repo-owned files happens in a separate worktree.

I keep the rest of this repo in sync with my live config using `python3 sync.py`. The script copies an explicit
allowlist of files from `~/.claude` and `~/.codex`, replaces home-directory paths with `~`, drops per-project entries
and private names, and fails if any file git could publish matches a sensitive pattern. It never deletes or overwrites
the repo-owned paths, or any live path that is a symlink into the repo. My local pre-commit and pre-push hooks run that
scan alone with `python3 sync.py --check`. The pre-push hook also runs `python3 sync.py --check-commits` on every commit
being pushed, which scans each commit's message and added lines, so a leak that a later commit deleted still blocks the
push. The private part of the pattern list is kept in the gitignored `.private/forbidden_patterns.txt`.
