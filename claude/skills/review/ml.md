# ML reviewer

Question: is the ML here sane? You are looking for mistakes that make results wrong or misleading, not for
every possible improvement.

Examples of what to check (not exhaustive):

- Leakage: target or future information in features; preprocessing, scaling, imputation, feature selection or
  target encoding fit on data that includes the evaluation set; duplicates or the same entity across splits;
  random splits on time-ordered or grouped data.
- Evaluation: a clean holdout that was not used for tuning or early stopping; metrics that fit the problem and
  class balance; a baseline to compare against; results reported on the right split; enough eval data for the
  claimed differences.
- Overfitting and selection: many configurations tried and the best one reported on the same data; seed
  cherry-picking; no variance across seeds or folds.
- Hyperparameters: values that look wrong for the setting (learning rate, batch size, regularization, tree
  depth, epochs), defaults that are known to be poor here, schedules that never take effect.
- Training mechanics: loss and output activation mismatch, wrong label encoding, train/eval mode, gradient
  handling, shuffling, class weighting, data loader and augmentation bugs.
- Reproducibility: seeds, data versions and configs recorded so the result can be reproduced.

Flag what would change a conclusion or a decision.
