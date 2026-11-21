# Large data and slow cells

These rules add detail to the "Large data and slow cells" section of the notebooks skill; that section still applies.

## Memory

The lazy scan puts column selection, row filters and downcasts in the plan and collects with the streaming engine:

```python
window = (
    pl.scan_parquet(path)
    .select([*feature_cols, "event_ts"])
    .filter(pl.col("event_ts") >= window_start)
    .with_columns(pl.col(float_feature_cols).cast(pl.Float32))
    .collect(engine="streaming")
)
```

- Where the code already uses pandas, pass `columns=` and `filters=` to `read_parquet` for the column and row pushdown a lazy scan gets.
- Scan once per split, with that split's filter in the scan.
- Readers keep the file's types, so downcast in the plan: Float32 for model features, Int32, Int16 or Int8 for counts and codes whose range you checked, Boolean for flags, Categorical or Enum for repeated strings. A cast in the plan shrinks the frame you keep; only the streaming engine also lowers the collect's own peak. Keep Float64 for money that can exceed about $131,000, where Float32 stops resolving cents, and cast to Float64 inside a sum over many rows. Keep the dtype map in one module, and make it raise on a column the data lacks.
- Leave string and JSON columns out unless a later step reads them; they grow several-fold when materialized.
- Stream file-to-file transforms with `sink_parquet` instead of collecting the whole frame. When several cells read one large source, sink its slim version once and scan that.
- Take row counts, null counts and min/max from the parquet footer (`pyarrow.parquet.read_metadata`); a missing statistic means unknown, not zero.
- Run high-cardinality aggregates (`n_unique`, a `group_by` with many keys) on their own instead of dozens of aggregates in one collect.

## Speed

Set thread counts before the first import of a native library (NumPy, Polars, BLAS): in the environment that launches the kernel or script, in a Jupyter notebook's first cell, or in marimo's setup cell (`with app.setup:`). A marimo notebook run as `python notebook.py` imports NumPy, through matplotlib when it is installed, before its first ordinary cell, and an environment variable set after a library loads does nothing.

- Write row-wise logic as dataframe or NumPy expressions. For an expensive per-value transform, compute it on the unique values and join back. `.to_list()` followed by a loop is still per-row Python, and so is `map_elements`.
- Batch at file level with one `group_by().agg()` instead of many small per-partition calls, and use Numba for genuinely sequential logic.
- Profile before optimizing, on full-size data: `.collect()` inside a loop and per-element Series indexing are the usual culprits.
