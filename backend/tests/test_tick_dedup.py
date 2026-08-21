from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.main import _is_near_duplicate_tick
from app.models.schemas import TickIn


def make_tick(symbol: str, bid: float, ask: float, timestamp: datetime) -> TickIn:
    return TickIn(
        symbol=symbol,
        broker_symbol=symbol,
        bid=bid,
        ask=ask,
        timestamp=timestamp,
        source="mt5_exness",
    )


def make_latest_tick(symbol: str, bid: float, ask: float, timestamp: datetime):
    return SimpleNamespace(
        symbol=symbol,
        bid=bid,
        ask=ask,
        timestamp=timestamp,
        source="mt5_exness",
    )


def test_near_duplicate_true_within_time_and_price_tolerance():
    base_ts = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    latest = make_latest_tick("EURUSD", 1.10000, 1.10010, base_ts)
    incoming = make_tick("EURUSD", 1.10001, 1.10011, base_ts + timedelta(seconds=1))

    assert _is_near_duplicate_tick(latest, incoming) is True


def test_near_duplicate_false_when_time_delta_exceeds_window():
    base_ts = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    latest = make_latest_tick("EURUSD", 1.10000, 1.10010, base_ts)
    incoming = make_tick("EURUSD", 1.10001, 1.10011, base_ts + timedelta(seconds=5))

    assert _is_near_duplicate_tick(latest, incoming) is False


def test_near_duplicate_false_when_price_delta_exceeds_tolerance():
    base_ts = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    latest = make_latest_tick("EURUSD", 1.10000, 1.10010, base_ts)
    incoming = make_tick("EURUSD", 1.10006, 1.10016, base_ts + timedelta(seconds=1))

    assert _is_near_duplicate_tick(latest, incoming) is False