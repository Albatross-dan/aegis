from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from app.core.logging_config import logger

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
