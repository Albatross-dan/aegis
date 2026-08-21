from app.jobs import trend_confidence_audit


def test_build_audit_query_contains_key_joins_and_filters():
    query = trend_confidence_audit.build_audit_query()

    assert "FROM ai_recommendations r" in query
    assert "JOIN candles_1m c_now" in query
    assert "JOIN LATERAL" in query
    assert "c_future.bucket >= r.bucket + make_interval(mins => :horizon_minutes)" in query
    assert "is_directional_prediction" in query
    assert "directional_accuracy" in query
    assert "make_interval(mins => :horizon_minutes)" in query


def test_summarize_bins_returns_zeroed_summary_when_empty():
    summary = trend_confidence_audit.summarize_bins([])

    assert summary["total_samples"] == 0
    assert summary["overall_accuracy"] is None
    assert summary["overall_avg_confidence"] is None
    assert summary["directional_samples"] == 0
    assert summary["overall_directional_accuracy"] is None


def test_summarize_bins_computes_weighted_metrics():
    rows = [
        {
            "confidence_bin": 5,
            "sample_size": 10,
            "accuracy": 0.6,
            "avg_confidence": 0.55,
            "directional_sample_size": 4,
            "directional_accuracy": 0.5,
        },
        {
            "confidence_bin": 8,
            "sample_size": 20,
            "accuracy": 0.8,
            "avg_confidence": 0.85,
            "directional_sample_size": 6,
            "directional_accuracy": 0.8333,
        },
    ]

    summary = trend_confidence_audit.summarize_bins(rows)

    assert summary["total_samples"] == 30
    assert summary["overall_accuracy"] == 0.7333
    assert summary["overall_avg_confidence"] == 0.75
    assert summary["directional_samples"] == 10
    assert summary["overall_directional_accuracy"] == 0.7