"""
Risk models for the 3-plane trading system.

Defines:
- RiskEvent: Risk breach/warning event
- BreachType: Types of risk violations
- RiskLevel: Severity levels

Risk events are generated when:
- Position limits exceeded
- Drawdown thresholds breached
- PSR (Probabilistic Sharpe Ratio) falls below threshold
- Kill-switch triggered

All risk events are logged for audit and compliance.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Optional
from pydantic import Field

from shared.models.base import BaseModel, TimestampMixin, SymbolMixin


class BreachType(str, Enum):
    """Risk breach types."""
    POSITION_LIMIT = "POSITION_LIMIT"          # Single symbol position limit
    PORTFOLIO_LIMIT = "PORTFOLIO_LIMIT"        # Total portfolio limit
    DAILY_DRAWDOWN = "DAILY_DRAWDOWN"          # Intraday drawdown
    MAX_DRAWDOWN = "MAX_DRAWDOWN"              # Maximum drawdown from peak
    PSR_THRESHOLD = "PSR_THRESHOLD"            # Probabilistic Sharpe Ratio
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"      # Unusual volatility
    KILL_SWITCH = "KILL_SWITCH"                # Emergency halt triggered
    LEVERAGE_LIMIT = "LEVERAGE_LIMIT"          # Leverage exceeded
    CONCENTRATION = "CONCENTRATION"            # Over-concentration in single asset
    LIQUIDITY_RISK = "LIQUIDITY_RISK"          # Insufficient liquidity


class RiskLevel(str, Enum):
    """Risk severity levels."""
    INFO = "INFO"              # Informational (no action)
    WARNING = "WARNING"        # Warning (log but allow)
    CRITICAL = "CRITICAL"      # Critical (block order)
    EMERGENCY = "EMERGENCY"    # Emergency (halt all trading)


class RiskEvent(BaseModel, TimestampMixin):
    """
    Risk event (breach or warning).

    Generated when risk rules detect violations.
    All events are logged to reports/risk_events.log for audit.

    Critical/Emergency events block order execution.
    Warning events are logged but allow execution.

    Example:
        RiskEvent(
            timestamp=datetime.now(timezone.utc),
            breach_type=BreachType.DAILY_DRAWDOWN,
            level=RiskLevel.CRITICAL,
            message='Daily drawdown (-5.2%) exceeded limit (-5.0%)',
            limit_value=-5.0,
            observed_value=-5.2,
            order_id='123e4567-e89b-12d3-a456-426614174000',
            action_taken='ORDER_BLOCKED'
        )
    """

    breach_type: Annotated[
        BreachType,
        Field(
            description="Type of risk breach/warning"
        )
    ]

    level: Annotated[
        RiskLevel,
        Field(
            description="Severity level: INFO, WARNING, CRITICAL, EMERGENCY"
        )
    ]

    message: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Human-readable description of the risk event"
        )
    ]

    limit_value: Annotated[
        Optional[float],
        Field(
            default=None,
            description="Configured limit value (if applicable)"
        )
    ]

    observed_value: Annotated[
        Optional[float],
        Field(
            default=None,
            description="Observed value that triggered the breach (if applicable)"
        )
    ]

    symbol: Annotated[
        Optional[str],
        Field(
            default=None,
            max_length=10,
            description="Symbol associated with the breach (if applicable)"
        )
    ]

    order_id: Annotated[
        Optional[str],
        Field(
            default=None,
            max_length=100,
            description="Order ID that triggered the breach (if applicable)"
        )
    ]

    action_taken: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description="Action taken in response (e.g., 'ORDER_BLOCKED', 'POSITION_REDUCED', 'TRADING_HALTED')"
        )
    ]

    metadata: Annotated[
        Optional[dict],
        Field(
            default=None,
            description="Optional metadata (e.g., portfolio state, risk metrics)"
        )
    ]

    cool_off_until: Annotated[
        Optional[datetime],
        Field(
            default=None,
            description="Timestamp until which trading is halted (for kill-switch events)"
        )
    ]
