---
name: write-plainly
description: Use when writing, co-drafting or revising nonfiction prose that people other than the user will read, such as a README, a Google Doc, a report, memo, design doc, proposal, recommendation, research write-up, PR description, documentation, or anything published online, including substantive edits to an existing draft. Also use when the user asks to make writing plainer or clearer, or to remove AI writing tells, sales language, excess metaphor or mannered phrasing. Not for chat replies to the user, agent instruction files, internal scratch notes, or intentionally literary writing.
---

# Write plainly

Write so the reader understands on the first reading, with the least effort. Preserve accuracy and meaning first; then aim for clarity, information density, intuitive explanation, and rigor without verbosity. A document should take longer to write than to read, and every sentence in it should be about this particular work. The register is casual, straightforward and a bit breezy, and also direct and literal: plain words, with no metaphor, flash, or sales and search-engine language. From technical standards take only their precision: stable terms, modality treated as content, explicit conditions, and claims the reader can check. First person, contractions, and direct judgments are fine.

Sounding human gets little weight, and sounding polished or impressive gets none. The obvious model tics still matter, because a reader who spots an em dash or a reflexive "not X, but Y" stops reading carefully.

Before drafting a substantial document with the user, follow "Co-drafting a substantial document" below. For papers and research write-ups, `paper-drafting` decides the narrative, the claims and the drafting order, and this skill governs the prose. For figures, use `visualization`.

## Preserve meaning

Keep quantities, units, names, dates, attribution, comparisons, causal direction, negative findings, and the line between observation and inference. Treat modality as content: "fails," "might fail," "must," "should," "may," and "will" make different claims, so do not change them to sound firmer. Keep quotations, identifiers, commands, code, and link targets unchanged.

Add specificity only from information you have. Never invent a number, mechanism, quotation, source, or example presented as fact to improve a sentence. If an essential detail is missing, flag it; otherwise keep the accurate general statement. Label hypothetical examples and estimates as such.

## Organize for the reader

Give the answer first. A readout or report leads with the finding and the conditions needed to understand it; a proposal leads with a problem the reader already has, stated as a fact, and states the ask in the first paragraph. Then order the support as the reader needs it: setup before a mechanism, evidence before a disputed inference, prerequisites before an action. Do not narrate the order in which you found things; what was tried and failed goes to an appendix unless the failure is the finding. A standalone document must make sense to someone who saw neither the work nor the conversation behind it, so write for the reader with the least context.

Develop one idea per paragraph. Explain what happens (inputs, operations, outputs) so the reader can work through a small case, define a quantity by the arithmetic that produces it, and carry one concrete example through the explanation instead of introducing a new one for each point.

Include a detail only if it changes the claim, its scope, the confidence it deserves, or the decision, but keep the reasoning the reader needs to check the conclusion. For comparisons, name the criteria, reach a judgment, and say what would change it; do not give weak options equal space to look balanced. Stop when the task is answered, without a recap.

## Sequence the argument

A document reads top to bottom, so later sections build on earlier ones instead of standing alone. Give each fact one home section and refer to it from elsewhere; the TL;DR or summary is the one place that repeats. After drafting a paragraph, name the question a cold reader now has. The next paragraph answers it, and a paragraph that answers no open question is misplaced or cuttable. Apply the same test to the outline and again in the coherence pass: each section answers the question the one before it raised.

Transitions assert inference. "So," "but," and "because" claim a relation between two paragraphs, so use them only when the relation holds. If only "also" or "additionally" fits, the paragraphs sit in an arbitrary order: reorder them until a real connective fits, or accept that the material is a list and format it as one.

When the document's job is to correct a belief, state that belief once, in terms its holders would accept, and only if this reader actually holds it; a belief nobody holds is a straw man. Answer the two or three objections this reader will actually raise, where they arise, in a clause joined to the answer: "the speedup could come from a warmer cache, but the cold-start runs show the same gain."

## Route caveats and detail

Readers do not want a document that is half disclaimers. A caveat sits beside a claim only when the claim is wrong without it, and then once. An important nit goes in a footnote, and a real, substantive limitation goes in a limitations section. Everything else, including exhaustive detail such as all the configurations, runs, and edge cases, goes in a separate appendix document that readers and agents can consult; that is the usual home, and the main text links to it.

Hedge where the uncertainty lives. Forecasts, estimates, and secondhand facts carry a hedge; measured results are stated plainly, and a headline claim carries at most one marker such as "we expect." Keep honest uncertainty ("probably," "I think"), and cut vagueness that dodges a specific claim ("various enhancements"). When a reviewer or your own instinct asks for another qualification, first check whether the claim is already stated at the right strength; reviewers tend to ask for more caveats than these rules allow.

## Readable beats short

Minimize the reader's time to understand, not the word count. A reader who rereads a sentence, or comes back with a question, has already spent more time than the shorter draft saved. Cutting fixes padded, promotional prose, but overdone, it produces a second machine register of fragments, arrow chains, and noun phrases stacked four deep.

Cut content, not prose: shorten a draft by dropping details that would not change what the reader does next, and write everything that survives in full sentences. These compression devices are out:

- Fragments, dropped subjects, and dropped articles. "Tests green, deploy pending" becomes "The tests pass, and the deploy is waiting for approval."
- Abbreviations the reader has to expand, such as "RPS" for a reader who says "requests per second." Define a standard acronym the audience may not know once in parentheses, as in "time to first byte (TTFB)," then use it.
- Arrow chains in place of a sentence. "cache miss -> DB read -> timeout" becomes "On a cache miss the request goes to the database, and the read times out." Arrows are fine in diagrams, shell pipelines, and code.
- Hyphenated compounds stacked into a noun phrase that should be a clause. "The per-tenant rate-limit config change" becomes "the change that gives each tenant its own rate limit."
- Labels coined during the work: plan step numbers ("step 4"), option letters ("option B"), round numbers ("round 3"), or nicknames ("the pool"). The reader did not see the work, so say what the thing is ("the rerun with the patched grader," not "run B"), and give variants and stages descriptive names ("median" and "stack," not "A" and "B").

Give each identifier its own clause that says in plain words what it is: "We raised `max_retries`, the number of times the client resends a failed request, from 3 to 5," not "`max_retries` 3->5 fix." Translate vocabulary from your source material (a team's nicknames, a dataset's column codes) or define it in place; terms of art are fine, defined if the audience may not know them. Refer to things by name: no "as in the second case," "the former," or "the change mentioned earlier" reaching back several paragraphs, because repeating a noun phrase costs the reader less than a lookup. Use one term per concept throughout, without switching synonyms for variety.

## Sentences

Give each sentence a real actor as its subject and a verb that states what the actor does. Write in active voice; "we" is fine and often the clearest subject. Use passive voice only when the actor is genuinely unknown or irrelevant, and never invent an actor. Keep the subject next to its verb, put a condition before the claim it limits, and open with what the reader already has so the sentence ends on the new information. Turn action nouns back into verbs ("we migrated the tables," not "the migration of the tables") and unpack noun stacks. Write the plain clause instead of a cleft that fronts an abstraction: "What limits throughput is the index lock" becomes "The index lock limits throughput."

Keep most sentences short enough to follow in one pass, and split one that runs past about 40 words unless it is a plain list. Lean toward short, simple sentences, and let the shorter plain version win a tie. Split two clauses joined by a semicolon or colon unless the join itself carries meaning. Vary length by regrouping content (join parallel items into one sentence, give a separate point its own), never by adding a sentence for rhythm. Prefer the everyday word to a formal synonym ("use," not "utilize") unless the formal word is the term of art. Contractions are normal and never required. Read a doubtful sentence aloud; if you would not say it to a colleague, rewrite it.

Check that the subject can do what the verb says. A test, a log, or a dataset can show, find, measure, need, or fail; it cannot want, tell, believe, refuse, or struggle. "The logs show two retries" is literal, while "the logs tell us" and "the result refuses a simple story" are not. When a person acted, make the person the subject: "we sent half the requests to the new server," not "the new server took half the requests." When writing about AI models, describe their behavior and do not attribute intention or experience without evidence. Do not use a stronger causal verb than the evidence supports.

Write literally. In documents, use no metaphor; an everyday idiom may stay when it is the plainest wording, and established technical terms such as "cache" or "bottleneck" are literal. Use an analogy only when it explains faster than the literal account, then return to the mechanism.

Say what each part does. Use a negative only when the reader would otherwise assume the opposite: "the service does not retry failed payments." Do not define something by what it is not; "the scheduler never decides the order" becomes a statement of what does decide it ("each job's priority field sets the order").

## Evidence and numbers

State what was measured, changed, or compared, and under what conditions. Separate measurements from your interpretation and your recommendation, and mark which sentences are which, so speculation does not read with the confidence of data. State a material assumption once. An inconclusive result is not evidence of equivalence. Cite the source for each claim, prefer primary sources, and do not claim to have checked sources you did not read. Attribute a claim to a named person, document, or dataset, not to "experts" or "studies."

Numbers mostly live in tables and figures, and the prose says what they show, because every number in a sentence is one more thing the reader holds in memory. Body prose carries at most about 2 numbers per 100 words, and no paragraph carries more than two. The rest go in a table or figure. The sentence beside it says which way the result went, roughly how large it is in plain words ("several times faster," "a slight drop"), and whether it is distinguishable from noise, then points to the table. A comparison across several groups is a table, never a sentence per group. The TL;DR or summary, tables, captions, footnotes, and the appendix are exempt, though a summary still carries only the headline numbers. Write numbers as digits. A small count in words ("two options") is fine, but a spelled-out number from ten up, or a multiple like "three times," counts like any other.

For each number you keep, express the result once: the effect size ("median runtime fell by 20%"), or the endpoints when the absolute values matter ("from 25 s to 20 s"), not both plus a ratio. Give each important number its baseline, denominator, units, and period. Distinguish percent from percentage points, and match precision to the measurement.

Write procedures as numbered imperative steps in execution order, with each prerequisite before the step it affects. Do not invent thresholds or acceptance criteria.

## Remove mannerisms

Rewrite the underlying claim instead of swapping words, and do not replace a habit with slang, fake anecdotes, or choppy fragments.

- Never use em dashes. Use a comma, parentheses, a colon, a semicolon, or a new sentence, whichever fits the relationship. An en dash or spaced hyphen in the same role is also out; en dashes in numeric ranges are fine.
- Drop "not X, but Y," "not just X, but Y," and contrastive "X rather than Y" unless the reader actually holds X or X is a plausible cause the evidence rules out. Keep a contrast that states a limitation.
- Open with the information. Do not open with why the topic matters or with what the document covers ("in this document," "as described below"). Replace claims of importance or quality with the actual result; if nothing is left, delete the sentence. Enthusiasm is fine when the specific result carries it.
- A paragraph's first sentence should make its first claim. A bold run-in label ("**How accurate the clock is.**") or a sentence that only announces the topic ("The clock has three sources of error.") adds nothing; state the claim, which tells the reader the topic.
- Do not rate your own writing or ideas ("the cleanest framing," "to put it plainly," "an honest comparison"), announce a takeaway before giving it ("The lesson:", "The takeaway here is"), or tease an insight ("Here's the thing," "the part most people miss"). If the words before a colon only name what the words after it say, cut them.
- End a sentence on the fact that carries it, not on a verdict or an "-ing" clause that interprets it ("…, highlighting the need for…"). End a paragraph on its last new fact or consequence, not on a restatement, a moral, or a hope.
- Cut announcing phrases ("it is worth noting," "importantly," "the real issue," "at its core"), empty importance claims ("this matters," "plays a key role," "a critical piece"), promotional words ("unlock," "seamless," "game-changing," "transformative"), LLM vocabulary ("delve," "tapestry," figurative "landscape"), scientific terms borrowed for gravitas ("orthogonal" for unrelated, "inflection point" for change), forced groups of three, stacked hedges, "simply" or "obviously" before a hard step, rhetorical questions you answer yourself, and closing punchlines.
- Cut padding: filler ("in order to" for "to," "in spite of the fact that" for "although"), redundant pairs ("first and foremost"), qualifier pairs that deliver no fact ("minor but notable"), and intensifiers ("very," "extremely"). Keep an adverb only when the sentence says less without it.

## Format

Use paragraphs for reasoning, lists for separate items, numbered lists for sequences, and tables for lookup. Use headings only when they help readers find substantial material, in sentence case with a shallow hierarchy. Bold only a decision or a label the reader must find; no bold lead-ins on every bullet, emojis, or decorative dividers.

Body paragraphs run four to six sentences, and four is the floor. A paragraph of one to three sentences is a fragment: merge it into a neighbor on the same topic, or develop it with content the reader needs, and never pad it. Structural blocks are exempt: list lead-ins, captions, footnotes, and the sentence or two that explains a figure or table. Do not split a coherent longer paragraph to hit the range. Put a figure's explanation directly after the figure, saying what it shows and what to take from it, with no sentence before it that only announces the figure.

A top-level section (h2) carries real body: usually two or three paragraphs, sometimes more, often with a table or figure. A section with one paragraph, or an h2 holding only a few bullets, reads oddly; merge it into a neighbor, or make it a minor heading (h4) inside a larger section. A TL;DR or summary section is the exception. When a section runs past about four paragraphs, break it up with a minor heading or a figure rather than adding another h2. A document rarely needs more than six top-level sections, and a short one (under about a thousand words) needs two or three. A heading for each finding turns a document into an outline; findings are paragraphs under a shared heading.

## Edit by removing

Human editors mostly delete, replace, and restructure; model editors mostly add. Prefer the first three. Before adding a sentence, check whether an existing one can carry the point.

Sort weak sentences into two kinds. A fixable sentence has a real claim under bad prose: rewrite it to state that claim. A hollow sentence has no claim to recover (it restates, announces, or praises): delete it. To check that every sentence is about this particular work, ask of each one: would it fit just as well in a document about a different project? Then it is generic: replace it with the specific thing this work found, or delete it. If a hollow sentence sits where the document needs content, flag the gap for the author instead of filling it with invented detail.

For a local edit, make the smallest change that fixes the problem. For a rewrite, restructure as needed while preserving meaning. Return only the writing, without an editing audit, unless asked; if asked for a review, name the consequential problems and give targeted fixes.

## Co-drafting a substantial document

For a design doc, proposal, report, or similar document written with the user, work in three passes, in order: what to say, how to order it, then the words. Most bad documents fail in the first two passes, and no sentence polish fixes a wrong outline, so settle the claims and their order while they are cheap to change. Skip this process for small edits and short messages.

1. Gather context. Start by asking about the audience, the decision or effect the document should produce, the constraints, and whether there is a template. If the user has templates, voice samples, or related documents, read them. Let the user explain in any form, then ask the five to ten questions that close the remaining gaps. You are done when you can discuss edge cases and tradeoffs without needing the basics explained, and can state the document's point in one sentence. If you cannot state it, the problem is in the thinking, and wording will not fix it.
2. Agree the outline with the user before drafting: the argument in a few beats that chain, the section list, and the figures and tables the document will carry. Never write the whole document in one pass.
3. Draft one section at a time. For each one, brainstorm five to fifteen candidate points, let the user keep, cut, combine, and reorder them, and draft from the curated list. Start with the section that has the most unknowns, usually the core proposal or method, not the introduction. Refine each section with surgical edits instead of rewriting it. Where a figure does not exist yet, put a placeholder with its intended file path.
4. Run a coherence pass when the draft is about 80% complete. Reread the whole document for flow, consistency, contradictions, repetition, and filler, and raise problems with the user before polishing.
5. Run a cut pass over the full text. Drop each word, sentence, and number that does not change what the reader understands or decides, and move a number that repeats another or adds needless precision to a table or footnote. Required labels and units, caveats that keep a claim true, and the summary the document type requires are locked. When the user has already approved the text line by line, list the proposed cuts, each with a one-line reason, instead of editing silently.

## Check before returning

Run these checks once, in order. If the user approved the text line by line, do not apply what the checks produce. List each linter fix, review finding and gap closing with a one-line reason, as in the cut pass.

1. Run `~/.claude/skills/write-plainly/check-prose.sh FILE` on the draft. The script runs three linters. sloplint catches rhetorical model tells, with few false alarms. slop-guard, with a tuned config, catches patterns in structure, rhythm and sentences. `lint_prose.py` checks this skill's countable rules, such as dashes, coined labels, paragraph and section shape, and number density.
2. Triage the findings once; do not optimize the score or rerun the linters to chase it. Fix every em dash, coined label, and high-confidence sloplint note unless it sits in a quotation or names something literally. Fix a number-density or section-shape finding by moving numbers into a table or restructuring, never by spelling numbers out or splitting text to dodge the count. Treat a slop-guard rhythm finding as a prompt to check that sentence length follows the content, and fix it only by regrouping content, never by adding a sentence or splitting one to change the spread. Treat a single word-level hit ("robust," "crucial") as a prompt to check that the word is literal and earned, since careful human writers use these words too. Skip findings in quoted material, code, and tables.
3. Search the draft for passive voice and make each instance active unless the actor is unknown or irrelevant; no linter covers this. Compare against the source for numbers, negation, modality, scope, and attribution.
4. For a standalone document others will read, run the review by a fresh reader below.
5. After delivering to a rendered format (Google Docs, a PR page, a rendered site), check what the reader sees: re-read the rendered result for empty paragraphs, lost headings or lists, broken tables, and stray markup.

### Review by a fresh reader

Dispatch two read-only subagents in parallel, and pass neither of them the linter output, so that each reads the document cold:

- `prose-reviewer` (Opus) gets the document path, the intended reader, and the source material if there is any. It returns at most six findings, and zero findings is a valid result. Each finding is a quoted span with its problem and a fix: delete, replace, move to a footnote, the limitations section or the appendix, or requires author input.
- `prose-reader-test` (Opus) gets only the document path and the intended reader, and reads the document alone, without this skill. It predicts the questions a cold reader in that audience would ask, answers each one from the document with a quoted span or "not answered," and lists the gaps.

Apply the reviewer findings you agree with, using deletion, replacement or a move where they suffice. Close each gap from information you have, and place the answer as "Route caveats and detail" says. It goes in the main text only when this reader needs it to decide or act, and otherwise in a footnote, the limitations section or the appendix the main text points to. If you lack the information, flag the gap for the author, and never fill it with an invented fact. If the edits touched more than a few sentences, dispatch `prose-fidelity-checker` (Sonnet) with the earlier version, the source notes if there are any, and the revision. It marks every change in meaning as supported or unsupported by the source. Revert or fix the unsupported ones.

Run this review once. Do not loop critique and rewrite until a reviewer approves: repeated passes accumulate drift and strip useful detail.

## Calibration examples

These show the register and the kind of repair. They are not facts to reuse. Make a repair only when the source supports the revised statement, and leave missing information missing.

| Original | Revision |
| --- | --- |
| The change does more than reduce allocations: it also removes the shared lock. | The change reduces allocations and removes the shared lock. |
| The data refuses to settle the question of whether the effect persists. | The data does not establish whether the effect persists. |
| An evaluation of the revised model was performed by the team. | The team evaluated the revised model. |
| Recall rose from 0.71 to 0.78, precision fell from 0.83 to 0.80, and F1 rose from 0.76 to 0.79. | Recall rose and precision fell slightly, for a small net gain in F1 (Table 2). |
| The new cache dramatically improves performance, reducing median response time from 100 ms to 50 ms. | The new cache reduces median response time from 100 ms to 50 ms. |
| The request could potentially have failed because of a timeout. | The request might have failed because of a timeout. |
| It is worth noting that this study only included experienced developers. | The study included only experienced developers. |
| The pass rate rose after the round-3 fix — a big win. | The pass rate rose after the grader fix that rejects symlinked paths. (If the source does not say what the fix was, flag the label instead of guessing.) |
| Latency fell by 30%, underscoring the value of the new design. | Latency fell by 30%. |
| This approach strikes a good balance between performance and maintainability. | Replace it with the specific trade the source names, such as which query got slower, or delete it. The sentence would fit a document about any project. |
| Overall, these results paint a promising picture for the future of the approach. | Delete. The sentence has no claim to recover. |
| The model was trained on 2M examples. Note that results may vary on other datasets, and further work is needed. | The model was trained on 2M examples. (Cut the generic caveat. If particular untested datasets matter, name them in the limitations section.) |
| The service does not retry failed payments. | Keep this sentence. A reader would otherwise assume failed payments are retried. |
| We did not test on non-English text, so these numbers may not hold there. | Keep this sentence beside the numbers. Without it the claim reads as covering all languages, which would be wrong. |

A developed technical explanation in the target register:

> A random train-test split can overestimate performance on new customers when examples from the same customer appear in both sets. The model may then use customer-specific information that will be unavailable for a new customer. To test performance on new customers, assign each customer's examples to a single split. This makes the evaluation match the intended use more closely. It still does not measure the effect of changes over time, which requires a separate evaluation.

The sources behind these instructions are listed in `sources.md`. Applying the skill does not require reading them.
