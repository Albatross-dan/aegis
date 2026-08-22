from app.jobs import trend_confidence_readiness


def test_build_readiness_query_contains_bucket_pairing_logic():
    query = trend_confidence_readiness.build_readiness_query()

    assert "FROM ai_recommendations" in query
    assert "COUNT(DISTINCT recs.bucket)" in query
    assert "latest_candle" in query
    assert "completed_samples" in query
    assert "make_interval(mins => :horizon_minutes)" in query


def test_assess_readiness_not_ready_without_enough_completed_samples():
    metrics = {
        "total_recommendations": 6,
        "unique_buckets": 1,
        "completed_samples": 0,
    }

    readiness = trend_confidence_readiness.assess_readiness(metrics, 1, 2)

    assert readiness["ready"] is False
    assert "need at least 2 distinct recommendation buckets" in readiness["reasons"]
    assert "need at least 1 completed horizon sample(s)" in readiness["reasons"]


def test_assess_readiness_ready_when_thresholds_met():
    metrics = {
        "total_recommendations": 12,
        "unique_buckets": 4,
        "completed_samples": 3,
    }

    readiness = trend_confidence_readiness.assess_readiness(metrics, 1, 2)

    assert readiness["ready"] is True
    assert readiness["reasons"] == []


def test_run_reports_deferred_when_market_is_closed(monkeypatch):
    monkeypatch.setattr(trend_confidence_readiness, "is_forex_market_closed", lambda _now: True)

    class FakeDb:
        def execute(self, *_args, **_kwargs):
            class Result:
                def mappings(self):
                    class Mappings:
                        def one(self):
                            return {
                                "total_recommendations": 6,
                                "unique_buckets": 1,
                                "latest_recommendation_bucket": None,
                                "earliest_recommendation_bucket": None,
                                "latest_candle_bucket": None,
                                "completed_samples": 0,
                            }
                    return Mappings()
            return Result()

        def close(self):
            pass

    report = trend_confidence_readiness.run(db_session=FakeDb(), model_version="trend_ai_v2")

    assert report["market_closed"] is True
    assert report["readiness"]["ready"] is False