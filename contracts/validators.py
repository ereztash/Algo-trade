"""
Message contract validators for the 3-plane Kafka architecture.

This module defines Pydantic models for all messages flowing through the system:
- BarEvent: OHLCV market data events (Data Plane → Strategy Plane)
- TickEvent: Level-1/Level-2 tick data (Data Plane → Strategy Plane)
- OFIEvent: Order Flow Imbalance signals (Data Plane → Strategy Plane)
- OrderIntent: Trading signals (Strategy Plane → Order Plane)
- ExecutionReport: Order execution feedback (Order Plane → Strategy Plane)

All models include comprehensive validation logic and custom validators.
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Literal, List, Dict, Any
from uuid import UUID
from datetime import datetime
import re


# ============================================================================
# Data Quality and Metadata Models
# ============================================================================

class DataQuality(BaseModel):
    """Data quality metadata for market data events."""
    completeness_score: float = Field(..., ge=0.0, le=1.0, description="Data completeness (0-1)")
    freshness_ms: int = Field(..., ge=0, description="Data freshness in milliseconds")
    source: Literal['ibkr_realtime', 'ibkr_historical', 'cache', 'synthetic'] = Field(
        ..., description="Data source"
    )


class EventMetadata(BaseModel):
    """Metadata for event tracking and routing."""
    producer_id: Optional[str] = Field(None, description="Producer service ID")
    sequence_number: Optional[int] = Field(None, ge=0, description="Sequence number for ordering")
    kafka_topic: Optional[str] = Field(None, description="Kafka topic name")


# ============================================================================
# Market Data Events (Data Plane → Strategy Plane)
# ============================================================================

class BarEvent(BaseModel):
    """
    OHLCV bar event emitted by Data Plane.

    Represents a candlestick/bar with open, high, low, close, and volume.
    Includes data quality metadata and OHLC consistency validation.
    """
    event_type: Literal['bar_event'] = 'bar_event'
    symbol: str = Field(..., min_length=1, max_length=20, pattern=r'^[A-Z0-9]+$')
    timestamp: datetime = Field(..., description="Bar close timestamp (UTC)")

    # OHLCV data
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price")
    low: float = Field(..., gt=0, description="Lowest price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: int = Field(..., ge=0, description="Trading volume")

    # Optional fields
    bar_duration: Optional[Literal['1m', '5m', '15m', '30m', '1h', '4h', '1d']] = '1d'
    asset_class: Optional[Literal['equity', 'future', 'forex', 'crypto', 'bond']] = 'equity'
    exchange: Optional[str] = None
    currency: Optional[str] = Field('USD', pattern=r'^[A-Z]{3}$')

    # Metadata
    data_quality: Optional[DataQuality] = None
    metadata: Optional[EventMetadata] = None

    @model_validator(mode='after')
    def validate_ohlc_consistency(self):
        """Validate OHLC consistency: high >= open/close, low <= open/close."""
        if all([self.high, self.low, self.open, self.close]):
            if self.high < self.open or self.high < self.close:
                raise ValueError(
                    f"High price {self.high} must be >= open {self.open} and close {self.close}"
                )
            if self.low > self.open or self.low > self.close:
                raise ValueError(
                    f"Low price {self.low} must be <= open {self.open} and close {self.close}"
                )

        return self

    class Config:
        schema_extra = {
            "example": {
                "event_type": "bar_event",
                "symbol": "SPY",
                "timestamp": "2025-11-07T16:00:00Z",
                "open": 450.25,
                "high": 452.80,
                "low": 449.50,
                "close": 451.75,
                "volume": 85234567,
                "bar_duration": "1d",
                "asset_class": "equity",
                "exchange": "NYSE",
                "currency": "USD"
            }
        }


class TickEvent(BaseModel):
    """
    Level-1/Level-2 tick event emitted by Data Plane.

    Represents real-time quote and trade data with optional Level-2 order book.
    """
    event_type: Literal['tick_event'] = 'tick_event'
    symbol: str = Field(..., min_length=1, max_length=20, pattern=r'^[A-Z0-9]+$')
    timestamp: datetime = Field(..., description="Tick timestamp (UTC)")

    # Level-1 quote data
    bid: float = Field(..., gt=0, description="Best bid price")
    ask: float = Field(..., gt=0, description="Best ask price")
    bid_size: float = Field(..., ge=0, description="Best bid size")
    ask_size: float = Field(..., ge=0, description="Best ask size")

    # Trade data
    last: Optional[float] = Field(None, gt=0, description="Last trade price")
    last_size: Optional[float] = Field(None, ge=0, description="Last trade size")

    # Level-2 order book (optional)
    level2: Optional[Dict[str, Any]] = Field(None, description="Level-2 order book data")

    # Metadata
    data_quality: Optional[DataQuality] = None
    metadata: Optional[EventMetadata] = None

    @model_validator(mode='after')
    def validate_bid_ask_spread(self):
        """Validate bid-ask spread: ask must be >= bid."""
        if self.ask < self.bid:
            raise ValueError(f"Ask {self.ask} must be >= bid {self.bid}")
        return self

    class Config:
        schema_extra = {
            "example": {
                "event_type": "tick_event",
                "symbol": "SPY",
                "timestamp": "2025-11-07T14:30:05.123Z",
                "bid": 451.50,
                "ask": 451.52,
                "bid_size": 500,
                "ask_size": 300,
                "last": 451.51,
                "last_size": 100
            }
        }


class OFIEvent(BaseModel):
    """
    Order Flow Imbalance event calculated from Level-2 quotes.

    OFI measures the net buying/selling pressure in the order book.
    """
    event_type: Literal['ofi_event'] = 'ofi_event'
    symbol: str = Field(..., min_length=1, max_length=20, pattern=r'^[A-Z0-9]+$')
    timestamp: datetime = Field(..., description="OFI calculation timestamp (UTC)")
    ofi_z: float = Field(..., description="Standardized OFI z-score")

    # Optional: raw OFI and additional metrics
    ofi_raw: Optional[float] = Field(None, description="Raw OFI value")
    ofi_ma: Optional[float] = Field(None, description="OFI moving average")
    ofi_std: Optional[float] = Field(None, description="OFI standard deviation")

    metadata: Optional[EventMetadata] = None

    class Config:
        schema_extra = {
            "example": {
                "event_type": "ofi_event",
                "symbol": "SPY",
                "timestamp": "2025-11-07T14:30:05.123Z",
                "ofi_z": 2.35,
                "ofi_raw": 1500.0,
                "ofi_ma": 100.0,
                "ofi_std": 595.7
            }
        }


# ============================================================================
# Order Intent (Strategy Plane → Order Plane)
# ============================================================================

class RiskChecks(BaseModel):
    """Pre-computed risk checks from Strategy Plane."""
    within_box_limit: bool = Field(..., description="Position within box constraints")
    within_gross_limit: bool = Field(..., description="Gross exposure within limit")
    within_net_limit: bool = Field(..., description="Net exposure within limit")
    pnl_kill_switch: bool = Field(..., description="PnL kill switch NOT triggered")
    drawdown_kill_switch: bool = Field(..., description="Drawdown kill switch NOT triggered")


class ExecutionParams(BaseModel):
    """Execution parameters for order placement."""
    pov_cap: float = Field(0.08, ge=0.0, le=1.0, description="POV (Percentage of Volume) cap")
    adv_cap: float = Field(0.10, ge=0.0, le=1.0, description="ADV (Average Daily Volume) cap")
    max_slippage_bps: float = Field(10.0, ge=0.0, description="Max slippage (basis points)")


class OrderIntentMetadata(BaseModel):
    """Metadata for order intent."""
    portfolio_id: Optional[str] = None
    regime: Optional[Literal['Calm', 'Normal', 'Storm']] = None
    kafka_topic: Optional[str] = 'order_intents'


class OrderIntent(BaseModel):
    """
    Order intent emitted by Strategy Plane to Order Plane.

    Represents a trading signal with risk checks and execution parameters.
    """
    event_type: Literal['order_intent'] = 'order_intent'
    intent_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    symbol: str = Field(..., min_length=1, max_length=20, pattern=r'^[A-Z0-9]+$')
    direction: Literal['BUY', 'SELL']
    quantity: float = Field(..., gt=0, description="Order quantity")
    order_type: Literal['MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT', 'ADAPTIVE']
    timestamp: datetime = Field(..., description="Intent generation timestamp (UTC)")
    strategy_id: Literal['OFI', 'ERN', 'VRP', 'POS', 'TSX', 'SIF', 'COMPOSITE']

    # Optional price fields
    limit_price: Optional[float] = Field(None, gt=0, description="Limit price (required for LIMIT orders)")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop price (required for STOP orders)")

    # Execution parameters
    time_in_force: Optional[Literal['DAY', 'GTC', 'IOC', 'FOK']] = 'DAY'
    urgency: Optional[Literal['LOW', 'NORMAL', 'HIGH', 'URGENT']] = 'NORMAL'

    # Portfolio context
    target_weight: Optional[float] = Field(None, ge=-1.0, le=1.0)
    current_weight: Optional[float] = Field(None, ge=-1.0, le=1.0)
    signal_strength: Optional[float] = Field(None, ge=0.0, le=1.0)

    # Risk and execution
    risk_checks: Optional[RiskChecks] = None
    execution_params: Optional[ExecutionParams] = None
    metadata: Optional[OrderIntentMetadata] = None

    @model_validator(mode='after')
    def validate_limit_price_required(self):
        """Validate that LIMIT orders have a limit_price."""
        if self.order_type == 'LIMIT' and self.limit_price is None:
            raise ValueError("LIMIT orders must specify limit_price")

        if self.order_type in ['STOP', 'STOP_LIMIT']:
            if self.stop_price is None:
                raise ValueError(f"{self.order_type} orders must specify stop_price")

        return self

    class Config:
        schema_extra = {
            "example": {
                "event_type": "order_intent",
                "intent_id": "550e8400-e29b-41d4-a716-446655440000",
                "symbol": "TSLA",
                "direction": "BUY",
                "quantity": 100,
                "order_type": "LIMIT",
                "limit_price": 245.50,
                "timestamp": "2025-11-07T14:30:00Z",
                "strategy_id": "COMPOSITE",
                "time_in_force": "DAY",
                "urgency": "NORMAL"
            }
        }


# ============================================================================
# Execution Report (Order Plane → Strategy Plane)
# ============================================================================

class Fill(BaseModel):
    """Individual fill record for partial fills."""
    fill_id: str
    quantity: float = Field(..., gt=0)
    price: float = Field(..., gt=0)
    timestamp: datetime
    commission: Optional[float] = Field(0.0, ge=0.0)


class ExecutionCosts(BaseModel):
    """Execution cost breakdown."""
    commission: float = Field(..., ge=0.0)
    slippage: Optional[float] = None
    market_impact: Optional[float] = None
    total_cost_bps: Optional[float] = Field(None, description="Total cost in basis points")


class LatencyMetrics(BaseModel):
    """Latency metrics for order execution."""
    intent_to_submit_ms: Optional[int] = Field(None, ge=0, description="Intent → Submit latency")
    submit_to_ack_ms: Optional[int] = Field(None, ge=0, description="Submit → Ack latency")
    ack_to_fill_ms: Optional[int] = Field(None, ge=0, description="Ack → Fill latency")
    total_latency_ms: Optional[int] = Field(None, ge=0, description="Total latency")


class ExecutionReportMetadata(BaseModel):
    """Metadata for execution report."""
    broker: Optional[str] = 'IBKR'
    account_id: Optional[str] = None
    kafka_topic: Optional[str] = 'exec_reports'


class ExecutionReport(BaseModel):
    """
    Execution report emitted by Order Plane after order fill.

    Provides detailed execution information including fills, costs, and latency metrics.
    """
    event_type: Literal['execution_report'] = 'execution_report'
    report_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    intent_id: str = Field(..., pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    order_id: str = Field(..., description="Broker order ID")
    symbol: str = Field(..., min_length=1, max_length=20)
    status: Literal['SUBMITTED', 'ACKNOWLEDGED', 'PARTIAL_FILL', 'FILLED', 'CANCELED', 'REJECTED', 'TIMEOUT', 'ERROR']
    timestamp: datetime = Field(..., description="Report generation timestamp (UTC)")

    # Optional fields
    direction: Optional[Literal['BUY', 'SELL']] = None
    submitted_timestamp: Optional[datetime] = None
    acknowledged_timestamp: Optional[datetime] = None
    filled_timestamp: Optional[datetime] = None

    # Quantities
    requested_quantity: Optional[float] = Field(None, gt=0)
    filled_quantity: Optional[float] = Field(0.0, ge=0.0)
    remaining_quantity: Optional[float] = Field(None, ge=0.0)

    # Pricing
    average_fill_price: Optional[float] = Field(None, gt=0)
    limit_price: Optional[float] = Field(None, gt=0)

    # Costs
    commission: Optional[float] = Field(0.0, ge=0.0)
    slippage_bps: Optional[float] = None
    execution_costs: Optional[ExecutionCosts] = None

    # Error handling
    reject_reason: Optional[str] = None
    error_message: Optional[str] = None

    # Detailed fills
    fills: Optional[List[Fill]] = None

    # Metrics
    latency_metrics: Optional[LatencyMetrics] = None
    metadata: Optional[ExecutionReportMetadata] = None

    @model_validator(mode='after')
    def filled_quantity_validation(self):
        """Validate filled_quantity <= requested_quantity."""
        if self.requested_quantity is not None and self.filled_quantity > self.requested_quantity:
            raise ValueError(f"Filled quantity {self.filled_quantity} cannot exceed requested {self.requested_quantity}")
        return self

    class Config:
        schema_extra = {
            "example": {
                "event_type": "execution_report",
                "report_id": "660e8400-e29b-41d4-a716-446655440001",
                "intent_id": "550e8400-e29b-41d4-a716-446655440000",
                "order_id": "IBKR_12345678",
                "symbol": "TSLA",
                "status": "FILLED",
                "direction": "BUY",
                "timestamp": "2025-11-07T14:30:05.500Z",
                "requested_quantity": 100,
                "filled_quantity": 100,
                "average_fill_price": 245.52,
                "commission": 1.50
            }
        }
