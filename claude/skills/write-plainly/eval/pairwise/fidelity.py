"""Reading the fidelity checker's output, and counting the sentences a revision changed."""

from __future__ import annotations

import difflib
import re

CHECKER_LINE = re.compile(r"^- (UN)?SUPPORTED: ")
NO_CHANGES = "No changes in meaning."
PASSAGE_HEADING = re.compile(r"^##\s*Passage\s+([A-Z])\s*$", re.MULTILINE)
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def changed_sentence_count(earlier: str, revision: str) -> int:
    earlier_sentences = SENTENCE_END.split(" ".join(earlier.split()))
    revision_sentences = SENTENCE_END.split(" ".join(revision.split()))
    matcher = difflib.SequenceMatcher(a=earlier_sentences, b=revision_sentences, autojunk=False)
    return sum(
        max(earlier_end - earlier_start, revision_end - revision_start)
        for tag, earlier_start, earlier_end, revision_start, revision_end in matcher.get_opcodes()
        if tag != "equal"
    )


def unsupported_count(checker_output: str) -> int:
    """Count the fidelity checker's UNSUPPORTED lines; any line outside its output form raises."""
    lines = [line.rstrip() for line in checker_output.splitlines() if line.strip()]
    malformed = [line for line in lines if line != NO_CHANGES and not CHECKER_LINE.match(line)]
    if malformed:
        raise RuntimeError(f"fidelity checker lines outside its output form: {malformed}")
    return sum(line.startswith("- UNSUPPORTED: ") for line in lines)


def unsupported_by_passage(checker_output: str, labels: dict[str, str]) -> dict[str, int]:
    """Per-pipeline UNSUPPORTED counts from a measurement with one `## Passage X` section each."""
    preamble, *sections = PASSAGE_HEADING.split(checker_output)
    headings, bodies = sections[0::2], sections[1::2]
    if preamble.strip() or sorted(headings) != sorted(labels):
        raise RuntimeError(
            f"fidelity output has passages {headings} after {preamble.strip()[:200]!r}, "
            f"expected one each of {sorted(labels)} and nothing before them"
        )
    return {labels[label]: unsupported_count(body) for label, body in zip(headings, bodies)}
