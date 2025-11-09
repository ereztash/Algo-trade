"""
Event definitions for the 3-plane trading system orchestrator.

Events are emitted at every state transition for:
- Complete audit trail (replayability)
- Debugging and forensics
- Metrics and monitoring
- Integration testing

All events are JSON-serializable and logged to disk.
"""

from datetime import datetime
from typing import TypedDict, Optional, Any, Literal
from enum import Enum


class EventType(str, Enum):
    """Event types for the orchestrator lifecycle."""
    START = "START"
    TICK = "TICK"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    ORDER_PROPOSED = "ORDER_PROPOSED"
    ORDER_FILLED = "ORDER_FILLED"
    RISK_BREACH = "RISK_BREACH"
    SHUTDOWN = "SHUTDOWN"


class StrategyEvent(TypedDict, total=False):
    """
    Base event structure.

    All events include:
    - event_type: Discriminator for event type
    - timestamp: When the event occurred (ISO 8601 UTC)
    - metadata: Optional event-specific data
    """
    event_type: str
    timestamp: str
    metadata: Optional[dict[str, Any]]


class StartEvent(StrategyEvent):
    """
    Emitted when the orchestrator starts.

    Metadata includes:
    - mode: dry|prelive|live
    - config_path: Path to config file
    - symbols: List of symbols to trade
    """
    event_type: Literal["START"]


class TickEvent(StrategyEvent):
    """
    Emitted when new market data arrives.

    Metadata includes:
    - symbol: Symbol ticker
    - timestamp: Bar/tick timestamp
    - price: Current price (close or last)
    - volume: Volume traded
    """
    event_type: Literal["TICK"]
    symbol: str


class SignalGeneratedEvent(StrategyEvent):
    """
    Emitted when a strategy generates a signal.

    Metadata includes:
    - signal_id: Unique signal identifier
    - symbol: Symbol ticker
    - direction: LONG|SHORT|FLAT
    - confidence: Confidence score [0, 1]
    - strategy_id: Strategy that generated the signal
    """
    event_type: Literal["SIGNAL_GENERATED"]
    signal_id: str
    symbol: str
    direction: str
    confidence: float


class OrderProposedEvent(StrategyEvent):
    """
    Emitted when an order is proposed (before risk checks).

    Metadata includes:
    - order_id: Unique order identifier
    - symbol: Symbol ticker
    - side: BUY|SELL
    - quantity: Order quantity
    - order_type: MARKET|LIMIT|STOP
    """
    event_type: Literal["ORDER_PROPOSED"]
    order_id: str
    symbol: str
    side: str
    quantity: float


class OrderFilledEvent(StrategyEvent):
    """
    Emitted when an order is filled by the broker.

    Metadata includes:
    - order_id: Unique order identifier
    - symbol: Symbol ticker
    - filled_quantity: Quantity filled
    - average_fill_price: Average execution price
    - commission: Total commission paid
    """
    event_type: Literal["ORDER_FILLED"]
    order_id: str
    symbol: str
    filled_quantity: float
    average_fill_price: float


class RiskBreachEvent(StrategyEvent):
    """
    Emitted when a risk rule is breached.

    Metadata includes:
    - breach_type: Type of breach (DAILY_DRAWDOWN, POSITION_LIMIT, etc.)
    - level: INFO|WARNING|CRITICAL|EMERGENCY
    - message: Human-readable breach description
    - action_taken: Action taken (ORDER_BLOCKED, TRADING_HALTED, etc.)
    """
    event_type: Literal["RISK_BREACH"]
    breach_type: str
    level: str
    action_taken: str


class ShutdownEvent(StrategyEvent):
    """
    Emitted when the orchestrator shuts down.

    Metadata includes:
    - reason: Reason for shutdown (NORMAL, ERROR, KILL_SWITCH, etc.)
    - uptime_seconds: Total uptime in seconds
    - total_signals: Total signals generated
    - total_orders: Total orders executed
    """
    event_type: Literal["SHUTDOWN"]
    reason: str
    uptime_seconds: float
