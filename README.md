# agent-config

My configuration for Claude Code and OpenAI Codex: the instructions file both agents read, custom skills, subagents,
safety hooks and settings. Paths are shown as `~`, and per-project entries and
auto-saved command approvals are removed.

| Path | What it is |
|---|---|
| `AGENTS.md` | Global instructions for both agents. Locally, `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` are symlinks to it |
| `claude/settings.json` | Claude Code settings: permission allow and deny lists, hooks, plugins, auto-mode rules |
| `claude/hooks/guard-bash.sh` | PreToolUse hook that blocks destructive or credential-reading shell commands |
| `claude/statusline-command.sh` | Status line: model, effort, directory, branch, context use, rate limits |
| `claude/agents/` | Subagents used by the review and write-plainly skills |
| `claude/skills/review/` | Multi-domain code review workflow (correctness, ML, stats, security, performance, ...) with a Codex second opinion |
| `claude/skills/paper-drafting/` | Turning research into a paper or blog post: narrative, claims ledger, evidence red-team, drafting order |
| `claude/skills/write-plainly/` | Rules for plain prose in documents other people read (READMEs, reports, posts), three prose linters run by `check-prose.sh`, and an Opus reviewer subagent |
| `claude/skills/visualization/` | Plot choice, uncertainty, computed and asserted titles, light and dark themes, figure review; includes `vizstyle.py` and tests |
| `codex/config.toml` | Codex settings: permissions profiles, network allowlist, agents, hook registration |
| `codex/rules/default.rules` | Codex prefix rules that forbid the same destructive commands as the Claude deny list |
| `codex/hooks/` | Codex PreToolUse guard that reuses the Claude guard and checks compound shell commands, with test cases |

## Installing

To use any of this, copy or symlink the pieces you want into `~/.claude/` and `~/.codex/`; skills go in
`~/.claude/skills/<name>/`. The hooks call `jq`, and the Codex guard runs under the system `python3`. The
write-plainly linters need [uv](https://docs.astral.sh/uv/) for slop-guard, and Ruby 3.3 or later with
`gem install sloplint` so that `sloplint` is on `PATH`.

I keep this repo in sync with my live config using `python3 sync.py`. The script copies an explicit allowlist of files
from `~/.claude` and `~/.codex`, replaces home-directory paths with `~`, drops per-project entries and private names,
and fails if any file in the repo matches a sensitive
pattern. The private part of that pattern list is kept in the gitignored `.private/forbidden_patterns.txt`.
