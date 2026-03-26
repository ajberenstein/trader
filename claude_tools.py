#!/usr/bin/env python3
"""
Claude Tools Wrapper for Trader

This script provides a complete integration between the Trader connector
and Claude's tool-calling capabilities. It defines the trading tools that
Claude can use for autonomous trading decisions.

Usage:
    python claude_tools.py

Requirements:
    - anthropic >= 0.7.0
    - trader package
"""

import json
import os
from typing import Dict, Any, List
from trader import AlpacaConnector, MarketDataHandler, TradingHandler
from trader.data_utils import fetch_yahoo_data
from trader import Backtester, SimpleDipStrategy, MomentumStrategy

# Claude tools definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_account",
            "description": "Get current account status, showing cash balance, portfolio value, and buying power",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_history",
            "description": "Retrieve historical price data for a symbol to analyze trends",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol (e.g., 'AAPL')"},
                    "days": {"type": "integer", "description": "Number of days of history to retrieve", "default": 20}
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Place a buy or sell order for a security",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol"},
                    "quantity": {"type": "number", "description": "Number of shares"},
                    "side": {"type": "string", "enum": ["buy", "sell"], "description": "Buy or sell"}
                },
                "required": ["symbol", "quantity", "side"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "backtest_strategy",
            "description": "Run a backtest on a trading strategy to evaluate performance",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock symbol to backtest"},
                    "strategy": {"type": "string", "enum": ["simple_dip", "momentum"], "description": "Strategy to test"},
                    "period": {"type": "string", "description": "Time period (e.g., '1y', '6mo')", "default": "1y"}
                },
                "required": ["symbol", "strategy"]
            }
        }
    }
]

class ClaudeTradingTools:
    """Handles Claude tool calls for trading operations."""

    def __init__(self):
        self.connector = None
        self.market = None
        self.trading = None
        self.backtester = Backtester(initial_capital=10000)

    def initialize(self) -> bool:
        """Initialize the trading connection."""
        try:
            self.connector = AlpacaConnector()
            if self.connector.connect():
                self.market = MarketDataHandler(self.connector)
                self.trading = TradingHandler(self.connector)
                return True
            return False
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            return False

    def check_account(self) -> Dict[str, Any]:
        """Handle check_account tool call."""
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

    def get_price_history(self, symbol: str, days: int = 20) -> Dict[str, Any]:
        """Handle get_price_history tool call."""
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

    def place_order(self, symbol: str, quantity: float, side: str) -> Dict[str, Any]:
        """Handle place_order tool call."""
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

    def backtest_strategy(self, symbol: str, strategy: str, period: str = "1y") -> Dict[str, Any]:
        """Handle backtest_strategy tool call."""
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

    def handle_tool_call(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Route tool calls to appropriate handlers."""
        if tool_name == "check_account":
            return self.check_account()
        elif tool_name == "get_price_history":
            return self.get_price_history(**tool_input)
        elif tool_name == "place_order":
            return self.place_order(**tool_input)
        elif tool_name == "backtest_strategy":
            return self.backtest_strategy(**tool_input)
        else:
            return {"error": f"Unknown tool: {tool_name}"}


def main():
    """Main function for interactive Claude trading."""
    print("🤖 Claude Trading Tools")
    print("=" * 50)

    # Initialize tools
    tools_handler = ClaudeTradingTools()
    if not tools_handler.initialize():
        print("❌ Failed to initialize trading connection. Check your .env file.")
        return

    print("✅ Trading connection initialized successfully!")

    # Check if Anthropic is available
    try:
        import anthropic
        client = anthropic.Anthropic()
    except ImportError:
        print("❌ Anthropic package not installed. Install with: pip install anthropic")
        return
    except Exception as e:
        print(f"❌ Failed to initialize Anthropic client: {e}")
        print("Make sure ANTHROPIC_API_KEY is set in your .env file")
        return

    # System prompt
    system_prompt = """You are an expert trading analyst with access to real-time market data and trading capabilities.

You can:
1. Check account status and available funds
2. Analyze historical price trends
3. Place buy/sell orders
4. Run backtests on trading strategies

Always be conservative and analytical. Before making any trade:
- Check account status first
- Analyze price trends and patterns
- Consider risk management
- Only trade with paper money unless explicitly instructed otherwise

For backtesting: Use it to validate strategies before live trading. Look for strategies with positive returns and reasonable win rates.

Be helpful and explain your reasoning clearly."""

    print("\n💬 Start chatting with Claude about trading!")
    print("Type 'quit' to exit.\n")

    messages = []

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ['quit', 'exit', 'q']:
            break

        messages.append({"role": "user", "content": user_input})

        # Get Claude's response
        try:
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                system=system_prompt,
                tools=TOOLS,
                messages=messages
            )
        except Exception as e:
            print(f"❌ Error calling Claude API: {e}")
            continue

        # Handle tool calls
        tool_calls = []
        assistant_content = []

        for block in response.content:
            if block.type == "text":
                assistant_content.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(block)

        # Execute tool calls
        tool_results = []
        for tool_call in tool_calls:
            print(f"🔧 Claude is calling: {tool_call.name}")
            result = tools_handler.handle_tool_call(tool_call.name, tool_call.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": json.dumps(result, indent=2)
            })
            print(f"✅ Tool result: {result}")

        # Add assistant's response to messages
        messages.append({"role": "assistant", "content": response.content})

        # If there were tool calls, continue the conversation with results
        if tool_results:
            messages.append({"role": "user", "content": tool_results})

            # Get Claude's analysis of the tool results
            try:
                follow_up = client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=2048,
                    system=system_prompt,
                    tools=TOOLS,
                    messages=messages
                )
                for block in follow_up.content:
                    if block.type == "text":
                        assistant_content.append(block.text)
            except Exception as e:
                print(f"❌ Error in follow-up: {e}")

        # Print Claude's response
        print(f"\n🤖 Claude: {''.join(assistant_content)}\n")


if __name__ == "__main__":
    main()