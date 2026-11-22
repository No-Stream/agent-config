#!/usr/bin/env bash
# Usage: link-repo-owned.sh [--replace]. Links each repo-owned live path (sync.py --list-repo-owned) into this repo; see README.md, Installing.
set -euo pipefail

replace=false
for argument in "$@"; do
  case "$argument" in
    --replace) replace=true ;;
    *)
      echo "error: unknown argument $argument; the only option is --replace" >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
branch="$(git -C "$repo_root" symbolic-ref --short HEAD)"
if [[ "$branch" != main ]]; then
  echo "error: $repo_root is on branch $branch; the live paths must link into a checkout on main, so run this from one and do feature work in a separate worktree" >&2
  exit 1
fi
repo_owned="$(python3 "$repo_root/sync.py" --list-repo-owned)"
backup_root="${HOME:?}/.local/state/agent-config-backups/$(date +%Y%m%d-%H%M%S)"

while IFS= read -r relative; do
  repo_path="$repo_root/$relative"
  live_path="$HOME/.$relative"
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
    backup_path="$backup_root/.$relative"
    mkdir -p "$(dirname "$backup_path")"
    mv "$live_path" "$backup_path"
    echo "backed up: $live_path -> $backup_path"
  fi
  mkdir -p "$(dirname "$live_path")"
  ln -s "$repo_path" "$live_path"
  echo "linked: $live_path -> $repo_path"
done <<< "$repo_owned"
