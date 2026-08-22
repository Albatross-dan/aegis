from datetime import datetime, timezone

from app.jobs import research_registry


def test_build_insert_statement_mentions_research_experiments():
    statement = research_registry.build_insert_statement()

    assert "INSERT INTO research_experiments" in statement
    assert "experiment_name" in statement
    assert "parameters" in statement
    assert "results" in statement


def test_build_experiment_payload_uses_utc_timestamp():
    payload = research_registry.build_experiment_payload(
        experiment_name="trend_ai_backtest",
        run_type="backtest",
        parameters={"horizon_minutes": 3},
        results={"accuracy": 0.5},
        model_version="trend_ai_v2",
        notes="sample run",
        created_at=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
    )

    assert payload["experiment_name"] == "trend_ai_backtest"
    assert payload["run_type"] == "backtest"
    assert payload["model_version"] == "trend_ai_v2"
    assert payload["parameters"] == {"horizon_minutes": 3}
    assert payload["results"] == {"accuracy": 0.5}
    assert payload["notes"] == "sample run"


def test_record_experiment_executes_and_commits():
    calls = {"execute": 0, "commit": 0}

    class FakeDb:
        def execute(self, *_args, **_kwargs):
            calls["execute"] += 1

        def commit(self):
            calls["commit"] += 1

    payload = research_registry.record_experiment(
        db=FakeDb(),
        experiment_name="trend_ai_backtest",
        run_type="backtest",
        parameters={"horizon_minutes": 3},
        results={"accuracy": 0.5},
        status="completed",
        model_version="trend_ai_v2",
        notes=None,
    )

    assert calls["execute"] == 1
    assert calls["commit"] == 1
    assert payload["experiment_name"] == "trend_ai_backtest"