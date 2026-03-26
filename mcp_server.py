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
from starlette.responses import JSONResponse, HTMLResponse, RedirectResponse
from starlette.requests import Request
from uvicorn import Config, Server as UvicornServer

# Import our trading modules
from trader import AlpacaConnector, MarketDataHandler, TradingHandler
from trader.data_utils import fetch_yahoo_data, get_fundamentals
from trader import Backtester, SimpleDipStrategy, MomentumStrategy
from mcp_auth import SimpleTokenOAuthProvider, make_auth_settings

SERVER_URL = os.environ.get("MCP_SERVER_URL", "https://trader.137-184-12-167.sslip.io")
MCP_ACCESS_TOKEN = os.environ.get("MCP_ACCESS_TOKEN", "")

oauth_provider = SimpleTokenOAuthProvider(
    valid_token=MCP_ACCESS_TOKEN,
    server_url=SERVER_URL,
)

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
                "quantity": float(order.quantity),
                "side": order.side,
                "type": order.order_type
            }
        except Exception as e:
            return {"error": f"Failed to place order: {str(e)}"}

    async def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get status of a specific order."""
        if not self.trading:
            return {"error": "Trading handler not initialized"}
        try:
            order = self.trading.get_order(order_id)
            if not order:
                return {"error": f"Order {order_id} not found"}
            return {
                "order_id": order.id,
                "symbol": order.symbol,
                "quantity": float(order.quantity),
                "side": order.side,
                "type": order.order_type,
                "status": order.status,
                "filled_qty": float(order.filled_qty),
                "filled_avg_price": float(order.filled_avg_price),
                "created_at": str(order.created_at),
                "updated_at": str(order.updated_at),
            }
        except Exception as e:
            return {"error": f"Failed to get order: {str(e)}"}

    async def list_orders(self, status: str = "all", limit: int = 20) -> dict[str, Any]:
        """List orders with optional status filter."""
        if not self.trading:
            return {"error": "Trading handler not initialized"}
        try:
            orders = self.trading.list_orders(status=status, limit=limit)
            if orders is None:
                return {"error": "Failed to fetch orders"}
            return {
                "orders": [
                    {
                        "order_id": o.id,
                        "symbol": o.symbol,
                        "quantity": float(o.quantity),
                        "side": o.side,
                        "type": o.order_type,
                        "status": o.status,
                        "filled_qty": float(o.filled_qty),
                        "filled_avg_price": float(o.filled_avg_price),
                        "created_at": str(o.created_at),
                    }
                    for o in orders
                ],
                "count": len(orders),
            }
        except Exception as e:
            return {"error": f"Failed to list orders: {str(e)}"}

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a specific open order."""
        if not self.trading:
            return {"error": "Trading handler not initialized"}
        try:
            success = self.trading.cancel_order(order_id)
            if success:
                return {"cancelled": True, "order_id": order_id}
            return {"cancelled": False, "order_id": order_id, "error": "Cancel failed"}
        except Exception as e:
            return {"error": f"Failed to cancel order: {str(e)}"}

    async def cancel_all_orders(self) -> dict[str, Any]:
        """Cancel all open orders."""
        if not self.trading or not self.connector.client:
            return {"error": "Trading handler not initialized"}
        try:
            self.connector.client.cancel_all_orders()
            return {"cancelled": True}
        except Exception as e:
            return {"error": f"Failed to cancel all orders: {str(e)}"}

    async def get_positions(self) -> dict[str, Any]:
        """Get all open positions."""
        if not self.connector:
            return {"error": "Trading connector not initialized"}
        try:
            positions = self.connector.get_positions()
            if positions is None:
                return {"error": "Failed to fetch positions"}
            return {
                "positions": [
                    {
                        "symbol": p.symbol,
                        "qty": float(p.qty),
                        "avg_entry_price": float(p.avg_entry_price),
                        "current_price": float(p.current_price),
                        "market_value": float(p.market_value),
                        "unrealized_pl": float(p.unrealized_pl),
                        "unrealized_plpc": float(p.unrealized_plpc),
                    }
                    for p in positions.values()
                ],
                "count": len(positions),
            }
        except Exception as e:
            return {"error": f"Failed to get positions: {str(e)}"}

    async def get_position(self, symbol: str) -> dict[str, Any]:
        """Get position for a specific symbol."""
        if not self.connector:
            return {"error": "Trading connector not initialized"}
        try:
            p = self.connector.get_position(symbol)
            if not p:
                return {"error": f"No open position for {symbol}"}
            return {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "avg_entry_price": float(p.avg_entry_price),
                "current_price": float(p.current_price),
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
            }
        except Exception as e:
            return {"error": f"Failed to get position: {str(e)}"}

    async def place_limit_order(self, symbol: str, quantity: float, side: str, limit_price: float) -> dict[str, Any]:
        """Place a limit order."""
        if not self.trading:
            return {"error": "Trading handler not initialized"}
        try:
            order = self.trading.place_limit_order(symbol, quantity, side, limit_price)
            if not order:
                return {"error": "Failed to place limit order"}
            return {"order_id": order.id, "status": order.status, "symbol": order.symbol,
                    "quantity": float(order.quantity), "side": order.side, "type": order.order_type,
                    "limit_price": limit_price}
        except Exception as e:
            return {"error": f"Failed to place limit order: {str(e)}"}

    async def place_stop_order(self, symbol: str, quantity: float, side: str, stop_price: float) -> dict[str, Any]:
        """Place a stop order."""
        if not self.trading:
            return {"error": "Trading handler not initialized"}
        try:
            order = self.trading.place_stop_order(symbol, quantity, side, stop_price)
            if not order:
                return {"error": "Failed to place stop order"}
            return {"order_id": order.id, "status": order.status, "symbol": order.symbol,
                    "quantity": float(order.quantity), "side": order.side, "type": order.order_type,
                    "stop_price": stop_price}
        except Exception as e:
            return {"error": f"Failed to place stop order: {str(e)}"}

    async def place_bracket_order(
        self, symbol: str, quantity: float, side: str,
        take_profit_price: float, stop_loss_price: float
    ) -> dict[str, Any]:
        """Place a bracket order (entry + take-profit + stop-loss)."""
        if not self.trading:
            return {"error": "Trading handler not initialized"}
        try:
            order = self.trading.place_bracket_order(symbol, quantity, side, take_profit_price, stop_loss_price)
            if not order:
                return {"error": "Failed to place bracket order"}
            return {"order_id": order.id, "status": order.status, "symbol": order.symbol,
                    "quantity": float(order.quantity), "side": order.side,
                    "take_profit_price": take_profit_price, "stop_loss_price": stop_loss_price}
        except Exception as e:
            return {"error": f"Failed to place bracket order: {str(e)}"}

    async def modify_order(self, order_id: str, qty: float = None, limit_price: float = None, stop_price: float = None) -> dict[str, Any]:
        """Modify an open order."""
        if not self.trading:
            return {"error": "Trading handler not initialized"}
        try:
            order = self.trading.modify_order(order_id, qty=qty, limit_price=limit_price, stop_price=stop_price)
            if not order:
                return {"error": f"Failed to modify order {order_id}"}
            return {"order_id": order.id, "status": order.status, "symbol": order.symbol,
                    "quantity": float(order.quantity), "type": order.order_type}
        except Exception as e:
            return {"error": f"Failed to modify order: {str(e)}"}

    async def get_ohlcv(self, symbol: str, timeframe: str = "1Day", limit: int = 50) -> dict[str, Any]:
        """Get OHLCV bars."""
        if not self.market:
            return {"error": "Market data handler not initialized"}
        try:
            bars = self.market.get_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if bars is None:
                return {"error": f"No data for {symbol}"}
            return {"symbol": symbol, "timeframe": timeframe, "bars": bars, "count": len(bars)}
        except Exception as e:
            return {"error": f"Failed to get OHLCV: {str(e)}"}

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        """Get latest bid/ask quote."""
        if not self.market:
            return {"error": "Market data handler not initialized"}
        try:
            quote = self.market.get_quote(symbol)
            if quote is None:
                return {"error": f"No quote available for {symbol}"}
            return quote
        except Exception as e:
            return {"error": f"Failed to get quote: {str(e)}"}

    async def get_fundamentals_data(self, symbol: str) -> dict[str, Any]:
        """Get fundamental data via Yahoo Finance."""
        try:
            data = get_fundamentals(symbol)
            if data is None:
                return {"error": f"No fundamental data for {symbol}"}
            return data
        except Exception as e:
            return {"error": f"Failed to get fundamentals: {str(e)}"}

    async def search_symbols_data(self, query: str) -> dict[str, Any]:
        """Search symbols by name or ticker."""
        if not self.market:
            return {"error": "Market data handler not initialized"}
        try:
            results = self.market.search_symbols(query)
            if results is None:
                return {"error": "Search failed"}
            return {"query": query, "results": results, "count": len(results)}
        except Exception as e:
            return {"error": f"Failed to search symbols: {str(e)}"}

    async def get_portfolio_history_data(self, period: str = "1M", timeframe: str = "1D") -> dict[str, Any]:
        """Get portfolio equity history."""
        if not self.connector:
            return {"error": "Trading connector not initialized"}
        try:
            history = self.connector.get_portfolio_history(period=period, timeframe=timeframe)
            if history is None:
                return {"error": "Failed to fetch portfolio history"}
            return history
        except Exception as e:
            return {"error": f"Failed to get portfolio history: {str(e)}"}

    async def get_pnl_summary(self) -> dict[str, Any]:
        """Get P&L summary from account and open positions."""
        if not self.connector:
            return {"error": "Trading connector not initialized"}
        try:
            account = self.connector.get_account()
            positions = self.connector.get_positions() or {}
            unrealized_pl = sum(p.unrealized_pl for p in positions.values())
            unrealized_plpc = (
                sum(p.unrealized_plpc for p in positions.values()) / len(positions)
                if positions else 0.0
            )
            return {
                "cash": float(account.cash),
                "portfolio_value": float(account.portfolio_value),
                "buying_power": float(account.buying_power),
                "open_positions": len(positions),
                "unrealized_pl": round(unrealized_pl, 2),
                "unrealized_pl_pct": round(float(unrealized_plpc) * 100, 2),
            }
        except Exception as e:
            return {"error": f"Failed to get P&L summary: {str(e)}"}

    async def get_trade_history_data(self, limit: int = 50) -> dict[str, Any]:
        """Get recent executed trades."""
        if not self.connector:
            return {"error": "Trading connector not initialized"}
        try:
            trades = self.connector.get_trade_history(limit=limit)
            if trades is None:
                return {"error": "Failed to fetch trade history"}
            return {"trades": trades, "count": len(trades)}
        except Exception as e:
            return {"error": f"Failed to get trade history: {str(e)}"}

    async def backtest_strategy(self, symbol: str, strategy: str, period: str = "1y") -> dict[str, Any]:
        """Run a backtest on a trading strategy."""
        try:
            # Convert period string to days
            period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730}
            days = period_days.get(period, 365)
            data = fetch_yahoo_data(symbol, days=days)

            # Select strategy
            if strategy == "simple_dip":
                strat = SimpleDipStrategy()
            elif strategy == "momentum":
                strat = MomentumStrategy()
            else:
                return {"error": f"Unknown strategy: {strategy}"}

            # Run backtest
            results = self.backtester.run(symbol, data, strat)

            return {
                "symbol": symbol,
                "strategy": strategy,
                "period": period,
                "total_return_pct": float(results.total_profit_pct),
                "total_trades": results.num_trades,
                "winning_trades": results.winning_trades,
                "win_rate_pct": float(results.win_rate_pct),
                "data_points": len(data)
            }
        except Exception as e:
            return {"error": f"Failed to run backtest: {str(e)}"}


# Create MCP server instance
server = FastMCP(
    "trading-tools",
    auth_server_provider=oauth_provider,
    auth=make_auth_settings(SERVER_URL),
    transport_security=TransportSecuritySettings(
        allowed_hosts=["trader.137-184-12-167.sslip.io", "127.0.0.1:*", "localhost:*", "[::1]:*"]
    ),
)
trading_server = TradingMCPServer()


async def health_endpoint(request: Request):
    """HTTP health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "trading_connection": trading_server.connector is not None,
        "market_data": trading_server.market is not None,
        "version": "1.0.0"
    })


async def login_get(request: Request):
    """Show the token login form."""
    return HTMLResponse(oauth_provider.login_form(dict(request.query_params)))


async def login_post(request: Request):
    """Handle token submission, redirect back to Claude with auth code."""
    form = dict(await request.form())
    redirect_url, error = oauth_provider.validate_and_create_code(form)
    if error:
        return HTMLResponse(oauth_provider.login_form(form, error=error), status_code=401)
    return RedirectResponse(redirect_url, status_code=302)


# Use FastMCP's own Starlette app directly (preserves lifespan/task group init).
# Add /health and /login routes on the same app.
app = server.streamable_http_app()
app.routes.insert(0, Route("/health", health_endpoint))
app.routes.insert(1, Route("/login", login_get, methods=["GET"]))
app.routes.insert(2, Route("/login", login_post, methods=["POST"]))


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
async def get_order_status(order_id: str) -> str:
    """Get the status and details of a specific order by its ID."""
    result = await trading_server.get_order_status(order_id)
    return json.dumps(result, indent=2)


@server.tool()
async def list_orders(status: str = "all", limit: int = 20) -> str:
    """List orders. Status can be: all, open, closed, filled, cancelled, pending_new."""
    result = await trading_server.list_orders(status, limit)
    return json.dumps(result, indent=2)


@server.tool()
async def cancel_order(order_id: str) -> str:
    """Cancel a specific open order by its ID."""
    result = await trading_server.cancel_order(order_id)
    return json.dumps(result, indent=2)


@server.tool()
async def cancel_all_orders() -> str:
    """Cancel all open orders."""
    result = await trading_server.cancel_all_orders()
    return json.dumps(result, indent=2)


@server.tool()
async def get_positions() -> str:
    """Get all open positions with P&L information."""
    result = await trading_server.get_positions()
    return json.dumps(result, indent=2)


@server.tool()
async def get_position(symbol: str) -> str:
    """Get the open position for a specific symbol."""
    result = await trading_server.get_position(symbol)
    return json.dumps(result, indent=2)


@server.tool()
async def place_limit_order(symbol: str, quantity: float, side: str, limit_price: float) -> str:
    """Place a limit order. Executes only if the market reaches limit_price."""
    result = await trading_server.place_limit_order(symbol, quantity, side, limit_price)
    return json.dumps(result, indent=2)


@server.tool()
async def place_stop_order(symbol: str, quantity: float, side: str, stop_price: float) -> str:
    """Place a stop order. Triggers a market order when price reaches stop_price."""
    result = await trading_server.place_stop_order(symbol, quantity, side, stop_price)
    return json.dumps(result, indent=2)


@server.tool()
async def place_bracket_order(
    symbol: str, quantity: float, side: str,
    take_profit_price: float, stop_loss_price: float
) -> str:
    """Place a bracket order: market entry with automatic take-profit and stop-loss legs."""
    result = await trading_server.place_bracket_order(symbol, quantity, side, take_profit_price, stop_loss_price)
    return json.dumps(result, indent=2)


@server.tool()
async def modify_order(order_id: str, qty: float = None, limit_price: float = None, stop_price: float = None) -> str:
    """Modify an open order's quantity, limit price, or stop price."""
    result = await trading_server.modify_order(order_id, qty=qty, limit_price=limit_price, stop_price=stop_price)
    return json.dumps(result, indent=2)


@server.tool()
async def get_ohlcv(symbol: str, timeframe: str = "1Day", limit: int = 50) -> str:
    """Get OHLCV candlestick bars. Timeframes: 1Min, 5Min, 15Min, 1Hour, 1Day."""
    result = await trading_server.get_ohlcv(symbol, timeframe, limit)
    return json.dumps(result, indent=2)


@server.tool()
async def get_quote(symbol: str) -> str:
    """Get real-time bid/ask quote with spread for a symbol."""
    result = await trading_server.get_quote(symbol)
    return json.dumps(result, indent=2)


@server.tool()
async def get_fundamentals(symbol: str) -> str:
    """Get fundamental data: P/E ratio, EPS, market cap, sector, 52-week range, etc."""
    result = await trading_server.get_fundamentals_data(symbol)
    return json.dumps(result, indent=2)


@server.tool()
async def search_symbols(query: str) -> str:
    """Search for tradable US equity symbols by company name or ticker prefix."""
    result = await trading_server.search_symbols_data(query)
    return json.dumps(result, indent=2)


@server.tool()
async def list_strategies() -> str:
    """List all available backtesting strategies with descriptions."""
    strategies = {
        "strategies": [
            {
                "name": "simple_dip",
                "description": "Buys when price drops significantly below its recent average, sells on recovery.",
            },
            {
                "name": "momentum",
                "description": "Buys when price is trending up (short MA > long MA), sells when trend reverses.",
            },
        ]
    }
    return json.dumps(strategies, indent=2)


@server.tool()
async def get_backtest_trades(symbol: str, strategy: str, period: str = "1y") -> str:
    """Run a backtest and return the individual trade-by-trade detail."""
    try:
        period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730}
        days = period_days.get(period, 365)
        data = fetch_yahoo_data(symbol, days=days)
        if strategy == "simple_dip":
            from trader import SimpleDipStrategy
            strat = SimpleDipStrategy()
        elif strategy == "momentum":
            from trader import MomentumStrategy
            strat = MomentumStrategy()
        else:
            return json.dumps({"error": f"Unknown strategy: {strategy}"})
        from trader import Backtester
        results = Backtester(initial_capital=10000).run(symbol, data, strat)
        trades = [
            {
                "entry_date": t.entry_date.isoformat(),
                "entry_price": round(t.entry_price, 4),
                "exit_date": t.exit_date.isoformat(),
                "exit_price": round(t.exit_price, 4),
                "shares": t.shares,
                "profit": round(t.profit, 2),
                "return_pct": round(t.return_pct, 2),
                "duration_days": t.duration_days,
            }
            for t in results.trades
        ]
        return json.dumps({
            "symbol": symbol, "strategy": strategy, "period": period,
            "total_return_pct": round(float(results.total_profit_pct), 2),
            "num_trades": results.num_trades,
            "trades": trades,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to get backtest trades: {str(e)}"})


@server.tool()
async def backtest_multi_symbol(symbols: str, strategy: str, period: str = "1y") -> str:
    """Run the same strategy across multiple symbols. symbols is comma-separated (e.g. 'AAPL,MSFT,TSLA')."""
    try:
        period_days = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730}
        days = period_days.get(period, 365)
        if strategy == "simple_dip":
            from trader import SimpleDipStrategy as Strat
        elif strategy == "momentum":
            from trader import MomentumStrategy as Strat
        else:
            return json.dumps({"error": f"Unknown strategy: {strategy}"})
        from trader import Backtester
        backtester = Backtester(initial_capital=10000)
        results = {}
        for sym in [s.strip() for s in symbols.split(",")]:
            data = fetch_yahoo_data(sym, days=days)
            if not data:
                results[sym] = {"error": "No data available"}
                continue
            r = backtester.run(sym, data, Strat())
            results[sym] = {
                "total_return_pct": round(float(r.total_profit_pct), 2),
                "num_trades": r.num_trades,
                "win_rate_pct": round(float(r.win_rate_pct), 2),
                "max_drawdown_pct": round(float(r.max_drawdown_pct), 2),
            }
        return json.dumps({"strategy": strategy, "period": period, "results": results}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to run multi-symbol backtest: {str(e)}"})


@server.tool()
async def get_portfolio_history(period: str = "1M", timeframe: str = "1D") -> str:
    """Get portfolio equity curve. period: 1D,1W,1M,3M,6M,1A,all. timeframe: 1Min,5Min,15Min,1H,1D."""
    result = await trading_server.get_portfolio_history_data(period, timeframe)
    return json.dumps(result, indent=2)


@server.tool()
async def get_pnl_summary() -> str:
    """Get P&L summary: cash, portfolio value, unrealized gains/losses across all open positions."""
    result = await trading_server.get_pnl_summary()
    return json.dumps(result, indent=2)


@server.tool()
async def get_trade_history(limit: int = 50) -> str:
    """Get history of executed trades (fills) ordered by most recent first."""
    result = await trading_server.get_trade_history_data(limit)
    return json.dumps(result, indent=2)


@server.tool()
async def health_check() -> str:
    """Check server health and connectivity."""
    from datetime import datetime, timezone
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
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