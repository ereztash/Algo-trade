"""
Pytest fixtures for chaos engineering tests.

Provides mocks and utilities with chaos injection capabilities.
"""

import pytest
import time
from typing import Dict, List, Optional
from unittest.mock import Mock, MagicMock
from tests.chaos.utils import (
    NetworkFaultInjector,
    RecoveryTimer,
    StateValidator,
    FaultType,
)


class ChaosIBKRClient:
    """
    IBKR client mock with chaos engineering capabilities.

    Extends basic mock with fault injection for:
    - Connection failures
    - Timeouts
    - Rate limiting
    - Slow responses
    - Partial data loss
    """

    def __init__(self):
        self.connected = False
        self.network_injector = NetworkFaultInjector()
        self.rate_limit_count = 0
        self.rate_limit_threshold = 100
        self.connection_attempts = 0
        self.last_connect_time = 0
        self.min_reconnect_delay_s = 1.0

        # Tracking
        self.sent_orders: List[Dict] = []
        self.acknowledged_orders: List[Dict] = []
        self.streamed_data: List[Dict] = []
        self.failed_requests: List[Dict] = []

        # Chaos configuration
        self.disconnect_on_next_request = False
        self.timeout_on_next_request = False
        self.slow_response_delay_ms = 0

    def connect(self) -> bool:
        """
        Connect to IBKR with chaos injection support.

        Returns:
            True if connected, False otherwise
        """
        self.connection_attempts += 1

        # Check network connectivity
        if self.network_injector.is_disconnected():
            self.connected = False
            return False

        # Enforce minimum reconnect delay
        time_since_last = time.time() - self.last_connect_time
        if time_since_last < self.min_reconnect_delay_s:
            time.sleep(self.min_reconnect_delay_s - time_since_last)

        # Apply network latency
        self.network_injector.apply_latency()

        # Simulate packet loss
        if self.network_injector.should_drop_packet():
            self.connected = False
            return False

        # Successful connection
        self.connected = True
        self.last_connect_time = time.time()
        return True

    def disconnect(self):
        """Disconnect from IBKR"""
        self.connected = False

    def is_connected(self) -> bool:
        """Check if currently connected"""
        # Network fault can cause implicit disconnect
        if self.network_injector.is_disconnected():
            self.connected = False
        return self.connected

    def place_order(self, order: Dict) -> Optional[Dict]:
        """
        Place an order with chaos injection.

        Args:
            order: Order dictionary with order_id, symbol, qty, etc.

        Returns:
            Order acknowledgment if successful, None otherwise
        """
        # Check connection
        if not self.is_connected():
            self.failed_requests.append({
                'type': 'place_order',
                'reason': 'not_connected',
                'order': order,
            })
            return None

        # Apply latency
        self.network_injector.apply_latency()

        # Chaos injection: disconnect
        if self.disconnect_on_next_request:
            self.disconnect()
            self.disconnect_on_next_request = False
            self.failed_requests.append({
                'type': 'place_order',
                'reason': 'disconnect',
                'order': order,
            })
            return None

        # Chaos injection: timeout
        if self.timeout_on_next_request:
            self.timeout_on_next_request = False
            time.sleep(10)  # Simulate timeout
            self.failed_requests.append({
                'type': 'place_order',
                'reason': 'timeout',
                'order': order,
            })
            return None

        # Chaos injection: slow response
        if self.slow_response_delay_ms > 0:
            time.sleep(self.slow_response_delay_ms / 1000.0)

        # Check rate limit
        self.rate_limit_count += 1
        if self.rate_limit_count > self.rate_limit_threshold:
            self.failed_requests.append({
                'type': 'place_order',
                'reason': 'rate_limit',
                'order': order,
            })
            return None

        # Packet loss
        if self.network_injector.should_drop_packet():
            self.failed_requests.append({
                'type': 'place_order',
                'reason': 'packet_loss',
                'order': order,
            })
            return None

        # Success
        self.sent_orders.append(order)
        ack = {
            'order_id': order['order_id'],
            'status': 'submitted',
            'timestamp': time.time(),
        }
        self.acknowledged_orders.append(ack)
        return ack

    def stream_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Stream market data with chaos injection.

        Args:
            symbol: Symbol to stream

        Returns:
            Market data tick if successful, None otherwise
        """
        if not self.is_connected():
            return None

        self.network_injector.apply_latency()

        if self.network_injector.should_drop_packet():
            return None

        tick = {
            'symbol': symbol,
            'price': 100.0,
            'timestamp': time.time(),
        }
        self.streamed_data.append(tick)
        return tick

    def inject_disconnect(self):
        """Inject immediate disconnect"""
        self.disconnect()

    def inject_disconnect_on_next_request(self):
        """Inject disconnect on next request"""
        self.disconnect_on_next_request = True

    def inject_timeout_on_next_request(self):
        """Inject timeout on next request"""
        self.timeout_on_next_request = True

    def inject_slow_response(self, delay_ms: int):
        """Inject slow response delay"""
        self.slow_response_delay_ms = delay_ms

    def inject_rate_limit(self):
        """Trigger rate limit"""
        self.rate_limit_count = self.rate_limit_threshold + 1

    def reset_chaos(self):
        """Reset all chaos injection settings"""
        self.disconnect_on_next_request = False
        self.timeout_on_next_request = False
        self.slow_response_delay_ms = 0
        self.network_injector = NetworkFaultInjector()

    def reset_rate_limit(self):
        """Reset rate limit counter"""
        self.rate_limit_count = 0

    def get_metrics(self) -> Dict:
        """Get client metrics for validation"""
        return {
            'connection_attempts': self.connection_attempts,
            'sent_orders': len(self.sent_orders),
            'acknowledged_orders': len(self.acknowledged_orders),
            'streamed_data': len(self.streamed_data),
            'failed_requests': len(self.failed_requests),
            'is_connected': self.is_connected(),
        }


@pytest.fixture
def chaos_ibkr_client():
    """Provide IBKR client with chaos injection capabilities"""
    client = ChaosIBKRClient()
    yield client
    # Cleanup
    client.disconnect()


@pytest.fixture
def network_fault_injector():
    """Provide network fault injector"""
    return NetworkFaultInjector()


@pytest.fixture
def recovery_timer():
    """Provide recovery timer for measuring recovery time"""
    return RecoveryTimer()


@pytest.fixture
def state_validator():
    """Provide state validator for consistency checks"""
    return StateValidator()


@pytest.fixture
def chaos_config():
    """Provide chaos testing configuration"""
    return {
        'rto_target_s': 30.0,  # Recovery Time Objective
        'max_data_loss_ratio': 0.05,  # 5% max data loss
        'max_retry_attempts': 5,
        'base_retry_delay_s': 1.0,
        'max_retry_delay_s': 30.0,
        'connection_timeout_s': 10.0,
        'request_timeout_s': 5.0,
        'rate_limit_per_minute': 100,
    }


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer with fault injection"""
    producer = Mock()
    producer.send = MagicMock(return_value=Mock())
    producer.flush = MagicMock()
    producer.close = MagicMock()
    producer.connected = True

    def inject_broker_failure():
        producer.connected = False
        producer.send.side_effect = Exception("Broker unavailable")

    def inject_timeout():
        def slow_send(*args, **kwargs):
            time.sleep(6)  # Exceed typical timeout
            return Mock()
        producer.send.side_effect = slow_send

    def reset():
        producer.connected = True
        producer.send.side_effect = None

    producer.inject_broker_failure = inject_broker_failure
    producer.inject_timeout = inject_timeout
    producer.reset = reset

    return producer


@pytest.fixture
def mock_kafka_consumer():
    """Mock Kafka consumer with fault injection"""
    consumer = Mock()
    consumer.poll = MagicMock(return_value={})
    consumer.close = MagicMock()
    consumer.connected = True
    consumer._message_queue = []

    def inject_lag(message_count: int):
        """Simulate consumer lag"""
        consumer._message_queue.extend([Mock()] * message_count)

    def inject_rebalance():
        """Simulate consumer rebalance"""
        consumer.poll.side_effect = Exception("Rebalancing")

    def reset():
        consumer.connected = True
        consumer.poll.side_effect = None
        consumer._message_queue.clear()

    consumer.inject_lag = inject_lag
    consumer.inject_rebalance = inject_rebalance
    consumer.reset = reset

    return consumer


@pytest.fixture
def chaos_orchestrator(chaos_ibkr_client, mock_kafka_producer):
    """Mock orchestrator with chaos-injectable components"""
    orchestrator = Mock()
    orchestrator.ibkr_client = chaos_ibkr_client
    orchestrator.kafka_producer = mock_kafka_producer
    orchestrator.is_running = False
    orchestrator.processed_messages = []
    orchestrator.failed_messages = []

    def start():
        if not chaos_ibkr_client.is_connected():
            chaos_ibkr_client.connect()
        orchestrator.is_running = True

    def stop():
        orchestrator.is_running = False

    def process_message(msg):
        if not orchestrator.is_running:
            orchestrator.failed_messages.append(msg)
            return False

        try:
            # Process message
            orchestrator.processed_messages.append(msg)
            return True
        except Exception as e:
            orchestrator.failed_messages.append(msg)
            return False

    orchestrator.start = start
    orchestrator.stop = stop
    orchestrator.process_message = process_message

    return orchestrator


@pytest.fixture(autouse=True)
def chaos_test_setup():
    """Setup and teardown for chaos tests"""
    # Setup
    print("\n[CHAOS TEST START]")
    start_time = time.time()

    yield

    # Teardown
    elapsed = time.time() - start_time
    print(f"[CHAOS TEST END] Duration: {elapsed:.2f}s\n")


# Parametrized fixtures for different chaos scenarios

@pytest.fixture(params=[3, 10, 30])
def network_disconnect_duration(request):
    """Parametrized network disconnect durations (seconds)"""
    return request.param


@pytest.fixture(params=[100, 500, 2000, 5000])
def network_latency_ms(request):
    """Parametrized network latencies (milliseconds)"""
    return request.param


@pytest.fixture(params=[0.05, 0.20, 0.50])
def packet_loss_probability(request):
    """Parametrized packet loss probabilities"""
    return request.param
