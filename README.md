# Trader: Claude-Powered Trading Agent

A modular Python connector for algorithmic trading with [Alpaca Markets API](https://alpaca.markets/), exposed as an MCP server for integration with Claude (Claude Code and Claude.ai web).

## Overview

**Trader** provides a clean interface for:
- ✅ Verifying Alpaca API connection
- 📊 Retrieving historical price data
- 💼 Placing and managing orders (paper & live trading)
- 📈 Backtesting trading strategies

The included MCP server (`mcp_server.py`) deploys all of the above as tools that Claude can discover and call autonomously.

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

mcp_server.py              # MCP server — exposes trading tools to Claude
Dockerfile                 # Container image
docker-compose.yml         # Production deployment
docker-compose.override.yml  # Development bind-mount override
```

## Deployment (Docker + Caddy)

The recommended setup runs the MCP server in Docker behind a Caddy reverse proxy that handles HTTPS automatically via [sslip.io](https://sslip.io).

### 1. Clone and configure

```bash
git clone https://github.com/ajberenstein/trader.git
cd trader
cp .env.example .env
# Edit .env with your Alpaca credentials
```

`.env` format:
```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

### 2. Build and run

```bash
docker compose up -d --build

# Check health
curl http://localhost:8080/health
```

### 3. HTTPS via Caddy (for Claude.ai web)

Claude.ai requires HTTPS. Set up Caddy as a reverse proxy on the same host:

```
trader.YOUR-IP-DASHES.sslip.io {
    reverse_proxy 172.17.0.1:8080 {
        flush_interval -1
    }
}
```

Replace `YOUR-IP-DASHES` with your server IP using dashes (e.g. IP `137.184.12.167` → `trader.137-184-12-167.sslip.io`). Caddy provisions the TLS certificate automatically.

The MCP endpoint will be at: `https://trader.YOUR-IP-DASHES.sslip.io/mcp`

### Docker commands

```bash
# View logs
docker compose logs -f

# Restart
docker compose restart

# Stop
docker compose down
```

## Claude Integration

### Claude Code

Add to `.claude/settings.json` in your project:

```json
{
  "mcpServers": {
    "trader": {
      "url": "https://trader.YOUR-IP-DASHES.sslip.io/mcp"
    }
  }
}
```

### Claude.ai (web)

In Claude.ai settings → Integrations → Add MCP server:
- URL: `https://trader.YOUR-IP-DASHES.sslip.io/mcp`

### Available tools

Once connected, Claude has access to:

| Tool | Description |
|------|-------------|
| `check_account` | Account status, cash balance, buying power |
| `get_price_history(symbol, days)` | Historical price stats for a symbol |
| `place_order(symbol, quantity, side)` | Execute buy or sell orders |
| `backtest_strategy(symbol, strategy, period)` | Run strategy backtest |
| `get_market_comparison(symbols)` | Compare multiple symbols |

### Example

```
You: Analyze AAPL and MSFT, then buy 5 shares of the better performer

Claude: [calls get_price_history for AAPL and MSFT]
        [compares performance]
        [calls place_order for the winner]
✅ Order placed successfully!
```

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run server locally
python mcp_server.py
# Health check: http://localhost:8080/health
# MCP endpoint: http://localhost:8080/mcp
```

For Claude Code local dev, point the MCP URL to `http://localhost:8080/mcp`.

## Python API

### AlpacaConnector

```python
from trader import AlpacaConnector

connector = AlpacaConnector()
connector.connect()
account = connector.get_account()
print(f"Cash: ${account.cash:,.2f}")
```

### MarketDataHandler

```python
from trader import MarketDataHandler

market = MarketDataHandler(connector)
bars = market.get_historical_bars("AAPL", timeframe="1Day", limit=20)
stats = market.get_price_range("AAPL", days=30)
# Returns: {current_price, min_price, max_price, avg_price, change_pct}
comparison = market.compare_symbols(["AAPL", "GOOGL", "MSFT"])
```

### TradingHandler

```python
from trader import TradingHandler

trading = TradingHandler(connector)
order = trading.buy("AAPL", quantity=10)
order = trading.sell("GOOGL", quantity=5)
```

### Backtester

```python
from trader import Backtester, SimpleDipStrategy, MomentumStrategy
from trader.data_utils import fetch_yahoo_data

data = fetch_yahoo_data("AAPL", period="1y")
backtester = Backtester(initial_capital=10000)

results = backtester.run(SimpleDipStrategy(), data)
print(f"Dip Strategy: {results.total_return:.2f}% | Win rate: {results.win_rate:.0%}")

results = backtester.run(MomentumStrategy(), data)
print(f"Momentum: {results.total_return:.2f}% | Win rate: {results.win_rate:.0%}")
```

## Paper Trading vs Live Trading

**Paper trading (default, safe for testing):**
```
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

**Live trading (real money):**
```
ALPACA_BASE_URL=https://api.alpaca.markets
```

⚠️ Always test with paper trading before going live.

## Requirements

- Python 3.11+
- alpaca-trade-api
- mcp >= 1.26.0
- uvicorn
- pydantic >= 2.0.0
- pandas
- yfinance
- python-dotenv
- Docker (for containerized deployment)

## Roadmap

- [x] Strategy backtesting
- [x] MCP server for Claude Code and Claude.ai integration
- [x] Docker containerization + HTTPS via Caddy
- [ ] Crypto trading support
- [ ] Advanced order types (trailing stops, brackets)
- [ ] Streaming real-time quotes
- [ ] Performance analytics dashboard

## License

MIT
