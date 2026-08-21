# F2 Confidence Validation (Trend AI)

This document defines the baseline, repeatable confidence audit for `trend_ai_v2`.

## Objective

Validate whether reported confidence aligns with realized directional accuracy over historical data.

## Method

For each recommendation (`buy`/`sell`/`hold`) from `ai_recommendations`:

1. Pair recommendation bucket with the current `candles_1m.close`.
2. Pair again with `candles_1m.close` at `bucket + horizon_minutes` (default 3).
3. Infer observed direction:
   - `buy` if `future_close > now_close`
   - `sell` if `future_close < now_close`
   - `hold` if unchanged
4. Score recommendation as correct when `predicted_direction == observed_direction`.
5. Aggregate by confidence deciles (`0.0-0.1`, ..., `0.9-1.0`) and compare:
   - `accuracy` per decile
   - `avg_confidence` per decile
   - directional subset quality (`buy`/`sell` only): `directional_sample_size`, `directional_accuracy`

## Run

From `backend/` with venv active:

```bash
python -m app.jobs.trend_confidence_audit
```

Optional parameters:

```bash
python -m app.jobs.trend_confidence_audit --model-version trend_ai_v2 --lookback-days 30 --horizon-minutes 3
python -m app.jobs.trend_confidence_audit --model-version all
```

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