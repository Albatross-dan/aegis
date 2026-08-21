from sqlalchemy import Column, String, Float, DateTime, BigInteger
from app.db.session import Base


class MarketTick(Base):
    __tablename__ = "market_ticks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), primary_key=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    broker_symbol = Column(String(30), nullable=False)
    bid = Column(Float, nullable=False)
    ask = Column(Float, nullable=False)
    source = Column(String(30), nullable=False, default="mt5_exness")


class RejectedTick(Base):
    __tablename__ = "rejected_ticks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=True)
    symbol = Column(String(20), nullable=True)
    broker_symbol = Column(String(20), nullable=True)
    bid = Column(Float, nullable=True)
    ask = Column(Float, nullable=True)
    source = Column(String(50), nullable=True)
    rejection_reason = Column(String(255), nullable=False)
