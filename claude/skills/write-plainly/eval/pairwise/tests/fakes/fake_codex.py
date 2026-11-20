"""Stand-in for `codex exec` in tests: picks right for every pair in the batch file it is given."""

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
    batch_file = Path(re.search(r"Then read (\S+), which holds", prompt).group(1))
    pair_ids = re.findall(r"^## Pair (\S+)$", batch_file.read_text(), re.MULTILINE)
    lines = [json.dumps({"pair_id": p, "choice": "right", "reason": "stub"}) for p in pair_ids]
    output_file.write_text("Here are the verdicts.\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
