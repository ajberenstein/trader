"""Market data handler - retrieves historical price data."""

from typing import Optional, List
from datetime import datetime, timedelta
import pandas as pd
import logging
from .alpaca_connector import AlpacaConnector
from .models import PriceData
from .config import Config

logger = logging.getLogger(__name__)


class MarketDataHandler:
    """
    Handles historical market data retrieval from Alpaca.
    """

    def __init__(self, connector: AlpacaConnector):
        """
        Initialize market data handler.

        Args:
            connector: Connected AlpacaConnector instance
        """
        self.connector = connector

    def get_historical_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        limit: int = 100,
        end_date: Optional[datetime] = None,
    ) -> Optional[List[PriceData]]:
        """
        Get historical price bars for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            timeframe: Time frame ('1Min', '5Min', '15Min', '1H', '1Day', etc.)
            limit: Number of bars to retrieve (max 10000)
            end_date: End date for historical data (defaults to today)

        Returns:
            List of PriceData objects, or None if error.

        Example:
            >>> data = handler.get_historical_bars('AAPL', '1Day', limit=20)
            >>> for price in data:
            ...     print(f"{price.symbol}: {price.close}")
        """
        if not self.connector.is_connected or not self.connector.client:
            logger.warning(
                "Not connected to Alpaca. Call connector.connect() first."
            )
            return None

        try:
            if end_date is None:
                end_date = datetime.now()
            
            # Format end_date as RFC3339 (YYYY-MM-DD format) for Alpaca API
            if hasattr(end_date, 'date'):
                end_date = end_date.date()

            bars = self.connector.client.get_bars(
                symbol,
                timeframe,
                limit=limit,
                end=end_date,
                feed="iex",
            )

            price_data = [
                PriceData(
                    symbol=symbol,
                    timestamp=bar.t,
                    open=float(bar.o),
                    high=float(bar.h),
                    low=float(bar.l),
                    close=float(bar.c),
                    volume=int(bar.v),
                )
                for bar in bars
            ]

            logger.info(
                f"Retrieved {len(price_data)} bars for {symbol} ({timeframe})"
            )
            return price_data

        except Exception as e:
            logger.error(
                f"Error retrieving bars for {symbol}: {str(e)}"
            )
            return None

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        Get the latest price for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Latest close price, or None if error.
        """
        if not self.connector.is_connected or not self.connector.client:
            logger.warning(
                "Not connected to Alpaca. Call connector.connect() first."
            )
            return None

        try:
            quote = self.connector.client.get_latest_trade(symbol)
            return float(quote.price) if quote else None
        except Exception as e:
            logger.error(f"Error retrieving latest price for {symbol}: {str(e)}")
            return None

    def get_price_range(
        self,
        symbol: str,
        days: int = 30,
        timeframe: str = "1Day",
    ) -> Optional[dict]:
        """
        Get price statistics (high, low, change) for a period.

        Args:
            symbol: Stock symbol
            days: Number of days to look back
            timeframe: Timeframe for bars

        Returns:
            Dictionary with price statistics or None if error.

        Example:
            >>> stats = handler.get_price_range('AAPL', days=30)
            >>> print(f"52-week range: {stats['min']} - {stats['max']}")
        """
        bars = self.get_historical_bars(
            symbol, timeframe=timeframe, limit=days
        )

        if not bars or len(bars) == 0:
            return None

        closes = [bar.close for bar in bars]
        return {
            "symbol": symbol,
            "current_price": closes[-1],
            "min_price": min(closes),
            "max_price": max(closes),
            "avg_price": sum(closes) / len(closes),
            "change_pct": ((closes[-1] - closes[0]) / closes[0]) * 100,
            "periods_analyzed": len(bars),
        }

    def get_ohlcv(
        self, symbol: str, timeframe: str = "1Day", limit: int = 50
    ) -> Optional[List[dict]]:
        """Return OHLCV bars as a list of dicts."""
        bars = self.get_historical_bars(symbol, timeframe=timeframe, limit=limit)
        if not bars:
            return None
        return [
            {
                "timestamp": bar.timestamp.isoformat(),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]

    def get_quote(self, symbol: str) -> Optional[dict]:
        """Return latest bid/ask quote."""
        if not self.connector.is_connected or not self.connector.client:
            return None
        try:
            quote = self.connector.client.get_latest_quote(symbol, feed="iex")
            raw = getattr(quote, "_raw", {})
            bid = float(raw.get("bp", 0))
            ask = float(raw.get("ap", 0))
            return {
                "symbol": symbol,
                "bid": bid,
                "ask": ask,
                "spread": round(ask - bid, 4),
                "bid_size": int(raw.get("bs", 0)),
                "ask_size": int(raw.get("as", 0)),
            }
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {str(e)}")
            return None

    def search_symbols(self, query: str, limit: int = 10) -> Optional[List[dict]]:
        """Search tradable US equity symbols by ticker or company name."""
        if not self.connector.is_connected or not self.connector.client:
            return None
        try:
            assets = self.connector.client.list_assets(
                status="active", asset_class="us_equity"
            )
            q = query.lower()
            results = [
                {
                    "symbol": a.symbol,
                    "name": getattr(a, "name", ""),
                    "exchange": getattr(a, "exchange", ""),
                    "tradable": getattr(a, "tradable", False),
                }
                for a in assets
                if q in a.symbol.lower() or q in (getattr(a, "name", "") or "").lower()
            ]
            return results[:limit]
        except Exception as e:
            logger.error(f"Error searching symbols: {str(e)}")
            return None

    def compare_symbols(
        self, symbols: List[str], timeframe: str = "1Day", limit: int = 100
    ) -> Optional[dict]:
        """
        Compare price performance across multiple symbols.

        Args:
            symbols: List of stock symbols
            timeframe: Timeframe for bars
            limit: Number of bars per symbol

        Returns:
            Dictionary comparing symbols or None if error.
        """
        results = {}
        for symbol in symbols:
            stats = self.get_price_range(symbol, days=limit, timeframe=timeframe)
            if stats:
                results[symbol] = stats

        return results if results else None
