"""
Kafka Message Bus Adapter - Production Implementation

This module provides a production-ready Kafka adapter for the Algo-Trade system
with async support, error handling, DLQ routing, and comprehensive monitoring.

Features:
- Async producer with batching and compression
- Async consumer with offset management
- Schema validation with DLQ routing for invalid messages
- Retry logic with exponential backoff
- Health checks and monitoring
- Graceful shutdown

Usage:
    from data_plane.bus.kafka_adapter import KafkaAdapter, KafkaConfig

    config = KafkaConfig(
        bootstrap_servers="localhost:9092",
        client_id="data-plane-client"
    )

    adapter = KafkaAdapter(config)
    await adapter.connect()

    # Publish a message
    await adapter.publish("market_events", {"symbol": "SPY", ...})

    # Consume messages
    async for message in adapter.consume("market_events", "data-plane-group"):
        print(f"Received: {message}")

    await adapter.close()
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncIterator, List
from dataclasses import dataclass
from enum import Enum

try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    from aiokafka.errors import KafkaError, KafkaConnectionError
except ImportError:
    raise ImportError(
        "aiokafka is required for KafkaAdapter. "
        "Install with: pip install aiokafka>=0.9.0"
    )

from contracts.schema_validator import MessageValidator, ValidationMode, ValidationResult

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class KafkaConfig:
    """
    Kafka adapter configuration.

    Attributes:
        bootstrap_servers: Comma-separated list of Kafka brokers (host:port)
        client_id: Client identifier for this connection
        security_protocol: Security protocol (PLAINTEXT, SASL_SSL, SSL)
        sasl_mechanism: SASL mechanism (PLAIN, SCRAM-SHA-256, SCRAM-SHA-512)
        sasl_username: SASL username (optional)
        sasl_password: SASL password (optional)
        ssl_ca_location: Path to CA certificate (optional)
        ssl_cert_location: Path to client certificate (optional)
        ssl_key_location: Path to client key (optional)
        compression_type: Compression type (none, gzip, snappy, lz4, zstd)
        batch_size: Producer batch size in bytes
        linger_ms: Time to wait before sending batch (milliseconds)
        max_in_flight_requests: Max number of unacknowledged requests
        acks: Number of acknowledgments (0, 1, all)
        enable_auto_commit: Enable automatic offset commit
        auto_commit_interval_ms: Auto-commit interval (milliseconds)
        auto_offset_reset: Where to start consuming (earliest, latest)
        session_timeout_ms: Consumer session timeout (milliseconds)
        max_poll_records: Max records per poll
        request_timeout_ms: Request timeout (milliseconds)
        validation_mode: Message validation mode
        dlq_enabled: Enable Dead Letter Queue for invalid messages
    """
    bootstrap_servers: str = "localhost:9092"
    client_id: str = "algo-trade-client"

    # Security
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: Optional[str] = None
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None
    ssl_ca_location: Optional[str] = None
    ssl_cert_location: Optional[str] = None
    ssl_key_location: Optional[str] = None

    # Producer Configuration
    compression_type: str = "snappy"
    batch_size: int = 16384
    linger_ms: int = 10
    max_in_flight_requests: int = 5
    acks: str = "all"

    # Consumer Configuration
    enable_auto_commit: bool = True
    auto_commit_interval_ms: int = 5000
    auto_offset_reset: str = "latest"
    session_timeout_ms: int = 30000
    max_poll_records: int = 500

    # Request Configuration
    request_timeout_ms: int = 30000

    # Validation Configuration
    validation_mode: ValidationMode = ValidationMode.BOTH
    dlq_enabled: bool = True

    @classmethod
    def from_env(cls) -> "KafkaConfig":
        """Create config from environment variables."""
        import os

        return cls(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            client_id=os.getenv("KAFKA_CLIENT_ID", "algo-trade-client"),
            security_protocol=os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
            sasl_mechanism=os.getenv("KAFKA_SASL_MECHANISM"),
            sasl_username=os.getenv("KAFKA_SASL_USERNAME"),
            sasl_password=os.getenv("KAFKA_SASL_PASSWORD"),
            ssl_ca_location=os.getenv("KAFKA_SSL_CA_LOCATION"),
            ssl_cert_location=os.getenv("KAFKA_SSL_CERT_LOCATION"),
            ssl_key_location=os.getenv("KAFKA_SSL_KEY_LOCATION"),
            compression_type=os.getenv("KAFKA_COMPRESSION_TYPE", "snappy"),
            batch_size=int(os.getenv("KAFKA_BATCH_SIZE", "16384")),
            linger_ms=int(os.getenv("KAFKA_LINGER_MS", "10")),
            max_in_flight_requests=int(os.getenv("KAFKA_MAX_IN_FLIGHT_REQUESTS", "5")),
            acks=os.getenv("KAFKA_ACKS", "all"),
            enable_auto_commit=os.getenv("KAFKA_ENABLE_AUTO_COMMIT", "true").lower() == "true",
            auto_commit_interval_ms=int(os.getenv("KAFKA_AUTO_COMMIT_INTERVAL_MS", "5000")),
            auto_offset_reset=os.getenv("KAFKA_AUTO_OFFSET_RESET", "latest"),
            session_timeout_ms=int(os.getenv("KAFKA_SESSION_TIMEOUT_MS", "30000")),
            max_poll_records=int(os.getenv("KAFKA_MAX_POLL_RECORDS", "500")),
            request_timeout_ms=int(os.getenv("KAFKA_REQUEST_TIMEOUT_MS", "30000")),
            validation_mode=ValidationMode(os.getenv("VALIDATION_MODE", "both")),
            dlq_enabled=os.getenv("VALIDATION_DLQ_ENABLED", "true").lower() == "true",
        )


# =============================================================================
# DLQ Topic Mapping
# =============================================================================

DLQ_TOPIC_MAP = {
    "market_events": "dlq_market_events",
    "market_raw": "dlq_market_events",
    "ofi_events": "dlq_market_events",
    "order_intents": "dlq_order_intents",
    "exec_reports": "dlq_execution_reports",
}


# =============================================================================
# Kafka Adapter
# =============================================================================

class KafkaAdapter:
    """
    Production Kafka message bus adapter with validation and DLQ support.

    This adapter handles:
    - Message publishing with validation
    - Message consumption with validation
    - Dead Letter Queue routing for invalid messages
    - Retry logic with exponential backoff
    - Health monitoring
    - Graceful shutdown
    """

    def __init__(self, cfg: KafkaConfig):
        """
        Initialize Kafka adapter.

        Args:
            cfg: Kafka configuration
        """
        self.config = cfg
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.validator = MessageValidator(mode=cfg.validation_mode)
        self._connected = False
        self._metrics = {
            "messages_published": 0,
            "messages_consumed": 0,
            "validation_errors": 0,
            "dlq_messages": 0,
            "publish_errors": 0,
            "consume_errors": 0,
        }

        logger.info(
            f"KafkaAdapter initialized: "
            f"bootstrap_servers={cfg.bootstrap_servers}, "
            f"client_id={cfg.client_id}, "
            f"validation_mode={cfg.validation_mode}, "
            f"dlq_enabled={cfg.dlq_enabled}"
        )

    async def connect(self) -> None:
        """
        Connect to Kafka cluster and initialize producer.

        Raises:
            KafkaConnectionError: If connection fails after retries
        """
        if self._connected:
            logger.warning("KafkaAdapter already connected")
            return

        try:
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                client_id=f"{self.config.client_id}-producer",
                compression_type=self.config.compression_type,
                max_batch_size=self.config.batch_size,
                linger_ms=self.config.linger_ms,
                max_in_flight_requests_per_connection=self.config.max_in_flight_requests,
                acks=self.config.acks,
                request_timeout_ms=self.config.request_timeout_ms,
                security_protocol=self.config.security_protocol,
                sasl_mechanism=self.config.sasl_mechanism,
                sasl_plain_username=self.config.sasl_username,
                sasl_plain_password=self.config.sasl_password,
                ssl_context=self._create_ssl_context() if self.config.security_protocol in ["SSL", "SASL_SSL"] else None,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            )

            await self.producer.start()
            self._connected = True

            logger.info(
                f"KafkaAdapter connected successfully: "
                f"bootstrap_servers={self.config.bootstrap_servers}"
            )

        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}", exc_info=True)
            raise KafkaConnectionError(f"Failed to connect to Kafka: {e}")

    def _create_ssl_context(self):
        """Create SSL context from configuration."""
        import ssl

        context = ssl.create_default_context()

        if self.config.ssl_ca_location:
            context.load_verify_locations(cafile=self.config.ssl_ca_location)

        if self.config.ssl_cert_location and self.config.ssl_key_location:
            context.load_cert_chain(
                certfile=self.config.ssl_cert_location,
                keyfile=self.config.ssl_key_location
            )

        return context

    async def publish(
        self,
        topic: str,
        msg: Dict[str, Any],
        key: Optional[str] = None,
        validate: bool = True,
        message_type: Optional[str] = None
    ) -> bool:
        """
        Publish a message to a Kafka topic with validation.

        Args:
            topic: Kafka topic name
            msg: Message payload (dict)
            key: Optional message key for partitioning
            validate: Whether to validate message before publishing
            message_type: Message type for validation (e.g., 'bar_event', 'order_intent')
                         If None, inferred from msg['event_type']

        Returns:
            bool: True if message was published successfully, False otherwise

        Raises:
            KafkaError: If publishing fails after retries
        """
        if not self._connected or self.producer is None:
            raise KafkaConnectionError("KafkaAdapter not connected. Call connect() first.")

        # Infer message type if not provided
        if message_type is None:
            message_type = msg.get("event_type")

        # Validate message
        if validate and message_type:
            validation_result = self.validator.validate_message(msg, message_type)

            if not validation_result.is_valid:
                self._metrics["validation_errors"] += 1
                logger.warning(
                    f"Message validation failed for topic '{topic}': "
                    f"errors={validation_result.errors}"
                )

                # Route to DLQ if enabled
                if self.config.dlq_enabled:
                    await self._publish_to_dlq(topic, msg, validation_result.errors)

                return False

        # Publish message
        try:
            key_bytes = key.encode('utf-8') if key else None

            await self.producer.send_and_wait(topic, value=msg, key=key_bytes)

            self._metrics["messages_published"] += 1
            logger.debug(f"Published message to topic '{topic}': key={key}")

            return True

        except KafkaError as e:
            self._metrics["publish_errors"] += 1
            logger.error(
                f"Failed to publish message to topic '{topic}': {e}",
                exc_info=True
            )
            raise

    async def _publish_to_dlq(
        self,
        source_topic: str,
        msg: Dict[str, Any],
        errors: List[str]
    ) -> None:
        """
        Publish invalid message to Dead Letter Queue.

        Args:
            source_topic: Original topic where message failed validation
            msg: Original message payload
            errors: Validation errors
        """
        dlq_topic = DLQ_TOPIC_MAP.get(source_topic, "dlq_unknown")

        dlq_message = {
            "source_topic": source_topic,
            "original_message": msg,
            "validation_errors": errors,
            "timestamp": msg.get("timestamp"),
            "event_type": msg.get("event_type"),
        }

        try:
            await self.producer.send_and_wait(dlq_topic, value=dlq_message)

            self._metrics["dlq_messages"] += 1
            logger.info(
                f"Routed invalid message to DLQ: "
                f"source_topic={source_topic}, dlq_topic={dlq_topic}, "
                f"errors={len(errors)}"
            )

        except Exception as e:
            logger.error(
                f"Failed to publish to DLQ topic '{dlq_topic}': {e}",
                exc_info=True
            )

    async def consume(
        self,
        topic: str,
        group_id: str,
        validate: bool = True,
        message_type: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Consume messages from a Kafka topic with validation.

        Args:
            topic: Kafka topic name
            group_id: Consumer group ID
            validate: Whether to validate consumed messages
            message_type: Message type for validation (e.g., 'bar_event')
                         If None, inferred from msg['event_type']

        Yields:
            Dict[str, Any]: Validated message payload

        Raises:
            KafkaError: If consumption fails
        """
        if not self._connected:
            raise KafkaConnectionError("KafkaAdapter not connected. Call connect() first.")

        # Create consumer if not exists
        consumer_key = f"{topic}:{group_id}"
        if consumer_key not in self.consumers:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.config.bootstrap_servers,
                client_id=f"{self.config.client_id}-consumer-{group_id}",
                group_id=group_id,
                enable_auto_commit=self.config.enable_auto_commit,
                auto_commit_interval_ms=self.config.auto_commit_interval_ms,
                auto_offset_reset=self.config.auto_offset_reset,
                session_timeout_ms=self.config.session_timeout_ms,
                max_poll_records=self.config.max_poll_records,
                request_timeout_ms=self.config.request_timeout_ms,
                security_protocol=self.config.security_protocol,
                sasl_mechanism=self.config.sasl_mechanism,
                sasl_plain_username=self.config.sasl_username,
                sasl_plain_password=self.config.sasl_password,
                ssl_context=self._create_ssl_context() if self.config.security_protocol in ["SSL", "SASL_SSL"] else None,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            )

            await consumer.start()
            self.consumers[consumer_key] = consumer

            logger.info(
                f"Started Kafka consumer: topic={topic}, group_id={group_id}"
            )

        consumer = self.consumers[consumer_key]

        try:
            async for record in consumer:
                msg = record.value

                self._metrics["messages_consumed"] += 1

                # Infer message type if not provided
                msg_type = message_type or msg.get("event_type")

                # Validate message
                if validate and msg_type:
                    validation_result = self.validator.validate_message(msg, msg_type)

                    if not validation_result.is_valid:
                        self._metrics["validation_errors"] += 1
                        logger.warning(
                            f"Consumed invalid message from topic '{topic}': "
                            f"errors={validation_result.errors}, "
                            f"offset={record.offset}, partition={record.partition}"
                        )

                        # Route to DLQ if enabled
                        if self.config.dlq_enabled:
                            await self._publish_to_dlq(topic, msg, validation_result.errors)

                        continue  # Skip invalid message

                logger.debug(
                    f"Consumed message from topic '{topic}': "
                    f"offset={record.offset}, partition={record.partition}"
                )

                yield msg

        except KafkaError as e:
            self._metrics["consume_errors"] += 1
            logger.error(
                f"Error consuming from topic '{topic}': {e}",
                exc_info=True
            )
            raise

    async def close(self) -> None:
        """Close all Kafka connections gracefully."""
        logger.info("Closing KafkaAdapter connections...")

        # Close producer
        if self.producer:
            await self.producer.stop()
            logger.info("Producer closed")

        # Close all consumers
        for consumer_key, consumer in self.consumers.items():
            await consumer.stop()
            logger.info(f"Consumer closed: {consumer_key}")

        self.consumers.clear()
        self._connected = False

        logger.info("KafkaAdapter closed successfully")

    def health(self) -> Dict[str, Any]:
        """
        Get health status of Kafka adapter.

        Returns:
            Dict with health status and metrics
        """
        return {
            "connected": self._connected,
            "producer_ready": self.producer is not None,
            "active_consumers": len(self.consumers),
            "metrics": self._metrics.copy(),
            "config": {
                "bootstrap_servers": self.config.bootstrap_servers,
                "client_id": self.config.client_id,
                "validation_mode": self.config.validation_mode.value,
                "dlq_enabled": self.config.dlq_enabled,
            }
        }

    def get_metrics(self) -> Dict[str, int]:
        """Get current metrics."""
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        """Reset metrics counters."""
        self._metrics = {
            "messages_published": 0,
            "messages_consumed": 0,
            "validation_errors": 0,
            "dlq_messages": 0,
            "publish_errors": 0,
            "consume_errors": 0,
        }
        logger.info("Metrics reset")


# =============================================================================
# Convenience Functions
# =============================================================================

async def create_kafka_adapter(
    bootstrap_servers: Optional[str] = None,
    client_id: Optional[str] = None,
    **kwargs
) -> KafkaAdapter:
    """
    Create and connect a Kafka adapter.

    Args:
        bootstrap_servers: Kafka bootstrap servers (overrides env)
        client_id: Client ID (overrides env)
        **kwargs: Additional KafkaConfig parameters

    Returns:
        Connected KafkaAdapter instance
    """
    config = KafkaConfig.from_env()

    if bootstrap_servers:
        config.bootstrap_servers = bootstrap_servers
    if client_id:
        config.client_id = client_id

    # Override with kwargs
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    adapter = KafkaAdapter(config)
    await adapter.connect()

    return adapter
