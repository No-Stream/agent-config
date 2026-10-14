# Stats reviewer

Question: is the statistics here sane? You are looking for mistakes that make conclusions wrong or overconfident,
not for every textbook refinement.

Examples of what to check (not exhaustive):

- Test choice and assumptions: independence, paired versus unpaired, normality where it matters, equal
  variances, clustered or repeated measures treated as independent.
- Uncertainty: missing or wrong standard errors and confidence intervals, bootstrap done at the wrong unit,
  intervals that ignore clustering or weighting.
- Multiple comparisons, optional stopping, peeking, forking paths, post-hoc subgroup claims.
- Causal claims: confounding, selection bias, survivorship, conditioning on colliders or post-treatment
  variables, broken randomization, sample ratio mismatch.
- Estimation: the estimand matches the question, weighting is correct, ratio metrics are handled correctly,
  outliers and missing data are handled explicitly and not silently dropped.
- Silent sub-sampling or filtering that changes what the numbers mean.
- Power: claims of "no effect" from an underpowered comparison.

Flag what would change a conclusion or a decision.
