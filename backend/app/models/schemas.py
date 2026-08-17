from pydantic import BaseModel
from datetime import datetime

class TickIn(BaseModel):
    symbol: str
    broker_symbol: str
    bid: float
    ask: float
    timestamp: datetime
    source: str = "mt5_exness"
