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