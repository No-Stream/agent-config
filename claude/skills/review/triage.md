# Triage

You receive a batch of related findings from parallel reviewers (Claude and Codex, several domains). Some are
real, some are wrong, some are real but not worth fixing. Your job: verify each against the code, decide its
priority, and propose a concrete fix.

Read-only: do not run code, tests or builds. The batch is in your task prompt. Read `scope.md` in the review
bundle, and the code each finding points to, with enough context to judge it.

## For each finding

1. **Verify.** Read the cited code and check the claim. `confirmed`: you can see the problem. `plausible`: the
   reasoning holds but depends on something you cannot confirm by reading. `rejected`: the claim is wrong, the
   scenario cannot happen, or the code already handles it. Say why in one or two sentences.
2. **Prioritize.**
   - `fix`: confirmed or plausible, and leaving it causes wrong results, crashes on realistic paths, missing
     required functionality, or clear structural damage.
   - `worth fixing`: real, and the fix makes the code better at a cost that pays for itself.
   - `deprioritized`: real but fixing it would be counterproductive or not worth it. Typical cases: guarding an
     extremely rare or impossible edge case, where the guard adds branching and makes the code harder to read;
     speculative generality; a nit whose fix is churn. Failing loudly on a truly rare case is acceptable.
   - `rejected`: not real.
3. **Propose the fix** for `fix` and `worth fixing`: the concrete change, with a short snippet when it helps.
   Prefer the fix that deletes complexity over one that adds a guard. If findings in the batch share a root
   cause, propose one fix and point the others at it.

Severity from the reviewer is a hint; reassess it. Agreement between a Claude and a Codex reviewer is evidence,
not proof.

## Output

Return every finding id in the batch through the structured-output tool, with: the claim (corrected if the
reviewer's wording was off), locations, verdict and why, priority and why (always explain a deprioritization),
your reassessed severity, and the fix (or "none").
