"""Synthetic data feed stub for testing."""

import random
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator

from shared.models import Bar


class FeedStub:
    """
    Synthetic tick generator for testing.

    Generates realistic-looking random price data with:
    - Trending behavior (drift)
    - Volatility (random walk)
    - Gaps and spikes (simulates real market behavior)
    """

    def __init__(self, symbols: list[str], num_bars: int = 100, initial_price: float = 150.0):
        self.symbols = symbols
        self.num_bars = num_bars
        self.initial_price = initial_price

    async def fetch_bars(self) -> AsyncIterator[Bar]:
        """Generate synthetic bars (async generator)."""
        for symbol in self.symbols:
            price = self.initial_price
            timestamp = datetime.now(timezone.utc) - timedelta(days=self.num_bars)

            for i in range(self.num_bars):
                # Random walk with drift
                drift = random.gauss(0.001, 0.02)  # Slight upward drift with volatility
                price = price * (1 + drift)

                # Generate OHLC with realistic patterns
                open_price = price
                high = price * (1 + abs(random.gauss(0, 0.01)))
                low = price * (1 - abs(random.gauss(0, 0.01)))
                close = price * (1 + random.gauss(0, 0.005))
                volume = random.uniform(500000, 2000000)

                bar = Bar(
                    timestamp=timestamp,
                    symbol=symbol,
                    open=round(open_price, 2),
                    high=round(max(high, open_price, close), 2),
                    low=round(min(low, open_price, close), 2),
                    close=round(close, 2),
                    volume=round(volume, 0),
                    interval='1D'
                )

                yield bar

                timestamp += timedelta(days=1)
                price = close
