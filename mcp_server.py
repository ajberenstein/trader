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
from mcp import Server, Tool
from mcp.types import TextContent, PromptMessage
import mcp.server

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
        self.backtester = Backtester(initial_cash=10000)

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


# Create MCP server instance
server = Server("trading-tools")
trading_server = TradingMCPServer()


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


async def main():
    """Main server function."""
    print("🤖 Starting Trading MCP Server...")
    print("=" * 50)

    # Initialize trading connections
    if not await trading_server.initialize_trading():
        print("❌ Failed to initialize trading connections. Check your .env file.")
        return

    print("✅ Trading connections initialized successfully!")
    print("🚀 Server ready for Claude for Work connections")

    # Start MCP server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())