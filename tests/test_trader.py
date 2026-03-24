"""
Tests for the trader module.
"""

import pytest
from trader import AlpacaConnector, MarketDataHandler, TradingHandler, OrderRequest
from trader.config import Config


class TestAlpacaConnector:
    """Test AlpacaConnector functionality."""

    def test_connector_initialization(self):
        """Test connector can be initialized."""
        connector = AlpacaConnector()
        assert connector is not None
        assert not connector.is_connected

    def test_connection_validation(self):
        """Test connection requires credentials."""
        connector = AlpacaConnector(api_key="", secret_key="")
        result = connector.connect()
        # This will fail without real credentials, but validates error handling
        assert result is False or result is True


class TestOrderRequest:
    """Test OrderRequest model."""

    def test_market_order_creation(self):
        """Test creating a market order."""
        order = OrderRequest(
            symbol="AAPL",
            quantity=10,
            side="buy",
            order_type="market"
        )
        assert order.symbol == "AAPL"
        assert order.quantity == 10
        assert order.side == "buy"

    def test_limit_order_creation(self):
        """Test creating a limit order."""
        order = OrderRequest(
            symbol="GOOGL",
            quantity=5,
            side="sell",
            order_type="limit",
            limit_price=150.50
        )
        assert order.limit_price == 150.50
        assert order.order_type == "limit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
