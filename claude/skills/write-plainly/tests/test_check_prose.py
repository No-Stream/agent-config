"""Run check-prose.sh end to end, with stand-in sloplint, uvx and uv executables on the PATH."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parents[1]
FAKES_DIR = Path(__file__).resolve().parent / "fakes"
CLOSING_LINE_START = "Fix each finding with a structural change"


def _launcher(directory: Path, name: str, script: Path) -> None:
    path = directory / name
    path.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
    path.chmod(0o755)


@pytest.fixture
def run(tmp_path: Path):
    """Run check-prose.sh and check that it left nothing in its temporary directory."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _launcher(bin_dir, "sloplint", FAKES_DIR / "fake_sloplint.py")
    _launcher(bin_dir, "uvx", FAKES_DIR / "fake_uvx.py")
    _launcher(bin_dir, "uv", FAKES_DIR / "fake_uv.py")
    temporary_dir = tmp_path / "tmp"
    temporary_dir.mkdir()
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "TMPDIR": str(temporary_dir),
    }

    def run_check_prose(*arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["bash", str(SKILL_DIR / "check-prose.sh"), *arguments],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
            cwd=tmp_path,
        )
        assert list(temporary_dir.iterdir()) == []
        return result

    return run_check_prose


def _write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
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
        assert CLOSING_LINE_START not in result.stdout
        assert f"{path}: (7 words)" in result.stdout.splitlines()

    def test_findings_end_with_the_closing_line_and_no_slop_guard_score(
        self, run, tmp_path: Path
    ) -> None:
        path = _write(tmp_path, "dash.md", "The branch lends drills — and ladders.\n")
        result = run(path)
        assert result.returncode == 1, result.stderr
        assert result.stdout.splitlines()[-1].startswith(CLOSING_LINE_START)
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

    def test_runs_the_syntax_linter_under_the_notebook_name(self, run, tmp_path: Path) -> None:
        notebook = _notebook(tmp_path, "bread.ipynb", "We ate the bread the old baker sold.\n")
        result = run(notebook)
        assert result.returncode == 1, result.stderr
        lines = result.stdout.splitlines()
        assert "== syntax (lint_syntax.py)" in lines
        hits = [line for line in lines if ": dropped-relativizer: Check:" in line]
        assert [line.split(":")[0] for line in hits] == [notebook]

    def test_a_linter_that_exits_1_with_no_findings_has_failed(self, run, tmp_path: Path) -> None:
        failing_uv = tmp_path / "bin" / "uv"
        failing_uv.write_text("#!/bin/sh\necho 'could not resolve spacy' >&2\nexit 1\n")
        path = _write(tmp_path, "clean.md", "The branch lends drills to its members.\n")
        result = run(path)
        assert result.returncode == 2
        assert CLOSING_LINE_START not in result.stdout

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

    def test_converts_an_earlier_revision_of_a_notebook_with_the_same_name(
        self, run, tmp_path: Path
    ) -> None:
        old = _notebook(tmp_path, "old/loans.ipynb", "# Loans\n\nDrills lead.\n")
        new = _notebook(tmp_path, "loans.ipynb", "# Loans\n\nDrills lead, and ladders follow.\n")
        result = run("--against", old, new)
        assert result.returncode == 1, result.stderr
        assert f"{new}:1:1: revision-growth:" in result.stdout

    def test_a_notebook_jupytext_cannot_read_exits_2(self, run, tmp_path: Path) -> None:
        broken = _write(tmp_path, "broken.ipynb", '<<<<<<< HEAD\n{"cells": []\n')
        result = run(broken)
        assert result.returncode == 2
        assert f"jupytext could not convert {broken}" in result.stderr
        assert result.stdout == ""

    @pytest.mark.parametrize(
        "arguments", [["--against", "missing.md", "draft.md"], ["missing.md"]], ids=["old", "input"]
    )
    def test_a_missing_file_exits_2_with_no_closing_line(
        self, run, tmp_path: Path, arguments: list[str]
    ) -> None:
        _write(tmp_path, "draft.md", "The branch lends drills.\n")
        result = run(*arguments)
        assert result.returncode == 2
        assert "house rules (lint_prose.py) exited with 2" in result.stderr
        assert CLOSING_LINE_START not in result.stdout

    def test_usage_errors_exit_2(self, run, tmp_path: Path) -> None:
        path = _write(tmp_path, "doc.md", "The branch lends drills.\n")
        assert run().returncode == 2
        assert run("--budget").returncode == 2
        assert run("--budget", "5").returncode == 2
        assert run("--color", path).returncode == 2
