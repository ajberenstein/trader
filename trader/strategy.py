"""Base strategy class for defining trading strategies."""

from abc import ABC, abstractmethod
from typing import List
from .models import PriceData


class Strategy(ABC):
    """
    Abstract base class for trading strategies.
    Implement should_buy() and should_sell() to define your strategy logic.
    """

    def __init__(self, name: str):
        """
        Initialize strategy.

        Args:
            name: Strategy name for logging/reporting
        """
        self.name = name

    @abstractmethod
    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        """
        Determine if we should buy based on price data.

        Args:
            price_data: List of historical price bars (oldest to newest)
            current_price: Current price (last bar close)

        Returns:
            True if conditions met to buy, False otherwise
        """
        pass

    @abstractmethod
    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        """
        Determine if we should sell based on price data and entry price.

        Args:
            price_data: List of historical price bars
            current_price: Current price
            entry_price: Price at which we bought

        Returns:
            True if conditions met to sell, False otherwise
        """
        pass


class SimpleDipStrategy(Strategy):
    """
    Simple strategy: Buy on X% dip from moving average, sell on Y% gain.

    Rules:
    - Buy: Price drops 5% below 20-day moving average
    - Sell: Price rises 3% above entry price OR drops 2% below entry (stop loss)
    """

    def __init__(self, dip_threshold: float = 0.05, target_gain: float = 0.03, stop_loss: float = 0.02):
        """
        Initialize dip strategy.

        Args:
            dip_threshold: Buy when price is X% below MA (e.g., 0.05 = 5%)
            target_gain: Sell when profit reaches X% (e.g., 0.03 = 3%)
            stop_loss: Sell when loss reaches X% (e.g., 0.02 = 2%)
        """
        super().__init__("SimpleDipStrategy")
        self.dip_threshold = dip_threshold
        self.target_gain = target_gain
        self.stop_loss = stop_loss

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        """Buy when price dips below 20-day MA."""
        if len(price_data) < 20:
            return False

        # Calculate 20-day moving average
        ma_20 = sum(bar.close for bar in price_data[-20:]) / 20

        # Buy if current price is dip_threshold% below MA
        dip = (ma_20 - current_price) / ma_20
        return dip >= self.dip_threshold

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        """Sell on target gain or stop loss."""
        return_pct = (current_price - entry_price) / entry_price

        # Sell on target gain
        if return_pct >= self.target_gain:
            return True

        # Sell on stop loss
        if return_pct <= -self.stop_loss:
            return True

        return False


class MomentumStrategy(Strategy):
    """
    Momentum strategy: Buy when price up 3 days in a row, sell on reverse.

    Rules:
    - Buy: Last 3 consecutive days closed higher
    - Sell: Price closes lower OR 5% gain
    """

    def __init__(self, gain_target: float = 0.05):
        super().__init__("MomentumStrategy")
        self.gain_target = gain_target

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        """Buy after 3 consecutive up days."""
        if len(price_data) < 3:
            return False

        last_3 = price_data[-3:]
        return all(
            last_3[i].close > last_3[i - 1].close
            for i in range(1, 3)
        )

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        """Sell on reversal or gain target."""
        if len(price_data) < 1:
            return False

        # Sell if price reverses (lower than previous day)
        if current_price < price_data[-1].close:
            return True

        # Sell on target gain
        return_pct = (current_price - entry_price) / entry_price
        return return_pct >= self.gain_target
