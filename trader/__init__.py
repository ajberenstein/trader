"""
Trader: A modular connector for algorithmic trading via Claude agents.
Interfaces with Alpaca Markets API for paper and live trading.
"""

from .alpaca_connector import AlpacaConnector
from .market_data import MarketDataHandler
from .trading import TradingHandler
from .backtester import Backtester, BacktestResult, Trade
from .strategy import (
    Strategy, SimpleDipStrategy, MomentumStrategy,
    RSIOversoldStrategy, BollingerBandsStrategy, MACDCrossoverStrategy,
    MeanReversionStrategy, MACrossoverStrategy,
    QualityDipStrategy, GrowthMomentumStrategy, LowBetaReversionStrategy,
    STRATEGY_REGISTRY, create_strategy,
)
from .models import OrderRequest, PriceData, Position

__version__ = "0.1.0"
__all__ = [
    "AlpacaConnector",
    "MarketDataHandler",
    "TradingHandler",
    "Backtester",
    "BacktestResult",
    "Trade",
    "Strategy",
    "SimpleDipStrategy",
    "MomentumStrategy",
    "RSIOversoldStrategy",
    "BollingerBandsStrategy",
    "MACDCrossoverStrategy",
    "MeanReversionStrategy",
    "MACrossoverStrategy",
    "QualityDipStrategy",
    "GrowthMomentumStrategy",
    "LowBetaReversionStrategy",
    "STRATEGY_REGISTRY",
    "create_strategy",
    "OrderRequest",
    "PriceData",
    "Position",
]
