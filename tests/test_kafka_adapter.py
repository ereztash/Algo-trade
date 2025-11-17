"""
Unit tests for KafkaAdapter.

Tests cover:
- Configuration loading from environment
- Producer initialization and message publishing
- Consumer initialization and message consumption
- Message validation and DLQ routing
- Health checks and metrics
- Error handling and connection management
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from data_plane.bus.kafka_adapter import (
    KafkaAdapter,
    KafkaConfig,
    create_kafka_adapter,
    DLQ_TOPIC_MAP,
)
from contracts.schema_validator import ValidationMode


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def kafka_config():
    """Create a test Kafka configuration."""
    return KafkaConfig(
        bootstrap_servers="localhost:9092",
        client_id="test-client",
        compression_type="snappy",
        validation_mode=ValidationMode.BOTH,
        dlq_enabled=True,
    )


@pytest.fixture
def valid_bar_event():
    """Create a valid BarEvent message."""
    return {
        "event_type": "bar_event",
        "symbol": "SPY",
        "timestamp": "2025-11-17T10:00:00Z",
        "open": 450.0,
        "high": 452.0,
        "low": 449.0,
        "close": 451.0,
        "volume": 1000000,
        "bar_size": "5min",
        "conid": 12345,
    }


@pytest.fixture
def invalid_bar_event():
    """Create an invalid BarEvent message (high < low)."""
    return {
        "event_type": "bar_event",
        "symbol": "SPY",
        "timestamp": "2025-11-17T10:00:00Z",
        "open": 450.0,
        "high": 448.0,  # Invalid: high < low
        "low": 449.0,
        "close": 451.0,
        "volume": 1000000,
        "bar_size": "5min",
        "conid": 12345,
    }


@pytest.fixture
def valid_order_intent():
    """Create a valid OrderIntent message."""
    return {
        "event_type": "order_intent",
        "intent_id": "intent-001",
        "symbol": "SPY",
        "direction": "BUY",
        "quantity": 100,
        "order_type": "LIMIT",
        "limit_price": 450.0,
        "timestamp": "2025-11-17T10:00:00Z",
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


# =============================================================================
# Configuration Tests
# =============================================================================

class TestKafkaConfig:
    """Tests for KafkaConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = KafkaConfig()

        assert config.bootstrap_servers == "localhost:9092"
        assert config.client_id == "algo-trade-client"
        assert config.compression_type == "snappy"
        assert config.acks == "all"
        assert config.validation_mode == ValidationMode.BOTH
        assert config.dlq_enabled is True

    def test_custom_config(self):
        """Test custom configuration values."""
        config = KafkaConfig(
            bootstrap_servers="kafka:9093",
            client_id="custom-client",
            compression_type="lz4",
            acks="1",
            validation_mode=ValidationMode.PYDANTIC_ONLY,
            dlq_enabled=False,
        )

        assert config.bootstrap_servers == "kafka:9093"
        assert config.client_id == "custom-client"
        assert config.compression_type == "lz4"
        assert config.acks == "1"
        assert config.validation_mode == ValidationMode.PYDANTIC_ONLY
        assert config.dlq_enabled is False

    @patch.dict("os.environ", {
        "KAFKA_BOOTSTRAP_SERVERS": "prod-kafka:9092",
        "KAFKA_CLIENT_ID": "prod-client",
        "KAFKA_COMPRESSION_TYPE": "zstd",
        "KAFKA_ACKS": "all",
        "VALIDATION_MODE": "pydantic_only",
        "VALIDATION_DLQ_ENABLED": "false",
    })
    def test_config_from_env(self):
        """Test configuration loading from environment variables."""
        config = KafkaConfig.from_env()

        assert config.bootstrap_servers == "prod-kafka:9092"
        assert config.client_id == "prod-client"
        assert config.compression_type == "zstd"
        assert config.acks == "all"
        assert config.validation_mode == ValidationMode.PYDANTIC_ONLY
        assert config.dlq_enabled is False


# =============================================================================
# KafkaAdapter Tests
# =============================================================================

class TestKafkaAdapter:
    """Tests for KafkaAdapter."""

    def test_init(self, kafka_config):
        """Test adapter initialization."""
        adapter = KafkaAdapter(kafka_config)

        assert adapter.config == kafka_config
        assert adapter.producer is None
        assert len(adapter.consumers) == 0
        assert adapter._connected is False

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    async def test_connect(self, mock_producer_class, kafka_config):
        """Test Kafka connection."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer_class.return_value = mock_producer

        adapter = KafkaAdapter(kafka_config)
        await adapter.connect()

        # Verify producer was created and started
        assert adapter._connected is True
        assert adapter.producer is not None
        mock_producer.start.assert_called_once()

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    async def test_publish_valid_message(self, mock_producer_class, kafka_config, valid_bar_event):
        """Test publishing a valid message."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer.send_and_wait = AsyncMock()
        mock_producer_class.return_value = mock_producer

        adapter = KafkaAdapter(kafka_config)
        await adapter.connect()

        # Publish message
        result = await adapter.publish("market_events", valid_bar_event, key="SPY")

        # Verify
        assert result is True
        mock_producer.send_and_wait.assert_called_once()
        assert adapter.get_metrics()["messages_published"] == 1
        assert adapter.get_metrics()["validation_errors"] == 0

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    async def test_publish_invalid_message_with_dlq(
        self, mock_producer_class, kafka_config, invalid_bar_event
    ):
        """Test publishing an invalid message routes to DLQ."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer.send_and_wait = AsyncMock()
        mock_producer_class.return_value = mock_producer

        adapter = KafkaAdapter(kafka_config)
        await adapter.connect()

        # Publish invalid message
        result = await adapter.publish("market_events", invalid_bar_event, key="SPY")

        # Verify
        assert result is False  # Validation failed
        assert adapter.get_metrics()["validation_errors"] == 1
        assert adapter.get_metrics()["dlq_messages"] == 1

        # Verify DLQ message was sent
        assert mock_producer.send_and_wait.call_count == 1  # Only DLQ message
        call_args = mock_producer.send_and_wait.call_args
        assert call_args[0][0] == "dlq_market_events"  # DLQ topic

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    async def test_publish_without_validation(
        self, mock_producer_class, kafka_config, invalid_bar_event
    ):
        """Test publishing without validation bypasses checks."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer.send_and_wait = AsyncMock()
        mock_producer_class.return_value = mock_producer

        adapter = KafkaAdapter(kafka_config)
        await adapter.connect()

        # Publish without validation
        result = await adapter.publish(
            "market_events", invalid_bar_event, key="SPY", validate=False
        )

        # Verify
        assert result is True  # Published without validation
        assert adapter.get_metrics()["messages_published"] == 1
        assert adapter.get_metrics()["validation_errors"] == 0

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    @patch("data_plane.bus.kafka_adapter.AIOKafkaConsumer")
    async def test_consume_valid_messages(
        self, mock_consumer_class, mock_producer_class, kafka_config, valid_bar_event
    ):
        """Test consuming valid messages."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer_class.return_value = mock_producer

        # Mock consumer
        mock_record = MagicMock()
        mock_record.value = valid_bar_event
        mock_record.offset = 0
        mock_record.partition = 0

        async def mock_consumer_iter():
            yield mock_record

        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer.__aiter__ = lambda self: mock_consumer_iter()
        mock_consumer_class.return_value = mock_consumer

        adapter = KafkaAdapter(kafka_config)
        await adapter.connect()

        # Consume messages
        messages = []
        async for msg in adapter.consume("market_events", "test-group"):
            messages.append(msg)
            break  # Only consume one message

        # Verify
        assert len(messages) == 1
        assert messages[0] == valid_bar_event
        assert adapter.get_metrics()["messages_consumed"] == 1
        assert adapter.get_metrics()["validation_errors"] == 0

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    @patch("data_plane.bus.kafka_adapter.AIOKafkaConsumer")
    async def test_consume_invalid_message_routes_to_dlq(
        self, mock_consumer_class, mock_producer_class, kafka_config, invalid_bar_event
    ):
        """Test consuming invalid message routes to DLQ and skips message."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer.send_and_wait = AsyncMock()
        mock_producer_class.return_value = mock_producer

        # Mock consumer
        mock_record = MagicMock()
        mock_record.value = invalid_bar_event
        mock_record.offset = 0
        mock_record.partition = 0

        async def mock_consumer_iter():
            yield mock_record

        mock_consumer = AsyncMock()
        mock_consumer.start = AsyncMock()
        mock_consumer.__aiter__ = lambda self: mock_consumer_iter()
        mock_consumer_class.return_value = mock_consumer

        adapter = KafkaAdapter(kafka_config)
        await adapter.connect()

        # Consume messages
        messages = []
        async for msg in adapter.consume("market_events", "test-group"):
            messages.append(msg)
            break  # Should not reach here

        # Verify
        assert len(messages) == 0  # Invalid message skipped
        assert adapter.get_metrics()["messages_consumed"] == 1
        assert adapter.get_metrics()["validation_errors"] == 1
        assert adapter.get_metrics()["dlq_messages"] == 1

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    async def test_close(self, mock_producer_class, kafka_config):
        """Test adapter close."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer.stop = AsyncMock()
        mock_producer_class.return_value = mock_producer

        adapter = KafkaAdapter(kafka_config)
        await adapter.connect()
        await adapter.close()

        # Verify
        assert adapter._connected is False
        mock_producer.stop.assert_called_once()

    def test_health_disconnected(self, kafka_config):
        """Test health check when disconnected."""
        adapter = KafkaAdapter(kafka_config)
        health = adapter.health()

        assert health["connected"] is False
        assert health["producer_ready"] is False
        assert health["active_consumers"] == 0

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    async def test_health_connected(self, mock_producer_class, kafka_config):
        """Test health check when connected."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer_class.return_value = mock_producer

        adapter = KafkaAdapter(kafka_config)
        await adapter.connect()
        health = adapter.health()

        # Verify
        assert health["connected"] is True
        assert health["producer_ready"] is True
        assert health["config"]["bootstrap_servers"] == "localhost:9092"

    def test_get_metrics(self, kafka_config):
        """Test metrics retrieval."""
        adapter = KafkaAdapter(kafka_config)
        metrics = adapter.get_metrics()

        assert "messages_published" in metrics
        assert "messages_consumed" in metrics
        assert "validation_errors" in metrics
        assert "dlq_messages" in metrics

    def test_reset_metrics(self, kafka_config):
        """Test metrics reset."""
        adapter = KafkaAdapter(kafka_config)
        adapter._metrics["messages_published"] = 100
        adapter._metrics["validation_errors"] = 5

        adapter.reset_metrics()

        assert adapter.get_metrics()["messages_published"] == 0
        assert adapter.get_metrics()["validation_errors"] == 0


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    @patch("data_plane.bus.kafka_adapter.AIOKafkaProducer")
    async def test_create_kafka_adapter(self, mock_producer_class):
        """Test create_kafka_adapter convenience function."""
        # Mock producer
        mock_producer = AsyncMock()
        mock_producer.start = AsyncMock()
        mock_producer_class.return_value = mock_producer

        # Create adapter
        adapter = await create_kafka_adapter(
            bootstrap_servers="test-kafka:9092",
            client_id="test-client"
        )

        # Verify
        assert adapter._connected is True
        assert adapter.config.bootstrap_servers == "test-kafka:9092"
        assert adapter.config.client_id == "test-client"

        await adapter.close()


# =============================================================================
# DLQ Topic Mapping Tests
# =============================================================================

class TestDLQTopicMapping:
    """Tests for DLQ topic mapping."""

    def test_dlq_topic_map(self):
        """Test DLQ topic mapping."""
        assert DLQ_TOPIC_MAP["market_events"] == "dlq_market_events"
        assert DLQ_TOPIC_MAP["order_intents"] == "dlq_order_intents"
        assert DLQ_TOPIC_MAP["exec_reports"] == "dlq_execution_reports"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
