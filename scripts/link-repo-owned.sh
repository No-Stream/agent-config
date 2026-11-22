#!/usr/bin/env bash
# Usage: link-repo-owned.sh [--replace] [--layer NAME]. Links each repo-owned live path (sync.py --list-repo-owned) into this repo and, with --layer, builds ~/.codex/AGENTS.md from the core and that layer and installs a post-merge hook that rebuilds it; see README.md, Installing.
set -euo pipefail

replace=false
layer=""
while (( $# > 0 )); do
  case "$1" in
    --replace) replace=true ;;
    --layer)
      if (( $# < 2 )); then
        echo "error: --layer needs the name of a layer, such as personal" >&2
        exit 2
      fi
      layer="$2"
      shift
      ;;
    *)
      echo "error: unknown argument $1; the options are --replace and --layer NAME" >&2
      exit 2
      ;;
  esac
  shift
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
branch="$(git -C "$repo_root" symbolic-ref --short HEAD)"
if [[ "$branch" != main ]]; then
  echo "error: $repo_root is on branch $branch; the live paths must link into a checkout on main, so run this from one and do feature work in a separate worktree" >&2
  exit 1
fi
repo_owned="$(python3 "$repo_root/sync.py" --list-repo-owned)"
layers="$(cut -f2 <<< "$repo_owned" | sed -n 's|^\.claude/rules/\(.*\)\.md$|\1|p')"
if [[ -n "$layer" ]] && ! grep -qxF -- "$layer" <<< "$layers"; then
  echo "error: this repo has no layer named $layer; its layers are: $(paste -sd ' ' <<< "$layers")" >&2
  exit 2
fi
backup_root="${HOME:?}/.local/state/agent-config-backups/$(date +%Y%m%d-%H%M%S)"

while IFS=$'\t' read -r relative live_relative; do
  repo_path="$repo_root/$relative"
  live_path="$HOME/$live_relative"
  if [[ "$live_relative" == .claude/rules/* && "$live_relative" != ".claude/rules/$layer.md" ]]; then
    echo "skipped: $live_path is a machine layer; link it with --layer $(basename "$live_relative" .md) on its own machine"
    continue
  fi
  if [[ ! -e "$repo_path" ]]; then
    echo "error: the repo copy $repo_path does not exist" >&2
    exit 1
  fi
  if [[ -L "$live_path" && "$live_path" -ef "$repo_path" ]]; then
    echo "already linked: $live_path"
    continue
  fi
  if [[ -e "$live_path" || -L "$live_path" ]]; then
    if [[ "$replace" == false ]] && ! diff -r -x __pycache__ -x .pytest_cache -x .ruff_cache -x .cache "$live_path" "$repo_path"; then
      echo "error: $live_path differs from $repo_path (diff above); reconcile them and rerun, or rerun with --replace to back up the live copy and link the repo's" >&2
      exit 1
    fi
    backup_path="$backup_root/$live_relative"
    mkdir -p "$(dirname "$backup_path")"
    mv "$live_path" "$backup_path"
    echo "backed up: $live_path -> $backup_path"
  fi
  mkdir -p "$(dirname "$live_path")"
  ln -s "$repo_path" "$live_path"
  echo "linked: $live_path -> $repo_path"
done <<< "$repo_owned"

if [[ -n "$layer" ]]; then
  python3 "$repo_root/scripts/build_codex_agents.py" "$layer"
  hook="$(git -C "$repo_root" rev-parse --path-format=absolute --git-path hooks)/post-merge"
  hook_text="#!/bin/sh
# Installed by scripts/link-repo-owned.sh --layer $layer: rebuilds ~/.codex/AGENTS.md after a merge or pull.
exec python3 \"$repo_root/scripts/build_codex_agents.py\" \"$layer\""
  if [[ -e "$hook" || -L "$hook" ]]; then
    if ! diff "$hook" - <<< "$hook_text"; then
      echo "error: $hook differs from the post-merge hook this script installs (diff above); merge the two or move yours aside, then rerun" >&2
      exit 1
    fi
    echo "already installed: $hook"
  else
    printf '%s\n' "$hook_text" > "$hook"
    chmod +x "$hook"
    echo "installed: $hook"
  fi
fi
