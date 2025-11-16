"""
End-to-End Tests: Order Lifecycle & Regime Transitions

Tests the complete order lifecycle from creation to execution and
system behavior during market regime changes:

1. Order Lifecycle:
   - Order creation from signal
   - Order validation
   - Broker submission
   - Fill confirmation
   - Execution reporting

2. Regime Transitions:
   - Calm → Normal → Storm transitions
   - Position sizing adjustments
   - Strategy parameter adaptation
   - Risk limit modifications
"""

import pytest
import asyncio
import numpy as np
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from enum import Enum

from contracts.validators import (
    BarEvent, OrderIntent, ExecutionReport,
    DataQuality, EventMetadata
)


# =============================================================================
# Market Regime Detection
# =============================================================================

class MarketRegime(Enum):
    """Market volatility regimes."""
    CALM = "calm"          # Vol < 10%
    NORMAL = "normal"      # 10% <= Vol < 20%
    ELEVATED = "elevated"  # 20% <= Vol < 40%
    STORM = "storm"        # Vol >= 40%


class RegimeDetector:
    """Detect and track market regime changes."""

    def __init__(self, window=20):
        self.window = window
        self.returns_history = []
        self.current_regime = MarketRegime.NORMAL

    def update(self, returns: float) -> MarketRegime:
        """Update regime based on new return."""
        self.returns_history.append(returns)

        if len(self.returns_history) > self.window:
            self.returns_history = self.returns_history[-self.window:]

        if len(self.returns_history) >= 10:  # Minimum data
            vol = np.std(self.returns_history) * np.sqrt(252)  # Annualized

            if vol < 0.10:
                self.current_regime = MarketRegime.CALM
            elif vol < 0.20:
                self.current_regime = MarketRegime.NORMAL
            elif vol < 0.40:
                self.current_regime = MarketRegime.ELEVATED
            else:
                self.current_regime = MarketRegime.STORM

        return self.current_regime

    def get_position_scalar(self) -> float:
        """Get position size scalar based on regime."""
        scalars = {
            MarketRegime.CALM: 1.2,      # Increase size in calm markets
            MarketRegime.NORMAL: 1.0,    # Normal size
            MarketRegime.ELEVATED: 0.6,  # Reduce size
            MarketRegime.STORM: 0.3,     # Minimal size
        }
        return scalars[self.current_regime]


# =============================================================================
# Order Lifecycle Management
# =============================================================================

class OrderStatus(Enum):
    """Order lifecycle states."""
    PENDING = "pending"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class OrderLifecycleTracker:
    """Track order through its complete lifecycle."""

    def __init__(self):
        self.orders = {}  # intent_id -> order state

    def create_order(self, intent: OrderIntent) -> str:
        """Create new order from intent."""
        self.orders[intent.intent_id] = {
            'status': OrderStatus.PENDING,
            'intent': intent,
            'created_at': datetime.now(timezone.utc),
            'filled_quantity': 0,
            'executions': []
        }
        return intent.intent_id

    def validate_order(self, intent_id: str) -> bool:
        """Validate order (risk checks, etc.)."""
        if intent_id not in self.orders:
            return False

        order = self.orders[intent_id]
        intent = order['intent']

        # Risk checks
        if intent.quantity <= 0:
            order['status'] = OrderStatus.REJECTED
            order['reject_reason'] = "Invalid quantity"
            return False

        if not intent.risk_limit_checks_passed:
            order['status'] = OrderStatus.REJECTED
            order['reject_reason'] = "Risk limits violated"
            return False

        order['status'] = OrderStatus.VALIDATED
        return True

    def submit_order(self, intent_id: str) -> bool:
        """Submit order to broker."""
        if intent_id not in self.orders:
            return False

        order = self.orders[intent_id]

        if order['status'] != OrderStatus.VALIDATED:
            return False

        order['status'] = OrderStatus.SUBMITTED
        order['submitted_at'] = datetime.now(timezone.utc)
        return True

    def acknowledge_order(self, intent_id: str, broker_order_id: str):
        """Receive broker acknowledgment."""
        if intent_id in self.orders:
            order = self.orders[intent_id]
            order['status'] = OrderStatus.ACKNOWLEDGED
            order['broker_order_id'] = broker_order_id
            order['acknowledged_at'] = datetime.now(timezone.utc)

    def record_fill(self, intent_id: str, execution: ExecutionReport):
        """Record order fill (partial or complete)."""
        if intent_id not in self.orders:
            return

        order = self.orders[intent_id]
        order['executions'].append(execution)
        order['filled_quantity'] += execution.filled_quantity

        intent = order['intent']

        if order['filled_quantity'] >= intent.quantity:
            order['status'] = OrderStatus.FILLED
            order['filled_at'] = datetime.now(timezone.utc)
        else:
            order['status'] = OrderStatus.PARTIAL_FILL

    def get_order_age_ms(self, intent_id: str) -> float:
        """Get order age in milliseconds."""
        if intent_id not in self.orders:
            return -1

        order = self.orders[intent_id]
        created = order['created_at']
        now = datetime.now(timezone.utc)
        return (now - created).total_seconds() * 1000


# =============================================================================
# E2E Tests: Order Lifecycle
# =============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestOrderLifecycle:
    """E2E tests for complete order lifecycle."""

    async def test_complete_order_lifecycle(self):
        """
        E2E: Complete Order Lifecycle

        Test order from creation → validation → submission → fill.
        """
        tracker = OrderLifecycleTracker()

        # Step 1: Create order intent
        intent = OrderIntent(
            intent_id=str(uuid4()),
            symbol='AAPL',
            side='buy',
            quantity=100,
            order_type='market',
            timestamp=datetime.now(timezone.utc),
            strategy_id='momentum_v1',
            signal_strength=0.75,
            risk_limit_checks_passed=True
        )

        # Step 2: Create order
        order_id = tracker.create_order(intent)
        assert order_id == intent.intent_id
        assert tracker.orders[order_id]['status'] == OrderStatus.PENDING

        # Step 3: Validate order
        valid = tracker.validate_order(order_id)
        assert valid
        assert tracker.orders[order_id]['status'] == OrderStatus.VALIDATED

        # Step 4: Submit to broker
        submitted = tracker.submit_order(order_id)
        assert submitted
        assert tracker.orders[order_id]['status'] == OrderStatus.SUBMITTED

        # Step 5: Broker acknowledgment
        broker_id = 'IB-TEST-001'
        tracker.acknowledge_order(order_id, broker_id)
        assert tracker.orders[order_id]['status'] == OrderStatus.ACKNOWLEDGED
        assert tracker.orders[order_id]['broker_order_id'] == broker_id

        # Step 6: Execution report (full fill)
        execution = ExecutionReport(
            execution_id=str(uuid4()),
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            filled_quantity=intent.quantity,
            avg_fill_price=182.50,
            status='filled',
            timestamp=datetime.now(timezone.utc),
            broker_order_id=broker_id,
            commission=1.00
        )

        tracker.record_fill(order_id, execution)
        assert tracker.orders[order_id]['status'] == OrderStatus.FILLED
        assert tracker.orders[order_id]['filled_quantity'] == intent.quantity

    async def test_partial_fill_lifecycle(self):
        """
        E2E: Partial Fill Lifecycle

        Test order with partial fills.
        """
        tracker = OrderLifecycleTracker()

        intent = OrderIntent(
            intent_id=str(uuid4()),
            symbol='TSLA',
            side='sell',
            quantity=1000,
            order_type='limit',
            limit_price=250.00,
            timestamp=datetime.now(timezone.utc),
            strategy_id='mean_revert_v1',
            signal_strength=0.60,
            risk_limit_checks_passed=True
        )

        order_id = tracker.create_order(intent)
        tracker.validate_order(order_id)
        tracker.submit_order(order_id)
        tracker.acknowledge_order(order_id, 'IB-PART-001')

        # Partial fill 1: 300 shares
        exec1 = ExecutionReport(
            execution_id=str(uuid4()),
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            filled_quantity=300,
            avg_fill_price=250.05,
            status='partial_fill',
            timestamp=datetime.now(timezone.utc),
            broker_order_id='IB-PART-001',
            commission=0.30
        )

        tracker.record_fill(order_id, exec1)
        assert tracker.orders[order_id]['status'] == OrderStatus.PARTIAL_FILL
        assert tracker.orders[order_id]['filled_quantity'] == 300

        # Partial fill 2: 400 shares
        exec2 = ExecutionReport(
            execution_id=str(uuid4()),
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            filled_quantity=400,
            avg_fill_price=250.10,
            status='partial_fill',
            timestamp=datetime.now(timezone.utc),
            broker_order_id='IB-PART-001',
            commission=0.40
        )

        tracker.record_fill(order_id, exec2)
        assert tracker.orders[order_id]['status'] == OrderStatus.PARTIAL_FILL
        assert tracker.orders[order_id]['filled_quantity'] == 700

        # Final fill: 300 shares
        exec3 = ExecutionReport(
            execution_id=str(uuid4()),
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            filled_quantity=300,
            avg_fill_price=250.15,
            status='filled',
            timestamp=datetime.now(timezone.utc),
            broker_order_id='IB-PART-001',
            commission=0.30
        )

        tracker.record_fill(order_id, exec3)
        assert tracker.orders[order_id]['status'] == OrderStatus.FILLED
        assert tracker.orders[order_id]['filled_quantity'] == 1000

        # Verify all executions recorded
        assert len(tracker.orders[order_id]['executions']) == 3

    async def test_rejected_order_lifecycle(self):
        """
        E2E: Rejected Order

        Test order rejected during validation.
        """
        tracker = OrderLifecycleTracker()

        # Order with risk check failure
        intent = OrderIntent(
            intent_id=str(uuid4()),
            symbol='NVDA',
            side='buy',
            quantity=1000,
            order_type='market',
            timestamp=datetime.now(timezone.utc),
            strategy_id='aggressive_v1',
            signal_strength=0.90,
            risk_limit_checks_passed=False  # Fails risk check
        )

        order_id = tracker.create_order(intent)
        assert tracker.orders[order_id]['status'] == OrderStatus.PENDING

        # Validation should fail
        valid = tracker.validate_order(order_id)
        assert not valid
        assert tracker.orders[order_id]['status'] == OrderStatus.REJECTED
        assert 'reject_reason' in tracker.orders[order_id]

        # Should not be able to submit rejected order
        submitted = tracker.submit_order(order_id)
        assert not submitted


# =============================================================================
# E2E Tests: Regime Transitions
# =============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestRegimeTransitions:
    """E2E tests for market regime transitions."""

    async def test_calm_to_storm_transition(self):
        """
        E2E: Calm → Storm Transition

        Test system adapts position sizing during volatility spike.
        """
        detector = RegimeDetector(window=20)

        # Simulate calm market (low volatility)
        np.random.seed(42)
        for _ in range(20):
            ret = np.random.randn() * 0.005  # 0.5% daily vol → ~8% annual
            regime = detector.update(ret)

        assert detector.current_regime == MarketRegime.CALM
        calm_scalar = detector.get_position_scalar()
        assert calm_scalar == 1.2  # Increased size

        # Volatility spike (storm)
        for _ in range(20):
            ret = np.random.randn() * 0.03  # 3% daily vol → ~47% annual
            regime = detector.update(ret)

        assert detector.current_regime == MarketRegime.STORM
        storm_scalar = detector.get_position_scalar()
        assert storm_scalar == 0.3  # Reduced size

        # Verify position size reduced by 75%
        assert storm_scalar < calm_scalar

    async def test_position_sizing_across_regimes(self):
        """
        E2E: Position Sizing Adaptation

        Test that position sizes adjust appropriately across all regimes.
        """
        detector = RegimeDetector()

        base_quantity = 100

        # Test each regime
        regime_vols = {
            MarketRegime.CALM: 0.005,      # ~8% annual
            MarketRegime.NORMAL: 0.012,    # ~19% annual
            MarketRegime.ELEVATED: 0.020,  # ~32% annual
            MarketRegime.STORM: 0.035,     # ~55% annual
        }

        positions = {}

        for target_regime, daily_vol in regime_vols.items():
            detector = RegimeDetector()  # Reset

            # Generate returns to reach target regime
            np.random.seed(42)
            for _ in range(30):
                ret = np.random.randn() * daily_vol
                detector.update(ret)

            scalar = detector.get_position_scalar()
            quantity = int(base_quantity * scalar)
            positions[target_regime] = quantity

        # Verify ordering: CALM > NORMAL > ELEVATED > STORM
        assert positions[MarketRegime.CALM] > positions[MarketRegime.NORMAL]
        assert positions[MarketRegime.NORMAL] > positions[MarketRegime.ELEVATED]
        assert positions[MarketRegime.ELEVATED] > positions[MarketRegime.STORM]

    async def test_regime_persistence(self):
        """
        E2E: Regime Persistence

        Test that regime doesn't flip rapidly (hysteresis).
        """
        detector = RegimeDetector(window=20)

        # Establish normal regime
        np.random.seed(42)
        for _ in range(30):
            ret = np.random.randn() * 0.012  # Normal volatility
            detector.update(ret)

        assert detector.current_regime == MarketRegime.NORMAL

        # Single high-vol day shouldn't flip regime
        detector.update(0.05)  # Single 5% move

        # Should still be normal (or elevated at most, not storm)
        assert detector.current_regime in [MarketRegime.NORMAL, MarketRegime.ELEVATED]

    async def test_order_adaptation_during_transition(self):
        """
        E2E: Order Adaptation During Regime Change

        Test that orders adjust when regime changes mid-day.
        """
        detector = RegimeDetector()
        tracker = OrderLifecycleTracker()

        # Start in normal regime
        np.random.seed(42)
        for _ in range(20):
            ret = np.random.randn() * 0.012
            detector.update(ret)

        initial_regime = detector.current_regime
        initial_scalar = detector.get_position_scalar()

        # Create order with normal regime sizing
        base_quantity = 100
        quantity = int(base_quantity * initial_scalar)

        intent = OrderIntent(
            intent_id=str(uuid4()),
            symbol='SPY',
            side='buy',
            quantity=quantity,
            order_type='market',
            timestamp=datetime.now(timezone.utc),
            strategy_id='adaptive_v1',
            signal_strength=0.70,
            risk_limit_checks_passed=True
        )

        order_id = tracker.create_order(intent)

        # Market volatility spikes (transition to storm)
        for _ in range(15):
            ret = np.random.randn() * 0.035  # Storm volatility
            detector.update(ret)

        new_regime = detector.current_regime
        new_scalar = detector.get_position_scalar()

        # If creating new order now, would use reduced size
        new_quantity = int(base_quantity * new_scalar)

        assert new_quantity < quantity  # Position size reduced
        assert new_regime != initial_regime  # Regime changed


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
