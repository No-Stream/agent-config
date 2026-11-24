"""Invariants of the shared text preparation in lint_prose_markdown.py and of its consumers' word
rules, as checks that return each place where one breaks.

The preparation must not invent a word, drop prose it does not mean to drop, split a word of
letters, or lose track of where a word came from. `stretch_violations` and `document_violations`
check the paper's preparation itself; `linter_violations`, `parse_violations`,
`surprisal_violations` and `clean_row_violations` check what each consumer reads, split into
words as that consumer splits them. What the preparation drops, splits or replaces on purpose is
listed in DROPPED_ON_PURPOSE, SPLIT_ON_PURPOSE and REPLACED_ON_PURPOSE, and each such span is
checked against CommonMark, pandoc or the document's own lines rather than against the
preparation's patterns.
"""

from __future__ import annotations

import bisect
import re
import sys
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))
sys.path.insert(0, str(SKILL_DIR / "eval" / "surprisal"))

import prose
import reference
from spacy.tokens import Doc

import lint_prose_markdown
import syntax_features
from lint_prose_markdown import (
    PLACEHOLDER,
    PROSE_KINDS,
    Block,
    Stretch,
    masked_lines,
    parse_blocks,
    prose_blocks,
    stretches,
)

INVENTED = "invented-word"
DROPPED = "dropped-prose"
SPLIT = "split-word"
OFFSET = "offset"

# Source spans whose words the preparation drops on purpose, and why.
DROPPED_ON_PURPOSE = {
    "frontmatter": "metadata above the text, closed by a second --- line",
    "code": "fenced code",
    "quote": "a block quote quotes other words; eval/README.md lists it as skipped",
    "table": "eval/README.md lists tables as skipped",
    "heading": "headings are not prose blocks for any consumer",
    "image": "an image's alt text and address are not read in line",
    "comment": "an HTML comment is not shown",
    "link-target": "a link's address or reference label is not shown",
    "citation": "a numbered citation link such as [1](url) reads as a reference, not a word",
    "footnote": "a footnote reference is a mark, not a word",
    "html-tag": "a CommonMark HTML tag and its attributes are not shown",
    "break-tag": "a CommonMark HTML tag and its attributes are not shown",
    "stop": "an arrow, emoji or stray math symbol ends a stretch",
    "list-marker": "a list or footnote marker",
    "escape": "the backslash of a CommonMark escape; the character after it is kept",
}
# Words the preparation splits on purpose, and why.
SPLIT_ON_PURPOSE = {
    "url-after-word": "a URL scheme glued to a word starts the URL there, as the writer meant",
}
# Source spans the preparation replaces with PLACEHOLDER on purpose, and why.
REPLACED_ON_PURPOSE = {
    "code-span": "inline code, as CommonMark delimits it",
    "url": "a bare or angle-bracket URL",
    "math": "inline math, as pandoc's dollar rule or a TeX command delimits it",
    "path": "a file path",
    "identifier": "a code identifier with an underscore",
    "call": "a function call",
    "dotted-name": "a dotted module or attribute name",
}
# Markup that may sit inside a word, so the letters on either side still form one word.
INTRAWORD_MARKUP = {
    *("emphasis", "link-target", "link-bracket", "comment", "footnote", "html-tag", "escape"),
}
# Tags that end a line or a block, so no word continues across them.
BREAK_TAGS = {
    *("address", "article", "aside", "blockquote", "br", "dd", "details", "div", "dl", "dt"),
    *("figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr"),
    *("img", "li", "ol", "p", "pre", "section", "summary", "table", "td", "th", "tr", "ul"),
}


def _marks() -> str:
    """Every character in Unicode category M (combining marks), as character-class ranges."""
    ranges: list[list[int]] = []
    for code in range(sys.maxunicode + 1):
        if unicodedata.category(chr(code))[0] != "M":
            continue
        if ranges and ranges[-1][1] == code - 1:
            ranges[-1][1] = code
        else:
            ranges.append([code, code])
    return "".join(f"{chr(low)}-{chr(high)}" for low, high in ranges)


# A run of letters and digits in any script, each with the combining marks after it.
WORD_RUN = re.compile(f"(?:[^\\W_]+[{_marks()}]*)+")
POSSESSIVE = re.compile(r"['’]s")
ASCII_PUNCTUATION = r"[!-/:-@\[-`{-~]"
# Markup read on the source; the first alternative that matches at a position decides.
SOURCE_PIECE = re.compile(
    r"(?P<comment><!--.*?-->)"
    r"|(?P<image>!\[[^\]]*\]\([^)]*\))"
    r"|(?P<citation>\[\d+\]\([^)]*\))"
    r"|(?P<target>\]\([^)]*\)|\]\[[^\]]*\])"
    r"|(?P<footnote>\[\^[^\]]+\])"
    r"|(?P<tag></?[A-Za-z][^>\n]*>)"
    r"|(?P<emphasis>\*+|_+|~~)"
    r"|(?P<bracket>[\[\]])"
    r"|(?P<space>\s+)"
    r"|(?P<stop><=>|->|=>|<-|[←-⇿⟰-⟿⤀-⥿]"
    r"|[\U0001f000-\U0001faff☀-➿️]"
    r"|[=≈≠≤≥±×÷∑∏√∞<>])"
    r"|(?P<other>.)",
    re.DOTALL,
)
# CommonMark's raw HTML tags, and the rest of an inline link after its text.
ATTRIBUTE = r"""\s+[A-Za-z_:][A-Za-z0-9_.:-]*(?:\s*=\s*(?:[^\s"'=<>`]+|'[^']*'|"[^"]*"))?"""
HTML_TAG = re.compile(rf"<[A-Za-z][A-Za-z0-9-]*(?:{ATTRIBUTE})*\s*/?>|</[A-Za-z][A-Za-z0-9-]*\s*>")
LINK_DESTINATION = r"(?:<[^<>\n]*>|(?:[^\s()\\]|\\.|\((?:[^\s()\\]|\\.)*\))+)"
LINK_TITLE = r"""(?:"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\((?:[^()\\]|\\.)*\))"""
LINK_TAIL = re.compile(rf"\]\(\s*(?:{LINK_DESTINATION}(?:\s+{LINK_TITLE})?)?\s*\)|\]\[[^\]]*\]")
LINK_OPEN = re.compile(r"\[(?:[^\[\]\\]|\\.|\[[^\[\]]*\])*\](?:\(|\[)")
IMAGE_OR_LINK = re.compile(r"!?\[[^\]]*\]\([^)]*\)")


@dataclass(frozen=True)
class Violation:
    """One place where an invariant breaks: which one, its cause, the consumer whose text breaks
    it, the word involved, and where the source has it."""

    invariant: str
    cause: str
    consumer: str
    word: str
    line: int
    column: int


def _violation(
    invariant: str, cause: str, consumer: str, word: str, block: Block, offset: int
) -> Violation:
    line, column = block.position(offset)
    return Violation(invariant, cause, consumer, word, line, column)


def _block_source(block: Block) -> str:
    return "\n".join(block.source_lines)


def word_runs(text: str, start: int = 0) -> list[tuple[int, int]]:
    """The (start, end) of each run of letters, digits and combining marks in text."""
    return [match.span() for match in WORD_RUN.finditer(text, start)]


def code_spans(source: str) -> list[tuple[int, int]]:
    """The code spans CommonMark finds in one block's source: a run of backticks, not escaped,
    up to the next run of the same length; a run with no such partner is literal."""
    spans = []
    position = 0
    while (opening := source.find("`", position)) != -1:
        run_end = opening
        while run_end < len(source) and source[run_end] == "`":
            run_end += 1
        backslashes = len(source[:opening]) - len(source[:opening].rstrip("\\"))
        if backslashes % 2:
            opening += 1
        length = run_end - opening
        closing = run_end
        while length and (closing := source.find("`", closing)) != -1:
            closing_end = closing
            while closing_end < len(source) and source[closing_end] == "`":
                closing_end += 1
            if closing_end - closing == length:
                spans.append((opening, closing_end))
                break
            closing = closing_end
        position = spans[-1][1] if spans and spans[-1][0] == opening else run_end
    return spans


def math_end(source: str, start: int) -> int | None:
    """Where inline math opened by the dollar at `start` ends: at the next dollar on the line when
    pandoc's rule holds (no space inside either dollar, no digit after the closing one), or when a
    TeX command lies between them."""
    closing = source.find("$", start + 1)
    if closing == -1 or "\n" in source[start:closing] or closing == start + 1:
        return None
    if source[closing + 1 : closing + 2].isdigit():
        return None
    inside = source[start + 1 : closing]
    pandoc = not inside[0].isspace() and not inside[-1].isspace()
    return closing + 1 if pandoc or re.search(r"\\[A-Za-z]", inside) else None


def _piece_kind(source: str, match: re.Match[str]) -> str:
    """Name the markup piece a SOURCE_PIECE match found, judged by CommonMark where it decides
    whether the piece is markup at all."""
    kind = match.lastgroup
    if kind == "tag":
        if not HTML_TAG.fullmatch(match.group()):
            return "not-a-tag"
        name = re.match(r"</?([A-Za-z][A-Za-z0-9-]*)", match.group()).group(1).lower()
        return "break-tag" if name in BREAK_TAGS else "html-tag"
    if kind == "target":
        tail = LINK_TAIL.match(source, match.start())
        return "link-target" if tail and tail.end() >= match.end() else "not-a-link"
    if kind == "bracket":
        opens = match.group() == "[" and LINK_OPEN.match(source, match.start())
        closes = match.group() == "]" and source[match.end() : match.end() + 1] in ("(", "[")
        return "link-bracket" if opens or closes else "bracket"
    return kind


def _pieces(source: str, start: int, end: int) -> list[tuple[int, int, str]]:
    """Split source[start:end], which the preparation dropped, into its markup pieces."""
    pieces = []
    position = start
    while position < end:
        # An escape's character lies past the dropped text, so it is read on the whole source.
        if source[position] == "\\" and re.match(
            ASCII_PUNCTUATION, source[position + 1 : position + 2]
        ):
            pieces.append((position, position + 1, "escape"))
            position += 1
            continue
        match = SOURCE_PIECE.match(source, position, end)
        pieces.append((match.start(), match.end(), _piece_kind(source, match)))
        position = match.end()
    return pieces


def _is_word_character(character: str) -> bool:
    return bool(WORD_RUN.fullmatch(character))


def _cuts_word(source: str, offset: int) -> bool:
    """Whether a span edge at `offset` falls between two characters of one word."""
    return 0 < offset < len(source) and all(
        _is_word_character(character) for character in source[offset - 1 : offset + 1]
    )


def _replaced_kind(text: str) -> str:
    if text.startswith("`"):
        return "code-span"
    if text.startswith("$"):
        return "math"
    if text.startswith("<") or re.match(r"(?i)https?://", text):
        return "url"
    if "/" in text:
        return "path"
    if text.endswith("()"):
        return "call"
    if "_" in text:
        return "identifier"
    return "dotted-name" if "." in text else "unknown"


@dataclass
class _Coverage:
    """Where each source character of one prose block went: copied into a stretch, or replaced by
    a placeholder; any other character was dropped."""

    source: str
    copied: dict[int, tuple[int, int]]
    replaced: list[tuple[int, int]]

    def in_replaced(self, offset: int) -> bool:
        index = bisect.bisect_right(self.replaced, (offset, len(self.source) + 1)) - 1
        return index >= 0 and self.replaced[index][0] <= offset < self.replaced[index][1]

    def dropped_pieces(self, start: int) -> list[tuple[int, int, str]]:
        """The markup pieces of every dropped stretch of the source from `start`."""
        pieces = []
        position = start
        while position < len(self.source):
            if position in self.copied or self.in_replaced(position):
                position += 1
                continue
            gap_end = position
            while gap_end < len(self.source) and not (
                gap_end in self.copied or self.in_replaced(gap_end)
            ):
                gap_end += 1
            pieces.extend(_pieces(self.source, position, gap_end))
            position = gap_end
        return pieces


def _placeholder_range(stretch: Stretch) -> dict[int, int]:
    """Map each character index inside a placeholder to the index where that placeholder starts."""
    return {
        index: start
        for start in stretch.placeholder_starts
        for index in range(start, start + len(PLACEHOLDER))
    }


def _coverage(block: Block, block_stretches: Sequence[Stretch]) -> _Coverage:
    copied: dict[int, tuple[int, int]] = {}
    replaced = set()
    for stretch_index, stretch in enumerate(block_stretches):
        inside = _placeholder_range(stretch)
        replaced.update((stretch.starts[start], stretch.ends[start]) for start in inside.values())
        for index, (start, end) in enumerate(zip(stretch.starts, stretch.ends)):
            if index not in inside and end == start + 1:
                copied[start] = (stretch_index, index)
    return _Coverage(_block_source(block), copied, sorted(replaced))


def _character_violations(block: Block, stretch: Stretch, source: str) -> list[Violation]:
    """Each prepared character is its source character, a space for whitespace, a space set
    between a placeholder and a letter, or part of a placeholder; and the characters keep the
    source's order."""
    found = []
    inside = _placeholder_range(stretch)
    previous_end = 0
    for index, character in enumerate(stretch.text):
        start, end = stretch.starts[index], stretch.ends[index]
        if index in inside:
            kept = character == PLACEHOLDER[index - inside[index]] and start < end
        elif start == end:
            kept = character == " "
        else:
            original = source[start]
            kept = end == start + 1 and (
                character == original or (character == " " and original.isspace())
            )
        in_order = start >= previous_end or (index in inside and start == stretch.starts[index - 1])
        if not (kept and in_order):
            found.append(_violation(OFFSET, "character", "stretches", character, block, start))
        previous_end = end
    return found


def _word_violations(
    stretch: Stretch, start: int, end: int, consumer: str, source: str
) -> list[Violation]:
    """Check one word of a consumer's prepared text, stretch.text[start:end]: it is the
    placeholder (or its possessive), or its letters are adjacent in the source, with only markup
    that may sit inside a word between them."""
    word = stretch.text[start:end]
    block = stretch.block
    inside = _placeholder_range(stretch)
    placeholder_starts = sorted({inside[index] for index in range(start, end) if index in inside})
    if placeholder_starts:
        first = placeholder_starts[0]
        after = stretch.text[first + len(PLACEHOLDER) : end]
        alone = placeholder_starts == [first] and first == start
        if alone and (not after or POSSESSIVE.fullmatch(after)):
            return []
        return [
            _violation(INVENTED, "placeholder-joined", consumer, word, block, stretch.starts[start])
        ]
    for index in range(start, end - 1):
        gap_start, gap_end = stretch.ends[index], stretch.starts[index + 1]
        kinds = {kind for _, _, kind in _pieces(source, gap_start, gap_end)} - INTRAWORD_MARKUP
        if kinds:
            cause = f"joined-across-{min(kinds)}"
            return [_violation(INVENTED, cause, consumer, word, block, stretch.starts[start])]
    return []


def escapes(source: str) -> list[int]:
    """The offset of each backslash that escapes the ASCII punctuation after it, as CommonMark
    reads it outside code."""
    found = []
    position = 0
    while (backslash := source.find("\\", position)) != -1:
        if re.match(ASCII_PUNCTUATION, source[backslash + 1 : backslash + 2]):
            found.append(backslash)
            position = backslash + 2
        else:
            position = backslash + 1
    return found


def _escape_violations(block: Block, coverage: _Coverage) -> list[Violation]:
    """No escaping backslash reaches the prepared text, since a reader never sees one."""
    in_code = {offset for start, end in code_spans(coverage.source) for offset in range(start, end)}
    return [
        _violation(
            INVENTED,
            "escape-kept",
            "stretches",
            coverage.source[offset : offset + 2],
            block,
            offset,
        )
        for offset in escapes(coverage.source)
        if offset in coverage.copied and offset not in in_code
    ]


def _replaced_violations(block: Block, coverage: _Coverage) -> list[Violation]:
    """Each placeholder replaces one item of a kind in REPLACED_ON_PURPOSE, delimited as CommonMark
    or pandoc delimits it, and cuts no word in two."""
    found = []
    source = coverage.source
    commonmark = code_spans(source)
    in_code = {offset for start, end in commonmark for offset in range(start, end)}
    for start, end in coverage.replaced:
        text = source[start:end]
        kind = _replaced_kind(text)
        if kind == "code-span":
            prose_inside = [run for run in word_runs(source[:end], start) if run[0] not in in_code]
            found.extend(
                _violation(DROPPED, "code-span-overrun", "stretches", source[a:b], block, a)
                for a, b in prose_inside
            )
        elif kind == "math" and math_end(source, start) != end:
            found.append(_violation(DROPPED, "math-not-pandoc", "stretches", text, block, start))
        elif kind == "unknown" or (kind != "math" and re.search(r"\s", text)):
            found.append(_violation(DROPPED, f"replaced-{kind}", "stretches", text, block, start))
        url_after_word = kind == "url" and "url-after-word" in SPLIT_ON_PURPOSE
        if (_cuts_word(source, start) and not url_after_word) or _cuts_word(source, end):
            found.append(
                _violation(SPLIT, "placeholder-cuts-word", "stretches", text, block, start)
            )
    for start, end in commonmark:
        copied = [run for run in word_runs(source[:end], start) if run[0] in coverage.copied]
        if copied:
            word = source[start:end]
            found.append(
                _violation(INVENTED, "code-read-as-prose", "stretches", word, block, start)
            )
    return found


def _dropped_violations(block: Block, coverage: _Coverage) -> list[Violation]:
    """Every word of the block's prose reaches a stretch, or lies in a placeholder or in markup
    the preparation drops on purpose."""
    found = []
    for start, end, kind in coverage.dropped_pieces(block.marker_end):
        if kind in DROPPED_ON_PURPOSE:
            continue
        for run_start, run_end in word_runs(coverage.source[:end], start):
            word = coverage.source[run_start:run_end]
            found.append(
                _violation(DROPPED, f"dropped-{kind}", "stretches", word, block, run_start)
            )
    return found


def _kept_word_violations(block: Block, coverage: _Coverage) -> list[Violation]:
    """A word of letters that reaches the prepared text reaches it whole, in one stretch, with no
    space set inside it."""
    found = []
    for start, end in word_runs(coverage.source, block.marker_end):
        places = [coverage.copied.get(offset) for offset in range(start, end)]
        if None in places:
            continue
        stretch_index = places[0][0]
        indices = [index for _, index in places]
        whole = {index for index, _ in places} == {stretch_index} and indices == list(
            range(indices[0], indices[0] + len(indices))
        )
        if not whole:
            word = coverage.source[start:end]
            found.append(_violation(SPLIT, "stretch-splits-word", "stretches", word, block, start))
    return found


def stretch_violations(block: Block, block_stretches: Sequence[Stretch]) -> list[Violation]:
    """Check the paper's preparation of one prose block: every character traces back to the
    source, placeholders replace only what they are meant to, no prose is dropped by accident,
    and no word of letters is split."""
    source = _block_source(block)
    coverage = _coverage(block, block_stretches)
    found = [
        violation
        for stretch in block_stretches
        for violation in _character_violations(block, stretch, source)
    ]
    found.extend(_replaced_violations(block, coverage))
    found.extend(_escape_violations(block, coverage))
    found.extend(_dropped_violations(block, coverage))
    found.extend(_kept_word_violations(block, coverage))
    return found


def document_violations(markdown: str, blocks: Sequence[Block]) -> list[Violation]:
    """Check what the block model drops from a whole document: every line of prose is in a
    block, front matter is closed, and an image line holds no prose after the image."""
    original, _, kinds = masked_lines(markdown)
    found = []
    covered = {
        block.first_line + index for block in blocks for index in range(len(block.source_lines))
    }
    for number, (line, kind) in enumerate(zip(original, kinds), start=1):
        if kind and kind not in DROPPED_ON_PURPOSE:
            raise ValueError(f"line kind {kind!r} is dropped but not listed in DROPPED_ON_PURPOSE")
        if not kind and line.strip() and number not in covered and word_runs(line):
            found.append(Violation(DROPPED, "line-outside-blocks", "blocks", line, number, 1))
    if kinds and kinds[0] == "frontmatter":
        closed = any(
            kind == "frontmatter" and line.strip() == "---"
            for line, kind in list(zip(original, kinds))[1:]
        )
        if not closed:
            found.append(Violation(DROPPED, "front-matter-unclosed", "blocks", "---", 1, 1))
    for block in blocks:
        if block.kind == "image":
            rest = IMAGE_OR_LINK.sub(" ", block.source_lines[0])
            if word_runs(rest):
                found.append(
                    Violation(
                        DROPPED, "text-after-image", "blocks", rest.strip(), block.first_line, 1
                    )
                )
    return found


def _line_markup(source: str) -> list[tuple[int, int, str]]:
    """The linter's INLINE_MARKUP matches on each line of a block's source, with block offsets."""
    found = []
    line_start = 0
    for line in source.split("\n"):
        for match in lint_prose_markdown.INLINE_MARKUP.finditer(line):
            found.append((line_start + match.start(), line_start + match.end(), match.lastgroup))
        line_start += len(line) + 1
    return found


def linter_violations(block: Block) -> list[Violation]:
    """Check the text lint_prose.py reads for one prose or masked block: each character is its
    source character or a blank, a blanked word is inside markup the linter masks on purpose,
    and its word rule keeps each word of letters whole."""
    source = _block_source(block)
    text = block.text
    if len(text) != len(source):
        return [_violation(OFFSET, "length", "linter", text[:40], block, 0)]
    found = [
        _violation(OFFSET, "character", "linter", character, block, offset)
        for offset, character in enumerate(text)
        if character not in (" ", source[offset])
    ]
    markup = _line_markup(source)
    commonmark = code_spans(source)
    in_code = {offset for start, end in commonmark for offset in range(start, end)}
    for start, end in word_runs(source, block.marker_end):
        blanked = [offset for offset in range(start, end) if text[offset] == " "]
        word = source[start:end]
        if not blanked:
            kept = lint_prose_markdown.WORD.match(text, start)
            if kept is None or kept.end() < end:
                found.append(_violation(SPLIT, "word-rule", "linter", word, block, start))
            continue
        span = next(((a, b, group) for a, b, group in markup if a <= blanked[0] < b), None)
        if span is None:
            found.append(_violation(DROPPED, "dropped-unexplained", "linter", word, block, start))
            continue
        a, b, group = span
        url_after_word = group == "placeholder" and source[a] != "`" and b >= end
        if (a > start and not url_after_word) or b < end:
            found.append(_violation(SPLIT, "mask-cuts-word", "linter", word, block, start))
        if group == "placeholder" and source[a] == "`" and blanked[0] not in in_code:
            found.append(_violation(DROPPED, "code-span-overrun", "linter", word, block, start))
        elif group == "drop":
            kind = _piece_kind(source, SOURCE_PIECE.match(source, a, b))
            if kind not in DROPPED_ON_PURPOSE:
                found.append(_violation(DROPPED, f"dropped-{kind}", "linter", word, block, start))
    return found


def _token_runs_violations(
    stretch: Stretch, token_spans: Sequence[tuple[int, int]], consumer: str
) -> list[Violation]:
    """Each word of letters copied into the stretch lies inside one of the consumer's tokens."""
    owner: list[int | None] = [None] * len(stretch.text)
    for number, (start, end) in enumerate(token_spans):
        owner[start:end] = [number] * (end - start)
    inside = _placeholder_range(stretch)
    found = []
    for start, end in word_runs(stretch.text):
        owners = set(owner[start:end])
        if not inside.keys() & range(start, end) and (len(owners) != 1 or None in owners):
            word = stretch.text[start:end]
            offset = stretch.starts[start]
            found.append(_violation(SPLIT, "token-rule", consumer, word, stretch.block, offset))
    return found


def surprisal_violations(markdown: str) -> list[Violation]:
    """Check prose.plain_text and prose.tokens, which the surprisal study reads: the text is the
    prose blocks' stretches, no prose block is left out, each token is a source word or the
    placeholder, a word of letters is one token, and each token's source position is its own."""
    plain = prose.plain_text(markdown)
    original = markdown.splitlines()
    found = []
    offsets: list[int] = []
    placed: list[Stretch] = []
    paragraphs = []
    position = 0
    for block in prose_blocks(markdown):
        block_stretches = stretches(block)
        if not lint_prose_markdown.WORD.search(block.text):
            coverage = _coverage(block, block_stretches)
            kept = [run for run in word_runs(coverage.source) if run[0] in coverage.copied]
            found.extend(
                _violation(
                    DROPPED, "block-without-word", "surprisal", coverage.source[a:b], block, a
                )
                for a, b in kept
            )
            continue
        for stretch in block_stretches:
            offsets.append(position)
            placed.append(stretch)
            position += len(stretch.text) + 1
        paragraphs.append("\n".join(stretch.text for stretch in block_stretches))
        position += 1
    if plain.text != "\n\n".join(paragraphs):
        return [Violation(OFFSET, "plain-text", "surprisal", plain.text[:40], 1, 1)]
    by_stretch: dict[int, list[tuple[int, int]]] = {}
    for token in prose.tokens(plain.text):
        number = bisect.bisect_right(offsets, token.start) - 1
        stretch = placed[number]
        start, end = token.start - offsets[number], token.end - offsets[number]
        by_stretch.setdefault(number, []).append((start, end))
        source = _block_source(stretch.block)
        found.extend(_word_violations(stretch, start, end, "surprisal", source))
        line, column = stretch.block.position(stretch.starts[start])
        at_source = original[line - 1][column - 1 : column] == source[stretch.starts[start]]
        if plain.sources.get(token.start) != (line, column) or not at_source:
            found.append(
                _violation(
                    OFFSET, "source", "surprisal", token.text, stretch.block, stretch.starts[start]
                )
            )
    for number, stretch in enumerate(placed):
        found.extend(_token_runs_violations(stretch, by_stretch.get(number, []), "surprisal"))
    return found


def parse_violations(markdown: str, tokenize: Callable[[Stretch], Doc]) -> list[Violation]:
    """Check the sentences syntax_features.py parses: every prepared word reaches a sentence, each
    token is a source word or the placeholder, and each token's Span quotes its own source;
    `tokenize` splits one prepared sentence into tokens as the parse does."""
    parts = syntax_features._prepare(markdown)
    line_starts = syntax_features._line_starts(markdown)
    found = []
    in_sentences: dict[int, set[int]] = {}
    for part in parts:
        in_sentences.setdefault(part.block.first_line, set()).update(part.starts)
    for block in prose_blocks(markdown):
        coverage = _coverage(block, stretches(block))
        sentence_offsets = in_sentences.get(block.first_line, set())
        for start, end in word_runs(coverage.source, block.marker_end):
            if start in coverage.copied and start not in sentence_offsets:
                word = coverage.source[start:end]
                found.append(
                    _violation(DROPPED, "sentence-without-word", "parse", word, block, start)
                )
    for part in parts:
        doc = tokenize(part)
        reader = syntax_features._Reader(part, doc, markdown, line_starts)
        source = _block_source(part.block)
        inside = _placeholder_range(part)
        for token in doc:
            if token.is_space:
                continue
            start, end = token.idx, token.idx + len(token.text)
            found.extend(_word_violations(part, start, end, "parse", source))
            span = reader.span(token, token)
            expected = source[part.starts[start] : part.ends[end - 1]]
            position = part.block.position(part.starts[start])
            if span.text != expected or (span.line, span.column) != position:
                found.append(
                    _violation(OFFSET, "span", "parse", token.text, part.block, part.starts[start])
                )
            is_placeholder = (
                start in inside and inside[start] == start and token.text == PLACEHOLDER
            )
            if is_placeholder != reader.is_placeholder(token):
                found.append(
                    _violation(
                        OFFSET,
                        "placeholder-mark",
                        "parse",
                        token.text,
                        part.block,
                        part.starts[start],
                    )
                )
    return found


def clean_row_violations(row: str, line: int = 1) -> list[Violation]:
    """Check reference.clean_row on one WikiText row as prose.tokens reads it: its words are the
    row's own once the corpus's @ markers and clitic spaces are undone, so closing a space before
    punctuation never joins two words, and a word of letters is one token."""
    raw = row.strip("\n").strip()
    for marker, replacement in reference.MARKERS:
        raw = raw.replace(marker, replacement)
    raw = reference.CLITIC.sub("", raw)
    cleaned = reference.clean_row(row)
    if cleaned.replace(" ", "") != raw.replace(" ", ""):
        return [Violation(DROPPED, "changed-character", "reference", cleaned[:40], line, 1)]
    found = []
    if not cleaned.isascii():
        found.extend(
            Violation(SPLIT, "token-rule", "reference", cleaned[start:end], line, start + 1)
            for start, end in word_runs(cleaned)
            if (kept := prose.TOKEN_WORD.match(cleaned, start)) is None or kept.end() < end
        )
    if prose.TOKEN_WORD.findall(cleaned) != prose.TOKEN_WORD.findall(raw):
        words, expected = prose.tokens(cleaned), prose.tokens(raw)
        word = next(
            (word for word, other in zip(words, expected) if word.text != other.text), words[-1]
        )
        found.append(
            Violation(INVENTED, "joined-across-space", "reference", word.text, line, word.start + 1)
        )
    return found


def all_violations(markdown: str, tokenize: Callable[[Stretch], Doc]) -> list[Violation]:
    """Every check on one markdown document, for every consumer."""
    original, visible, kinds = masked_lines(markdown)
    blocks = parse_blocks(original, visible, kinds)
    found = document_violations(markdown, blocks)
    for block in blocks:
        if block.kind in PROSE_KINDS:
            found.extend(stretch_violations(block, stretches(block)))
        if block.kind in (*PROSE_KINDS, "masked"):
            found.extend(linter_violations(block))
    found.extend(parse_violations(markdown, tokenize))
    found.extend(surprisal_violations(markdown))
    return found
