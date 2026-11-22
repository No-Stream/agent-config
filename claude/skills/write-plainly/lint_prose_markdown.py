"""The markdown model lint_prose.py reads: masked lines, blocks, sections and sentences."""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from typing import Literal

from lint_prose_patterns import QUOTATION

EXCERPT_LEFT_CONTEXT = 30
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+")
FENCE = re.compile(r"^\s*(```+|~~~+)")
ORDERED_MARKER = r"\d+[.)]"
LIST_MARKER = rf"(?:[-*+]|{ORDERED_MARKER})"
ORDERED_ITEM = re.compile(rf"^\s*{ORDERED_MARKER}\s+")
SUMMARY_HEADING = re.compile(r"(?i)^(?:tl;?\s?dr|summary|abstract|executive summary)$")
BACK_MATTER_HEADING = re.compile(
    r"(?i)^(?:appendix\b.*|appendices|references|bibliography|notes|footnotes)$"
)
CAPTION_START = re.compile(r"(?i)^[*_]{0,3}(?:fig(?:ure)?\.?|table)\s+\d+[a-z]?\s*[.:]")
LIST_ITEM = re.compile(rf"^\s*{LIST_MARKER}\s+")
FOOTNOTE_DEFINITION = re.compile(r"^\s*(?:\[\^[^\]]+\]:|[⁰¹²³⁴⁵⁶⁷⁸⁹]+\s)")
IMAGE_LINE = re.compile(r"^\s*!\[")
THEMATIC_BREAK = re.compile(r"^\s{0,3}(?:[-*_]\s*){3,}$")
TABLE_DELIMITER_ROW = re.compile(r"^\|?\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)*\|?$")
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
OUTER_PIPES = re.compile(r"^\||(?<!\\)\|$")
ABBREVIATION_PERIODS = re.compile(r"(?i:\b(?:e\.g|i\.e|vs|dr|fig|et al)\.)|\betc\.(?!\s+[A-Z])")
SENTENCE_END = re.compile(r"[.!?]+[\"'’”)\]]*(?=\s|\Z)")
WORD = re.compile(r"[A-Za-z0-9]+(?:['’.,-][A-Za-z0-9]+)*")
PROSE_KINDS = ("paragraph", "list-item", "caption", "footnote")

Section = Literal["summary", "back-matter", "body"]


@dataclass(frozen=True)
class Finding:
    """One rule hit; `excerpt` is the source around it, or a measurement for a whole document."""

    rule: str
    line: int
    column: int
    excerpt: str


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
    source_lines: tuple[str, ...]

    def position(self, offset: int) -> tuple[int, int]:
        line_start = self.text.rfind("\n", 0, offset) + 1
        return self.first_line + self.text.count("\n", 0, offset), offset - line_start + 1

    def source_line(self, line_number: int) -> str:
        return self.source_lines[line_number - self.first_line]

    def finding(self, rule: str, offset: int) -> Finding:
        line_number, column = self.position(offset)
        return Finding(rule, line_number, column, excerpt(self.source_line(line_number), column))

    @property
    def start_offset(self) -> int:
        return len(self.text) - len(self.text.lstrip())


@dataclass
class _BlockDraft:
    kind: str
    first_line: int
    after_image: bool
    section: Section
    lines: list[str]

    def finish(self, original_lines: list[str]) -> Block:
        """Build the block; its lines are consecutive source lines from its first line."""
        text = "\n".join(self.lines)
        caption = CAPTION_START.match(text.lstrip()) or (
            self.after_image and sentence_count(text) <= 2
        )
        kind = "caption" if self.kind == "paragraph" and caption else self.kind
        first = self.first_line - 1
        source_lines = tuple(original_lines[first : first + len(self.lines)])
        return Block(kind, self.first_line, text, self.section, source_lines)


def blank_match(match: re.Match[str]) -> str:
    return " " * len(match.group())


def _mask_inline(text: str) -> str:
    text = re.sub(r"<!--.*?-->", blank_match, text, flags=re.DOTALL)
    text = re.sub(r"`+[^`]*`+", blank_match, text)
    text = re.sub(r"\[\d+\]\([^)]*\)", blank_match, text)
    text = re.sub(r"\]\([^)]*\)", blank_match, text)
    text = re.sub(r"https?://\S*[^\s.,;:!?)\]'\"]", blank_match, text, flags=re.IGNORECASE)
    text = re.sub(r"\[\^[^\]]+\]", blank_match, text)
    return text


def mask_quotations(text: str) -> str:
    """Blank double-quoted spans, which quote other words rather than the writer's own."""
    return QUOTATION.sub(blank_match, text)


def _starts_other_block(line: str) -> bool:
    """Whether a line opens a block that ends a table: a heading, quote, fence or break."""
    return bool(
        HEADING.match(line) or FENCE.match(line) or THEMATIC_BREAK.match(line)
    ) or line.lstrip().startswith(">")


def _cell_count(row: str) -> int:
    return len(UNESCAPED_PIPE.findall(OUTER_PIPES.sub("", row.strip()))) + 1


def _is_table_header(line: str, next_line: str) -> bool:
    """Whether a line heads a table: the next line is a delimiter row with as many cells.

    A delimiter row of dashes alone is a heading underline or a break, and one that reads as a
    list item is a list item, so neither makes a table.
    """
    delimiter = next_line.strip()
    return (
        bool(line.strip())
        and not _starts_other_block(line)
        and bool(TABLE_DELIMITER_ROW.match(delimiter))
        and ("|" in delimiter or ":" in delimiter)
        and not LIST_ITEM.match(next_line)
        and _cell_count(line) == _cell_count(delimiter)
    )


def _table_lines(lines: list[str]) -> list[bool]:
    """Flag each line of a GFM table, whose outer pipes are optional.

    A table is a header row, a delimiter row and the rows after them up to a blank line or the
    start of another block; a header row can carry a list marker, since a table can sit in a list.
    """
    flags = [False] * len(lines)
    in_table = False
    for index, line in enumerate(lines):
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        body_row = bool(line.strip()) and not (_starts_other_block(line) or LIST_ITEM.match(line))
        in_table = (in_table and body_row) or _is_table_header(line, next_line)
        flags[index] = in_table
    return flags


def masked_lines(text: str) -> tuple[list[str], list[str], list[str]]:
    """Return the source lines, the lines with markup blanked, and each blanked line's kind.

    The kind is frontmatter, code, quote, table or masked for a blanked line, and empty otherwise.
    """
    original_lines = text.splitlines()
    if text.endswith(("\n", "\r")):
        original_lines.append("")
    visible_lines = list(original_lines)
    kinds = [""] * len(original_lines)
    table_lines = _table_lines(original_lines)
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
        elif stripped.startswith("|") or table_lines[index]:
            kinds[index] = "table"
        else:
            visible_lines[index] = _mask_inline(line)
            if line.strip() and not visible_lines[index].strip():
                kinds[index] = "masked"
            continue
        visible_lines[index] = ""
    return original_lines, visible_lines, kinds


def excerpt(line: str, column: int) -> str:
    """Shorten a source line to a window that starts a few words before the finding."""
    start = column - 1 - EXCERPT_LEFT_CONTEXT
    if start > 0:
        start = line.find(" ", start, column - 1) + 1 or start
        line = "..." + line[start:]
    return textwrap.shorten(line, width=120, placeholder="...")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of each sentence that contains a word."""
    protected = ABBREVIATION_PERIODS.sub(lambda match: match.group().replace(".", "\0"), text)
    ends = [match.end() for match in SENTENCE_END.finditer(protected)]
    spans = []
    for start, end in zip([0, *ends], [*ends, len(text)]):
        segment = text[start:end]
        if WORD.search(segment):
            spans.append((start + len(segment) - len(segment.lstrip()), end))
    return spans


def sentence_count(paragraph: str) -> int:
    return max(1, len(sentence_spans(paragraph)))


def heading_level(line: str) -> int:
    heading = HEADING.match(line)
    return len(heading.group(1)) if heading else 0


def is_heading(line: str) -> bool:
    return heading_level(line) > 0


def heading_text(line: str) -> str:
    heading = re.sub(r"`+[^`]*`+", " ", HEADING.sub("", line))
    return re.sub(r"[*_~]", "", heading).strip(" #:")


def heading_words(line: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9']*", heading_text(line))


def is_summary_heading(line: str) -> bool:
    return is_heading(line) and bool(SUMMARY_HEADING.match(heading_text(line)))


def _section_role(heading_line: str) -> Section:
    if is_summary_heading(heading_line):
        return "summary"
    if BACK_MATTER_HEADING.match(heading_text(heading_line)):
        return "back-matter"
    return "body"


def ordered_items_by_line(visible_lines: list[str]) -> list[int]:
    """Count the ordered-list items in the section (between any two headings) of each line."""
    counts = [0] * len(visible_lines)
    boundaries = [index for index, line in enumerate(visible_lines) if is_heading(line)]
    for start, end in zip([0, *boundaries], [*boundaries, len(visible_lines)]):
        items = sum(1 for line in visible_lines[start:end] if ORDERED_ITEM.match(line))
        counts[start:end] = [items] * (end - start)
    return counts


def parse_blocks(
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
        level = heading_level(visible)
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
    return [draft.finish(original_lines) for draft in drafts]


def top_sections(blocks: list[Block]) -> list[tuple[Block | None, list[Block]]]:
    """Split the blocks at each H1 or H2 heading; the text before the first one has no heading."""
    sections: list[tuple[Block | None, list[Block]]] = [(None, [])]
    for block in blocks:
        if block.kind == "heading" and heading_level(block.text) <= 2:
            sections.append((block, []))
        else:
            sections[-1][1].append(block)
    return sections
