from datetime import datetime, timedelta, timezone
import json
from urllib import request
from urllib.error import URLError, HTTPError

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.db.session import SessionLocal

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"]

TICK_STALENESS = timedelta(minutes=2)
FEATURE_STALENESS = timedelta(minutes=3)
TREND_STALENESS = timedelta(minutes=3)

BACKEND_HEALTH_URL = "http://127.0.0.1:8000/health"
BACKEND_TIMEOUT_SECONDS = 3

FOREX_MARKET_CLOSE_WEEKDAY = 4  # Friday
FOREX_MARKET_CLOSE_HOUR_UTC = 21
FOREX_MARKET_OPEN_WEEKDAY = 6  # Sunday
FOREX_MARKET_OPEN_HOUR_UTC = 21


def _format_age(now: datetime, ts: datetime) -> str:
    return f"{(now - ts).total_seconds():.1f}s"


def is_forex_market_closed(now: datetime) -> bool:
    now_utc = now.astimezone(timezone.utc)
    weekday = now_utc.weekday()
    hour = now_utc.hour

    if weekday == 5:
        return True

    if weekday == FOREX_MARKET_CLOSE_WEEKDAY and hour >= FOREX_MARKET_CLOSE_HOUR_UTC:
        return True

    if weekday == FOREX_MARKET_OPEN_WEEKDAY and hour < FOREX_MARKET_OPEN_HOUR_UTC:
        return True

    return False


def get_latest_tick_timestamp(db: Session, symbol: str):
    result = db.execute(
        text("""
            SELECT MAX(timestamp) AS latest_ts
            FROM market_ticks
            WHERE symbol = :symbol
        """),
        {"symbol": symbol},
    )
    return result.mappings().one()["latest_ts"]


def get_latest_feature_timestamp(db: Session, symbol: str):
    result = db.execute(
        text("""
            SELECT MAX(computed_at) AS latest_ts
            FROM technical_features
            WHERE symbol = :symbol
        """),
        {"symbol": symbol},
    )
    return result.mappings().one()["latest_ts"]


def get_latest_trend_timestamp(db: Session, symbol: str):
    result = db.execute(
        text("""
            SELECT MAX(computed_at) AS latest_ts
            FROM ai_recommendations
            WHERE symbol = :symbol
              AND expert_name = 'trend_ai'
        """),
        {"symbol": symbol},
    )
    return result.mappings().one()["latest_ts"]


def check_backend_health() -> tuple[bool, str]:
    req = request.Request(BACKEND_HEALTH_URL, method="GET")
    try:
        with request.urlopen(req, timeout=BACKEND_TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8")
            payload = json.loads(body)
            status_value = payload.get("status")
            if status_value == "healthy":
                return True, "healthy"
            return False, f"backend returned status='{status_value}'"
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"backend health check failed: {exc}"


def _check_freshness(
    symbol: str,
    latest_ts,
    now: datetime,
    threshold: timedelta,
    label: str,
    suppress_stale_alert: bool = False,
) -> bool:
    if latest_ts is None:
        logger.warning(
            f"ALERT: [{label}] {symbol} has no records; expected fresh data within {int(threshold.total_seconds())}s."
        )
        return True

    age = now - latest_ts
    if age > threshold:
        if suppress_stale_alert:
            logger.info(
                f"[heartbeat] [{label}] {symbol} expected stale (market closed); "
                f"latest={latest_ts.isoformat()} age={_format_age(now, latest_ts)}"
            )
            return False

        logger.warning(
            f"ALERT: [{label}] {symbol} stale; latest={latest_ts.isoformat()} age={_format_age(now, latest_ts)} "
            f"threshold={int(threshold.total_seconds())}s"
        )
        return True

    logger.info(
        f"[heartbeat] [{label}] {symbol} healthy; latest={latest_ts.isoformat()} age={_format_age(now, latest_ts)}"
    )
    return False


def run(db_session: Session | None = None, now: datetime | None = None, health_check_fn=check_backend_health) -> int:
    db = db_session or SessionLocal()
    owns_session = db_session is None
    check_time = now or datetime.now(timezone.utc)

    alert_count = 0
    market_closed = is_forex_market_closed(check_time)

    if market_closed:
        logger.info("[heartbeat] market is closed (weekend window); stale market-data checks are informational only")

    try:
        for symbol in SYMBOLS:
            latest_tick = get_latest_tick_timestamp(db, symbol)
            if _check_freshness(
                symbol,
                latest_tick,
                check_time,
                TICK_STALENESS,
                "market_ticks",
                suppress_stale_alert=market_closed,
            ):
                alert_count += 1

            latest_feature = get_latest_feature_timestamp(db, symbol)
            if _check_freshness(
                symbol,
                latest_feature,
                check_time,
                FEATURE_STALENESS,
                "technical_features",
                suppress_stale_alert=market_closed,
            ):
                alert_count += 1

            latest_trend = get_latest_trend_timestamp(db, symbol)
            if _check_freshness(
                symbol,
                latest_trend,
                check_time,
                TREND_STALENESS,
                "ai_recommendations",
                suppress_stale_alert=market_closed,
            ):
                alert_count += 1

        backend_ok, backend_message = health_check_fn()
        if backend_ok:
            logger.info(f"[heartbeat] [backend] healthy; {backend_message}")
        else:
            alert_count += 1
            logger.warning(f"ALERT: [backend] {backend_message}")

        if alert_count == 0:
            logger.info("[heartbeat] all checks healthy")
        else:
            logger.warning(f"ALERT: heartbeat detected {alert_count} alert condition(s)")

        return alert_count
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    alerts = run()
    raise SystemExit(1 if alerts > 0 else 0)