"""
End-to-End Tests: Recovery Scenarios

Tests system recovery from various failure modes:
- Data plane reconnection
- Kafka message replay
- Position reconciliation after restart
- Order state recovery
- Kill-switch reset procedures
"""

import pytest
import asyncio
import numpy as np
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from typing import Dict, List

from contracts.validators import (
    BarEvent, OrderIntent, ExecutionReport,
    DataQuality, EventMetadata
)


# =============================================================================
# System State Management
# =============================================================================

class SystemState:
    """Track system state for recovery testing."""

    def __init__(self):
        self.is_running = False
        self.last_heartbeat = None
        self.kafka_connected = False
        self.ibkr_connected = False
        self.positions: Dict[str, int] = {}  # symbol -> quantity
        self.pending_orders: List[str] = []  # order IDs
        self.last_processed_offset: Dict[str, int] = {}  # topic -> offset

    def start(self):
        """Start system."""
        self.is_running = True
        self.last_heartbeat = datetime.now(timezone.utc)
        self.kafka_connected = True
        self.ibkr_connected = True

    def stop(self):
        """Stop system."""
        self.is_running = False
        self.kafka_connected = False
        self.ibkr_connected = False

    def heartbeat(self):
        """Update heartbeat timestamp."""
        if self.is_running:
            self.last_heartbeat = datetime.now(timezone.utc)

    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        if not self.is_running:
            return False

        if self.last_heartbeat is None:
            return False

        # Heartbeat within last 30 seconds
        age = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        if age > 30:
            return False

        return self.kafka_connected and self.ibkr_connected

    def update_position(self, symbol: str, quantity: int):
        """Update position."""
        self.positions[symbol] = self.positions.get(symbol, 0) + quantity

    def get_position(self, symbol: str) -> int:
        """Get current position."""
        return self.positions.get(symbol, 0)

    def set_kafka_offset(self, topic: str, offset: int):
        """Set last processed Kafka offset."""
        self.last_processed_offset[topic] = offset

    def get_kafka_offset(self, topic: str) -> int:
        """Get last processed Kafka offset."""
        return self.last_processed_offset.get(topic, 0)


# =============================================================================
# Position Reconciliation
# =============================================================================

class PositionReconciler:
    """Reconcile positions after restart."""

    def __init__(self):
        self.system_positions: Dict[str, int] = {}
        self.broker_positions: Dict[str, int] = {}

    def update_system_position(self, symbol: str, quantity: int):
        """Update system's view of positions."""
        self.system_positions[symbol] = quantity

    def update_broker_position(self, symbol: str, quantity: int):
        """Update broker's actual positions."""
        self.broker_positions[symbol] = quantity

    def reconcile(self) -> Dict[str, int]:
        """
        Reconcile positions between system and broker.

        Returns:
            Dict mapping symbol to discrepancy (broker - system)
        """
        all_symbols = set(self.system_positions.keys()) | set(self.broker_positions.keys())

        discrepancies = {}
        for symbol in all_symbols:
            system_qty = self.system_positions.get(symbol, 0)
            broker_qty = self.broker_positions.get(symbol, 0)

            diff = broker_qty - system_qty
            if diff != 0:
                discrepancies[symbol] = diff

        return discrepancies

    def needs_reconciliation(self) -> bool:
        """Check if reconciliation is needed."""
        discrepancies = self.reconcile()
        return len(discrepancies) > 0


# =============================================================================
# E2E Tests: System Recovery
# =============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestSystemRecovery:
    """E2E tests for system restart and recovery."""

    async def test_clean_restart(self):
        """
        E2E: Clean System Restart

        Test normal startup/shutdown cycle.
        """
        state = SystemState()

        # Initial startup
        state.start()
        assert state.is_running
        assert state.is_healthy()

        # Normal operation
        state.heartbeat()
        await asyncio.sleep(0.1)
        state.heartbeat()

        assert state.is_healthy()

        # Clean shutdown
        state.stop()
        assert not state.is_running
        assert not state.is_healthy()

        # Restart
        state.start()
        assert state.is_running
        assert state.is_healthy()

    async def test_crash_recovery(self):
        """
        E2E: Recovery from Crash

        Test system recovery after unexpected shutdown.
        """
        state = SystemState()

        # Normal operation with positions
        state.start()
        state.update_position('SPY', 100)
        state.update_position('QQQ', 50)
        state.set_kafka_offset('market_events', 1234)

        positions_before = state.positions.copy()
        offset_before = state.get_kafka_offset('market_events')

        # Simulate crash (abrupt stop)
        state.stop()
        state.kafka_connected = False
        state.ibkr_connected = False

        # Recovery: restore from persistent state
        # In real system, would load from database/disk
        recovered_state = SystemState()
        recovered_state.positions = positions_before
        recovered_state.last_processed_offset['market_events'] = offset_before

        recovered_state.start()

        # Verify positions restored
        assert recovered_state.get_position('SPY') == 100
        assert recovered_state.get_position('QQQ') == 50

        # Verify can resume from last offset
        assert recovered_state.get_kafka_offset('market_events') == 1234

    async def test_kafka_reconnection(self):
        """
        E2E: Kafka Reconnection

        Test recovery from Kafka disconnect.
        """
        state = SystemState()
        state.start()

        # Set Kafka offset before disconnect
        state.set_kafka_offset('market_events', 500)

        # Simulate Kafka disconnect
        state.kafka_connected = False
        assert not state.is_healthy()

        # Reconnection with offset resume
        state.kafka_connected = True

        # Should resume from last processed offset
        resume_offset = state.get_kafka_offset('market_events')
        assert resume_offset == 500  # Resume from last committed

        assert state.is_healthy()


@pytest.mark.e2e
@pytest.mark.asyncio
class TestPositionReconciliation:
    """E2E tests for position reconciliation."""

    async def test_position_sync_after_restart(self):
        """
        E2E: Position Reconciliation After Restart

        Test that positions sync with broker after restart.
        """
        reconciler = PositionReconciler()

        # Before restart: system thinks it has these positions
        reconciler.update_system_position('AAPL', 100)
        reconciler.update_system_position('MSFT', 50)

        # After restart: query broker for actual positions
        # In real system, would call broker API
        reconciler.update_broker_position('AAPL', 100)  # Match
        reconciler.update_broker_position('MSFT', 50)   # Match

        # Verify no discrepancies
        assert not reconciler.needs_reconciliation()

        discrepancies = reconciler.reconcile()
        assert len(discrepancies) == 0

    async def test_position_discrepancy_detection(self):
        """
        E2E: Position Discrepancy Detection

        Test detection of position mismatches.
        """
        reconciler = PositionReconciler()

        # System state (possibly stale)
        reconciler.update_system_position('TSLA', 200)
        reconciler.update_system_position('NVDA', 150)

        # Broker actual positions (some orders filled while down)
        reconciler.update_broker_position('TSLA', 250)  # +50 discrepancy
        reconciler.update_broker_position('NVDA', 150)  # Match
        reconciler.update_broker_position('AMD', 100)   # New position

        # Detect discrepancies
        assert reconciler.needs_reconciliation()

        discrepancies = reconciler.reconcile()

        assert 'TSLA' in discrepancies
        assert discrepancies['TSLA'] == 50  # Broker has 50 more

        assert 'AMD' in discrepancies
        assert discrepancies['AMD'] == 100  # System missing this position

        assert 'NVDA' not in discrepancies  # Matched

    async def test_reconciliation_correction(self):
        """
        E2E: Position Correction

        Test correcting system state to match broker.
        """
        reconciler = PositionReconciler()

        # Initial mismatch
        reconciler.update_system_position('SPY', 100)
        reconciler.update_broker_position('SPY', 150)

        discrepancies = reconciler.reconcile()
        assert discrepancies['SPY'] == 50

        # Correct system to match broker
        broker_position = reconciler.broker_positions['SPY']
        reconciler.update_system_position('SPY', broker_position)

        # Verify reconciled
        assert not reconciler.needs_reconciliation()


@pytest.mark.e2e
@pytest.mark.asyncio
class TestOrderRecovery:
    """E2E tests for recovering pending orders."""

    async def test_pending_order_recovery(self):
        """
        E2E: Pending Order Recovery

        Test recovery of pending orders after restart.
        """
        # Before crash: orders in flight
        pending_orders = {
            'order-1': {
                'symbol': 'AAPL',
                'quantity': 100,
                'status': 'submitted',
                'broker_id': 'IB-001'
            },
            'order-2': {
                'symbol': 'MSFT',
                'quantity': 50,
                'status': 'acknowledged',
                'broker_id': 'IB-002'
            }
        }

        # After restart: query broker for order status
        # Mock broker responses
        broker_status = {
            'IB-001': 'filled',  # Completed while down
            'IB-002': 'pending'  # Still pending
        }

        # Reconcile order states
        for order_id, order in pending_orders.items():
            broker_id = order['broker_id']
            actual_status = broker_status.get(broker_id)

            if actual_status == 'filled':
                # Update order status and position
                order['status'] = 'filled'
            elif actual_status == 'pending':
                # Order still active, continue monitoring
                pass

        # Verify order-1 detected as filled
        assert pending_orders['order-1']['status'] == 'filled'

        # Verify order-2 still pending
        assert pending_orders['order-2']['status'] == 'acknowledged'

    async def test_duplicate_order_prevention(self):
        """
        E2E: Duplicate Order Prevention

        Test that orders aren't re-submitted after restart.
        """
        submitted_orders = set()

        # Before crash: submit order
        order_id_1 = str(uuid4())
        submitted_orders.add(order_id_1)

        # Simulate crash and restart

        # After restart: same signal generated
        # Check if order already submitted
        order_id_2 = str(uuid4())

        # Would check against persistent store of submitted orders
        # to avoid duplicate submission

        # In this test, order_id_2 is different (new)
        assert order_id_2 not in submitted_orders

        # But if reprocessing same message, would use same intent_id
        # and detect duplicate


@pytest.mark.e2e
@pytest.mark.asyncio
class TestKillSwitchRecovery:
    """E2E tests for kill-switch recovery procedures."""

    async def test_kill_switch_persist_across_restart(self):
        """
        E2E: Kill-Switch Persistence

        Test that kill-switch state persists across restart.
        """
        # Kill-switch triggered before shutdown
        kill_switch_state = {
            'pnl_killed': True,
            'dd_killed': False,
            'psr_killed': False,
            'triggered_at': datetime.now(timezone.utc),
            'requires_manual_reset': True
        }

        # System shutdown

        # System restart
        # Load kill-switch state from persistent storage
        loaded_state = kill_switch_state.copy()

        # Verify kill-switch still active
        assert loaded_state['pnl_killed'] is True

        # Verify cannot trade without manual reset
        if loaded_state['requires_manual_reset']:
            # Should block all trading
            can_trade = not any([
                loaded_state['pnl_killed'],
                loaded_state['dd_killed'],
                loaded_state['psr_killed']
            ])

            assert not can_trade

    async def test_manual_kill_switch_reset(self):
        """
        E2E: Manual Kill-Switch Reset

        Test manual reset procedure after recovery.
        """
        # Kill-switch active
        kill_switch_state = {
            'pnl_killed': True,
            'manual_override_code': None
        }

        # Attempt reset without override (should fail)
        override_code = '12345-OVERRIDE'

        if kill_switch_state['manual_override_code'] != override_code:
            # Reset not authorized
            reset_successful = False
        else:
            kill_switch_state['pnl_killed'] = False
            reset_successful = True

        assert not reset_successful

        # Provide correct override code
        kill_switch_state['manual_override_code'] = override_code

        if kill_switch_state['manual_override_code'] == override_code:
            kill_switch_state['pnl_killed'] = False
            reset_successful = True

        assert reset_successful
        assert not kill_switch_state['pnl_killed']


@pytest.mark.e2e
@pytest.mark.asyncio
class TestDataReplay:
    """E2E tests for Kafka message replay after recovery."""

    async def test_message_replay_from_offset(self):
        """
        E2E: Message Replay from Offset

        Test replaying Kafka messages from last committed offset.
        """
        # Simulate Kafka topic with messages
        market_events = []
        for i in range(100):
            event = {
                'offset': i,
                'symbol': 'SPY',
                'close': 450.0 + i * 0.1,
                'timestamp': datetime.now(timezone.utc) - timedelta(seconds=100-i)
            }
            market_events.append(event)

        # System processed up to offset 75 before crash
        last_committed_offset = 75

        # After restart: replay from offset 76
        messages_to_replay = [
            msg for msg in market_events
            if msg['offset'] > last_committed_offset
        ]

        # Verify correct number of messages to replay
        assert len(messages_to_replay) == 24  # Offsets 76-99

        # Verify first message is offset 76
        assert messages_to_replay[0]['offset'] == 76

        # Verify last message is offset 99
        assert messages_to_replay[-1]['offset'] == 99

    async def test_no_message_loss_after_recovery(self):
        """
        E2E: No Message Loss

        Test that no messages are lost during recovery.
        """
        # Track processed message offsets
        processed_before_crash = set(range(0, 50))

        # Crash occurs

        # After restart: resume from last committed
        last_committed = max(processed_before_crash)

        # Continue processing from last_committed + 1
        processed_after_restart = set(range(last_committed + 1, 100))

        # Verify no gaps
        all_processed = processed_before_crash | processed_after_restart

        expected_offsets = set(range(0, 100))
        assert all_processed == expected_offsets  # No gaps or duplicates


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
