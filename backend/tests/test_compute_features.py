from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd

from app.jobs.compute_features import compute_indicators


def make_candle_frame(rows: int = 25) -> pd.DataFrame:
    start = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    buckets = [start + timedelta(minutes=index) for index in range(rows)]
    closes = np.linspace(1.1000, 1.1240, rows)

    return pd.DataFrame(
        {
            "bucket": buckets,
            "open": closes - 0.0002,
            "high": closes + 0.0005,
            "low": closes - 0.0006,
            "close": closes,
        }
    )


def test_compute_indicators_creates_expected_indicator_columns():
    df = make_candle_frame()

    result = compute_indicators(df.copy())

    assert result.loc[:18, "sma_20"].isna().all()
    assert result.loc[19:, "sma_20"].notna().all()

    assert result.loc[:18, "ema_20"].isna().all()
    assert result.loc[19:, "ema_20"].notna().all()

    non_nan_rsi = result["rsi_14"].dropna()
    assert not non_nan_rsi.empty
    assert non_nan_rsi.between(0, 100).all()

    non_nan_atr = result["atr_14"].dropna()
    assert not non_nan_atr.empty
    assert (non_nan_atr >= 0).all()