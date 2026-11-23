"""Stand-in for the two uvx calls in check-prose.sh: slop-guard's `sg` and `jupytext`."""

import json
import sys
from pathlib import Path
from typing import NoReturn

SLOP_GUARD_OPTIONS = ["-v", "--counts", "-t", "100", "-c"]
JUPYTEXT_OPTIONS = ["--quiet", "--to", "md"]


def _reject(tool: str, arguments: list[str]) -> NoReturn:
    """Exit 2, which check-prose.sh reads as a failed linter, so a leaked option never passes."""
    print(f"unexpected {tool} arguments: {arguments}", file=sys.stderr)
    sys.exit(2)


def _slop_guard(arguments: list[str]) -> int:
    """Score each file 100 less 10 per em dash, in slop-guard's text summary format."""
    if arguments[:5] != SLOP_GUARD_OPTIONS or not Path(arguments[5]).is_file():
        _reject("sg", arguments)
    failed = False
    for path in arguments[6:]:
        text = Path(path).read_text(encoding="utf-8")
        dashes = text.count("—")
        score = 100 - 10 * dashes
        band, symbol = ("clean", ".") if dashes == 0 else ("light", "*")
        counts = f"  (em_dash={dashes})" if dashes else ""
        print(f"{path}: {score}/100 [{band}] ({len(text.split())} words) {symbol}{counts}")
        failed = failed or score < 100
    return 1 if failed else 0


def _jupytext(arguments: list[str]) -> int:
    """Write a notebook's markdown cells as they are and its code cells as fenced blocks."""
    if arguments[:3] != JUPYTEXT_OPTIONS or "-o" not in arguments:
        _reject("jupytext", arguments)
    output = Path(arguments[arguments.index("-o") + 1])
    notebook = json.loads(Path(arguments[-1]).read_text(encoding="utf-8"))
    parts = []
    for cell in notebook["cells"]:
        source = "".join(cell["source"])
        parts.append(source if cell["cell_type"] == "markdown" else f"```python\n{source}\n```")
    output.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    return 0


def main() -> None:
    arguments = sys.argv[1:]
    if arguments[:3] == ["--from", "slop-guard@latest", "sg"]:
        sys.exit(_slop_guard(arguments[3:]))
    if arguments[:3] == ["--from", "jupytext@latest", "jupytext"]:
        sys.exit(_jupytext(arguments[3:]))
    _reject("uvx", arguments)


if __name__ == "__main__":
    main()
