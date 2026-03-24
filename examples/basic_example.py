"""
Example: Basic Trading Flow
Demonstrates connection, data retrieval, and order placement.
"""

import logging
from trader import AlpacaConnector, MarketDataHandler, TradingHandler, OrderRequest

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)

def main():
    print("=" * 60)
    print("Trading Connector Example - Alpaca Paper Trading")
    print("=" * 60)

    # Step 1: Connect to Alpaca
    print("\n[1] Connecting to Alpaca API...")
    connector = AlpacaConnector()
    if not connector.connect():
        print("❌ Failed to connect. Check your credentials in .env")
        return

    # Step 2: Get account info
    print("\n[2] Fetching account information...")
    account = connector.get_account()
    if account:
        print(f"   Account Type: {account.account_type}")
        print(f"   Cash: ${account.cash:,.2f}")
        print(f"   Portfolio Value: ${account.portfolio_value:,.2f}")
        print(f"   Trading Mode: {account.trading_mode}")

    # Step 3: Get market data
    print("\n[3] Retrieving historical data...")
    market_data = MarketDataHandler(connector)
    
    symbols = ["AAPL", "GOOGL", "MSFT"]
    price_stats = market_data.compare_symbols(symbols, limit=20)
    
    if price_stats:
        for symbol, stats in price_stats.items():
            print(f"\n   {symbol}:")
            print(f"     Current Price: ${stats['current_price']:.2f}")
            print(f"     Range: ${stats['min_price']:.2f} - ${stats['max_price']:.2f}")
            print(f"     Change: {stats['change_pct']:.2f}%")

    # Step 4: Check existing positions
    print("\n[4] Current positions:")
    positions = connector.get_positions()
    if positions:
        for symbol, position in positions.items():
            print(f"   {symbol}: {position.qty} shares @ ${position.avg_entry_price:.2f}")
    else:
        print("   No open positions")

    # Step 5: Example order (commented out - uncomment to test)
    print("\n[5] Example: Placing a test order (DISABLED for safety)")
    print("   To enable trading, uncomment the order placement code below")
    
    # Uncomment these lines to actually place orders:
    # print("   Placing a buy order for 1 AAPL...")
    # trading = TradingHandler(connector)
    # order = trading.buy("AAPL", 1)
    # if order:
    #     print(f"   ✅ Order placed: {order.id} - Status: {order.status}")

    # Step 6: Disconnect
    print("\n[6] Closing connection...")
    connector.disconnect()
    print("✅ Example complete!")


if __name__ == "__main__":
    main()
