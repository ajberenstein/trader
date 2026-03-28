"""Alpaca API connector - handles authentication and basic connection."""

from alpaca_trade_api import REST
from alpaca_trade_api.entity import Order as AlpacaOrder, Position as AlpacaPosition
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from .config import Config
from .models import Account, Order, Position

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    _ALPACA_DATA_AVAILABLE = True
except ImportError:
    _ALPACA_DATA_AVAILABLE = False

_TF_MAP = {
    "1Min":  lambda: TimeFrame(1,  TimeFrameUnit.Minute),
    "5Min":  lambda: TimeFrame(5,  TimeFrameUnit.Minute),
    "15Min": lambda: TimeFrame(15, TimeFrameUnit.Minute),
    "1Hour": lambda: TimeFrame(1,  TimeFrameUnit.Hour),
} if _ALPACA_DATA_AVAILABLE else {}

logger = logging.getLogger(__name__)


class AlpacaConnector:
    """
    Main connector for Alpaca Markets API.
    Handles authentication, account info, and basic operations.
    """

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize Alpaca connector.

        Args:
            api_key: Alpaca API key (uses env if not provided)
            secret_key: Alpaca secret key (uses env if not provided)
            base_url: API base URL (uses env if not provided)
        """
        self.api_key = api_key or Config.API_KEY
        self.secret_key = secret_key or Config.SECRET_KEY
        self.base_url = base_url or Config.BASE_URL
        self.client: Optional[REST] = None
        self.data_client = None
        self.is_connected = False

    def connect(self) -> bool:
        """
        Establish connection to Alpaca API.

        Returns:
            True if connection successful, False otherwise.

        Raises:
            ValueError: If credentials are missing.
        """
        try:
            if not self.api_key or not self.secret_key:
                raise ValueError(
                    "Missing API credentials. Ensure ALPACA_API_KEY and "
                    "ALPACA_SECRET_KEY are set in .env"
                )

            self.client = REST(
                key_id=self.api_key,
                secret_key=self.secret_key,
                base_url=self.base_url,
            )

            # Verify connection by fetching account
            account = self.client.get_account()
            logger.info(f"✅ Connected to Alpaca API - Account ID: {account.id}")
            self.is_connected = True

            if _ALPACA_DATA_AVAILABLE:
                self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)

            return True

        except Exception as e:
            logger.error(f"❌ Failed to connect to Alpaca API: {str(e)}")
            self.is_connected = False
            return False

    def get_account(self) -> Optional[Account]:
        """
        Get current account information.

        Returns:
            Account object with account details, or None if error.
        """
        if not self.is_connected or not self.client:
            logger.warning("Not connected to Alpaca. Call connect() first.")
            return None

        try:
            account = self.client.get_account()
            account_type = getattr(account, "account_type", None)
            if account_type is None:
                account_type = getattr(account, "account_number", "unknown")

            return Account(
                account_type=account_type,
                cash=float(getattr(account, "cash", 0)),
                portfolio_value=float(getattr(account, "portfolio_value", 0)),
                buying_power=float(getattr(account, "buying_power", 0)),
                multiplier=getattr(account, "multiplier", 1),
                trading_mode="paper" if "paper" in self.base_url else "live",
            )
        except Exception as e:
            logger.error(f"Error fetching account: {str(e)}")
            return None

    def get_positions(self) -> Optional[Dict[str, Position]]:
        """
        Get all open positions.

        Returns:
            Dictionary of symbol -> Position, or None if error.
        """
        if not self.is_connected or not self.client:
            logger.warning("Not connected to Alpaca. Call connect() first.")
            return None

        try:
            positions = self.client.list_positions()
            return {
                pos.symbol: Position(
                    symbol=pos.symbol,
                    qty=float(pos.qty),
                    avg_entry_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    market_value=float(pos.market_value),
                    unrealized_pl=float(pos.unrealized_pl),
                    unrealized_plpc=float(pos.unrealized_plpc),
                )
                for pos in positions
            }
        except Exception as e:
            logger.error(f"Error fetching positions: {str(e)}")
            return None

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get specific position by symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Position object or None if not found.
        """
        if not self.is_connected or not self.client:
            logger.warning("Not connected to Alpaca. Call connect() first.")
            return None

        try:
            pos = self.client.get_position(symbol)
            return Position(
                symbol=pos.symbol,
                qty=float(pos.qty),
                avg_entry_price=float(pos.avg_entry_price),
                current_price=float(pos.current_price),
                market_value=float(pos.market_value),
                unrealized_pl=float(pos.unrealized_pl),
                unrealized_plpc=float(pos.unrealized_plpc),
            )
        except Exception as e:
            logger.error(f"Error fetching position for {symbol}: {str(e)}")
            return None

    def get_portfolio_history(self, period: str = "1M", timeframe: str = "1D") -> Optional[dict]:
        """Return equity curve for the account."""
        if not self.is_connected or not self.client:
            return None
        try:
            history = self.client.get_portfolio_history(period=period, timeframe=timeframe)
            timestamps = history.timestamp or []
            equity = history.equity or []
            profit_loss = history.profit_loss or []
            profit_loss_pct = history.profit_loss_pct or []
            data = [
                {
                    "timestamp": datetime.fromtimestamp(ts).isoformat(),
                    "equity": float(eq) if eq is not None else None,
                    "profit_loss": float(pl) if pl is not None else None,
                    "profit_loss_pct": float(plp) if plp is not None else None,
                }
                for ts, eq, pl, plp in zip(timestamps, equity, profit_loss, profit_loss_pct)
            ]
            return {
                "period": period,
                "timeframe": timeframe,
                "base_value": float(history.base_value),
                "data": data,
            }
        except Exception as e:
            logger.error(f"Error fetching portfolio history: {str(e)}")
            return None

    def get_trade_history(self, limit: int = 50) -> Optional[List[dict]]:
        """Return recent fill activities (executed trades)."""
        if not self.is_connected or not self.client:
            return None
        try:
            activities = self.client.get_activities(activity_type="FILL")
            result = []
            for a in list(activities)[:limit]:
                result.append({
                    "id": getattr(a, "id", None),
                    "symbol": getattr(a, "symbol", None),
                    "side": getattr(a, "side", None),
                    "quantity": float(getattr(a, "qty", 0) or 0),
                    "price": float(getattr(a, "price", 0) or 0),
                    "transaction_time": str(getattr(a, "transaction_time", "")),
                    "order_id": getattr(a, "order_id", None),
                })
            return result
        except Exception as e:
            logger.error(f"Error fetching trade history: {str(e)}")
            return None

    def get_bars(
        self,
        symbol: str,
        start: str,
        end: str,
        timeframe: str = "1Hour",
        feed: str = "iex",
    ) -> Optional[dict]:
        """
        Download historical OHLCV bars via alpaca-py StockHistoricalDataClient.

        Args:
            symbol:    Ticker symbol (e.g. 'AAPL')
            start:     Start date string 'YYYY-MM-DD'
            end:       End date string 'YYYY-MM-DD'
            timeframe: '1Min' | '5Min' | '15Min' | '1Hour'
            feed:      'iex' (free) | 'sip' (paid)

        Returns:
            dict with keys: symbol, timeframe, start, end, count,
                            first_bar, last_bar, bars (list of OHLCV dicts)
        """
        if not _ALPACA_DATA_AVAILABLE or self.data_client is None:
            logger.error("alpaca-py data client not available")
            return None

        if timeframe not in _TF_MAP:
            logger.error(f"Unsupported timeframe: {timeframe}. Use one of {list(_TF_MAP)}")
            return None

        try:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=_TF_MAP[timeframe](),
                start=start,
                end=end,
                adjustment="all",
                feed=feed,
            )
            df = self.data_client.get_stock_bars(req).df.reset_index()

            bars = []
            for row in df.to_dict(orient="records"):
                bar = {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in row.items()}
                bars.append(bar)

            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "feed": feed,
                "start": start,
                "end": end,
                "count": len(bars),
                "first_bar": str(df["timestamp"].iloc[0]) if len(df) else None,
                "last_bar": str(df["timestamp"].iloc[-1]) if len(df) else None,
                "bars": bars,
            }
        except Exception as e:
            logger.error(f"Error fetching bars for {symbol}: {str(e)}")
            return None

    def disconnect(self):
        """Close the connection."""
        self.client = None
        self.data_client = None
        self.is_connected = False
        logger.info("Disconnected from Alpaca API")
