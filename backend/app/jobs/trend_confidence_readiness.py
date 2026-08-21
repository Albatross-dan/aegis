from datetime import datetime, timezone
import argparse
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.db.session import SessionLocal

EXPERT_NAME = "trend_ai"
DEFAULT_MODEL_VERSION = "trend_ai_v2"
DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_HORIZON_MINUTES = 3
DEFAULT_MIN_COMPLETED_SAMPLES = 1
DEFAULT_MIN_UNIQUE_BUCKETS = 2


def _serialize_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def build_readiness_query() -> str:
    return """
        WITH recs AS (
            SELECT
                bucket
            FROM ai_recommendations
            WHERE expert_name = :expert_name
              AND (:model_version IS NULL OR model_version = :model_version)
              AND bucket >= (NOW() - make_interval(days => :lookback_days))
        ),
        latest_candle AS (
            SELECT MAX(bucket) AS latest_bucket
            FROM candles_1m
        ),
        cutoff AS (
            SELECT latest_bucket - make_interval(mins => :horizon_minutes) AS cutoff_bucket
            FROM latest_candle
        )
        SELECT
            COUNT(*) AS total_recommendations,
            COUNT(DISTINCT recs.bucket) AS unique_buckets,
            MAX(recs.bucket) AS latest_recommendation_bucket,
            MIN(recs.bucket) AS earliest_recommendation_bucket,
            MAX(latest_candle.latest_bucket) AS latest_candle_bucket,
            SUM(CASE WHEN recs.bucket <= cutoff.cutoff_bucket THEN 1 ELSE 0 END) AS completed_samples
        FROM recs
        CROSS JOIN latest_candle
        CROSS JOIN cutoff
    """


def fetch_readiness_metrics(
    db: Session,
    model_version: str | None,
    lookback_days: int,
    horizon_minutes: int,
) -> dict:
    row = db.execute(
        text(build_readiness_query()),
        {
            "expert_name": EXPERT_NAME,
            "model_version": model_version,
            "lookback_days": lookback_days,
            "horizon_minutes": horizon_minutes,
        },
    ).mappings().one()
    return dict(row)


def assess_readiness(metrics: dict, min_completed_samples: int, min_unique_buckets: int) -> dict:
    total_recommendations = int(metrics["total_recommendations"] or 0)
    unique_buckets = int(metrics["unique_buckets"] or 0)
    completed_samples = int(metrics["completed_samples"] or 0)

    ready = completed_samples >= min_completed_samples and unique_buckets >= min_unique_buckets

    reasons = []
    if total_recommendations == 0:
        reasons.append("no recommendations found")
    if unique_buckets < min_unique_buckets:
        reasons.append(f"need at least {min_unique_buckets} distinct recommendation buckets")
    if completed_samples < min_completed_samples:
        reasons.append(f"need at least {min_completed_samples} completed horizon sample(s)")

    return {
        "ready": ready,
        "total_recommendations": total_recommendations,
        "unique_buckets": unique_buckets,
        "completed_samples": completed_samples,
        "reasons": reasons,
    }


def run(
    db_session: Session | None = None,
    model_version: str | None = DEFAULT_MODEL_VERSION,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    horizon_minutes: int = DEFAULT_HORIZON_MINUTES,
    min_completed_samples: int = DEFAULT_MIN_COMPLETED_SAMPLES,
    min_unique_buckets: int = DEFAULT_MIN_UNIQUE_BUCKETS,
) -> dict:
    db = db_session or SessionLocal()
    owns_session = db_session is None

    try:
        metrics = fetch_readiness_metrics(
            db=db,
            model_version=model_version,
            lookback_days=lookback_days,
            horizon_minutes=horizon_minutes,
        )
        readiness = assess_readiness(
            metrics,
            min_completed_samples=min_completed_samples,
            min_unique_buckets=min_unique_buckets,
        )

        serialized_metrics = {key: _serialize_value(value) for key, value in metrics.items()}

        report = {
            "expert_name": EXPERT_NAME,
            "model_version": model_version or "all",
            "lookback_days": lookback_days,
            "horizon_minutes": horizon_minutes,
            "min_completed_samples": min_completed_samples,
            "min_unique_buckets": min_unique_buckets,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": serialized_metrics,
            "readiness": readiness,
        }

        if readiness["ready"]:
            logger.info(
                "[confidence_readiness] ready=%s completed_samples=%s unique_buckets=%s",
                readiness["ready"],
                readiness["completed_samples"],
                readiness["unique_buckets"],
            )
        else:
            logger.warning(
                "[confidence_readiness] not ready: %s",
                "; ".join(readiness["reasons"]) if readiness["reasons"] else "insufficient data",
            )

        return report
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trend AI confidence readiness check")
    parser.add_argument("--model-version", default=DEFAULT_MODEL_VERSION, help="Model version to inspect (use 'all' for no filter)")
    parser.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    parser.add_argument("--horizon-minutes", type=int, default=DEFAULT_HORIZON_MINUTES)
    parser.add_argument("--min-completed-samples", type=int, default=DEFAULT_MIN_COMPLETED_SAMPLES)
    parser.add_argument("--min-unique-buckets", type=int, default=DEFAULT_MIN_UNIQUE_BUCKETS)
    args = parser.parse_args()

    selected_model_version = None if args.model_version == "all" else args.model_version
    report = run(
        model_version=selected_model_version,
        lookback_days=args.lookback_days,
        horizon_minutes=args.horizon_minutes,
        min_completed_samples=args.min_completed_samples,
        min_unique_buckets=args.min_unique_buckets,
    )
    print(json.dumps(report, indent=2))