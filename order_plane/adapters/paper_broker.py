"""Paper broker (simulated order execution)."""

import random
from datetime import datetime, timezone
from typing import Optional

from shared.models import OrderIntent, OrderExec, OrderStatus


class PaperBroker:
    """
    Paper broker (simulated fills).

    Simulates:
    - Instant fills (no real market)
    - Slippage (Gaussian noise)
    - Commission (fixed per trade)
    - Fill price = limit_price + slippage
    """

    def __init__(self, commission: float = 1.0, slippage_std: float = 0.02):
        self.commission = commission
        self.slippage_std = slippage_std

    async def execute_order(self, order: OrderIntent) -> OrderExec:
        """Execute order (simulated fill)."""
        # Simulate slippage
        slippage = random.gauss(0, self.slippage_std)

        # Fill price (limit price + slippage if LIMIT, else use a default)
        if order.limit_price:
            fill_price = order.limit_price * (1 + slippage)
        else:
            # For MARKET orders, assume we fill at some estimated price
            fill_price = 150.0 * (1 + slippage)  # Placeholder

        return OrderExec(
            timestamp=datetime.now(timezone.utc),
            symbol=order.symbol,
            order_id=order.order_id,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            remaining_quantity=0.0,
            average_fill_price=round(fill_price, 2),
            commission=self.commission,
            slippage=round(slippage, 4),
            execution_timestamp=datetime.now(timezone.utc)
        )
