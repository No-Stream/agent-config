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
  surprising results hardest (see Surprising results below).
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
- **Pre- vs post-hoc**: was the result predicted before it was seen? Exploration is fine, but a result picked from
  many variants (prompts, configurations, metrics, layers) is weaker evidence until it is confirmed on fresh samples or
  a held-out split. Count roughly how many variants were tried. When more data is cheap, confirmation replaces
  pre-registration; when it is not, say the result is post-hoc.
- **Independence of evidence**: several qualitatively different lines of evidence beat many near-duplicates. Ask how
  well result 1 predicts result 2.
- **Quality over quantity**: is there at least one compelling experiment that is hard to deny? Lead with it; move
  weaker ones down or out.
- **Domain controls**: apply the repo's standing controls (for example matched-norm placebos for steering, eval
  awareness rates).

## Surprising results

Surprising results are often wrong. Any result that surprised us, or that contradicts prior work or the field's
expectations, must clear these checks before it enters the ledger as *verified*. Ideally they happen during the
research, as part of code review; if not, do them now.

- **Rule out the obvious explanations first.** The usual causes are a bug in the pipeline, the wrong model, checkpoint
  or adapter loaded, stale cached results, a prompt-template or chat-format error, truncated outputs, an answer parser
  or judge that fails silently, swapped labels or conditions, and overlap between training and eval data.
- **Read raw samples** from each condition, not only the aggregate. Many errors are obvious in ten transcripts.
- **Run the controls that would expose an artefact**: a null or placebo condition (random direction, shuffled
  labels, unrelated fine-tune), a condition where a known effect should reproduce, and a check that the effect does
  not track a confound such as length or refusal rate.
- **Ask what the result would look like if it were an artefact**, and check that it does not look like that.

If these checks have not been done, say so in the audit report, mark the result *not checked*, and propose the checks
with their cost. A surprising result with no controls is at most a hedged claim.

## Citations

A light check, not a literature review. For each citation the argument leans on (prior results we build on, claims
about what other work found), a subagent finds the passage in the cited paper and records the section or page and a
short quote in the narrative file. If the paper says something weaker or different, narrow our wording or drop the
citation. Skip citations that only point to a method or a dataset.

## Output

A short audit report in the narrative file: each claim's evidence status (verified / mismatch / not checked),
the problems found, any narrowing of claims they force, and a proposed confidence and "what would change our mind"
for each claim. Then a list of the misconceptions or over-updates a reader is likely to make; these feed the
Limitations section.

## Distilling experiments

By the end of a project it is usually clear which experiment would be decisive. If a cleaner or larger version of the
key experiment is feasible, propose it with its cost. Scaling up (more models, seeds, data) is a proposal for the
owner, not something to run unasked.
