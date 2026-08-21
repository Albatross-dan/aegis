"""
Feature computation job (Doc 06 SS5, Doc 09 Phase 2).

Reads OHLC candles from the candles_1m continuous aggregate and computes
technical indicators (SMA, EMA, RSI, ATR), upserting results into
technical_features. Safe to re-run repeatedly - unique constraint on
(symbol, bucket) prevents duplicates.
"""
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.logging_config import logger

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"]

SMA_PERIOD = 20
EMA_PERIOD = 20
RSI_PERIOD = 14
ATR_PERIOD = 14

# Need enough history for the longest lookback (SMA/EMA 20), plus buffer
CANDLE_LOOKBACK = 100


def fetch_candles(db: Session, symbol: str) -> pd.DataFrame:
    result = db.execute(
        text("""
            SELECT bucket, open, high, low, close
            FROM candles_1m
            WHERE symbol = :symbol
            ORDER BY bucket DESC
            LIMIT :lookback
        """),
        {"symbol": symbol, "lookback": CANDLE_LOOKBACK},
    )
    rows = result.fetchall()
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["bucket", "open", "high", "low", "close"])
    df = df.sort_values("bucket").reset_index(drop=True)
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df["sma_20"] = df["close"].rolling(window=SMA_PERIOD).mean()
    df["ema_20"] = df["close"].ewm(span=EMA_PERIOD, adjust=False, min_periods=EMA_PERIOD).mean()

    # RSI (Wilder's smoothing)
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # ATR (true range, Wilder's smoothing)
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.ewm(alpha=1 / ATR_PERIOD, adjust=False).mean()

    return df


def upsert_features(db: Session, symbol: str, df: pd.DataFrame):
    now = datetime.now(timezone.utc)
    written = 0

    for _, row in df.iterrows():
        # Skip rows with no computed indicators at all (not enough history yet)
        if pd.isna(row["sma_20"]) and pd.isna(row["rsi_14"]):
            continue

        db.execute(
            text("""
                INSERT INTO technical_features
                    (symbol, bucket, sma_20, ema_20, rsi_14, atr_14, computed_at)
                VALUES
                    (:symbol, :bucket, :sma_20, :ema_20, :rsi_14, :atr_14, :computed_at)
                ON CONFLICT (symbol, bucket)
                DO UPDATE SET
                    sma_20 = EXCLUDED.sma_20,
                    ema_20 = EXCLUDED.ema_20,
                    rsi_14 = EXCLUDED.rsi_14,
                    atr_14 = EXCLUDED.atr_14,
                    computed_at = EXCLUDED.computed_at
            """),
            {
                "symbol": symbol,
                "bucket": row["bucket"],
                "sma_20": None if pd.isna(row["sma_20"]) else float(row["sma_20"]),
                "ema_20": None if pd.isna(row["ema_20"]) else float(row["ema_20"]),
                "rsi_14": None if pd.isna(row["rsi_14"]) else float(row["rsi_14"]),
                "atr_14": None if pd.isna(row["atr_14"]) else float(row["atr_14"]),
                "computed_at": now,
            },
        )
        written += 1

    db.commit()
    return written


def run():
    db = SessionLocal()
    try:
        for symbol in SYMBOLS:
            df = fetch_candles(db, symbol)
            if df.empty:
                logger.info(f"[features] No candle data for {symbol}, skipping")
                continue

            df = compute_indicators(df)
            written = upsert_features(db, symbol, df)
            logger.info(f"[features] {symbol}: {written} rows upserted")
    finally:
        db.close()


if __name__ == "__main__":
    run()
