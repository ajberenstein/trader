#!/usr/bin/env python3
"""
MCP Server for Trader - Claude for Work Integration

This MCP server exposes trading functions to Claude for Work, allowing
autonomous trading without expensive API calls.

Usage:
    python mcp_server.py

The server will start on a configurable port and expose tools that Claude
can discover and use automatically.
"""

import asyncio
import json
import os
from typing import Any, Sequence
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route
from starlette.responses import JSONResponse
from uvicorn import Config, Server as UvicornServer

# Import our trading modules
from trader import AlpacaConnector, MarketDataHandler, TradingHandler
from trader.data_utils import fetch_yahoo_data
from trader import Backtester, SimpleDipStrategy, MomentumStrategy

class TradingMCPServer:
    """MCP Server that provides trading tools to Claude."""

    def __init__(self):
        self.connector = None
        self.market = None
        self.trading = None
        self.backtester = Backtester(initial_capital=10000)

    async def initialize_trading(self) -> bool:
        """Initialize trading connections."""
        try:
            self.connector = AlpacaConnector()
            if self.connector.connect():
                self.market = MarketDataHandler(self.connector)
                self.trading = TradingHandler(self.connector)
                return True
            return False
        except Exception as e:
            print(f"❌ Trading initialization failed: {e}")
            return False

    async def check_account(self) -> dict[str, Any]:
        """Check account status."""
        if not self.connector:
            return {"error": "Trading connector not initialized"}

        try:
            account = self.connector.get_account()
            return {
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "trading_mode": account.trading_mode
            }
        except Exception as e:
            return {"error": f"Failed to get account info: {str(e)}"}

    async def get_price_history(self, symbol: str, days: int = 20) -> dict[str, Any]:
        """Get price history for analysis."""
        if not self.market:
            return {"error": "Market data handler not initialized"}

        try:
            stats = self.market.get_price_range(symbol, days=days)
            return {
                "symbol": symbol,
                "current_price": float(stats["current_price"]),
                "min_price": float(stats["min_price"]),
                "max_price": float(stats["max_price"]),
                "change_percent": float(stats["change_pct"]),
                "period_days": days
            }
        except Exception as e:
            return {"error": f"Failed to get price history: {str(e)}"}

    async def place_order(self, symbol: str, quantity: float, side: str) -> dict[str, Any]:
        """Place a buy or sell order."""
        if not self.trading:
            return {"error": "Trading handler not initialized"}

        try:
            if side.lower() == "buy":
                order = self.trading.buy(symbol, quantity)
            elif side.lower() == "sell":
                order = self.trading.sell(symbol, quantity)
            else:
                return {"error": f"Invalid side: {side}. Must be 'buy' or 'sell'"}

            return {
                "order_id": order.id,
                "status": order.status,
                "symbol": order.symbol,
                "quantity": float(order.qty),
                "side": order.side,
                "type": order.type
            }
        except Exception as e:
            return {"error": f"Failed to place order: {str(e)}"}

    async def backtest_strategy(self, symbol: str, strategy: str, period: str = "1y") -> dict[str, Any]:
        """Run a backtest on a trading strategy."""
        try:
            # Get historical data
            data = fetch_yahoo_data(symbol, period=period)

            # Select strategy
            if strategy == "simple_dip":
                strat = SimpleDipStrategy()
            elif strategy == "momentum":
                strat = MomentumStrategy()
            else:
                return {"error": f"Unknown strategy: {strategy}"}

            # Run backtest
            results = self.backtester.run(strat, data)

            return {
                "symbol": symbol,
                "strategy": strategy,
                "period": period,
                "total_return": float(results.total_return),
                "total_trades": results.total_trades,
                "winning_trades": results.winning_trades,
                "win_rate": float(results.win_rate),
                "data_points": len(data)
            }
        except Exception as e:
            return {"error": f"Failed to run backtest: {str(e)}"}


# Create MCP server instance — allow external host (behind Caddy reverse proxy)
server = FastMCP("trading-tools", transport_security=TransportSecuritySettings(
    allowed_hosts=["trader.137-184-12-167.sslip.io", "127.0.0.1:*", "localhost:*", "[::1]:*"]
))
trading_server = TradingMCPServer()


async def health_endpoint(request):
    """HTTP health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "trading_connection": trading_server.connector is not None,
        "market_data": trading_server.market is not None,
        "version": "1.0.0"
    })


# Use FastMCP's own Starlette app directly (preserves lifespan/task group init).
# Add /health as a route on the same app.
app = server.streamable_http_app()
app.routes.insert(0, Route("/health", health_endpoint))


@server.tool()
async def check_account() -> str:
    """Get current account status, showing cash balance, portfolio value, and buying power."""
    result = await trading_server.check_account()
    return json.dumps(result, indent=2)


@server.tool()
async def get_price_history(symbol: str, days: int = 20) -> str:
    """Retrieve historical price data for a symbol to analyze trends."""
    result = await trading_server.get_price_history(symbol, days)
    return json.dumps(result, indent=2)


@server.tool()
async def place_order(symbol: str, quantity: float, side: str) -> str:
    """Place a buy or sell order for a security."""
    result = await trading_server.place_order(symbol, quantity, side)
    return json.dumps(result, indent=2)


@server.tool()
async def backtest_strategy(symbol: str, strategy: str, period: str = "1y") -> str:
    """Run a backtest on a trading strategy to evaluate performance."""
    result = await trading_server.backtest_strategy(symbol, strategy, period)
    return json.dumps(result, indent=2)


@server.tool()
async def get_market_comparison(symbols: str) -> str:
    """Compare multiple symbols' performance."""
    if not trading_server.market:
        return json.dumps({"error": "Market data handler not initialized"})

    try:
        symbol_list = [s.strip() for s in symbols.split(",")]
        comparison = trading_server.market.compare_symbols(symbol_list)
        return json.dumps(comparison, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to compare symbols: {str(e)}"})


@server.tool()
async def health_check() -> str:
    """Check server health and connectivity."""
    health_status = {
        "status": "healthy",
        "timestamp": "2026-03-24T12:00:00Z",  # Would use datetime in real implementation
        "trading_connection": trading_server.connector is not None,
        "market_data": trading_server.market is not None,
        "version": "1.0.0"
    }
    return json.dumps(health_status, indent=2)


async def run_http_server():
    """Run the HTTP health check server."""
    config = Config(app=app, host="0.0.0.0", port=8080, log_level="info", proxy_headers=True, forwarded_allow_ips="*")
    http_server = UvicornServer(config)
    await http_server.serve()


async def main():
    """Main function."""
    print("🤖 Starting Trader MCP Server with Health Check")
    print("=" * 50)

    # Initialize trading connections
    if not await trading_server.initialize_trading():
        print("❌ Failed to initialize trading connections. Check your .env file.")
        return

    print("✅ Trading connections initialized successfully!")
    print("🚀 Server ready for Claude Code connections")
    print("📊 Health check: http://0.0.0.0:8080/health")
    print("🔌 MCP endpoint: http://0.0.0.0:8080/mcp")

    await run_http_server()


if __name__ == "__main__":
    asyncio.run(main())