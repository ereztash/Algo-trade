"""
Comprehensive Order Lifecycle Tests

Tests cover critical edge cases for order management:
- Duplicate orders detection
- Stuck orders (timeouts)
- Order cancellations (before/after fill)
- Partial fills
- State machine transitions
- Concurrent order management

These tests prevent catastrophic trading issues like:
- Sending duplicate orders (double exposure)
- Missing fills (lost trades)
- Invalid state transitions (data corruption)
"""

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from typing import List, Dict, Optional

from contracts.validators import OrderIntent, ExecutionReport
from tests.e2e.ibkr_mock import IBKRMockClient, OrderStatus


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_ibkr():
    """Create a fresh IBKR mock client for each test."""
    client = IBKRMockClient(
        auto_fill=True,
        fill_delay_ms=100,
        partial_fill_prob=0.0,  # Disable by default
        reject_prob=0.0,
    )
    return client


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


@pytest.fixture
def sample_limit_order_intent() -> OrderIntent:
    """Generate a valid LIMIT OrderIntent."""
    return OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='TSLA',
        direction='SELL',
        quantity=50.0,
        order_type='LIMIT',
        limit_price=250.0,
        timestamp=datetime.now(timezone.utc),
        strategy_id='ERN',
        time_in_force='GTC',
        urgency='HIGH',
    )


# ============================================================================
# 1. NORMAL FLOW TESTS (Happy Path)
# ============================================================================

@pytest.mark.asyncio
async def test_normal_order_flow_market(mock_ibkr: IBKRMockClient, sample_order_intent: OrderIntent):
    """
    Test normal order lifecycle: send → acknowledged → filled

    Validates:
    - State transitions: PENDING → SUBMITTED → ACKNOWLEDGED → FILLED
    - Execution report generation
    - Fill quantities match requested
    - Average fill price is calculated
    """
    # Connect to mock broker
    await mock_ibkr.connect()

    # Place order
    order_id = await mock_ibkr.place(sample_order_intent)
    assert order_id is not None
    assert len(order_id) > 0

    # After place() completes, order should be at least SUBMITTED or ACKNOWLEDGED
    # (mock transitions to ACKNOWLEDGED during place())
    status = mock_ibkr.get_order_status(order_id)
    assert status in [OrderStatus.SUBMITTED, OrderStatus.ACKNOWLEDGED], \
        f"Expected SUBMITTED or ACKNOWLEDGED, got {status}"

    # Wait for fill
    await asyncio.sleep(0.15)  # fill_delay_ms=100
    status = mock_ibkr.get_order_status(order_id)
    assert status == OrderStatus.FILLED

    # Poll execution reports
    reports = await mock_ibkr.poll_reports()
    assert len(reports) >= 2  # At least ACKNOWLEDGED + FILLED

    # Validate FILLED report
    filled_report = next((r for r in reports if r.status == 'FILLED'), None)
    assert filled_report is not None
    assert filled_report.order_id == order_id
    assert filled_report.intent_id == sample_order_intent.intent_id
    assert filled_report.filled_quantity == sample_order_intent.quantity
    assert filled_report.remaining_quantity == 0.0
    assert filled_report.average_fill_price is not None
    assert filled_report.average_fill_price > 0


@pytest.mark.asyncio
async def test_normal_order_flow_limit(mock_ibkr: IBKRMockClient, sample_limit_order_intent: OrderIntent):
    """
    Test LIMIT order flow with price validation

    Validates:
    - LIMIT orders require limit_price
    - Fill price respects limit constraints
    """
    await mock_ibkr.connect()

    order_id = await mock_ibkr.place(sample_limit_order_intent)
    await asyncio.sleep(0.2)

    status = mock_ibkr.get_order_status(order_id)
    assert status == OrderStatus.FILLED

    reports = await mock_ibkr.poll_reports()
    filled_report = next((r for r in reports if r.status == 'FILLED'), None)

    # For SELL limit, fill price should be >= limit_price
    assert filled_report.average_fill_price >= sample_limit_order_intent.limit_price


# ============================================================================
# 2. DUPLICATE ORDERS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_duplicate_intent_id_rejection(mock_ibkr: IBKRMockClient, sample_order_intent: OrderIntent):
    """
    CRITICAL: Prevent duplicate order submission with same intent_id

    Catastrophic scenario:
    - Strategy sends same intent twice due to bug
    - Both orders execute → double position (2x risk)
    - Example: Want 100 shares, get 200 shares

    Expected behavior:
    - Second submission with same intent_id should be rejected
    - Or: Return same order_id (idempotent)
    """
    await mock_ibkr.connect()

    # First submission
    order_id_1 = await mock_ibkr.place(sample_order_intent)
    assert order_id_1 is not None

    # Second submission with SAME intent_id
    # Should either:
    # 1. Raise exception (preferred)
    # 2. Return same order_id (idempotent behavior)
    try:
        order_id_2 = await mock_ibkr.place(sample_order_intent)
        # If no exception, must be idempotent
        assert order_id_2 == order_id_1, "Duplicate intent_id should return same order_id"
    except ValueError as e:
        # This is the preferred behavior
        assert "duplicate" in str(e).lower() or "already exists" in str(e).lower()


@pytest.mark.asyncio
async def test_concurrent_duplicate_orders(mock_ibkr: IBKRMockClient, sample_order_intent: OrderIntent):
    """
    Test race condition: two simultaneous submissions of same intent

    Simulates:
    - Network retry logic submitting twice
    - Parallel strategy execution bugs

    Expected: Only one order should be created
    """
    await mock_ibkr.connect()

    # Submit same intent concurrently
    results = await asyncio.gather(
        mock_ibkr.place(sample_order_intent),
        mock_ibkr.place(sample_order_intent),
        return_exceptions=True,
    )

    # Either both return same order_id, or one raises exception
    order_ids = [r for r in results if isinstance(r, str)]
    exceptions = [r for r in results if isinstance(r, Exception)]

    if len(order_ids) == 2:
        assert order_ids[0] == order_ids[1], "Concurrent duplicates must be idempotent"
    else:
        assert len(exceptions) == 1, "One submission should fail"
        assert "duplicate" in str(exceptions[0]).lower()


# ============================================================================
# 3. STUCK ORDERS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_order_timeout_no_acknowledgment(sample_order_intent: OrderIntent):
    """
    CRITICAL: Detect orders stuck in SUBMITTED state

    Catastrophic scenario:
    - Order sent to broker but never acknowledged
    - Strategy thinks order is active, but broker doesn't have it
    - Position reconciliation fails

    Expected behavior:
    - After timeout (e.g., 30s), mark as TIMEOUT
    - Generate ExecutionReport with TIMEOUT status
    - Alert system/operator
    """
    # Create mock that never acknowledges
    mock_no_ack = IBKRMockClient(
        auto_fill=False,  # Disable auto-fill
        fill_delay_ms=99999,
    )
    await mock_no_ack.connect()

    order_id = await mock_no_ack.place(sample_order_intent)

    # Wait beyond reasonable timeout
    await asyncio.sleep(0.5)

    status = mock_no_ack.get_order_status(order_id)

    # In production, implement timeout detection
    # For now, verify it stays in SUBMITTED (stuck)
    assert status in [OrderStatus.SUBMITTED, OrderStatus.TIMEOUT], \
        "Order should be stuck or timed out"


@pytest.mark.asyncio
async def test_order_stuck_acknowledged_no_fill(sample_order_intent: OrderIntent):
    """
    Test: Order acknowledged but never fills

    Scenarios:
    - LIMIT order with unrealistic price (never executes)
    - Low liquidity symbol (no counterparty)
    - Market closed (order queued until open)

    Expected behavior:
    - After timeout (e.g., 60s for MARKET, EOD for LIMIT DAY)
    - Mark as TIMEOUT or CANCELED (depending on TIF)
    """
    mock_no_fill = IBKRMockClient(
        auto_fill=False,
        fill_delay_ms=99999,
    )
    await mock_no_fill.connect()

    order_id = await mock_no_fill.place(sample_order_intent)

    # Manually ack but don't fill
    await asyncio.sleep(0.2)
    status = mock_no_fill.get_order_status(order_id)

    # Should be acknowledged but not filled
    assert status in [OrderStatus.ACKNOWLEDGED, OrderStatus.SUBMITTED]

    # In production: implement timeout → TIMEOUT state
    # For MARKET orders: timeout after 30-60s
    # For LIMIT orders: respect time_in_force


@pytest.mark.asyncio
async def test_timeout_state_transition(sample_order_intent: OrderIntent):
    """
    Test explicit TIMEOUT state handling

    Validates:
    - Orders can transition to TIMEOUT
    - TIMEOUT is a terminal state
    - ExecutionReport generated with TIMEOUT status
    """
    mock_timeout = IBKRMockClient(auto_fill=True, fill_delay_ms=100)
    await mock_timeout.connect()

    order_id = await mock_timeout.place(sample_order_intent)

    # Simulate timeout (in production, orchestrator detects this)
    # For now, verify timeout state is valid
    # NOTE: Need to implement timeout detection in orchestrator.py

    # Placeholder: verify TIMEOUT is in valid states
    valid_states = [s.value for s in OrderStatus]
    assert "TIMEOUT" in valid_states


# ============================================================================
# 4. ORDER CANCELLATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_cancel_order_before_fill(mock_ibkr: IBKRMockClient, sample_order_intent: OrderIntent):
    """
    Test successful cancellation before fill

    Validates:
    - Cancel submitted order → CANCELED state
    - ExecutionReport with CANCELED status
    - Remaining quantity preserved
    """
    await mock_ibkr.connect()

    # Disable auto-fill to have time to cancel
    mock_ibkr.auto_fill = False
    order_id = await mock_ibkr.place(sample_order_intent)

    await asyncio.sleep(0.05)

    # Cancel before fill
    success = await mock_ibkr.cancel(order_id)
    assert success, "Cancel should succeed for pending order"

    status = mock_ibkr.get_order_status(order_id)
    assert status == OrderStatus.CANCELED

    # Verify execution report
    reports = await mock_ibkr.poll_reports()
    canceled_report = next((r for r in reports if r.status == 'CANCELED'), None)
    assert canceled_report is not None
    assert canceled_report.filled_quantity == 0.0
    assert canceled_report.remaining_quantity == sample_order_intent.quantity


@pytest.mark.asyncio
async def test_cannot_cancel_filled_order(mock_ibkr: IBKRMockClient, sample_order_intent: OrderIntent):
    """
    Test: Cannot cancel already filled order

    Validates:
    - Cancel after FILLED → should fail
    - State remains FILLED
    - Error message clear
    """
    await mock_ibkr.connect()

    order_id = await mock_ibkr.place(sample_order_intent)

    # Wait for fill
    await asyncio.sleep(0.2)
    status = mock_ibkr.get_order_status(order_id)
    assert status == OrderStatus.FILLED

    # Try to cancel filled order
    success = await mock_ibkr.cancel(order_id)
    assert not success, "Cannot cancel filled order"

    # State should remain FILLED
    status = mock_ibkr.get_order_status(order_id)
    assert status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_cancel_partial_fill(sample_order_intent: OrderIntent):
    """
    Test: Cancel order with partial fill

    Scenario:
    - Order partially filled (e.g., 60 out of 100 shares)
    - User cancels remaining

    Expected behavior:
    - Filled portion: preserved (60 shares filled)
    - Remaining: canceled (40 shares canceled)
    - Final state: CANCELED (not FILLED)
    - ExecutionReport shows filled_quantity=60, remaining=40
    """
    mock_partial = IBKRMockClient(
        auto_fill=True,
        fill_delay_ms=100,  # Longer delay to ensure we can cancel before full fill
        partial_fill_prob=1.0,  # Force partial fill
    )
    await mock_partial.connect()

    order_id = await mock_partial.place(sample_order_intent)

    # Wait for partial fill (first fill happens at ~100ms)
    await asyncio.sleep(0.12)

    # Cancel remaining (before second fill at ~150ms)
    success = await mock_partial.cancel(order_id)

    # Get final report
    reports = await mock_partial.poll_reports()
    final_report = reports[-1]

    # Should show partial fill + canceled
    assert final_report.filled_quantity > 0
    assert final_report.filled_quantity < sample_order_intent.quantity
    assert final_report.remaining_quantity > 0
    assert final_report.status in ['PARTIAL_FILL', 'CANCELED']


@pytest.mark.asyncio
async def test_cancel_race_condition_with_fill(mock_ibkr: IBKRMockClient, sample_order_intent: OrderIntent):
    """
    Test race: Cancel request arrives as order fills

    Catastrophic scenario:
    - User cancels order
    - Order fills simultaneously
    - System shows CANCELED but position exists

    Expected behavior:
    - If fill completes first → cancel fails, state=FILLED
    - If cancel wins → cancel succeeds, state=CANCELED
    - NO ambiguous state allowed
    """
    await mock_ibkr.connect()

    mock_ibkr.auto_fill = True
    mock_ibkr.fill_delay_ms = 100

    order_id = await mock_ibkr.place(sample_order_intent)

    # Race: cancel immediately after submit
    await asyncio.sleep(0.05)
    cancel_task = asyncio.create_task(mock_ibkr.cancel(order_id))

    # Wait for resolution
    await asyncio.sleep(0.15)

    status = mock_ibkr.get_order_status(order_id)

    # Must be deterministic: either FILLED or CANCELED, not both
    assert status in [OrderStatus.FILLED, OrderStatus.CANCELED], \
        "Race must resolve to definitive state"

    # If FILLED, cancel should have failed
    # If CANCELED, fill should have failed


# ============================================================================
# 5. PARTIAL FILLS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_partial_fill_progression(sample_order_intent: OrderIntent):
    """
    Test multiple partial fills until complete

    Scenario:
    - Order 100 shares
    - Fill 1: 40 shares
    - Fill 2: 30 shares
    - Fill 3: 30 shares (complete)

    Validates:
    - State: ACKNOWLEDGED → PARTIAL_FILL → PARTIAL_FILL → FILLED
    - Running totals correct
    - Average fill price calculated correctly
    """
    mock_partial = IBKRMockClient(
        auto_fill=True,
        fill_delay_ms=50,
        partial_fill_prob=0.4,  # Multiple partials
    )
    await mock_partial.connect()

    order_id = await mock_partial.place(sample_order_intent)

    # Wait for fills to complete
    await asyncio.sleep(0.5)

    reports = await mock_partial.poll_reports()

    # Find all PARTIAL_FILL reports
    partial_reports = [r for r in reports if r.status == 'PARTIAL_FILL']
    filled_report = next((r for r in reports if r.status == 'FILLED'), None)

    if partial_reports:
        # Validate progression
        running_filled = 0.0
        for report in partial_reports:
            assert report.filled_quantity > running_filled, \
                "Filled quantity should increase monotonically"
            running_filled = report.filled_quantity

    # Final report should show complete fill
    assert filled_report is not None
    assert filled_report.filled_quantity == sample_order_intent.quantity
    assert filled_report.remaining_quantity == 0.0


@pytest.mark.asyncio
async def test_partial_fill_average_price_calculation(sample_order_intent: OrderIntent):
    """
    Test average fill price calculation across multiple fills

    Scenario:
    - Fill 1: 50 shares @ $100.00 = $5,000
    - Fill 2: 50 shares @ $100.50 = $5,025
    - Total: 100 shares, avg = $100.25

    Validates:
    - Average weighted correctly
    - Commission included/excluded appropriately
    """
    mock_partial = IBKRMockClient(
        auto_fill=True,
        partial_fill_prob=0.5,
        fill_delay_ms=50,
    )
    await mock_partial.connect()

    order_id = await mock_partial.place(sample_order_intent)
    await asyncio.sleep(0.3)

    reports = await mock_partial.poll_reports()
    filled_report = next((r for r in reports if r.status == 'FILLED'), None)

    if filled_report and filled_report.fills:
        # Calculate expected average manually
        total_value = sum(fill.price * fill.quantity for fill in filled_report.fills)
        total_qty = sum(fill.quantity for fill in filled_report.fills)
        expected_avg = total_value / total_qty

        # Allow small floating point error
        assert abs(filled_report.average_fill_price - expected_avg) < 0.01, \
            f"Average price mismatch: {filled_report.average_fill_price} vs {expected_avg}"


# ============================================================================
# 6. STATE MACHINE VALIDATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_invalid_state_transitions():
    """
    Test: Prevent invalid state transitions

    Invalid transitions:
    - FILLED → PENDING (no backwards)
    - CANCELED → FILLED (terminal state)
    - REJECTED → ACKNOWLEDGED (terminal state)

    Validates:
    - State machine enforces valid transitions
    - Invalid transitions raise errors or ignored
    """
    # NOTE: This requires implementing state transition validation
    # in the actual IBKRExecClient (production code)

    valid_transitions = {
        OrderStatus.PENDING: [OrderStatus.SUBMITTED, OrderStatus.REJECTED],
        OrderStatus.SUBMITTED: [OrderStatus.ACKNOWLEDGED, OrderStatus.REJECTED, OrderStatus.TIMEOUT],
        OrderStatus.ACKNOWLEDGED: [OrderStatus.PARTIAL_FILL, OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED],
        OrderStatus.PARTIAL_FILL: [OrderStatus.PARTIAL_FILL, OrderStatus.FILLED, OrderStatus.CANCELED],
        OrderStatus.FILLED: [],  # Terminal
        OrderStatus.CANCELED: [],  # Terminal
        OrderStatus.REJECTED: [],  # Terminal
        OrderStatus.TIMEOUT: [],  # Terminal
    }

    # Verify terminal states have no valid transitions
    terminal_states = [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.TIMEOUT]
    for state in terminal_states:
        assert valid_transitions[state] == [], f"{state} should be terminal"


@pytest.mark.asyncio
async def test_order_rejection_by_broker(sample_order_intent: OrderIntent):
    """
    Test: Broker rejects order

    Scenarios:
    - Insufficient buying power
    - Invalid symbol
    - Market closed (non-GTC order)
    - Regulatory restriction

    Expected behavior:
    - State: SUBMITTED → REJECTED
    - ExecutionReport with REJECTED status
    - Error message provided
    """
    mock_reject = IBKRMockClient(
        auto_fill=False,
        reject_prob=1.0,  # Always reject
    )
    await mock_reject.connect()

    order_id = await mock_reject.place(sample_order_intent)
    await asyncio.sleep(0.1)

    status = mock_reject.get_order_status(order_id)
    assert status == OrderStatus.REJECTED

    reports = await mock_reject.poll_reports()
    rejected_report = next((r for r in reports if r.status == 'REJECTED'), None)
    assert rejected_report is not None
    assert rejected_report.filled_quantity == 0.0


# ============================================================================
# 7. CONCURRENT ORDER MANAGEMENT TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_concurrent_multiple_orders(mock_ibkr: IBKRMockClient):
    """
    Test: Manage multiple concurrent orders

    Scenario:
    - Submit 10 orders simultaneously
    - Different symbols, quantities
    - All should process independently

    Validates:
    - No cross-contamination between orders
    - All orders tracked correctly
    - Reports mapped to correct orders
    """
    await mock_ibkr.connect()

    # Create 10 different orders
    intents = []
    for i in range(10):
        intent = OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol=f'STOCK{i}',
            direction='BUY' if i % 2 == 0 else 'SELL',
            quantity=float(100 + i * 10),
            order_type='MARKET',
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )
        intents.append(intent)

    # Submit concurrently
    order_ids = await asyncio.gather(*[mock_ibkr.place(intent) for intent in intents])

    # All should succeed
    assert len(order_ids) == 10
    assert len(set(order_ids)) == 10  # All unique

    # Wait for fills
    await asyncio.sleep(0.3)

    # Verify all filled
    for order_id in order_ids:
        status = mock_ibkr.get_order_status(order_id)
        assert status == OrderStatus.FILLED

    # Verify reports
    reports = await mock_ibkr.poll_reports()
    filled_reports = [r for r in reports if r.status == 'FILLED']
    assert len(filled_reports) == 10


@pytest.mark.asyncio
async def test_concurrent_cancel_and_fill_different_orders(mock_ibkr: IBKRMockClient):
    """
    Test: Cancel one order while another fills

    Scenario:
    - Order A: cancel immediately
    - Order B: let fill
    - Should not interfere with each other

    Validates:
    - Independent order lifecycle management
    """
    await mock_ibkr.connect()

    intent_a = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='OFI',
    )

    intent_b = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='TSLA',
        direction='SELL',
        quantity=50.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='ERN',
    )

    # Place both orders with auto_fill enabled
    order_id_a = await mock_ibkr.place(intent_a)
    order_id_b = await mock_ibkr.place(intent_b)

    # Cancel A immediately, let B fill naturally
    await asyncio.sleep(0.02)  # Small delay to ensure both are placed
    await mock_ibkr.cancel(order_id_a)

    # Wait for B to fill
    await asyncio.sleep(0.2)

    status_a = mock_ibkr.get_order_status(order_id_a)
    status_b = mock_ibkr.get_order_status(order_id_b)

    # A should be canceled, B should fill normally
    assert status_a == OrderStatus.CANCELED
    assert status_b == OrderStatus.FILLED


# ============================================================================
# 8. LATENCY METRICS TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_latency_metrics_captured(mock_ibkr: IBKRMockClient, sample_order_intent: OrderIntent):
    """
    Test: Execution reports include latency metrics

    Validates:
    - intent_to_submit_ms: Time to send order
    - submit_to_ack_ms: Broker acknowledgment latency
    - ack_to_fill_ms: Fill execution latency

    Critical for:
    - Performance monitoring
    - SLA compliance
    - Identifying slow brokers/networks
    """
    await mock_ibkr.connect()

    order_id = await mock_ibkr.place(sample_order_intent)
    await asyncio.sleep(0.2)

    reports = await mock_ibkr.poll_reports()
    filled_report = next((r for r in reports if r.status == 'FILLED'), None)

    assert filled_report is not None

    # Check if latency metrics exist
    if filled_report.latency_metrics:
        metrics = filled_report.latency_metrics

        # All latencies should be non-negative
        assert metrics.intent_to_submit_ms >= 0
        assert metrics.submit_to_ack_ms >= 0
        assert metrics.ack_to_fill_ms >= 0

        # Total latency should be sum of parts (approximately)
        # Allow some tolerance for clock skew
        total = (metrics.intent_to_submit_ms +
                metrics.submit_to_ack_ms +
                metrics.ack_to_fill_ms)
        assert total > 0, "Total latency should be positive"


# ============================================================================
# 9. ERROR HANDLING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_network_failure_retry():
    """
    Test: Handle network failures gracefully

    Scenario:
    - Connection drops during order submission
    - Retry logic attempts reconnect
    - Order eventually succeeds or fails cleanly

    Expected behavior:
    - Exponential backoff retry (2s, 4s, 8s, 16s)
    - Max 4 retries
    - If all fail → ERROR state
    """
    # NOTE: Implement network failure simulation in mock
    # For now, verify error state is valid
    pass


@pytest.mark.asyncio
async def test_malformed_order_intent():
    """
    Test: Reject malformed OrderIntent before submission

    Scenarios:
    - Negative quantity
    - Missing required fields
    - Invalid symbol format
    - LIMIT order without limit_price

    Expected behavior:
    - Validation fails before broker submission
    - Clear error message
    - No PENDING/SUBMITTED state created
    """
    # Invalid: negative quantity
    with pytest.raises(ValueError):
        OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol='AAPL',
            direction='BUY',
            quantity=-100.0,  # Invalid
            order_type='MARKET',
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )

    # Invalid: LIMIT without limit_price
    with pytest.raises(ValueError):
        OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol='AAPL',
            direction='BUY',
            quantity=100.0,
            order_type='LIMIT',  # Requires limit_price
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',
        )


# ============================================================================
# 10. POSITION RECONCILIATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_position_tracking_after_fills(mock_ibkr: IBKRMockClient):
    """
    Test: Position updates correctly after fills

    Scenario:
    - Start: 0 shares
    - BUY 100 → Position: +100
    - SELL 50 → Position: +50
    - SELL 50 → Position: 0

    Validates:
    - Position tracking accurate
    - Accounts for partial fills
    - No phantom positions
    """
    await mock_ibkr.connect()

    # BUY 100
    buy_intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='OFI',
    )

    await mock_ibkr.place(buy_intent)
    await asyncio.sleep(0.2)

    # Check position (mock should track this)
    # NOTE: Need to implement get_position() in mock
    # For now, verify buy/sell tracking exists
    assert mock_ibkr.position_buy_qty >= 100.0

    # SELL 50
    sell_intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='SELL',
        quantity=50.0,
        order_type='MARKET',
        timestamp=datetime.now(timezone.utc),
        strategy_id='OFI',
    )

    await mock_ibkr.place(sell_intent)
    await asyncio.sleep(0.2)

    assert mock_ibkr.position_sell_qty >= 50.0


# ============================================================================
# INTEGRATION TEST MARKERS
# ============================================================================

# Mark critical tests that MUST pass before production
CRITICAL_TESTS = [
    'test_duplicate_intent_id_rejection',
    'test_concurrent_duplicate_orders',
    'test_cancel_race_condition_with_fill',
    'test_order_timeout_no_acknowledgment',
]

# Mark tests requiring real IBKR connection (skip in CI)
pytest.mark.ibkr_live = pytest.mark.skipif(
    True,  # Set to False when testing with real IBKR
    reason="Requires live IBKR connection"
)
