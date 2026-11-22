"""Put the skill directory on the import path, as running lint_prose.py as a script does, and
share the helper the linter tests use."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lint_prose


def rule_lines(rule: str, text: str) -> list[int]:
    """Return the line of each finding of one rule, in order."""
    return [finding.line for finding in lint_prose.lint_text(text) if finding.rule == rule]
