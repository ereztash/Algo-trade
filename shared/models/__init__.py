"""
Shared data models for the 3-plane trading system.

These models serve as the single source of truth for data contracts across:
- Data Plane: Market data ingestion and normalization
- Control Plane: Strategy orchestration and signal generation
- Execution Plane: Order execution and risk management
"""

from shared.models.base import BaseModel, TimestampMixin, SymbolMixin
from shared.models.market import Bar, Quote, TradeTick
from shared.models.signal import Signal, SignalDirection
from shared.models.allocation import Allocation, PortfolioTarget
from shared.models.order import OrderIntent, OrderExec, OrderStatus, OrderSide, OrderType
from shared.models.risk import RiskEvent, BreachType, RiskLevel

__all__ = [
    # Base
    "BaseModel",
    "TimestampMixin",
    "SymbolMixin",
    # Market
    "Bar",
    "Quote",
    "TradeTick",
    # Signal
    "Signal",
    "SignalDirection",
    # Allocation
    "Allocation",
    "PortfolioTarget",
    # Order
    "OrderIntent",
    "OrderExec",
    "OrderStatus",
    "OrderSide",
    "OrderType",
    # Risk
    "RiskEvent",
    "BreachType",
    "RiskLevel",
]
