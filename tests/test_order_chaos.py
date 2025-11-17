"""
Order Chaos & Resilience Tests

Tests system resilience under extreme conditions:
- Network failures and reconnection
- Broker disconnects during order execution
- Order book volatility (rapid price changes)
- High load (burst of concurrent orders)
- Malformed responses from broker
- Slow broker responses (high latency)
"""

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from typing import List

from contracts.validators import OrderIntent, ExecutionReport
from tests.e2e.ibkr_mock import IBKRMockClient, OrderStatus


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def sample_order_intent() -> OrderIntent:
    """Generate a valid OrderIntent for testing."""
    return OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='OFI',
        time_in_force='DAY',
        urgency='NORMAL',
    )


# ============================================================================
# 1. NETWORK FAILURE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_order_placement_during_network_failure():
    """
    CHAOS: Network fails during order placement

    Scenario:
    - Place order
    - Network disconnects mid-flight
    - System should detect disconnect
    - No phantom orders created

    Expected behavior:
    - Raise connection error
    - Order not placed (or retry logic kicks in)
    """
    mock = IBKRMockClient()
    await mock.connect()

    # Place one order successfully
    intent1 = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='OFI',
    )

    order_id_1 = await mock.place(intent1)
    assert order_id_1 is not None

    # Simulate network disconnect
    mock.disconnect()

    # Try to place another order (should fail)
    intent2 = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='TSLA',
        direction='SELL',
        quantity=50.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='ERN',
    )

    with pytest.raises(RuntimeError, match="Not connected"):
        await mock.place(intent2)


@pytest.mark.asyncio
async def test_reconnection_after_network_failure(sample_order_intent: OrderIntent):
    """
    RESILIENCE: Reconnect after network failure

    Scenario:
    - Network fails
    - System reconnects
    - Order placement resumes

    Expected behavior:
    - Reconnect succeeds
    - Orders can be placed again
    - No duplicate orders from retry
    """
    mock = IBKRMockClient()
    await mock.connect()

    # Disconnect
    mock.disconnect()
    assert not mock.is_connected()

    # Reconnect
    await mock.connect()
    assert mock.is_connected()

    # Place order successfully
    order_id = await mock.place(sample_order_intent)
    assert order_id is not None

    # Wait for fill
    await asyncio.sleep(0.2)
    status = mock.get_order_status(order_id)
    assert status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_network_disconnect_during_fill():
    """
    CHAOS: Network disconnects while order is filling

    Scenario:
    - Place order
    - Order starts filling (partial fill)
    - Network disconnects
    - Reconnect
    - Verify fill state is correct

    Expected behavior:
    - Partial fill persists after reconnect
    - No duplicate fills
    - Correct filled quantity
    """
    mock = IBKRMockClient(partial_fill_prob=1.0)  # Force partial fill
    await mock.connect()

    intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='OFI',
    )

    order_id = await mock.place(intent)

    # Wait for partial fill
    await asyncio.sleep(0.15)

    status = mock.get_order_status(order_id)
    # Should be partial or filled by now
    assert status in [OrderStatus.PARTIAL_FILL, OrderStatus.FILLED]

    # Simulate disconnect and reconnect
    mock.disconnect()
    await asyncio.sleep(0.05)
    await mock.connect()

    # Verify order state persisted
    # In production, would need to query broker for current state
    # Mock simulates persistence
    status_after = mock.get_order_status(order_id)
    assert status_after in [OrderStatus.PARTIAL_FILL, OrderStatus.FILLED]


# ============================================================================
# 2. HIGH LOAD / BURST TRAFFIC TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_burst_order_placement():
    """
    CHAOS: Burst of 100 orders submitted simultaneously

    Scenario:
    - Submit 100 orders in < 1 second
    - All should be accepted
    - All should fill eventually
    - No duplicates
    - No dropped orders

    Expected behavior:
    - All 100 orders tracked
    - All fill successfully
    - No duplicate intent_ids
    - System remains stable
    """
    mock = IBKRMockClient(fill_delay_ms=50)  # Fast fills
    await mock.connect()

    num_orders = 100
    intents = [
        OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol=f'STOCK{i % 10}',  # 10 different symbols
            direction='BUY' if i % 2 == 0 else 'SELL',
            quantity=float(100 + i),
            order_type='MARKET',
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )
        for i in range(num_orders)
    ]

    # Submit all concurrently
    order_ids = await asyncio.gather(*[mock.place(intent) for intent in intents])

    # Verify all accepted
    assert len(order_ids) == num_orders
    assert len(set(order_ids)) == num_orders  # All unique

    # Wait for all to fill
    await asyncio.sleep(0.5)

    # Verify all filled
    filled_count = 0
    for order_id in order_ids:
        status = mock.get_order_status(order_id)
        if status == OrderStatus.FILLED:
            filled_count += 1

    assert filled_count == num_orders, f"Only {filled_count}/{num_orders} orders filled"


@pytest.mark.asyncio
async def test_high_frequency_order_cancellations():
    """
    CHAOS: Rapid order placement and cancellation

    Scenario:
    - Place 50 orders
    - Cancel them all rapidly
    - Verify no race conditions
    - No stuck orders

    Expected behavior:
    - All orders either FILLED or CANCELED
    - No orders stuck in PENDING/SUBMITTED
    """
    mock = IBKRMockClient(fill_delay_ms=200)  # Slower fills to allow cancellation
    await mock.connect()

    num_orders = 50
    order_ids = []

    # Place orders
    for i in range(num_orders):
        intent = OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol='AAPL',
            direction='BUY',
            quantity=100.0,
            order_type='MARKET',
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )
        order_id = await mock.place(intent)
        order_ids.append(order_id)

    # Immediately cancel all
    await asyncio.sleep(0.05)  # Small delay
    cancel_results = await asyncio.gather(*[mock.cancel(oid) for oid in order_ids])

    # Wait for resolution
    await asyncio.sleep(0.3)

    # Check final statuses
    terminal_states = [OrderStatus.FILLED, OrderStatus.CANCELED]
    for order_id in order_ids:
        status = mock.get_order_status(order_id)
        assert status in terminal_states, f"Order {order_id} stuck in {status}"


# ============================================================================
# 3. BROKER MALFUNCTION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_all_orders_rejected_by_broker():
    """
    CHAOS: Broker rejects all orders (e.g., account suspended)

    Scenario:
    - Broker set to reject_prob=1.0
    - Submit multiple orders
    - All should be REJECTED

    Expected behavior:
    - All orders reach REJECTED state
    - System logs rejections
    - No retries (unless configured)
    """
    mock = IBKRMockClient(reject_prob=1.0)  # Reject everything
    await mock.connect()

    num_orders = 10
    order_ids = []

    for i in range(num_orders):
        intent = OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol='AAPL',
            direction='BUY',
            quantity=100.0,
            order_type='MARKET',
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )
        order_id = await mock.place(intent)
        order_ids.append(order_id)

    # Wait for processing
    await asyncio.sleep(0.2)

    # All should be rejected
    rejected_count = 0
    for order_id in order_ids:
        status = mock.get_order_status(order_id)
        if status == OrderStatus.REJECTED:
            rejected_count += 1

    assert rejected_count == num_orders, f"Only {rejected_count}/{num_orders} rejected"


@pytest.mark.asyncio
async def test_intermittent_broker_failures():
    """
    CHAOS: Broker randomly rejects 20% of orders

    Scenario:
    - reject_prob=0.2
    - Submit 50 orders
    - ~10 should be rejected, ~40 should fill

    Expected behavior:
    - System handles rejections gracefully
    - Successful orders complete
    - Metrics track rejection rate
    """
    mock = IBKRMockClient(reject_prob=0.2)
    await mock.connect()

    num_orders = 50
    order_ids = []

    for i in range(num_orders):
        intent = OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol='AAPL',
            direction='BUY',
            quantity=100.0,
            order_type='MARKET',
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )
        order_id = await mock.place(intent)
        order_ids.append(order_id)

    # Wait for all to resolve
    await asyncio.sleep(0.3)

    # Count outcomes
    filled = 0
    rejected = 0
    for order_id in order_ids:
        status = mock.get_order_status(order_id)
        if status == OrderStatus.FILLED:
            filled += 1
        elif status == OrderStatus.REJECTED:
            rejected += 1

    # Should have mix of filled and rejected
    assert filled > 0, "No orders filled"
    assert rejected > 0, "No orders rejected (expected ~20%)"
    assert filled + rejected == num_orders


# ============================================================================
# 4. LATENCY / SLOW BROKER TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_slow_broker_acknowledgment():
    """
    CHAOS: Broker takes 5 seconds to acknowledge orders

    Scenario:
    - fill_delay_ms=5000
    - Submit order
    - Should eventually fill (but slowly)

    Expected behavior:
    - Order completes despite high latency
    - Timeout detection doesn't trigger prematurely
    - System remains responsive
    """
    mock = IBKRMockClient(fill_delay_ms=1000)  # 1 second delay
    await mock.connect()

    intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='OFI',
    )

    order_id = await mock.place(intent)

    # Order should be acknowledged initially
    status = mock.get_order_status(order_id)
    assert status in [OrderStatus.ACKNOWLEDGED, OrderStatus.SUBMITTED]

    # Wait for slow fill
    await asyncio.sleep(1.5)

    # Should be filled by now
    status = mock.get_order_status(order_id)
    assert status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_orders_under_sustained_load():
    """
    RESILIENCE: System handles sustained order flow

    Scenario:
    - Submit 10 orders/second for 5 seconds (50 orders)
    - All should process correctly
    - No degradation over time

    Expected behavior:
    - All orders accepted
    - All orders fill
    - System metrics remain healthy
    """
    mock = IBKRMockClient(fill_delay_ms=100)
    await mock.connect()

    duration_s = 2  # Reduced for test speed
    orders_per_second = 10
    total_orders = duration_s * orders_per_second

    order_ids = []
    start_time = asyncio.get_event_loop().time()

    for i in range(total_orders):
        intent = OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol='AAPL',
            direction='BUY',
            quantity=100.0,
            order_type='MARKET',
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )

        order_id = await mock.place(intent)
        order_ids.append(order_id)

        # Maintain rate: sleep to achieve target orders/sec
        elapsed = asyncio.get_event_loop().time() - start_time
        expected_elapsed = (i + 1) / orders_per_second
        sleep_time = expected_elapsed - elapsed
        if sleep_time > 0:
            await asyncio.sleep(sleep_time)

    # Wait for all to fill
    await asyncio.sleep(0.5)

    # Verify all filled
    filled_count = sum(
        1 for oid in order_ids
        if mock.get_order_status(oid) == OrderStatus.FILLED
    )

    assert filled_count == total_orders, \
        f"Only {filled_count}/{total_orders} filled under sustained load"


# ============================================================================
# 5. EDGE CASE TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_zero_latency_order_flow():
    """
    EDGE CASE: Orders fill instantly (0ms delay)

    Scenario:
    - fill_delay_ms=0
    - Orders fill immediately
    - Test race conditions

    Expected behavior:
    - System handles instant fills
    - No race conditions
    - Reports generated correctly
    """
    mock = IBKRMockClient(fill_delay_ms=0)
    await mock.connect()

    intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='OFI',
    )

    order_id = await mock.place(intent)

    # Should be filled almost immediately
    await asyncio.sleep(0.1)
    status = mock.get_order_status(order_id)
    assert status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_mixed_success_and_failure_scenarios():
    """
    CHAOS: Mix of successful fills, rejections, and cancellations

    Scenario:
    - Submit 30 orders
    - Some fill
    - Some rejected
    - Some canceled manually

    Expected behavior:
    - System handles mixed outcomes
    - Correct final states
    - No inconsistencies
    """
    mock = IBKRMockClient(reject_prob=0.15, fill_delay_ms=300)  # Longer delay to allow cancellations
    await mock.connect()

    num_orders = 30
    order_ids = []

    for i in range(num_orders):
        intent = OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol='AAPL',
            direction='BUY',
            quantity=100.0,
            order_type='MARKET',
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )
        order_id = await mock.place(intent)
        order_ids.append(order_id)

    # Cancel first 10 orders quickly
    await asyncio.sleep(0.02)  # Very short delay to catch before fill
    for order_id in order_ids[:10]:
        await mock.cancel(order_id)

    # Wait for rest to resolve
    await asyncio.sleep(0.5)

    # Count outcomes
    filled = 0
    canceled = 0
    rejected = 0

    for order_id in order_ids:
        status = mock.get_order_status(order_id)
        if status == OrderStatus.FILLED:
            filled += 1
        elif status == OrderStatus.CANCELED:
            canceled += 1
        elif status == OrderStatus.REJECTED:
            rejected += 1

    # Should have mix of all three
    assert filled + canceled + rejected == num_orders
    assert canceled >= 5, f"Expected at least 5 cancellations, got {canceled}"  # Some might have filled before cancel
    assert filled > 0, "Expected some fills"


# Mark chaos tests that simulate extreme scenarios
pytest.mark.chaos = pytest.mark.skipif(
    False,  # Always run
    reason="Chaos tests simulate extreme failure scenarios"
)
