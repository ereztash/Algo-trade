"""Integration test for schema roundtrip validation."""

import pytest
from datetime import datetime, timezone

from shared.models import (
    Bar, Quote, Signal, SignalDirection,
    OrderIntent, OrderSide, OrderType,
    RiskEvent, BreachType, RiskLevel
)


def test_bar_roundtrip():
    """Test Bar model roundtrip."""
    bar = Bar(
        timestamp=datetime.now(timezone.utc),
        symbol="AAPL",
        open=150.0,
        high=155.0,
        low=149.0,
        close=154.5,
        volume=1000000.0
    )
    json_str = bar.model_dump_json()
    reconstructed = Bar.model_validate_json(json_str)
    assert bar.model_dump() == reconstructed.model_dump()


def test_signal_roundtrip():
    """Test Signal model roundtrip."""
    signal = Signal(
        timestamp=datetime.now(timezone.utc),
        symbol="AAPL",
        direction=SignalDirection.LONG,
        confidence=0.75,
        rationale="Test signal",
        strategy_id="test_strategy"
    )
    json_str = signal.model_dump_json()
    reconstructed = Signal.model_validate_json(json_str)
    assert signal.model_dump() == reconstructed.model_dump()


def test_order_roundtrip():
    """Test OrderIntent model roundtrip."""
    order = OrderIntent(
        timestamp=datetime.now(timezone.utc),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100.0,
        order_type=OrderType.LIMIT,
        limit_price=150.50,
        strategy_id="test_strategy"
    )
    json_str = order.model_dump_json()
    reconstructed = OrderIntent.model_validate_json(json_str)
    assert order.model_dump() == reconstructed.model_dump()
