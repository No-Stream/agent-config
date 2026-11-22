"""Rules about a document's shape: its sections, paragraph runs, headings, numbers and summary."""

from __future__ import annotations

import re

from lint_prose_markdown import (
    LIST_ITEM,
    PROSE_KINDS,
    WORD,
    Block,
    Finding,
    blank_match,
    heading_level,
    is_summary_heading,
    sentence_count,
    sentence_spans,
    top_sections,
)
from lint_prose_patterns import (
    ARITHMETIC,
    DECIMAL_RATE,
    LARGE_SPELLED_NUMBER,
    NOT_A_NUMBER,
    NUMBER,
    SPELLED_NUMBER,
    SUPPORTING_STATISTIC,
    YEAR_ORDINAL_OR_VERSION,
)

NUMBERS_PER_BLOCK = 2
NUMBERS_PER_100_WORDS = 2
MIN_BODY_WORDS_FOR_DENSITY = 100
FREE_TOP_LEVEL_SECTIONS = 6
WORDS_PER_EXTRA_SECTION = 400
MAX_SUMMARY_SENTENCES = 8
MAX_SUMMARY_NUMBERS = 4

LINK_OR_URL = re.compile(r"\]\(|https?://")


def section_findings(blocks: list[Block]) -> list[Finding]:
    """Flag an H2 section whose body is a single block or a single list."""
    findings: list[Finding] = []
    for heading, body in top_sections(blocks):
        if heading is None or heading_level(heading.text) != 2:
            continue
        if is_summary_heading(heading.text):
            continue
        kinds = [block.kind for block in body if block.kind not in ("heading", "break")]
        pairs = zip(["", *kinds], kinds)
        merged = [kind for previous, kind in pairs if not (kind == previous == "list-item")]
        thin = len(merged) < 2 or merged == ["list-item"]
        if thin and not _is_reference_list(body):
            findings.append(heading.finding("thin-h2-section", 0))
    return findings


def _is_reference_list(body: list[Block]) -> bool:
    first_lines = [block.source_lines[0] for block in body if block.kind == "list-item"]
    items = [line for line in first_lines if LIST_ITEM.match(line)]
    return bool(items) and all(LINK_OR_URL.search(item) for item in items)


def short_paragraph_findings(blocks: list[Block]) -> list[Finding]:
    """Flag three paragraphs of one or two sentences in a row; any other block ends a run."""
    findings: list[Finding] = []
    run: list[Block] = []
    for block in blocks:
        if block.kind != "paragraph" or sentence_count(block.text) > 2:
            run = []
            continue
        run.append(block)
        if len(run) == 3:
            findings.append(run[0].finding("short-paragraph-run", 0))
    return findings


def heading_density_findings(blocks: list[Block], prose: list[Block]) -> list[Finding]:
    """Count sections at the shallowest heading level below a lone H1 title against a budget."""
    levels = [
        (block.first_line, heading_level(block.text)) for block in blocks if block.kind == "heading"
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
    return [Finding("heading-density", sections[budget], 1, summary)]


def _number_count(sentence: str) -> int:
    masked = NOT_A_NUMBER.sub(blank_match, sentence)
    numbers = [match.group() for match in NUMBER.finditer(masked)]
    counted = [number for number in numbers if not YEAR_ORDINAL_OR_VERSION.fullmatch(number)]
    spelled = [
        match
        for match in SPELLED_NUMBER.finditer(masked)
        if match.group("times") or LARGE_SPELLED_NUMBER.search(match.group())
    ]
    return len(counted) + len(spelled)


def _sentences(block: Block) -> list[str]:
    return [block.text[start:end] for start, end in sentence_spans(block.text)]


def _fits_summary(sentences: list[str]) -> bool:
    numbers = sum(_number_count(sentence) for sentence in sentences)
    return len(sentences) <= MAX_SUMMARY_SENTENCES and numbers <= MAX_SUMMARY_NUMBERS


def number_density_findings(blocks: list[Block]) -> list[Finding]:
    """Flag number-heavy body prose: whole documents by density, single blocks by count.

    With no summary section, an opening paragraph shaped like a summary counts as the summary.
    """
    body = [
        block
        for block in blocks
        if block.kind in ("paragraph", "list-item") and block.section == "body"
    ]
    has_summary = any(block.section == "summary" for block in blocks)
    opening = next((block for block in blocks if block.kind == "paragraph"), None)
    if not has_summary and opening in body and _fits_summary(_sentences(opening)):
        body.remove(opening)
    findings: list[Finding] = []
    total_numbers = total_words = 0
    for block in body:
        prose = [sentence for sentence in _sentences(block) if not ARITHMETIC.search(sentence)]
        numbers = sum(_number_count(sentence) for sentence in prose)
        total_numbers += numbers
        total_words += sum(len(WORD.findall(sentence)) for sentence in prose)
        if numbers > NUMBERS_PER_BLOCK:
            findings.append(block.finding("number-density", block.start_offset))
    dense = total_numbers * 100 > NUMBERS_PER_100_WORDS * total_words
    if total_words >= MIN_BODY_WORDS_FOR_DENSITY and dense:
        density = 100 * total_numbers / total_words
        summary = f"body prose carries {density:.1f} numbers per 100 words"
        findings.append(Finding("number-density", body[0].first_line, 1, summary))
    return findings


def supporting_statistic_findings(blocks: list[Block]) -> list[Finding]:
    """Flag a sentence outside the back matter that quotes a statistic supporting a result.

    The statistics are a test statistic, degrees of freedom, a p-value, an interval, a plus-minus
    spread and two rates written as decimals. Tables, captions and footnotes are exempt.
    """
    findings: list[Finding] = []
    for block in blocks:
        if block.kind not in ("paragraph", "list-item") or block.section == "back-matter":
            continue
        for start, end in sentence_spans(block.text):
            if _quotes_supporting_statistic(block.text[start:end]):
                findings.append(block.finding("supporting-statistic", start))
    return findings


def _quotes_supporting_statistic(sentence: str) -> bool:
    masked = NOT_A_NUMBER.sub(blank_match, sentence)
    if SUPPORTING_STATISTIC.search(masked):
        return True
    rates = [match for match in NUMBER.finditer(masked) if DECIMAL_RATE.fullmatch(match.group())]
    return len(rates) > 1 and not ARITHMETIC.search(sentence)


def summary_findings(blocks: list[Block]) -> list[Finding]:
    """Flag a TL;DR, summary or abstract section that is long or quotes many numbers."""
    sections: list[tuple[int, list[Block]]] = []
    for block in blocks:
        if block.kind == "heading" and is_summary_heading(block.text):
            sections.append((block.first_line, []))
        elif block.section == "summary" and block.kind in PROSE_KINDS:
            sections[-1][1].append(block)
    findings: list[Finding] = []
    for heading_line, prose in sections:
        sentences = [sentence for block in prose for sentence in _sentences(block)]
        if not _fits_summary(sentences):
            numbers = sum(_number_count(sentence) for sentence in sentences)
            measurement = f"summary has {len(sentences)} sentences and {numbers} numbers"
            findings.append(Finding("tldr-shape", heading_line, 1, measurement))
    return findings
