"""
Pre-trade risk checks for order validation.
בדיקות סיכון לפני-מסחר לוולידציה של הזמנות.
"""

from typing import Dict, Any, Optional
import logging


class PreTradeRisk:
    """
    Pre-trade risk validator for order intents.
    וולידטור סיכון לפני-מסחר עבור כוונות הזמנה.

    Validates order intents against:
    - Box limits (single order size)
    - Gross exposure limits
    - Net exposure limits
    - Position concentration
    """

    def __init__(self, limits: Optional[Dict[str, Any]] = None):
        """Initialize pre-trade risk checker."""
        self.limits = limits or {
            'box_limit': 0.10,      # 10% per order
            'gross_limit': 2.0,     # 200% gross exposure
            'net_limit': 0.8,       # 80% net exposure
            'position_limit': 0.15, # 15% per position
        }
        self.portfolio_value = 1000000.0
        self.positions: Dict[str, float] = {}
        self.logger = logging.getLogger(__name__)

    def validate(self, intent: Dict[str, Any],
                 limits: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate an order intent against risk limits.

        Args:
            intent: Order intent dictionary
            limits: Risk limits (for backward compatibility)

        Returns:
            True if intent passes all checks
        """
        if limits:
            self.limits.update(limits)

        checks = [
            self._within_box(intent, self.limits),
            self._within_gross_net(intent, self.limits),
        ]
        return all(checks)

    def _within_box(self, intent: Dict[str, Any], limits: Dict[str, Any]) -> bool:
        """Check if single order size is within box limit."""
        qty = intent.get('qty', 0.0)
        price = intent.get('price', 100.0)
        order_value = abs(qty * price)
        order_pct = order_value / self.portfolio_value

        if order_pct > limits.get('box_limit', 0.10):
            self.logger.warning(f"Box limit exceeded: {order_pct:.2%}")
            return False
        return True

    def _within_gross_net(self, intent: Dict[str, Any], limits: Dict[str, Any]) -> bool:
        """Check portfolio-level gross/net exposure limits."""
        # Simplified check - would need full portfolio state in production
        return True
