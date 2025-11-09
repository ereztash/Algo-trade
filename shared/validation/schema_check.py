"""
Schema validation and roundtrip testing for data contracts.

This module verifies that all models can:
1. Serialize to JSON (model → JSON)
2. Deserialize from JSON (JSON → model)
3. Maintain equality after roundtrip (model → JSON → model)

All models MUST pass roundtrip validation before PR-2 can begin.

Usage:
    python -c "from shared.validation.schema_check import validate_all; validate_all()"
"""

import json
import sys
from datetime import datetime, timezone
from typing import Type, List, Any
from pydantic import BaseModel

# Import all models to validate
from shared.models import (
    Bar, Quote, TradeTick,
    Signal, SignalDirection,
    Allocation, PortfolioTarget,
    OrderIntent, OrderExec, OrderStatus, OrderSide, OrderType,
    RiskEvent, BreachType, RiskLevel
)


def validate_roundtrip(model_class: Type[BaseModel], instance: BaseModel) -> bool:
    """
    Validate roundtrip: model → JSON → model → assert equality.

    Args:
        model_class: The Pydantic model class
        instance: An instance of the model to test

    Returns:
        True if roundtrip successful, raises exception otherwise

    Raises:
        AssertionError: If roundtrip produces different data
        ValueError: If serialization/deserialization fails
    """
    try:
        # Step 1: Serialize to JSON
        json_str = instance.model_dump_json()

        # Step 2: Deserialize back to model
        reconstructed = model_class.model_validate_json(json_str)

        # Step 3: Verify equality
        # Note: For frozen models, we compare dict representations
        original_dict = instance.model_dump()
        reconstructed_dict = reconstructed.model_dump()

        if original_dict != reconstructed_dict:
            print(f"❌ Roundtrip failed for {model_class.__name__}")
            print(f"   Original:      {original_dict}")
            print(f"   Reconstructed: {reconstructed_dict}")
            return False

        print(f"✓ {model_class.__name__}: Roundtrip successful")
        return True

    except Exception as e:
        print(f"❌ {model_class.__name__}: Roundtrip failed with error: {e}")
        raise


def create_test_instances() -> List[tuple[Type[BaseModel], BaseModel]]:
    """
    Create test instances for all models.

    Returns:
        List of (model_class, instance) tuples
    """
    now_utc = datetime.now(timezone.utc)

    test_cases = [
        # Market models
        (Bar, Bar(
            timestamp=now_utc,
            symbol="AAPL",
            open=150.0,
            high=155.0,
            low=149.0,
            close=154.5,
            volume=1000000.0,
            interval="1D"
        )),
        (Quote, Quote(
            timestamp=now_utc,
            symbol="SPY",
            bid=450.10,
            ask=450.15,
            bid_size=100.0,
            ask_size=200.0,
            exchange="NASDAQ"
        )),
        (TradeTick, TradeTick(
            timestamp=now_utc,
            symbol="TSLA",
            price=250.50,
            size=50.0,
            side="BUY",
            exchange="NASDAQ",
            trade_id="TX123456"
        )),

        # Signal models
        (Signal, Signal(
            timestamp=now_utc,
            symbol="AAPL",
            direction=SignalDirection.LONG,
            confidence=0.75,
            rationale="SMA crossover: 50-day > 200-day",
            strategy_id="mean_reversion_v1",
            target_weight=0.5,
            stop_loss=140.0,
            take_profit=170.0
        )),

        # Allocation models
        (Allocation, Allocation(
            symbol="AAPL",
            weight=0.4,
            conviction=0.8,
            metadata={"expected_return": 0.15}
        )),
        (PortfolioTarget, PortfolioTarget(
            timestamp=now_utc,
            allocations=[
                Allocation(symbol="AAPL", weight=0.4),
                Allocation(symbol="SPY", weight=0.6),
            ],
            max_leverage=1.0,
            strategy_id="mean_reversion_v1",
            rebalance_reason="Signal threshold breach"
        )),

        # Order models
        (OrderIntent, OrderIntent(
            timestamp=now_utc,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            order_type=OrderType.LIMIT,
            limit_price=150.50,
            strategy_id="mean_reversion_v1",
            time_in_force="DAY"
        )),
        (OrderExec, OrderExec(
            timestamp=now_utc,
            symbol="AAPL",
            order_id="test-order-123",
            status=OrderStatus.FILLED,
            filled_quantity=100.0,
            average_fill_price=150.75,
            commission=1.0,
            slippage=0.25,
            broker_order_id="IBKR-123456"
        )),

        # Risk models
        (RiskEvent, RiskEvent(
            timestamp=now_utc,
            breach_type=BreachType.DAILY_DRAWDOWN,
            level=RiskLevel.CRITICAL,
            message="Daily drawdown (-5.2%) exceeded limit (-5.0%)",
            limit_value=-5.0,
            observed_value=-5.2,
            symbol="AAPL",
            order_id="test-order-123",
            action_taken="ORDER_BLOCKED"
        )),
    ]

    return test_cases


def validate_all() -> bool:
    """
    Validate all models with roundtrip tests.

    This is Gate 1 validation. Must pass before proceeding to PR-2.

    Returns:
        True if all validations pass, False otherwise

    Exit codes:
        0: All validations passed
        1: At least one validation failed
    """
    print("=" * 60)
    print("SCHEMA VALIDATION - Gate 1")
    print("=" * 60)
    print()

    test_cases = create_test_instances()
    results = []

    for model_class, instance in test_cases:
        try:
            result = validate_roundtrip(model_class, instance)
            results.append(result)
        except Exception as e:
            print(f"❌ {model_class.__name__}: Exception during validation: {e}")
            results.append(False)

    print()
    print("=" * 60)
    print(f"RESULTS: {sum(results)}/{len(results)} models passed")
    print("=" * 60)

    if all(results):
        print("✅ Gate 1 PASSED: All models validated successfully")
        print("✅ Ready to proceed to PR-2 (Orchestration)")
        return True
    else:
        print("❌ Gate 1 FAILED: Fix model validations before proceeding")
        print("❌ BLOCKING: Cannot proceed to PR-2 until all models pass")
        return False


if __name__ == "__main__":
    success = validate_all()
    sys.exit(0 if success else 1)
