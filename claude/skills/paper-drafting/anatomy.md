# Section anatomy

Guidance per section, in the order they appear in a finished paper. Write them in the order the main skill gives
(methods and results first, the abstract last).

## Title

States the main claim or the question, in plain words. Many more people read the title than anything else.

## Abstract (paper)

The reader arrives cold and may not know the subfield or the kind of paper. Roughly one sentence per idea:

1. An uncontroversial statement placing the work in its area.
2. The gap, problem or unknown that motivates the work.
3. The main contribution, losing nuance if needed.
4. Optional: what the claim means, or how it can be tested.
5. One sentence per key piece of evidence or secondary claim, with at least one concrete number.
6. Why it matters and how strong the evidence is ("a preliminary step towards", "practitioners should", "compelling
   evidence that").

Use simple language; define any jargon that cannot be avoided.

## TL;DR (post)

An epistemic-status line first (how much work went into this, overall confidence, the weakest part). Then 3-6
bullets: the main finding with its number and confidence, the key evidence, the most important caveat, and why it is
interesting. A reader who stops here should have the whole story.

## Introduction

An extended abstract that a reader can stop after. Repetition with the abstract is fine.

1. **Context**: the topic, the motivating question, why it matters. Cite to show the problem is real.
2. **Background**: what is known, which established techniques this builds on, why existing work does not settle the
   question.
3. **Main claim**, with the nuance and definitions it needs. Be explicit about what is new and what is prior work.
   The same results read as arrogant or as modest depending on how the novelty is framed.
4. **The case**: the most important evidence for it. Repeat 3-4 for a second or third claim.
5. **Implications**: who should do what differently, which misconception this corrects. Hedge the ones the evidence
   does not establish ("plausibly", "speculatively") and point to the implications section.
6. **Contributions**: a bullet list of claims, each with its key evidence in a phrase and, in a paper, the section
   that argues it.

The introduction sets the structure of the rest of the paper.

## Figures and tables

Figures carry most of the message for skimmers. Plan each one around a single takeaway.

- Decide what the reader should conclude, then choose the plot that makes that obvious. Highlight the key line or bar;
  mute the rest.
- Readable axes, tick labels and legends; units on every axis.
- Captions should stand alone: what is shown, how to read it, the intended interpretation, key technical detail
  (n, seeds, error bar meaning).
- Heatmaps: sequential scale starting white at zero for non-negative data; diverging scale with white at zero for
  signed data. Do not encode key information as red versus green.
- Combining several panels into a figure 1 often works. An explanatory diagram of the main idea is a strong figure 1.
- For making and reviewing the figures themselves (plot choice, uncertainty, computed titles, themes, review), use the
  visualization skill.

## Background

Define terms and techniques the reader needs. Keep new definitions for this work in a separate, clearly marked
subsection so they are not mistaken for prior work. A glossary appendix helps when space is short.

## Methods and results

Most of the word count. A skeptical, engaged reader must be able to see exactly what was done and draw their own
conclusions.

- Explain what was done, why it bears on the claim, the technical choices and how they affect interpretation.
- Organise by claim. If each claim has its own kind of evidence, give each its own section with method and result
  together; a long methods section followed by a long results section makes readers forget the method before they see
  its result. If experiments share one method, a single methods section with a subsection per experiment is fine.
- Plan each paragraph's first and last sentence: what it shows and how it connects to the claim.
- Report baselines, controls, sample sizes and uncertainty next to the result, not in an appendix.
- Say how the result was found: what was explored, roughly how many variants were tried, which shortcuts were taken,
  and how the reported result was confirmed.
- Give enough detail to replicate; link code where possible.

## Limitations

Required. The reader needs a calibrated sense of what was learned, and the authors know the weaknesses better than
anyone. Include: conditions not tested, small samples, untuned baselines, alternative explanations not ruled out, and
likely misreadings or over-updates. Researchers whose opinion matters think more of work that states its limits.
For each central claim, say what result would most lower our confidence in it, unless the results section already
does.

## Implications and speculation

Papers and posts. The broader conclusions the authors find plausible but this work does not establish: what the result
suggests about other models, settings or open questions, and intuitions about mechanism. Each item gets a confidence
(a probability, or a word from the confidence vocabulary in the main skill), the reason we believe it, and the evidence
that would change it. In a conference paper keep it to a short section; in a post it can run as long as it is useful.

## Related work

Paper: usually the penultimate section and short. For each closely related paper, say how this work differs. If the
difference is small, say so (parallel work, a fix to a flaw in it, a more rigorous version). Criticise methods
politely and never authors. Put related work up front only when the paper exists to fill a gap in or correct specific
prior work. Post: inline links, plus a section only if the post corrects or extends specific prior work.

A literature-search subagent given the claims ledger is a good way to find what must be cited. When a citation
supports a specific claim, cite the section or page; in a post, a short quote in a footnote helps.

## Discussion and conclusion

Omit by default. If an insight is worth stating, it belongs in the abstract or introduction; a plausible but
unestablished implication belongs in the implications and speculation section.

## Appendices

Everything else: full hyperparameters, extra experiments, the rabbit holes, the cut-list items marked *appendix*.
Lightly read, so low polish is fine. A tacit-knowledge appendix (what was hard, what broke, advice for replicators,
open directions) is often the most useful part for the few who read it.
