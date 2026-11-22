"""Run check-prose.sh end to end, with stand-in sloplint and uvx executables on the PATH."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
FAKES_DIR = Path(__file__).resolve().parent / "fakes"
CLOSING_LINE = (
    "Fix each finding with a structural change: a table, a footnote, a cut, regrouped content or a"
    " sentence rewritten around its claim. Rewording until the pattern stops matching (a number in"
    " words or as a fraction, a synonym, a split sentence, a demoted heading) leaves the defect in"
    " place. Keep a flagged span only when the pattern misread it (a quotation, code, a literal"
    " use)."
)


def _launcher(directory: Path, name: str, script: Path) -> None:
    path = directory / name
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    path.chmod(0o755)


@pytest.fixture
def run(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _launcher(bin_dir, "sloplint", FAKES_DIR / "fake_sloplint.py")
    _launcher(bin_dir, "uvx", FAKES_DIR / "fake_uvx.py")
    environment = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}

    def run_check_prose(*arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(SKILL_DIR / "check-prose.sh"), *arguments],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
            cwd=tmp_path,
        )

    return run_check_prose


def _write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def _notebook(tmp_path: Path, name: str, markdown: str) -> str:
    cells = [
        {"cell_type": "markdown", "metadata": {}, "source": [markdown]},
        {
            "cell_type": "code",
            "metadata": {},
            "execution_count": 1,
            "outputs": [{"output_type": "stream", "name": "stdout", "text": ["done — ok\n"]}],
            "source": ["loans = count_loans()  # see the README\n"],
        },
    ]
    notebook = {"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
    return _write(tmp_path, name, json.dumps(notebook))


class TestCheckProse:
    def test_a_clean_file_passes_with_no_closing_line(self, run, tmp_path: Path) -> None:
        path = _write(tmp_path, "clean.md", "The branch lends drills to its members.\n")
        result = run(path)
        assert result.returncode == 0, result.stderr
        assert CLOSING_LINE not in result.stdout
        assert f"{path}: (7 words)" in result.stdout.splitlines()

    def test_findings_end_with_the_closing_line_and_no_slop_guard_score(
        self, run, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, "dash.md", "The branch lends drills — and ladders.\n")
        result = run(path)
        assert result.returncode == 1, result.stderr
        assert result.stdout.splitlines()[-1] == CLOSING_LINE
        assert f"{path}: (7 words)  (em_dash=1)" in result.stdout.splitlines()
        assert "/100" not in result.stdout

    def test_lints_a_notebook_as_markdown_under_the_notebook_name(
        self, run, tmp_path: Path
    ) -> None:
        notebook = _notebook(tmp_path, "loans.ipynb", "# Loans\n\nDrills lead — ladders follow.\n")
        result = run(notebook)
        assert result.returncode == 1, result.stderr
        hits = [line for line in result.stdout.splitlines() if "em-dash" in line]
        assert [line.split(":")[0] for line in hits] == [notebook, notebook]
        assert "loans.md" not in result.stdout
        assert "metadata" not in result.stdout

    def test_passes_budget_against_and_pr_to_lint_prose_only(self, run, tmp_path: Path) -> None:
        old = _write(tmp_path, "old.md", "The branch lends drills.\n")
        new = _write(
            tmp_path,
            "new.md",
            "The branch lends drills and ladders to its members. Loans run for a week.\n",
        )
        result = run("--budget", "5", "--against", old, "--pr", new)
        assert result.returncode == 1, result.stderr
        rules = {line.split(": ")[1] for line in result.stdout.splitlines() if f"{new}:" in line}
        assert {"over-budget", "revision-growth"} <= rules
        assert old not in result.stdout

    def test_converts_a_notebook_given_as_the_old_version(self, run, tmp_path: Path) -> None:
        old = _notebook(tmp_path, "old.ipynb", "# Loans\n\nDrills lead.\n")
        new = _notebook(tmp_path, "new.ipynb", "# Loans\n\nDrills lead, and ladders follow.\n")
        result = run("--against", old, new)
        assert result.returncode == 1, result.stderr
        assert f"{new}:1:1: revision-growth:" in result.stdout

    def test_usage_errors_exit_2(self, run, tmp_path: Path) -> None:
        path = _write(tmp_path, "doc.md", "The branch lends drills.\n")
        assert run().returncode == 2
        assert run("--budget").returncode == 2
        assert run("--budget", "5").returncode == 2
        assert run("--color", path).returncode == 2
