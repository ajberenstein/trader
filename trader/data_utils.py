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
