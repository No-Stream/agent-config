---
name: review
description: Multi-agent code review of the current changes - parallel Claude and Codex reviewers per domain (correctness, completeness, code quality, plus ML/stats/perf/security when relevant), then grouped triage with proposed fixes. Token-heavy; run only when the user invokes /review.
disable-model-invocation: true
argument-hint: "[ref | range | PR number | paths] [extra focus text]"
---

# Review

You are the orchestrator. You settle the scope and the reviewer roster (judgment calls, possibly questions for
the user), then run `review.workflow.js`, which does the review, merging, grouping and triage. You do not review
the code yourself, and you do not apply fixes. Target 7-15 agents total.

Files next to this one: `common.md` (rules for every reviewer), one brief per domain, `triage.md`,
`review.workflow.js`, and `codex-review.sh` (used by the `codex-reviewer` agent). Claude and Codex reviewers of
the same domain read the same brief.

## 1. Scope

Resolve what to review from `$ARGUMENTS`:

- A ref or range (`main~5`, `abc123..HEAD`): review that range plus uncommitted changes.
- A PR number: `gh pr diff <n>` and `gh pr view <n>` for intent.
- Paths: review those files in full (no diff).
- Free text after the target: extra focus, passed to every reviewer.

With no target, decide only if it is obvious, otherwise ask with AskUserQuestion (show `git log --oneline -15`
and `git status --short`):

- On a non-default branch: `merge-base(default branch)..` plus uncommitted. Obvious.
- On the default branch with only uncommitted changes that form one coherent change: those. Obvious.
- On the default branch with a clean tree, or uncommitted changes plus a run of recent topical commits: ask.

Untracked files are not in `git diff`. List them separately so reviewers read them in full.

## 2. Context bundle

Create the review directory inside the git dir (keeps the tree clean, readable by Codex's sandbox):

```bash
REVIEW_DIR="$(git rev-parse --absolute-git-dir)/review/$(date +%Y%m%d-%H%M%S)"; mkdir -p "$REVIEW_DIR"
```

Write into it:

- `diff.patch`: the diff for the scope (`git diff <base>` includes uncommitted changes).
- `scope.md`: repo root, scope description and base ref, `git diff --stat`, untracked files, commit subjects in
  range, the user's focus text, and the plan and backlog paths (below).

Plan and backlog discovery: a `backlog/` directory or backlog config means run `backlog task list --plain` and
save it to `backlog.txt`. Look for plan files: markdown changed in the diff with plan/spec/design in the path,
`docs/plans/`, `docs/superpowers/plans/`, `plans/`, and recently modified `*plan*.md`. Record what you found. If
several candidates are plausible, ask which one. If none exists, record "no plan file, no backlog" - the
completeness reviewer treats that as a finding for nontrivial features.

## 3. Pick reviewers

Always the six core reviewers: correctness, completeness, quality - each once on Claude, once on Codex.

Add bonus domains only when the diff gives a real reason, one Claude reviewer each (Codex too if the domain is
central to the change):

- `ml.md`: training, evaluation, feature pipelines, model selection, data splits.
- `stats.md`: hypothesis tests, CIs, causal estimates, A/B analysis, sampling, weighting.
- `perf.md`: GPU/CUDA, kernels, hot loops, large-data pipelines, anything where speed or memory is the point.
- `security.md`: an actual attack surface - untrusted input, auth, network-exposed services, secrets,
  shell/SQL built from external input. Internal tooling and research scripts do not qualify.

State the chosen roster and why in one line before dispatching.

## 4. Run the workflow

Call Workflow with `scriptPath: "~/.claude/skills/review/review.workflow.js"` (expand `~`) and args:

```json
{"repoRoot": "...", "reviewDir": "...", "skillDir": "<absolute path of this skill>",
 "claudeDomains": ["correctness", "completeness", "quality", "<bonus domains>"],
 "codexDomains": ["correctness", "completeness", "quality", "<bonus domains central to the change>"]}
```

Domain names are brief file names without `.md`. Claude reviewers run as read-only `review-reader` agents on
Opus. Each Codex reviewer is a Haiku `codex-reviewer` agent driving a read-only Codex job on the newest Sol model
at high effort. One Opus agent merges and groups the findings, then one Opus triage agent handles each batch.

Wait for the completion notification. Do not poll. If the run fails partway, fix the cause and resume it with
`resumeFromRunId`: finished agents replay from cache.

## 5. Report

The workflow returns `failedReviewers`, `checkedSummaries`, `rawFindingCount`, `triaged` (sorted by priority,
then severity) and `untriaged` (findings whose triage agent died). Write `<REVIEW_DIR>/report.md`:

- The scope, the roster, failed reviewers, and what each reviewer checked.
- Every triaged finding, grouped under `fix`, `worth fixing`, `deprioritized`, `rejected`: id, locations, claim,
  severity, verdict and reason, priority reason, who raised it, proposed fix.
- Untriaged findings, listed as such. Do not drop them.

In chat: a one-sentence outcome, then the `fix` and `worth fixing` items in full (claim, location, proposed fix),
then one line for each deprioritized item with its reason, then the count of rejected false positives, failed
reviewers and untriaged findings if any, then the report path. Do not apply any fix; the user picks which ones
to apply.
