#!/usr/bin/env python3
"""Find selected house-style patterns in human-facing prose."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterator, Sequence
from dataclasses import asdict
from itertools import groupby
from pathlib import Path

from lint_prose_document import (
    DOCUMENT_MESSAGES,
    budget_findings,
    heading_density_findings,
    number_density_findings,
    pr_shape_findings,
    revision_findings,
    section_findings,
    short_paragraph_findings,
    summary_findings,
    supporting_statistic_findings,
)
from lint_prose_markdown import (
    LIST_MARKER,
    PROSE_KINDS,
    WORD,
    Block,
    Finding,
    blank_match,
    excerpt,
    heading_text,
    heading_words,
    is_heading,
    mask_quotations,
    masked_lines,
    ordered_items_by_line,
    parse_blocks,
    pr_appendix_as_back_matter,
    sentence_spans,
    top_sections,
)
from lint_prose_patterns import (
    ACRONYM,
    ACRONYM_DEFINITION,
    ANNOUNCING_COLON,
    ANNOUNCING_NOTES,
    ANNOUNCING_QUESTION,
    CAPITALIZED_RUN,
    CLEFT,
    DESCRIBED_ID,
    HASH_NUMBER,
    HEX_ID,
    INLINE_MATH,
    INTENSIFIER,
    LABEL_PATTERN,
    LIST_ENTRY_WORDS,
    OPENING_PHRASE,
    ORDINARY_WORD,
    PHRASE_RULES,
    PRONOUN_I_AFTER_LABEL,
    PUBLIC_IDS,
    PULL_REQUEST_FILE_NAME,
    REVERSE_CLEFT,
    ROMAN_NUMERALS,
    SECTION_LABEL_HEADING,
    SECTION_LABEL_RUN_IN,
    SERIES,
    SHORT_CODE,
    STACCATO_DETERMINERS,
    STANDARD_ID_PREFIXES,
    SYMBOL_IN_PROSE,
    TELL_RULES,
    TITLE_SMALL_WORDS,
    TRACKER_ID,
    UNIVERSAL_ACRONYMS,
)

LONG_SENTENCE_WORDS = 35
LONG_SENTENCE_MAX_PUNCTUATION = 1
COMPLEX_SENTENCE_WORDS = 40
FREE_COMPLEX_SENTENCES = 1
ANNOUNCING_QUESTION_MAX_WORDS = 12
STACCATO_MAX_WORDS = 12
STACCATO_RUN = 3
FREE_TRIADS_PER_SECTION = 2
FREE_INTENSIFIERS_PER_SECTION = 2

MESSAGES = {
    **DOCUMENT_MESSAGES,
    "em-dash": "Em dash; use a comma, parentheses, a colon, a semicolon or a new sentence.",
    "dash-substitute": "Dash used as a pause; use punctuation that shows how the clauses connect.",
    "coined-label": (
        "Check: label or ID that may have been coined during the work (advisory). Name the thing"
        " by what it is, with any ID after that description, unless a smart reader outside the"
        ' work would know it. A reworded label ("step four", "the round-three fix") is still a'
        " label."
    ),
    "bold-run-in": "Bold run-in heading; use a heading or plain prose.",
    "title-case-heading": "Heading looks like Title Case; use sentence case.",
    "stacked-hedge": (
        "Two hedges on one claim; keep the one that states the real uncertainty. Swapping in a"
        ' hedge the pattern misses ("could plausibly") is not a fix.'
    ),
    "nominalization-of": (
        "Check: possible action buried in a noun (advisory). If someone did it, use the verb,"
        ' as in "we implemented X".'
    ),
    "inverted-animacy": (
        "A thing given a person's verb; say what it does (shows, returns) or who does it."
    ),
    "inverted-animacy-check": (
        "Check: a thing that earns, holds, buys or wins (advisory). Make the person the subject,"
        " or say what the thing has or contains. Another verb that gives the thing the same"
        ' agency ("came out ahead") is not a fix.'
    ),
    "back-reference": (
        "Check: points back to earlier text (advisory). Restate the thing here so this text"
        " stands alone."
    ),
    "announcing-sentence": (
        "Check: sentence only announces what follows (advisory). Say the point itself. Dropping"
        ' the colon or a word such as "honest" still announces.'
    ),
    "stock-emphasis": (
        "Stock emphasis phrase; cut it, or state the fact that makes the point. Another emphasis"
        " phrase in its place is not a fix."
    ),
    "history-in-document": (
        "Edit history in the text; state the current fact and drop what it replaced. Rewording"
        ' the old state ("also called", "initially") is not a fix.'
    ),
    "all-caps-emphasis": (
        "Ordinary word in capitals; use italics or plain wording, or backticks if it is code."
    ),
    "rather-than": (
        "Check: a contrast with an alternative the reader may not hold (advisory). If no reader"
        ' expects the alternative, state what the thing is and what follows from it ("the branch'
        ' lends tools, so members can borrow a drill"). Swapping in "instead of", "as opposed to"'
        " or a second sentence about what it is not is the same contrast."
    ),
    "american-spelling": (
        "British spelling; use the American form (color, center, license, organize, analyze,"
        " modeling)."
    ),
    "cannot-rule-out": (
        '"Cannot rule out" reads a result off an interval edge; give the point estimate and say'
        " whether it is distinguishable from noise, with the interval in a table or footnote"
        " unless the reader needs it to decide."
    ),
    "cleft-sentence": (
        "Check: cleft sentence (advisory). Try the plain clause with the real subject first."
        ' Moving the frame into another form ("is the thing that", "is why") is not a fix.'
    ),
    "power-read": (
        "Check: a result read off the test's power, or a winner the intervals do not separate"
        " (advisory). Give the point estimate and say in words how large an effect it is. If"
        ' power matters, say it plainly ("the survey is too small to show a difference between'
        ' branches, and we found none"), with the detectable size in a table or footnote. Show'
        " overlapping results as ranks with their intervals."
    ),
    "universal-negative": (
        "Check: a claim that nothing exists or ever happened (advisory). Say what you searched"
        ' and that you found none ("we could not find a branch that..."); the same absolute'
        ' claim in other words ("branches to date have not...") is not a fix.'
    ),
    "number-notation": (
        "Write a share as a percentage (1.8%) and a ranking metric at a cutoff as NDCG@10."
        ' "Per hundred", "in every 100" and spelled-out forms are the same notation.'
    ),
    "triad-density": (
        f"Check: more than {FREE_TRIADS_PER_SECTION} lists of three in this section (advisory);"
        " keep the ones that matter."
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
    "staccato-run": (
        "Check: a run of short sentences of the same shape (advisory). Join them into one sentence"
        " or a list; changing their first words is not a fix."
    ),
    "borrowed-jargon": (
        "Check: a scientific term borrowed for weight (advisory). Unless the literal sense is"
        ' meant, say "unrelated", "a change" or "a chance".'
    ),
    "chat-phrasing": (
        "Check: chat phrasing addressed to the requester (advisory). Cut it from a document;"
        " it is fine in a message the user sends."
    ),
    "section-label": (
        "Stock section label; name the section by its content, or state the point. Another stock"
        " label is not a fix."
    ),
    "intensifier": (
        f"Check: more than {FREE_INTENSIFIERS_PER_SECTION} intensifiers in this section"
        " (advisory); keep one only where the sentence says less without it. An intensifier"
        ' missing from the list ("really", "super") is not a fix.'
    ),
    "passive-by-agent": (
        "Check: passive voice with a named actor (advisory). Make the actor the subject unless"
        " the sentence is about what was acted on."
    ),
    "formal-word": (
        'Check: a formal word with an everyday one (advisory); write "use", "start", "find out",'
        ' "try", "help", "need" or "before" unless the formal word is the term of art.'
    ),
    "wordy-phrase": (
        'Check: wordy phrase (advisory); use the short form ("to", "about", "because", "if",'
        ' "now") unless the words mean something else here, as in "written in order to disk".'
    ),
    "finance-word": (
        'Check: a finance word for a plain idea (advisory). Write "lost" for "foregone", "earns'
        ' back" for "recoups", "accounts for 30%" for "carries 30%".'
    ),
    "metaphor": (
        "Check: an image or stock idiom in place of the literal claim (advisory). Name the"
        " threshold, method, cause or quantity itself; a different image is not a fix."
    ),
    "signposting": (
        "Check: a signpost that announces what the text covers or that a recap follows"
        " (advisory). State the content itself and cut the recap."
    ),
    "symbol-in-prose": (
        'Check: emoji or arrow in prose (advisory). Write the word ("to", "becomes", "leads to")'
        " or drop the symbol; a menu path such as File → Save can stay."
    ),
}

LINK_TEXT = re.compile(r"\[[^\]\n]*\](?=\()")
CODE_SPAN = re.compile(r"`([^`\n]+)`")
CODE_ID_SHAPES = (TRACKER_ID, HEX_ID, HASH_NUMBER)  # a short code in backticks is a variable name
LABEL_SHAPES = (LABEL_PATTERN, *CODE_ID_SHAPES, SHORT_CODE)
LINE_BREAK = re.compile(r"[ \t]*\n[ \t]*")
INTERNAL_PUNCTUATION = re.compile(r"[,;:](?=\s)|[(—–]|\s--?\s")
BOLD_RUN_IN = re.compile(rf"^\s*(?:{LIST_MARKER}\s+)?(?:\*\*(.+?)\*\*|__(.+?)__)(.*)$")


def _in_link_text(source_line: str, column: int) -> bool:
    return any(link.start() < column - 1 < link.end() for link in LINK_TEXT.finditer(source_line))


def _is_title_case_heading(line: str) -> bool:
    if not is_heading(line):
        return False
    words = heading_words(line)
    if len(words) < 4:
        return False
    candidate_words = [word for word in words[1:] if word.lower() not in TITLE_SMALL_WORDS]
    uppercase_words = [
        word for word in candidate_words if not word.islower() and not word.isupper()
    ]
    return len(uppercase_words) >= 3


def _line_hits(visible: str) -> Iterator[tuple[str, int]]:
    """Yield the rule and column of each hit in one line with its markup blanked."""
    for match in re.finditer("—", visible):
        yield "em-dash", match.start() + 1
    for match in SYMBOL_IN_PROSE.finditer(INLINE_MATH.sub(blank_match, mask_quotations(visible))):
        yield "symbol-in-prose", match.start() + 1
    for match in re.finditer(r"–", visible):
        left = visible[match.start() - 1] if match.start() else ""
        right = visible[match.end()] if match.end() < len(visible) else ""
        between_letters = left.isalpha() and right.isalpha()
        spaced = left.isspace() or right.isspace()
        numeric_range = left.isdigit() and right.isdigit()
        if (between_letters or spaced) and not numeric_range:
            yield "dash-substitute", match.start() + 1
    for match in re.finditer(r"(?<=\w) - (?=\w)|(?<=\w) -- (?=\w)|(?<=\w)--(?=\w)", visible):
        yield "dash-substitute", match.start() + 1
    if _is_title_case_heading(visible):
        yield "title-case-heading", 1
    run_in = BOLD_RUN_IN.match(visible)
    if run_in:
        bold_text = run_in.group(1) or run_in.group(2)
        trailing = run_in.group(3)
        terminal_inside = bold_text.endswith((".", ":"))
        terminal_after = bool(re.match(r"^[:.—–](?=\s|\w)", trailing))
        if trailing.strip() and (terminal_inside or terminal_after):
            yield "bold-run-in", run_in.start(0) + 1


def _line_findings(original_lines: list[str], visible_lines: list[str]) -> list[Finding]:
    return [
        Finding(rule, line_number, column, excerpt(source, column))
        for line_number, (source, visible) in enumerate(zip(original_lines, visible_lines), start=1)
        if visible.strip()
        for rule, column in _line_hits(visible)
    ]


def _with_ids_in_code(block: Block) -> str:
    """Return the block text with inline code put back where the code is nothing but an ID."""
    lines = block.text.split("\n")
    for index, source in enumerate(block.source_lines):
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


def _coined_label_findings(visible_lines: list[str], blocks: list[Block]) -> list[Finding]:
    """Flag labels and IDs, except one in parentheses after a plain description and its reuses."""
    ordered_items = ordered_items_by_line(visible_lines)
    introduced: set[str] = set()
    findings: list[Finding] = []
    for block in blocks:
        if block.kind not in (*PROSE_KINDS, "heading"):
            continue
        text = _with_ids_in_code(block)
        described = [match.span("inside") for match in DESCRIBED_ID.finditer(text)]
        for match in _label_candidates(text):
            line_number, _ = block.position(match.start())
            name = " ".join(match.group().lower().split())
            if any(start <= match.start() < end for start, end in described):
                introduced.add(name)
                continue
            known = _is_known_name(match, text, ordered_items[line_number - 1])
            if name not in introduced and not known:
                findings.append(block.finding("coined-label", match.start()))
    return findings


def _joined_lines(text: str) -> tuple[str, list[int]]:
    """Return the text with each line break and its indentation as one space, and the offset in
    the original text of each character, so a phrase wrapped across lines still matches."""
    offsets: list[int] = []
    position = 0
    for match in LINE_BREAK.finditer(text):
        offsets.extend(range(position, match.start() + 1))
        position = match.end()
    offsets.extend(range(position, len(text)))
    return LINE_BREAK.sub(" ", text), offsets


def _phrase_findings(blocks: list[Block], rules: dict[str, re.Pattern[str]]) -> list[Finding]:
    findings: list[Finding] = []
    for block in blocks:
        text, offsets = _joined_lines(mask_quotations(block.text))
        findings.extend(
            block.finding(rule, offsets[match.start("hit")])
            for rule, pattern in rules.items()
            for match in pattern.finditer(text)
        )
    return findings


def _section_label_findings(blocks: list[Block]) -> list[Finding]:
    """Flag a heading, bold run-in or colon label that is a stock label such as "Key takeaways"."""
    findings: list[Finding] = []
    for block in blocks:
        if block.kind == "heading":
            if SECTION_LABEL_HEADING.match(heading_text(block.text)):
                findings.append(block.finding("section-label", block.start_offset))
        elif block.kind in PROSE_KINDS:
            label = SECTION_LABEL_RUN_IN.match(block.text)
            if label:
                findings.append(block.finding("section-label", label.start("hit")))
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


def _sentence_findings(prose: list[Block]) -> list[Finding]:
    findings: list[Finding] = []
    complex_sentences = 0
    for block in prose:
        for start, end in sentence_spans(block.text):
            rule = _sentence_rule(block.text[start:end])
            if rule is None:
                continue
            if rule == "complex-sentence":
                complex_sentences += 1
                if complex_sentences <= FREE_COMPLEX_SENTENCES:
                    continue
            findings.append(block.finding(rule, start))
    return findings


def _sentence_shape(sentence: str) -> str | None:
    """Name the shape rule a sentence breaks: an announcement of what follows, or a cleft."""
    plain = re.sub(r"[*_]", "", " ".join(sentence.split())).replace("’", "'").lstrip("'(")
    short = len(WORD.findall(plain)) <= ANNOUNCING_QUESTION_MAX_WORDS
    if ANNOUNCING_COLON.match(plain) or ANNOUNCING_NOTES.match(plain):
        return "announcing-sentence"
    if short and ANNOUNCING_QUESTION.match(plain):
        return "announcing-sentence"
    cleft = CLEFT.match(plain) or REVERSE_CLEFT.search(plain)
    if cleft and not plain.rstrip("')]").endswith("?"):
        return "cleft-sentence"
    return None


def _sentence_shape_findings(prose: list[Block]) -> list[Finding]:
    findings: list[Finding] = []
    for block in prose:
        text = mask_quotations(block.text)
        for start, end in sentence_spans(text):
            rule = _sentence_shape(text[start:end])
            if rule:
                findings.append(block.finding(rule, start))
    return findings


def _staccato_key(words: list[str]) -> str | None:
    """Key a sentence by its opening: None when it is long, one key for every determiner such as
    "the" or "each", and otherwise its first word."""
    if len(words) > STACCATO_MAX_WORDS:
        return None
    first_word = words[0].lower()
    return "" if first_word in STACCATO_DETERMINERS else first_word


def _staccato_findings(prose: list[Block]) -> list[Finding]:
    """Flag the first of three or more short sentences in a paragraph that open the same way."""
    findings: list[Finding] = []
    for block in prose:
        if block.kind != "paragraph":
            continue
        spans = sentence_spans(mask_quotations(block.text))
        keyed = [
            (start, _staccato_key(WORD.findall(block.text[start:end]))) for start, end in spans
        ]
        for key, run in groupby(keyed, key=lambda sentence: sentence[1]):
            starts = [start for start, _ in run]
            if key is not None and len(starts) >= STACCATO_RUN:
                findings.append(block.finding("staccato-run", starts[0]))
    return findings


def _three_item_series(text: str, start: int, end: int) -> re.Match[str] | None:
    """Return the first comma series in the sentence with exactly two items before its
    conjunction, reading it after any opening phrase such as "In winter,"."""
    opening = OPENING_PHRASE.match(text, start, end)
    return next(
        (
            match
            for match in SERIES.finditer(text, opening.end() if opening else start, end)
            if match.group("before_conjunction").count(",") == 1
        ),
        None,
    )


def _series_sentences(body: list[Block]) -> Iterator[tuple[Block, re.Match[str]]]:
    """Yield the three-item series of each sentence in the paragraphs, captions and footnotes."""
    for block in body:
        if block.kind not in ("paragraph", "caption", "footnote"):
            continue
        text = mask_quotations(block.text)
        for start, end in sentence_spans(text):
            match = _three_item_series(text, start, end)
            if match:
                yield block, match


def _triad_findings(blocks: list[Block]) -> list[Finding]:
    """Flag each sentence with a three-item series past the free ones in its H1 or H2 section."""
    return [
        block.finding("triad-density", match.start())
        for _, body in top_sections(blocks)
        for block, match in list(_series_sentences(body))[FREE_TRIADS_PER_SECTION:]
    ]


def _intensifier_findings(blocks: list[Block]) -> list[Finding]:
    """Flag each intensifier past the free ones in its H1 or H2 section."""
    findings: list[Finding] = []
    for _, body in top_sections(blocks):
        hits = [
            (block, match.start())
            for block in body
            if block.kind in PROSE_KINDS
            for match in INTENSIFIER.finditer(mask_quotations(block.text))
        ]
        findings.extend(
            block.finding("intensifier", offset)
            for block, offset in hits[FREE_INTENSIFIERS_PER_SECTION:]
        )
    return findings


def _is_ordinary_word(token: str) -> bool:
    return bool(ORDINARY_WORD.fullmatch(token.lower().replace("’", "'")))


def _spells(acronym: str, words: str) -> bool:
    """Whether the words' initials, with or without small words, or their capitals spell it."""
    parts = re.findall(r"[^\s-]+", words)
    initials = "".join(part[0] for part in parts)
    content_initials = "".join(part[0] for part in parts if part.lower() not in TITLE_SMALL_WORDS)
    capitals = re.sub(r"[^A-Z]", "", words)
    return acronym in (initials.upper(), content_initials.upper(), capitals)


def _defined_acronyms(prose: list[Block]) -> dict[str, tuple[int, int]]:
    """Map each acronym the document defines to the block index and offset of its definition."""
    defined: dict[str, tuple[int, int]] = {}
    for index, block in enumerate(prose):
        for match in ACRONYM_DEFINITION.finditer(block.text):
            short, long, spelled = match.group("short", "long", "spelled")
            if short or _spells(long, spelled):
                defined.setdefault(short or long, (index, match.start()))
    return defined


def _all_caps_findings(prose: list[Block]) -> list[Finding]:
    """Flag a run of capitals that holds an ordinary word the document does not define."""
    defined = _defined_acronyms(prose)
    findings: list[Finding] = []
    for block in prose:
        for run in CAPITALIZED_RUN.finditer(mask_quotations(block.text)):
            if any(_is_ordinary_word(word) for word in run.group().split() if word not in defined):
                findings.append(block.finding("all-caps-emphasis", run.start()))
    return findings


def _undefined_acronym_findings(prose: list[Block]) -> list[Finding]:
    """Flag the first use of each acronym when it comes before any definition of it."""
    first_definition = _defined_acronyms(prose)
    first_use: dict[str, tuple[int, int]] = {}
    for index, block in enumerate(prose):
        for match in ACRONYM.finditer(block.text):
            acronym = match.group("acronym")
            line_number, column = block.position(match.start())
            exempt = acronym in UNIVERSAL_ACRONYMS or acronym in ROMAN_NUMERALS
            if exempt or _is_ordinary_word(acronym):
                continue
            if not _in_link_text(block.source_line(line_number), column):
                first_use.setdefault(acronym, (index, match.start()))
    findings: list[Finding] = []
    for acronym, (index, offset) in first_use.items():
        definition = first_definition.get(acronym)
        if definition is None or definition > (index, offset):
            findings.append(prose[index].finding("undefined-acronym", offset))
    return findings


def _blocks(text: str, pr: bool) -> tuple[list[str], list[str], list[Block]]:
    """Return the source lines, the lines with markup blanked, and the blocks of a document; in a
    pull request description, the part below the first horizontal rule is the appendix."""
    original_lines, visible_lines, line_kinds = masked_lines(text)
    blocks = parse_blocks(original_lines, visible_lines, line_kinds)
    return original_lines, visible_lines, pr_appendix_as_back_matter(blocks) if pr else blocks


def lint_text(
    text: str, *, budget: int | None = None, against: str | None = None, pr: bool = False
) -> list[Finding]:
    """Return conservative style findings, retaining original line locations.

    `budget` is the agreed main-text word count, `against` the text of the version this one
    revises, and `pr` marks a pull request description; each turns on the rule that needs it.
    """
    original_lines, visible_lines, blocks = _blocks(text, pr)
    prose = [block for block in blocks if block.kind in PROSE_KINDS]
    headings = [block for block in blocks if block.kind == "heading"]
    findings = _line_findings(original_lines, visible_lines)
    findings.extend(_coined_label_findings(visible_lines, blocks))
    findings.extend(section_findings(blocks))
    findings.extend(short_paragraph_findings(blocks))
    findings.extend(_phrase_findings(prose, PHRASE_RULES))
    findings.extend(_phrase_findings([*prose, *headings], TELL_RULES))
    findings.extend(_section_label_findings(blocks))
    findings.extend(_intensifier_findings(blocks))
    findings.extend(_sentence_findings(prose))
    findings.extend(_sentence_shape_findings(prose))
    findings.extend(_staccato_findings(prose))
    findings.extend(_triad_findings(blocks))
    findings.extend(_all_caps_findings(prose))
    findings.extend(_undefined_acronym_findings(prose))
    findings.extend(number_density_findings(blocks))
    findings.extend(supporting_statistic_findings(blocks))
    findings.extend(heading_density_findings(blocks, prose))
    findings.extend(summary_findings(blocks))
    if budget is not None:
        findings.extend(budget_findings(blocks, budget))
    if against is not None:
        _, _, old_blocks = _blocks(against, pr)
        findings.extend(revision_findings(blocks, old_blocks))
    if pr:
        findings.extend(pr_shape_findings(blocks))
    return sorted(findings, key=lambda finding: (finding.line, finding.column, finding.rule))


def _read_input(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8")


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be a positive whole number, got {value}")
    return number


def _is_pr_description_name(path: str) -> bool:
    """Whether a file name marks a pull request or code review description, as pr-body.md does."""
    return bool(PULL_REQUEST_FILE_NAME.search(Path(path).name))


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write findings as JSON")
    parser.add_argument(
        "--budget", type=_positive_int, metavar="N", help="report main text over 110%% of N words"
    )
    parser.add_argument(
        "--against",
        metavar="OLD",
        help="report growth against OLD, the version a cleanup or review pass revises",
    )
    parser.add_argument(
        "--pr", action="store_true", help="check the shape of a pull request description"
    )
    parser.add_argument("inputs", nargs="+", metavar="INPUT", help="file path or - for stdin")
    options = parser.parse_args(arguments)
    if options.against is not None and len(options.inputs) != 1:
        parser.error("--against compares one input with OLD; give exactly one INPUT")
    paths = [*options.inputs, *([] if options.against is None else [options.against])]
    missing = [path for path in paths if path != "-" and not Path(path).is_file()]
    if missing:
        parser.error(f"no such file: {', '.join(missing)}")
    against = None if options.against is None else _read_input(options.against)
    all_findings: list[dict[str, object]] = []
    text_findings: list[str] = []
    for input_path in options.inputs:
        pr = options.pr or _is_pr_description_name(input_path)
        findings = lint_text(_read_input(input_path), budget=options.budget, against=against, pr=pr)
        for finding in findings:
            message = MESSAGES[finding.rule]
            all_findings.append({**asdict(finding), "message": message, "path": input_path})
            text_findings.append(
                f"{input_path}:{finding.line}:{finding.column}: {finding.rule}: "
                f"{message} | {finding.excerpt}"
            )
    if options.json:
        sys.stdout.write(json.dumps(all_findings, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write("\n".join(text_findings) + ("\n" if text_findings else ""))
    return 1 if all_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
