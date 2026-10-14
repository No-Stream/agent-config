# Evidence audit and red-teaming

Do this before drafting, and again on the finished draft. Many published papers are wrong or badly misleading; the
audit is how a draft avoids being one of them. A good narrative makes it tempting to ignore inconvenient results. The
audit is the counterweight.

## Re-derive the key numbers

For every result that supports a claim, dispatch a subagent to re-derive it from the raw artifacts (traces, eval
records, logs), not from summaries or earlier notes. Aim to verify every key result and at least 75% of the rest.
Where cheap, re-compute through a different code path. Report mismatches before writing.

If only notes or summaries exist, check them for internal consistency instead (per-seed values against the mean,
subsets against the total, intervals against the reported spread), mark those results *notes only* in the ledger, and
keep drafting. A *notes only* result can appear in the draft, but the report must list it as unverified. If a rerun would settle a
question, propose it with its cost; do not launch paid or long compute without the owner's approval.

## Questions per claim

Assume a mistake exists, and look for it.

- **Bugs**: How surprised would I be if this turned out to be a bug, a judge error or a data leak? Check the most
  surprising results hardest.
- **Noise**: Sample size, seeds, standard error. Is the effect clearly larger than run-to-run variation?
- **Statistics**: for frequentist tests, treat p < 0.05 as weak. Want p < 0.01 for a confirmatory result and
  p < 0.001 for one found while exploring many hypotheses. When no test was run, do the back-of-envelope version: a
  rate p on n items has standard error about sqrt(p(1-p)/n), the difference of two independent rates has standard
  error sqrt(SE1² + SE2²), and a difference under about 3 standard errors is suggestive at best. Seed-to-seed spread
  is often larger than this sampling error; use it when there are several seeds.
- **Both directions of the behaviour**: does the eval contain only cases where the target behaviour is wrong? Then a
  model that is simply more contrarian, more hedged or less coherent scores "better". A reduction needs a control set
  where the opposite behaviour would be the error.
- **Discriminating power**: Would this result look different if the main alternative explanation were true? A good
  experiment separates hypotheses.
- **Alternative explanations**: confounds such as length, formatting, judge bias, prompt artefacts. What else predicts
  the same result?
- **Could the evidence be true and the claim false?** How?
- **Baselines**: Is there one? Is it the strongest reasonable alternative, tuned with comparable effort to the new
  method? An untuned baseline supports "X works at all", not "X is better".
- **Ablations**: for a method with several changes, does each change earn its place?
- **Cherry-picking**: are qualitative examples representative? Give random examples alongside chosen ones, or say how
  they were chosen. Existence-proof claims are the exception: one trustworthy example suffices.
- **Pre- vs post-hoc**: was the result predicted before it was seen? Post-hoc fits are weaker evidence; say which is
  which.
- **Independence of evidence**: several qualitatively different lines of evidence beat many near-duplicates. Ask how
  well result 1 predicts result 2.
- **Quality over quantity**: is there at least one compelling experiment that is hard to deny? Lead with it; move
  weaker ones down or out.
- **Domain controls**: apply the repo's standing controls (for example matched-norm placebos for steering, eval
  awareness rates).

## Output

A short audit report in the narrative file: each claim's evidence status (verified / mismatch / not checked),
the problems found, and any narrowing of claims they force. Then a list of the misconceptions or over-updates a reader
is likely to make; these feed the Limitations section.

## Distilling experiments

By the end of a project it is usually clear which experiment would be decisive. If a cleaner or larger version of the
key experiment is feasible, propose it with its cost. Scaling up (more models, seeds, data) is a proposal for the
owner, not something to run unasked.
