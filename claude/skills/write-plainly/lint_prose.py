#!/usr/bin/env python3
"""Find selected house-style patterns in human-facing prose."""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from lint_prose_patterns import (
    ACRONYM,
    ACRONYM_DEFINITION,
    ANNOUNCING_COLON,
    ANNOUNCING_QUESTION,
    ARITHMETIC,
    CAPITALIZED_RUN,
    CLEFT,
    DEFINED_IN_PARENTHESES,
    DESCRIBED_ID,
    HASH_NUMBER,
    HEX_ID,
    LABEL_PATTERN,
    LARGE_SPELLED_NUMBER,
    LIST_ENTRY_WORDS,
    NOT_A_NUMBER,
    NUMBER,
    ORDINARY_WORD,
    PHRASE_RULES,
    PRONOUN_I_AFTER_LABEL,
    PUBLIC_IDS,
    QUOTATION,
    ROMAN_NUMERALS,
    SHORT_CODE,
    SPELLED_NUMBER,
    STANDARD_ID_PREFIXES,
    THREE_ITEM_SERIES,
    TITLE_SMALL_WORDS,
    TRACKER_ID,
    UNIVERSAL_ACRONYMS,
    YEAR_ORDINAL_OR_VERSION,
)

EXCERPT_LEFT_CONTEXT = 30
LONG_SENTENCE_WORDS = 35
LONG_SENTENCE_MAX_PUNCTUATION = 1
COMPLEX_SENTENCE_WORDS = 40
FREE_COMPLEX_SENTENCES = 1
NUMBERS_PER_BLOCK = 2
NUMBERS_PER_100_WORDS = 2
MIN_BODY_WORDS_FOR_DENSITY = 100
FREE_TOP_LEVEL_SECTIONS = 6
WORDS_PER_EXTRA_SECTION = 400
ANNOUNCING_QUESTION_MAX_WORDS = 12
FREE_TRIADS_PER_SECTION = 2
MAX_SUMMARY_SENTENCES = 8
MAX_SUMMARY_NUMBERS = 4

MESSAGES = {
    "em-dash": "Em dash; use a comma, parentheses, a colon, a semicolon or a new sentence.",
    "dash-substitute": "Dash used as a pause; use punctuation that shows how the clauses connect.",
    "coined-label": (
        "Check: label or ID that may have been coined during the work (advisory). Name the thing"
        " by what it is, with any ID after that description, unless the reader already knows it."
    ),
    "bold-run-in": "Bold run-in heading; use a heading or plain prose.",
    "thin-h2-section": (
        "Section has little body; merge it into a neighbour or make it a minor heading."
    ),
    "short-paragraph-run": (
        "Run of very short paragraphs; combine related sentences and state how they connect."
    ),
    "title-case-heading": "Heading looks like Title Case; use sentence case.",
    "stacked-hedge": "Two hedges on one claim; keep the one that states the real uncertainty.",
    "nominalization-of": (
        "Check: possible action buried in a noun (advisory). If someone did it, use the verb,"
        ' as in "we implemented X".'
    ),
    "inverted-animacy": (
        "A thing given a person's verb; say what it does (shows, returns) or who does it."
    ),
    "inverted-animacy-check": (
        "Check: a thing that earns, holds, buys or wins (advisory). Make the person the subject,"
        " or say what the thing has or contains."
    ),
    "back-reference": (
        "Check: points back to earlier text (advisory). Restate the thing here so this text"
        " stands alone."
    ),
    "announcing-sentence": (
        "Check: sentence only announces what follows (advisory). Say the point itself."
    ),
    "stock-emphasis": "Stock emphasis phrase; cut it, or state the fact that makes the point.",
    "history-in-document": (
        "Edit history in the text; state the current fact and drop what it replaced."
    ),
    "all-caps-emphasis": (
        "Ordinary word in capitals; use italics or plain wording, or backticks if it is code."
    ),
    "rather-than": (
        'Check: contrast with "rather than" or ", not" (advisory). If no reader expects the'
        " alternative, state only what is true."
    ),
    "cannot-rule-out": (
        '"Cannot rule out" reads a result off an interval edge; quote the point estimate and'
        " its interval."
    ),
    "cleft-sentence": (
        "Check: cleft sentence (advisory). Try the plain clause with the real subject first."
    ),
    "triad-density": (
        f"Check: more than {FREE_TRIADS_PER_SECTION} lists of three in this section (advisory);"
        " keep the ones that matter."
    ),
    "tldr-shape": (
        f"Summary runs past {MAX_SUMMARY_SENTENCES} sentences or carries more than the headline"
        " numbers; keep what and why, the main findings and the ask."
    ),
    "undefined-acronym": (
        "Check: acronym used before it is defined (advisory). Spell it out at first use with"
        " the short form in parentheses."
    ),
    "long-sentence": (
        "Long sentence with almost no punctuation; split it or mark where its clauses break."
    ),
    "complex-sentence": (
        f"Sentence of {COMPLEX_SENTENCE_WORDS} or more words; split it so each sentence makes"
        " one point."
    ),
    "number-density": (
        "Too many numbers for body prose; move them to a table or figure and say what they show."
    ),
    "heading-density": (
        "More top-level sections than the length supports; merge sections or nest them."
    ),
}

HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+")
FENCE = re.compile(r"^\s*(```+|~~~+)")
ORDERED_ITEM = re.compile(r"^\s*\d+[.)]\s+")
SUMMARY_HEADING = re.compile(r"(?i)^(?:tl;?\s?dr|summary|abstract|executive summary)$")
BACK_MATTER_HEADING = re.compile(
    r"(?i)^(?:appendix\b.*|appendices|references|bibliography|notes|footnotes)$"
)
CAPTION_START = re.compile(r"(?i)^[*_]{0,3}(?:fig(?:ure)?\.?|table)\s+\d+[a-z]?\s*[.:]")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
FOOTNOTE_DEFINITION = re.compile(r"^\s*\[\^[^\]]+\]:")
IMAGE_LINE = re.compile(r"^\s*!\[")
THEMATIC_BREAK = re.compile(r"^\s{0,3}(?:[-*_]\s*){3,}$")
LINK_OR_URL = re.compile(r"\]\(|https?://")
LINK_TEXT = re.compile(r"\[[^\]\n]*\](?=\()")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
CODE_ID_SHAPES = (TRACKER_ID, HEX_ID, HASH_NUMBER)  # a short code in backticks is a variable name
LABEL_SHAPES = (LABEL_PATTERN, *CODE_ID_SHAPES, SHORT_CODE)
ABBREVIATION_PERIODS = re.compile(r"(?i:\b(?:e\.g|i\.e|vs|dr|fig|et al)\.)|\betc\.(?!\s+[A-Z])")
SENTENCE_END = re.compile(r"[.!?]+[\"'’”)\]]*(?=\s|\Z)")
WORD = re.compile(r"[A-Za-z0-9]+(?:['’.,-][A-Za-z0-9]+)*")
INTERNAL_PUNCTUATION = re.compile(r"[,;:](?=\s)|[(—–]|\s--?\s")
PROSE_KINDS = ("paragraph", "list-item", "caption", "footnote")

Section = Literal["summary", "back-matter", "body"]


@dataclass(frozen=True)
class Finding:
    rule: str
    line: int
    column: int
    excerpt: str
    message: str


@dataclass(frozen=True)
class Block:
    """One markdown block, in document order, with markup blanked from its text.

    The prose kinds are paragraph, list-item, caption and footnote. The others are heading,
    break, image, code, quote, table and masked (a line that inline masking left blank).
    """

    kind: str
    first_line: int
    text: str
    section: Section

    def position(self, offset: int) -> tuple[int, int]:
        line_start = self.text.rfind("\n", 0, offset) + 1
        return self.first_line + self.text.count("\n", 0, offset), offset - line_start + 1

    @property
    def start_position(self) -> tuple[int, int]:
        return self.position(len(self.text) - len(self.text.lstrip()))


@dataclass
class _BlockDraft:
    kind: str
    first_line: int
    after_image: bool
    section: Section
    lines: list[str]

    def finish(self) -> Block:
        text = "\n".join(self.lines)
        caption = CAPTION_START.match(text.lstrip()) or (
            self.after_image and _sentence_count(text) <= 2
        )
        kind = "caption" if self.kind == "paragraph" and caption else self.kind
        return Block(kind, self.first_line, text, self.section)


def _blank_match(match: re.Match[str]) -> str:
    return " " * len(match.group())


def _mask_inline(text: str) -> str:
    text = re.sub(r"<!--.*?-->", _blank_match, text, flags=re.DOTALL)
    text = re.sub(r"`+[^`]*`+", _blank_match, text)
    text = re.sub(r"\[\d+\]\([^)]*\)", _blank_match, text)
    text = re.sub(r"\]\([^)]*\)", _blank_match, text)
    text = re.sub(r"https?://\S*[^\s.,;:!?)\]'\"]", _blank_match, text, flags=re.IGNORECASE)
    text = re.sub(r"\[\^[^\]]+\]", _blank_match, text)
    return text


def _mask_quotations(text: str) -> str:
    """Blank double-quoted spans, which quote other words rather than the writer's own."""
    return QUOTATION.sub(_blank_match, text)


def _in_link_text(source_line: str, column: int) -> bool:
    return any(link.start() < column - 1 < link.end() for link in LINK_TEXT.finditer(source_line))


def _visible_lines(text: str) -> tuple[list[str], list[str], list[str]]:
    """Return the source lines, the lines with markup blanked, and each blanked line's kind.

    The kind is frontmatter, code, quote, table or masked for a blanked line, and empty otherwise.
    """
    original_lines = text.splitlines()
    if text.endswith(("\n", "\r")):
        original_lines.append("")
    visible_lines = list(original_lines)
    kinds = [""] * len(original_lines)
    in_frontmatter = bool(original_lines and original_lines[0].strip() == "---")
    fence_marker = ""
    for index, line in enumerate(original_lines):
        stripped = line.lstrip()
        fence_match = FENCE.match(line)
        if in_frontmatter:
            kinds[index] = "frontmatter"
            in_frontmatter = index == 0 or stripped != "---"
        elif fence_marker:
            kinds[index] = "code"
            if fence_match and fence_match.group(1)[0] == fence_marker:
                fence_marker = ""
        elif fence_match:
            kinds[index] = "code"
            fence_marker = fence_match.group(1)[0]
        elif stripped.startswith(">"):
            kinds[index] = "quote"
        elif stripped.startswith("|"):
            kinds[index] = "table"
        else:
            visible_lines[index] = _mask_inline(line)
            if line.strip() and not visible_lines[index].strip():
                kinds[index] = "masked"
            continue
        visible_lines[index] = ""
    return original_lines, visible_lines, kinds


def _excerpt(line: str, column: int) -> str:
    """Shorten a source line to a window that starts a few words before the finding."""
    start = column - 1 - EXCERPT_LEFT_CONTEXT
    if start > 0:
        start = line.find(" ", start, column - 1) + 1 or start
        line = "..." + line[start:]
    return textwrap.shorten(line, width=120, placeholder="...")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of each sentence that contains a word."""
    protected = ABBREVIATION_PERIODS.sub(lambda match: match.group().replace(".", "\0"), text)
    ends = [match.end() for match in SENTENCE_END.finditer(protected)]
    spans = []
    for start, end in zip([0, *ends], [*ends, len(text)]):
        segment = text[start:end]
        if WORD.search(segment):
            spans.append((start + len(segment) - len(segment.lstrip()), end))
    return spans


def _sentence_count(paragraph: str) -> int:
    return max(1, len(_sentence_spans(paragraph)))


def _heading_level(line: str) -> int:
    heading = HEADING.match(line)
    return len(heading.group(1)) if heading else 0


def _is_heading(line: str) -> bool:
    return _heading_level(line) > 0


def _heading_text(line: str) -> str:
    heading = re.sub(r"`+[^`]*`+", " ", HEADING.sub("", line))
    return re.sub(r"[*_~]", "", heading).strip(" #:")


def _heading_words(line: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9']*", _heading_text(line))


def _is_summary_heading(line: str) -> bool:
    return _is_heading(line) and bool(SUMMARY_HEADING.match(_heading_text(line)))


def _section_role(heading_line: str) -> Section:
    if _is_summary_heading(heading_line):
        return "summary"
    if BACK_MATTER_HEADING.match(_heading_text(heading_line)):
        return "back-matter"
    return "body"


def _ordered_items_by_line(visible_lines: list[str]) -> list[int]:
    """Count the ordered-list items in the section (between any two headings) of each line."""
    counts = [0] * len(visible_lines)
    boundaries = [index for index, line in enumerate(visible_lines) if _is_heading(line)]
    for start, end in zip([0, *boundaries], [*boundaries, len(visible_lines)]):
        items = sum(1 for line in visible_lines[start:end] if ORDERED_ITEM.match(line))
        counts[start:end] = [items] * (end - start)
    return counts


def _is_title_case_heading(line: str) -> bool:
    if not _is_heading(line):
        return False
    words = _heading_words(line)
    if len(words) < 4:
        return False
    candidate_words = [word for word in words[1:] if word.lower() not in TITLE_SMALL_WORDS]
    uppercase_words = [
        word for word in candidate_words if word.islower() is False and not word.isupper()
    ]
    return len(uppercase_words) >= 3


def _add_finding(
    findings: list[Finding], rule: str, line_number: int, column: int, source_line: str
) -> None:
    findings.append(
        Finding(rule, line_number, column, _excerpt(source_line, column), MESSAGES[rule])
    )


def _document_finding(rule: str, line_number: int, measurement: str) -> Finding:
    return Finding(rule, line_number, 1, measurement, MESSAGES[rule])


def _line_findings(original_lines: list[str], visible_lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, (source, visible) in enumerate(zip(original_lines, visible_lines), start=1):
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
                _add_finding(findings, "dash-substitute", line_number, match.start() + 1, source)
        for match in re.finditer(r"(?<=\w) - (?=\w)|(?<=\w) -- (?=\w)|(?<=\w)--(?=\w)", visible):
            _add_finding(findings, "dash-substitute", line_number, match.start() + 1, source)
        if _is_title_case_heading(visible):
            _add_finding(findings, "title-case-heading", line_number, 1, source)
        run_in = re.match(r"^\s*(?:[-*]\s+|\d+\.\s+)?(?:\*\*(.+?)\*\*|__(.+?)__)(.*)$", visible)
        if run_in:
            bold_text = run_in.group(1) or run_in.group(2) or ""
            trailing = run_in.group(3)
            terminal_inside = bold_text.endswith((".", ":"))
            terminal_after = bool(re.match(r"^[:.—–](?=\s|\w)", trailing))
            has_following_text = bool(trailing.strip())
            if has_following_text and (terminal_inside or terminal_after):
                _add_finding(findings, "bold-run-in", line_number, run_in.start(0) + 1, source)
    return findings


def _with_ids_in_code(block: Block, original_lines: list[str]) -> str:
    """Return the block text with inline code put back where the code is nothing but an ID."""
    lines = block.text.split("\n")
    first = block.first_line - 1
    for index, source in enumerate(original_lines[first : first + len(lines)]):
        for span in CODE_SPAN.finditer(source):
            if any(shape.fullmatch(span.group(1)) for shape in CODE_ID_SHAPES):
                line = lines[index]
                lines[index] = line[: span.start(1)] + span.group(1) + line[span.end(1) :]
    return "\n".join(lines)


def _label_candidates(text: str) -> list[re.Match[str]]:
    """Return the label and ID matches in the text, first to last, without overlaps."""
    matches = sorted(
        (match for shape in LABEL_SHAPES for match in shape.finditer(text)),
        key=lambda match: (match.start(), -match.end()),
    )
    kept: list[re.Match[str]] = []
    for match in matches:
        if not kept or match.start() >= kept[-1].end():
            kept.append(match)
    return kept


def _is_known_name(match: re.Match[str], text: str, ordered_items: int) -> bool:
    """Whether a label-shaped match is a public name or an entry of the section's own list."""
    if match.re is TRACKER_ID:
        return match.group("prefix") in STANDARD_ID_PREFIXES
    if match.re is not LABEL_PATTERN:
        return match.group() in PUBLIC_IDS
    if PRONOUN_I_AFTER_LABEL.match(text, match.start()):
        return True
    word, label = match.group("word", "label")
    entry = re.match(r"\d+", label)
    return word.lower() in LIST_ENTRY_WORDS and bool(entry) and int(entry.group()) <= ordered_items


def _coined_label_findings(
    original_lines: list[str], visible_lines: list[str], blocks: list[Block]
) -> list[Finding]:
    """Flag labels and IDs, except one in parentheses after a plain description and its reuses."""
    ordered_items = _ordered_items_by_line(visible_lines)
    introduced: set[str] = set()
    findings: list[Finding] = []
    for block in blocks:
        if block.kind not in (*PROSE_KINDS, "heading"):
            continue
        text = _with_ids_in_code(block, original_lines)
        described = [match.span("inside") for match in DESCRIBED_ID.finditer(text)]
        for match in _label_candidates(text):
            line_number, column = block.position(match.start())
            name = " ".join(match.group().lower().split())
            if any(start <= match.start() < end for start, end in described):
                introduced.add(name)
                continue
            known = _is_known_name(match, text, ordered_items[line_number - 1])
            if name not in introduced and not known:
                source = original_lines[line_number - 1]
                _add_finding(findings, "coined-label", line_number, column, source)
    return findings


def _blocks(
    original_lines: list[str], visible_lines: list[str], line_kinds: list[str]
) -> list[Block]:
    """Split the document into blocks; an indented block after a list item stays in the list."""
    drafts: list[_BlockDraft] = []
    open_kind = ""
    in_list = after_image = False
    section: Section = "body"
    section_level = 0
    lines = zip(original_lines, visible_lines, line_kinds)
    for line_number, (source, visible, line_kind) in enumerate(lines, start=1):
        if line_kind == "frontmatter":
            continue
        if line_kind:
            if line_kind != open_kind:
                drafts.append(_BlockDraft(line_kind, line_number, False, section, []))
            drafts[-1].lines.append(visible)
            open_kind, after_image = line_kind, False
            continue
        level = _heading_level(visible)
        if level:
            if section_level and level <= section_level:
                section, section_level = "body", 0
            role = _section_role(visible)
            if not section_level and role != "body":
                section, section_level = role, level
        image = bool(IMAGE_LINE.match(source))
        if level or image or THEMATIC_BREAK.match(visible):
            kind = "heading" if level else "image" if image else "break"
            drafts.append(_BlockDraft(kind, line_number, False, section, [visible]))
            open_kind, in_list, after_image = "", False, image
            continue
        if not visible.strip():
            open_kind = ""
            continue
        footnote = FOOTNOTE_DEFINITION.match(source)
        list_marker = LIST_ITEM.match(visible)
        marker = footnote or list_marker
        if marker or open_kind != "prose":
            in_list = bool(list_marker) or (in_list and visible.startswith("  "))
            kind = "footnote" if footnote else "list-item" if in_list else "paragraph"
            drafts.append(_BlockDraft(kind, line_number, after_image, section, []))
            open_kind, after_image = "prose", False
        drafts[-1].lines.append(" " * marker.end() + visible[marker.end() :] if marker else visible)
    return [draft.finish() for draft in drafts]


def _section_findings(original_lines: list[str], blocks: list[Block]) -> list[Finding]:
    """Flag an H2 section whose body is a single block or a single list."""
    findings: list[Finding] = []
    for index, heading in enumerate(blocks):
        if heading.kind != "heading" or _heading_level(heading.text) != 2:
            continue
        if _is_summary_heading(heading.text):
            continue
        body: list[Block] = []
        for block in blocks[index + 1 :]:
            if block.kind == "heading" and _heading_level(block.text) <= 2:
                break
            body.append(block)
        kinds = [block.kind for block in body if block.kind not in ("heading", "break")]
        pairs = zip(["", *kinds], kinds)
        merged = [kind for previous, kind in pairs if not (kind == previous == "list-item")]
        thin = len(merged) < 2 or merged == ["list-item"]
        if thin and not _is_reference_list(original_lines, body):
            line_number = heading.first_line
            _add_finding(
                findings, "thin-h2-section", line_number, 1, original_lines[line_number - 1]
            )
    return findings


def _is_reference_list(original_lines: list[str], body: list[Block]) -> bool:
    first_lines = [
        original_lines[block.first_line - 1] for block in body if block.kind == "list-item"
    ]
    items = [line for line in first_lines if LIST_ITEM.match(line)]
    return bool(items) and all(LINK_OR_URL.search(item) for item in items)


def _heading_density_findings(blocks: list[Block], prose: list[Block]) -> list[Finding]:
    """Count sections at the shallowest heading level below a lone H1 title against a budget."""
    levels = [
        (block.first_line, _heading_level(block.text))
        for block in blocks
        if block.kind == "heading"
    ]
    if [level for _, level in levels].count(1) == 1:
        levels = [(line, level) for line, level in levels if level != 1]
    top = min((level for _, level in levels), default=0)
    sections = [line for line, level in levels if level == top]
    words = sum(len(WORD.findall(block.text)) for block in prose)
    budget = FREE_TOP_LEVEL_SECTIONS + words // WORDS_PER_EXTRA_SECTION
    if len(sections) <= budget:
        return []
    summary = f"{len(sections)} top-level sections; {budget} fit {words} words of prose"
    return [_document_finding("heading-density", sections[budget], summary)]


def _number_count(sentence: str) -> int:
    masked = NOT_A_NUMBER.sub(_blank_match, sentence)
    numbers = [match.group() for match in NUMBER.finditer(masked)]
    counted = [number for number in numbers if not YEAR_ORDINAL_OR_VERSION.fullmatch(number)]
    spelled = [
        match
        for match in SPELLED_NUMBER.finditer(masked)
        if match.group("times") or LARGE_SPELLED_NUMBER.search(match.group())
    ]
    return len(counted) + len(spelled)


def _number_density_findings(original_lines: list[str], blocks: list[Block]) -> list[Finding]:
    """Flag number-heavy body prose: whole documents by density, single blocks by count."""
    body = [
        block
        for block in blocks
        if block.kind in ("paragraph", "list-item") and block.section == "body"
    ]
    has_summary = any(block.section == "summary" for block in blocks)
    opening = next((block for block in blocks if block.kind == "paragraph"), None)
    if not has_summary and opening in body:
        body.remove(opening)
    findings: list[Finding] = []
    total_numbers = total_words = 0
    for block in body:
        sentences = [block.text[start:end] for start, end in _sentence_spans(block.text)]
        prose = [sentence for sentence in sentences if not ARITHMETIC.search(sentence)]
        numbers = sum(_number_count(sentence) for sentence in prose)
        total_numbers += numbers
        total_words += sum(len(WORD.findall(sentence)) for sentence in prose)
        if numbers > NUMBERS_PER_BLOCK:
            line_number, column = block.start_position
            _add_finding(
                findings, "number-density", line_number, column, original_lines[line_number - 1]
            )
    dense = total_numbers * 100 > NUMBERS_PER_100_WORDS * total_words
    if total_words >= MIN_BODY_WORDS_FOR_DENSITY and dense:
        density = 100 * total_numbers / total_words
        summary = f"body prose carries {density:.1f} numbers per 100 words"
        findings.append(_document_finding("number-density", body[0].first_line, summary))
    return findings


def _phrase_findings(original_lines: list[str], prose: list[Block]) -> list[Finding]:
    findings: list[Finding] = []
    for block in prose:
        text = _mask_quotations(block.text)
        for rule, pattern in PHRASE_RULES.items():
            for match in pattern.finditer(text):
                line_number, column = block.position(match.start("hit"))
                _add_finding(findings, rule, line_number, column, original_lines[line_number - 1])
    return findings


def _sentence_rule(sentence: str) -> str | None:
    """Classify a sentence by length; a run of capitalized words is a name list, not a sentence."""
    words = WORD.findall(sentence)
    initials = [word[0] for word in words if word[0].isalpha()]
    if sum(initial.islower() for initial in initials) * 2 < len(initials):
        return None
    punctuation = len(INTERNAL_PUNCTUATION.findall(sentence))
    if len(words) >= LONG_SENTENCE_WORDS and punctuation <= LONG_SENTENCE_MAX_PUNCTUATION:
        return "long-sentence"
    if len(words) >= COMPLEX_SENTENCE_WORDS:
        return "complex-sentence"
    return None


def _sentence_findings(original_lines: list[str], prose: list[Block]) -> list[Finding]:
    findings: list[Finding] = []
    complex_sentences = 0
    for block in prose:
        for start, end in _sentence_spans(block.text):
            rule = _sentence_rule(block.text[start:end])
            if rule is None:
                continue
            if rule == "complex-sentence":
                complex_sentences += 1
                if complex_sentences <= FREE_COMPLEX_SENTENCES:
                    continue
            line_number, column = block.position(start)
            _add_finding(findings, rule, line_number, column, original_lines[line_number - 1])
    return findings


def _sentence_shape(sentence: str) -> str | None:
    """Name the shape rule a sentence breaks: an announcement of what follows, or a cleft."""
    plain = re.sub(r"[*_]", "", " ".join(sentence.split())).replace("’", "'").lstrip("'(")
    short = len(WORD.findall(plain)) <= ANNOUNCING_QUESTION_MAX_WORDS
    if ANNOUNCING_COLON.match(plain) or (short and ANNOUNCING_QUESTION.match(plain)):
        return "announcing-sentence"
    if CLEFT.match(plain) and not plain.rstrip("')]").endswith("?"):
        return "cleft-sentence"
    return None


def _sentence_shape_findings(original_lines: list[str], prose: list[Block]) -> list[Finding]:
    findings: list[Finding] = []
    for block in prose:
        text = _mask_quotations(block.text)
        for start, end in _sentence_spans(text):
            rule = _sentence_shape(text[start:end])
            if rule:
                line_number, column = block.position(start)
                _add_finding(findings, rule, line_number, column, original_lines[line_number - 1])
    return findings


def _triad_findings(original_lines: list[str], blocks: list[Block]) -> list[Finding]:
    """Flag each sentence with a three-item series past the free ones in its H1 or H2 section."""
    findings: list[Finding] = []
    series = 0
    for block in blocks:
        if block.kind == "heading" and _heading_level(block.text) <= 2:
            series = 0
        if block.kind not in ("paragraph", "caption", "footnote"):
            continue
        text = _mask_quotations(block.text)
        for start, end in _sentence_spans(text):
            match = THREE_ITEM_SERIES.search(text, start, end)
            if not match:
                continue
            series += 1
            if series > FREE_TRIADS_PER_SECTION:
                line_number, column = block.position(match.start())
                source = original_lines[line_number - 1]
                _add_finding(findings, "triad-density", line_number, column, source)
    return findings


def _is_ordinary_word(token: str) -> bool:
    return bool(ORDINARY_WORD.fullmatch(token.lower().replace("’", "'")))


def _all_caps_findings(original_lines: list[str], prose: list[Block]) -> list[Finding]:
    """Flag a run of capitals that holds an ordinary word the document does not define."""
    defined = {
        match.group("acronym")
        for block in prose
        for match in DEFINED_IN_PARENTHESES.finditer(block.text)
    }
    findings: list[Finding] = []
    for block in prose:
        for run in CAPITALIZED_RUN.finditer(_mask_quotations(block.text)):
            if any(_is_ordinary_word(word) for word in run.group().split() if word not in defined):
                line_number, column = block.position(run.start())
                source = original_lines[line_number - 1]
                _add_finding(findings, "all-caps-emphasis", line_number, column, source)
    return findings


def _undefined_acronym_findings(original_lines: list[str], prose: list[Block]) -> list[Finding]:
    """Flag the first use of each acronym when it comes before any definition of it."""
    first_definition: dict[str, tuple[int, int]] = {}
    first_use: dict[str, tuple[int, int]] = {}
    for index, block in enumerate(prose):
        for match in ACRONYM_DEFINITION.finditer(block.text):
            acronym = match.group("short") or match.group("long")
            first_definition.setdefault(acronym, (index, match.start()))
        for match in ACRONYM.finditer(block.text):
            acronym = match.group("acronym")
            line_number, column = block.position(match.start())
            exempt = acronym in UNIVERSAL_ACRONYMS or acronym in ROMAN_NUMERALS
            if exempt or _is_ordinary_word(acronym):
                continue
            if not _in_link_text(original_lines[line_number - 1], column):
                first_use.setdefault(acronym, (index, match.start()))
    findings: list[Finding] = []
    for acronym, (index, offset) in first_use.items():
        definition = first_definition.get(acronym)
        if definition is None or definition > (index, offset):
            line_number, column = prose[index].position(offset)
            source = original_lines[line_number - 1]
            _add_finding(findings, "undefined-acronym", line_number, column, source)
    return findings


def _summary_findings(blocks: list[Block]) -> list[Finding]:
    """Flag a TL;DR, summary or abstract section that is long or quotes many numbers."""
    sections: list[tuple[int, list[Block]]] = []
    for block in blocks:
        if block.kind == "heading" and _is_summary_heading(block.text):
            sections.append((block.first_line, []))
        elif block.section == "summary" and block.kind in PROSE_KINDS:
            sections[-1][1].append(block)
    findings: list[Finding] = []
    for heading_line, prose in sections:
        sentences = [
            block.text[start:end] for block in prose for start, end in _sentence_spans(block.text)
        ]
        numbers = sum(_number_count(sentence) for sentence in sentences)
        if len(sentences) > MAX_SUMMARY_SENTENCES or numbers > MAX_SUMMARY_NUMBERS:
            measurement = f"summary has {len(sentences)} sentences and {numbers} numbers"
            findings.append(_document_finding("tldr-shape", heading_line, measurement))
    return findings


def _short_paragraph_findings(original_lines: list[str], blocks: list[Block]) -> list[Finding]:
    """Flag three paragraphs of one or two sentences in a row; any other block ends a run."""
    findings: list[Finding] = []
    run: list[Block] = []
    for block in blocks:
        if block.kind != "paragraph" or _sentence_count(block.text) > 2:
            run = []
            continue
        run.append(block)
        if len(run) == 3:
            start_line = run[0].first_line
            _add_finding(
                findings, "short-paragraph-run", start_line, 1, original_lines[start_line - 1]
            )
    return findings


def lint_text(text: str) -> list[Finding]:
    """Return conservative style findings, retaining original line locations."""
    original_lines, visible_lines, line_kinds = _visible_lines(text)
    blocks = _blocks(original_lines, visible_lines, line_kinds)
    prose = [block for block in blocks if block.kind in PROSE_KINDS]
    findings = _line_findings(original_lines, visible_lines)
    findings.extend(_coined_label_findings(original_lines, visible_lines, blocks))
    findings.extend(_section_findings(original_lines, blocks))
    findings.extend(_short_paragraph_findings(original_lines, blocks))
    findings.extend(_phrase_findings(original_lines, prose))
    findings.extend(_sentence_findings(original_lines, prose))
    findings.extend(_sentence_shape_findings(original_lines, prose))
    findings.extend(_triad_findings(original_lines, blocks))
    findings.extend(_all_caps_findings(original_lines, prose))
    findings.extend(_undefined_acronym_findings(original_lines, prose))
    findings.extend(_number_density_findings(original_lines, blocks))
    findings.extend(_heading_density_findings(blocks, prose))
    findings.extend(_summary_findings(blocks))
    return sorted(findings, key=lambda finding: (finding.line, finding.column, finding.rule))


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write findings as JSON")
    parser.add_argument("inputs", nargs="+", metavar="INPUT", help="file path or - for stdin")
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
