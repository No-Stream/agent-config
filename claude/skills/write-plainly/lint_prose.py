#!/usr/bin/env python3
"""Find selected house-style patterns in human-facing prose."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)

MESSAGES = {
    "em-dash": "Em dash; use a comma, parentheses, a colon, a semicolon or a new sentence.",
    "dash-substitute": "Dash used as a pause; use punctuation that shows how the clauses connect.",
    "coined-label": "Label that may have been coined during the work; name the thing by what it is unless the reader already knows this label.",
    "bold-run-in": "Bold run-in heading; use a heading or plain prose.",
    "thin-h2-section": "Section has little body; merge it into a neighbour or make it a minor heading.",
    "short-paragraph-run": "Run of very short paragraphs; combine related sentences and state how they connect.",
    "title-case-heading": "Heading looks like Title Case; use sentence case.",
}

LABEL_WORDS = (
    "step|phase|stage|round|option|arm|run|variant|approach|plan|track|wave|batch|tier"
)
LABEL_PATTERN = re.compile(rf"\b(?i:{LABEL_WORDS})\s+(?:\d+[a-z]?|[A-Z])\b")
TITLE_SMALL_WORDS = {
    "a",
    "an",
    "the",
    "of",
    "and",
    "or",
    "to",
    "in",
    "on",
    "for",
    "with",
    "vs",
}
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "Dr.", "Fig.", "et al.")


@dataclass(frozen=True)
class Finding:
    rule: str
    line: int
    column: int
    excerpt: str
    message: str


def _blank_match(match: re.Match[str]) -> str:
    return " " * len(match.group())


def _mask_inline(text: str) -> str:
    text = re.sub(r"<!--.*?-->", _blank_match, text, flags=re.DOTALL)
    text = re.sub(r"`+[^`]*`+", _blank_match, text)
    text = re.sub(r"https?://\S+", _blank_match, text, flags=re.IGNORECASE)
    text = re.sub(r"\]\([^)]*\)", _blank_match, text)
    return text


def _visible_lines(text: str) -> tuple[list[str], list[str]]:
    original_lines = text.splitlines()
    if text.endswith(("\n", "\r")):
        original_lines.append("")
    visible_lines = list(original_lines)
    in_frontmatter = bool(original_lines and original_lines[0].strip() == "---")
    in_fence = False
    fence_marker = ""
    for index, line in enumerate(original_lines):
        stripped = line.lstrip()
        if in_frontmatter:
            visible_lines[index] = ""
            if index > 0 and stripped == "---":
                in_frontmatter = False
            continue
        fence_match = re.match(r"(```+|~~~+)", stripped)
        if in_fence:
            visible_lines[index] = ""
            if fence_match and fence_match.group(1)[0] == fence_marker:
                in_fence = False
            continue
        if fence_match:
            visible_lines[index] = ""
            in_fence = True
            fence_marker = fence_match.group(1)[0]
            continue
        if stripped.startswith(">") or stripped.startswith("|"):
            visible_lines[index] = ""
            continue
        visible_lines[index] = _mask_inline(line)
    return original_lines, visible_lines


def _excerpt(line: str) -> str:
    cleaned = " ".join(line.strip().split())
    return cleaned if len(cleaned) <= 120 else cleaned[:117] + "..."


def _sentence_count(paragraph: str) -> int:
    normalized = paragraph
    for abbreviation in ABBREVIATIONS:
        normalized = re.sub(
            re.escape(abbreviation),
            abbreviation.replace(".", "<DOT>"),
            normalized,
            flags=re.IGNORECASE,
        )
    normalized = re.sub(r"(?<=\d)\.(?=\d)", "<DOT>", normalized)
    return max(1, len(re.findall(r"[.!?](?=\s+[A-Z]|\s*$)", normalized)))


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^\s{0,3}#{1,6}\s+", line))


def _heading_words(line: str) -> list[str]:
    heading = re.sub(r"^\s{0,3}#{1,6}\s+", "", line).strip()
    heading = re.sub(r"`+[^`]*`+", " ", heading)
    heading = re.sub(r"[*_~]", "", heading)
    return re.findall(r"[A-Za-z][A-Za-z0-9']*", heading)


def _is_title_case_heading(line: str) -> bool:
    if not re.match(r"^\s{0,3}#{1,6}\s+", line):
        return False
    words = _heading_words(line)
    if len(words) < 4:
        return False
    candidate_words = [
        word for word in words[1:] if word.lower() not in TITLE_SMALL_WORDS
    ]
    uppercase_words = [
        word
        for word in candidate_words
        if word.islower() is False and not word.isupper()
    ]
    return len(uppercase_words) >= 3


def _add_finding(
    findings: list[Finding], rule: str, line_number: int, column: int, source_line: str
) -> None:
    findings.append(
        Finding(rule, line_number, column, _excerpt(source_line), MESSAGES[rule])
    )


def _line_findings(
    original_lines: list[str], visible_lines: list[str]
) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, (source, visible) in enumerate(
        zip(original_lines, visible_lines), start=1
    ):
        if not visible.strip():
            continue
        for match in re.finditer("—", visible):
            _add_finding(findings, "em-dash", line_number, match.start() + 1, source)
        for match in re.finditer(r"–", visible):
            left = visible[match.start() - 1] if match.start() else ""
            right = visible[match.end()] if match.end() < len(visible) else ""
            between_letters = left.isalpha() and right.isalpha()
            spaced = left.isspace() or right.isspace()
            numeric_range = left.isdigit() and right.isdigit()
            if (between_letters or spaced) and not numeric_range:
                _add_finding(
                    findings, "dash-substitute", line_number, match.start() + 1, source
                )
        for match in re.finditer(
            r"(?<=\w) - (?=\w)|(?<=\w) -- (?=\w)|(?<=\w)--(?=\w)", visible
        ):
            _add_finding(
                findings, "dash-substitute", line_number, match.start() + 1, source
            )
        for match in LABEL_PATTERN.finditer(visible):
            if re.match(r"(?i:approach)\s+I\s+like\b", visible[match.start() :]):
                continue
            _add_finding(
                findings, "coined-label", line_number, match.start() + 1, source
            )
        if _is_title_case_heading(visible):
            _add_finding(findings, "title-case-heading", line_number, 1, source)
        run_in = re.match(
            r"^\s*(?:[-*]\s+|\d+\.\s+)?(?:\*\*(.+?)\*\*|__(.+?)__)(.*)$", visible
        )
        if run_in:
            bold_text = run_in.group(1) or run_in.group(2) or ""
            trailing = run_in.group(3)
            terminal_inside = bold_text.endswith((".", ":"))
            terminal_after = bool(re.match(r"^[:.—–](?=\s|\w)", trailing))
            has_following_text = bool(trailing.strip())
            if has_following_text and (terminal_inside or terminal_after):
                _add_finding(
                    findings, "bold-run-in", line_number, run_in.start(0) + 1, source
                )
    return findings


def _section_findings(
    original_lines: list[str], visible_lines: list[str]
) -> list[Finding]:
    findings: list[Finding] = []
    heading_indices = [
        index
        for index, line in enumerate(visible_lines)
        if re.match(r"^\s{0,3}#{1,2}\s+", line)
    ]
    for position, heading_index in enumerate(heading_indices):
        if not re.match(r"^\s{0,3}##\s+", visible_lines[heading_index]):
            continue
        end_index = (
            heading_indices[position + 1]
            if position + 1 < len(heading_indices)
            else len(visible_lines)
        )
        body = original_lines[heading_index + 1 : end_index]
        blocks: list[str] = []
        current: list[str] = []
        current_kind = ""
        in_fence = False
        fence_marker = ""
        for line in body:
            stripped = line.strip()
            is_fence = bool(re.match(r"^\s*(```+|~~~+)", line))
            if in_fence:
                if (
                    is_fence
                    and re.match(r"^\s*(```+|~~~+)", line).group(1)[0] == fence_marker
                ):  # type: ignore[union-attr]
                    in_fence = False
                    blocks.append("code")
                    current_kind = ""
                continue
            if is_fence:
                in_fence = True
                fence_marker = re.match(r"^\s*(```+|~~~+)", line).group(1)[0]  # type: ignore[union-attr]
                if current:
                    blocks.append(current_kind)
                    current = []
                continue
            if not stripped or _is_heading(line):
                if current:
                    blocks.append(current_kind)
                    current = []
                    current_kind = ""
                continue
            if re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", line):
                kind = "list"
            elif stripped.startswith("|"):
                kind = "table"
            elif re.match(r"^\s*!\[[^]]*\]\([^)]*\)", line):
                kind = "image"
            else:
                kind = "paragraph"
            if current and kind != current_kind:
                blocks.append(current_kind)
                current = []
            current_kind = kind
            current.append(line)
        if current:
            blocks.append(current_kind)
        if len(blocks) < 2 or blocks == ["list"]:
            _add_finding(
                findings,
                "thin-h2-section",
                heading_index + 1,
                1,
                original_lines[heading_index],
            )
    return findings


def _short_paragraph_findings(
    original_lines: list[str], visible_lines: list[str]
) -> list[Finding]:
    paragraphs: list[tuple[int, str] | None] = []
    current_lines: list[str] = []
    current_start = 1
    for line_number, (source, line) in enumerate(
        zip(original_lines, visible_lines), start=1
    ):
        structural_block = (
            _is_heading(source)
            or re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|>|\|)|^\s*!", source)
            or re.match(r"^\s*(```+|~~~+)", source)
        )
        if structural_block:
            if current_lines:
                paragraphs.append(
                    (current_start, " ".join(part.strip() for part in current_lines))
                )
                current_lines = []
            paragraphs.append(None)
            continue
        if not line.strip():
            if source.strip():
                if current_lines:
                    paragraphs.append(
                        (
                            current_start,
                            " ".join(part.strip() for part in current_lines),
                        )
                    )
                    current_lines = []
                paragraphs.append(None)
            elif current_lines:
                paragraphs.append(
                    (current_start, " ".join(part.strip() for part in current_lines))
                )
                current_lines = []
            continue
        if not current_lines:
            current_start = line_number
        current_lines.append(line)
    if current_lines:
        paragraphs.append(
            (current_start, " ".join(part.strip() for part in current_lines))
        )

    findings: list[Finding] = []
    run_start: int | None = None
    run_length = 0
    for paragraph in paragraphs:
        if paragraph is None:
            run_start = None
            run_length = 0
            continue
        line_number, paragraph_text = paragraph
        short = _sentence_count(paragraph_text) <= 2
        if short:
            if run_length == 0:
                run_start = line_number
            run_length += 1
        else:
            run_start = None
            run_length = 0
        if run_length == 3 and run_start is not None:
            _add_finding(
                findings,
                "short-paragraph-run",
                run_start,
                1,
                original_lines[run_start - 1],
            )
    return findings


def lint_text(text: str) -> list[Finding]:
    """Return conservative style findings, retaining original line locations."""
    original_lines, visible_lines = _visible_lines(text)
    findings = _line_findings(original_lines, visible_lines)
    findings.extend(_section_findings(original_lines, visible_lines))
    findings.extend(_short_paragraph_findings(original_lines, visible_lines))
    return sorted(
        findings, key=lambda finding: (finding.line, finding.column, finding.rule)
    )


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write findings as JSON")
    parser.add_argument(
        "inputs", nargs="+", metavar="INPUT", help="file path or - for stdin"
    )
    options = parser.parse_args(arguments)
    all_findings: list[dict[str, object]] = []
    text_findings: list[str] = []
    for input_path in options.inputs:
        for finding in lint_text(_read_input(input_path)):
            data = asdict(finding)
            data["path"] = input_path
            all_findings.append(data)
            text_findings.append(
                f"{input_path}:{finding.line}:{finding.column}: {finding.rule}: "
                f"{finding.message} | {finding.excerpt}"
            )
    if options.json:
        sys.stdout.write(json.dumps(all_findings, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write("\n".join(text_findings) + ("\n" if text_findings else ""))
    return 1 if all_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
