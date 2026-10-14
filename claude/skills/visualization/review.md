# Reviewing figures

Use a reviewer with fresh context for any batch of 5 or more final figures, and for any figure 1 or non-standard plot.
The reviewer must not see the plotting code or the conversation first; a reader only sees the image.

## Dispatch

Give the reviewer, for each figure: the PNG path(s), the medium (paper, blog, slide), and the one sentence the figure
is meant to make obvious. Ask for this, in order:

1. Without reading the intended sentence: what does the figure say? One sentence per figure.
2. Compare with the intended sentence. Mismatch means the figure fails, whatever else is right.
3. Defects, each with the figure name and a concrete fix:
   - Text that is clipped, overlapping or too small at the target display width.
   - Intervals or markers whose meaning is not stated, or claims the intervals do not support.
   - Axes stretched by an outlier or a wide whisker; zero included or excluded wrongly; missing units.
   - Colors hard to tell apart, inconsistent across figures, or not matching the medium's theme.
   - Anything decorative that carries no information, and any explanation that a better plot would make unnecessary.
   - A non-standard plot where a standard one would say the same thing.
4. The single change that would most improve the batch.

The reviewer reads every image with the Read tool. Treat its findings like code review: fix what is right, push back
on what is not, then re-render and look again.

## Batches of exploratory plots

Exploratory plots do not need a reviewer. Do look at every one yourself, and when a plot shows something surprising,
check the data before trusting the plot: a surprising plot is more often a bug than a finding.
