"""Stand-in for `codex exec` in tests: ranks the passages of the set file it is given in reverse."""

import json
import re
import sys
from pathlib import Path


def main() -> None:
    arguments = sys.argv[1:]
    if sys.stdin.read() != "":
        sys.exit("codex must get an empty stdin")
    output_file = Path(arguments[arguments.index("-o") + 1])
    prompt = arguments[-1]
    set_file = Path(re.search(r"Then read (\S+), which holds", prompt).group(1))
    letters = re.findall(r"^### Passage (\S+)$", set_file.read_text(), re.MULTILINE)
    answer = json.dumps({"ranking": "".join(reversed(letters)), "reason": "stub"})
    output_file.write_text(f"Here is the ranking.\n{answer}\n")


if __name__ == "__main__":
    main()
