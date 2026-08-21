from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.schemas import TickIn

# --- Configurable thresholds (Doc 06 SS4) ---

MAX_FUTURE_SKEW_SECONDS = 5
MAX_STALENESS_SECONDS = 60

# Per-symbol config: (fallback_min_price, fallback_max_price, max_spread)
# The price bounds are only fallback safety nets; dynamic ranges are derived from
# live historical market_ticks data.
SYMBOL_CONFIG = {
    "EURUSD": (0.90, 1.30, 0.0010),
    "GBPUSD": (1.05, 1.45, 0.0015),
    "USDJPY": (100.0, 170.0, 0.15),
    "USDCHF": (0.75, 1.05, 0.0015),
    "AUDUSD": (0.55, 0.80, 0.0015),
    "USDCAD": (1.20, 1.50, 0.0015),
}

MIN_HISTORY_TICKS = 100
HISTORY_LOOKBACK_DAYS = 30


def get_dynamic_price_bounds(symbol: str, db_session: Session) -> tuple[float, float]:
    fallback = SYMBOL_CONFIG.get(symbol)
    if fallback is None:
        raise ValueError(f"Unsupported symbol: {symbol}")

    fallback_low, fallback_high, _ = fallback
    if db_session is None:
        return fallback_low, fallback_high

    result = db_session.execute(
        text("""
            SELECT
                COUNT(*) AS tick_count,
                MIN(bid) AS min_bid,
                MAX(bid) AS max_bid
            FROM market_ticks
            WHERE symbol = :symbol
              AND timestamp >= NOW() - (:lookback_days || ' days')::interval
        """),
        {"symbol": symbol, "lookback_days": HISTORY_LOOKBACK_DAYS},
    )
    row = result.mappings().one()
    tick_count = row["tick_count"] or 0
    min_bid = row["min_bid"]
    max_bid = row["max_bid"]

    if tick_count < MIN_HISTORY_TICKS or min_bid is None or max_bid is None:
        return fallback_low, fallback_high

    return min_bid * 0.85, max_bid * 1.15


def check_missing_fields(tick: TickIn) -> tuple[bool, Optional[str]]:
    if not tick.symbol or not tick.broker_symbol or not tick.source:
        return False, "missing required string field"
    if tick.bid is None or tick.ask is None:
        return False, "missing bid/ask"
    if tick.timestamp is None:
        return False, "missing timestamp"
    return True, None


def check_timestamp_sanity(tick: TickIn) -> tuple[bool, Optional[str]]:
    now = datetime.now(timezone.utc)
    ts = tick.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    if ts > now + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
        return False, f"timestamp too far in future (>{MAX_FUTURE_SKEW_SECONDS}s)"
    if ts < now - timedelta(seconds=MAX_STALENESS_SECONDS):
        return False, f"stale timestamp (>{MAX_STALENESS_SECONDS}s old)"
    return True, None


def check_price_sanity(tick: TickIn, db_session: Session) -> tuple[bool, Optional[str]]:
    if tick.bid <= 0 or tick.ask <= 0:
        return False, "non-positive bid/ask"
    if tick.ask < tick.bid:
        return False, "crossed market (ask < bid)"

    low, high = get_dynamic_price_bounds(tick.symbol, db_session)
    if not (low <= tick.bid <= high) or not (low <= tick.ask <= high):
        return False, f"price out of expected range [{low}, {high}] for {tick.symbol}"
    return True, None


def check_spread_sanity(tick: TickIn) -> tuple[bool, Optional[str]]:
    spread = tick.ask - tick.bid

    config = SYMBOL_CONFIG.get(tick.symbol)
    max_spread = config[2] if config else 0.0010  # fallback for unconfigured symbols

    if spread > max_spread:
        return False, f"spread too wide ({spread:.5f} > {max_spread}) for {tick.symbol}"
    return True, None


# Ordered pipeline. Fail-fast: first failing check determines the rejection reason.
VALIDATION_CHECKS = [
    check_missing_fields,
    check_timestamp_sanity,
    check_price_sanity,
    check_spread_sanity,
]


def validate_tick(tick: TickIn, db_session: Session) -> tuple[bool, Optional[str]]:
    """Run all validation checks in order. Returns (is_valid, reason)."""
    for check in VALIDATION_CHECKS:
        if check is check_price_sanity:
            is_valid, reason = check(tick, db_session)
        else:
            is_valid, reason = check(tick)
        if not is_valid:
            return False, reason
    return True, None
