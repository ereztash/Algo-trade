"""Strategy interface (adapter pattern)."""

from abc import ABC, abstractmethod
from typing import List, Optional
from shared.models import Bar, Signal


class Strategy(ABC):
    """
    Strategy interface (Abstract Base Class).

    All strategies must implement:
    - generate_signal(): Pure function that takes bars, returns signal
    - No side effects (strategies can't fetch data or modify state)
    - No I/O (all data passed as arguments)
    """

    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id

    @abstractmethod
    async def generate_signal(self, bars: List[Bar]) -> Optional[Signal]:
        """
        Generate trading signal from bar history.

        Args:
            bars: List of bars (ordered by timestamp, oldest first)

        Returns:
            Signal or None (if no signal generated)
        """
        pass
