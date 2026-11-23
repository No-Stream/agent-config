"""Stand-in for `sloplint check --markdown --ignore impact-noun-bare FILE...`: flags em dashes."""

import sys
from pathlib import Path


def main() -> None:
    arguments = sys.argv[1:]
    paths = arguments[4:]
    if arguments[:4] != ["check", "--markdown", "--ignore", "impact-noun-bare"] or not all(
        Path(path).is_file() for path in paths
    ):
        print(f"unexpected sloplint arguments: {arguments}", file=sys.stderr)
        sys.exit(2)
    hits = [
        f"{path}:{number}:{line.index('—') + 1}: info (medium confidence) em-dash  Em dash."
        for path in paths
        for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1)
        if "—" in line
    ]
    if hits:
        print("\n".join(hits))
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
