"""Stand-in for `claude -p` in tests: logs each call and answers in Claude Code's JSON format.

Author calls (a JSON schema with `passage`) return four sentences that differ on every call, so
each author stage changes every sentence. A gate fidelity check reports one unsupported change;
the per-task measurement reports one for passage A only. Each call reads the files its prompt
lists. Environment variables change that:

- FAKE_CLAUDE_FAIL_ONCE_ON=<text>: the first call whose prompt contains the text fails.
- FAKE_CLAUDE_SKIP_READS=<text>: a call whose prompt contains the text reads nothing.
- FAKE_CLAUDE_GATE_OUTPUT=<text>: a gate fidelity check answers with the text.
- FAKE_CLAUDE_SERVED_MODEL=<name>: every call reports that model as serving it.
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path


def option(arguments: list[str], name: str) -> str | None:
    return arguments[arguments.index(name) + 1] if name in arguments else None


def main() -> None:
    arguments = sys.argv[1:]
    prompt = sys.stdin.read()
    log_file = Path(os.environ["FAKE_CLAUDE_LOG"])
    call_number = (len(log_file.read_text().splitlines()) if log_file.exists() else 0) + 1
    with log_file.open("a") as log:
        log.write(json.dumps({"arguments": arguments, "prompt": prompt}) + "\n")
    fail_marker = log_file.with_suffix(".failed")
    fail_on = os.environ.get("FAKE_CLAUDE_FAIL_ONCE_ON")
    if fail_on and fail_on in prompt and not fail_marker.exists():
        fail_marker.write_text("failed once\n")
        sys.stderr.write("injected failure\n")
        sys.exit(1)
    model = option(arguments, "--model")
    session_id = option(arguments, "--session-id") or str(uuid.uuid4())
    schema = option(arguments, "--json-schema") or ""
    structured = None
    text = f"Finding from call {call_number}."
    if '"passage"' in schema:
        sentences = [
            f"Sentence {word} of call {call_number}." for word in ("one", "two", "three", "four")
        ]
        structured = {"passage": " ".join(sentences)}
        text = json.dumps(structured)
    elif '"verdicts"' in schema:
        batch_file = Path(re.search(r"Then read (\S+), which holds", prompt).group(1))
        pair_ids = re.findall(r"^## Pair (\S+)$", batch_file.read_text(), re.MULTILINE)
        structured = {
            "verdicts": [{"pair_id": p, "choice": "left", "reason": "stub"} for p in pair_ids]
        }
        text = json.dumps(structured)
    elif "There are" in prompt and "revisions" in prompt:
        labels = re.findall(r"\b([A-Z]): /", prompt)
        text = "\n".join(
            f"## Passage {label}\n"
            + (
                '- UNSUPPORTED: "x" (was: absent). stub'
                if label == "A"
                else "No changes in meaning."
            )
            for label in labels
        )
    elif "The earlier version is the file" in prompt:
        text = os.environ.get(
            "FAKE_CLAUDE_GATE_OUTPUT", '- UNSUPPORTED: "Sentence one" (was: absent). stub'
        )
    result = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": text,
        "session_id": session_id,
        "total_cost_usd": 0.01,
        "modelUsage": {os.environ.get("FAKE_CLAUDE_SERVED_MODEL", f"claude-{model}-5-5"): {}},
    }
    if structured is not None:
        result["structured_output"] = structured
    skip_reads_on = os.environ.get("FAKE_CLAUDE_SKIP_READS")
    reads = (
        []
        if skip_reads_on and skip_reads_on in prompt
        else re.findall(r"^- (/\S+)$", prompt, re.MULTILINE)
    )
    tool_uses = [
        {"type": "tool_use", "name": "Read", "input": {"file_path": path}} for path in reads
    ]
    print(
        json.dumps(
            [{"type": "system"}, {"type": "assistant", "message": {"content": tool_uses}}, result]
        )
    )


if __name__ == "__main__":
    main()
