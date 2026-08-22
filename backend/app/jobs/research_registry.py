from datetime import datetime, timezone
import argparse
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging_config import logger
from app.db.session import SessionLocal


def build_insert_statement() -> str:
    return """
        INSERT INTO research_experiments
            (experiment_name, run_type, model_version, status, parameters, results, notes, created_at)
        VALUES
            (:experiment_name, :run_type, :model_version, :status, :parameters, :results, :notes, :created_at)
    """


def build_experiment_payload(
    experiment_name: str,
    run_type: str,
    parameters: dict,
    results: dict,
    status: str = "completed",
    model_version: str | None = None,
    notes: str | None = None,
    created_at: datetime | None = None,
) -> dict:
    return {
        "experiment_name": experiment_name,
        "run_type": run_type,
        "model_version": model_version,
        "status": status,
        "parameters": parameters,
        "results": results,
        "notes": notes,
        "created_at": created_at or datetime.now(timezone.utc),
    }


def record_experiment(
    db: Session,
    experiment_name: str,
    run_type: str,
    parameters: dict,
    results: dict,
    status: str = "completed",
    model_version: str | None = None,
    notes: str | None = None,
) -> dict:
    payload = build_experiment_payload(
        experiment_name=experiment_name,
        run_type=run_type,
        parameters=parameters,
        results=results,
        status=status,
        model_version=model_version,
        notes=notes,
    )
    execution_payload = {
        **payload,
        "parameters": json.dumps(payload["parameters"]),
        "results": json.dumps(payload["results"]),
    }
    db.execute(text(build_insert_statement()), execution_payload)
    db.commit()
    logger.info(
        "[research_registry] recorded experiment=%s run_type=%s status=%s",
        experiment_name,
        run_type,
        status,
    )
    return payload


def run(
    experiment_name: str,
    run_type: str,
    parameters: dict,
    results: dict,
    status: str = "completed",
    model_version: str | None = None,
    notes: str | None = None,
    db_session: Session | None = None,
) -> dict:
    db = db_session or SessionLocal()
    owns_session = db_session is None

    try:
        return record_experiment(
            db=db,
            experiment_name=experiment_name,
            run_type=run_type,
            parameters=parameters,
            results=results,
            status=status,
            model_version=model_version,
            notes=notes,
        )
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Record a Phase 5 research experiment")
    parser.add_argument("--experiment-name", required=True)
    parser.add_argument("--run-type", required=True)
    parser.add_argument("--model-version", default=None)
    parser.add_argument("--status", default="completed")
    parser.add_argument("--parameters", required=True, help="JSON object string")
    parser.add_argument("--results", required=True, help="JSON object string")
    parser.add_argument("--notes", default=None)
    args = parser.parse_args()

    payload = run(
        experiment_name=args.experiment_name,
        run_type=args.run_type,
        parameters=json.loads(args.parameters),
        results=json.loads(args.results),
        status=args.status,
        model_version=args.model_version,
        notes=args.notes,
    )
    print(json.dumps({**payload, "created_at": payload["created_at"].isoformat()}, indent=2))