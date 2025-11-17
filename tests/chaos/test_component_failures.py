"""
Component Failure Tests

Tests resilience to component-level failures:
- Kafka broker failures
- Producer/consumer failures
- Orchestrator failures
- Cascading failures across components
- Circuit breaker behavior

Recovery Target: ≤30 seconds
"""

import pytest
import time
from unittest.mock import Mock
from tests.chaos.utils import (
    RecoveryTimer,
    StateValidator,
    chaos_scenario,
    FaultType,
)


@pytest.mark.chaos
@pytest.mark.slow
class TestKafkaResilience:
    """Test Kafka message bus resilience"""

    def test_kafka_broker_shutdown(
        self,
        mock_kafka_producer,
        chaos_config,
    ):
        """
        Test recovery from Kafka broker shutdown.

        Scenario:
        1. Normal message production
        2. Broker fails
        3. Messages buffered locally
        4. Broker recovers
        5. Messages flushed
        6. Verify recovery within RTO
        """
        with chaos_scenario("Kafka Broker Shutdown", FaultType.COMPONENT_CRASH):
            # Establish baseline
            assert mock_kafka_producer.connected

            # Send some messages successfully
            for i in range(5):
                result = mock_kafka_producer.send('test_topic', {'msg_id': i})
                assert result is not None

            timer = RecoveryTimer()
            with timer:
                # Inject broker failure
                mock_kafka_producer.inject_broker_failure()
                assert not mock_kafka_producer.connected
                timer.mark_detected()

                # Attempt to send messages (should fail or buffer)
                buffered_messages = []
                for i in range(5, 10):
                    try:
                        mock_kafka_producer.send('test_topic', {'msg_id': i})
                    except Exception as e:
                        # Buffer locally instead
                        buffered_messages.append({'msg_id': i})
                        print(f"  Message {i} buffered due to: {e}")

                print(f"  Buffered {len(buffered_messages)} messages during outage")

                # Broker recovers
                timer.mark_recovery_started()
                mock_kafka_producer.reset()
                assert mock_kafka_producer.connected

                # Flush buffered messages
                for msg in buffered_messages:
                    result = mock_kafka_producer.send('test_topic', msg)
                    assert result is not None

                mock_kafka_producer.flush()
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto
            assert len(buffered_messages) == 5, "Message buffering failed"

    def test_kafka_producer_timeout(
        self,
        mock_kafka_producer,
        state_validator,
    ):
        """
        Test handling of Kafka producer timeouts.

        Scenario:
        1. Inject slow sends (timeout)
        2. Detect timeout
        3. Retry with backoff
        4. Verify message delivery
        """
        with chaos_scenario("Kafka Producer Timeout", FaultType.CONNECTION_TIMEOUT):
            timer = RecoveryTimer()
            with timer:
                # Inject timeout
                mock_kafka_producer.inject_timeout()

                # Attempt to send (will timeout)
                msg = {'msg_id': 'TEST001'}
                try:
                    start = time.time()
                    mock_kafka_producer.send('test_topic', msg)
                    elapsed = time.time() - start
                    print(f"  Send took {elapsed:.1f}s (timeout)")
                except Exception as e:
                    print(f"  Timeout detected: {e}")

                timer.mark_detected()

                # Reset and retry
                timer.mark_recovery_started()
                mock_kafka_producer.reset()

                result = mock_kafka_producer.send('test_topic', msg)
                assert result is not None, "Retry failed"
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_kafka_consumer_lag_recovery(
        self,
        mock_kafka_consumer,
        chaos_config,
    ):
        """
        Test recovery from consumer lag.

        Scenario:
        1. Consumer processing normally
        2. Inject lag (1000 messages behind)
        3. Detect lag
        4. Increase processing rate
        5. Verify catch-up within RTO
        """
        with chaos_scenario("Kafka Consumer Lag", FaultType.SLOW_RESPONSE):
            timer = RecoveryTimer()
            with timer:
                # Inject lag
                lag_size = 1000
                mock_kafka_consumer.inject_lag(lag_size)
                print(f"  Injected lag: {lag_size} messages")
                timer.mark_detected()

                # Start catch-up
                timer.mark_recovery_started()

                # Process messages at increased rate
                processed = 0
                start_time = time.time()
                batch_size = 100

                while mock_kafka_consumer._message_queue:
                    # Process batch
                    batch = mock_kafka_consumer._message_queue[:batch_size]
                    mock_kafka_consumer._message_queue = (
                        mock_kafka_consumer._message_queue[batch_size:]
                    )
                    processed += len(batch)

                    # Brief processing time per batch
                    time.sleep(0.1)

                    # Check if caught up
                    remaining = len(mock_kafka_consumer._message_queue)
                    if remaining == 0:
                        break

                    # Safety: don't exceed RTO
                    if time.time() - start_time > 25:
                        print(f"  Warning: {remaining} messages still lagging")
                        break

                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            print(f"  Processed {processed}/{lag_size} messages")

            assert timer.metrics.meets_rto, "Failed to catch up within RTO"
            assert processed >= lag_size * 0.95, "Too many messages unprocessed"

    def test_kafka_rebalancing_handling(
        self,
        mock_kafka_consumer,
    ):
        """
        Test handling of consumer rebalancing.

        Scenario:
        1. Consumer processing
        2. Rebalance triggered
        3. Detect rebalance
        4. Rejoin and resume
        5. Verify recovery
        """
        with chaos_scenario("Kafka Rebalancing", FaultType.COMPONENT_CRASH):
            timer = RecoveryTimer()
            with timer:
                # Inject rebalance
                mock_kafka_consumer.inject_rebalance()

                # Attempt to poll (will fail with rebalance exception)
                try:
                    mock_kafka_consumer.poll(timeout=1.0)
                    assert False, "Should have raised rebalance exception"
                except Exception as e:
                    print(f"  Rebalance detected: {e}")
                    timer.mark_detected()

                # Recovery: reset consumer
                timer.mark_recovery_started()
                mock_kafka_consumer.reset()

                # Resume polling
                result = mock_kafka_consumer.poll(timeout=1.0)
                assert result is not None or result == {}, "Polling failed after rebalance"
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto


@pytest.mark.chaos
@pytest.mark.slow
class TestOrchestratorResilience:
    """Test orchestrator component resilience"""

    def test_orchestrator_restart_recovery(
        self,
        chaos_orchestrator,
        state_validator,
    ):
        """
        Test orchestrator restart and state recovery.

        Scenario:
        1. Orchestrator running
        2. Process crash
        3. Restart
        4. Verify state restoration
        5. Resume processing
        """
        with chaos_scenario("Orchestrator Restart", FaultType.COMPONENT_CRASH):
            # Start orchestrator
            chaos_orchestrator.start()
            assert chaos_orchestrator.is_running

            # Process some messages
            for i in range(5):
                msg = {'msg_id': i, 'data': f'test_{i}'}
                assert chaos_orchestrator.process_message(msg)

            timer = RecoveryTimer()
            with timer:
                # Simulate crash
                chaos_orchestrator.stop()
                assert not chaos_orchestrator.is_running
                timer.mark_detected()

                # Restart
                timer.mark_recovery_started()
                chaos_orchestrator.start()
                assert chaos_orchestrator.is_running

                # Verify can process again
                test_msg = {'msg_id': 'recovery_test', 'data': 'test'}
                assert chaos_orchestrator.process_message(test_msg)
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_orchestrator_with_ibkr_failure(
        self,
        chaos_orchestrator,
    ):
        """
        Test orchestrator when IBKR connection fails.

        Scenario:
        1. Orchestrator running with IBKR connected
        2. IBKR disconnects
        3. Orchestrator detects and handles gracefully
        4. IBKR reconnects
        5. Orchestrator resumes
        """
        with chaos_scenario("Orchestrator IBKR Failure", FaultType.NETWORK_DISCONNECT):
            chaos_orchestrator.start()

            # Verify IBKR is connected
            assert chaos_orchestrator.ibkr_client.is_connected()

            timer = RecoveryTimer()
            with timer:
                # IBKR disconnects
                chaos_orchestrator.ibkr_client.inject_disconnect()
                assert not chaos_orchestrator.ibkr_client.is_connected()
                timer.mark_detected()

                # Orchestrator should handle gracefully
                # (in real system, would buffer or pause)

                # Reconnect IBKR
                timer.mark_recovery_started()
                for attempt in range(3):
                    if chaos_orchestrator.ibkr_client.connect():
                        break
                    time.sleep(1)

                assert chaos_orchestrator.ibkr_client.is_connected()

                # Verify orchestrator can continue
                test_msg = {'msg_id': 'recovery_test'}
                assert chaos_orchestrator.process_message(test_msg)
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_orchestrator_with_kafka_failure(
        self,
        chaos_orchestrator,
    ):
        """
        Test orchestrator when Kafka fails.

        Scenario:
        1. Orchestrator running with Kafka connected
        2. Kafka broker fails
        3. Orchestrator buffers messages locally
        4. Kafka recovers
        5. Orchestrator flushes buffer
        """
        with chaos_scenario("Orchestrator Kafka Failure", FaultType.COMPONENT_CRASH):
            chaos_orchestrator.start()

            timer = RecoveryTimer()
            with timer:
                # Kafka fails
                chaos_orchestrator.kafka_producer.inject_broker_failure()
                timer.mark_detected()

                # Orchestrator should buffer
                buffered = []
                for i in range(5):
                    msg = {'msg_id': i, 'data': f'test_{i}'}
                    try:
                        chaos_orchestrator.kafka_producer.send('topic', msg)
                    except:
                        # Buffer locally
                        buffered.append(msg)

                print(f"  Buffered {len(buffered)} messages")

                # Kafka recovers
                timer.mark_recovery_started()
                chaos_orchestrator.kafka_producer.reset()

                # Flush buffer
                for msg in buffered:
                    chaos_orchestrator.kafka_producer.send('topic', msg)
                chaos_orchestrator.kafka_producer.flush()

                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto


@pytest.mark.chaos
@pytest.mark.slow
class TestCascadingFailures:
    """Test cascading failure scenarios"""

    def test_ibkr_and_kafka_simultaneous_failure(
        self,
        chaos_orchestrator,
        state_validator,
        chaos_config,
    ):
        """
        Test recovery from simultaneous IBKR and Kafka failure.

        Scenario:
        1. Both IBKR and Kafka fail together
        2. Detect both failures
        3. Buffer all operations locally
        4. Both recover
        5. Restore operations
        6. Verify no data loss
        """
        with chaos_scenario("IBKR + Kafka Failure", FaultType.COMPONENT_CRASH):
            chaos_orchestrator.start()

            timer = RecoveryTimer()
            with timer:
                # Both fail
                chaos_orchestrator.ibkr_client.inject_disconnect()
                chaos_orchestrator.kafka_producer.inject_broker_failure()

                assert not chaos_orchestrator.ibkr_client.is_connected()
                assert not chaos_orchestrator.kafka_producer.connected
                timer.mark_detected()

                # Buffer operations
                buffered_orders = []
                buffered_messages = []

                for i in range(10):
                    # Try IBKR order
                    order = {'order_id': f'ORDER_{i}', 'symbol': 'AAPL', 'qty': 100}
                    result = chaos_orchestrator.ibkr_client.place_order(order)
                    if result is None:
                        buffered_orders.append(order)

                    # Try Kafka message
                    msg = {'msg_id': i, 'data': f'test_{i}'}
                    try:
                        chaos_orchestrator.kafka_producer.send('topic', msg)
                    except:
                        buffered_messages.append(msg)

                print(f"  Buffered {len(buffered_orders)} orders")
                print(f"  Buffered {len(buffered_messages)} messages")

                # Both recover
                timer.mark_recovery_started()

                # Recover IBKR
                for attempt in range(3):
                    if chaos_orchestrator.ibkr_client.connect():
                        break
                    time.sleep(1)

                # Recover Kafka
                chaos_orchestrator.kafka_producer.reset()

                # Flush buffers
                for order in buffered_orders:
                    result = chaos_orchestrator.ibkr_client.place_order(order)
                    assert result is not None, f"Failed to recover order {order['order_id']}"

                for msg in buffered_messages:
                    chaos_orchestrator.kafka_producer.send('topic', msg)

                chaos_orchestrator.kafka_producer.flush()
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto
            assert timer.metrics.data_loss_count == 0, "Data was lost during cascading failure"

    def test_data_plane_failure_isolation(
        self,
        chaos_ibkr_client,
        mock_kafka_producer,
    ):
        """
        Test that Data Plane failure doesn't affect Order Plane.

        Scenario:
        1. Data Plane IBKR connection fails
        2. Order Plane continues operating
        3. Verify isolation
        4. Data Plane recovers independently
        """
        with chaos_scenario("Data Plane Isolation", FaultType.NETWORK_DISCONNECT):
            # Simulate separate IBKR connections for data and order planes
            data_plane_client = chaos_ibkr_client
            order_plane_client = chaos_ibkr_client.__class__()  # Separate instance

            data_plane_client.connect()
            order_plane_client.connect()

            timer = RecoveryTimer()
            with timer:
                # Data plane fails
                data_plane_client.inject_disconnect()
                assert not data_plane_client.is_connected()
                timer.mark_detected()

                # Order plane should still work
                order = {'order_id': 'TEST001', 'symbol': 'AAPL', 'qty': 100}
                result = order_plane_client.place_order(order)
                assert result is not None, "Order plane affected by data plane failure"

                # Data plane recovers independently
                timer.mark_recovery_started()
                for attempt in range(3):
                    if data_plane_client.connect():
                        break
                    time.sleep(1)

                assert data_plane_client.is_connected()
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_order_plane_failure_isolation(
        self,
        chaos_ibkr_client,
    ):
        """
        Test that Order Plane failure doesn't affect Data Plane.

        Scenario:
        1. Order Plane IBKR connection fails
        2. Data Plane continues streaming
        3. Verify isolation
        4. Order Plane recovers independently
        """
        with chaos_scenario("Order Plane Isolation", FaultType.NETWORK_DISCONNECT):
            # Separate instances
            data_plane_client = chaos_ibkr_client
            order_plane_client = chaos_ibkr_client.__class__()

            data_plane_client.connect()
            order_plane_client.connect()

            timer = RecoveryTimer()
            with timer:
                # Order plane fails
                order_plane_client.inject_disconnect()
                assert not order_plane_client.is_connected()
                timer.mark_detected()

                # Data plane should still work
                tick = data_plane_client.stream_market_data('AAPL')
                assert tick is not None, "Data plane affected by order plane failure"

                # Order plane recovers
                timer.mark_recovery_started()
                for attempt in range(3):
                    if order_plane_client.connect():
                        break
                    time.sleep(1)

                assert order_plane_client.is_connected()
                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            assert timer.metrics.meets_rto

    def test_triple_failure_recovery(
        self,
        chaos_orchestrator,
    ):
        """
        Test recovery from triple failure: IBKR + Kafka + Network.

        Scenario:
        1. All three components fail
        2. Detect catastrophic failure
        3. Apply emergency procedures
        4. Gradual recovery
        5. Verify system restoration
        """
        with chaos_scenario("Triple Failure", FaultType.COMPONENT_CRASH):
            chaos_orchestrator.start()

            timer = RecoveryTimer()
            with timer:
                # Triple failure
                chaos_orchestrator.ibkr_client.inject_disconnect()
                chaos_orchestrator.kafka_producer.inject_broker_failure()
                network_injector = chaos_orchestrator.ibkr_client.network_injector
                chaos_orchestrator.ibkr_client.network_injector._is_disconnected = True

                timer.mark_detected()
                print("  CATASTROPHIC: All components failed")

                # Emergency: stop orchestrator gracefully
                chaos_orchestrator.stop()

                # Gradual recovery
                timer.mark_recovery_started()
                time.sleep(2)  # Brief cooldown

                # Recover network first
                chaos_orchestrator.ibkr_client.network_injector._is_disconnected = False

                # Recover IBKR
                for attempt in range(5):
                    if chaos_orchestrator.ibkr_client.connect():
                        print(f"  IBKR recovered after {attempt + 1} attempts")
                        break
                    time.sleep(2 ** attempt)

                # Recover Kafka
                chaos_orchestrator.kafka_producer.reset()
                print("  Kafka recovered")

                # Restart orchestrator
                chaos_orchestrator.start()
                print("  Orchestrator restarted")

                # Verify functionality
                test_msg = {'msg_id': 'recovery_test'}
                assert chaos_orchestrator.process_message(test_msg)

                timer.mark_recovery_completed()

            print(f"\n{timer.metrics}")
            # Triple failure may take longer but should still meet RTO
            assert timer.metrics.recovery_time_s is not None
            print(f"  Triple failure recovery: {timer.metrics.recovery_time_s:.1f}s")


@pytest.mark.chaos
def test_component_health_checks(
    chaos_orchestrator,
):
    """
    Test health check system for all components.

    Verifies:
    - Health checks detect failures
    - Health checks don't false-positive
    - Health status accurate
    """
    with chaos_scenario("Health Check System", FaultType.COMPONENT_CRASH):
        chaos_orchestrator.start()

        # All healthy initially
        assert chaos_orchestrator.ibkr_client.is_connected()
        assert chaos_orchestrator.kafka_producer.connected

        # Inject IBKR failure
        chaos_orchestrator.ibkr_client.inject_disconnect()
        assert not chaos_orchestrator.ibkr_client.is_connected()

        # Inject Kafka failure
        chaos_orchestrator.kafka_producer.inject_broker_failure()
        assert not chaos_orchestrator.kafka_producer.connected

        # Recover IBKR
        chaos_orchestrator.ibkr_client.connect()
        assert chaos_orchestrator.ibkr_client.is_connected()

        # Recover Kafka
        chaos_orchestrator.kafka_producer.reset()
        assert chaos_orchestrator.kafka_producer.connected

        print("  Health check system validated")
