#!/usr/bin/env bash
# Read-only Codex reviewer on the newest Sol model, split into calls that each fit under the 10-minute Bash limit.
#   codex-review.sh launch <repo_root> <review_dir> <domain>  -> writes the prompt file, prints the job id
#   codex-review.sh wait   <repo_root> <job_id>               -> waits up to 9 min, prints the job status
#   codex-review.sh result <repo_root> <job_id>               -> prints Codex's final message
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
codex_companion="$(ls -d ~/.claude/plugins/cache/openai-codex/codex/*/ | sort -V | tail -1)scripts/codex-companion.mjs"
subcommand="$1"
repo_root="$2"

case "$subcommand" in
  launch)
    review_dir="$3"
    domain="$4"
    prompt_file="$review_dir/prompt-codex-$domain.md"
    printf 'You are the %s reviewer. Read %s/common.md, then %s/%s.md, then follow them. Review bundle: %s. Repo: %s.\n' \
      "$domain" "$skill_dir" "$skill_dir" "$domain" "$review_dir" "$repo_root" > "$prompt_file"
    newest_sol_model="$(python3 -c "
import json, os, re
slugs = [m['slug'] for m in json.load(open(os.path.expanduser('~/.codex/models_cache.json')))['models']
         if m['visibility'] == 'list' and m['slug'].endswith('-sol')]
print(max(slugs, key=lambda slug: [int(part) for part in re.findall(r'\d+', slug)]))")"
    node "$codex_companion" task --background --fresh --model "$newest_sol_model" --effort high \
      --cwd "$repo_root" --prompt-file "$prompt_file" \
      | sed -n 's/.* started in the background as \([A-Za-z0-9-]*\)\..*/\1/p'
    ;;
  wait)
    node "$codex_companion" status "$3" --wait --timeout-ms 540000 --cwd "$repo_root" --json \
      | python3 -c "import json, sys; print(json.load(sys.stdin)['job']['status'])"
    ;;
  result)
    node "$codex_companion" result "$3" --cwd "$repo_root"
    ;;
  *)
    echo "unknown subcommand: $subcommand" >&2
    exit 2
    ;;
esac
