"""Data fetching utilities for historical data from free sources."""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
from .models import PriceData

logger = logging.getLogger(__name__)


def fetch_yahoo_data(
    symbol: str,
    days: int = 365,
    end_date: Optional[datetime] = None
) -> Optional[List[PriceData]]:
    """
    Fetch historical data from Yahoo Finance (free, no subscription needed).

    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        days: Number of days of history to retrieve
        end_date: End date (defaults to today)

    Returns:
        List of PriceData objects or None if error
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return None

    try:
        if end_date is None:
            end_date = datetime.now()

        start_date = end_date - timedelta(days=days)

        # Fetch data
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)

        if df.empty:
            logger.error(f"No data found for {symbol}")
            return None

        # Convert to PriceData
        price_data = []
        for date, row in df.iterrows():
            price_data.append(
                PriceData(
                    symbol=symbol,
                    timestamp=date.to_pydatetime(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                )
            )

        logger.info(f"Retrieved {len(price_data)} bars for {symbol} from Yahoo Finance")
        return price_data

    except Exception as e:
        logger.error(f"Error fetching data from Yahoo Finance: {str(e)}")
        return None


def fetch_yahoo_intraday(
    symbol: str,
    interval: str = "1h",
    days: int = 30,
) -> Optional[List[PriceData]]:
    """
    Fetch intraday OHLCV bars from Yahoo Finance.

    Yahoo Finance intraday limits (hard limits, not configurable):
        "1m"  → max 7 days of history
        "5m"  → max 60 days
        "15m" → max 60 days
        "30m" → max 60 days
        "1h"  → max 730 days (2 years)

    Args:
        symbol:   Stock symbol (e.g. "AAPL")
        interval: Bar size — "1m", "5m", "15m", "30m", "1h"
        days:     How many calendar days of history to request.
                  Capped automatically to the Yahoo Finance limit for the interval.

    Returns:
        List of PriceData objects (oldest → newest), or None on error.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return None

    # Hard caps per interval
    max_days = {"1m": 7, "5m": 60, "15m": 60, "30m": 60, "1h": 730}
    days = min(days, max_days.get(interval, 60))

    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date, interval=interval)

        if df.empty:
            logger.error(f"No intraday data for {symbol} at {interval}")
            return None

        price_data = [
            PriceData(
                symbol=symbol,
                timestamp=date.to_pydatetime(),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
            for date, row in df.iterrows()
        ]
        logger.info(f"Retrieved {len(price_data)} {interval} bars for {symbol} from Yahoo Finance")
        return price_data

    except Exception as e:
        logger.error(f"Error fetching intraday data for {symbol}: {str(e)}")
        return None


def get_fundamentals(symbol: str) -> Optional[dict]:
    """
    Fetch fundamental data for a symbol via Yahoo Finance.

    Returns P/E, EPS, market cap, sector, 52-week range, etc.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return None

    try:
        info = yf.Ticker(symbol).info
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "revenue": info.get("totalRevenue"),
            "profit_margin": info.get("profitMargins"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
        }
    except Exception as e:
        logger.error(f"Error fetching fundamentals for {symbol}: {str(e)}")
        return None
