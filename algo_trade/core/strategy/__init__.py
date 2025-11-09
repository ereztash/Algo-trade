"""Strategy adapters."""

from algo_trade.core.strategy.api import Strategy
from algo_trade.core.strategy.mean_reversion import MeanReversionStrategy

__all__ = ["Strategy", "MeanReversionStrategy"]
