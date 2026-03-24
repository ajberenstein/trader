#!/usr/bin/env python3
"""
Setup verification script - Check if the trading connector is ready to use.
Run this after installing dependencies and configuring credentials.
"""

import sys
import os
from pathlib import Path

def check_env_file():
    """Check if .env file exists and has credentials."""
    print("\n[1/5] Checking .env configuration...")
    env_path = Path(__file__).parent / ".env"
    
    if not env_path.exists():
        print("❌ .env file not found")
        print(f"   → Copy .env.example to .env and add your credentials")
        return False
    
    with open(env_path) as f:
        content = f.read()
        has_key = "ALPACA_API_KEY=" in content
        has_secret = "ALPACA_SECRET_KEY=" in content
        
        if not has_key or not has_secret:
            print("❌ .env missing API credentials")
            return False
        
        # Check if placeholders are still there
        if "your_api_key_here" in content or "your_secret_key_here" in content:
            print("❌ .env still contains placeholder values")
            print("   → Edit .env and replace with real Alpaca credentials")
            return False
    
    print("✅ .env file configured")
    return True


def check_dependencies():
    """Check if required packages are installed."""
    print("\n[2/5] Checking dependencies...")
    
    required = {
        'alpaca_trade_api': 'alpaca-trade-api',
        'pydantic': 'pydantic',
        'pandas': 'pandas',
        'dotenv': 'python-dotenv',
    }
    
    missing = []
    for module, package in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"   → Run: pip install {' '.join(missing)}")
        return False
    
    print("✅ All dependencies installed")
    return True


def check_module_structure():
    """Check if the trader module is properly structured."""
    print("\n[3/5] Checking module structure...")
    
    trader_path = Path(__file__).parent / "trader"
    required_files = [
        "__init__.py",
        "config.py",
        "models.py",
        "alpaca_connector.py",
        "market_data.py",
        "trading.py",
    ]
    
    missing = []
    for file in required_files:
        if not (trader_path / file).exists():
            missing.append(file)
    
    if missing:
        print(f"❌ Missing module files: {', '.join(missing)}")
        return False
    
    print("✅ Module structure is complete")
    return True


def test_connection():
    """Test actual connection to Alpaca API."""
    print("\n[4/5] Testing Alpaca API connection...")
    
    try:
        from trader import AlpacaConnector
        
        connector = AlpacaConnector()
        if connector.connect():
            account = connector.get_account()
            print(f"✅ Connected to Alpaca!")
            if account:
                print(f"   Account Type: {account.account_type}")
                print(f"   Cash Available: ${account.cash:,.2f}")
                print(f"   Portfolio Value: ${account.portfolio_value:,.2f}")
            else:
                print("   ⚠️ Could not parse account details, but connection is established")
            connector.disconnect()
            return True
        else:
            print("❌ Failed to connect to Alpaca API")
            print("   → Check your API credentials in .env")
            print("   → Verify your credentials are valid in Alpaca dashboard")
            return False
            
    except Exception as e:
        print(f"❌ Error during connection test: {str(e)}")
        return False


def test_market_data():
    """Test market data retrieval."""
    print("\n[5/5] Testing market data retrieval...")
    
    try:
        from trader import AlpacaConnector, MarketDataHandler
        
        connector = AlpacaConnector()
        if not connector.connect():
            print("❌ Cannot test market data (not connected)")
            return False
        
        market = MarketDataHandler(connector)
        price = market.get_latest_price("AAPL")
        
        if price:
            print(f"✅ Can retrieve market data")
            print(f"   Latest AAPL price: ${price:.2f}")
            connector.disconnect()
            return True
        else:
            print("❌ Failed to retrieve market data")
            return False
            
    except Exception as e:
        print(f"❌ Error during market data test: {str(e)}")
        return False


def main():
    """Run all checks."""
    print("=" * 60)
    print("Trader Setup Verification")
    print("=" * 60)
    
    checks = [
        check_env_file,
        check_dependencies,
        check_module_structure,
        test_connection,
        test_market_data,
    ]
    
    results = []
    for check in checks:
        try:
            results.append(check())
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    if all(results):
        print("✅ All checks passed! You're ready to trade!")
        print("\nNext steps:")
        print("  1. Run: python examples/basic_example.py")
        print("  2. Read the README for API documentation")
        print("  3. Create your trading agent with Claude")
        return 0
    else:
        print(f"❌ {sum(not r for r in results)} check(s) failed")
        print("\nFix the issues above and run setup.py again")
        return 1


if __name__ == "__main__":
    sys.exit(main())
