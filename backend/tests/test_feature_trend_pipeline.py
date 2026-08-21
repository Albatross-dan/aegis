from app.jobs import feature_trend_pipeline


def test_pipeline_runs_features_then_trend():
    steps = []

    def features_runner():
        steps.append("features")

    def trend_runner():
        steps.append("trend")

    exit_code = feature_trend_pipeline.run(
        features_runner=features_runner,
        trend_runner=trend_runner,
    )

    assert exit_code == 0
    assert steps == ["features", "trend"]


def test_pipeline_does_not_run_trend_if_features_fail():
    steps = []

    def features_runner():
        steps.append("features")
        raise RuntimeError("feature job failed")

    def trend_runner():
        steps.append("trend")

    exit_code = feature_trend_pipeline.run(
        features_runner=features_runner,
        trend_runner=trend_runner,
    )

    assert exit_code == 1
    assert steps == ["features"]