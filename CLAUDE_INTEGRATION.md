# Integrating Trader with Claude Agents

This document explains how to use the Trader connector with Claude for autonomous trading decisions.

## Overview

The Trader connector is designed to be called by Claude agents through tool definitions. Claude can then make trading decisions based on market analysis.

## Implementation Pattern

### 1. Define Claude Tools

When interacting with Claude via the API, define the trading tools:

```json
{
  "tools": [
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
            "days": {"type": "integer", "description": "Number of days of history to retrieve"}
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
    }
  ]
}
```

### 2. Create Tool Handler Functions

```python
from trader import AlpacaConnector, MarketDataHandler, TradingHandler

# Initialize connector once
connector = AlpacaConnector()
connector.connect()

market = MarketDataHandler(connector)
trading = TradingHandler(connector)

def check_account():
    """Handle check_account tool call."""
    account = connector.get_account()
    return {
        "cash": account.cash,
        "portfolio_value": account.portfolio_value,
        "buying_power": account.buying_power
    }

def get_price_history(symbol: str, days: int = 20):
    """Handle get_price_history tool call."""
    stats = market.get_price_range(symbol, days=days)
    return {
        "symbol": symbol,
        "current_price": stats["current_price"],
        "min_price": stats["min_price"],
        "max_price": stats["max_price"],
        "change_percent": stats["change_pct"]
    }

def place_order(symbol: str, quantity: float, side: str):
    """Handle place_order tool call."""
    if side == "buy":
        order = trading.buy(symbol, quantity)
    else:
        order = trading.sell(symbol, quantity)
    
    return {
        "order_id": order.id,
        "status": order.status,
        "filled_qty": order.filled_qty
    }
```

### 3. Use with Claude API

```python
import anthropic

client = anthropic.Anthropic()

# Define your tools (see step 1)
tools = [...]

# System prompt for the agent
system_prompt = """You are a trading analyst. You can:
1. Check account status
2. Analyze historical prices
3. Place buy/sell orders

Always check the account first, analyze price trends, then make trading decisions.
Be conservative - only trade when you're confident in the analysis."""

# Start conversation
messages = [
    {"role": "user", "content": "Analyze AAPL and GOOGL current prices. If they look good, buy 5 shares of each."}
]

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=system_prompt,
    tools=tools,
    messages=messages
)

# Handle tool calls from Claude
while response.stop_reason == "tool_use":
    # Find tool use blocks
    tool_uses = [block for block in response.content if block.type == "tool_use"]
    
    # Process each tool call
    tool_results = []
    for tool_use in tool_uses:
        if tool_use.name == "check_account":
            result = check_account()
        elif tool_use.name == "get_price_history":
            result = get_price_history(**tool_use.input)
        elif tool_use.name == "place_order":
            result = place_order(**tool_use.input)
        
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": str(result)
        })
    
    # Continue conversation with tool results
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": tool_results})
    
    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1024,
        system=system_prompt,
        tools=tools,
        messages=messages
    )

# Final response from Claude
print("Claude Analysis:")
for block in response.content:
    if hasattr(block, "text"):
        print(block.text)
```

## Example Trading Conversation

**User:** "Buy AAPL if the 20-day average is down more than 5%"

**Claude's thinking:**
1. Calls `check_account()` → Gets $50,000 cash available
2. Calls `get_price_history(symbol="AAPL", days=20)` → Gets trend data
3. Analyzes: "Current price $150, 20-day high $160 = 6.25% down ✓"
4. Calls `place_order(symbol="AAPL", quantity=100, side="buy")`
5. Reports: "Placed buy order for 100 AAPL at market price"

## Safety Considerations

### Always Use Paper Trading First
```python
# .env
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # ← For testing
# NOT: ALPACA_BASE_URL=https://api.alpaca.markets  # Live money!
```

### Add Safeguards in Claude System Prompt

```
DO NOT:
- Trade more than 10% of portfolio in a day
- Place orders larger than $10,000 without confirmation
- Trade illiquid securities
- Use leverage (margin) without explicit approval
```

### Add Rate Limits

```python
from functools import wraps
from time import time

def rate_limit(max_per_minute=10):
    def decorator(func):
        calls = []
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time()
            calls[:] = [c for c in calls if c > now - 60]
            if len(calls) >= max_per_minute:
                raise RuntimeError("Rate limit exceeded")
            calls.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limit(max_per_minute=5)
def place_order(*args, **kwargs):
    # ... implementation
```

## Testing Claude Integration

Use this simple test to verify the setup:

```python
# Test that Claude can access all tools correctly
import anthropic

client = anthropic.Anthropic()

test_message = """I want to check my account status and see current prices for AAPL."""

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": test_message}]
)

# Should request tool use
assert response.stop_reason == "tool_use"
print("✅ Claude successfully requested tools")
```

## Next Steps

1. **Set up Claude API credentials** - Get your API key from https://console.anthropic.com
2. **Test the basic example** - Run `python examples/basic_example.py` 
3. **Build your trading strategy** - Define what analysis Claude should do
4. **Start with paper trading** - Always test thoroughly before live trading
5. **Monitor Claude's decisions** - Review trades and adjust constraints as needed

## Resources

- [Claude API Documentation](https://docs.anthropic.com)
- [Alpaca Trading API](https://docs.alpaca.markets)
- [Building AI Agents](https://docs.anthropic.com/building-a-tool-use-agent)
