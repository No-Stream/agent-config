# Archetypes

Pick by the sentence the figure should make obvious. Seaborn axes-level functions take `ax=` and fit custom layouts;
figure-level ones (`relplot`, `displot`, `catplot`) own the figure and make small multiples with `col=` / `row=`.
Seaborn's `errorbar=` takes `("ci", 95)` (bootstrap CI of the estimate), `"se"`, `"sd"` or `("pi", 95)` (spread).
CI and SE shrink with more data; SD and percentile intervals do not. Pick by whether the reader should judge the
precision of an estimate or the variability of runs.

## Comparisons

| Sentence | Plot | How | Uncertainty |
|---|---|---|---|
| "A, B and C differ by this much" | Dot + CI, horizontal, sorted by value | `sns.pointplot(..., errorbar=("ci", 95), linestyle="none")` or `ax.errorbar` | CI whiskers; raw seed points if 10 or fewer |
| Same, zero is close to the data | Bars from zero | `sns.barplot(..., errorbar=("ci", 95))` | Whiskers; overlay `sns.stripplot` for seeds |
| "Ours beats each baseline" | Forest plot of differences vs a reference, line at 0 | Compute paired differences per seed or item, bootstrap their mean, `ax.errorbar` | CI of the difference. This is the plot that answers the question; per-group CIs do not |
| Before vs after, per item | Slopegraph or paired dots | Two x positions, one thin line per item | Implicit in the spread of lines; add mean with CI |
| Many models x many tasks | Small multiples of dot + CI, or annotated heatmap of differences | `sns.catplot(kind="point", col=...)` or `sns.heatmap(annot=True)` | Whiskers per panel; for heatmaps, mark cells whose CI includes 0 |
| Counts per category | Bars from zero | `sns.countplot` | Usually none needed |

Accuracy and other proportions: use Wilson intervals, not normal-approximation ones, which misbehave near 0 and 1.
`scipy.stats.binomtest(n_correct, n_items).proportion_ci(confidence_level=0.95, method="wilson")`.

## Change over time, steps or a continuous setting

| Sentence | Plot | How | Uncertainty |
|---|---|---|---|
| "Y changes with X" | Line | `sns.lineplot(..., errorbar=("ci", 95))` | Shaded band |
| Several configs over training | Mean line + band per config, direct labels | `sns.lineplot(hue=...)` then `vizstyle.label_line_ends` | Band over seeds; also draw seeds as thin lines if 3 or fewer |
| One run behaves differently | Small multiples per config, or the odd run drawn separately and labelled | `sns.relplot(kind="line", col=..., units="seed", estimator=None)` | Each seed visible |
| Noisy curves | Raw curve faint, smoothed curve bold, both drawn | Rolling mean or EMA; state the window | The faint raw curve shows the noise |
| Scaling (compute, params, data) | Line or scatter on log-log | `ax.set_xscale("log")` | Band or whiskers per point |

## Distributions

| Sentence | Plot | How | Uncertainty |
|---|---|---|---|
| "This is the shape of X" | Histogram with many bins | `sns.histplot(bins=...)`, use as many bins as stay readable | Visible bin-to-bin jitter shows the sampling noise |
| Compare a few distributions | ECDF per group, or overlaid step histograms | `sns.ecdfplot(hue=...)`, `sns.histplot(element="step", fill=False)` | ECDFs need no binning choice |
| Compare many groups | Box or violin with raw points | `sns.boxplot(showfliers=False)` + `sns.stripplot(size=2, alpha=.4)` | Raw points |
| Small n | Strip or swarm plot only | `sns.stripplot`, `sns.swarmplot` | Every point is shown |
| Heavy tails (latency, cost) | Strip of points on a log axis, with the median and a tail percentile marked | `ax.set_xscale("log")` + `vizstyle.plain_log_ticks` | Bootstrap CI on both; pick a percentile with at least ~10 points beyond it |
| Marginal detail for a scalar | Rug under a histogram or KDE | `sns.rugplot` | Rug shows each observation |

## Relationships

| Sentence | Plot | How | Uncertainty |
|---|---|---|---|
| "X and Y are related" | Scatter | `sns.scatterplot`; alpha or hexbin when dense | Fit line with band only if the fit is the claim: `sns.regplot` |
| Calibration (predicted vs observed) | Binned reliability plot with the diagonal | Bin by predicted value, plot mean observed per bin | Wilson CI per bin; histogram of predictions underneath |
| Agreement between two measures | Scatter with the y = x line | `ax.axline((0, 0), slope=1)` | Equal aspect ratio |
| All pairwise relations, exploratory | Pair grid | `sns.pairplot` | Exploratory only |

## Matrices

| Sentence | Plot | How | Uncertainty |
|---|---|---|---|
| Confusion matrix | Heatmap, row-normalized, annotated | `sns.heatmap(annot=True, fmt=".0%")` | State n per row |
| Correlations or differences with a meaningful 0 | Diverging map centered at 0 | `sns.heatmap(center=0, cmap="RdBu_r" or a blue-purple diverging map)` | Hatch or gray out cells whose CI includes 0 |
| Hyperparameter grid | Sequential map, annotated | `cmap="viridis"` or `"mako"` | Annotate mean, note seeds per cell |

Sequential maps: `viridis`, `mako`, `cividis`. Never `jet` or `rainbow`. Diverging maps only when the midpoint means
something (zero, chance, the baseline).

## Non-standard plots

Allowed for one key figure per writeup when a standard plot cannot show the point: a slopegraph of rank changes,
a small-multiple grid of sparklines, a hand-annotated figure 1 that walks through the method. The reader has to learn
how to read it, so it needs a clear title, direct annotations on the plot, and a reviewer pass that checks whether a
first-time reader gets the message.
