"""Stand-in for sloplint in tests: reports one `exact-exactly` note per "exactly" in each file."""

import json
import re
import sys
from pathlib import Path

CATALOG = [
    {"id": "exact-exactly", "confidence": "medium"},
    {"id": "never-fires", "confidence": "high"},
    {"id": "noisy-low", "confidence": "low"},
]


def _notes(path: str) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8")
    return [
        {"path": path, "rule": "exact-exactly", "column": match.start() + 1}
        for match in re.finditer(r"\bexactly\b", text)
    ]


def main() -> None:
    arguments = sys.argv[1:]
    if arguments == ["--version"]:
        print("0.10.0")
        return
    if arguments == ["rules", "--json"]:
        print(json.dumps(CATALOG))
        return
    if arguments[:4] != ["-o", "json", "check", "--markdown"]:
        sys.exit(f"unexpected sloplint arguments: {arguments}")
    paths = arguments[4:]
    notes = {path: _notes(path) for path in paths}
    if len(paths) == 1:
        print(json.dumps(notes[paths[0]]))
    else:
        print(json.dumps({path: found for path, found in notes.items() if found}))
    sys.exit(1 if any(notes.values()) else 0)


if __name__ == "__main__":
    main()
