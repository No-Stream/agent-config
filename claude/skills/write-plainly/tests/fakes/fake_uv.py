"""Stand-in for check-prose.sh's `uv run --script` of lint_syntax.py: runs the script on this
Python, which the tests give the script's dependencies, so the real syntax linter runs."""

import os
import sys

UV_RUN_OPTIONS = ["run", "--quiet", "--upgrade", "--script"]


def main() -> None:
    arguments = sys.argv[1:]
    if arguments[: len(UV_RUN_OPTIONS)] != UV_RUN_OPTIONS:
        print(f"unexpected uv arguments: {arguments}", file=sys.stderr)
        sys.exit(2)
    os.execv(sys.executable, [sys.executable, *arguments[len(UV_RUN_OPTIONS) :]])


if __name__ == "__main__":
    main()
