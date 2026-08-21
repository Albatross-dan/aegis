"""
Pipeline job for explicit dependency ordering between feature computation
and Trend AI recommendation generation.

Replaces sleep-based cron sequencing by running both jobs in a single process:
1) compute_features
2) trend_ai
"""

from app.ai_council import trend_ai
from app.core.logging_config import logger
from app.jobs import compute_features


def run(
    features_runner=compute_features.run,
    trend_runner=trend_ai.run,
) -> int:
    logger.info("[pipeline] Starting feature->trend pipeline")
    try:
        features_runner()
        logger.info("[pipeline] Feature computation completed")

        trend_runner()
        logger.info("[pipeline] Trend AI computation completed")

        logger.info("[pipeline] Pipeline completed successfully")
        return 0
    except Exception as exc:
        logger.exception(f"ALERT: [pipeline] Pipeline failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(run())