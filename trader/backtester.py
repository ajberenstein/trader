"""Backtesting engine for trading strategies."""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from .models import PriceData
from .strategy import Strategy

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a completed trade."""

    entry_date: datetime
    entry_price: float
    exit_date: datetime
    exit_price: float
    shares: float
    side: str = "long"

    @property
    def profit(self) -> float:
        """Calculate profit in dollars."""
        return (self.exit_price - self.entry_price) * self.shares

    @property
    def return_pct(self) -> float:
        """Calculate return percentage."""
        return ((self.exit_price - self.entry_price) / self.entry_price) * 100

    @property
    def duration_days(self) -> int:
        """Duration of trade in days."""
        return (self.exit_date - self.entry_date).days


@dataclass
class BacktestResult:
    """Results from backtest."""

    symbol: str
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    num_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    total_profit: float
    total_profit_pct: float
    avg_win: float
    avg_loss: float
    max_drawdown_pct: float
    sharpe_ratio: Optional[float] = None

    def __str__(self) -> str:
        return f"""
=== Backtest Results: {self.symbol} ({self.strategy_name}) ===
Period: {self.start_date.date()} to {self.end_date.date()}

Capital:
  Initial: ${self.initial_capital:,.2f}
  Final:   ${self.final_capital:,.2f}
  Profit:  ${self.total_profit:,.2f} ({self.total_profit_pct:.2f}%)

Trades:
  Total:   {self.num_trades}
  Wins:    {self.winning_trades}
  Losses:  {self.losing_trades}
  Win Rate: {self.win_rate_pct:.2f}%

Performance:
  Avg Win:      ${self.avg_win:,.2f}
  Avg Loss:     ${self.avg_loss:,.2f}
  Max Drawdown: {self.max_drawdown_pct:.2f}%
"""


class Backtester:
    """Engine for simulating a strategy against historical price data."""

    def __init__(self, initial_capital: float = 10000, shares_per_trade: float = 1):
        """
        Initialize backtester.

        Args:
            initial_capital: Starting cash
            shares_per_trade: Number of shares per trade
        """
        self.initial_capital = initial_capital
        self.shares_per_trade = shares_per_trade

    def run(
        self, 
        symbol: str,
        price_data: List[PriceData],
        strategy: Strategy,
        lookback_bars: int = 20
    ) -> BacktestResult:
        """
        Run backtest on price data with given strategy.

        Args:
            symbol: Stock symbol
            price_data: List of PriceData bars (must be ordered oldest to newest)
            strategy: Strategy instance to test
            lookback_bars: Minimum bars needed before first signal

        Returns:
            BacktestResult with performance metrics
        """
        if not price_data or len(price_data) < lookback_bars:
            raise ValueError(f"Need at least {lookback_bars} bars of data")

        trades: List[Trade] = []
        capital = self.initial_capital
        position: Optional[Dict] = None  # {entry_price, entry_date, shares}
        equity_curve = [capital]

        # Simulate trading logic
        for i in range(lookback_bars, len(price_data)):
            current_bar = price_data[i]
            current_price = current_bar.close
            history = price_data[:i]

            # Check if we should sell
            if position:
                if strategy.should_sell(history, current_price, position["entry_price"]):
                    profit = (current_price - position["entry_price"]) * position["shares"]
                    capital += profit
                    trades.append(
                        Trade(
                            entry_date=position["entry_date"],
                            entry_price=position["entry_price"],
                            exit_date=current_bar.timestamp,
                            exit_price=current_price,
                            shares=position["shares"],
                        )
                    )
                    position = None

            # Check if we should buy (and not already in position)
            if not position and capital > current_price * self.shares_per_trade:
                if strategy.should_buy(history, current_price):
                    cost = current_price * self.shares_per_trade
                    capital -= cost
                    position = {
                        "entry_price": current_price,
                        "entry_date": current_bar.timestamp,
                        "shares": self.shares_per_trade,
                    }

            # Track equity
            if position:
                position_value = position["shares"] * current_price
                equity_curve.append(capital + position_value)
            else:
                equity_curve.append(capital)

        # Close any open position at end
        if position:
            final_price = price_data[-1].close
            profit = (final_price - position["entry_price"]) * position["shares"]
            capital += profit
            trades.append(
                Trade(
                    entry_date=position["entry_date"],
                    entry_price=position["entry_price"],
                    exit_date=price_data[-1].timestamp,
                    exit_price=final_price,
                    shares=position["shares"],
                )
            )

        # Calculate metrics
        winning_trades = [t for t in trades if t.profit > 0]
        losing_trades = [t for t in trades if t.profit <= 0]

        win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0
        avg_win = sum(t.profit for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.profit for t in losing_trades) / len(losing_trades) if losing_trades else 0

        total_profit = capital - self.initial_capital
        total_profit_pct = (total_profit / self.initial_capital) * 100

        # Max drawdown
        max_drawdown = self._calculate_max_drawdown(equity_curve)

        return BacktestResult(
            symbol=symbol,
            strategy_name=strategy.name,
            start_date=price_data[0].timestamp,
            end_date=price_data[-1].timestamp,
            initial_capital=self.initial_capital,
            final_capital=capital,
            num_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate_pct=win_rate,
            total_profit=total_profit,
            total_profit_pct=total_profit_pct,
            avg_win=avg_win,
            avg_loss=abs(avg_loss),
            max_drawdown_pct=max_drawdown,
        )

    @staticmethod
    def _calculate_max_drawdown(equity_curve: List[float]) -> float:
        """Calculate maximum drawdown percentage."""
        if not equity_curve:
            return 0

        running_max = equity_curve[0]
        max_dd = 0

        for value in equity_curve[1:]:
            if value > running_max:
                running_max = value
            drawdown = (running_max - value) / running_max * 100
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd
