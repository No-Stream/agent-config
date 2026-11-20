#!/usr/bin/env bash
# Rebuild the manifest, score every new or changed text with every detector, write the summaries.
# The SageMaker step waits for its job (10 to 30 minutes), so run this in tmux.
set -euo pipefail
cd "$(dirname "$0")"
private="$(git rev-parse --show-toplevel)/.private/eval/detectors"
read -r -a cpu_launcher <<< "${CPU_LAUNCHER-heavy --threads 8 --mem 16G --}"

uv run manifest.py
"${cpu_launcher[@]}" env TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_PROGRESS_BARS=1 \
  uv run score_local.py
uv run sagemaker_job.py run
uv run summarize.py > "$private/summary.md"
uv run summarize.py --corpus bheijden > "$private/summary-public.md"
echo "wrote $private/summary.md and $private/summary-public.md"
