"""Stand-in for `uvx --from slop-guard@latest sg -j -c CONFIG FILE...`: counts "not only" per file."""

import json
import sys
from pathlib import Path


def _result(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8").lower()
    counts = {"contrast_pairs": text.count("not only"), "weasel": 0}
    return {"score": 100, "counts": counts, "source": path}


def main() -> None:
    arguments = sys.argv[1:]
    if arguments[0] != "--from" or arguments[2:5] != ["sg", "-j", "-c"]:
        sys.exit(f"unexpected uvx arguments: {arguments}")
    if not Path(arguments[5]).is_file():
        sys.exit(f"slop-guard config {arguments[5]} does not exist")
    results = [_result(path) for path in arguments[6:]]
    print(json.dumps(results[0] if len(results) == 1 else results))
    sys.exit(1 if any(any(result["counts"].values()) for result in results) else 0)


if __name__ == "__main__":
    main()
