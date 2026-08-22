# Phase 5 Research Registry

The research registry is a simple audit log for backtests, replay runs, and calibration experiments.

## Purpose

- Record what was tested.
- Store the exact parameter set used for the experiment.
- Preserve the outputs or summary metrics returned by the run.
- Make later comparison and replication straightforward.
The registry is stored in `research_experiments`.

## Recommended Uses

Record a run with `python -m app.jobs.research_registry`.
- `experiment_name`
- `run_type`
- `model_version`
- `status`
- `parameters`
- `results`
- `notes`

## Operator Rule

Use the registry for reproducibility, not as a substitute for analysis.
Each record should be backed by a real experiment or replay run.