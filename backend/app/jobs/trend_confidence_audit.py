from datetime import datetime, timezone
import argparse
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.db.session import SessionLocal

EXPERT_NAME = "trend_ai"
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_HORIZON_MINUTES = 3


def build_audit_query() -> str:
    return """
        WITH paired AS (
            SELECT
                r.symbol,
                r.bucket,
                r.direction AS predicted_direction,
                r.confidence,
                c_now.close AS close_now,
                                c_future.close AS close_future,
                CASE
                    WHEN c_future.close > c_now.close THEN 'buy'
                    WHEN c_future.close < c_now.close THEN 'sell'
                    ELSE 'hold'
                END AS observed_direction
            FROM ai_recommendations r
            JOIN candles_1m c_now
              ON c_now.symbol = r.symbol
             AND c_now.bucket = r.bucket
                        JOIN LATERAL (
                                SELECT close
                                FROM candles_1m c_future
                                WHERE c_future.symbol = r.symbol
                                    AND c_future.bucket >= r.bucket + make_interval(mins => :horizon_minutes)
                                ORDER BY c_future.bucket ASC
                                LIMIT 1
                        ) c_future ON TRUE
            WHERE r.expert_name = :expert_name
                            AND (:model_version IS NULL OR r.model_version = :model_version)
              AND r.bucket >= (NOW() - make_interval(days => :lookback_days))
        ),
        scored AS (
            SELECT
                symbol,
                bucket,
                predicted_direction,
                observed_direction,
                confidence,
                CASE WHEN predicted_direction = observed_direction THEN 1 ELSE 0 END AS is_correct,
                CASE WHEN predicted_direction IN ('buy', 'sell') THEN 1 ELSE 0 END AS is_directional_prediction,
                CASE
                    WHEN predicted_direction IN ('buy', 'sell') AND observed_direction IN ('buy', 'sell')
                         AND predicted_direction = observed_direction THEN 1
                    ELSE 0
                END AS is_directional_correct,
                LEAST(FLOOR(confidence * 10)::int, 9) AS confidence_bin
            FROM paired
        ),
        bucket_stats AS (
            SELECT
                confidence_bin,
                COUNT(*) AS sample_size,
                AVG(is_correct::float) AS accuracy,
                AVG(confidence) AS avg_confidence,
                SUM(is_directional_prediction) AS directional_sample_size,
                AVG(
                    CASE
                        WHEN is_directional_prediction = 1 THEN is_directional_correct::float
                        ELSE NULL
                    END
                ) AS directional_accuracy
            FROM scored
            GROUP BY confidence_bin
            ORDER BY confidence_bin
        )
        SELECT
            confidence_bin,
            sample_size,
            ROUND(accuracy::numeric, 4)::float AS accuracy,
            ROUND(avg_confidence::numeric, 4)::float AS avg_confidence,
            directional_sample_size,
            CASE
                WHEN directional_accuracy IS NULL THEN NULL
                ELSE ROUND(directional_accuracy::numeric, 4)::float
            END AS directional_accuracy
        FROM bucket_stats
    """


def fetch_confidence_bins(
    db: Session,
    model_version: str | None,
    lookback_days: int,
    horizon_minutes: int,
) -> list[dict]:
    rows = db.execute(
        text(build_audit_query()),
        {
            "expert_name": EXPERT_NAME,
            "model_version": model_version,
            "lookback_days": lookback_days,
            "horizon_minutes": horizon_minutes,
        },
    ).mappings().all()
    return [dict(row) for row in rows]


def summarize_bins(rows: list[dict]) -> dict:
    total_samples = sum(int(row["sample_size"]) for row in rows)
    total_directional_samples = sum(int(row["directional_sample_size"]) for row in rows)
    if total_samples == 0:
        return {
            "total_samples": 0,
            "overall_accuracy": None,
            "overall_avg_confidence": None,
            "directional_samples": 0,
            "overall_directional_accuracy": None,
        }

    weighted_accuracy = sum(float(row["accuracy"]) * int(row["sample_size"]) for row in rows) / total_samples
    weighted_confidence = sum(float(row["avg_confidence"]) * int(row["sample_size"]) for row in rows) / total_samples

    directional_weighted_accuracy = None
    if total_directional_samples > 0:
        directional_weighted_accuracy = round(
            sum(
                float(row["directional_accuracy"]) * int(row["directional_sample_size"])
                for row in rows
                if row["directional_accuracy"] is not None
            )
            / total_directional_samples,
            4,
        )

    return {
        "total_samples": total_samples,
        "overall_accuracy": round(weighted_accuracy, 4),
        "overall_avg_confidence": round(weighted_confidence, 4),
        "directional_samples": total_directional_samples,
        "overall_directional_accuracy": directional_weighted_accuracy,
    }


def run(
    db_session: Session | None = None,
    model_version: str | None = "trend_ai_v2",
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    horizon_minutes: int = DEFAULT_HORIZON_MINUTES,
) -> dict:
    db = db_session or SessionLocal()
    owns_session = db_session is None

    try:
        bins = fetch_confidence_bins(
            db=db,
            model_version=model_version,
            lookback_days=lookback_days,
            horizon_minutes=horizon_minutes,
        )
        summary = summarize_bins(bins)

        report = {
            "expert_name": EXPERT_NAME,
            "model_version": model_version or "all",
            "lookback_days": lookback_days,
            "horizon_minutes": horizon_minutes,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "bins": bins,
        }

        if summary["total_samples"] == 0:
            logger.warning("[confidence_audit] No paired samples found for configured window.")
        else:
            logger.info(
                "[confidence_audit] samples=%s accuracy=%s avg_confidence=%s",
                summary["total_samples"],
                summary["overall_accuracy"],
                summary["overall_avg_confidence"],
            )

        return report
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trend AI confidence calibration audit")
    parser.add_argument("--model-version", default="trend_ai_v2", help="Model version to audit (use 'all' for no filter)")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--horizon-minutes", type=int, default=DEFAULT_HORIZON_MINUTES)
    args = parser.parse_args()

    selected_model_version = None if args.model_version == "all" else args.model_version
    report = run(
        model_version=selected_model_version,
        lookback_days=args.lookback_days,
        horizon_minutes=args.horizon_minutes,
    )
    print(json.dumps(report, indent=2))