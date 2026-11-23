"""Rules about a document's shape: its sections, paragraphs, headings, numbers, summary, length
and revisions."""

from __future__ import annotations

import re

from lint_prose_markdown import (
    LIST_ITEM,
    PROSE_KINDS,
    WORD,
    Block,
    Finding,
    blank_match,
    first_rule,
    heading_level,
    is_summary_heading,
    nested_sections,
    sentence_count,
    sentence_spans,
)
from lint_prose_patterns import (
    ARITHMETIC,
    LABELED_BRACKET_INTERVAL,
    LARGE_SPELLED_NUMBER,
    MEASURED_NUMBER_WORD,
    MULTIPLE_WITHOUT_NUMBER_WORD,
    NOT_A_NUMBER,
    NUMBER,
    RATE_CONTRAST,
    SPELLED_NUMBER,
    SUPPORTING_STATISTIC,
    YEAR_ORDINAL_OR_VERSION,
)

NUMBERS_PER_BLOCK = 2
NUMBERS_PER_100_WORDS = 2
MIN_BODY_WORDS_FOR_DENSITY = 100
FREE_SECTIONS = 6
WORDS_PER_EXTRA_SECTION = 400
MAX_SUMMARY_SENTENCES = 8
MAX_SUMMARY_NUMBERS = 4
MIN_FULL_PARAGRAPH_SENTENCES = 4
BUDGET_TOLERANCE_PERCENT = 110
MAX_PR_SUMMARY_SENTENCES = 6
MAX_PR_SUMMARY_WORDS = 150
PR_SUMMARY_BLOCK_NAMES = {"list-item": "a list", "table": "a table", "code": "a code block"}

DOCUMENT_MESSAGES = {
    "thin-section": (
        "Section has less than its level needs: two blocks under an h1 or h2, and under a lower"
        f" heading a full paragraph's worth of prose, {MIN_FULL_PARAGRAPH_SENTENCES} sentences in"
        " its paragraphs. Merge it into a neighboring section, or fold a subsection into its"
        " parent's prose. Demoting the heading or padding the section is not a fix."
    ),
    "short-paragraph-run": (
        "Run of very short paragraphs; combine related sentences and state how they connect."
    ),
    "heading-density": (
        "More sections than the length supports; merge sections into paragraphs under fewer"
        " headings. Demoting a heading is not a fix."
    ),
    "number-density": (
        "Too many numbers for body prose. Move them into a table or figure, or cut the ones the"
        " reader does not need, and keep only the headline numbers in prose. Spelling a number"
        ' out, writing it as a fraction or as a measured amount in words ("three cents"), or'
        ' rewording it ("all but four") is not a fix.'
    ),
    "supporting-statistic": (
        "Check: a statistic that supports a result (advisory), such as a test statistic, degrees"
        " of freedom, a p-value, an interval or two rates set against each other. Move it to a"
        " table, footnote or appendix, or cut it, unless the reader needs it to decide, and keep"
        ' only the headline number in prose. Spelling it out or rewording it ("plus or minus")'
        " is not a fix."
    ),
    "tldr-shape": (
        f"Summary runs past {MAX_SUMMARY_SENTENCES} sentences or carries more than the headline"
        " numbers; keep what and why, the main findings and the ask. Spelling numbers out or"
        " joining sentences is not a fix."
    ),
    "over-budget": (
        "Main text is over its word budget; cut whole paragraphs or sections, or move them to the"
        " linked appendix. Trimming words inside sentences is not a fix."
    ),
    "revision-growth": (
        "Main text is longer than in the version this revises; a cleanup or review pass should"
        " leave it shorter. Delete, replace and restructure before adding, and cut a sentence for"
        " each one you add. Compressing sentences to get under the old count is not a fix."
    ),
    "appendix-growth": (
        "Check: the appendix and footnotes grew in this revision (advisory). Detail moved out of"
        " the main text belongs there; add new detail only if a reader of the appendix needs it."
    ),
    "pr-shape": (
        "Open with four to six plain sentences on the main change, for reviewers, then a"
        " horizontal rule (---); lists, tables, code, details and the repo's template go below it"
        " as the appendix. Joining sentences to meet the count is not a fix."
    ),
}

LINK_OR_URL = re.compile(r"\]\(|https?://")
DIAGRAM_FENCE = re.compile(r"^\s*(?:```+|~~~+)\s*mermaid\b")


def section_findings(blocks: list[Block]) -> list[Finding]:
    """Flag a section outside the back matter with less body than its level needs.

    A section runs to the next heading of its level or higher, so it holds its subsections. An H1
    or H2 needs two blocks, and a lower heading a full paragraph's worth of prose: four sentences
    in its paragraphs, however they are split. A heading followed straight by a deeper heading only
    groups subsections.
    """
    findings: list[Finding] = []
    for heading, body in nested_sections(blocks):
        grouping = body and body[0].kind == "heading"
        if heading.section == "back-matter" or is_summary_heading(heading.text) or grouping:
            continue
        if _is_thin(body, heading_level(heading.text)) and not _is_reference_list(body):
            findings.append(heading.finding("thin-section", 0))
    return findings


def _is_thin(body: list[Block], level: int) -> bool:
    if level > 2:
        sentences = sum(sentence_count(block.text) for block in body if block.kind == "paragraph")
        return sentences < MIN_FULL_PARAGRAPH_SENTENCES
    content = [block for block in body if block.kind not in ("heading", "break")]
    pairs = zip([None, *content], content)
    merged = [
        block
        for previous, block in pairs
        if not (previous and previous.kind == block.kind == "list-item")
    ]
    return len(merged) < 2


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


def _words(blocks: list[Block]) -> int:
    return sum(len(WORD.findall(block.text)) for block in blocks)


def heading_density_findings(blocks: list[Block], prose: list[Block]) -> list[Finding]:
    """Count the headings at every level below a lone H1 title and outside the back matter
    against a budget."""
    sections = [
        heading.first_line
        for heading, _ in nested_sections(blocks)
        if heading.section != "back-matter"
    ]
    words = _words(prose)
    budget = FREE_SECTIONS + words // WORDS_PER_EXTRA_SECTION
    if len(sections) <= budget:
        return []
    summary = f"{len(sections)} sections; {budget} fit {words} words of prose"
    return [Finding("heading-density", sections[budget], 1, summary)]


def _number_count(sentence: str) -> int:
    masked = NOT_A_NUMBER.sub(blank_match, sentence)
    numbers = [match.group() for match in NUMBER.finditer(masked)]
    counted = [number for number in numbers if not YEAR_ORDINAL_OR_VERSION.fullmatch(number)]
    spelled = [
        match.span()
        for match in SPELLED_NUMBER.finditer(masked)
        if match.group("not_a_count") or LARGE_SPELLED_NUMBER.search(match.group())
    ]
    measured = [
        match
        for match in MEASURED_NUMBER_WORD.finditer(masked)
        if not any(start < match.end() and match.start() < end for start, end in spelled)
    ]
    multiples = MULTIPLE_WITHOUT_NUMBER_WORD.findall(masked)
    return len(counted) + len(spelled) + len(measured) + len(multiples)


def _sentences(block: Block) -> list[str]:
    return [block.text[start:end] for start, end in sentence_spans(block.text)]


def _summary_shape(sentences: list[str]) -> tuple[int, int]:
    """Return the number of sentences and the count of numbers they quote."""
    return len(sentences), sum(_number_count(sentence) for sentence in sentences)


def _fits_summary(sentences: int, numbers: int) -> bool:
    return sentences <= MAX_SUMMARY_SENTENCES and numbers <= MAX_SUMMARY_NUMBERS


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
    if not has_summary and opening in body and _fits_summary(*_summary_shape(_sentences(opening))):
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
    spread and two decimal rates set against each other. Tables, captions and footnotes are exempt.
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
    # The citation mask blanks "[12, 18]", so a labeled bracket is read in the unmasked sentence.
    if SUPPORTING_STATISTIC.search(masked) or LABELED_BRACKET_INTERVAL.search(sentence):
        return True
    return bool(RATE_CONTRAST.search(masked)) and not ARITHMETIC.search(sentence)


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
        sentences, numbers = _summary_shape(
            [sentence for block in prose for sentence in _sentences(block)]
        )
        if not _fits_summary(sentences, numbers):
            measurement = f"summary has {sentences} sentences and {numbers} numbers"
            findings.append(Finding("tldr-shape", heading_line, 1, measurement))
    return findings


def _main_text_words(blocks: list[Block]) -> int:
    """Count the words of paragraphs and list items outside the back matter.

    Headings, tables, figures, captions, code, quotations and footnotes are not main text.
    """
    return _words(
        [
            block
            for block in blocks
            if block.kind in ("paragraph", "list-item") and block.section != "back-matter"
        ]
    )


def _appendix_words(blocks: list[Block]) -> int:
    return _words(
        [
            block
            for block in blocks
            if block.kind in PROSE_KINDS
            and (block.section == "back-matter" or block.kind == "footnote")
        ]
    )


def budget_findings(blocks: list[Block], budget: int) -> list[Finding]:
    """Flag main text more than a tenth over the agreed word budget."""
    words = _main_text_words(blocks)
    if words * 100 <= budget * BUDGET_TOLERANCE_PERCENT:
        return []
    measurement = f"main text has {words} words against a budget of {budget}"
    return [Finding("over-budget", 1, 1, measurement)]


def revision_findings(blocks: list[Block], old_blocks: list[Block]) -> list[Finding]:
    """Flag a revision whose main text grew, and on a second line one whose appendix grew."""
    findings: list[Finding] = []
    words, old_words = _main_text_words(blocks), _main_text_words(old_blocks)
    if words > old_words:
        measurement = f"main text has {words} words against {old_words} in the old version"
        findings.append(Finding("revision-growth", 1, 1, measurement))
    appendix, old_appendix = _appendix_words(blocks), _appendix_words(old_blocks)
    if appendix > old_appendix:
        measurement = (
            f"appendix and footnotes have {appendix} words against {old_appendix}"
            " in the old version"
        )
        findings.append(Finding("appendix-growth", 1, 1, measurement))
    return findings


def _pr_summary_problems(summary: list[Block]) -> list[str]:
    """Name what a pull request summary carries beyond a few plain sentences under one title."""
    prose = [block for block in summary if block.kind in ("paragraph", "caption")]
    sentences = sum(len(sentence_spans(block.text)) for block in prose)
    words = _words(prose)
    kinds = {block.kind for block in summary if not DIAGRAM_FENCE.match(block.source_lines[0])}
    bold_lead_in = any(
        block.kind == "paragraph" and block.source_lines[0].lstrip().startswith(("**", "__"))
        for block in summary
    )
    later_heading = any(
        block.kind == "heading" and position > 0 for position, block in enumerate(summary)
    )
    problems = []
    if sentences > MAX_PR_SUMMARY_SENTENCES or words > MAX_PR_SUMMARY_WORDS:
        problems.append(f"{sentences} sentences and {words} words")
    problems += [name for kind, name in PR_SUMMARY_BLOCK_NAMES.items() if kind in kinds]
    if bold_lead_in:
        problems.append("a bold lead-in")
    if later_heading:
        problems.append("a heading after the title")
    return problems


def pr_shape_findings(blocks: list[Block]) -> list[Finding]:
    """Flag a pull request description whose summary, above the first horizontal rule, is long or
    carries a list, a table, code, a bold lead-in or a heading after one leading title."""
    rule = first_rule(blocks)
    problems = _pr_summary_problems([block for block in blocks[:rule] if block.kind != "masked"])
    if not problems:
        return []
    listed = ", ".join(problems[:-1]) + " and " + problems[-1] if len(problems) > 1 else problems[0]
    where = "summary above the first horizontal rule has"
    if rule == len(blocks):
        where = "no horizontal rule, and the whole description has"
    return [Finding("pr-shape", 1, 1, f"{where} {listed}")]
