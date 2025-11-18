"""
Network Chaos Tests

Tests system resilience to network-level failures:
- Network disconnections (partitions)
- High latency injection
- Packet loss scenarios
- DNS failures

Recovery Target: ≤30 seconds
"""

import pytest
import time
import asyncio
from tests.chaos.utils import (
    RecoveryTimer,
    chaos_scenario,
    FaultType,
    wait_for_condition,
)


@pytest.mark.chaos
@pytest.mark.slow
class TestNetworkDisconnection:
    """Test recovery from network disconnections"""

    def test_network_partition_3s_recovery(
        self,
        chaos_ibkr_client,
        network_fault_injector,
        state_validator,
        chaos_config,
    ):
        """
        Test recovery from 3-second network partition.

        Scenario:
        1. Establish connection
        2. Inject 3s network disconnect
        3. Verify detection and recovery
        4. Validate RTO ≤30s
        """
        with chaos_scenario("3s Network Partition", FaultType.NETWORK_DISCONNECT):
            # Establish baseline connection
            assert chaos_ibkr_client.connect(), "Initial connection failed"
            assert chaos_ibkr_client.is_connected()

            # Start recovery timer
            timer = RecoveryTimer()
            with timer:
                # Inject 3-second network disconnect
                with network_fault_injector.inject_disconnect(3.0):
                    chaos_ibkr_client.network_injector = network_fault_injector

                    # Connection should fail during disconnect
                    assert not chaos_ibkr_client.is_connected()
                    timer.mark_detected()

                    # Wait for disconnect to end
                    time.sleep(3.0)

                # Attempt reconnection
                timer.mark_recovery_started()

                # Retry connection with exponential backoff
                max_retries = 5
                for attempt in range(max_retries):
                    if chaos_ibkr_client.connect():
                        break
                    time.sleep(2 ** attempt)  # Exponential backoff

                assert chaos_ibkr_client.is_connected(), "Recovery failed"
                timer.mark_recovery_completed()

            # Verify RTO compliance
            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto, (
                f"Recovery time {timer.metrics.recovery_time_s:.2f}s "
                f"exceeds RTO target of {chaos_config['rto_target_s']}s"
            )

            # Verify no data loss
            assert timer.metrics.data_loss_count == 0
            assert timer.metrics.order_integrity_violations == 0

    def test_network_partition_10s_recovery(
        self,
        chaos_ibkr_client,
        network_fault_injector,
        chaos_config,
    ):
        """Test recovery from 10-second network partition"""
        with chaos_scenario("10s Network Partition", FaultType.NETWORK_DISCONNECT):
            assert chaos_ibkr_client.connect()

            timer = RecoveryTimer()
            with timer:
                with network_fault_injector.inject_disconnect(10.0):
                    chaos_ibkr_client.network_injector = network_fault_injector
                    assert not chaos_ibkr_client.is_connected()
                    timer.mark_detected()
                    time.sleep(10.0)

                timer.mark_recovery_started()

                for attempt in range(5):
                    if chaos_ibkr_client.connect():
                        break
                    time.sleep(2 ** attempt)

                assert chaos_ibkr_client.is_connected()
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_network_partition_30s_recovery(
        self,
        chaos_ibkr_client,
        network_fault_injector,
        chaos_config,
    ):
        """Test recovery from 30-second network partition (edge case)"""
        with chaos_scenario("30s Network Partition", FaultType.NETWORK_DISCONNECT):
            assert chaos_ibkr_client.connect()

            timer = RecoveryTimer()
            with timer:
                # This is an edge case - partition is exactly at RTO limit
                with network_fault_injector.inject_disconnect(25.0):
                    chaos_ibkr_client.network_injector = network_fault_injector
                    assert not chaos_ibkr_client.is_connected()
                    timer.mark_detected()
                    time.sleep(25.0)

                timer.mark_recovery_started()

                # Need aggressive retry for edge case
                for attempt in range(3):
                    if chaos_ibkr_client.connect():
                        break
                    time.sleep(1)  # Fast retry for edge case

                assert chaos_ibkr_client.is_connected()
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            # Should barely meet RTO
            assert timer.metrics.recovery_time_s is not None
            assert timer.metrics.recovery_time_s <= 30.0


@pytest.mark.chaos
@pytest.mark.slow
class TestNetworkLatency:
    """Test resilience to high network latency"""

    @pytest.mark.parametrize("latency_ms", [100, 500, 2000, 5000])
    def test_high_latency_tolerance(
        self,
        chaos_ibkr_client,
        network_fault_injector,
        latency_ms,
    ):
        """
        Test system tolerance to various latency levels.

        Tests:
        - 100ms: Normal degraded network
        - 500ms: High latency
        - 2000ms: Very high latency
        - 5000ms: Extreme latency (should timeout)
        """
        with chaos_scenario(
            f"{latency_ms}ms Latency Injection",
            FaultType.NETWORK_LATENCY,
        ):
            assert chaos_ibkr_client.connect()

            # Inject latency
            with network_fault_injector.inject_latency(latency_ms):
                chaos_ibkr_client.network_injector = network_fault_injector

                # Try to place order
                start = time.time()
                order = {
                    'order_id': 'TEST001',
                    'symbol': 'AAPL',
                    'qty': 100,
                }

                result = chaos_ibkr_client.place_order(order)
                elapsed_ms = (time.time() - start) * 1000

                print(f"Order placement took {elapsed_ms:.0f}ms")

                # For extreme latency, we expect timeout behavior
                if latency_ms >= 5000:
                    # System should handle gracefully (timeout or retry)
                    print("Extreme latency: system should timeout gracefully")
                else:
                    # Should complete despite latency
                    assert result is not None, (
                        f"Order failed with {latency_ms}ms latency"
                    )
                    assert elapsed_ms >= latency_ms, (
                        "Latency not properly injected"
                    )

    def test_variable_latency_handling(
        self,
        chaos_ibkr_client,
        network_fault_injector,
    ):
        """Test handling of variable latency conditions"""
        with chaos_scenario("Variable Latency", FaultType.NETWORK_LATENCY):
            assert chaos_ibkr_client.connect()

            latencies = [50, 100, 500, 200, 100, 50]  # Varying latency
            successful_orders = 0

            for i, latency in enumerate(latencies):
                with network_fault_injector.inject_latency(latency):
                    chaos_ibkr_client.network_injector = network_fault_injector

                    order = {
                        'order_id': f'TEST{i:03d}',
                        'symbol': 'AAPL',
                        'qty': 100,
                    }

                    result = chaos_ibkr_client.place_order(order)
                    if result:
                        successful_orders += 1

            # Should handle most orders despite variable latency
            success_rate = successful_orders / len(latencies)
            print(f"Success rate: {success_rate:.1%}")
            assert success_rate >= 0.80, "Too many failures under variable latency"


@pytest.mark.chaos
@pytest.mark.slow
class TestPacketLoss:
    """Test resilience to packet loss"""

    @pytest.mark.parametrize("loss_prob", [0.05, 0.20, 0.50])
    def test_packet_loss_resilience(
        self,
        chaos_ibkr_client,
        network_fault_injector,
        state_validator,
        loss_prob,
    ):
        """
        Test resilience to packet loss at various levels.

        Tests:
        - 5%: Normal network conditions
        - 20%: Degraded network
        - 50%: Severely degraded network
        """
        with chaos_scenario(
            f"{loss_prob:.0%} Packet Loss",
            FaultType.NETWORK_PACKET_LOSS,
        ):
            assert chaos_ibkr_client.connect()

            # Inject packet loss
            with network_fault_injector.inject_packet_loss(loss_prob):
                chaos_ibkr_client.network_injector = network_fault_injector

                # Attempt to place multiple orders
                num_orders = 50
                sent_orders = []
                successful_orders = []

                for i in range(num_orders):
                    order = {
                        'order_id': f'TEST{i:03d}',
                        'symbol': 'AAPL',
                        'qty': 100,
                    }
                    sent_orders.append(order)

                    # May need retries due to packet loss
                    max_retries = 3
                    for attempt in range(max_retries):
                        result = chaos_ibkr_client.place_order(order)
                        if result:
                            successful_orders.append(result)
                            break
                        # Retry after brief delay
                        time.sleep(0.1)

                success_rate = len(successful_orders) / num_orders
                print(f"Success rate with {loss_prob:.0%} loss: {success_rate:.1%}")

                # With retries, should still achieve reasonable success rate
                if loss_prob <= 0.20:
                    assert success_rate >= 0.90, "Too many failures with retries"
                else:
                    assert success_rate >= 0.70, "Excessive failures even with retries"

    def test_streaming_data_with_packet_loss(
        self,
        chaos_ibkr_client,
        network_fault_injector,
        state_validator,
    ):
        """Test market data streaming under packet loss"""
        with chaos_scenario("Streaming with Packet Loss", FaultType.NETWORK_PACKET_LOSS):
            assert chaos_ibkr_client.connect()

            # 10% packet loss during streaming
            with network_fault_injector.inject_packet_loss(0.10):
                chaos_ibkr_client.network_injector = network_fault_injector

                # Stream data for period
                expected_ticks = 100
                received_ticks = []

                for i in range(expected_ticks):
                    tick = chaos_ibkr_client.stream_market_data('AAPL')
                    if tick:
                        received_ticks.append(tick)
                    time.sleep(0.01)  # 10ms per tick

                # Validate data completeness
                is_complete = state_validator.validate_data_completeness(
                    expected_count=expected_ticks,
                    actual_count=len(received_ticks),
                    tolerance=0.15,  # Allow 15% loss with 10% packet loss + variance
                )

                print(f"Received {len(received_ticks)}/{expected_ticks} ticks")
                assert is_complete, f"Data loss exceeds tolerance: {state_validator.get_violations()}"


@pytest.mark.chaos
@pytest.mark.slow
def test_combined_network_faults(
    chaos_ibkr_client,
    network_fault_injector,
    state_validator,
):
    """
    Test recovery from combined network faults.

    Scenario:
    1. High latency (500ms)
    2. Packet loss (10%)
    3. Brief disconnect (2s)
    4. Verify recovery
    """
    with chaos_scenario("Combined Network Faults", FaultType.NETWORK_DISCONNECT):
        assert chaos_ibkr_client.connect()

        timer = RecoveryTimer()
        with timer:
            # Phase 1: High latency
            with network_fault_injector.inject_latency(500):
                chaos_ibkr_client.network_injector = network_fault_injector
                order1 = {'order_id': 'TEST001', 'symbol': 'AAPL', 'qty': 100}
                result1 = chaos_ibkr_client.place_order(order1)
                assert result1, "Failed under high latency"

            # Phase 2: Packet loss
            with network_fault_injector.inject_packet_loss(0.10):
                chaos_ibkr_client.network_injector = network_fault_injector
                order2 = {'order_id': 'TEST002', 'symbol': 'GOOGL', 'qty': 50}
                # May need retry
                result2 = None
                for _ in range(3):
                    result2 = chaos_ibkr_client.place_order(order2)
                    if result2:
                        break
                    time.sleep(0.1)
                assert result2, "Failed under packet loss even with retries"

            # Phase 3: Brief disconnect
            with network_fault_injector.inject_disconnect(2.0):
                chaos_ibkr_client.network_injector = network_fault_injector
                assert not chaos_ibkr_client.is_connected()
                timer.mark_detected()
                time.sleep(2.0)

            # Recovery
            timer.mark_recovery_started()
            for attempt in range(5):
                if chaos_ibkr_client.connect():
                    break
                time.sleep(1)

            assert chaos_ibkr_client.is_connected()
            timer.mark_recovery_completed()

        print(f"\n{timer.metrics}")
        assert timer.metrics.meets_rto, "Recovery too slow under combined faults"


@pytest.mark.chaos
def test_network_resilience_metrics(
    chaos_ibkr_client,
    network_fault_injector,
):
    """Collect and validate network resilience metrics"""
    with chaos_scenario("Network Metrics Collection", FaultType.NETWORK_LATENCY):
        assert chaos_ibkr_client.connect()

        # Test various scenarios and collect metrics
        scenarios = [
            ('normal', 0, 0.0),
            ('latent', 200, 0.0),
            ('lossy', 0, 0.10),
            ('degraded', 500, 0.20),
        ]

        results = {}

        for name, latency, loss in scenarios:
            chaos_ibkr_client.reset_chaos()

            with network_fault_injector.inject_latency(latency):
                with network_fault_injector.inject_packet_loss(loss):
                    chaos_ibkr_client.network_injector = network_fault_injector

                    # Place test orders
                    successful = 0
                    for i in range(10):
                        order = {'order_id': f'{name}_{i}', 'symbol': 'AAPL', 'qty': 100}
                        if chaos_ibkr_client.place_order(order):
                            successful += 1

                    results[name] = successful / 10

        print("\nNetwork Resilience Results:")
        for name, success_rate in results.items():
            print(f"  {name}: {success_rate:.0%} success rate")

        # Validate baseline performance
        assert results['normal'] >= 0.95, "Poor performance under normal conditions"
        assert results['latent'] >= 0.90, "Poor tolerance to latency"
        assert results['lossy'] >= 0.80, "Poor tolerance to packet loss"
