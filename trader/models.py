"""Data models for trading operations."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PriceData(BaseModel):
    """Historical price data for a symbol."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    class Config:
        from_attributes = True


class OrderRequest(BaseModel):
    """Request to place a trading order."""

    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    quantity: float = Field(..., description="Number of shares")
    side: str = Field(..., description="'buy' or 'sell'")
    order_type: str = Field(default="market", description="market, limit, stop")
    limit_price: Optional[float] = Field(
        None, description="For limit orders"
    )
    stop_price: Optional[float] = Field(None, description="For stop orders")
    time_in_force: str = Field(default="day", description="day, gtc, opg, cls")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "quantity": 10,
                "side": "buy",
                "order_type": "market",
                "time_in_force": "day",
            }
        }


class Order(BaseModel):
    """Executed order details."""

    id: str
    symbol: str
    quantity: float
    side: str
    order_type: str
    status: str
    filled_qty: float
    filled_avg_price: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Position(BaseModel):
    """Current position in a symbol."""

    symbol: str
    qty: float
    avg_entry_price: float
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pl: Optional[float] = None
    unrealized_plpc: Optional[float] = None

    class Config:
        from_attributes = True


class Account(BaseModel):
    """Account information."""

    account_type: str
    cash: float
    portfolio_value: float
    buying_power: float
    multiplier: int
    trading_mode: str

    class Config:
        from_attributes = True
