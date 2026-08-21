"""
Trend Intelligence AI (Doc 05 SS5).

Mission: determine the dominant market trend using EMA/SMA structure.
Produces independent recommendations per Doc 04 SS7 - direction, confidence,
evidence, explanation. Does not communicate with other experts (Doc 05 SS4).
"""
from datetime import datetime, timezone
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.db.session import SessionLocal

MODEL_VERSION = "trend_ai_v2"
EXPERT_NAME = "trend_ai"
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"]

CONFIRMATION_WINDOW = 5
MIN_AGREEING_CANDLES = 4
LOW_CONFIDENCE_DEFAULT = 0.1


def fetch_recent_features(db: Session, symbol: str):
    result = db.execute(
        text("""
            SELECT bucket, close, sma_20, ema_20, atr_14
            FROM (
                SELECT
                    tf.bucket,
                    c.close,
                    tf.sma_20,
                    tf.ema_20,
                    tf.atr_14
                FROM technical_features tf
                JOIN candles_1m c ON c.symbol = tf.symbol AND c.bucket = tf.bucket
                WHERE tf.symbol = :symbol
                ORDER BY tf.bucket DESC
                LIMIT :window_size
            ) recent
            ORDER BY bucket ASC
        """),
        {"symbol": symbol, "window_size": CONFIRMATION_WINDOW},
    )
    return result.mappings().all()


def classify_candle(candle: dict) -> str:
    close = candle["close"]
    sma = candle["sma_20"]
    ema = candle["ema_20"]

    if close is None or sma is None or ema is None:
        return "hold"

    if close > ema > sma:
        return "buy"

    if close < ema < sma:
        return "sell"

    return "hold"


def serialize_bucket(bucket) -> str:
    if hasattr(bucket, "isoformat"):
        return bucket.isoformat()

    return str(bucket)


def compute_magnitude(close, sma, atr) -> float:
    if close is None or sma is None or atr is None or atr == 0:
        return 0.1

    magnitude = abs(close - sma) / atr
    return min(magnitude, 1.0)


def build_insufficient_history_result(candles: list[dict]) -> dict:
    latest = candles[-1] if candles else {}
    classifications = [classify_candle(candle) for candle in candles]

    evidence = {
        "window_size": CONFIRMATION_WINDOW,
        "classifications": [
            {"bucket": serialize_bucket(candle["bucket"]), "classification": classification}
            for candle, classification in zip(candles, classifications)
        ],
        "buy_count": classifications.count("buy"),
        "sell_count": classifications.count("sell"),
        "persistence": 0.0,
        "magnitude": 0.1,
        "latest_close": latest.get("close"),
        "latest_sma_20": latest.get("sma_20"),
        "latest_ema_20": latest.get("ema_20"),
        "latest_atr_14": latest.get("atr_14"),
    }

    return {
        "direction": "hold",
        "confidence": LOW_CONFIDENCE_DEFAULT,
        "evidence": evidence,
        "explanation": "Insufficient history to confirm a trend across 5 candles; defaulting to hold with low confidence.",
    }


def analyze(candles: list[dict]) -> dict:
    if len(candles) < CONFIRMATION_WINDOW:
        return build_insufficient_history_result(candles)

    latest = candles[-1]
    latest_close = latest["close"]
    latest_sma = latest["sma_20"]
    latest_ema = latest["ema_20"]
    latest_atr = latest["atr_14"]

    if latest_sma is None or latest_ema is None:
        return build_insufficient_history_result(candles)

    classifications = [classify_candle(candle) for candle in candles]
    buy_count = classifications.count("buy")
    sell_count = classifications.count("sell")
    hold_count = classifications.count("hold")

    signal_count = max(buy_count, sell_count)

    if buy_count >= MIN_AGREEING_CANDLES:
        direction = "buy"
        agreeing_count = buy_count
        explanation = (
            f"Bullish trend confirmed: {buy_count} of {CONFIRMATION_WINDOW} candles agreed on buy structure."
        )
    elif sell_count >= MIN_AGREEING_CANDLES:
        direction = "sell"
        agreeing_count = sell_count
        explanation = (
            f"Bearish trend confirmed: {sell_count} of {CONFIRMATION_WINDOW} candles agreed on sell structure."
        )
    else:
        direction = "hold"
        agreeing_count = signal_count
        explanation = (
            f"No consistent trend found: {buy_count} buy, {sell_count} sell, and {hold_count} hold candles "
            f"failed to reach the {MIN_AGREEING_CANDLES}-of-{CONFIRMATION_WINDOW} confirmation threshold."
        )

    persistence = agreeing_count / CONFIRMATION_WINDOW
    magnitude = compute_magnitude(latest_close, latest_sma, latest_atr)
    confidence = round((persistence * 0.6) + (magnitude * 0.4), 4)

    evidence = {
        "window_size": CONFIRMATION_WINDOW,
        "classifications": [
            {"bucket": serialize_bucket(candle["bucket"]), "classification": classification}
            for candle, classification in zip(candles, classifications)
        ],
        "buy_count": buy_count,
        "sell_count": sell_count,
        "persistence": round(persistence, 4),
        "magnitude": round(magnitude, 4),
        "latest_close": latest_close,
        "latest_sma_20": latest_sma,
        "latest_ema_20": latest_ema,
        "latest_atr_14": latest_atr,
    }

    return {
        "direction": direction,
        "confidence": confidence,
        "evidence": evidence,
        "explanation": explanation,
    }


def upsert_recommendation(db: Session, symbol: str, bucket, result: dict):
    now = datetime.now(timezone.utc)
    db.execute(
        text("""
            INSERT INTO ai_recommendations
                (symbol, bucket, expert_name, direction, confidence, evidence, explanation, model_version, computed_at)
            VALUES
                (:symbol, :bucket, :expert_name, :direction, :confidence, :evidence, :explanation, :model_version, :computed_at)
            ON CONFLICT (symbol, bucket, expert_name)
            DO UPDATE SET
                direction = EXCLUDED.direction,
                confidence = EXCLUDED.confidence,
                evidence = EXCLUDED.evidence,
                explanation = EXCLUDED.explanation,
                model_version = EXCLUDED.model_version,
                computed_at = EXCLUDED.computed_at
        """),
        {
            "symbol": symbol,
            "bucket": bucket,
            "expert_name": EXPERT_NAME,
            "direction": result["direction"],
            "confidence": result["confidence"],
            "evidence": json.dumps(result["evidence"]),
            "explanation": result["explanation"],
            "model_version": MODEL_VERSION,
            "computed_at": now,
        },
    )
    db.commit()


def run():
    db = SessionLocal()
    try:
        for symbol in SYMBOLS:
            candles = fetch_recent_features(db, symbol)
            if not candles:
                logger.info(f"[trend_ai] No feature data for {symbol}, skipping")
                continue

            result = analyze(candles)
            upsert_recommendation(db, symbol, candles[-1]["bucket"], result)
            logger.info(
                f"[trend_ai] {symbol}: {result['direction']} "
                f"(confidence={result['confidence']}) - {result['explanation']}"
            )
    finally:
        db.close()


if __name__ == "__main__":
    run()