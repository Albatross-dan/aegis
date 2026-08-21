from datetime import datetime, timedelta, timezone
from math import isclose

import pytest

from app.core import validation
from app.models.schemas import TickIn


class FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def one(self):
        return self._row


class FakeSession:
    def __init__(self, rows_by_symbol):
        self.rows_by_symbol = rows_by_symbol

    def execute(self, statement, params):
        symbol = params["symbol"]
        return FakeResult(self.rows_by_symbol[symbol])


@pytest.fixture
def tick_factory():
    def _make_tick(**overrides):
        base = TickIn(
            symbol="EURUSD",
            broker_symbol="EURUSDm",
            bid=1.1000,
            ask=1.1002,
            timestamp=datetime.now(timezone.utc),
            source="mt5_exness",
        )
        data = base.model_dump()
        data.update(overrides)
        return TickIn.model_construct(**data)

    return _make_tick


@pytest.fixture
def db_session_factory():
    def _make_session(**rows_by_symbol):
        return FakeSession(rows_by_symbol)

    return _make_session


def test_get_dynamic_price_bounds_uses_historial_range_when_enough_ticks(db_session_factory):
    db_session = db_session_factory(
        EURUSD={"tick_count": 120, "min_bid": 1.0000, "max_bid": 1.1000}
    )

    low, high = validation.get_dynamic_price_bounds("EURUSD", db_session)

    assert isclose(low, 0.85)
    assert isclose(high, 1.265)


def test_get_dynamic_price_bounds_falls_back_when_history_is_small(db_session_factory):
    db_session = db_session_factory(
        USDJPY={"tick_count": 42, "min_bid": 150.0, "max_bid": 151.0}
    )

    low, high = validation.get_dynamic_price_bounds("USDJPY", db_session)

    assert (low, high) == validation.SYMBOL_CONFIG["USDJPY"][:2]


def test_check_missing_fields_valid_tick_passes(tick_factory):
    tick = tick_factory()

    is_valid, reason = validation.check_missing_fields(tick)

    assert is_valid is True
    assert reason is None


@pytest.mark.parametrize(
    "field_name",
    ["symbol", "bid", "ask", "timestamp"],
)
def test_check_missing_fields_each_required_field_fails(tick_factory, field_name):
    tick = tick_factory(**{field_name: None if field_name != "symbol" else ""})

    is_valid, reason = validation.check_missing_fields(tick)

    assert is_valid is False
    assert reason is not None


def test_check_timestamp_sanity_recent_timestamp_passes(tick_factory):
    tick = tick_factory(timestamp=datetime.now(timezone.utc) - timedelta(seconds=1))

    is_valid, reason = validation.check_timestamp_sanity(tick)

    assert is_valid is True
    assert reason is None


def test_check_timestamp_sanity_stale_timestamp_fails(tick_factory):
    tick = tick_factory(timestamp=datetime.now(timezone.utc) - timedelta(seconds=61))

    is_valid, reason = validation.check_timestamp_sanity(tick)

    assert is_valid is False
    assert reason is not None and "stale" in reason


def test_check_timestamp_sanity_future_timestamp_fails(tick_factory):
    tick = tick_factory(timestamp=datetime.now(timezone.utc) + timedelta(seconds=6))

    is_valid, reason = validation.check_timestamp_sanity(tick)

    assert is_valid is False
    assert reason is not None and "future" in reason


def test_check_price_sanity_valid_eurusd_passes(tick_factory, db_session_factory):
    db_session = db_session_factory(
        EURUSD={"tick_count": 150, "min_bid": 1.0000, "max_bid": 1.1000}
    )
    tick = tick_factory(symbol="EURUSD", bid=1.0500, ask=1.0502)

    is_valid, reason = validation.check_price_sanity(tick, db_session)

    assert is_valid is True
    assert reason is None


@pytest.mark.parametrize(
    "bid, ask",
    [(-0.1, 1.1002), (1.1000, -0.1)],
)
def test_check_price_sanity_negative_bid_or_ask_fails(tick_factory, db_session_factory, bid, ask):
    db_session = db_session_factory(
        EURUSD={"tick_count": 150, "min_bid": 1.0000, "max_bid": 1.1000}
    )
    tick = tick_factory(bid=bid, ask=ask)

    is_valid, reason = validation.check_price_sanity(tick, db_session)

    assert is_valid is False
    assert reason == "non-positive bid/ask"


def test_check_price_sanity_crossed_market_fails(tick_factory, db_session_factory):
    db_session = db_session_factory(
        EURUSD={"tick_count": 150, "min_bid": 1.0000, "max_bid": 1.1000}
    )
    tick = tick_factory(bid=1.1005, ask=1.1004)

    is_valid, reason = validation.check_price_sanity(tick, db_session)

    assert is_valid is False
    assert reason == "crossed market (ask < bid)"


@pytest.mark.parametrize(
    "symbol, bid, ask",
    [
        ("EURUSD", 1.4000, 1.4002),
        ("USDJPY", 99.0, 99.1),
    ],
)
def test_check_price_sanity_out_of_range_for_multiple_symbols_fails(tick_factory, db_session_factory, symbol, bid, ask):
    db_session = db_session_factory(
        EURUSD={"tick_count": 50, "min_bid": 1.0000, "max_bid": 1.1000},
        USDJPY={"tick_count": 50, "min_bid": 150.0, "max_bid": 151.0},
    )
    tick = tick_factory(symbol=symbol, bid=bid, ask=ask)

    is_valid, reason = validation.check_price_sanity(tick, db_session)

    assert is_valid is False
    assert reason is not None and symbol in reason


def test_check_spread_sanity_normal_spread_passes(tick_factory):
    tick = tick_factory(symbol="EURUSD", bid=1.1000, ask=1.1002)

    is_valid, reason = validation.check_spread_sanity(tick)

    assert is_valid is True
    assert reason is None


def test_check_spread_sanity_usdjpy_exceeds_max_fails(tick_factory):
    tick = tick_factory(symbol="USDJPY", bid=150.00, ask=150.20)

    is_valid, reason = validation.check_spread_sanity(tick)

    assert is_valid is False
    assert reason is not None and "USDJPY" in reason


def test_validate_tick_valid_tick_passes_end_to_end(tick_factory, db_session_factory):
    db_session = db_session_factory(
        EURUSD={"tick_count": 150, "min_bid": 1.0000, "max_bid": 1.1000}
    )
    tick = tick_factory()

    is_valid, reason = validation.validate_tick(tick, db_session)

    assert is_valid is True
    assert reason is None


def test_validate_tick_fail_fast_returns_first_reason(tick_factory, db_session_factory):
    db_session = db_session_factory(
        EURUSD={"tick_count": 150, "min_bid": 1.0000, "max_bid": 1.1000}
    )
    tick = tick_factory(
        symbol="EURUSD",
        bid=1.5000,
        ask=1.4990,
        timestamp=datetime.now(timezone.utc) - timedelta(seconds=61),
    )

    is_valid, reason = validation.validate_tick(tick, db_session)

    assert is_valid is False
    assert reason is not None and "stale" in reason