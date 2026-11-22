---
name: write-plainly
description: Use when writing, co-drafting or revising nonfiction prose that people other than the user will read, such as a README, a Google Doc, a report, memo, design doc, proposal, recommendation, research write-up, PR description, documentation, a message the user will send to a colleague, or anything published online, including substantive edits to an existing draft. Also use when the user asks to make writing plainer or clearer, or to remove AI writing tells, sales language, excess metaphor or mannered phrasing. Not for chat replies to the user, agent instruction files, internal scratch notes, or intentionally literary writing.
---

# Write plainly

Write so the reader understands on the first reading, with the least effort. Preserve accuracy and meaning first; then aim for clarity, information density, intuitive explanation, and rigor without verbosity. A document should take longer to write than to read, and every sentence in it should be about this particular work. The register is casual, straightforward and a bit breezy, and also direct and literal: plain words, with no metaphor, flash, or sales and search-engine language. From technical standards take only their precision: stable terms, modality treated as content, explicit conditions, and claims the reader can check. First person, contractions, and direct judgments are fine.

Sounding human gets little weight, and sounding polished or impressive gets none. The obvious model tics still matter, because a reader who spots an em dash or a reflexive "not X, but Y" stops reading carefully.

Before drafting a substantial document with the user, follow "Co-drafting a substantial document" below. For papers and research write-ups, `paper-drafting` decides the narrative, the claims and the drafting order, and this skill governs the prose. For figures, use `visualization`.

## Preserve meaning

Keep quantities, units, names, dates, attribution, comparisons, causal direction, negative findings, and the line between observation and inference. Treat modality as content: "fails," "might fail," "must," "should," "may," and "will" make different claims, so do not change them to sound firmer. Keep quotations, identifiers, commands, code, and link targets unchanged.

Add specificity only from information you have. Never invent a number, mechanism, quotation, source, or example presented as fact to improve a sentence. If an essential detail is missing, flag it; otherwise keep the accurate general statement.

## Organize for the reader

Give the answer first. A readout or report leads with the finding and the conditions needed to understand it; a proposal leads with a problem the reader already has, stated as a fact, and states the ask in the first paragraph. Then order the support as the reader needs it: setup before a mechanism, evidence before a disputed inference, prerequisites before an action. Do not narrate the order in which you found things; what was tried and failed goes to an appendix unless the failure is the finding.

The intended reader sets the document's purpose: the question it answers and the decision it supports. Explain for the reader with the least context, a smart reader outside the field who saw neither the work nor the conversation behind it, even when the intended reader is a specialist. Give each term outside common knowledge a short plain explanation where it first appears, then use the term: "the endpoint is idempotent: sending a request twice has the same effect as sending it once." To stay clear without dumbing it down, explain a term once and briefly, leave alone what any educated reader knows (a percentage, an average), and add no padding.

Develop one idea per paragraph. When a claim rests on a method, a setup, or a mechanism, explain it so a reader outside the field can follow and check it: what goes in, what each step does, what is held fixed, and why that makes the result valid. Give the intuition in plain words before the formal detail, so the reader can work through a small case. Define a quantity by the arithmetic that produces it, and carry one concrete example through the explanation instead of introducing a new one for each point.

Include a detail only if it changes the claim, its scope, the confidence it deserves, or the decision, but keep the reasoning the reader needs to check the conclusion. For comparisons, name the criteria, reach a judgment, and say what would change it; do not give weak options equal space to look balanced. Stop when the task is answered, without a recap.

When the team that owns a system will read about it, describe their system and past choices neutrally, without verdicts such as "wrong" or "broken." Present a gain as the next revision of their work, credit by name the people who built what you extend, and raise only the faults that change what this reader decides.

## Sequence the argument

A document reads top to bottom, so later sections build on earlier ones instead of standing alone. Give each fact one home section and refer to it from elsewhere; the TL;DR or summary is the one place that repeats. After drafting a paragraph, name the question a cold reader now has. The next paragraph answers it, and a paragraph that answers no open question is misplaced or cuttable. Apply the same test to the outline and again in the coherence pass: each section answers the question the one before it raised.

Transitions assert inference. "So," "but," and "because" claim a relation between two paragraphs, so use them only when the relation holds. If only "also" or "additionally" fits, the paragraphs sit in an arbitrary order: reorder them until a real connective fits, or accept that the material is a list and format it as one.

When the document's job is to correct a belief, state that belief once, in terms its holders would accept, and only if this reader actually holds it; a belief nobody holds is a straw man. Answer the two or three objections this reader will actually raise, where they arise, in a clause joined to the answer: "the speedup could come from a warmer cache, but the cold-start runs show the same gain."

## Route caveats and detail

A caveat sits beside a claim only when the claim is wrong without it, and then once. An important nit goes in a footnote, and a substantive limitation goes in a limitations section. Everything else, such as every configuration and run, goes in a separate appendix document that the main text links to.

Hedge where the uncertainty lives. Forecasts, estimates, and secondhand facts carry a hedge; measured results are stated plainly, and a headline claim carries at most one marker such as "we expect." State an unfavorable result as plainly as a favorable one, without excuses, and label a hypothesis as one once. Keep a hedge that states real uncertainty ("probably," "I think"), and cut vagueness that dodges a specific claim ("various enhancements"). When a reviewer or your own instinct asks for another qualification, first check whether the claim already has the right strength; reviewers tend to ask for more caveats than these rules allow.

Some results have a status the reader must know first: an interim read partway through a test, simulated data, a back-of-envelope estimate, or a hypothetical example. Say so once, prominently, where the reader first meets the result ("an interim read, two weeks into a two-month test"). Then give the best current reading plainly, without verdicts the data cannot yet support, such as a pass or fail on an unfinished test.

## Readable beats short

Minimize the reader's time to understand, not the word count. A reader who rereads a sentence, or comes back with a question, has already spent more time than the shorter draft saved. Cutting fixes padded, promotional prose, but overdone, it produces a second machine register.

Shorten a draft by dropping details that would not change what the reader does next, and write everything that survives in full sentences. These compression devices are out:

- Fragments, dropped subjects, and dropped articles. "Tests green, deploy pending" becomes "The tests pass, and the deploy is waiting for approval."
- Abbreviations the reader has to expand, such as "RPS" for "requests per second." Spell out an acronym outside common knowledge once, as in "time to first byte (TTFB)," then use it.
- Arrow chains in place of a sentence. "cache miss -> DB read -> timeout" becomes "On a cache miss the request goes to the database, and the read times out." Arrows are fine in diagrams, shell pipelines, and code.
- Hyphenated compounds stacked into a noun phrase that should be a clause. "The per-tenant rate-limit config change" becomes "the change that gives each tenant its own rate limit."
- Labels coined during the work: plan step numbers ("step 4"), option letters ("option B"), round numbers ("round 3"), or nicknames ("the pool"). The reader did not see the work, so say what the thing is ("the rerun with the patched grader," not "run B"), and give variants and stages descriptive names ("median" and "stack," not "A" and "B").

Give each identifier its own clause that says in plain words what it is: "We raised `max_retries`, the number of times the client resends a failed request, from 3 to 5," not "`max_retries` 3->5 fix." Translate vocabulary from your source material (a team's nicknames, a dataset's column codes) or define it in place, and use the term the field already uses ("epoch," "held-out set") instead of inventing one or paraphrasing it at greater length. Refer to things by name: no "as in the second case," "the former," or "the change mentioned earlier" reaching back several paragraphs, because repeating a noun phrase costs the reader less than a lookup. Use one term per concept throughout, without switching synonyms for variety.

## Sentences

Give each sentence a real actor as its subject and a verb that states what the actor does. Write in active voice. Use passive voice only when the actor is unknown or irrelevant, and never invent an actor. Keep the subject next to its verb, put a condition before the claim it limits, and open with what the reader already has so the sentence ends on the new information. Turn action nouns back into verbs ("we migrated the tables," not "the migration of the tables") and unpack noun stacks. Write the plain clause instead of a cleft that fronts an abstraction: "What limits throughput is the index lock" becomes "The index lock limits throughput."

Keep most sentences short enough to follow in one pass, and split one that runs past about 40 words unless it is a plain list. Let the shorter plain version win a tie. Split two clauses joined by a semicolon or colon unless the join itself carries meaning. Vary length by regrouping content (join parallel items into one sentence, give a separate point its own), never by adding a sentence for rhythm. Prefer the everyday word to a formal synonym ("use," not "utilize") unless the formal word is the term of art. Read a doubtful sentence aloud; if you would not say it to a colleague, rewrite it.

Check that the subject can do what the verb says. A test, a log, or a dataset can show, find, measure, need, or fail; it cannot want, tell, believe, refuse, or struggle. When a person acted, make the person the subject: "we sent half the requests to the new server," not "the new server took half the requests." When writing about AI models, describe their behavior and do not attribute intention or experience without evidence. Do not use a stronger causal verb than the evidence supports.

Write literally. In documents, use no metaphor; an everyday idiom may stay when it is the plainest wording, and established technical terms such as "cache" or "bottleneck" are literal. The usual slips are images for a threshold (a bar, a floor, a yardstick), for a method (a ladder, a bridge, a lens), and for a set of assumptions (a ledger). Name the threshold, the method, or the assumptions instead. Use an analogy only when it explains faster than the literal account, then return to the mechanism.

Say what each part does. Use a negative only when the reader would otherwise assume the opposite: "the service does not retry failed payments." Do not define something by what it is not; "the scheduler never decides the order" becomes a statement of what does decide it ("each job's priority field sets the order").

## Evidence and numbers

State what was measured, changed, or compared, and under what conditions. Separate measurements from your interpretation and your recommendation, and mark which sentences are which, so speculation does not read with the confidence of data. State a material assumption once. An inconclusive result is not evidence of equivalence, and a search that found nothing shows only that you found nothing. Cite the source for each claim, prefer primary sources, and do not claim to have checked sources you did not read. Attribute a claim to a named person, document, or dataset; "experts" and "studies" give the reader no one to check.

Tables, figures, captions, footnotes, and the appendix carry the supporting detail: test statistics, degrees of freedom, p-values, interval endpoints, and side-by-side rates. All other prose, the summary included, keeps only the headline numbers the reader acts on. Body prose carries at most about 2 numbers per 100 words, and no paragraph carries more than two. The TL;DR or summary, tables, captions, footnotes, and the appendix are exempt from this count. The sentence beside the table says which way the result went, roughly how large it is in plain words ("several times faster," "a slight drop"), and whether it is distinguishable from noise, then points to the table. A comparison across several groups is a table, never a sentence per group.

For each number you keep, express the result once: the effect size ("median runtime fell by 20%"), or the endpoints when the absolute values matter ("from 25 s to 20 s"), not both plus a ratio. Give each important number its metric name, baseline, denominator, units, and period, and put numbers the reader will compare on one scale. Distinguish percent from percentage points, and match precision to the measurement.

Write numbers in their idiomatic form: digits, a percentage for a share ("40%," not "4 in 10"), and a metric name in its standard form ("Recall@10"). Write a range with "to" or a dash, since square brackets read as a confidence interval. Separate two results with a comma instead of nesting one in parentheses. A small count in words ("two options") is fine.

When a number, figure, or conclusion looks inconsistent with an earlier one, say so where the second one appears, and give the reason they differ, such as a different population, time window, or definition. A reader who sees one quantity at two values stops trusting both. Keep a synthetic or simulated test apart from the real result, and say which one each later statement is about. A difference you cannot explain may be a bug, so check it before the document goes out.

Write procedures as numbered imperative steps in execution order. Do not invent thresholds or acceptance criteria.

## Remove mannerisms

Rewrite the underlying claim instead of swapping words, and do not replace a habit with slang, fake anecdotes, or choppy fragments.

- Never use em dashes. Use a comma, parentheses, a colon, a semicolon, or a new sentence, whichever fits the relationship. An en dash or spaced hyphen in the same role is also out; en dashes in numeric ranges are fine.
- Drop "not X, but Y," "not just X, but Y," and contrastive "X rather than Y" unless the reader actually holds X or X is a plausible cause the evidence rules out. Keep a contrast that states a limitation.
- Open with the information. Do not open with why the topic matters or with what the document covers ("in this document," "as described below"). Enthusiasm is fine when the specific result justifies it.
- A paragraph's first sentence should make its first claim. A bold run-in label ("**How accurate the clock is.**") or a sentence that only announces the topic ("The clock has three sources of error.") adds nothing; state the claim, which tells the reader the topic.
- Do not rate your own writing or ideas ("the cleanest framing," "to put it plainly," "an honest comparison"), announce a takeaway before giving it ("The lesson:", "The takeaway here is"), or tease an insight ("Here's the thing," "the part most people miss"). If the words before a colon only name what the words after it say, cut them.
- End a sentence on the fact that carries it, and cut a trailing verdict or an "-ing" clause that interprets the fact ("…, highlighting the need for…"). End a paragraph on its last new fact or consequence, with no restatement, moral, or hope after it.
- Cut announcing phrases ("it is worth noting," "importantly," "the real issue," "at its core"), empty importance claims ("this matters," "plays a key role," "a critical piece"), promotional words ("unlock," "seamless," "game-changing," "transformative"), LLM vocabulary ("delve," "tapestry," figurative "landscape"), scientific terms borrowed for gravitas ("orthogonal" for unrelated, "inflection point" for change), forced groups of three, stacked hedges, "simply" or "obviously" before a hard step, rhetorical questions you answer yourself, and closing punchlines.
- Cut padding: filler ("in order to" for "to," "in spite of the fact that" for "although"), redundant pairs ("first and foremost"), qualifier pairs that deliver no fact ("minor but notable"), and intensifiers ("very," "extremely"). Keep an adverb only when the sentence says less without it.

## Format

Use paragraphs for reasoning, lists for separate items, numbered lists for sequences, and tables for lookup. Use headings only when they help readers find substantial material, in sentence case with a shallow hierarchy. Bold only a decision or a label the reader must find; no bold lead-ins on every bullet, emojis, or decorative dividers.

Body paragraphs run four to six sentences. A paragraph of one to three sentences is a fragment: merge it into a neighbor on the same topic, or develop it with content the reader needs, and never pad it. Structural blocks are exempt: list lead-ins, captions, footnotes, and the sentence or two that explains a figure or table. Do not split a coherent longer paragraph to hit the range. Put a figure's explanation directly after the figure, saying what it shows and what to take from it, with no sentence before it that only announces the figure.

Size the main text to the document's job. Tables and figures do not count against the word budget. Without a stated budget, aim for these lengths, counting a page as about 300 words:

| Document | Main text |
| --- | --- |
| Short readout or status update | About 600 words |
| Full readout or report | At most 1,500 words |
| Proposal, or a note to senior readers | 300 to 450 words |

A top-level section (h2) usually carries two or three paragraphs, sometimes more, often with a table or figure. A section with one paragraph, or an h2 holding only a few bullets, reads oddly; merge it into a neighbor, or make it a minor heading (h4) inside a larger section. A TL;DR or summary section is the exception. When a section runs past about four paragraphs, break it up with a minor heading or a figure rather than adding another h2. A document rarely needs more than six top-level sections, and a short one (under about a thousand words) needs two or three. A heading for each finding turns a document into an outline; findings are paragraphs under a shared heading.

## Summaries, PR descriptions, and drafted messages

A TL;DR opens with one sentence on what the work is and why it was done, then gives the findings and the recommendation, in about five to eight sentences in all. Each sentence must make sense to a reader who reads nothing else, so it uses no term it leaves unexplained and carries no statistical detail or worked example.

A pull request or code-review description opens with four to six plain sentences on the main intended change: what it changes and why. Most reviewers read only that. Further detail, and whatever the repository's template asks for, goes below a horizontal rule, marked as an appendix and in small type where the format allows it. A screenshot is welcome when it shows the change faster than text.

A message drafted for the user to send to a colleague, such as a chat post, an email, or a request to another team, is one to four casual, plain sentences unless the user asks for more. It says what happened or what is needed, plus one concrete example if it helps. Write it the way a coworker would, with normal capitalization even if the user types in lowercase, show it inline in your reply, and stop. The sentence and word rules apply to it; the paragraph and section rules do not.

## Edit by removing

Human editors mostly delete, replace, and restructure; model editors mostly add. Prefer the first three. Before adding a sentence, check whether an existing one can carry the point.

Sort weak sentences into two kinds. A fixable sentence has a real claim under bad prose: rewrite it to state that claim. A hollow sentence has no claim to recover (it restates, announces, or praises): delete it. A sentence that would fit just as well in a document about a different project is generic: replace it with the specific thing this work found, or delete it.

For a local edit, make the smallest change that fixes the problem. For a rewrite, restructure as needed while preserving meaning. Return only the writing, without an editing audit, unless asked; if asked for a review, name the consequential problems and give targeted fixes.

When the user owns the document or has approved its text, leave the document unchanged. Propose each edit in the conversation as a numbered before-and-after pair with a one-line reason, and apply only the pairs the user accepts. The cut pass and the checks before returning follow this rule too.

## Co-drafting a substantial document

For a design doc, proposal, report, or similar document written with the user, work in three passes, in order: what to say, how to order it, then the words. No sentence polish fixes a wrong outline, so settle the claims and their order while they are cheap to change. Skip this process for small edits and short messages. Write a document that others will read only when the user asks for one, and show each section's proposed text in the conversation before inserting it into a shared document.

1. Gather context. Start by asking about the audience, the decision or effect the document should produce, the constraints, and whether there is a template. If the user has templates, voice samples, or related documents, read them. Then ask the five to ten questions that close the remaining gaps. You are done when you can discuss edge cases and tradeoffs without needing the basics explained, and can state the document's point in one sentence. If you cannot state it, the problem is in the thinking, and wording will not fix it.
2. Agree the outline with the user before drafting: the argument in a few beats that chain, the section list, the figures and tables the document will carry, and the word budget ("Format" gives defaults).
3. Draft one section at a time. For each one, brainstorm five to fifteen candidate points, let the user keep, cut, combine, and reorder them, and draft from the curated list. Start with the section that has the most unknowns, usually the core proposal or method; the introduction comes later. Refine each section with surgical edits instead of rewriting it. Where a figure does not exist yet, put a placeholder with its intended file path.
4. Run a coherence pass when the draft is about 80% complete. Reread the whole document for flow, consistency, contradictions, repetition, and filler, and raise problems with the user before polishing.
5. Run a cut pass over the full text. Drop each word, sentence, and number that does not change what the reader understands or decides. Required labels and units, caveats that keep a claim true, and the summary the document type requires are locked.

## Check before returning

Run these checks once, in order.

1. Run `~/.claude/skills/write-plainly/check-prose.sh FILE` on the draft. It runs sloplint, slop-guard with a tuned config, and `lint_prose.py`, which checks this skill's countable rules.
2. Triage the findings once, and never rerun the linters to chase the score. Fix every em dash and high-confidence sloplint note unless it names something literally. Read each finding whose message starts with "Check:" and fix it only when the flagged text is a real instance. Fix a number-density or section-shape finding by moving numbers into a table or restructuring, never by spelling numbers out or splitting text to dodge the count. Fix a slop-guard rhythm finding only by regrouping content, never by adding or splitting a sentence to change the spread. Treat a single word-level hit ("pivotal," "landscape") as a prompt to check that the word is literal and earned. Skip findings in quoted material, code, and tables.
3. Search the draft for passives (`lint_prose.py` flags only those that name an actor) and make each active unless the actor is unknown or irrelevant. Compare against the source for numbers, negation, modality, scope, and attribution.
4. For a standalone document others will read, run the review by a fresh reader below.
5. After delivering to a rendered format (Google Docs, a PR page, a rendered site), re-read what the reader sees for empty paragraphs, lost headings or lists, broken tables, and stray markup.

### Review by a fresh reader

Dispatch two read-only subagents in parallel, and pass neither the linter output, so each reads the document cold:

- `prose-reviewer` (Opus) gets the document path, the intended reader, and any source material.
- `prose-reader-test` (Opus) gets only the document path and the intended reader, and reads the document without this skill. It returns the questions a smart reader outside the field would ask, each answered from the document or marked "not answered."

Apply the reviewer findings you agree with. An applied fix, like the draft, keeps supporting statistics out of body prose. Always fix a term either reviewer marks as unexplained or coined. Close every remaining gap from information you have, placing the answer where "Route caveats and detail" sends it, and flag the rest for the author. If the edits touched more than a few sentences, dispatch `prose-fidelity-checker` (Sonnet) with the earlier version, any source notes, and the revision, and revert or fix each change in meaning it marks unsupported by the source.

Run this review once, since repeated rounds of critique and rewrite accumulate drift and strip useful detail.

## Calibration examples

These show the register and the kind of repair. They are not facts to reuse.

| Original | Revision |
| --- | --- |
| The change does more than reduce allocations: it also removes the shared lock. | The change reduces allocations and removes the shared lock. |
| The data refuses to settle the question of whether the effect persists. | The data does not establish whether the effect persists. |
| An evaluation of the revised model was performed by the team. | The team evaluated the revised model. |
| Recall rose from 0.71 to 0.78, precision fell from 0.83 to 0.80, and F1 rose from 0.76 to 0.79. | Recall rose and precision fell slightly, for a small net gain in F1 (Table 2). |
| The pass rate rose after the round-3 fix — a big win. | The pass rate rose after the grader fix that rejects symlinked paths. (If the source does not say what the fix was, flag the label instead of guessing.) |
| Latency fell by 30%, underscoring the value of the new design. | Latency fell by 30%. |
| This approach strikes a good balance between performance and maintainability. | Replace it with the specific trade the source names, such as which query got slower, or delete it. |
| Overall, these results paint a promising picture for the future of the approach. | Delete. The sentence has no claim to recover. |
| The model was trained on 2M examples. Note that results may vary on other datasets, and further work is needed. | The model was trained on 2M examples. (Cut the generic caveat. If particular untested datasets matter, name them in the limitations section.) |
| No library clears the bar we set for cold starts. | No library starts in under 200 ms, the limit we set. |
| No browser has ever shipped this API without a flag. | We could not find a browser that ships this API without a flag. |
| Fix the broken cache eviction (a proposal title, read by the cache's owners) | Size-aware eviction for the page cache |
| We did not test on non-English text, so these numbers may not hold there. | Keep this sentence beside the numbers. Without it the claim reads as covering all languages, which would be wrong. |

A developed technical explanation in the target register:

> A random split into training and test sets can overestimate performance on new customers when examples from the same customer appear in both sets. The model may then use customer-specific information that will be unavailable for a new customer. To test performance on new customers, assign each customer's examples to a single split. This makes the evaluation match the intended use more closely. It still does not measure the effect of changes over time, which requires a separate evaluation.

The sources behind these instructions are in `sources.md`. Applying the skill does not require reading them.
