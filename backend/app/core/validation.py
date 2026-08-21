from datetime import datetime, timezone, timedelta
from typing import Optional

from app.models.schemas import TickIn

# --- Configurable thresholds (Doc 06 SS4) ---

MAX_FUTURE_SKEW_SECONDS = 5
MAX_STALENESS_SECONDS = 60

# Per-symbol config: (min_price, max_price, max_spread)
# Bounds are intentionally wide historical sanity ranges, not tight trading signals.
SYMBOL_CONFIG = {
    "EURUSD": (0.90, 1.30, 0.0010),
    "GBPUSD": (1.05, 1.45, 0.0015),
    "USDJPY": (100.0, 170.0, 0.15),
    "USDCHF": (0.75, 1.05, 0.0015),
    "AUDUSD": (0.55, 0.80, 0.0015),
    "USDCAD": (1.20, 1.50, 0.0015),
}


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


def check_price_sanity(tick: TickIn) -> tuple[bool, Optional[str]]:
    if tick.bid <= 0 or tick.ask <= 0:
        return False, "non-positive bid/ask"
    if tick.ask < tick.bid:
        return False, "crossed market (ask < bid)"

    config = SYMBOL_CONFIG.get(tick.symbol)
    if config:
        low, high, _ = config
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


def validate_tick(tick: TickIn) -> tuple[bool, Optional[str]]:
    """Run all validation checks in order. Returns (is_valid, reason)."""
    for check in VALIDATION_CHECKS:
        is_valid, reason = check(tick)
        if not is_valid:
            return False, reason
    return True, None
