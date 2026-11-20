from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import lint_prose


class TestEmDash:
    def test_flags_prose_and_ignores_markdown_exclusions(self) -> None:
        text = "An em dash — interrupts this sentence.\n> quoted — text\n| table — cell |\n`inline — code`\n```\ncode — block\n```\n[link](https://example.com/a-b)\n"
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("em-dash", 1)
        ]


class TestDashSubstitute:
    def test_flags_pauses_but_keeps_ranges_lists_and_compounds(self) -> None:
        text = "Use this – then that.\nWords - more words\nWords--more words\nWords -- more words\n3–5 and pp. 10–12 and 2020–2024\n- list marker\nA well-known phrase.\n`inline – code`\n```\ncode – block\n```\n> quoted – text\n| table – cell |\nSee https://example.com/a-b.\n"
        rules = [finding.rule for finding in lint_prose.lint_text(text)]
        assert rules == ["dash-substitute"] * 4


class TestCoinedLabel:
    def test_flags_labeled_work_phases_only(self) -> None:
        text = "We completed step 4 and Option B.\nA step function works; the option to wait is available.\nA run of tests passed. Run the script. Use an A/B test.\n`phase 2`\n```\nround 3\n```\n> arm A\n| tier B |\nhttps://example.com/phase-2\n"
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("coined-label", 1),
            ("coined-label", 1),
        ]

    def test_does_not_treat_a_pronoun_as_a_label(self) -> None:
        findings = lint_prose.lint_text("The approach I like to take is simple.\n")
        assert "coined-label" not in [finding.rule for finding in findings]


class TestBoldRunIn:
    def test_flags_line_initial_run_ins(self) -> None:
        text = "**How accurate the clock is.** The clock drifts.\n- **Latency:** 40 ms\n**Standalone bold.**\nThis **mid-sentence:** stays unflagged.\n`**inline:** code`\n```\n**code:** text\n```\n> **quote:** text\n| **table:** cell |\n"
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("bold-run-in", 1),
            ("bold-run-in", 2),
        ]


class TestThinH2Section:
    def test_counts_lists_tables_and_fenced_code_as_body_blocks(self) -> None:
        text = "## Thin\nOne paragraph.\n## List only\n- one\n- two\n## Two blocks\nA paragraph.\n\n```\ncode\n```\n## Table\n| a | b |\n| --- | --- |\n## End\n"
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("thin-h2-section", 1),
            ("thin-h2-section", 3),
            ("thin-h2-section", 12),
            ("thin-h2-section", 15),
        ]


class TestShortParagraphRun:
    def test_flags_three_consecutive_short_paragraphs(self) -> None:
        text = "First short sentence.\n\nSecond short sentence.\n\nThird short sentence.\n\nA longer paragraph has one sentence. It connects two thoughts.\n\nDr. Smith arrived.\n\nThe value is 3.14.\n\nThis is etc. useful.\n"
        findings = lint_prose.lint_text(text)
        assert [(finding.rule, finding.line) for finding in findings] == [
            ("short-paragraph-run", 1)
        ]

    def test_nonparagraph_blocks_break_the_run(self) -> None:
        text = "One sentence.\n\n- list item.\n\nSecond sentence.\n\n> quote.\n\nThird sentence.\n\n| cell |\n"
        assert "short-paragraph-run" not in [
            finding.rule for finding in lint_prose.lint_text(text)
        ]


class TestTitleCaseHeading:
    def test_flags_title_case_and_ignores_sentence_case_or_short_headings(self) -> None:
        text = "## Building Better Writing Habits\n## Building better writing habits\n## API and URL Design Guide\n## Simple Guide\n"
        findings = lint_prose.lint_text(text)
        assert [
            (finding.rule, finding.line)
            for finding in findings
            if finding.rule == "title-case-heading"
        ] == [("title-case-heading", 1)]

    def test_does_not_count_inline_code_words(self) -> None:
        text = "## `Making Every Word Title Case` in this heading\n"
        assert "title-case-heading" not in [
            finding.rule for finding in lint_prose.lint_text(text)
        ]


class TestEndToEnd:
    def test_realistic_readme_finds_exact_issues(self) -> None:
        readme = """# Project Notes

This small service processes events and stores them for later review.
It includes a command line interface and a compact local database.

## Getting Started

Install the package and run `python app.py` from the project directory.
The service writes logs to `./logs` and uses SQLite by default.

## Design Decisions

We finished step 3 — then measured the results.
The baseline covers versions 3–5 and 2020–2024.

The service accepts JSON and CSV input formats.

Requests are validated before they enter the queue.

The worker stores completed jobs in the local database.

## Configuration

Set the `APP_ENV` variable before starting the service.
The default value is `development`.

| Name | Purpose |
| --- | --- |
| APP_ENV | Runtime mode |

## **Deployment Guide**

Use the following command to build a container image.
The image contains the application and its dependencies.

## Troubleshooting

See [the issue tracker](https://example.com/project-with-hyphens/issues).
Run `python app.py --help` to list command line options.

## Further Reading

The API reference describes every supported endpoint.
The examples folder contains requests for common workflows.
"""
        assert len(readme.splitlines()) >= 40
        findings = lint_prose.lint_text(readme)
        assert {(finding.rule, finding.line) for finding in findings} == {
            ("coined-label", 13),
            ("em-dash", 13),
            ("short-paragraph-run", 13),
            ("thin-h2-section", 6),
            ("thin-h2-section", 31),
            ("thin-h2-section", 36),
            ("thin-h2-section", 41),
        }


class TestCli:
    def test_exit_codes_and_json_output(self, tmp_path: Path) -> None:
        script_path = Path(lint_prose.__file__).resolve()
        clean_path = tmp_path / "clean.md"
        flagged_path = tmp_path / "flagged.md"
        clean_path.write_text("A clear sentence.\n", encoding="utf-8")
        flagged_path.write_text("An em dash — here.\n", encoding="utf-8")

        clean_result = subprocess.run(
            [sys.executable, str(script_path), str(clean_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        flagged_result = subprocess.run(
            [sys.executable, str(script_path), "--json", str(flagged_path)],
            capture_output=True,
            text=True,
            check=False,
        )

        assert clean_result.returncode == 0
        assert flagged_result.returncode == 1
        json_findings = json.loads(flagged_result.stdout)
        assert [(finding["path"], finding["rule"]) for finding in json_findings] == [
            (str(flagged_path), "em-dash")
        ]
