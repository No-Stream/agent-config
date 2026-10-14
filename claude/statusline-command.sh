#!/bin/bash
# Status line: model, effort/thinking, cwd (relative to $HOME), git branch,
# context usage, and Claude.ai rate-limit usage (5h / 7d) when available.
#
# Fields not present in the stdin JSON for a given session/plan (e.g. `effort`
# on non-reasoning models, or `rate_limits` for non-subscribers) are simply
# omitted rather than faked.

input=$(cat)

model=$(echo "$input" | jq -r '.model.display_name')

effort=$(echo "$input" | jq -r '.effort.level // empty')
if [ -z "$effort" ]; then
  effort=$(echo "$input" | jq -r 'if .thinking.enabled == true then "thinking" else empty end')
fi

cwd=$(echo "$input" | jq -r '.workspace.current_dir')
cwd_display="${cwd/#$HOME/\~}"

branch=$(git --no-optional-locks -C "$cwd" branch --show-current 2>/dev/null)

used_tokens=$(echo "$input" | jq -r '.context_window.total_input_tokens // empty')
max_tokens=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
ctx_display=""
if [ -n "$used_tokens" ] && [ -n "$max_tokens" ]; then
  ctx_display="$((used_tokens / 1000))k/$((max_tokens / 1000))k"
fi

five_hour=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven_day=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')

c_model='\033[36m'
c_effort='\033[33m'
c_dir='\033[32m'
c_branch='\033[35m'
c_ctx_green='\033[32m'
c_ctx_yellow='\033[33m'
c_ctx_orange='\033[38;5;208m'
c_ctx_red='\033[31m'
c_rate='\033[90m'
c_reset='\033[0m'
c_dim='\033[2m'

c_ctx="$c_ctx_green"
if [ -n "$used_tokens" ]; then
  if [ "$used_tokens" -ge 768000 ]; then
    c_ctx="$c_ctx_red"
  elif [ "$used_tokens" -ge 512000 ]; then
    c_ctx="$c_ctx_orange"
  elif [ "$used_tokens" -ge 256000 ]; then
    c_ctx="$c_ctx_yellow"
  fi
fi

line=""
append() {
  [ -z "$1" ] && return
  if [ -n "$line" ]; then
    line="${line}${c_dim} · ${c_reset}"
  fi
  line="${line}$1"
}

append "${c_model}${model}${c_reset}"
[ -n "$effort" ] && append "${c_effort}${effort}${c_reset}"

dir_segment="${c_dir}${cwd_display}${c_reset}"
[ -n "$branch" ] && dir_segment="${dir_segment} ${c_branch}(${branch})${c_reset}"
append "$dir_segment"

[ -n "$ctx_display" ] && append "${c_ctx}ctx ${ctx_display}${c_reset}"

rate_segment=""
[ -n "$five_hour" ] && rate_segment="5h $(printf '%.0f' "$five_hour")%"
if [ -n "$seven_day" ]; then
  [ -n "$rate_segment" ] && rate_segment="${rate_segment}  "
  rate_segment="${rate_segment}7d $(printf '%.0f' "$seven_day")%"
fi
[ -n "$rate_segment" ] && append "${c_rate}${rate_segment}${c_reset}"

printf '%b' "$line"
