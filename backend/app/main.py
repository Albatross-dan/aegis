from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db

app = FastAPI(
    title="AEGIS - Artificial Financial Intelligence Platform",
    description="Institutional-grade AI Financial Intelligence Platform - Backend API",
    version="0.1.0",
)

@app.get("/")
def root():
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
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "connected" else "degraded",
        "database": db_status,
    }
