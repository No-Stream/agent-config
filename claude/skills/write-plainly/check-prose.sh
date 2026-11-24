#!/usr/bin/env bash
# Runs the write-plainly linters on markdown, plain-text or notebook files. The output is a list of
# findings to triage: a finding in a quotation, code, or a deliberate literal use can be correct as
# written. A notebook (.ipynb) is converted to markdown with jupytext first, so only its markdown
# cells are linted, and its findings carry the notebook's name.
# --budget N, --against OLD and --pr go to lint_prose.py only; see its --help. lint_syntax.py runs
# under uv with spaCy, whose transformer English model it fetches once into ~/.cache/write-plainly.
# Exit 0: no findings. Exit 1: findings. Exit 2 or higher: a linter failed or a tool is missing.
set -uo pipefail

usage() {
    echo "usage: check-prose.sh [--budget N] [--against OLD] [--pr] FILE [FILE ...]" >&2
    exit 2
}

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lint_options=()
files=()
against=""
while [ $# -gt 0 ]; do
    case "$1" in
        --budget)
            [ $# -ge 2 ] || usage
            lint_options+=("$1" "$2")
            shift 2
            ;;
        --against)
            [ $# -ge 2 ] || usage
            against="$2"
            shift 2
            ;;
        --pr)
            lint_options+=("$1")
            shift
            ;;
        -*) usage ;;
        *)
            files+=("$1")
            shift
            ;;
    esac
done
[ ${#files[@]} -ge 1 ] || usage
for tool in python3 uv uvx sloplint; do
    if ! command -v "$tool" >/dev/null; then
        echo "check-prose.sh: $tool not found on PATH (sloplint: gem install sloplint, needs Ruby 3.3+; uv and uvx: install uv)" >&2
        exit 2
    fi
done

tmp_dir="$(mktemp -d)" || exit 2
trap 'rm -rf "$tmp_dir"' EXIT

# Each notebook is linted as a markdown copy; converted[i] is that copy of notebooks[i].
notebooks=()
converted=()
as_markdown() {
    local notebook="$1"
    local markdown
    markdown="$tmp_dir/${#notebooks[@]}/$(basename "${notebook%.ipynb}").md"
    mkdir -p "$(dirname "$markdown")"
    if ! uvx --from jupytext@latest jupytext --quiet --to md --opt notebook_metadata_filter=-all \
        --opt cell_metadata_filter=-all -o "$markdown" "$notebook" 2>"$tmp_dir/jupytext.err"; then
        cat "$tmp_dir/jupytext.err" >&2
        echo "check-prose.sh: jupytext could not convert $notebook" >&2
        exit 2
    fi
    notebooks+=("$notebook")
    converted+=("$markdown")
    echo "== $notebook: linted as markdown converted by jupytext, so line numbers count lines of that markdown"
}

targets=()
for file in "${files[@]}"; do
    if [[ "$file" == *.ipynb ]]; then
        as_markdown "$file"
        targets+=("${converted[${#converted[@]} - 1]}")
    else
        targets+=("$file")
    fi
done
if [[ "$against" == *.ipynb ]]; then
    as_markdown "$against"
    against="${converted[${#converted[@]} - 1]}"
fi
if [ -n "$against" ]; then
    lint_options+=(--against "$against")
fi

# Print linter output with each notebook's markdown copy named as the notebook.
with_notebook_names() {
    if [ ${#converted[@]} -eq 0 ]; then
        cat
        return
    fi
    local line index
    while IFS= read -r line || [ -n "$line" ]; do
        for index in "${!converted[@]}"; do
            line="${line//"${converted[$index]}"/"${notebooks[$index]}"}"
        done
        printf '%s\n' "$line"
    done
}

found_findings=0
# A linter that finds something prints it, so exit 1 with no output is a failure, such as uv
# failing to resolve a tool.
run_linter() {
    local name="$1"
    shift
    echo "== $name"
    local output exit_code
    output="$("$@")"
    exit_code=$?
    if [ -n "$output" ]; then
        printf '%s\n' "$output" | with_notebook_names
    fi
    if [ "$exit_code" -eq 1 ] && [ -z "$output" ]; then
        echo "check-prose.sh: $name exited with 1 and printed no findings" >&2
        exit 2
    fi
    if [ "$exit_code" -gt 1 ]; then
        echo "check-prose.sh: $name exited with $exit_code" >&2
        exit "$exit_code"
    fi
    if [ "$exit_code" -eq 1 ]; then
        found_findings=1
    fi
}

# slop-guard's 0-100 score and band are left out, since triage fixes findings and never a score.
# shellcheck disable=SC2329  # run_linter calls it
slop_guard() {
    uvx --from slop-guard@latest sg -v --counts -t 100 -c "$skill_dir/slop-guard.jsonl" "$@" \
        | sed -E 's#: [0-9]+/100 \[[a-z]+\] (\([0-9]+ words\)) [^ ]+#: \1#'
}

run_linter "house rules (lint_prose.py)" python3 "$skill_dir/lint_prose.py" ${lint_options[@]+"${lint_options[@]}"} "${targets[@]}"
# lint_syntax.py declares its own Python and dependencies; four threads per native pool.
run_linter "syntax (lint_syntax.py)" env OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 \
    uv run --quiet --upgrade --script "$skill_dir/lint_syntax.py" "${targets[@]}"
# impact-noun-bare fires on careful research prose ("the impact of X on Y"); see eval/README.md.
run_linter "sloplint" sloplint check --markdown --ignore impact-noun-bare "${targets[@]}"
run_linter "slop-guard" slop_guard "${targets[@]}"
if [ "$found_findings" -eq 1 ]; then
    echo "Fix each finding with a structural change: a table, a footnote, a cut, regrouped content or a sentence rewritten around its claim. Rewording until the pattern stops matching (a number in words or as a fraction, a synonym, a split sentence, a demoted heading) leaves the defect in place. Keep a flagged span only when the pattern misread it (a quotation, code, a literal use)."
fi
exit "$found_findings"
