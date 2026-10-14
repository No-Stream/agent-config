---
name: visualization
description: Use when making any plot, chart or figure from data in Python (matplotlib, seaborn, pandas plotting), whether quick exploratory plots during analysis or debugging, or final figures for a paper, blog post, report, slide or writeup, and when reviewing or revising existing figures.
---

# Visualization

## Overview

A figure exists to make one comparison or pattern clear to a reader. Start top-down: write the one sentence the figure
should make obvious, then pick the plot that makes that sentence easiest to see. Everything else in this skill follows
from that. Clarity comes first; beauty is welcome when it does not cost clarity.

These rules are the owner's preferences and take precedence over the generic `dataviz` skill for static analysis and
research figures. Use `dataviz` for interactive HTML dashboards; its palette validator is still useful here.

## Decide the mode first

| | Exploratory (debugging, data trawling, many plots) | Final (paper, blog, report, slide) |
|---|---|---|
| Title | Describes what is plotted: "Train loss by step, 4 learning rates x 3 seeds" | States the takeaway as a plain sentence, with every number computed from the data |
| Claims in the figure | None. The data will change as bugs are found; a claim in a title will become false without anyone noticing | Yes, guarded by an `assert` so the script fails if the claim stops being true |
| Polish | Readable labels, uncertainty shown, otherwise fast | Theme for the medium, caption, review pass |
| Review | Look at every image yourself | Look yourself, plus a fresh-eyes reviewer for batches of 5+ figures |

The destination decides. If the request names a paper, post, report, slide or other writeup, the figure is final.
Otherwise it is exploratory. A takeaway title on a debugging plot is a liability: in the baseline test an agent put
"blow-up starts after step ~1400" in a debugging title when the data said ~1200.

If a final figure's message was not given, choose the one the data most clearly supports for the question asked, and
state the chosen message in your report so the owner can change it.

### Final titles: template every number and guard every claim

Never type a number into a title, caption, annotation or label. Compute it, and assert the claim the sentence makes:

```python
rl_gain_over_dpo = mean_accuracy["rl_tuned"] - mean_accuracy["dpo"]
assert diff_ci_low > 0, "Title claims rl_tuned beats dpo, but the 95% CI of the difference includes 0"
title = f"RL tuning adds {rl_gain_over_dpo:.1f} points of accuracy over DPO"
```

If a later fix changes the data, the number updates and a reversed claim crashes the script instead of shipping a false
figure. One claim per title; put a second claim in a second figure or the caption.

The same applies to numbers in the document's text and captions. For LaTeX, have the plotting script also write a
macros file (`\newcommand{\rlGainOverDpo}{4.4}`) and use the macros in the caption and body; for Markdown, generate
the sentence or a small table from the same computed values.

## Pick an archetype

Prefer standard plots. Readers already know how to read them, so they need no explanation. See `archetypes.md` for the
full question-to-plot table with seaborn calls and the uncertainty display for each.

| The sentence is about... | Default plot |
|---|---|
| A vs B (vs C): which is bigger, by how much | Dot + 95% CI (forest plot), or bars from zero when zero is close |
| "Ours beats baseline" | Forest plot of the **difference** with its CI, paired by seed or item, line at 0 |
| How something changes over steps or time | Line with CI band; small multiples if more than ~5 lines |
| The shape of a distribution | Histogram with many bins, ECDF, or strip/rug of raw points |
| Distributions across groups | Box or violin with raw points overlaid, or one ECDF per group |
| Relation between two numeric variables | Scatter, with a fit line only if the fit is the point |
| A matrix (confusion, correlation, sweep grid) | Annotated heatmap with a sequential or diverging map |
| Same plot across slices | Small multiples on shared axes |

A non-standard plot (Tufte-style, slopegraph, custom layout, anything clever) costs the reader effort to decode. Use one
only where it shows something a standard plot cannot, typically a figure 1 or the single key result of a writeup. At
most one per writeup. Supporting and exploratory figures stay standard.

## Show uncertainty

A figure should carry the evidence that could undermine it (Gelman: "any graph should contain the seeds of its own
destruction"). Default to 95% CIs and say what they are.

- Every interval is labelled once, in the legend, axis label or caption: "95% bootstrap CI over 5 seeds".
- Pick the interval by question. Precision of a mean: bootstrap CI or t-interval. Spread of runs: SD or percentile
  interval. Proportions (accuracy, pass rate): Wilson interval (`scipy.stats.binomtest(k, n).proportion_ci(method="wilson")`).
- With 10 or fewer seeds or runs, also draw the individual points, small and light, next to the summary.
- With 3 or 4 runs, a CI is not informative. Show every run, and summarize with the median and the min-max range.
- For "A beats B", plot the CI of the difference. Overlapping per-group CIs do not mean "no difference". Pair the
  difference only on a unit both arms truly share (the same eval items, or seeds that fix the same data order or
  init), and say what it is paired on. When nothing is shared, bootstrap each group independently and plot the CI of
  the difference.
- Lines get shaded bands; points and bars get whiskers; distributions show raw data via fine histogram bins, rugs or
  strips, so noise is visible.
- Tail percentiles: report one with at least ~10 observations beyond it (with 400 requests, p95 rather than p99), and
  give it a bootstrap CI.
- If there are two sources of variance (seeds and eval items), say which one the interval covers.
- If a number is an aggregate (mean over tasks, pooled over items), say how it is weighted.
- A band or whisker that sets the scale is a sign the summary is wrong for the data, not a reason to clip. One
  diverging run, for example, belongs in its own panel or line, not inside a band.

## Encode by importance

Readers judge position on a common scale most accurately, then length, then angle and slope, then area, then color
intensity (Cleveland and McGill). Put the main comparison on position or length.

- The key comparison goes on a shared axis, side by side. Never use bubble size, pie angles or color intensity for it.
- Hue is for identity, at most 5 categories. Beyond that use small multiples or direct labels.
- Highlight the focal series in the first palette color and draw context series in gray.
- Sort categories by value unless they have a natural order (model size, training stage, time).
- Label lines directly at their ends instead of a legend when there are 5 or fewer (`label_line_ends` nudges labels
  apart). When a legend is needed, put it where it covers no data, usually below the axes in one row.
- The same entity has the same color in every figure of a writeup.
- Interchangeable units (seeds, items, requests) share one color. Give one its own color only to point at it.

## Axes

- **Zero:** bars always start at zero. For dots and lines, if zero is in the neighborhood of the data, include it;
  if including it would squash the differences that matter, leave it out and use dots instead of bars.
- **Outliers and huge whiskers:** do not let a few points or one wide interval set the scale. In this order:
  1. If the data are multiplicative (latency, loss ratios, counts across orders of magnitude), use a log scale, say
     "log scale" in the axis label, and label ticks as plain numbers (`plain_log_ticks`), not powers of ten. This
     usually keeps the tail visible, which matters when the tail is part of the question.
  2. If a few values still squash the rest, clip the axis to the bulk of the data and mark the off-scale values at the
     edge with an arrow and their value (`mark_beyond_limit`, which merges several at one position).
  3. Avoid broken axes; use a second panel or an inset.
- Gridlines run across the value axis only. The theme draws them for a vertical value axis; for a horizontal layout
  (forest plots, horizontal strips) switch with `ax.grid(axis="y", visible=False); ax.grid(axis="x", visible=True)`.
- Small multiples share axes unless there is a reason not to, and then the panel says so.
- Axis labels name the quantity and unit in plain words: "Accuracy (%)", not "acc".

## Style

Copy `vizstyle.py` from this skill's directory into the project next to the plotting code (do not import it from the
skill directory; the project must stay reproducible). It provides light and dark themes, a cool, colorblind-checked
palette (blue, green, purple first; amber and plum only for a 4th and 5th category), and helpers.
`example_final_figure.py` is a complete final figure: paired-difference forest plot, computed and asserted title,
dark and light exports.

- **Medium decides the theme:** paper, PDF and arXiv use light. Blog posts use dark, and export light as well unless
  the owner says otherwise. `save_figure(draw, path_stem, themes=...)` renders one PNG per theme from the same code.
- Erase what carries no information: top and right spines, boxes around legends, outlines on bars, heavy grids, 3D,
  shadows, background fills. Keep light gridlines, axis labels and reference lines (zero, baseline, chance level).
- Show context the reader needs to judge size: chance level, the baseline, the previous best.
- Up to three sentences of pale gray text below the plot (`add_caption`) may explain what the plot cannot show itself.
  A figure that needs more than that is probably the wrong plot. In a paper, the document's own caption does this job
  instead, and follows the paper-drafting skill.
- Size text for the final display: readable at the column or screen width where the figure will appear.
- Multi-panel figures: the message goes in `fig.suptitle(title, x=0.01, ha="left", fontweight="bold")`; panel titles
  just name the panel.

## Look at every figure

Writing the code is not the end. After the final render, open every saved file with the Read tool, both themes,
and check each against this list. "Only the title changed" and "that edit did not touch this figure" are not
exceptions: every agent in testing that skipped a re-check used one of those two reasons.

- [ ] The one-sentence message is obvious within five seconds.
- [ ] Nothing is clipped, overlapping or colliding (titles, tick labels, direct labels, legend).
- [ ] Every interval and marker type is explained once.
- [ ] No outlier or whisker sets the scale; off-scale values are marked.
- [ ] Axis labels have units; zero is handled per the rule above.
- [ ] Final mode: every number in the text is computed, and the claim has an assert.
- [ ] Colors are distinguishable and consistent with the other figures.

For 5 or more final figures, or any figure 1, dispatch a reviewer subagent with fresh context. Follow `review.md`.
If you cannot dispatch one (for example, you are a subagent yourself), say in your report that the review is still
owed and list the figures that need it.

## Common mistakes

| Mistake | Fix |
|---|---|
| `"RL-tuned scores 74.5%..."` typed as a literal string | f-string from computed values, plus an assert on the claim |
| Takeaway titles on exploratory plots | Descriptive titles until the result is final |
| Bars on a 0-100 axis to compare 70 vs 74 | Forest plot of differences with CIs, no forced zero |
| 12 raw noisy lines on one panel | One summary line and band per config (median and range for 3-4 seeds), or small multiples; outlier runs drawn separately |
| Sequential ramp for 4 categories, two shades indistinguishable | Categorical palette, or direct labels plus small multiples |
| Error bars with no statement of what they are | Label once: "95% bootstrap CI over 5 seeds" |
| One extreme value stretches the axis | Log scale if multiplicative; otherwise clip and mark off-scale values |
| Declared done without opening the image | Read every saved file, every theme, after the final render |
