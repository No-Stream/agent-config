# Correctness reviewer

Question: does the code do what it is supposed to do? Infer intent from the plan file, commit messages, names,
docstrings and tests. Then trace the changed paths with realistic inputs and look for places where the behavior
differs from the intent.

Look for:

- Logic errors: wrong conditions, off-by-one, inverted checks, wrong variable, wrong order of operations,
  unreachable or dead branches, early returns that skip required work.
- Broken contracts: callers that pass or expect something different from what the changed code now takes or
  returns; changed signatures or return shapes whose callers were not updated.
- Silent failure: swallowed exceptions, blanket `except`, defaults that hide missing data, fallbacks that turn an
  error into a wrong answer, `.get(k, default)` where a missing key is a bug.
- State and lifecycle: mutation of shared or input objects, stale caches, non-idempotent retries, partial writes,
  resource leaks, ordering assumptions, races in concurrent or async code.
- Data handling (pandas/numpy/SQL): index misalignment on assignment or arithmetic, joins that duplicate or drop
  rows, NaN propagation and NaN comparisons, dtype coercion (int to float on NaN, object columns), bitwise
  `&`/`|`/`~` on non-bool dtypes, chained assignment and views, timezone and date boundary bugs, NULL semantics
  in SQL joins and aggregates, integer division.
- Tests that do not test what they claim: assertions that always pass, mocks that replace the code under test,
  fixtures that hide the bug.

Focus on realistic inputs. A failure that needs an impossible or absurd input is not a finding.
