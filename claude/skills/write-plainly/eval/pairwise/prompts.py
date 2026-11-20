"""Prompt templates for the pipeline runner's author turns, reviewers and fidelity checks."""

from __future__ import annotations

from common import read_list

DRAFT_PROMPT = """\
You are drafting one passage for a blind writing evaluation. Write it as the writing guidance in \
the files below says to, as if a colleague had handed you these notes and asked for this passage.

Read these files completely before writing, and follow them:
{read_list}

{instructions}

Document type: {doc_type}
Intended reader: {reader}
Target length: about {target_words} words; stay between {min_words} and {max_words}.

Source notes (the only facts you may use):
{notes}

How this run works:
- Nobody is available to answer questions. Skip any step of the guidance that needs the person \
who asked (gap questions, outline agreement, choosing a template) and write from the notes.
- Use only facts from the notes. Do not invent numbers, names or results.
- The passage is body text only: no title or heading, no preamble, no sign-off.
- Later turns in this conversation run the review steps one at a time. Do only what this turn asks.
{context}
Return the passage in the `passage` field."""

AUTHOR_PROMPT = """\
Next step: {stage_name}.

{instructions}
{blocks}
Current passage:
{passage}
{context}
Return the full passage after this step in the `passage` field, unchanged if this step changes \
nothing."""

GATE_FIDELITY_PROMPT = """\
The earlier version is the file {earlier_file}. The revision is the file {revision_file}.

Source notes both were written from:
{notes}
{context}"""

MEASURE_FIDELITY_PROMPT = """\
The earlier version is the source notes below. There are {count} revisions, the files {files}, \
each written independently from these notes by a different writer. Check each revision against \
the notes on its own, following your instructions. Each revision selects from the notes, so a fact \
it leaves out is not a change; list only statements that change, add to or misstate what the notes \
say, and caveats or conditions the notes attach to a claim the revision states without them.

Before each revision's lines, write a heading line `## Passage <letter>`. Under it, give that \
revision's lines in your output form, or `No changes in meaning.`

Source notes:
{notes}
{context}"""


def quoted(text: str) -> str:
    return f"<<<\n{text.strip()}\n>>>"


def read_first(paths: tuple[str, ...]) -> str:
    return "Read these files completely first:\n" + read_list(paths)


def inputs_block(names: tuple[str, ...], outputs: dict[str, str]) -> str:
    """The outputs of the named agent stages, for an author turn."""
    return "".join(f"\nOutput of {name}:\n{quoted(outputs[name])}\n" for name in names)


def lint_block(lint_runs: list[dict]) -> str:
    return "".join(
        f"\nOutput of the linter {run['lint']} on the current passage "
        f"(exit code {run['exit_code']}):\n{quoted(run['stdout'] + run['stderr'])}\n"
        for run in lint_runs
    )
