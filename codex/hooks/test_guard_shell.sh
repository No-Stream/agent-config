#!/usr/bin/env bash
# Table test for ~/.codex/hooks/guard_shell.py
cases="$1"
fail=0
while IFS=$'\t' read -r want cmd; do
  out=$(jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c}}' | /usr/bin/python3 ~/.codex/hooks/guard_shell.py)
  rc=$?
  got=ALLOW
  [ -n "$out" ] && got=BLOCK
  [ $rc -ne 0 ] && got="ERR$rc"
  if [ "$got" != "$want" ]; then fail=1; echo "MISMATCH want=$want got=$got: $cmd | $out"; fi
done < "$cases"
echo "table fail=$fail"
jq -nc '{tool_name:"apply_patch",tool_input:{command:"*** Begin Patch\n*** Update File: ~/.ssh/config\n@@\n-a\n+b\n*** End Patch"}}' | /usr/bin/python3 ~/.codex/hooks/guard_shell.py
echo
jq -nc '{tool_name:"apply_patch",tool_input:{command:"*** Begin Patch\n*** Update File: src/a.py\n*** End Patch"}}' | /usr/bin/python3 ~/.codex/hooks/guard_shell.py
echo "benign patch rc=$? (expect no output)"
