#!/usr/bin/env bash
# Rebuild the manifest, score new or changed texts with the CPU detectors, write the summaries.
# Binoculars and Fast-DetectGPT run apart: `uv run --upgrade sagemaker_job.py run`.
set -euo pipefail
cd "$(dirname "$0")"
private="$(git rev-parse --show-toplevel)/.private/eval/detectors"
read -r -a cpu_launcher <<< "${CPU_LAUNCHER-}"
read -r -a light_launcher <<< "${LIGHT_LAUNCHER-}"

"${light_launcher[@]}" uv run manifest.py
"${cpu_launcher[@]}" env TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_PROGRESS_BARS=1 \
  uv run --upgrade score_local.py
"${light_launcher[@]}" uv run --upgrade summarize.py > "$private/summary.md"
"${light_launcher[@]}" uv run --upgrade summarize.py --corpus bheijden > "$private/summary-public.md"
echo "wrote $private/summary.md and $private/summary-public.md"
