"""
Integration test for Kafka end-to-end flow.

This test demonstrates the full message flow:
1. Data Plane publishes BarEvent to market_events topic
2. Strategy Plane consumes BarEvent and publishes OrderIntent to order_intents topic
3. Order Plane consumes OrderIntent and publishes ExecutionReport to exec_reports topic

NOTE: This test requires a running Kafka instance.
Run with: docker-compose up -d kafka && pytest tests/integration/test_kafka_e2e.py
"""

import pytest
import asyncio
from typing import List
from datetime import datetime

from data_plane.bus.kafka_adapter import create_kafka_adapter, KafkaConfig


# =============================================================================
# Test Configuration
# =============================================================================

@pytest.fixture
def test_kafka_config():
    """Create test Kafka configuration."""
    return KafkaConfig(
        bootstrap_servers="localhost:9092",
        client_id="e2e-test",
        auto_offset_reset="earliest",  # Start from beginning for tests
    )


# =============================================================================
# Sample Messages
# =============================================================================

def create_bar_event(symbol: str = "SPY") -> dict:
    """Create a valid BarEvent message."""
    return {
        "event_type": "bar_event",
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "open": 450.0,
        "high": 452.0,
        "low": 449.0,
        "close": 451.0,
        "volume": 1000000,
        "bar_size": "5min",
        "conid": 12345,
    }


def create_order_intent(symbol: str = "SPY") -> dict:
    """Create a valid OrderIntent message."""
    return {
        "event_type": "order_intent",
        "intent_id": f"intent-{symbol}-001",
        "symbol": symbol,
        "direction": "BUY",
        "quantity": 100,
        "order_type": "LIMIT",
        "limit_price": 450.0,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "strategy_id": "OFI",
        "time_in_force": "DAY",
        "urgency": "NORMAL",
        "risk_checks": {
            "within_box_limit": True,
            "within_gross_limit": True,
            "within_net_limit": True,
            "pnl_kill_switch": False,
            "drawdown_kill_switch": False,
        },
    }


def create_execution_report(intent_id: str, symbol: str = "SPY") -> dict:
    """Create a valid ExecutionReport message."""
    return {
        "event_type": "execution_report",
        "report_id": f"report-{intent_id}",
        "intent_id": intent_id,
        "order_id": f"order-{symbol}-001",
        "symbol": symbol,
        "status": "FILLED",
        "filled_quantity": 100,
        "average_fill_price": 450.25,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "commission": 1.50,
        "latency_metrics": {
            "intent_to_submit_ms": 100,
            "submit_to_ack_ms": 150,
            "ack_to_fill_ms": 5200,
            "total_latency_ms": 5450,
        },
        "metadata": {
            "broker": "IBKR",
            "account_id": "DU1234567",
        },
    }


# =============================================================================
# Integration Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_and_consume(test_kafka_config):
    """
    Test basic publish and consume flow.

    This test verifies:
    - Adapter can connect to Kafka
    - Messages can be published to a topic
    - Messages can be consumed from a topic
    - Messages are validated correctly
    """
    adapter = None

    try:
        # Create and connect adapter
        adapter = await create_kafka_adapter(
            bootstrap_servers=test_kafka_config.bootstrap_servers,
            client_id="pub-sub-test",
        )

        # Publish a message
        bar_event = create_bar_event("TEST")
        published = await adapter.publish("market_events", bar_event, key="TEST")

        assert published is True, "Message should be published successfully"

        # Consume the message
        consumed_messages: List[dict] = []

        async def consume_task():
            async for msg in adapter.consume("market_events", "test-group"):
                if msg.get("symbol") == "TEST":
                    consumed_messages.append(msg)
                    break  # Stop after consuming our test message

        # Run consume with timeout
        try:
            await asyncio.wait_for(consume_task(), timeout=10.0)
        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for message consumption")

        # Verify
        assert len(consumed_messages) == 1, "Should consume exactly one message"
        assert consumed_messages[0]["symbol"] == "TEST"
        assert consumed_messages[0]["event_type"] == "bar_event"

    finally:
        if adapter:
            await adapter.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_trading_flow(test_kafka_config):
    """
    Test end-to-end trading flow across multiple topics.

    Flow:
    1. Data Plane publishes BarEvent → market_events
    2. Strategy Plane consumes BarEvent, generates OrderIntent → order_intents
    3. Order Plane consumes OrderIntent, executes, publishes ExecutionReport → exec_reports

    This test simulates all three planes working together.
    """
    data_plane = None
    strategy_plane = None
    order_plane = None

    try:
        # Create adapters for each plane
        data_plane = await create_kafka_adapter(
            bootstrap_servers=test_kafka_config.bootstrap_servers,
            client_id="data-plane-test",
        )

        strategy_plane = await create_kafka_adapter(
            bootstrap_servers=test_kafka_config.bootstrap_servers,
            client_id="strategy-plane-test",
        )

        order_plane = await create_kafka_adapter(
            bootstrap_servers=test_kafka_config.bootstrap_servers,
            client_id="order-plane-test",
        )

        # Step 1: Data Plane publishes BarEvent
        bar_event = create_bar_event("E2E")
        await data_plane.publish("market_events", bar_event, key="E2E")

        # Step 2: Strategy Plane consumes BarEvent and publishes OrderIntent
        order_intent_generated = False

        async def strategy_task():
            nonlocal order_intent_generated
            async for bar_msg in strategy_plane.consume("market_events", "strategy-group"):
                if bar_msg.get("symbol") == "E2E":
                    # Generate OrderIntent
                    order_intent = create_order_intent("E2E")
                    await strategy_plane.publish("order_intents", order_intent, key="E2E")
                    order_intent_generated = True
                    break

        await asyncio.wait_for(strategy_task(), timeout=10.0)
        assert order_intent_generated, "OrderIntent should be generated by Strategy Plane"

        # Step 3: Order Plane consumes OrderIntent and publishes ExecutionReport
        execution_report_generated = False

        async def order_task():
            nonlocal execution_report_generated
            async for intent_msg in order_plane.consume("order_intents", "order-group"):
                if intent_msg.get("symbol") == "E2E":
                    # Execute order and generate ExecutionReport
                    exec_report = create_execution_report(intent_msg["intent_id"], "E2E")
                    await order_plane.publish("exec_reports", exec_report, key="E2E")
                    execution_report_generated = True
                    break

        await asyncio.wait_for(order_task(), timeout=10.0)
        assert execution_report_generated, "ExecutionReport should be generated by Order Plane"

        # Verify metrics
        data_metrics = data_plane.get_metrics()
        strategy_metrics = strategy_plane.get_metrics()
        order_metrics = order_plane.get_metrics()

        assert data_metrics["messages_published"] >= 1
        assert strategy_metrics["messages_consumed"] >= 1
        assert strategy_metrics["messages_published"] >= 1
        assert order_metrics["messages_consumed"] >= 1
        assert order_metrics["messages_published"] >= 1

    finally:
        # Close all adapters
        if data_plane:
            await data_plane.close()
        if strategy_plane:
            await strategy_plane.close()
        if order_plane:
            await order_plane.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invalid_message_routes_to_dlq(test_kafka_config):
    """
    Test that invalid messages are routed to Dead Letter Queue.

    This test verifies:
    - Invalid messages fail validation
    - Invalid messages are routed to DLQ topic
    - DLQ messages contain original message and errors
    """
    adapter = None

    try:
        adapter = await create_kafka_adapter(
            bootstrap_servers=test_kafka_config.bootstrap_servers,
            client_id="dlq-test",
        )

        # Publish an invalid message (high < low)
        invalid_bar = {
            "event_type": "bar_event",
            "symbol": "DLQ_TEST",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "open": 450.0,
            "high": 448.0,  # Invalid: high < low
            "low": 449.0,
            "close": 451.0,
            "volume": 1000000,
            "bar_size": "5min",
            "conid": 12345,
        }

        # Attempt to publish (should fail validation and route to DLQ)
        published = await adapter.publish("market_events", invalid_bar, key="DLQ_TEST")

        assert published is False, "Invalid message should fail validation"

        # Verify DLQ message was created
        metrics = adapter.get_metrics()
        assert metrics["validation_errors"] >= 1
        assert metrics["dlq_messages"] >= 1

        # Consume from DLQ topic
        dlq_messages: List[dict] = []

        async def consume_dlq():
            async for dlq_msg in adapter.consume("dlq_market_events", "dlq-test-group", validate=False):
                if dlq_msg.get("original_message", {}).get("symbol") == "DLQ_TEST":
                    dlq_messages.append(dlq_msg)
                    break

        await asyncio.wait_for(consume_dlq(), timeout=10.0)

        # Verify DLQ message structure
        assert len(dlq_messages) == 1
        dlq_msg = dlq_messages[0]

        assert "source_topic" in dlq_msg
        assert "original_message" in dlq_msg
        assert "validation_errors" in dlq_msg
        assert dlq_msg["source_topic"] == "market_events"
        assert len(dlq_msg["validation_errors"]) > 0

    finally:
        if adapter:
            await adapter.close()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("Running Kafka Integration Tests")
    print("=" * 80)
    print("PREREQUISITE: Kafka must be running on localhost:9092")
    print("Start Kafka with: docker-compose up -d kafka")
    print("=" * 80)
    print()

    pytest.main([__file__, "-v", "-s", "-m", "integration"])
