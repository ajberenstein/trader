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

## Using with Claude for Work (MCP Server)

The `mcp_server.py` provides a **Model Context Protocol (MCP) server** that integrates seamlessly with Claude for Work, offering cost-effective trading without API call charges.

### Why MCP over Direct API Calls?

- **💰 Cost**: No API call charges - included in Claude for Work pricing
- **🔗 Native Integration**: Claude for Work discovers and uses tools automatically
- **⚡ Performance**: Direct connection without HTTP overhead
- **🛡️ Security**: Server runs on your infrastructure

### Setup Instructions

1. **Deploy to your droplet:**
   ```bash
   # On your DigitalOcean droplet
   git clone https://github.com/ajberenstein/trader.git
   cd trader
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your Alpaca credentials
   ```

2. **Configure Claude for Work:**
   - In Claude for Work settings, add your MCP server endpoint
   - Point to: `http://your-droplet-ip:port` (default port 8080)
   - The server will auto-discover available trading tools

3. **Start the server:**
   ```bash
   python mcp_server.py
   ```

### Available MCP Tools

Once connected, Claude for Work will have access to:

- ✅ `check_account()` - Account status and balances
- 📊 `get_price_history(symbol, days)` - Historical price analysis
- 💼 `place_order(symbol, quantity, side)` - Execute trades
- 📈 `backtest_strategy(symbol, strategy, period)` - Strategy testing
- 🔄 `get_market_comparison(symbols)` - Multi-symbol analysis

### Example Usage in Claude for Work

```
You: Analyze AAPL and GOOGL, then buy 5 shares of the better performer

Claude: Let me check both stocks' recent performance...
[Calls get_price_history for AAPL and GOOGL]
[Analyzes trends and compares performance]
[Calls place_order for the better stock]
✅ Order placed successfully!
```

### Security & Paper Trading

- **Always use paper trading first**: Set `ALPACA_BASE_URL=https://paper-api.alpaca.markets`
- **Server security**: Run behind firewall/reverse proxy on your droplet
- **API keys**: Never expose Alpaca credentials in logs

### Troubleshooting

- **Connection issues**: Check firewall allows port 8080
- **Tool not appearing**: Restart Claude for Work after server connection
- **Trading errors**: Verify .env configuration on droplet

## Deployment to DigitalOcean Droplet

### Option 1: Docker Deployment (Recommended)

The easiest way to deploy is using Docker:

```bash
# On your DigitalOcean droplet
git clone https://github.com/ajberenstein/trader.git
cd trader

# Configure environment
cp .env.example .env
# Edit .env with your Alpaca credentials

# Build and run with Docker Compose
docker-compose up -d --build

# Check logs
docker-compose logs -f trader-mcp

# Check health
curl http://localhost:8080/health
```

### Option 2: Automated Script

Use the automated deployment script:

```bash
# On your fresh DigitalOcean droplet (Ubuntu 22.04+)
wget https://raw.githubusercontent.com/ajberenstein/trader/main/deploy_droplet.sh
chmod +x deploy_droplet.sh
sudo ./deploy_droplet.sh
```

### Option 3: Manual Deployment

If you prefer manual setup:

```bash
# Clone and setup
git clone https://github.com/ajberenstein/trader.git
cd trader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with credentials

# Run server
python mcp_server.py
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

## Docker Containerization 🐳

The project is fully containerized for easy deployment and scaling:

### Quick Start with Docker

```bash
# Clone repository
git clone https://github.com/ajberenstein/trader.git
cd trader

# Configure environment
cp .env.example .env
# Edit .env with your Alpaca API credentials

# Build and run
docker-compose up -d --build

# Check logs
docker-compose logs -f

# Health check
curl http://localhost:8000/health
```

### Docker Architecture

- **Multi-stage build** for optimized image size
- **Health checks** for container monitoring
- **Non-root user** for security
- **Volume mounts** for logs and configuration
- **Development override** for local development

### Docker Commands

```bash
# Build image
docker build -t trader-mcp .

# Run container
docker run -d --name trader-mcp -p 8080:8080 --env-file .env trader-mcp

# View logs
docker logs -f trader-mcp

# Stop container
docker-compose down
```

### Production Deployment

For production on your droplet:

```bash
# Use docker-compose for production
docker-compose -f docker-compose.yml up -d

# Or use swarm mode for scaling
docker stack deploy -c docker-compose.yml trader
```

## Requirements

- Python 3.8+
- alpaca-trade-api >= 3.1.0
- pydantic >= 2.0.0
- pandas >= 1.5.0
- python-dotenv >= 0.19.0
- yfinance >= 0.2.0
- mcp >= 1.26.0
- fastapi >= 0.104.0
- uvicorn >= 0.24.0
- Docker (for containerized deployment)

## Roadmap

- [x] Strategy backtesting
- [x] MCP Server wrapper for direct Claude integration
- [x] Docker containerization
- [ ] Support for crypto trading (currently stocks only)
- [ ] Advanced order types (trailing stops, brackets)
- [ ] Streaming real-time quotes
- [ ] Performance analytics

## License

MIT