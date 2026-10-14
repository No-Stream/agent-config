---
name: paper-drafting
description: Use when turning finished or nearly finished research into a written output - an ML paper, arXiv preprint, conference submission, tech report, LessWrong or blog post, or research writeup - including drafting, outlining, restructuring, or reviewing such a draft.
---

# Paper Drafting

## Overview

A research writeup is a **narrative**: one to three specific claims that fit one theme, rigorous evidence for each,
and a reason the reader should care. Everything in the main text exists to support that narrative. Every other
finding goes to an appendix, a follow-up post, or nowhere.

The default failure is shoveling: listing every finding in the order it was found, with equal weight. The reader then
remembers nothing. Readers take away a few sentences at most, so choose those sentences on purpose. If you do not
choose what to drop, something important gets dropped by accident.

Adapted from Neel Nanda, "Highly Opinionated Advice on How to Write ML Papers" and his paper-writing checklist
(both 2025, Alignment Forum).

## Venue

Decide the venue first and state it. It changes the standard of defense, not the core narrative.

| | Paper (conference, arXiv, tech report) | Post (LessWrong, blog, internal writeup) |
|---|---|---|
| Opening | Abstract | TL;DR of 3-6 bullets |
| Objections | Pre-empt every serious reviewer objection | Answer real, meaningful objections; ignore nits; anticipate likely misreadings |
| Speculation | Out of the main text | Welcome, in a section labelled as speculation, with stated confidence |
| Related work | Short section, near the end | Inline links where they matter; a section only if the post corrects or extends prior work |
| Tacit knowledge | Appendix | Main text if it is interesting |

A post says what we did, what we found, and why it is interesting. It is not a maximally defended artifact.

## Where drafts live

Drafts, the claims ledger and outlines are internal notes. Put them where the repo's instructions say internal notes
go (check CLAUDE.md or AGENTS.md; often a gitignored scratch directory). If the repo has privacy or benchmark-integrity
rules, they apply to the draft too: no benchmark item text, no personal or machine-local information in anything that
will be published.

## Workflow

**This is co-drafting with the owner, not a one-shot output.** A full draft built on an unapproved narrative is
usually wrong and wastes the owner's review time. Each stage produces a working file (a deliverable of this skill, not
a summary report) and ends at a **CHECKPOINT**: hand the file back with the open questions and stop. Do not start the
next stage until the owner responds. Feedback on bullets is far cheaper than feedback on prose.

Skip a checkpoint only when the owner explicitly says to for that stage. Even then, write the narrative file and
outline first, mark unsettled choices inline as `[OWNER: question]`, and point to the narrative file and cut list
first when handing back.

Markers: `[OWNER: ...]` for a decision or a number only the owner can supply; `[UNSOURCED]` for a number in the draft
that has no source anywhere. Both are allowed in a draft handed back for review; neither survives to release.

1. **Audit the evidence.** Before writing anything, check that the key results are real. Follow
   `evidence-redteam.md`. Report problems found; do not bury them under the narrative. The audit goes in the narrative
   file and is reviewed at its checkpoint.
2. **Write the narrative file** with exactly these parts, in order:
   - **Narrative**: 3-5 sentences a stranger could repeat back: the context, the problem, what we showed, why it matters.
   - **Claims ledger**: one row per claim (see below).
   - **Cut list**: every finding in the source material that is not a claim, each with a destination: *supporting*
     (main text, as evidence, a control or setup for a named claim), *appendix*, *limitations*, *speculation* (posts
     only), *follow-up*, or *drop*, and a one-line reason. A finding marked *supporting* gets a sentence or a table
     row, not its own subsection; several supporting checks can share one "checks" table. Subsections belong to
     claims and their direct evidence.
   - **Alternative narratives**: if the right story is not obvious, 2-3 candidate narratives with their trade-offs and
     a recommendation.
   - **CHECKPOINT**: owner signs off on narrative and claims.
3. **Write the outline**: section headings; for each figure or table, the one takeaway it shows; for each paragraph of
   the main text, its first and last sentence, plus the numbers it uses. Every section must answer "what goes wrong if
   I cut this?" If nothing does, cut it. **CHECKPOINT**: owner signs off, and says whether to continue to prose or
   take the outline from here.
4. **Draft in this order, a few sections per round**: methods and results; then limitations and appendices; then
   figures, tables and captions; then the introduction and the abstract or TL;DR. Each round ends at a
   **CHECKPOINT**. The owner often rewrites sections in their own words; build on their version, never overwrite it.
   An early skeleton abstract is fine, but expect to replace it. Section guidance is in `anatomy.md`.
5. **Review** (see Review below), report the findings, revise what the owner agrees with, then run the final checks.

Ruthlessness applies to length too, not only to section count. At each drafting checkpoint, report the main-text
length (excluding appendices). Upper bounds: a paper's main text is at most 10 pages, or the venue limit if lower; a
post is shorter, at most about 4,000 words. If it is longer, move material to appendices before trimming words.

If the data for a planned figure is not available, write the figure plan (takeaway, axes, what is highlighted) and an
`[OWNER: ...]` marker for the data.

Effort goes where readers are: abstract/TL;DR, introduction, figures and tables > results > methods > everything else.
Most readers see only the title and abstract; many see the figures; few read the methods.

## The claims ledger

| Field | Content |
|---|---|
| Claim | One sentence, as specific as the evidence allows |
| Strength | existence proof / systematic / narrow (conditions) / hedged (suggestive, tentative) / guarantee |
| Evidence | Each supporting result, with a pointer to the file, run or table it comes from |
| Verification | *verified* (re-derived from raw artifacts), *notes only* (taken from notes or summaries), or *mismatch* |
| Pre- or post-hoc | Was the result predicted before it was seen? |
| Baselines and controls | What it was compared against, and how hard the baseline was tuned |
| Known weaknesses | Sample size, seeds, alternative explanations, untested conditions |

The wording in the draft must match the ledger's strength. One seed and n=100 is "suggestive" or an existence proof,
never "X causes Y". **Every number in the draft must trace to a ledger evidence pointer.** A derived number (a
difference, a standard error, a share) needs its derivation written in the narrative file. If a number cannot be
traced, mark it `[UNSOURCED]` and ask; never write a plausible-looking value.

When the owner's preferred takeaway has the weakest evidence, say so in the narrative file and offer the options:
keep it as a clearly labelled preliminary result, move it to speculation, or hold it for a follow-up.

Strong claims make interesting writeups but need more evidence. One well-supported claim is enough for a good paper.
Several claims must share a theme; a grab-bag of findings is hard to understand and harder to remember. The limit of
three applies to posts too. A result that strengthens a claim (a steering intervention, a length control) is evidence
under that claim, not a fourth claim.

## Sections

- **No discussion or conclusion section by default.** A real conclusion belongs in the abstract or introduction;
  what remains is usually grand statements. Write a **Limitations** section instead, which is required.
- Posts may add a **Speculation** section ("what I think is going on") with confidence stated per item.
- Ruthless appendices: anything not needed for the narrative goes there. Appendices are cheap and lightly read, so do
  not polish them.
- An optional **tacit knowledge** appendix (in a post, a main section): what was hard, what broke, what we
  misunderstood for weeks, advice for replicators.

## Review

Run both, each in a fresh subagent with no access to this conversation:

1. **Cold reader.** Give only the draft. Ask it to state the main contribution, why it matters, and why the evidence
   is convincing. If its answer differs from the narrative file, the draft is unclear. Fix the draft, not the reader.
2. **Adversarial reviewer.** Frame the draft as "a colleague's paper" (never "mine" or "ours", which invites
   sycophancy) and ask "What is the biggest problem with this?" For a paper, also include two or three strong papers
   from the field as context. For a post, tell it to ignore nits and report only objections that would change a
   careful reader's belief.

Then check each claim's wording against the ledger, and that every number has a source.

## Writing style

Inform, do not persuade. Precise and plain: jargon only where it adds precision, and define every term the reader
might not know. You have months of context and the reader has none. If the owner has prose-style instructions,
follow them.

## Final checks

These apply at release, not to a draft handed back for review.

- No `TODO`, `??`, `[UNSOURCED]`, `[OWNER: ...]`, or broken references.
- Every figure and table is referenced in the text.
- Limitations section present; no conclusion section unless the owner asked for one.
- Privacy and anonymity (for blind review: no names, usernames, identifying links).
- For papers: page count against the venue limit; venue-specific checklists. See `release.md`.

## Common mistakes

| Mistake | Fix |
|---|---|
| Every finding in the main text, in discovery order | Cut list; results ordered by claim, not by chronology |
| A rabbit hole gets a full section because it took weeks | Effort is not evidence. Appendix or tacit-knowledge note |
| One-seed or small-n result stated as a general fact | Match the wording to the ledger strength |
| Weak or untuned baseline presented as the comparison | Say it was untuned, or tune it before claiming |
| Strong result in the main text, contradicting result omitted | Contradicting results go in Limitations, or the claim narrows |
| A known-bug era number quoted alongside fixed numbers | Only post-fix numbers; mention the bug in an appendix if it matters |
| Conclusion section restating the intro | Delete it; move any new insight to the intro |
| Speculation mixed into results in a post | Separate labelled section |
| Prose before the narrative and outline are signed off | Go back to the narrative file |
