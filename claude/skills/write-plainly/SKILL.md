---
name: write-plainly
description: Use when writing or revising nonfiction prose that people other than the user will read, such as a README, a Google Doc, a report, memo, design doc, recommendation, research write-up, PR description, documentation, or anything published online, including substantive edits to an existing draft. Also use when the user asks to make writing plainer or clearer, or to remove AI writing tells, sales language, excess metaphor or mannered phrasing. Not for chat replies to the user, agent instruction files, internal scratch notes, or intentionally literary writing.
---

# Write plainly

Write for understanding on the first reading. Preserve accuracy and meaning first, then aim for clarity, useful precision, and economy. Aim more than halfway from conversational prose toward the register of a technical standard: literal wording, stable terms, explicit conditions, and claims the reader can check. Keep a competent colleague's voice; first person, contractions, and direct judgments are fine. Give no weight to sounding polished, impressive, or human.

This skill is for documents that other people will read: a README, a Google Doc, a post, a report, anything that ends up online. Repo notes and files written for agents do not need it unless the user asks. For papers and research write-ups, use it together with `paper-drafting`, which decides the narrative and claims; this skill governs the prose. For figures, use `visualization`.

## Preserve meaning

Keep quantities, units, names, dates, attribution, comparisons, causal direction, negative findings, and the line between observation and inference. Treat modality as content: "fails," "might fail," "must," "should," "may," and "will" make different claims, so do not change them to sound firmer. Keep quotations, identifiers, commands, code, and link targets unchanged.

Add specificity only from information you have. Never invent a number, mechanism, quotation, source, or example presented as fact to improve a sentence. If an essential detail is missing, flag it; otherwise keep the accurate general statement. Label hypothetical examples and estimates as such.

## Organize for the reader

Give the answer, finding, or recommendation first, with the conditions needed to understand it. Then order the support as the reader needs it: setup before a mechanism, evidence before a disputed inference, prerequisites before an action. Do not narrate the order in which you found things. A standalone document must make sense to someone who saw neither the work nor the conversation behind it.

Develop one idea per paragraph, usually in four to six sentences, sometimes up to eight. Avoid runs of short paragraphs, fragments, and tiny sections; combine related sentences and state how they connect. Explain what happens (inputs, operations, outputs) so the reader can work through a small case, and carry one concrete example through the explanation instead of introducing a new one for each point. Define unfamiliar terms at first use.

Include a detail only if it changes the claim, its scope, the confidence it deserves, or the decision, but keep the reasoning the reader needs to check the conclusion. For comparisons, name the criteria, reach a judgment, and say what would change it; do not give weak options equal space to look balanced. Stop when the task is answered, without a recap.

## Keep caveats and detail in proportion

Readers do not want a document that is half disclaimers. Put a caveat in the main text only when the claim is wrong or misleading without it, and then put it next to that claim, once. Other limitations go in a short limitations section or a footnote. Exhaustive detail (every configuration, every run, every edge case) goes in a separate appendix or reference document that few people will read and agents can consult; link it from the main text. When a reviewer or your own instinct asks for another qualification, first check whether the claim is already stated at the right strength.

## Name things by what they are

Never use labels coined during the work: plan step numbers ("step 4"), option letters ("option B"), round numbers ("round 3"), or nicknames ("the pool"). The reader did not see the work. Say what the thing is, such as "the rerun with the patched grader" instead of "run B," and give variants and stages descriptive names ("median" and "stack," not "A" and "B"). Use one term per concept throughout, without switching synonyms for variety. Terms of art are fine; define them if the audience may not know them.

## Sentences

Give each sentence a real actor as its subject and a verb that states what the actor does. Write in active voice; "we" is fine. Use passive voice only when the actor is genuinely unknown or irrelevant, and never invent an actor. Keep related words close, put a condition before the claim it limits, turn action nouns back into verbs, and unpack noun stacks.

Check that the subject can do what the verb says. Tests, results, and documents do not want, refuse, hold, or struggle: "tests show a memory leak" is literal, and "the result refuses a simple story" is not. Name the observation, mechanism, or person instead. When writing about AI models, describe their behavior and do not attribute intention or experience without evidence. Prefer literal wording to metaphor, but keep established technical terms such as "cache" or "bottleneck." Use an analogy only when it explains faster than the literal account, then return to the mechanism. Do not use a stronger causal verb than the evidence supports.

## Evidence and numbers

State what was measured, changed, or compared, and under what conditions. Separate findings from your interpretation and from your recommendation, and state a material assumption once. Mark which sentences are measurements and which are inferences or opinions, so speculation does not read with the same confidence as data. An inconclusive result is not evidence of equivalence. Cite the source for each claim, prefer primary sources, and do not claim to have checked sources you did not read. Attribute a claim to a named person, document, or dataset, not to "experts" or "studies."

Use numbers selectively. Put patterns in a figure and exact lookup values in a table; in prose, give the interpretation and the few numbers needed to check it. Express each result once: the effect size ("median runtime fell by 20%"), or the endpoints when the absolute values matter ("from 25 s to 20 s"), not both plus a ratio. Give each important number its baseline, denominator, units, and period. Distinguish percent from percentage points, and match precision to the measurement.

Write procedures as numbered imperative steps in execution order, with each prerequisite before the step it affects. Do not invent thresholds or acceptance criteria.

## Remove mannerisms

Rewrite the underlying claim instead of swapping words, and do not replace a habit with slang, fake anecdotes, or choppy fragments.

- Never use em dashes. Use a comma, parentheses, a colon, a semicolon, or a new sentence, whichever fits the relationship. An en dash or spaced hyphen in the same role is also out; en dashes in numeric ranges are fine.
- Drop "not X, but Y" and "not merely X" when the rejected alternative adds nothing. Keep a contrast that rules out a plausible cause or states a limitation, and keep negatives that state actual behavior ("the service does not retry").
- Open with the information, not with why the topic matters or what the document covers. Replace claims of importance or quality with the actual result; if nothing is left, delete the sentence.
- A paragraph's first sentence should make its first claim. A bold run-in label ("**How accurate the clock is.**") or a sentence that only announces the topic ("The clock has three sources of error.") adds nothing; state the claim, which tells the reader the topic.
- Do not rate your own writing or ideas ("the cleanest framing," "to put it plainly," "an honest comparison," "this clear breakdown"), announce a takeaway before giving it ("The lesson:"), or tease an insight ("Here's the thing").
- End a sentence on the fact that carries it, not on a verdict or an "-ing" clause that interprets it ("…, highlighting the need for…"). End a paragraph on its last new fact or consequence, not on a restatement, a moral, or a hope.
- Cut announcing phrases ("it is worth noting," "importantly," "the real issue," "at its core"), promotional words ("unlock," "seamless," "game-changing," "transformative"), LLM vocabulary ("delve," "tapestry," figurative "landscape"), forced groups of three, stacked hedges, "simply" or "obviously" before a hard step, rhetorical questions you answer yourself, and closing punchlines.

## Format

Use paragraphs for reasoning, lists for separate items, numbered lists for sequences, and tables for lookup. Do not turn an explanation into labeled bullets. Use headings only when they help readers find substantial material, in sentence case with a shallow hierarchy. Bold only a decision or a label the reader must find; no bold lead-ins on every bullet, emojis, or decorative dividers.

Size sections the way human-written documents do. A top-level section (h2) carries real body: usually two or three paragraphs, sometimes more, often with a table or figure. A section with one paragraph, or an h2 holding only a few bullets, reads oddly; merge it into a neighbor, or make it a minor heading (h4) inside a larger section. When a section runs past about four paragraphs, break it up with a minor heading or a figure rather than adding another h2. In a short document (under about a thousand words), two or three h2s are usually enough.

## Edit by removing

Human editors mostly delete, replace, and restructure; model editors mostly add. Prefer the first three. Before adding a sentence, check whether an existing one can carry the point.

Sort weak sentences into two kinds. A fixable sentence has a real claim under bad prose: rewrite it to state that claim. A hollow sentence has no claim to recover (it restates, announces, or praises): delete it. If a hollow sentence sits where the document needs content, flag the gap for the author instead of filling it with invented detail.

For a local edit, make the smallest change that fixes the problem. For a rewrite, restructure as needed while preserving meaning. Return only the writing, without an editing audit, unless asked; if asked for a review, name the consequential problems and give targeted fixes.

## Check before returning

1. Run `~/.claude/skills/write-plainly/check-prose.sh FILE` on the draft (write it to a scratch file first if it is not a file yet). It runs three linters: sloplint (rhetorical AI tells, high precision), slop-guard with a tuned config (word lists, structure, rhythm), and `lint_prose.py` (this skill's own rules: dashes, coined labels, bold run-ins, thin sections, short-paragraph runs, Title Case headings).
2. Triage the findings; do not optimize the score. Fix every em dash, coined label, and high-confidence sloplint note unless it sits in a quotation or names something literally. Treat a single slop-guard word hit ("robust," "crucial") as a prompt to check that the word is literal and earned, since careful human writers use these words too. Skip findings in quoted material, code, and tables.
3. Compare against the source for numbers, negation, modality, scope, and attribution. Read the result as someone who did not write it, and remove any sentence that adds no information.
4. For a standalone document others will read, also run the review below.

## Review by a fresh reader

Dispatch the `prose-reviewer` subagent (Opus) with the document path, the intended reader, and the source material if there is any. Do not pass it the linter output; it should read the document cold. It returns at most six findings, each a quoted span, the problem it causes the reader, and a fix of "delete," "replace with …," or "requires author input." Zero findings is a valid result. Apply the findings you agree with, using deletion and replacement where they suffice.

If the edits changed more than a few sentences, dispatch the `prose-fidelity-checker` subagent (Sonnet) with the earlier version (or the source notes) and the revision. It lists every change to a fact, number, quantifier, negation, modality, condition, causal claim, attribution, or identifier, and marks each as supported or unsupported by the source. Revert or fix the unsupported ones.

Run this review once. Do not loop critique and rewrite until a reviewer approves: repeated passes accumulate drift and strip useful detail.

## Calibration examples

These show the register and the kind of repair. They are not facts to reuse. Make a repair only when the source supports the revised statement, and leave missing information missing.

| Original | Revision |
| --- | --- |
| The test holds the answer: the failure occurs during parsing. | The test shows that the failure occurs during parsing. |
| The change does more than reduce allocations: it also removes the shared lock. | The change reduces allocations and removes the shared lock. |
| The data refuses to settle the question of whether the effect persists. | The data does not establish whether the effect persists. |
| An evaluation of the revised model was performed by the team. | The team evaluated the revised model. |
| The post-deployment failure-rate monitoring configuration is missing. | The configuration for monitoring failure rates after deployment is missing. |
| The new cache dramatically improves performance, reducing median response time from 100 ms to 50 ms. | The new cache reduces median response time from 100 ms to 50 ms. |
| The request could potentially have failed because of a timeout. | The request might have failed because of a timeout. |
| It is worth noting that this study only included experienced developers. | The study included only experienced developers. |
| The pass rate rose after the round-3 fix — a big win. | The pass rate rose after the grader fix that rejects symlinked paths. (If the source does not say what the fix was, flag the label instead of guessing.) |
| Latency fell by 30%, underscoring the value of the new design. | Latency fell by 30%. |
| Overall, these results paint a promising picture for the future of the approach. | Delete. The sentence has no claim to recover. |
| The model was trained on 2M examples. Note that results may vary on other datasets, and further work is needed. | The model was trained on 2M examples. (Move the generic caveat to the limitations section, or cut it if that section already says which datasets were tested.) |
| The service does not retry failed payments. | Keep this sentence. The negative states actual behavior. |
| We did not test on non-English text, so these numbers may not hold there. | Keep this sentence. The caveat changes how far the claim reaches. |

A developed technical explanation in the target register:

> A random train-test split can overestimate performance on new customers when examples from the same customer appear in both sets. The model may then use customer-specific information that will be unavailable for a new customer. To test performance on new customers, assign each customer's examples to a single split. This makes the evaluation match the intended use more closely. It still does not measure the effect of changes over time, which requires a separate evaluation.

The sources behind these instructions are listed in `sources.md`. Applying the skill does not require reading them.
