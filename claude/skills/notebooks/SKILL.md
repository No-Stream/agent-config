---
name: notebooks
description: Use when creating, editing, reviewing or running a Jupyter or marimo notebook for data analysis or research; before a long or multi-notebook run or a re-run after an upstream change ("run the pipeline", "re-run from notebook 3", "refresh the notebooks"); when asked whether a notebook is ready to share or shown its results; or when a notebook cell or run is slow or runs out of memory on a large dataframe or parquet dataset.
---

# Notebooks

A research notebook displays an analysis. A reader, person or agent, follows it top to bottom as named steps and trusts that every output and number came from the code it shows, run in order, on all the data. Logic lives in modules; cells orchestrate, display and interpret.

Prose in markdown cells follows `write-plainly`, and figures follow `visualization`. In marimo, reactive execution re-runs a cell's dependents (or marks them stale in lazy mode), a cell shows its last expression (more with `mo.output.append`), a plot cell ends with the figure rather than `plt.show()`, and the `.py` file saves no outputs; the IPython, `pl.Config` and batch-runner rules below do not apply.

## Never shrink the data or the analysis to make a cell finish

Never add `.sample()`, `.head()`, `[:N]` or any other row reduction to get past an out-of-memory error or a slow cell: results computed on a subset read as full-data results. Never drop an estimator, arm, outcome window or section to save time either, or run a simulation below the scale its question is about. Fix the cause or ask first, note an approved reduction beside it, and check for reductions earlier edits inserted. Fine without asking: a display preview, a smoke run on a small slice whose numbers are never reported, pulling more data, and only as many simulation replications as the question needs.

## Structure

- Open with a markdown cell that states the question, the data (source, population, time window, pull date), the result's status (final, interim, simulated, at what scale) and where the main results are.
- Before the first result, define each method, model or arm compared in a plain sentence, by the field's standard name where one exists.
- Keep one population, unit, outcome window and estimator throughout; a section that changes one says so first.
- Keep each cell to a few named steps, not one `run_everything(...)` call that hides them. Move substantial logic (more than about 20 lines of transforms, estimation or plotting) into an importable module, or into a helpers cell when it is display-only and one-off. Fix a library you own rather than work around it in a cell.
- When new work varies something already in the notebook (another estimator, a wider sweep, a re-cut chart), extend that section; search the notebook before adding a cell. Put other new work where it belongs in the argument (main result, then support, then detail), not at the end. Replace what a change supersedes, drop debugging outputs once their bug is fixed, and when patches pile up, rebuild the notebook from an outline.
- A notebook that replaces or summarizes earlier ones carries every analysis of theirs the question needs: read them all, reuse their code, and list what you leave out.
- Seed every random step, use repo-relative paths, and import column names, thresholds and paths from the project's config module.
- Assert the facts a frame must satisfy (unique keys, row counts kept across a join, no nulls in a key, covariates dated before treatment) in the cell that builds it.

## Outputs

- Follow every figure and table with one or two plain sentences on what it shows and means for the question, quoting only the numbers the claim needs. Give an effect as an estimate with its interval in the reader's units, never a verdict: no pass or fail, no winner where intervals overlap, no "no effect" from an underpowered read. Asked for a winner the data cannot name, say so and why, name the leader as a labelled best guess, and say what would settle it. When an output changes, check its markdown against it and fix what no longer holds.
- Never type a result, or the estimator, window or model behind it, into markdown or a figure title. Render tables as DataFrames, print inline numbers from the result objects (`print(f"lift {res.lift:.1%}, 95% CI [{res.lo:.1%}, {res.hi:.1%}]")`), and assert any claim the prose depends on, such as a sign or an ordering, in the cell that computes it.
- Open each section with the figure for its core comparison, then breakdowns (per segment, per fold); ablations and diagnostics go after them or in an appendix. Say how a pooled result is weighted.
- `display()` every frame: only a cell's last bare expression renders, and IPython's output cache keeps that object alive after `del`. Show each matplotlib figure once, with `plt.show()`.
- Preview a few rows of the columns you need. Show each finding as a figure, with its table after it in full (every candidate, neutral and negative results included), raising the renderer's row limit (`pl.Config.set_tbl_rows`) instead of filtering.
- Format for reading: round each metric to the precision it needs (a global three decimals shows 0.0004 as 0.000), cast integer-valued floats to integers, and name columns in plain words with units, not abbreviations or labels coined during the work.
- Keep the saved file small: cap figure sizes that scale with the data, and put per-iteration logs behind a verbosity flag.

## Running

- After editing a cell, re-run it and every cell that depends on it, or restart and run all, before reading later outputs or calling the notebook done; the kernel still holds the old state. After editing an imported module, reload it or restart.
- Leave a finished notebook as it is when upstream code changes, unless the change could move a conclusion; practically identical results count as identical.
- Run a long job you may still adjust in a live kernel you can address, so a late-cell fix re-runs against in-memory state. Use a fresh-kernel batch runner (papermill, nbconvert, nbclient) for runs you will not touch; a run whose expensive cells have not finished is cheap to restart.
- Before a long run of changed code, smoke-run the changed cells on a small slice or review them.
- Never edit a notebook while a run that saves it is in flight; the run writes back the copy it loaded.
- A tool's timeout on a live kernel does not stop the cell; check it before running it again.
- Run a pipeline of notebooks in its documented order (ask which ones if not told), each in a fresh kernel that you stop before starting the next. Check that each output exists, has a plausible row count and was written by this run.
- Before a big run, list kernels left holding memory, and check whose they are before killing any. Confirm a suspected out-of-memory kill in the system log (`dmesg`), since a tool can report a dead kernel as alive.

## Large data and slow cells

An out-of-memory error means the code materializes something the answer does not need. Compare the step's peak memory with the bytes its needed columns take, and fix the plan before asking for a bigger machine. Every frame a cell binds stays in memory until deleted, so build large intermediates inside functions. On a shared machine, estimate the peak first and stay well under its RAM. Use Polars for new work and keep pandas only where the code already uses it. Put column selection, row filters and downcasts in the lazy scan:

```python
window = (
    pl.scan_parquet(path)
    .select([*feature_cols, "event_ts"])
    .filter(pl.col("event_ts") >= window_start)
    .with_columns(pl.col(float_feature_cols).cast(pl.Float32))
    .collect(engine="streaming")
)
```

A slow cell usually runs Python per row or calls `.collect()` in a loop. Run independent fits in parallel, with workers times threads under the physical core count and headroom on a shared machine. A step on one core of many, or a run far past its estimate, is a defect: profile and fix it instead of waiting. Before fixing a large or slow cell or setting thread counts, read this skill's `large-data.md`.

## Reviewing a notebook

Review before an expensive run (when asked to run one, review it first) and before sharing. Read every cell, code and markdown, against the rules above, plus:

- Every number in prose matches the output it cites, and a statistic shown twice agrees.
- Main results are plausible against earlier runs and known results, and every change since the last run, NaN in a result, too-exact match to a target or apparent contradiction is explained.
- Every rendered figure was opened after the latest run and checked per `visualization`, and each reported fix shows in it.
- The saved outputs could have come from the current code, or the gap could not move a conclusion.
- The notebook follows its siblings' imports, display conventions, colors and names.

Report each finding as cell, problem, fix, and when the fix must land: before the run (it changes what is computed or the code's structure) or before sharing (markdown and display only). When asked only to review, report; when asked to run, land every before-run fix first.
