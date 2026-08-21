from datetime import datetime, timezone
from dataclasses import dataclass

from fastapi import FastAPI, Depends, status, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import get_db
from app.core.logging_config import logger
from app.core.validation import validate_tick, SYMBOL_CONFIG
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


NEAR_DUPLICATE_WINDOW_SECONDS = 2
NEAR_DUPLICATE_TOLERANCE_RATIO = 0.02


@dataclass
class NearDuplicateConfig:
    window_seconds: int
    price_tolerance: float


def _near_duplicate_config(symbol: str) -> NearDuplicateConfig:
    symbol_config = SYMBOL_CONFIG.get(symbol)
    max_spread = symbol_config[2] if symbol_config else 0.0010
    tolerance = max(max_spread * NEAR_DUPLICATE_TOLERANCE_RATIO, 0.000001)
    return NearDuplicateConfig(
        window_seconds=NEAR_DUPLICATE_WINDOW_SECONDS,
        price_tolerance=tolerance,
    )


def _is_near_duplicate_tick(latest_tick: MarketTick, incoming_tick: TickIn) -> bool:
    if latest_tick is None:
        return False

    config = _near_duplicate_config(incoming_tick.symbol)
    latest_ts = latest_tick.timestamp
    incoming_ts = incoming_tick.timestamp

    if latest_ts.tzinfo is None:
        latest_ts = latest_ts.replace(tzinfo=timezone.utc)
    if incoming_ts.tzinfo is None:
        incoming_ts = incoming_ts.replace(tzinfo=timezone.utc)

    seconds_delta = abs((incoming_ts - latest_ts).total_seconds())
    if seconds_delta > config.window_seconds:
        return False

    return (
        abs(incoming_tick.bid - latest_tick.bid) <= config.price_tolerance
        and abs(incoming_tick.ask - latest_tick.ask) <= config.price_tolerance
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
    is_valid, reason = validate_tick(tick, db)
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

    latest_symbol_tick = (
        db.query(MarketTick)
        .filter(
            MarketTick.symbol == tick.symbol,
            MarketTick.source == tick.source,
        )
        .order_by(MarketTick.timestamp.desc())
        .first()
    )
    if _is_near_duplicate_tick(latest_symbol_tick, tick):
        _quarantine_tick(db, tick, "near-duplicate tick")
        response.status_code = status.HTTP_202_ACCEPTED
        return {"status": "rejected", "symbol": tick.symbol, "reason": "near-duplicate tick"}

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
