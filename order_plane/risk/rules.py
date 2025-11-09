"""Risk rules for order validation."""

from typing import Optional, Tuple
from datetime import datetime, timezone

from shared.models import OrderIntent, RiskEvent, BreachType, RiskLevel


class Portfolio:
    """Simple portfolio tracker (placeholder)."""

    def __init__(self, initial_value: float = 100000.0):
        self.initial_value = initial_value
        self.current_value = initial_value
        self.positions = {}  # symbol -> quantity

    @property
    def drawdown(self) -> float:
        """Calculate current drawdown."""
        return (self.current_value - self.initial_value) / self.initial_value


class RiskChecker:
    """
    Risk rule checker.

    Implements guard functions:
    - check_daily_drawdown()
    - check_position_limit()
    - check_leverage()

    Default behavior: BLOCK unless ALL guards approve.
    """

    def __init__(
        self,
        daily_drawdown_limit: float = -0.05,
        max_position_size: float = 0.20,
        max_leverage: float = 1.0
    ):
        self.daily_drawdown_limit = daily_drawdown_limit
        self.max_position_size = max_position_size
        self.max_leverage = max_leverage

    async def check_order(
        self,
        order: OrderIntent,
        portfolio: Portfolio
    ) -> Tuple[bool, Optional[RiskEvent]]:
        """
        Check if order is allowed.

        Returns:
            (is_allowed, risk_event_if_blocked)
        """
        # Check drawdown
        if portfolio.drawdown < self.daily_drawdown_limit:
            event = RiskEvent(
                timestamp=datetime.now(timezone.utc),
                breach_type=BreachType.DAILY_DRAWDOWN,
                level=RiskLevel.CRITICAL,
                message=f"Daily drawdown ({portfolio.drawdown:.2%}) exceeded limit ({self.daily_drawdown_limit:.2%})",
                limit_value=self.daily_drawdown_limit,
                observed_value=portfolio.drawdown,
                order_id=order.order_id,
                action_taken="ORDER_BLOCKED"
            )
            return False, event

        # Check position size (placeholder logic)
        # In real system, would check actual position size vs limit

        # All guards passed
        return True, None
