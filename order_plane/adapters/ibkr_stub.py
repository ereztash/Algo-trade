"""IBKR broker stub (no-op for now)."""

from datetime import datetime, timezone

from shared.models import OrderIntent, OrderExec, OrderStatus


class IBKRStub:
    """
    IBKR broker stub (no-op placeholder).

    Returns ACCEPTED status (does not actually execute).
    Real IBKR integration will be added in a separate PR.
    """

    async def execute_order(self, order: OrderIntent) -> OrderExec:
        """Acknowledge order (no-op, returns ACCEPTED)."""
        return OrderExec(
            timestamp=datetime.now(timezone.utc),
            symbol=order.symbol,
            order_id=order.order_id,
            status=OrderStatus.ACCEPTED,
            filled_quantity=0.0,
            remaining_quantity=order.quantity
        )
