"""Configuration management for Alpaca connector."""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_PATH)


class Config:
    """Alpaca API configuration."""

    API_KEY = os.getenv("ALPACA_API_KEY", "")
    SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
    BASE_URL = os.getenv(
        "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
    )
    
    # Trading mode: 'paper' or 'live'
    TRADING_MODE = os.getenv("TRADING_MODE", "paper")
    
    # Default timeframe for historical data
    DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1Day")
    
    @classmethod
    def validate(cls):
        """Validate that required credentials are configured."""
        if not cls.API_KEY or not cls.SECRET_KEY:
            raise ValueError(
                "Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in environment"
            )
        return True
