# Personal layer

This file refines the shared core instructions for my personal machine and wins wherever the two differ. Tokens are limited here: I pay for my own usage, Claude usage is the scarcer budget, and codex usage is cheap.

## Budget (refines #delegation)

- Use subagents for any self-contained task, routed by the table below: codex first for well-defined, checkable work, Claude where taste or an unclear definition of done needs it.
- Spending that costs real money beyond my subscriptions (paid APIs, cloud compute) needs its price quoted and my sign-off first.

## Model selection {#model-selection}

Pick by how checkable the task's correctness is and how complete its spec is, not by how important it feels.

| Task | Model | Effort |
|---|---|---|
| Default for simple and routine implementation: data munging, backend plumbing, tests, parsers, refactors, codebase research, summaries | Luna (newest `gpt-*-luna`) | `xhigh` |
| Complex but well-specified implementation, or work where Luna isn't enough | Terra (newest `gpt-*-terra`) | `medium` |
| A second opinion on a design or an important call; advice only, never code | Astra (newest `gpt-*-astra`) | `medium` |
| Planning and system design | Claude Fable | high |
| Ambiguous, ill-defined or taste-heavy work: naming, API shape, UI, prose | Claude Opus | high |
| Thin Claude-side wrappers: agents that call codex or a CLI, mechanical stages of a Claude-only workflow | Claude Haiku | `high` (`low` for pure forwarding) |

- **Codex is the default, and Opus is the exception you justify.** The test is whether correctness is checkable: a task with a clear spec and a test, benchmark, type check or measurement that says whether it worked goes to codex however consequential it is. Opus is for real taste, for problems where you can't state up front what done looks like, and for irreversible decisions; planning goes to Fable. Before dispatching Opus, say in one line why codex couldn't verify the task, and if you can't, use codex. Long parallel Opus fan-outs also hit session limits and stop mid-task.
- Luna is cheap enough to parallelize aggressively, and its `xhigh` effort costs almost nothing, so never lower it to match Luna's place in the table. Terra at `medium` is usually enough, since `high` costs much more for a little more. Astra is the most expensive tier; use it sparingly. Sol is not a routine implementation pick.
- Fable is the planning model (`model: "fable"` on the Agent tool); Opus plans only when Fable is unavailable. Haiku is allowed and good, at `high`, when the work has to happen on the Claude side.
- Use the newest version of each tier and never hardcode a version here; OpenAI's tier lineup shifts between generations, so recheck this table when a new one ships. Resolve the slugs at dispatch time from codex's model list:

  ```bash
  python3 -c "import json; [print(m['slug']) for m in json.load(open('$HOME/.codex/models_cache.json'))['models'] if m['visibility'] == 'list']"
  ```

- Pass `--model` and `--effort` to the codex plugin explicitly (`/codex:rescue --model <newest gpt-*-terra slug> --effort medium <task>`); left unset, they fall through to `~/.codex/config.toml`, not to this table. `--effort` takes `none`, `minimal`, `low`, `medium`, `high` or `xhigh`; the plugin rejects `max` and `ultra`.
- When codex hits its usage limit, tell me at once with the reset time it reports, so I can decide whether to spend a banked reset. Meanwhile substitute Claude models (Haiku at `medium` or `high` for Luna, Opus at `medium` for Terra), and say so if Claude usage is near its limit too.

## Codex plugin jobs

A `/codex:rescue --background` dispatch only starts a job and returns "task started as task-XXX"; its results never arrive as a notification. Do other work while it runs, then wait for it and fetch the result:

```bash
node ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs status <task-id> --wait
node ~/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs result <task-id>
```

Bare `status` lists every job. Without a blocking wait, space checks by the core's cadence table (#bash-policy). `/codex:status` and `/codex:result` are the interactive equivalents.

## Review (refines #plan-gate and #review-findings)

- The review workflow here is the `review` skill. It is token-heavy, so it runs only when I invoke `/review`. Its triage sorts findings into `fix`, `worth fixing`, `deprioritized` and `rejected`, and I pick which fixes to apply.
- Without a `/review` run, run the plan audit yourself before calling work done: reread the plan, check each item against the diff, and report any item that is neither implemented nor deferred with my agreement.
- A fix's cost counts here: a real finding whose fix costs more than it returns can be deprioritized, with the reason stated. The typical case is a guard for an extremely rare or impossible case, where failing loudly is enough.

## Tests

Write unit tests too, beside the end-to-end tests the core prefers.

## Git (refines #git-writes)

- **Push only with my explicit authorization.** I grant it per branch, per repo or per session ("you may push the feature branches this session"); then pushing the authorized branches is allowed. Force-push, history rewrites and publishing a review still need their own sign-off.
- **No AI attribution anywhere in git or on GitHub:** commit messages, PR descriptions and PR replies carry none.

## Blocked commands (refines #denied-commands)

`~/.claude/settings.json` has deny rules and a guard hook (`guard-bash.sh`) for destructive and credential-reading commands, such as `rm -rf`, force-push, `git reset --hard` and `curl` piped to a shell. They catch obvious mistakes when I run without permission prompts. When one blocks a command that is actually needed and no allowed route reaches the same result, tell me the command and why, and I'll run it.

## Skills here

The writing skill is `write-plainly`. Notebooks follow `notebooks`, figures `visualization`, papers and research write-ups `paper-drafting`, and review is `review`.
