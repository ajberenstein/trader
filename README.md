# Trader: Claude-Powered Trading Agent

A modular Python connector for algorithmic trading with [Alpaca Markets API](https://alpaca.markets/). Designed to work seamlessly with Claude agents for autonomous trading analysis and execution.

## Overview

**Trader** provides a clean, documented interface for:
- ✅ Verifying Alpaca API connection
- 📊 Retrieving historical price data  
- 💼 Placing and managing orders (paper & live trading)

Perfect for building trading agents that can analyze markets and execute trades via Claude's tool-calling interface.

## Architecture

```
trader/
├── alpaca_connector.py    # Core API connection & account management
├── market_data.py         # Historical data retrieval & analysis
├── trading.py             # Order placement & management
├── models.py              # Pydantic data models
├── config.py              # Configuration management
├── strategy.py            # Trading strategy base classes
├── backtester.py          # Backtesting engine for strategy validation
└── data_utils.py          # Alternative data sources (Yahoo Finance)
```

## Installation

1. **Clone and setup environment:**
   ```bash
   cd /path/to/trader
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your credentials:
   ```
   ALPACA_API_KEY=your_key_here
   ALPACA_SECRET_KEY=your_secret_here
   ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Use this for paper trading
   
   # For Claude integration (get from https://console.anthropic.com/)
   ANTHROPIC_API_KEY=your_anthropic_key_here
   ```

## Quick Start

### 1. Test Connection

```python
from trader import AlpacaConnector

connector = AlpacaConnector()
if connector.connect():
    account = connector.get_account()
    print(f"✅ Connected! Cash: ${account.cash:,.2f}")
else:
    print("❌ Connection failed")
```

### 2. Get Historical Data

```python
from trader import AlpacaConnector, MarketDataHandler

connector = AlpacaConnector()
connector.connect()

market_data = MarketDataHandler(connector)
bars = market_data.get_historical_bars("AAPL", timeframe="1Day", limit=20)

for bar in bars:
    print(f"{bar.symbol}: ${bar.close} (Volume: {bar.volume})")
```

### 3. Place an Order

```python
from trader import AlpacaConnector, TradingHandler, OrderRequest

connector = AlpacaConnector()
connector.connect()

trading = TradingHandler(connector)

# Method 1: Convenience method
order = trading.buy("AAPL", quantity=10)

# Method 2: Full OrderRequest control
order_req = OrderRequest(
    symbol="GOOGL",
    quantity=5,
    side="buy",
    order_type="market"
)
order = trading.place_order(order_req)

if order:
    print(f"✅ Order placed: {order.id}")
```

### 4. Backtest Trading Strategies

```python
from trader import Backtester, SimpleDipStrategy, MomentumStrategy
from trader.data_utils import fetch_yahoo_data

# Get historical data
data = fetch_yahoo_data("AAPL", period="1y")

# Test strategies
backtester = Backtester(initial_cash=10000)

# Simple Dip Strategy: Buy on 5% dip, sell on 10% gain
dip_results = backtester.run(SimpleDipStrategy(), data)
print(f"Dip Strategy: {dip_results.total_return:.2f}% profit")

# Momentum Strategy: Buy on uptrend, sell on downtrend
momentum_results = backtester.run(MomentumStrategy(), data)
print(f"Momentum Strategy: {momentum_results.total_return:.2f}% profit")

# Compare with Buy & Hold
buy_hold_return = backtester.calculate_buy_hold_return(data)
print(f"Buy & Hold: {buy_hold_return:.2f}% profit")
```

## API Reference

### AlpacaConnector

```python
connector = AlpacaConnector()
connector.connect()                          # Establish connection
account = connector.get_account()            # Get account info
positions = connector.get_positions()        # Get all open positions
position = connector.get_position("AAPL")    # Get specific position
connector.disconnect()                       # Close connection
```

### MarketDataHandler

```python
market = MarketDataHandler(connector)

# Get historical bars
bars = market.get_historical_bars(
    symbol="AAPL",
    timeframe="1Day",    # 1Min, 5Min, 15Min, 1H, 1Day
    limit=100,
    end_date=None        # defaults to now
)

# Get latest price
price = market.get_latest_price("AAPL")

# Get price statistics
stats = market.get_price_range("AAPL", days=30)
# Returns: {current_price, min_price, max_price, avg_price, change_pct}

# Compare multiple symbols
comparison = market.compare_symbols(["AAPL", "GOOGL", "MSFT"])
```

### TradingHandler

```python
trading = TradingHandler(connector)

# Place market order
order = trading.place_order(OrderRequest(
    symbol="AAPL",
    quantity=10,
    side="buy",
    order_type="market"
))

# Convenience methods
order = trading.buy("AAPL", 10)
order = trading.sell("GOOGL", 5)

# Manage orders
orders = trading.list_orders(status="open")
order = trading.get_order("order_id")
success = trading.cancel_order("order_id")
```

## Data Models

### OrderRequest
```python
OrderRequest(
    symbol: str              # "AAPL"
    quantity: float          # 10
    side: str                # "buy" or "sell"
    order_type: str          # "market", "limit", "stop"
    limit_price: Optional    # For limit orders
    stop_price: Optional     # For stop orders
    time_in_force: str       # "day", "gtc", "opg", "cls"
)
```

### PriceData
```python
PriceData(
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
)
```

### Account
```python
Account(
    account_type: str        # "paper" or "margin"
    cash: float
    portfolio_value: float
    buying_power: float
    multiplier: int
    trading_mode: str        # "paper" or "live"
)
```

## Using with Claude Agents

The `claude_tools.py` script provides a complete integration with Claude's tool-calling capabilities:

```bash
# Install additional dependency
pip install anthropic

# Set up Anthropic API key in .env
ANTHROPIC_API_KEY=your_key_here

# Run the interactive Claude trading assistant
python claude_tools.py
```

This starts an interactive session where Claude can:
- ✅ Check account status
- 📊 Analyze price history  
- 💼 Place orders autonomously
- 📈 Run backtests on strategies

**Example conversation:**
```
You: Analyze AAPL and buy 10 shares if the price is below $180

Claude: First, let me check the account status...
[Calls check_account tool]
Account has $95,000 cash available.

Now let me get the current price data for AAPL...
[Calls get_price_history tool]  
AAPL is currently $175 (-2.3% from 20-day high).

This looks like a good buying opportunity. Placing order...
[Calls place_order tool]
✅ Order placed: AAPL buy 10 shares at market price
```

### Manual Claude Tools Setup

Define these functions in your Claude tool definitions:

```json
{
  "type": "function",
  "function": {
    "name": "check_account",
    "description": "Get current account status and cash available",
    "parameters": {}
  }
}
```

Then have Claude call them during trading decisions:

> "I'll check the account balance first, then analyze AAPL, and place 10 shares if it looks good..."

## Testing

Run the example script:
```bash
python examples/basic_example.py
```

Run unit tests:
```bash
pytest tests/
```

## Paper Trading vs Live Trading

**Paper Trading (Safe for Testing):**
```
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Default - Use this!
```

**Live Trading (Real Money - Be Careful):**
```
ALPACA_BASE_URL=https://api.alpaca.markets
```

⚠️ **Always test thoroughly with paper trading first!**

## Roadmap

- [x] Strategy backtesting
- [ ] Support for crypto trading (currently stocks only)
- [ ] Advanced order types (trailing stops, brackets)
- [ ] Streaming real-time quotes
- [ ] Performance analytics
- [ ] MCP Server wrapper for direct Claude integration

## Requirements

- Python 3.8+
- alpaca-trade-api >= 3.1.0
- pydantic >= 2.0.0
- pandas >= 1.5.0
- python-dotenv >= 0.19.0
- yfinance >= 0.2.0
- anthropic >= 0.7.0

## License

MIT