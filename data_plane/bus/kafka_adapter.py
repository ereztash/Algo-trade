"""
Kafka message bus adapter for the 3-plane trading system.

Provides async Kafka producer and consumer using aiokafka.
Handles message serialization, validation, and error handling.
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional, List
from dataclasses import dataclass

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError, KafkaConnectionError

from contracts.schema_validator import MessageValidator, ValidationMode, ValidationResult


logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class KafkaConfig:
    """Kafka configuration."""
    bootstrap_servers: List[str]
    group_id: Optional[str] = None
    auto_offset_reset: str = 'earliest'  # or 'latest'
    enable_auto_commit: bool = True
    max_poll_records: int = 500
    session_timeout_ms: int = 30000
    request_timeout_ms: int = 40000

    # Producer settings
    acks: str = 'all'  # or '0', '1', 'all'
    compression_type: Optional[str] = 'gzip'  # or 'snappy', 'lz4', 'zstd'
    max_request_size: int = 1048576  # 1MB

    # Security (optional)
    security_protocol: str = 'PLAINTEXT'  # or 'SSL', 'SASL_PLAINTEXT', 'SASL_SSL'
    sasl_mechanism: Optional[str] = None  # 'PLAIN', 'SCRAM-SHA-256', etc.
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None


# ============================================================================
# Kafka Adapter
# ============================================================================

class KafkaAdapter:
    """
    Async Kafka message bus adapter.

    Provides:
    - Async message publishing with validation
    - Async message consumption with validation
    - Automatic serialization/deserialization
    - Error handling and retries
    - Health checks
    """

    def __init__(
        self,
        config: Dict[str, Any],
        validator: Optional[MessageValidator] = None,
        validate_on_publish: bool = True,
        validate_on_consume: bool = True,
    ):
        """
        Initialize Kafka adapter.

        Args:
            config: Kafka configuration dictionary
            validator: MessageValidator instance (optional)
            validate_on_publish: Validate messages before publishing
            validate_on_consume: Validate messages after consuming
        """
        # Parse config
        bootstrap_servers = config.get('bootstrap_servers', ['localhost:9092'])
        if isinstance(bootstrap_servers, str):
            bootstrap_servers = [bootstrap_servers]

        self.config = KafkaConfig(
            bootstrap_servers=bootstrap_servers,
            group_id=config.get('group_id'),
            auto_offset_reset=config.get('auto_offset_reset', 'earliest'),
            enable_auto_commit=config.get('enable_auto_commit', True),
            acks=config.get('acks', 'all'),
            compression_type=config.get('compression_type', 'gzip'),
        )

        self.validator = validator or MessageValidator(mode=ValidationMode.PYDANTIC_ONLY)
        self.validate_on_publish = validate_on_publish
        self.validate_on_consume = validate_on_consume

        # Kafka clients (initialized in connect())
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}

        # Connection state
        self.connected = False
        self.producer_started = False

        logger.info(f"Initialized KafkaAdapter with servers: {bootstrap_servers}")

    async def connect(self) -> None:
        """Connect to Kafka and start producer."""
        if self.connected:
            logger.warning("Already connected to Kafka")
            return

        try:
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.bootstrap_servers,
                value_serializer=self._serialize,
                acks=self.config.acks,
                compression_type=self.config.compression_type,
                max_request_size=self.config.max_request_size,
                request_timeout_ms=self.config.request_timeout_ms,
            )

            # Start producer
            await self.producer.start()
            self.producer_started = True
            self.connected = True

            logger.info("Connected to Kafka successfully")
        except KafkaConnectionError as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to Kafka: {e}", exc_info=True)
            raise

    async def disconnect(self) -> None:
        """Disconnect from Kafka and cleanup resources."""
        if not self.connected:
            return

        try:
            # Stop producer
            if self.producer and self.producer_started:
                await self.producer.stop()
                self.producer_started = False

            # Stop all consumers
            for topic, consumer in self.consumers.items():
                try:
                    await consumer.stop()
                    logger.info(f"Stopped consumer for topic: {topic}")
                except Exception as e:
                    logger.error(f"Error stopping consumer for {topic}: {e}")

            self.consumers.clear()
            self.connected = False

            logger.info("Disconnected from Kafka")
        except Exception as e:
            logger.error(f"Error during Kafka disconnect: {e}", exc_info=True)

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        key: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> None:
        """
        Publish a message to a Kafka topic.

        Args:
            topic: Kafka topic name
            message: Message dictionary
            key: Optional message key for partitioning
            validate: Override validate_on_publish setting

        Raises:
            ValueError: If message validation fails
            KafkaError: If publishing fails
        """
        if not self.connected or not self.producer_started:
            raise RuntimeError("Not connected to Kafka. Call connect() first.")

        # Validate message
        should_validate = validate if validate is not None else self.validate_on_publish
        if should_validate:
            event_type = message.get('event_type')
            result = self.validator.validate_message(message, event_type)
            if not result.is_valid:
                error_msg = f"Message validation failed: {result.errors}"
                logger.error(error_msg)
                raise ValueError(error_msg)

        try:
            # Publish to Kafka
            key_bytes = key.encode('utf-8') if key else None
            await self.producer.send(topic, value=message, key=key_bytes)

            logger.debug(f"Published message to topic '{topic}': {message.get('event_type', 'unknown')}")
        except KafkaError as e:
            logger.error(f"Failed to publish to topic '{topic}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error publishing to '{topic}': {e}", exc_info=True)
            raise

    async def consume(
        self,
        topic: str,
        group_id: Optional[str] = None,
        validate: Optional[bool] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Consume messages from a Kafka topic.

        Args:
            topic: Kafka topic name
            group_id: Consumer group ID (uses config default if not provided)
            validate: Override validate_on_consume setting

        Yields:
            Message dictionaries

        Raises:
            ValueError: If message validation fails (in strict mode)
            KafkaError: If consumption fails
        """
        if not self.connected:
            raise RuntimeError("Not connected to Kafka. Call connect() first.")

        # Get or create consumer for this topic
        consumer_key = f"{topic}:{group_id or self.config.group_id}"
        if consumer_key not in self.consumers:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.config.bootstrap_servers,
                group_id=group_id or self.config.group_id,
                value_deserializer=self._deserialize,
                auto_offset_reset=self.config.auto_offset_reset,
                enable_auto_commit=self.config.enable_auto_commit,
                max_poll_records=self.config.max_poll_records,
                session_timeout_ms=self.config.session_timeout_ms,
            )

            await consumer.start()
            self.consumers[consumer_key] = consumer
            logger.info(f"Started consumer for topic '{topic}' with group_id '{group_id or self.config.group_id}'")

        consumer = self.consumers[consumer_key]
        should_validate = validate if validate is not None else self.validate_on_consume

        try:
            async for msg in consumer:
                message = msg.value

                # Validate message
                if should_validate:
                    event_type = message.get('event_type')
                    result = self.validator.validate_message(message, event_type)

                    if not result.is_valid:
                        logger.warning(
                            f"Invalid message from topic '{topic}': {result.errors}. Skipping."
                        )
                        # In production, would route to DLQ here
                        continue

                logger.debug(f"Consumed message from topic '{topic}': {message.get('event_type', 'unknown')}")
                yield message

        except KafkaError as e:
            logger.error(f"Error consuming from topic '{topic}': {e}")
            raise
        except asyncio.CancelledError:
            logger.info(f"Consumer for topic '{topic}' cancelled")
            raise
        except Exception as e:
            logger.error(f"Unexpected error consuming from '{topic}': {e}", exc_info=True)
            raise

    def health(self) -> Dict[str, Any]:
        """
        Get health status of Kafka connection.

        Returns:
            Health status dictionary
        """
        return {
            'connected': self.connected,
            'producer_started': self.producer_started,
            'active_consumers': len(self.consumers),
            'bootstrap_servers': self.config.bootstrap_servers,
        }

    @staticmethod
    def _serialize(value: Dict[str, Any]) -> bytes:
        """
        Serialize message to JSON bytes.

        Args:
            value: Message dictionary

        Returns:
            JSON bytes
        """
        try:
            # Handle datetime objects
            def default_serializer(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            return json.dumps(value, default=default_serializer).encode('utf-8')
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise

    @staticmethod
    def _deserialize(value: bytes) -> Dict[str, Any]:
        """
        Deserialize JSON bytes to message dictionary.

        Args:
            value: JSON bytes

        Returns:
            Message dictionary
        """
        try:
            return json.loads(value.decode('utf-8'))
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            raise


# ============================================================================
# Convenience Functions
# ============================================================================

async def create_kafka_adapter(
    bootstrap_servers: str = 'localhost:9092',
    group_id: Optional[str] = None,
    **kwargs
) -> KafkaAdapter:
    """
    Create and connect a Kafka adapter.

    Args:
        bootstrap_servers: Comma-separated Kafka servers
        group_id: Consumer group ID
        **kwargs: Additional configuration

    Returns:
        Connected KafkaAdapter instance

    Example:
        >>> adapter = await create_kafka_adapter('localhost:9092', group_id='data_plane')
        >>> await adapter.publish('market_events', {'event_type': 'bar_event', ...})
    """
    config = {
        'bootstrap_servers': bootstrap_servers,
        'group_id': group_id,
        **kwargs
    }

    adapter = KafkaAdapter(config)
    await adapter.connect()
    return adapter
