---
name: notebooks
description: Use when creating, editing, reviewing or running a Jupyter or marimo notebook for data analysis or research; before a long or multi-notebook run ("run the pipeline", "re-run from notebook 3"); when asked whether a notebook is ready to share or shown its results; or when a notebook cell runs out of memory or is slow on a large dataframe or parquet dataset.
---

# Notebooks

A research notebook displays an analysis. A reader, person or agent, follows it top to bottom as named steps and trusts that every output and number came from the current code, run in order, on all the data. Logic lives in modules; cells orchestrate, display and interpret.

Prose in markdown cells follows `write-plainly`, and figures follow `visualization`. In marimo, reactive execution re-runs a cell's dependents, a cell shows its last expression (more with `mo.output.append`), a plot cell ends with the figure rather than `plt.show()`, and the `.py` file saves no outputs; the IPython, `pl.Config` and batch-runner rules below do not apply.

## Never shrink the data to make a cell finish

Never add `.sample()`, `.head()`, `[:N]` or any other row reduction to a computation to get past an out-of-memory error or a slow cell: results computed on a subset read as full-data results. Fix the plan ("Large data") or tell the user and let them decide; note an approved reduction in a comment beside it. Check for reductions earlier edits inserted, too. A short preview in a display cell is fine.

## Structure

- Open with a markdown cell that states the question, the data (source, population, time window) and where the headline result is.
- Keep each cell to a few named steps. Move substantial logic (more than about 20 lines of transforms, estimation or plotting) into an importable module, or into a helpers cell when it is display-only and one-off. Prefer many small named helpers to one `run_everything(df, a, b, c, ...)` call, which hides the steps instead of showing them:

  ```python
  effects = estimate_effects(sessions, covariates)
  policies = rank_policies(effects, budgets)
  summary = evaluate_policies(policies, logged_outcomes)
  ```

- When new work varies something already in the notebook (another estimator, a wider sweep, a re-cut chart), extend that section; search the notebook before adding a cell. Put genuinely new work where it belongs in the argument (headline, then support, then detail), not at the end.
- Seed every random step, use repo-relative paths, and import constants (column names, thresholds, paths) from the project's config module.
- Assert the facts a frame must satisfy (unique keys, row counts kept across a join, no nulls in a key) in the cell that builds it.

## Outputs

- Follow every figure and table with markdown that says what it shows and what it means for the question. When a code change changes an output, update that markdown in the same edit.
- Never type a result into markdown. Render tables as DataFrames, print inline numbers from the result objects (`print(f"lift {res.lift:.1%}, 95% CI [{res.lo:.1%}, {res.hi:.1%}]")`), and assert any claim the prose depends on, such as a sign or an ordering, in the cell that computes it. Markdown says what a result means; code says what it is.
- Open each section with its headline figure and put breakdowns (per segment, per fold) after it. Say how a pooled headline is weighted.
- `display()` every frame: only a cell's last bare expression renders, and IPython's output cache keeps that object alive after `del`. Show each matplotlib figure once, with `plt.show()`. Use `print()` for diagnostics.
- Preview a few rows of the columns you need. Show a finding table (every candidate, every audit row, neutral and negative results included) in full, raising the renderer's row limit (`pl.Config.set_tbl_rows`) instead of filtering.
- Format for reading: round each metric to the precision it needs (a global three decimals shows 0.0004 as 0.000), cast integer-valued floats to integers, and shorten column names.
- Keep the saved file small, since every reader loads it: cap figure sizes in helpers that scale with the data, and put per-iteration logs behind a verbosity flag.

## Running

- After editing a cell, re-run it and every cell that depends on it before reading later outputs; the kernel still holds the old state. After editing an imported module, reload it or restart.
- Before calling a notebook done or sharing it, restart and run it top to bottom, so the saved outputs come from the current code.
- Run a long job you may still adjust in a live kernel you can address, so a late-cell fix re-runs against in-memory state. Use a fresh-kernel batch runner (papermill, nbconvert, nbclient) for runs you will not touch; a run whose expensive cells have not finished is cheap to restart.
- Never edit a notebook while a run that saves it is in flight; the run writes back the copy it loaded.
- Set thread counts before the first import of a native library (NumPy, Polars, BLAS), in the environment or the first cell; an environment variable set later does nothing.
- A tool's timeout on a live kernel does not stop the cell; check whether it is still running before you run it again.
- Run a pipeline of notebooks in its documented order (ask which ones if not told), each in a fresh kernel that you stop before starting the next. Check that each output exists, has a plausible row count and was written by this run (its modification time).
- Before a big run, list the kernels earlier runs or editors left holding memory, and read the list before killing any: another session's run may be on it. Confirm a suspected out-of-memory kill in the operating system log (`dmesg`, `journalctl -k`), since a tool can report a dead kernel as alive.

## Large data

An out-of-memory error means the code materializes something the answer does not need. Compare the step's peak memory with the bytes its needed columns take, and fix the plan before asking for a bigger machine. Every frame a cell binds stays in memory until deleted, so build large intermediates inside functions. On a shared machine, estimate the peak first and stay well under its RAM. The examples use Polars; with pandas, pass `columns=` and `filters=` to `read_parquet` for the same pushdown.

- Put column selection and row filters in the lazy scan, and scan once per split with that split's filter:

  ```python
  window = (
      pl.scan_parquet(path)
      .select([*feature_cols, "event_ts"])
      .filter(pl.col("event_ts") >= window_start)
      .with_columns(pl.col(float_feature_cols).cast(pl.Float32))
      .collect(engine="streaming")
  )
  ```

- Readers keep the file's types, so downcast in the plan: Float32 for model features, Int32, Int16 or Int8 for counts and codes whose range you checked, Boolean for flags, Categorical or Enum for repeated strings. A cast in the plan shrinks the frame you keep; only the streaming engine also lowers the collect's own peak. Keep Float64 for money that can exceed about $131,000, where Float32 stops resolving cents, and cast to Float64 inside a sum over many rows. Keep the dtype map in one module, and make it raise on a column the data lacks.
- Leave string and JSON columns out unless a later step reads them; they grow several-fold when materialized.
- Stream file-to-file transforms with `sink_parquet` instead of collecting the whole frame. When several cells read one large source, sink its slim version once and scan that.
- Take row counts, null counts and min/max from the parquet footer (`pyarrow.parquet.read_metadata`); a missing statistic means unknown, not zero. Run high-cardinality aggregates (`n_unique`, a `group_by` with many keys) on their own instead of dozens of aggregates in one collect.
- Write row-wise logic as dataframe or NumPy expressions. For an expensive per-value transform, compute it on the unique values and join back. `.to_list()` followed by a loop is still per-row Python, and so is `map_elements`. Batch at file level with one `group_by().agg()` instead of many small per-partition calls, and use Numba for genuinely sequential logic.
- Profile before optimizing, on full-size data: `.collect()` inside a loop and per-element Series indexing are the usual culprits.

## Reviewing a notebook

Review before an expensive run (when asked to run one, review it first) and before a notebook is shared. Read every cell, code and markdown, against the rules above, and add these checks:

- Every number in prose matches the output it cites, and a statistic shown twice agrees.
- The saved outputs could have come from the current code.
- The notebook follows its siblings' imports, display conventions, colors and names.

Report each finding as cell, problem, fix, and when the fix must land: before the run (it changes what is computed or how the code is structured) or before sharing (markdown and display only). When asked only to review, report; when asked to run, land every before-run fix first.
