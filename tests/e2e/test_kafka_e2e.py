"""
End-to-End Kafka Integration Tests

Tests the full message flow across the 3-plane architecture:
1. Data Plane publishes market events (bar_event, tick_event, ofi_event)
2. Strategy Plane consumes market events and publishes order_intent
3. Order Plane consumes order_intent and publishes execution_report

Prerequisites:
- Kafka broker running on localhost:9092
- Topics created: market_events, order_intents, exec_reports
"""

import asyncio
import pytest
from datetime import datetime, timezone
from typing import List, Dict, Any

from data_plane.bus.kafka_adapter import create_kafka_adapter, KafkaAdapter
from contracts.schema_validator import MessageValidator, ValidationMode


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
async def kafka_adapter():
    """Create a connected Kafka adapter for testing."""
    adapter = await create_kafka_adapter(
        bootstrap_servers='localhost:9092',
        group_id='test_e2e_group',
        auto_offset_reset='latest'  # Only consume new messages
    )
    yield adapter
    await adapter.disconnect()


@pytest.fixture
def validator():
    """Create a message validator."""
    return MessageValidator(mode=ValidationMode.PYDANTIC_ONLY)


@pytest.fixture
def sample_bar_event():
    """Sample bar event for testing."""
    return {
        'event_type': 'bar_event',
        'symbol': 'SPY',
        'source': 'ibkr_rt',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'duration': '1m',
        'open': 450.0,
        'high': 455.0,
        'low': 449.0,
        'close': 452.0,
        'volume': 1000000,
        'data_quality': {
            'completeness': 0.98,
            'freshness_ms': 120,
            'ntp_synced': True
        }
    }


@pytest.fixture
def sample_tick_event():
    """Sample tick event for testing."""
    return {
        'event_type': 'tick_event',
        'symbol': 'TSLA',
        'source': 'ibkr_rt',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'price': 250.75,
        'size': 100,
        'tick_type': 'TRADE',
        'data_quality': {
            'completeness': 1.0,
            'freshness_ms': 50,
            'ntp_synced': True
        }
    }


@pytest.fixture
def sample_ofi_event():
    """Sample OFI event for testing."""
    return {
        'event_type': 'ofi_event',
        'symbol': 'AAPL',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'ofi_value': 1500.0,
        'bid_volume_change': 800,
        'ask_volume_change': -700,
        'imbalance_ratio': 0.6
    }


@pytest.fixture
def sample_order_intent():
    """Sample order intent for testing."""
    return {
        'event_type': 'order_intent',
        'symbol': 'SPY',
        'strategy': 'OFI_Strategy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'intent_id': 'TEST_INTENT_001',
        'direction': 'BUY',
        'quantity': 100,
        'order_type': 'MARKET',
        'urgency': 'NORMAL',
        'signal_strength': 0.75,
        'risk_checks': {
            'pre_trade_passed': True,
            'position_limit_ok': True,
            'pov_limit_ok': True,
            'exposure_ok': True
        }
    }


@pytest.fixture
def sample_execution_report():
    """Sample execution report for testing."""
    return {
        'event_type': 'execution_report',
        'symbol': 'SPY',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'order_id': 'ORD_001',
        'intent_id': 'TEST_INTENT_001',
        'status': 'FILLED',
        'direction': 'BUY',
        'filled_qty': 100,
        'avg_fill_price': 451.50,
        'commission': 1.0,
        'slippage_bps': 2.5,
        'latency': {
            'intent_to_submit_ms': 15,
            'submit_to_ack_ms': 45,
            'ack_to_fill_ms': 120,
            'total_fill_ms': 180
        }
    }


# ============================================================================
# Unit Tests: Basic Kafka Operations
# ============================================================================

@pytest.mark.asyncio
async def test_kafka_connect_disconnect():
    """Test Kafka connection lifecycle."""
    adapter = await create_kafka_adapter('localhost:9092', group_id='test_lifecycle')

    # Check connection
    assert adapter.connected is True
    assert adapter.producer_started is True

    # Check health
    health = adapter.health()
    assert health['connected'] is True
    assert health['producer_started'] is True

    # Disconnect
    await adapter.disconnect()
    assert adapter.connected is False


@pytest.mark.asyncio
async def test_kafka_publish_bar_event(kafka_adapter, sample_bar_event, validator):
    """Test publishing a bar event to Kafka."""
    # Validate message before publishing
    result = validator.validate_message(sample_bar_event, 'bar_event')
    assert result.is_valid, f"Validation failed: {result.errors}"

    # Publish to Kafka
    await kafka_adapter.publish('test_market_events', sample_bar_event, key='SPY')

    # If we get here without exception, publish succeeded
    assert True


@pytest.mark.asyncio
async def test_kafka_publish_tick_event(kafka_adapter, sample_tick_event, validator):
    """Test publishing a tick event to Kafka."""
    result = validator.validate_message(sample_tick_event, 'tick_event')
    assert result.is_valid, f"Validation failed: {result.errors}"

    await kafka_adapter.publish('test_market_events', sample_tick_event, key='TSLA')
    assert True


@pytest.mark.asyncio
async def test_kafka_publish_ofi_event(kafka_adapter, sample_ofi_event, validator):
    """Test publishing an OFI event to Kafka."""
    result = validator.validate_message(sample_ofi_event, 'ofi_event')
    assert result.is_valid, f"Validation failed: {result.errors}"

    await kafka_adapter.publish('test_market_events', sample_ofi_event, key='AAPL')
    assert True


@pytest.mark.asyncio
async def test_kafka_publish_consume_roundtrip(kafka_adapter, sample_bar_event):
    """Test publish and consume roundtrip with a single message."""
    topic = 'test_roundtrip'

    # Publish
    await kafka_adapter.publish(topic, sample_bar_event, key='SPY')

    # Consume
    consumed = []
    async for message in kafka_adapter.consume(topic, group_id='test_roundtrip_consumer'):
        consumed.append(message)
        if len(consumed) >= 1:
            break  # Only consume the message we just published

    # Verify
    assert len(consumed) == 1
    msg = consumed[0]
    assert msg['event_type'] == 'bar_event'
    assert msg['symbol'] == 'SPY'
    assert msg['open'] == 450.0
    assert msg['close'] == 452.0


@pytest.mark.asyncio
async def test_kafka_validation_on_publish(kafka_adapter):
    """Test that validation fails for invalid messages on publish."""
    invalid_bar = {
        'event_type': 'bar_event',
        'symbol': 'SPY',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'open': 100.0,
        'high': 98.0,  # INVALID: high < open
        'low': 99.0,
        'close': 99.5,
        'volume': 1000
    }

    with pytest.raises(ValueError, match="Message validation failed"):
        await kafka_adapter.publish('test_validation', invalid_bar)


# ============================================================================
# Integration Tests: Multi-Message Flows
# ============================================================================

@pytest.mark.asyncio
async def test_data_plane_to_strategy_plane_flow(kafka_adapter, sample_bar_event, sample_tick_event, sample_ofi_event):
    """
    Test Data Plane → Strategy Plane message flow.

    Simulates:
    1. Data Plane publishes multiple market events
    2. Strategy Plane consumes them
    """
    topic = 'test_market_events_flow'

    # Publish multiple market events (simulating Data Plane)
    await kafka_adapter.publish(topic, sample_bar_event, key='SPY')
    await kafka_adapter.publish(topic, sample_tick_event, key='TSLA')
    await kafka_adapter.publish(topic, sample_ofi_event, key='AAPL')

    # Consume (simulating Strategy Plane)
    consumed_events = []
    async for message in kafka_adapter.consume(topic, group_id='strategy_plane_test'):
        consumed_events.append(message)
        if len(consumed_events) >= 3:
            break

    # Verify all event types received
    event_types = [msg['event_type'] for msg in consumed_events]
    assert 'bar_event' in event_types
    assert 'tick_event' in event_types
    assert 'ofi_event' in event_types


@pytest.mark.asyncio
async def test_strategy_plane_to_order_plane_flow(kafka_adapter, sample_order_intent):
    """
    Test Strategy Plane → Order Plane message flow.

    Simulates:
    1. Strategy Plane publishes order_intent
    2. Order Plane consumes it
    """
    topic = 'test_order_intents_flow'

    # Publish order intent (simulating Strategy Plane)
    await kafka_adapter.publish(topic, sample_order_intent, key='SPY')

    # Consume (simulating Order Plane)
    consumed = []
    async for message in kafka_adapter.consume(topic, group_id='order_plane_test'):
        consumed.append(message)
        if len(consumed) >= 1:
            break

    # Verify
    assert len(consumed) == 1
    intent = consumed[0]
    assert intent['event_type'] == 'order_intent'
    assert intent['symbol'] == 'SPY'
    assert intent['direction'] == 'BUY'
    assert intent['quantity'] == 100


@pytest.mark.asyncio
async def test_order_plane_to_strategy_plane_feedback(kafka_adapter, sample_execution_report):
    """
    Test Order Plane → Strategy Plane feedback loop.

    Simulates:
    1. Order Plane publishes execution_report
    2. Strategy Plane consumes it for learning
    """
    topic = 'test_exec_reports_flow'

    # Publish execution report (simulating Order Plane)
    await kafka_adapter.publish(topic, sample_execution_report, key='SPY')

    # Consume (simulating Strategy Plane learning loop)
    consumed = []
    async for message in kafka_adapter.consume(topic, group_id='strategy_learning_test'):
        consumed.append(message)
        if len(consumed) >= 1:
            break

    # Verify
    assert len(consumed) == 1
    exec_report = consumed[0]
    assert exec_report['event_type'] == 'execution_report'
    assert exec_report['status'] == 'FILLED'
    assert exec_report['filled_qty'] == 100
    assert exec_report['latency']['total_fill_ms'] == 180


# ============================================================================
# E2E Tests: Full 3-Plane Architecture
# ============================================================================

@pytest.mark.asyncio
async def test_full_3_plane_message_flow(
    kafka_adapter,
    sample_bar_event,
    sample_order_intent,
    sample_execution_report
):
    """
    Test complete message flow across all 3 planes.

    Flow:
    1. Data Plane publishes bar_event → market_events topic
    2. Strategy Plane consumes bar_event, generates order_intent → order_intents topic
    3. Order Plane consumes order_intent, executes, publishes execution_report → exec_reports topic
    4. Strategy Plane consumes execution_report for learning
    """
    # Step 1: Data Plane publishes market event
    await kafka_adapter.publish('e2e_market_events', sample_bar_event, key='SPY')

    # Step 2: Strategy Plane consumes market event
    consumed_bars = []
    async for message in kafka_adapter.consume('e2e_market_events', group_id='e2e_strategy'):
        consumed_bars.append(message)
        if len(consumed_bars) >= 1:
            break

    assert len(consumed_bars) == 1
    assert consumed_bars[0]['event_type'] == 'bar_event'

    # Step 3: Strategy Plane publishes order intent
    await kafka_adapter.publish('e2e_order_intents', sample_order_intent, key='SPY')

    # Step 4: Order Plane consumes order intent
    consumed_intents = []
    async for message in kafka_adapter.consume('e2e_order_intents', group_id='e2e_order_plane'):
        consumed_intents.append(message)
        if len(consumed_intents) >= 1:
            break

    assert len(consumed_intents) == 1
    assert consumed_intents[0]['event_type'] == 'order_intent'

    # Step 5: Order Plane publishes execution report
    await kafka_adapter.publish('e2e_exec_reports', sample_execution_report, key='SPY')

    # Step 6: Strategy Plane consumes execution report for learning
    consumed_reports = []
    async for message in kafka_adapter.consume('e2e_exec_reports', group_id='e2e_learning'):
        consumed_reports.append(message)
        if len(consumed_reports) >= 1:
            break

    assert len(consumed_reports) == 1
    assert consumed_reports[0]['event_type'] == 'execution_report'
    assert consumed_reports[0]['status'] == 'FILLED'


@pytest.mark.asyncio
async def test_high_throughput_message_flow(kafka_adapter):
    """
    Test high-throughput message publishing and consumption.

    Simulates realistic load with 1000 messages.
    """
    topic = 'test_high_throughput'
    num_messages = 1000

    # Publish many messages
    for i in range(num_messages):
        bar_event = {
            'event_type': 'bar_event',
            'symbol': f'SYM{i % 10}',  # 10 different symbols
            'source': 'ibkr_rt',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'duration': '1m',
            'open': 100.0 + i * 0.1,
            'high': 105.0 + i * 0.1,
            'low': 99.0 + i * 0.1,
            'close': 102.0 + i * 0.1,
            'volume': 1000 * (i + 1),
            'data_quality': {
                'completeness': 0.98,
                'freshness_ms': 100,
                'ntp_synced': True
            }
        }
        await kafka_adapter.publish(topic, bar_event, key=f'SYM{i % 10}')

    # Consume and count
    consumed_count = 0
    async for message in kafka_adapter.consume(topic, group_id='high_throughput_test'):
        consumed_count += 1
        if consumed_count >= num_messages:
            break

    assert consumed_count == num_messages


# ============================================================================
# Failure Scenario Tests
# ============================================================================

@pytest.mark.asyncio
async def test_invalid_message_handling(kafka_adapter):
    """
    Test that invalid messages are rejected and don't crash the system.
    """
    invalid_messages = [
        # Missing required fields
        {'event_type': 'bar_event', 'symbol': 'SPY'},

        # Invalid OHLC (high < open)
        {
            'event_type': 'bar_event',
            'symbol': 'SPY',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'open': 100.0,
            'high': 95.0,  # Invalid
            'low': 90.0,
            'close': 98.0,
            'volume': 1000
        },

        # Negative volume
        {
            'event_type': 'bar_event',
            'symbol': 'SPY',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'open': 100.0,
            'high': 105.0,
            'low': 99.0,
            'close': 102.0,
            'volume': -1000  # Invalid
        }
    ]

    # All should raise ValueError on publish
    for invalid_msg in invalid_messages:
        with pytest.raises(ValueError):
            await kafka_adapter.publish('test_invalid', invalid_msg)


@pytest.mark.asyncio
async def test_consumer_auto_skip_invalid_messages(kafka_adapter, sample_bar_event):
    """
    Test that consumers auto-skip invalid messages when validate_on_consume=True.
    """
    topic = 'test_auto_skip'

    # Publish valid message
    await kafka_adapter.publish(topic, sample_bar_event, key='SPY', validate=True)

    # Publish invalid message (bypass validation)
    invalid_bar = {
        'event_type': 'bar_event',
        'symbol': 'TSLA',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'open': 100.0,
        'high': 98.0,  # Invalid
        'low': 99.0,
        'close': 99.5,
        'volume': 1000
    }
    await kafka_adapter.publish(topic, invalid_bar, key='TSLA', validate=False)

    # Publish another valid message
    valid_bar_2 = {**sample_bar_event, 'symbol': 'AAPL'}
    await kafka_adapter.publish(topic, valid_bar_2, key='AAPL', validate=True)

    # Consume - should skip the invalid message
    consumed = []
    async for message in kafka_adapter.consume(topic, group_id='auto_skip_test', validate=True):
        consumed.append(message)
        if len(consumed) >= 2:
            break

    # Should have consumed 2 valid messages, skipped the invalid one
    assert len(consumed) == 2
    assert consumed[0]['symbol'] == 'SPY'
    assert consumed[1]['symbol'] == 'AAPL'
