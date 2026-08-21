from datetime import datetime, timezone

from fastapi import FastAPI, Depends, status, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.core.logging_config import logger
from app.core.validation import validate_tick
from app.models.schemas import TickIn
from app.models.market_data import MarketTick, RejectedTick

app = FastAPI(
    title="AEGIS - Artificial Financial Intelligence Platform",
    description="Institutional-grade AI Financial Intelligence Platform - Backend API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    logger.info("AEGIS backend starting up...")


@app.get("/")
def root():
    logger.info("Root endpoint accessed")
    return {
        "project": "AEGIS",
        "status": "operational",
        "message": "Observe. Understand. Reason. Protect. Execute. Learn. Improve."
    }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
        logger.info("Health check passed - database connected")
    except Exception as e:
        db_status = f"error: {str(e)}"
        logger.error(f"Health check failed - database error: {str(e)}")
    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
    }


def _quarantine_tick(db: Session, tick: TickIn, reason: str):
    rejected = RejectedTick(
        received_at=datetime.now(timezone.utc),
        timestamp=tick.timestamp,
        symbol=tick.symbol,
        broker_symbol=tick.broker_symbol,
        bid=tick.bid,
        ask=tick.ask,
        source=tick.source,
        rejection_reason=reason,
    )
    db.add(rejected)
    db.commit()
    logger.warning(f"Rejected tick: {tick.symbol} reason='{reason}'")


@app.post("/api/v1/ticks")
def ingest_tick(tick: TickIn, response: Response, db: Session = Depends(get_db)):
    # Stage Two validation (Doc 06 SS4)
    is_valid, reason = validate_tick(tick)
    if not is_valid:
        _quarantine_tick(db, tick, reason)
        response.status_code = status.HTTP_202_ACCEPTED
        return {"status": "rejected", "symbol": tick.symbol, "reason": reason}

    # Duplicate check - requires DB access, so it lives here rather than in validation.py
    existing = (
        db.query(MarketTick)
        .filter(
            MarketTick.symbol == tick.symbol,
            MarketTick.timestamp == tick.timestamp,
            MarketTick.bid == tick.bid,
            MarketTick.ask == tick.ask,
            MarketTick.source == tick.source,
        )
        .first()
    )
    if existing:
        _quarantine_tick(db, tick, "duplicate tick")
        response.status_code = status.HTTP_202_ACCEPTED
        return {"status": "rejected", "symbol": tick.symbol, "reason": "duplicate tick"}

    db_tick = MarketTick(
        symbol=tick.symbol,
        broker_symbol=tick.broker_symbol,
        bid=tick.bid,
        ask=tick.ask,
        timestamp=tick.timestamp,
        source=tick.source,
    )
    db.add(db_tick)
    db.commit()
    logger.info(f"Ingested tick: {tick.symbol} bid={tick.bid} ask={tick.ask}")
    response.status_code = status.HTTP_201_CREATED
    return {"status": "stored", "symbol": tick.symbol}


@app.get("/api/v1/prices/latest")
def latest_prices(db: Session = Depends(get_db)):
    result = db.execute(
        text("""
            SELECT DISTINCT ON (symbol)
                symbol, bid, ask, timestamp
            FROM market_ticks
            ORDER BY symbol, timestamp DESC
        """)
    )
    rows = result.fetchall()
    return {
        "prices": [
            {
                "symbol": row.symbol,
                "bid": row.bid,
                "ask": row.ask,
                "timestamp": row.timestamp.isoformat(),
            }
            for row in rows
        ]
    }
