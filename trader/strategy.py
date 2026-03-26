"""Base strategy class and all built-in trading strategies."""

from abc import ABC, abstractmethod
from typing import List, Optional
from .models import PriceData


# ---------------------------------------------------------------------------
# Indicator helpers (pure functions, no external dependencies)
# ---------------------------------------------------------------------------

def _sma(closes: List[float], period: int) -> float:
    """Simple moving average of the last `period` closes."""
    window = closes[-period:]
    return sum(window) / len(window)


def _ema_series(closes: List[float], period: int) -> List[float]:
    """Full EMA series aligned to `closes`. Length equals len(closes)."""
    if len(closes) < period:
        avg = sum(closes) / len(closes)
        return [avg] * len(closes)
    k = 2.0 / (period + 1)
    seed = sum(closes[:period]) / period
    emas = [seed]
    for price in closes[period:]:
        emas.append(price * k + emas[-1] * (1 - k))
    return [emas[0]] * (period - 1) + emas  # pad front so len matches


def _rsi(closes: List[float], period: int = 14) -> float:
    """
    Wilder RSI for the most recent bar.
    Returns a value in [0, 100]. Returns 50 (neutral) if not enough data.
    """
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


def _bollinger(closes: List[float], period: int = 20, n_std: float = 2.0):
    """
    Returns (lower_band, middle_band, upper_band) using the last `period` closes.
    Returns (None, None, None) if not enough data.
    """
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    mean = sum(window) / period
    variance = sum((p - mean) ** 2 for p in window) / period
    std = variance ** 0.5
    return mean - n_std * std, mean, mean + n_std * std


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


# ---------------------------------------------------------------------------
# Technical strategies
# ---------------------------------------------------------------------------

class RSIOversoldStrategy(Strategy):
    """
    RSI Oversold/Overbought mean-reversion strategy.

    Uses the Relative Strength Index (14-day Wilder smoothing) to detect
    when a stock is statistically oversold (likely to bounce) or overbought
    (likely to pull back).

    Buy signal:
        RSI drops below `oversold_threshold` (default 30). A reading below 30
        suggests the stock has been sold excessively and a reversal is likely.

    Sell signal:
        RSI rises above `overbought_threshold` (default 70), meaning the bounce
        played out and the stock may be stretched; OR stop-loss triggers.

    Best suited for:
        - Range-bound or mean-reverting stocks (consumer staples, utilities).
        - Stocks experiencing short-term panic sells without fundamental change.

    Not ideal for:
        - Strongly trending stocks — RSI can remain below 30 for extended periods
          in a real downtrend (avoid using on stocks in structural decline).

    Parameters:
        rsi_period (int): Lookback for RSI calculation. Default 14 (Wilder standard).
        oversold_threshold (float): RSI level triggering a buy. Default 30.
        overbought_threshold (float): RSI level triggering a sell. Default 70.
        stop_loss (float): Exit if loss exceeds this fraction. Default 0.05 (5%).
    """

    def __init__(
        self,
        rsi_period: int = 14,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
        stop_loss: float = 0.05,
    ):
        super().__init__("RSIOversold")
        self.rsi_period = rsi_period
        self.oversold_threshold = oversold_threshold
        self.overbought_threshold = overbought_threshold
        self.stop_loss = stop_loss

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        closes = [b.close for b in price_data] + [current_price]
        return _rsi(closes, self.rsi_period) < self.oversold_threshold

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        closes = [b.close for b in price_data] + [current_price]
        if _rsi(closes, self.rsi_period) > self.overbought_threshold:
            return True
        return (current_price - entry_price) / entry_price <= -self.stop_loss


class BollingerBandsStrategy(Strategy):
    """
    Bollinger Bands mean-reversion strategy.

    Bollinger Bands place a volatility envelope around a moving average.
    The bands expand during high-volatility periods and contract when
    volatility is low. Prices outside the bands are statistically unusual
    and tend to revert toward the mean.

    Buy signal:
        Current price closes BELOW the lower band (mean - n_std * std_dev).
        Interpretation: price is unusually cheap relative to recent volatility.

    Sell signal:
        Price rises back to the UPPER band (mean + n_std * std_dev) — full
        reversion captured; OR price reaches the middle band (mean) for a
        partial-profit approach; OR stop-loss triggers.

    Best suited for:
        - Stocks with stable, range-bound price action.
        - Works well during periods of normal market volatility.

    Not ideal for:
        - Trending markets: price can "walk the band" and never revert.
        - Earnings events or news-driven moves (one-sided volatility spike).

    Parameters:
        period (int): Moving average period for band calculation. Default 20.
        n_std (float): Band width in standard deviations. Default 2.0
                       (statistically, ~95% of prices fall inside the bands).
        stop_loss (float): Exit if loss exceeds this fraction. Default 0.04 (4%).
    """

    def __init__(self, period: int = 20, n_std: float = 2.0, stop_loss: float = 0.04):
        super().__init__("BollingerBands")
        self.period = period
        self.n_std = n_std
        self.stop_loss = stop_loss

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        closes = [b.close for b in price_data]
        lower, _, _ = _bollinger(closes, self.period, self.n_std)
        if lower is None:
            return False
        return current_price < lower

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        closes = [b.close for b in price_data]
        _, middle, upper = _bollinger(closes, self.period, self.n_std)
        if upper is None:
            return False
        if current_price >= upper:
            return True
        return (current_price - entry_price) / entry_price <= -self.stop_loss


class MACDCrossoverStrategy(Strategy):
    """
    MACD (Moving Average Convergence Divergence) crossover strategy.

    MACD measures momentum by comparing two exponential moving averages.
    The MACD line (fast EMA - slow EMA) crossing above the signal line
    indicates accelerating upward momentum; crossing below signals deceleration.

    Components:
        MACD line   = EMA(fast_period) - EMA(slow_period)   [default: EMA12 - EMA26]
        Signal line = EMA(MACD line, signal_period)          [default: EMA9 of MACD]
        Histogram   = MACD line - Signal line

    Buy signal:
        MACD line crosses ABOVE the signal line (histogram goes from negative to
        positive). Indicates momentum is shifting upward.

    Sell signal:
        MACD line crosses BELOW the signal line (histogram goes from positive to
        negative). Momentum has shifted downward; OR stop-loss triggers.

    Best suited for:
        - Trending markets with clear directional moves.
        - Medium-term swing trading (days to weeks).

    Not ideal for:
        - Choppy, sideways markets — generates many false crossovers ("whipsaws").
        - Very short timeframes where noise dominates.

    Parameters:
        fast_period (int): Fast EMA period. Default 12.
        slow_period (int): Slow EMA period. Default 26.
        signal_period (int): Signal line EMA period. Default 9.
        stop_loss (float): Exit if loss exceeds this fraction. Default 0.05 (5%).

    Note: Requires at least slow_period + signal_period bars (default 35) of history
    before generating signals.
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        stop_loss: float = 0.05,
    ):
        super().__init__("MACDCrossover")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.stop_loss = stop_loss

    def _macd_and_signal(self, closes: List[float]):
        """Returns (macd_value, signal_value) for the last bar, or (None, None)."""
        if len(closes) < self.slow_period + self.signal_period:
            return None, None
        fast = _ema_series(closes, self.fast_period)
        slow = _ema_series(closes, self.slow_period)
        macd_series = [f - s for f, s in zip(fast, slow)]
        signal_series = _ema_series(macd_series, self.signal_period)
        return macd_series[-1], signal_series[-1], macd_series[-2], signal_series[-2]

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        closes = [b.close for b in price_data] + [current_price]
        result = self._macd_and_signal(closes)
        if result[0] is None:
            return False
        macd, signal, prev_macd, prev_signal = result
        # Crossover: was below signal, now above
        return prev_macd <= prev_signal and macd > signal

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        closes = [b.close for b in price_data] + [current_price]
        result = self._macd_and_signal(closes)
        if result[0] is None:
            return False
        macd, signal, prev_macd, prev_signal = result
        if prev_macd >= prev_signal and macd < signal:
            return True
        return (current_price - entry_price) / entry_price <= -self.stop_loss


class MeanReversionStrategy(Strategy):
    """
    Statistical mean reversion strategy using z-score.

    Assumes prices fluctuate around a stable mean. When price moves too far
    below the mean (high negative z-score), it is expected to revert upward.
    The z-score measures how many standard deviations away from the mean
    the current price is.

    z-score = (mean - current_price) / std_dev

    A positive z-score means price is BELOW the mean.
    A negative z-score means price is ABOVE the mean.

    Buy signal:
        z-score > z_score_buy (default 1.5): price is 1.5+ standard deviations
        below the mean. Statistically, ~93% of prices are within 1.5 std devs,
        so this is an unusual low.

    Sell signal:
        Price returns to mean (z-score crosses 0 from above), meaning the
        reversion trade has played out; OR stop-loss triggers.

    Best suited for:
        - Stable, large-cap stocks with predictable trading ranges.
        - Consumer staples, utilities, REITs.

    Not ideal for:
        - Growth stocks or stocks in a fundamental downtrend (mean itself is falling).
        - Small caps with low liquidity.

    Parameters:
        period (int): Lookback window for mean/std calculation. Default 30.
        z_score_buy (float): Minimum z-score to trigger a buy. Default 1.5.
        stop_loss (float): Exit if loss exceeds this fraction. Default 0.05 (5%).
    """

    def __init__(self, period: int = 30, z_score_buy: float = 1.5, stop_loss: float = 0.05):
        super().__init__("MeanReversion")
        self.period = period
        self.z_score_buy = z_score_buy
        self.stop_loss = stop_loss

    def _z_score(self, closes: List[float], current_price: float) -> Optional[float]:
        if len(closes) < self.period:
            return None
        window = closes[-self.period:]
        mean = sum(window) / self.period
        variance = sum((p - mean) ** 2 for p in window) / self.period
        std = variance ** 0.5
        if std == 0:
            return 0.0
        return (mean - current_price) / std

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        closes = [b.close for b in price_data]
        z = self._z_score(closes, current_price)
        return z is not None and z >= self.z_score_buy

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        closes = [b.close for b in price_data]
        z = self._z_score(closes, current_price)
        if z is not None and z <= 0:  # price is at or above mean — reversion complete
            return True
        return (current_price - entry_price) / entry_price <= -self.stop_loss


class MACrossoverStrategy(Strategy):
    """
    Dual Moving Average Crossover strategy (Golden Cross / Death Cross).

    One of the oldest and most widely followed trend-following signals.
    When a shorter-term moving average crosses above a longer-term one,
    it signals the start of an uptrend ("Golden Cross"). The reverse is
    a "Death Cross".

    Buy signal:
        fast_ma crosses ABOVE slow_ma — uptrend is beginning or resuming.

    Sell signal:
        fast_ma crosses BELOW slow_ma — uptrend has ended, downtrend beginning.

    Classic configurations:
        - 20/50 (default): medium-term swing trades, requires 50+ bars.
        - 50/200 ("Golden/Death Cross"): long-term trend, requires 200+ bars.
          Use period="2y" in backtests when using 50/200.

    Best suited for:
        - Trending markets with sustained directional moves.
        - Set-and-forget style position trading.

    Not ideal for:
        - Sideways/range-bound markets — generates "whipsaw" false signals.
        - Short-term trading (MA crossovers lag by design).

    Parameters:
        fast_period (int): Fast moving average period. Default 20.
        slow_period (int): Slow moving average period. Default 50.

    Note: No stop-loss by default — exits are driven purely by the death cross.
    Add a stop-loss by subclassing if needed.
    """

    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        super().__init__("MACrossover")
        self.fast_period = fast_period
        self.slow_period = slow_period

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        closes = [b.close for b in price_data] + [current_price]
        if len(closes) < self.slow_period + 1:
            return False
        fast_now = _sma(closes, self.fast_period)
        slow_now = _sma(closes, self.slow_period)
        fast_prev = _sma(closes[:-1], self.fast_period)
        slow_prev = _sma(closes[:-1], self.slow_period)
        return fast_prev <= slow_prev and fast_now > slow_now  # crossover

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        closes = [b.close for b in price_data] + [current_price]
        if len(closes) < self.slow_period + 1:
            return False
        fast_now = _sma(closes, self.fast_period)
        slow_now = _sma(closes, self.slow_period)
        fast_prev = _sma(closes[:-1], self.fast_period)
        slow_prev = _sma(closes[:-1], self.slow_period)
        return fast_prev >= slow_prev and fast_now < slow_now  # death cross


# ---------------------------------------------------------------------------
# Fundamental-enhanced hybrid strategies
# ---------------------------------------------------------------------------

class QualityDipStrategy(Strategy):
    """
    Quality Filter + Mean Reversion hybrid strategy.

    Applies fundamental quality filters BEFORE allowing any position entry,
    then uses SimpleDip logic for timing. Only buys dips in companies that
    pass a fundamental health check, avoiding value traps.

    Fundamental filters (ALL must pass to allow buys):
        - EPS > 0: Company is currently profitable. Avoids companies with
          structural losses where dips may not recover.
        - P/E ratio < max_pe (default 35): Not excessively valued. A high P/E
          stock may have further to fall even after a dip.
        - Profit margin > 0: Company retains positive margins. Even a small
          positive margin is healthier than a margin-negative business.

    Technical entry/exit (same logic as SimpleDipStrategy):
        - Buy:  Price drops dip_threshold% BELOW its 20-day moving average.
        - Sell: Price rises target_gain% above entry (take profit);
                OR drops stop_loss% below entry (stop loss).

    Rationale:
        Dip-buying is most reliable in fundamentally sound companies where the
        price dip is caused by market noise (sector rotation, macro fear, short
        squeeze) rather than genuine business deterioration. A cheap stock that
        is also burning cash may never recover.

    IMPORTANT — Backtesting limitation:
        Fundamentals from yfinance reflect CURRENT values, not historical.
        Applying today's P/E to 2-year-old price data introduces look-ahead
        bias. Use this strategy for:
        (a) Short backtests (1-3 months) where fundamentals are stable.
        (b) Forward paper trading from today onward.

    Parameters:
        fundamentals (dict): Output of get_fundamentals(symbol). Must contain
            'eps', 'pe_ratio', 'profit_margin'. If None or values missing,
            the fundamental filter is skipped (falls back to SimpleDip behavior).
        dip_threshold (float): Buy when price is this % below 20-day MA. Default 0.05 (5%).
        target_gain (float): Take profit at this % gain from entry. Default 0.03 (3%).
        stop_loss (float): Stop loss at this % loss from entry. Default 0.02 (2%).
        max_pe (float): Maximum P/E ratio allowed. Default 35.
    """

    def __init__(
        self,
        fundamentals: Optional[dict] = None,
        dip_threshold: float = 0.05,
        target_gain: float = 0.03,
        stop_loss: float = 0.02,
        max_pe: float = 35.0,
    ):
        super().__init__("QualityDip")
        self.fundamentals = fundamentals or {}
        self.dip_threshold = dip_threshold
        self.target_gain = target_gain
        self.stop_loss = stop_loss
        self.max_pe = max_pe
        self._quality_ok = self._check_quality()

    def _check_quality(self) -> bool:
        if not self.fundamentals:
            return True  # no data → don't block
        eps = self.fundamentals.get("eps")
        pe = self.fundamentals.get("pe_ratio")
        margin = self.fundamentals.get("profit_margin")
        if eps is not None and eps <= 0:
            return False
        if pe is not None and pe > self.max_pe:
            return False
        if margin is not None and margin <= 0:
            return False
        return True

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        if not self._quality_ok:
            return False
        if len(price_data) < 20:
            return False
        ma_20 = _sma([b.close for b in price_data], 20)
        return (ma_20 - current_price) / ma_20 >= self.dip_threshold

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        ret = (current_price - entry_price) / entry_price
        return ret >= self.target_gain or ret <= -self.stop_loss


class GrowthMomentumStrategy(Strategy):
    """
    Growth Momentum hybrid strategy.

    Applies a forward-growth filter before riding momentum signals. Only
    enters positions in companies where analysts expect earnings to GROW,
    avoiding momentum trades in stocks that may be expensive for their growth.

    Fundamental filter (ALL must pass):
        - EPS > 0: Company must be currently profitable. Momentum in loss-making
          companies is speculative and often reverses sharply.
        - forward_pe < trailing_pe: Market expects future earnings to be HIGHER
          than current. This means the stock is "growing into" its valuation.
          A forward P/E lower than trailing P/E suggests analysts see improving
          profitability ahead.

    Technical entry/exit (same logic as MomentumStrategy):
        - Buy:  Last 3 consecutive daily closes were HIGHER than the prior day.
                Three up-days in a row signal sustained short-term momentum.
        - Sell: Price closes LOWER than the previous day (momentum lost);
                OR gain_target% profit is reached.

    Rationale:
        Momentum works best when backed by a fundamental growth story. Chasing
        momentum in stagnant or declining companies (high trailing P/E, low
        forward growth) leads to being caught in reversals. The forward/trailing
        P/E filter acts as a simple proxy for expected earnings acceleration.

    IMPORTANT — Backtesting limitation:
        forward_pe and trailing_pe are current analyst estimates from yfinance,
        not historical. This introduces look-ahead bias. Best used for:
        (a) Short backtests (1-3 months) where analyst estimates are stable.
        (b) Forward paper trading from today onward.

    Parameters:
        fundamentals (dict): Output of get_fundamentals(symbol). Must contain
            'eps', 'pe_ratio' (trailing), 'forward_pe'. If None or values
            missing, the fundamental filter is skipped (falls back to Momentum).
        gain_target (float): Take profit at this % gain from entry. Default 0.05 (5%).
    """

    def __init__(self, fundamentals: Optional[dict] = None, gain_target: float = 0.05):
        super().__init__("GrowthMomentum")
        self.fundamentals = fundamentals or {}
        self.gain_target = gain_target
        self._growth_ok = self._check_growth()

    def _check_growth(self) -> bool:
        if not self.fundamentals:
            return True
        eps = self.fundamentals.get("eps")
        pe = self.fundamentals.get("pe_ratio")
        fpe = self.fundamentals.get("forward_pe")
        if eps is not None and eps <= 0:
            return False
        if pe is not None and fpe is not None and fpe >= pe:
            return False  # forward P/E not lower → no expected earnings growth
        return True

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        if not self._growth_ok:
            return False
        if len(price_data) < 3:
            return False
        last_3 = price_data[-3:]
        return all(last_3[i].close > last_3[i - 1].close for i in range(1, 3))

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        if len(price_data) < 1:
            return False
        if current_price < price_data[-1].close:
            return True
        return (current_price - entry_price) / entry_price >= self.gain_target


class LowBetaReversionStrategy(Strategy):
    """
    Low Beta Mean Reversion hybrid strategy.

    Uses beta — a measure of a stock's sensitivity to overall market movements —
    as a fundamental filter to select stocks where mean reversion is most reliable.
    Low-beta stocks move more independently of the market, making their dips
    more likely to be temporary and self-correcting.

    What is beta?
        Beta = 1.0 → stock moves exactly with the S&P 500.
        Beta < 1.0 → stock is LESS volatile than the market (more stable).
        Beta > 1.0 → stock amplifies market moves (riskier for mean reversion).
        Beta < 0   → stock moves INVERSELY to the market (rare; e.g., gold stocks).

    Fundamental filter:
        - beta < max_beta (default 0.8): Only trade stocks that are meaningfully
          less volatile than the market. These stocks have stronger gravitational
          pull back to their mean because their dips are less likely to cascade
          into structural declines.

    Technical entry/exit (same logic as SimpleDipStrategy):
        - Buy:  Price drops dip_threshold% BELOW its 20-day moving average.
        - Sell: Price rises target_gain% above entry (take profit);
                OR drops stop_loss% below entry (stop loss).

    Rationale:
        Mean reversion strategies fail on high-beta stocks because market-driven
        momentum can push them far below the mean for extended periods. Low-beta
        stocks (utilities, consumer staples, healthcare) tend to oscillate
        predictably around their mean and recover faster.

    IMPORTANT — Backtesting limitation:
        Beta from yfinance is the current 5-year monthly beta. It's relatively
        stable over time compared to P/E or EPS, making it the most reliable
        of the three fundamental filters for backtesting purposes. Still, assume
        some look-ahead bias for backtests longer than 1 year.

    Parameters:
        fundamentals (dict): Output of get_fundamentals(symbol). Must contain
            'beta'. If None or beta unavailable, the filter is skipped
            (falls back to SimpleDip behavior).
        dip_threshold (float): Buy when price is this % below 20-day MA. Default 0.05 (5%).
        target_gain (float): Take profit at this % gain from entry. Default 0.03 (3%).
        stop_loss (float): Stop loss at this % loss from entry. Default 0.02 (2%).
        max_beta (float): Maximum allowed beta. Default 0.8.
    """

    def __init__(
        self,
        fundamentals: Optional[dict] = None,
        dip_threshold: float = 0.05,
        target_gain: float = 0.03,
        stop_loss: float = 0.02,
        max_beta: float = 0.8,
    ):
        super().__init__("LowBetaReversion")
        self.fundamentals = fundamentals or {}
        self.dip_threshold = dip_threshold
        self.target_gain = target_gain
        self.stop_loss = stop_loss
        self.max_beta = max_beta
        self._beta_ok = self._check_beta()

    def _check_beta(self) -> bool:
        if not self.fundamentals:
            return True
        beta = self.fundamentals.get("beta")
        if beta is None:
            return True
        return float(beta) < self.max_beta

    def should_buy(self, price_data: List[PriceData], current_price: float) -> bool:
        if not self._beta_ok:
            return False
        if len(price_data) < 20:
            return False
        ma_20 = _sma([b.close for b in price_data], 20)
        return (ma_20 - current_price) / ma_20 >= self.dip_threshold

    def should_sell(self, price_data: List[PriceData], current_price: float, entry_price: float) -> bool:
        ret = (current_price - entry_price) / entry_price
        return ret >= self.target_gain or ret <= -self.stop_loss


# ---------------------------------------------------------------------------
# Strategy factory
# ---------------------------------------------------------------------------

STRATEGY_REGISTRY = {
    "simple_dip": {
        "class": SimpleDipStrategy,
        "needs_fundamentals": False,
        "description": "Buy when price dips 5% below 20-day MA, sell on 3% gain or 2% stop-loss.",
        "type": "technical",
        "min_bars": 20,
    },
    "momentum": {
        "class": MomentumStrategy,
        "needs_fundamentals": False,
        "description": "Buy after 3 consecutive up-days, sell on reversal or 5% gain.",
        "type": "technical",
        "min_bars": 3,
    },
    "rsi_oversold": {
        "class": RSIOversoldStrategy,
        "needs_fundamentals": False,
        "description": "Buy when RSI < 30 (oversold), sell when RSI > 70 or 5% stop-loss.",
        "type": "technical",
        "min_bars": 15,
    },
    "bollinger_bands": {
        "class": BollingerBandsStrategy,
        "needs_fundamentals": False,
        "description": "Buy when price breaks below lower Bollinger Band (2σ), sell at upper band.",
        "type": "technical",
        "min_bars": 20,
    },
    "macd_crossover": {
        "class": MACDCrossoverStrategy,
        "needs_fundamentals": False,
        "description": "Buy on MACD/signal bullish crossover, sell on bearish crossover.",
        "type": "technical",
        "min_bars": 35,
    },
    "mean_reversion": {
        "class": MeanReversionStrategy,
        "needs_fundamentals": False,
        "description": "Buy when price is 1.5 std-devs below 30-day mean, sell when it returns to mean.",
        "type": "technical",
        "min_bars": 30,
    },
    "ma_crossover": {
        "class": MACrossoverStrategy,
        "needs_fundamentals": False,
        "description": "Buy on 20/50 MA golden cross, sell on death cross. Use 2y period for 50/200.",
        "type": "technical",
        "min_bars": 50,
    },
    "quality_dip": {
        "class": QualityDipStrategy,
        "needs_fundamentals": True,
        "description": "SimpleDip only on profitable companies (EPS>0, P/E<35, positive margins).",
        "type": "fundamental+technical",
        "min_bars": 20,
    },
    "growth_momentum": {
        "class": GrowthMomentumStrategy,
        "needs_fundamentals": True,
        "description": "Momentum only when forward P/E < trailing P/E (expected earnings growth).",
        "type": "fundamental+technical",
        "min_bars": 3,
    },
    "low_beta_reversion": {
        "class": LowBetaReversionStrategy,
        "needs_fundamentals": True,
        "description": "SimpleDip only on low-beta stocks (beta < 0.8) for reliable mean reversion.",
        "type": "fundamental+technical",
        "min_bars": 20,
    },
}


def create_strategy(name: str, fundamentals: Optional[dict] = None) -> Optional[Strategy]:
    """
    Instantiate a strategy by name.

    For fundamental-enhanced strategies (quality_dip, growth_momentum,
    low_beta_reversion), pass a `fundamentals` dict from get_fundamentals().
    If fundamentals are None, those strategies fall back to their technical
    logic without the fundamental filter.

    Args:
        name: Strategy name. Must be a key in STRATEGY_REGISTRY.
        fundamentals: Optional dict from get_fundamentals(). Required for
                      fundamental-enhanced strategies.

    Returns:
        Strategy instance, or None if name is unknown.
    """
    entry = STRATEGY_REGISTRY.get(name)
    if not entry:
        return None
    cls = entry["class"]
    if entry["needs_fundamentals"]:
        return cls(fundamentals=fundamentals)
    return cls()
