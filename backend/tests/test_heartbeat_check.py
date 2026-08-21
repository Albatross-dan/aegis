from datetime import datetime, timedelta, timezone
import logging

from app.jobs import heartbeat_check


def test_heartbeat_stale_tick_triggers_alert(monkeypatch, caplog):
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    fresh = now - timedelta(seconds=30)
    stale = now - timedelta(minutes=3)

    monkeypatch.setattr(
        heartbeat_check,
        "get_latest_tick_timestamp",
        lambda _db, symbol: stale if symbol == "EURUSD" else fresh,
    )
    monkeypatch.setattr(heartbeat_check, "get_latest_feature_timestamp", lambda _db, _symbol: fresh)
    monkeypatch.setattr(heartbeat_check, "get_latest_trend_timestamp", lambda _db, _symbol: fresh)

    caplog.set_level(logging.INFO, logger="aegis")
    alerts = heartbeat_check.run(db_session=object(), now=now, health_check_fn=lambda: (True, "healthy"))

    assert alerts == 1
    assert any("ALERT:" in record.message and "market_ticks" in record.message for record in caplog.records)


def test_heartbeat_fully_healthy_has_no_alerts(monkeypatch, caplog):
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    fresh = now - timedelta(seconds=20)

    monkeypatch.setattr(heartbeat_check, "get_latest_tick_timestamp", lambda _db, _symbol: fresh)
    monkeypatch.setattr(heartbeat_check, "get_latest_feature_timestamp", lambda _db, _symbol: fresh)
    monkeypatch.setattr(heartbeat_check, "get_latest_trend_timestamp", lambda _db, _symbol: fresh)

    caplog.set_level(logging.INFO, logger="aegis")
    alerts = heartbeat_check.run(db_session=object(), now=now, health_check_fn=lambda: (True, "healthy"))

    assert alerts == 0
    assert any("all checks healthy" in record.message for record in caplog.records)
    assert not any(record.message.startswith("ALERT:") for record in caplog.records)


def test_heartbeat_backend_unhealthy_triggers_alert(monkeypatch, caplog):
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    fresh = now - timedelta(seconds=20)

    monkeypatch.setattr(heartbeat_check, "get_latest_tick_timestamp", lambda _db, _symbol: fresh)
    monkeypatch.setattr(heartbeat_check, "get_latest_feature_timestamp", lambda _db, _symbol: fresh)
    monkeypatch.setattr(heartbeat_check, "get_latest_trend_timestamp", lambda _db, _symbol: fresh)

    caplog.set_level(logging.INFO, logger="aegis")
    alerts = heartbeat_check.run(
        db_session=object(),
        now=now,
        health_check_fn=lambda: (False, "backend returned status='degraded'"),
    )

    assert alerts == 1
    assert any(record.message.startswith("ALERT: [backend]") for record in caplog.records)