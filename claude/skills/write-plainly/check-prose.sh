#!/usr/bin/env bash
# Runs the write-plainly linters on markdown or plain-text files. The output is a list of findings to triage, not a
# quality score: a finding in a quotation, code, or a deliberate literal use can be correct as written.
# Exit 0: no findings. Exit 1: findings. Exit 2 or higher: a linter failed or a tool is missing.
set -uo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ $# -lt 1 ]; then
    echo "usage: check-prose.sh FILE [FILE ...]" >&2
    exit 2
fi
for tool in python3 uvx sloplint; do
    if ! command -v "$tool" >/dev/null; then
        echo "check-prose.sh: $tool not found on PATH (sloplint: gem install sloplint, needs Ruby 3.3+; uvx: install uv)" >&2
        exit 2
    fi
done

found_findings=0
run_linter() {
    local name="$1"
    shift
    echo "== $name"
    "$@"
    local exit_code=$?
    if [ "$exit_code" -gt 1 ]; then
        echo "check-prose.sh: $name exited with $exit_code" >&2
        exit "$exit_code"
    fi
    if [ "$exit_code" -eq 1 ]; then
        found_findings=1
    fi
}

run_linter "house rules (lint_prose.py)" python3 "$skill_dir/lint_prose.py" "$@"
# impact-noun-bare fires on careful research prose ("the impact of X on Y"); see eval/README.md.
run_linter "sloplint" sloplint check --markdown --ignore impact-noun-bare "$@"
run_linter "slop-guard (score is informational)" uvx --from slop-guard==0.5.0 sg -v --counts -t 100 -c "$skill_dir/slop-guard.jsonl" "$@"
exit "$found_findings"
