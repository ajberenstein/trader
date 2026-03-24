"""
Example: Backtesting Trading Strategies
Tests two strategies (SimpleDip and Momentum) against historical data.
Uses Yahoo Finance for reliable historical data.
"""

import logging
from trader import AlpacaConnector, Backtester
from trader.data_utils import fetch_yahoo_data
from trader.strategy import SimpleDipStrategy, MomentumStrategy

logging.basicConfig(level=logging.INFO)

def main():
    print("=" * 70)
    print("Backtesting Trading Strategies")
    print("=" * 70)

    # Test symbol
    symbol = "AAPL"
    print(f"\n[1] Fetching historical data for {symbol} (Yahoo Finance)...")
    
    # Get longer history (365 days) for better backtest
    price_data = fetch_yahoo_data(symbol=symbol, days=365)

    if not price_data:
        print(f"❌ Could not retrieve data for {symbol}")
        return

    print(f"   Got {len(price_data)} days of data")
    print(f"   Date range: {price_data[0].timestamp.date()} to {price_data[-1].timestamp.date()}")
    print(f"   Price range: ${min(b.low for b in price_data):.2f} - ${max(b.high for b in price_data):.2f}")

    # Initialize backtester
    print("\n[2] Running backtests...")
    backtester = Backtester(initial_capital=10000, shares_per_trade=1)

    # Test Strategy 1: SimpleDip
    print("\n" + "=" * 70)
    print(f"Strategy 1: SimpleDip (Buy on dip, sell on target)")
    print("=" * 70)
    
    simple_dip = SimpleDipStrategy(
        dip_threshold=0.05,  # Buy when 5% below 20-day MA
        target_gain=0.03,    # Sell when 3% profit
        stop_loss=0.02       # Sell when 2% loss
    )
    
    try:
        result1 = backtester.run(symbol, price_data, simple_dip, lookback_bars=20)
        print(result1)
    except Exception as e:
        print(f"❌ Backtest failed: {str(e)}")

    # Test Strategy 2: Momentum
    print("\n" + "=" * 70)
    print(f"Strategy 2: Momentum (Buy on 3-day up, sell on reversal)")
    print("=" * 70)
    
    momentum = MomentumStrategy(gain_target=0.05)
    
    try:
        result2 = backtester.run(symbol, price_data, momentum, lookback_bars=3)
        print(result2)
    except Exception as e:
        print(f"❌ Backtest failed: {str(e)}")

    # Buy and Hold comparison
    print("\n" + "=" * 70)
    print(f"Comparison: Buy & Hold")
    print("=" * 70)
    
    entry_price = price_data[20].close
    exit_price = price_data[-1].close
    shares = 10000 / entry_price
    profit = (exit_price - entry_price) * shares
    profit_pct = ((exit_price - entry_price) / entry_price) * 100
    
    print(f"Buy @ ${entry_price:.2f}, Sell @ ${exit_price:.2f}")
    print(f"Profit: ${profit:,.2f} ({profit_pct:.2f}%)")

    # Now verify connection to Alpaca works for live trading
    print("\n" + "=" * 70)
    print("Verifying live connection to Alpaca...")
    print("=" * 70)
    
    connector = AlpacaConnector()
    if connector.connect():
        account = connector.get_account()
        print(f"✅ Alpaca connection OK")
        print(f"   Account: {account.account_type}")
        print(f"   Cash: ${account.cash:,.2f}")
        connector.disconnect()
    else:
        print("❌ Could not connect to Alpaca (check credentials)")

    print("\n✅ Backtest complete!")


if __name__ == "__main__":
    main()
