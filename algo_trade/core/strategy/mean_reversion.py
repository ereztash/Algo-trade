"""Mean reversion strategy (example implementation)."""

import numpy as np
from datetime import datetime, timezone
from typing import List, Optional

from algo_trade.core.strategy.api import Strategy
from shared.models import Bar, Signal, SignalDirection


class MeanReversionStrategy(Strategy):
    """
    Simple mean reversion strategy (reference implementation).

    Logic:
    - Calculate SMA and Z-score
    - BUY when price < SMA - z_threshold * std (oversold)
    - SELL when price > SMA + z_threshold * std (overbought)
    - FLAT otherwise (no signal)

    NOT production-grade (example only).
    """

    def __init__(self, strategy_id: str = "mean_reversion_v1", lookback: int = 20, z_threshold: float = 2.0):
        super().__init__(strategy_id)
        self.lookback = lookback
        self.z_threshold = z_threshold

    async def generate_signal(self, bars: List[Bar]) -> Optional[Signal]:
        """Generate mean reversion signal."""
        if len(bars) < self.lookback:
            return None  # Not enough data

        # Extract close prices
        closes = np.array([bar.close for bar in bars[-self.lookback:]])

        # Calculate SMA and std
        sma = np.mean(closes)
        std = np.std(closes)

        # Current price and Z-score
        current_price = bars[-1].close
        z_score = (current_price - sma) / std if std > 0 else 0.0

        # Generate signal
        if z_score < -self.z_threshold:
            direction = SignalDirection.LONG
            confidence = min(abs(z_score) / (self.z_threshold * 2), 1.0)
            rationale = f"Oversold: Z-score={z_score:.2f}, SMA={sma:.2f}, price={current_price:.2f}"
        elif z_score > self.z_threshold:
            direction = SignalDirection.SHORT
            confidence = min(abs(z_score) / (self.z_threshold * 2), 1.0)
            rationale = f"Overbought: Z-score={z_score:.2f}, SMA={sma:.2f}, price={current_price:.2f}"
        else:
            return None  # No signal

        return Signal(
            timestamp=datetime.now(timezone.utc),
            symbol=bars[-1].symbol,
            direction=direction,
            confidence=round(confidence, 2),
            rationale=rationale,
            strategy_id=self.strategy_id
        )
