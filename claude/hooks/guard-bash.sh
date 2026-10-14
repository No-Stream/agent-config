#!/usr/bin/env bash
set -euo pipefail

input_json="$(cat)"
command_text="$(printf '%s' "$input_json" | jq -r '.tool_input.command // ""')"

deny() {
  local reason="$1"
  jq -nc --arg reason "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: $reason
    }
  }'
}

matches() {
  local pattern="$1"
  printf '%s' "$command_text" | grep -Eiq -- "$pattern"
}

if matches '\b(DROP[[:space:]]+(DATABASE|SCHEMA|TABLE)|TRUNCATE[[:space:]]+TABLE)\b'; then
  deny "Blocked: destructive SQL commands must be run manually."
  exit 0
fi

if matches '\b(curl|wget)\b.*\|[[:space:]]*(sudo[[:space:]]+)?(sh|bash|zsh|python[0-9.]*|perl|node|ruby)\b'; then
  deny "Blocked: piping curl/wget output directly into a shell or interpreter is disabled."
  exit 0
fi

if matches '\b(sh|bash|zsh)[[:space:]]+<\([[:space:]]*(curl|wget)\b'; then
  deny "Blocked: process substitution from curl/wget into a shell is disabled."
  exit 0
fi

if matches '\b(curl|wget)\b.*(169\.254\.169\.254|AWS_ACCESS|AWS_SECRET|AWS_SESSION)'; then
  deny "Blocked: command appears to access instance metadata or exfiltrate AWS credentials."
  exit 0
fi

if matches '\b(cat|head|tail|base64|cp)\b.*(^|[[:space:]])([^[:space:]]*/)?\.(aws|ssh)(/|[[:space:]]|$)'; then
  deny "Blocked: reading, encoding, or copying sensitive credential directories is disabled."
  exit 0
fi

if matches '\b(printenv|env|echo|grep)\b.*AWS_(ACCESS|SECRET|SESSION)|\benv\b.*\|.*\bgrep\b.*AWS'; then
  deny "Blocked: printing AWS credential environment variables is disabled."
  exit 0
fi

if matches '\bexport[[:space:]]+AWS_(ACCESS|SECRET|SESSION)'; then
  deny "Blocked: exporting AWS credential variables from the agent is disabled."
  exit 0
fi

if matches '\bpython[0-9.]*\b.*\b(boto3|botocore)\b.*\b(get_credentials|credentials)\b'; then
  deny "Blocked: extracting AWS credentials through boto3/botocore is disabled."
  exit 0
fi

if matches '\bAWS_PROFILE=[^[:space:]]*-prod[[:space:]]+aws[[:space:]]+s3[[:space:]]+(cp|mv|sync)\b.*[[:space:]]s3://'; then
  deny "Blocked: writing to S3 with a prod AWS profile must be run manually."
  exit 0
fi

if matches '\baws[[:space:]].*\b(delete-|terminate-|stop-)'; then
  deny "Blocked: destructive AWS operations must be run manually."
  exit 0
fi

if matches '\baws[[:space:]]+(s3[[:space:]]+(rm|rb)|configure[[:space:]]+(export-credentials|get)|sts[[:space:]]+(assume-role|get-session-token)|iam[[:space:]]+create-access-key|kms[[:space:]]+schedule-key-deletion)\b'; then
  deny "Blocked: sensitive or destructive AWS command must be run manually."
  exit 0
fi

if matches '\b(cdk|terraform|pulumi)[[:space:]]+destroy\b'; then
  deny "Blocked: infrastructure destroy commands must be run manually."
  exit 0
fi

if matches '\bkubectl[[:space:]]+delete[[:space:]]+namespace\b'; then
  deny "Blocked: namespace deletion must be run manually."
  exit 0
fi

if matches '\b(chmod|chown)\b.*(^|[[:space:]])/(boot|etc|lib|lib64|sbin|usr)(/|[[:space:]]|$)'; then
  deny "Blocked: changing ownership or permissions under system directories is disabled."
  exit 0
fi

if matches '\bchmod[[:space:]]+777\b'; then
  deny "Blocked: chmod 777 is disabled by global safety config."
  exit 0
fi

if matches '\b(dd|mkfs|shred|shutdown|reboot|halt|poweroff|systemctl[[:space:]]+(halt|poweroff|reboot)|su|sudo)\b'; then
  deny "Blocked: privileged or system-destructive command must be run manually."
  exit 0
fi

if matches '\b(nc|ncat|netcat)\b'; then
  deny "Blocked: netcat-style commands are disabled by global safety config."
  exit 0
fi
