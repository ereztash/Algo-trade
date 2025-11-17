"""
IBKR Resilience Tests

Tests IBKR connection resilience:
- Connection failures and recovery
- Order placement under failures
- Timeout handling
- Rate limit violations
- Partial fills during disconnects

Recovery Target: ≤30 seconds
"""

import pytest
import time
from tests.chaos.utils import (
    RecoveryTimer,
    StateValidator,
    chaos_scenario,
    FaultType,
    exponential_backoff,
)


@pytest.mark.chaos
@pytest.mark.slow
class TestIBKRConnectionResilience:
    """Test IBKR connection failure and recovery"""

    def test_ibkr_disconnect_immediate_recovery(
        self,
        chaos_ibkr_client,
        chaos_config,
    ):
        """
        Test immediate reconnection after disconnect.

        Scenario:
        1. Establish connection
        2. Disconnect
        3. Immediate reconnect attempt
        4. Verify recovery within RTO
        """
        with chaos_scenario("IBKR Immediate Disconnect", FaultType.NETWORK_DISCONNECT):
            # Establish connection
            assert chaos_ibkr_client.connect()

            timer = RecoveryTimer()
            with timer:
                # Inject disconnect
                chaos_ibkr_client.inject_disconnect()
                assert not chaos_ibkr_client.is_connected()
                timer.mark_detected()

                # Attempt recovery
                timer.mark_recovery_started()
                success = chaos_ibkr_client.connect()
                assert success, "Failed to reconnect"
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto
            # Immediate recovery should be very fast
            assert timer.metrics.recovery_time_s < 5.0, "Immediate recovery too slow"

    def test_ibkr_reconnect_with_exponential_backoff(
        self,
        chaos_ibkr_client,
        chaos_config,
    ):
        """
        Test reconnection with exponential backoff strategy.

        Scenario:
        1. Disconnect
        2. Attempt reconnect with backoff (1s, 2s, 4s, 8s, 16s)
        3. Verify recovery within RTO
        """
        with chaos_scenario("IBKR Exponential Backoff", FaultType.NETWORK_DISCONNECT):
            assert chaos_ibkr_client.connect()

            timer = RecoveryTimer()
            with timer:
                chaos_ibkr_client.inject_disconnect()
                timer.mark_detected()

                timer.mark_recovery_started()

                # Exponential backoff retry
                max_attempts = 5
                for attempt in range(max_attempts):
                    if chaos_ibkr_client.connect():
                        break

                    delay = exponential_backoff(
                        attempt,
                        base_delay_s=1.0,
                        max_delay_s=30.0,
                    )
                    print(f"  Retry {attempt + 1}/{max_attempts} after {delay:.1f}s")
                    time.sleep(delay)

                assert chaos_ibkr_client.is_connected(), "Reconnection failed"
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_connection_timeout_handling(
        self,
        chaos_ibkr_client,
        network_fault_injector,
        chaos_config,
    ):
        """
        Test handling of connection timeouts.

        Scenario:
        1. Inject high latency (simulating timeout)
        2. Attempt connection
        3. Verify timeout detection
        4. Retry with backoff
        5. Verify recovery
        """
        with chaos_scenario("Connection Timeout", FaultType.CONNECTION_TIMEOUT):
            timer = RecoveryTimer()
            with timer:
                # Inject 6s latency (exceeding typical 5s timeout)
                with network_fault_injector.inject_latency(6000):
                    chaos_ibkr_client.network_injector = network_fault_injector

                    # First attempt should timeout
                    start = time.time()
                    success = chaos_ibkr_client.connect()
                    elapsed = time.time() - start

                    print(f"  First attempt: {elapsed:.1f}s, success={success}")

                    if not success:
                        timer.mark_detected()

                # Latency removed, retry should succeed
                timer.mark_recovery_started()
                chaos_ibkr_client.network_injector = network_fault_injector.__class__()

                for attempt in range(3):
                    if chaos_ibkr_client.connect():
                        break
                    time.sleep(1)

                assert chaos_ibkr_client.is_connected()
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_rate_limit_violations_and_recovery(
        self,
        chaos_ibkr_client,
        chaos_config,
    ):
        """
        Test handling of rate limit violations.

        Scenario:
        1. Send requests to trigger rate limit
        2. Detect rate limit
        3. Back off and retry
        4. Verify recovery
        """
        with chaos_scenario("Rate Limit Violation", FaultType.RATE_LIMIT):
            assert chaos_ibkr_client.connect()

            # Set aggressive rate limit for testing
            chaos_ibkr_client.rate_limit_threshold = 10

            timer = RecoveryTimer()
            with timer:
                # Send requests to trigger rate limit
                for i in range(15):
                    order = {
                        'order_id': f'TEST{i:03d}',
                        'symbol': 'AAPL',
                        'qty': 100,
                    }
                    result = chaos_ibkr_client.place_order(order)

                    if result is None and i > chaos_ibkr_client.rate_limit_threshold:
                        # Rate limit hit
                        timer.mark_detected()
                        print(f"  Rate limit hit at request {i}")
                        break

                # Back off and reset
                timer.mark_recovery_started()
                print("  Backing off for 2s...")
                time.sleep(2)

                # Reset rate limit
                chaos_ibkr_client.reset_rate_limit()

                # Verify recovery
                test_order = {
                    'order_id': 'RECOVERY_TEST',
                    'symbol': 'AAPL',
                    'qty': 100,
                }
                result = chaos_ibkr_client.place_order(test_order)
                assert result is not None, "Recovery failed after rate limit"
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto


@pytest.mark.chaos
@pytest.mark.slow
class TestIBKROrderResilience:
    """Test order placement resilience"""

    def test_order_placement_during_disconnect(
        self,
        chaos_ibkr_client,
        state_validator,
    ):
        """
        Test order placement when disconnected.

        Scenario:
        1. Disconnect
        2. Attempt to place order (should fail gracefully)
        3. Reconnect
        4. Retry order placement
        5. Verify order integrity
        """
        with chaos_scenario("Order During Disconnect", FaultType.NETWORK_DISCONNECT):
            assert chaos_ibkr_client.connect()

            # Disconnect
            chaos_ibkr_client.inject_disconnect()

            # Attempt to place order while disconnected
            order = {
                'order_id': 'TEST001',
                'symbol': 'AAPL',
                'qty': 100,
            }

            result = chaos_ibkr_client.place_order(order)
            assert result is None, "Order should fail when disconnected"

            # Check that failure was tracked
            assert len(chaos_ibkr_client.failed_requests) > 0
            assert chaos_ibkr_client.failed_requests[-1]['reason'] == 'not_connected'

            # Reconnect and retry
            assert chaos_ibkr_client.connect()

            result = chaos_ibkr_client.place_order(order)
            assert result is not None, "Order should succeed after reconnect"

            # Verify order integrity
            assert state_validator.validate_order_integrity(
                sent_orders=[order],
                received_orders=chaos_ibkr_client.acknowledged_orders,
            )

    def test_order_acknowledgment_timeout(
        self,
        chaos_ibkr_client,
        chaos_config,
    ):
        """
        Test handling of order acknowledgment timeouts.

        Scenario:
        1. Place order
        2. Inject timeout on acknowledgment
        3. Verify timeout handling
        4. Retry and verify success
        """
        with chaos_scenario("Order Ack Timeout", FaultType.CONNECTION_TIMEOUT):
            assert chaos_ibkr_client.connect()

            timer = RecoveryTimer()
            with timer:
                # Inject timeout on next request
                chaos_ibkr_client.inject_timeout_on_next_request()

                order = {
                    'order_id': 'TEST001',
                    'symbol': 'AAPL',
                    'qty': 100,
                }

                # First attempt should timeout
                result = chaos_ibkr_client.place_order(order)
                assert result is None, "Order should timeout"
                timer.mark_detected()

                # Retry without timeout
                timer.mark_recovery_started()
                result = chaos_ibkr_client.place_order(order)
                assert result is not None, "Retry should succeed"
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_partial_fills_during_disconnect(
        self,
        chaos_ibkr_client,
        state_validator,
    ):
        """
        Test handling of partial fills when disconnect occurs.

        Scenario:
        1. Place large order
        2. Receive partial fill
        3. Disconnect
        4. Reconnect
        5. Verify position and remaining order
        """
        with chaos_scenario("Partial Fill Disconnect", FaultType.NETWORK_DISCONNECT):
            assert chaos_ibkr_client.connect()

            # Place order
            order = {
                'order_id': 'TEST001',
                'symbol': 'AAPL',
                'qty': 1000,  # Large order
                'filled_qty': 0,
            }

            result = chaos_ibkr_client.place_order(order)
            assert result is not None

            # Simulate partial fill (50% filled)
            order['filled_qty'] = 500

            # Disconnect
            chaos_ibkr_client.inject_disconnect()

            # Reconnect
            timer = RecoveryTimer()
            with timer:
                timer.mark_detected()
                timer.mark_recovery_started()

                for attempt in range(3):
                    if chaos_ibkr_client.connect():
                        break
                    time.sleep(1)

                assert chaos_ibkr_client.is_connected()
                timer.mark_recovery_completed()

            # After reconnect, should be able to query order status
            # and continue with remaining quantity (500 shares)

            # For now, verify we recovered
            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

            # In production, would verify:
            # - Position shows 500 shares filled
            # - Remaining 500 shares still working or ready to submit

    def test_order_during_slow_response(
        self,
        chaos_ibkr_client,
    ):
        """
        Test order placement during slow broker response.

        Scenario:
        1. Inject slow response (2s delay)
        2. Place order
        3. Verify order succeeds despite delay
        4. Verify response time is tracked
        """
        with chaos_scenario("Slow Order Response", FaultType.SLOW_RESPONSE):
            assert chaos_ibkr_client.connect()

            # Inject 2s delay on responses
            chaos_ibkr_client.inject_slow_response(2000)

            order = {
                'order_id': 'TEST001',
                'symbol': 'AAPL',
                'qty': 100,
            }

            start = time.time()
            result = chaos_ibkr_client.place_order(order)
            elapsed = time.time() - start

            print(f"  Order response time: {elapsed:.2f}s")

            # Should succeed despite slow response
            assert result is not None, "Order should succeed despite slow response"
            assert elapsed >= 2.0, "Slow response delay not applied"

            # Reset for next test
            chaos_ibkr_client.inject_slow_response(0)


@pytest.mark.chaos
@pytest.mark.slow
class TestIBKRStreamingResilience:
    """Test market data streaming resilience"""

    def test_streaming_during_disconnect(
        self,
        chaos_ibkr_client,
        state_validator,
    ):
        """
        Test market data streaming through disconnect/reconnect.

        Scenario:
        1. Start streaming
        2. Disconnect mid-stream
        3. Reconnect
        4. Resume streaming
        5. Validate data completeness
        """
        with chaos_scenario("Streaming Disconnect", FaultType.NETWORK_DISCONNECT):
            assert chaos_ibkr_client.connect()

            # Stream data before disconnect
            pre_disconnect_ticks = []
            for i in range(10):
                tick = chaos_ibkr_client.stream_market_data('AAPL')
                if tick:
                    pre_disconnect_ticks.append(tick)
                time.sleep(0.01)

            # Disconnect
            timer = RecoveryTimer()
            with timer:
                chaos_ibkr_client.inject_disconnect()
                timer.mark_detected()

                # Reconnect
                timer.mark_recovery_started()
                for attempt in range(3):
                    if chaos_ibkr_client.connect():
                        break
                    time.sleep(1)

                assert chaos_ibkr_client.is_connected()
                timer.mark_recovery_completed()

            # Resume streaming
            post_reconnect_ticks = []
            for i in range(10):
                tick = chaos_ibkr_client.stream_market_data('AAPL')
                if tick:
                    post_reconnect_ticks.append(tick)
                time.sleep(0.01)

            print(f"\n{timer.metrics}")
            print(f"Pre-disconnect: {len(pre_disconnect_ticks)} ticks")
            print(f"Post-reconnect: {len(post_reconnect_ticks)} ticks")

            assert timer.metrics.meets_rto
            assert len(post_reconnect_ticks) > 0, "No data after reconnect"

    def test_streaming_with_intermittent_failures(
        self,
        chaos_ibkr_client,
        state_validator,
    ):
        """
        Test streaming with intermittent connection failures.

        Scenario:
        1. Start streaming
        2. Inject multiple brief disconnects
        3. Verify continuous recovery
        4. Validate overall data quality
        """
        with chaos_scenario("Intermittent Failures", FaultType.NETWORK_DISCONNECT):
            assert chaos_ibkr_client.connect()

            total_ticks = []
            total_expected = 100
            disconnect_points = [25, 50, 75]  # Disconnect at these points

            for i in range(total_expected):
                # Inject brief disconnect at certain points
                if i in disconnect_points:
                    chaos_ibkr_client.inject_disconnect()
                    print(f"  Injected disconnect at tick {i}")

                    # Quick reconnect
                    for attempt in range(3):
                        if chaos_ibkr_client.connect():
                            print(f"  Reconnected after {attempt + 1} attempts")
                            break
                        time.sleep(0.1)

                # Stream data
                tick = chaos_ibkr_client.stream_market_data('AAPL')
                if tick:
                    total_ticks.append(tick)

                time.sleep(0.01)

            # Validate data completeness with tolerance for disconnects
            is_complete = state_validator.validate_data_completeness(
                expected_count=total_expected,
                actual_count=len(total_ticks),
                tolerance=0.10,  # 10% tolerance for brief disconnects
            )

            print(f"\nReceived {len(total_ticks)}/{total_expected} ticks")
            assert is_complete, f"Data loss exceeds tolerance: {state_validator.get_violations()}"


@pytest.mark.chaos
def test_ibkr_connection_metrics(
    chaos_ibkr_client,
):
    """
    Collect comprehensive IBKR connection metrics.

    Tracks:
    - Connection success rate
    - Reconnection attempts
    - Order success rate
    - Failed requests by type
    """
    with chaos_scenario("IBKR Metrics Collection", FaultType.COMPONENT_CRASH):
        scenarios = [
            ('normal', lambda: None),
            ('disconnect', lambda: chaos_ibkr_client.inject_disconnect()),
            ('timeout', lambda: chaos_ibkr_client.inject_timeout_on_next_request()),
            ('slow', lambda: chaos_ibkr_client.inject_slow_response(1000)),
        ]

        results = {}

        for name, fault_injector in scenarios:
            chaos_ibkr_client.reset_chaos()
            chaos_ibkr_client.connect()

            # Inject fault
            fault_injector()

            # Try operations
            order_success = 0
            for i in range(5):
                order = {
                    'order_id': f'{name}_{i}',
                    'symbol': 'AAPL',
                    'qty': 100,
                }

                # May need reconnect
                if not chaos_ibkr_client.is_connected():
                    chaos_ibkr_client.connect()

                result = chaos_ibkr_client.place_order(order)
                if result:
                    order_success += 1

            results[name] = {
                'success_rate': order_success / 5,
                'connection_attempts': chaos_ibkr_client.connection_attempts,
                'failed_requests': len(chaos_ibkr_client.failed_requests),
            }

        print("\nIBKR Resilience Metrics:")
        for name, metrics in results.items():
            print(f"\n{name}:")
            print(f"  Success Rate: {metrics['success_rate']:.0%}")
            print(f"  Connection Attempts: {metrics['connection_attempts']}")
            print(f"  Failed Requests: {metrics['failed_requests']}")

        # Validate baseline
        assert results['normal']['success_rate'] >= 0.95
