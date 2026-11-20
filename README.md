# agent-config

My configuration for Claude Code and OpenAI Codex: the instructions file both agents read, custom skills, subagents,
safety hooks and settings. Paths are shown as `~`, and per-project entries and auto-saved command approvals are removed.

| Path | What it is |
|---|---|
| `AGENTS.md` | Global instructions for both agents. Locally, `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` are symlinks to it |
| `claude/settings.json` | Claude Code settings: permission allow and deny lists, hooks, plugins, auto-mode rules |
| `claude/hooks/guard-bash.sh` | PreToolUse hook that blocks destructive or credential-reading shell commands |
| `claude/statusline-command.sh` | Status line: model, effort, directory, branch, context use, rate limits |
| `claude/agents/` | Subagents used by the review and write-plainly skills |
| `claude/skills/review/` | Multi-domain code review workflow (correctness, ML, stats, security, performance, ...) with a Codex second opinion |
| `claude/skills/paper-drafting/` | Turning research into a paper or blog post: narrative, claims ledger, evidence red-team, drafting order |
| `claude/skills/write-plainly/` | Rules for plain prose in documents other people read (READMEs, reports, posts), three prose linters run by `check-prose.sh`, and three subagents: an Opus reviewer, an Opus reader test that checks whether the document answers the questions its reader would ask, and a fidelity checker for edits |
| `claude/skills/visualization/` | Plot choice, uncertainty, computed and asserted titles, light and dark themes, figure review; includes `vizstyle.py` and tests |
| `codex/config.toml` | Codex settings: permissions profiles, network allowlist, agents, hook registration |
| `codex/rules/default.rules` | Codex prefix rules that forbid the same destructive commands as the Claude deny list |
| `codex/hooks/` | Codex PreToolUse guard that reuses the Claude guard and checks compound shell commands, with test cases |

## Installing

To use any of this, copy or symlink the pieces you want into `~/.claude/` and `~/.codex/`; skills go in
`~/.claude/skills/<name>/`. The hooks call `jq`, and the Codex guard runs under the system `python3`. The
write-plainly linters need [uv](https://docs.astral.sh/uv/) for slop-guard, and Ruby 3.3 or later with
`gem install sloplint` so that `sloplint` is on `PATH`.

The write-plainly skill and its three `prose-*.md` agents are edited in this repo, and each machine uses them through
symlinks. To set that up in a clone, run `scripts/link-repo-owned.sh`. It links `~/.claude/skills/write-plainly` and the
three agents in `~/.claude/agents/` to the clone's copies. When a live copy already exists, the script stops and prints
the diff if it differs from the clone. If it matches, the script moves it under
`~/.local/state/agent-config-backups/<timestamp>/`, outside the directories Claude Code loads skills and agents from.
Once you have read the diff, rerun the script with `--replace` to move a differing live copy to that backup directory
as well and link the clone's copy in its place. Running the script again leaves correct links alone. The checkout the
live paths link to stays on `main`, so the script refuses to run from any other branch, and feature work on the
repo-owned files happens in a separate worktree.

I keep the rest of this repo in sync with my live config using `python3 sync.py`. The script copies an explicit
allowlist of files from `~/.claude` and `~/.codex`, replaces home-directory paths with `~`, drops per-project entries
and private names, and fails if any file git could publish matches a sensitive pattern. It never deletes or overwrites
the repo-owned paths listed in its `REPO_OWNED`, or any live path that is a symlink into the repo. My local pre-commit
and pre-push hooks run that scan alone with `python3 sync.py --check`. The pre-push hook also runs
`python3 sync.py --check-commits` on every commit being pushed, which scans each commit's message and added lines, so a
leak that a later commit deleted still blocks the push. The private part of the pattern list is kept in the gitignored
`.private/forbidden_patterns.txt`.
