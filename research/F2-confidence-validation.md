# F2 Confidence Validation (Trend AI)

This document defines the baseline, repeatable confidence audit for `trend_ai_v2`.

## Objective

Validate whether reported confidence aligns with realized directional accuracy over historical data.

3. Infer observed direction:
   - `buy` if `future_close > now_close`
   - `sell` if `future_close < now_close`
   - `accuracy` per decile
   - `avg_confidence` per decile
   - directional subset quality (`buy`/`sell` only): `directional_sample_size`, `directional_accuracy`

Use [docs/ops/phase5-research-registry.md](../docs/ops/phase5-research-registry.md) to store the readiness snapshot or later backtest runs.

```bash
python -m app.jobs.trend_confidence_audit
```

Optional parameters:

```bash
python -m app.jobs.trend_confidence_audit --model-version trend_ai_v2 --lookback-days 30 --horizon-minutes 3
python -m app.jobs.trend_confidence_audit --model-version all
```

Readiness check:

```bash
python -m app.jobs.trend_confidence_readiness --model-version trend_ai_v2
```

This should report `ready: true` only when the v2 history has at least the configured number of distinct buckets and completed horizon samples.

When scheduled via cron, the recommended log target is `backend/logs/confidence_readiness.log`.

When the forex market is closed, the readiness check will report a deferred state instead of a hard failure.

## Output

The job prints JSON with:

- `summary.total_samples`
- `summary.overall_accuracy`
- `summary.overall_avg_confidence`
- `summary.directional_samples`
- `summary.overall_directional_accuracy`
- `bins[]` containing `confidence_bin`, `sample_size`, `accuracy`, `avg_confidence`

## Interpretation

- Well-calibrated behavior: higher bins should generally have higher observed accuracy.
- Overconfidence: `avg_confidence` consistently above corresponding bin accuracy.
- Underconfidence: `avg_confidence` consistently below corresponding bin accuracy.

## Notes

- Includes all predictions for full calibration visibility and separately reports directional-only quality metrics.
- Empty or sparse output indicates insufficient paired candle history for the chosen lookback/horizon.
- If the readiness check is not ready, wait for more `trend_ai_v2` buckets to accumulate and re-run the same audit.
- If the readiness check is deferred because the market is closed, rerun it after the next market-open candle sequence is available.