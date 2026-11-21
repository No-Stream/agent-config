"""Stand-in for `codex exec --json` in tests: ranks the passages of the set file it is given in
reverse, and reports a `cat` of each file its prompt lists, as codex's JSONL events do.

FAKE_CODEX_SKIP_READS=1 reports only the read of the set file, not of the listed files.
"""

import json
import os
import re
import sys
from pathlib import Path


def command_event(command: str) -> str:
    item = {"type": "command_execution", "command": command, "exit_code": 0}
    return json.dumps({"type": "item.completed", "item": item})


def main() -> None:
    arguments = sys.argv[1:]
    if sys.stdin.read() != "":
        sys.exit("codex must get an empty stdin")
    if "--json" not in arguments:
        sys.exit("the judge reads codex's commands from its --json events")
    output_file = Path(arguments[arguments.index("-o") + 1])
    prompt = arguments[-1]
    set_file = Path(re.search(r"Then read (\S+), which holds", prompt).group(1))
    skip_reads = os.environ.get("FAKE_CODEX_SKIP_READS")
    listed = [] if skip_reads else re.findall(r"^- (/\S+)$", prompt, re.MULTILINE)
    for path in [*listed, set_file]:
        print(command_event(f"/bin/zsh -lc 'cat {path}'"))
    letters = re.findall(r"^### Passage (\S+)$", set_file.read_text(), re.MULTILINE)
    answer = json.dumps({"ranking": "".join(reversed(letters)), "reason": "stub"})
    output_file.write_text(f"Here is the ranking.\n{answer}\n")


if __name__ == "__main__":
    main()
