"""
Kafka Message Bus Adapter - Full async implementation.

This module provides a complete Kafka producer/consumer implementation for the
3-plane architecture with:
- Async producers and consumers using aiokafka
- Message validation integration
- Dead Letter Queue (DLQ) support
- Metrics and monitoring
- Connection pooling and error handling
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncIterator, Callable
from datetime import datetime
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError
from aiokafka.admin import AIOKafkaAdminClient, NewTopic


logger = logging.getLogger(__name__)


class KafkaAdapter:
    """
    Async Kafka adapter for producing and consuming messages.

    Features:
    - Async producer/consumer with connection pooling
    - Automatic topic creation
    - Message serialization (JSON)
    - Error handling and retries
    - Dead Letter Queue support
    - Metrics tracking
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Kafka adapter.

        Args:
            config: Kafka configuration with keys:
                - bootstrap_servers: Kafka broker addresses (default: localhost:9092)
                - group_id: Consumer group ID
                - auto_offset_reset: 'earliest' or 'latest'
                - enable_auto_commit: Auto-commit offsets (default: True)
                - max_poll_records: Max records per poll (default: 500)
        """
        self.config = config or {}
        self.bootstrap_servers = self.config.get('bootstrap_servers', 'localhost:9092')
        self.group_id = self.config.get('group_id', 'algo-trade-default')
        self.auto_offset_reset = self.config.get('auto_offset_reset', 'earliest')
        self.enable_auto_commit = self.config.get('enable_auto_commit', True)
        self.max_poll_records = self.config.get('max_poll_records', 500)

        # Producer/consumer instances (lazy initialization)
        self._producer: Optional[AIOKafkaProducer] = None
        self._consumers: Dict[str, AIOKafkaConsumer] = {}
        self._admin_client: Optional[AIOKafkaAdminClient] = None

        # Metrics
        self._metrics = {
            'messages_produced': 0,
            'messages_consumed': 0,
            'produce_errors': 0,
            'consume_errors': 0,
            'dlq_messages': 0,
        }

        # Connection state
        self._connected = False
        self._lock = asyncio.Lock()

        logger.info(f"KafkaAdapter initialized with brokers: {self.bootstrap_servers}")

    async def _ensure_producer(self) -> AIOKafkaProducer:
        """Ensure producer is created and started."""
        if self._producer is None:
            async with self._lock:
                if self._producer is None:
                    self._producer = AIOKafkaProducer(
                        bootstrap_servers=self.bootstrap_servers,
                        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                        key_serializer=lambda k: k.encode('utf-8') if k else None,
                        compression_type='gzip',
                        acks='all',  # Wait for all replicas
                        retries=3,
                        max_in_flight_requests_per_connection=5,
                    )
                    await self._producer.start()
                    self._connected = True
                    logger.info("Kafka producer started")
        return self._producer

    async def _ensure_admin_client(self) -> AIOKafkaAdminClient:
        """Ensure admin client is created."""
        if self._admin_client is None:
            async with self._lock:
                if self._admin_client is None:
                    self._admin_client = AIOKafkaAdminClient(
                        bootstrap_servers=self.bootstrap_servers
                    )
                    await self._admin_client.start()
                    logger.info("Kafka admin client started")
        return self._admin_client

    async def create_topics(self, topics_config: Dict[str, Dict[str, Any]]):
        """
        Create Kafka topics based on configuration.

        Args:
            topics_config: Dictionary with topic names and their configuration:
                {
                    'market_events': {'retention': '24h', 'partitions': 3},
                    'order_intents': {'retention': '6h', 'acks': 'all'},
                }
        """
        admin = await self._ensure_admin_client()

        # Get existing topics
        existing_topics = await admin.list_topics()

        # Create new topics
        new_topics = []
        for topic_name, topic_config in topics_config.items():
            if topic_name not in existing_topics:
                # Parse retention period (e.g., '24h' -> milliseconds)
                retention = topic_config.get('retention', '24h')
                retention_ms = self._parse_retention(retention)

                num_partitions = topic_config.get('partitions', 3)
                replication_factor = topic_config.get('replication_factor', 1)

                new_topic = NewTopic(
                    name=topic_name,
                    num_partitions=num_partitions,
                    replication_factor=replication_factor,
                    topic_configs={
                        'retention.ms': str(retention_ms),
                        'compression.type': 'gzip',
                    }
                )
                new_topics.append(new_topic)
                logger.info(f"Creating topic: {topic_name} (retention={retention}, partitions={num_partitions})")

        if new_topics:
            try:
                await admin.create_topics(new_topics, validate_only=False)
                logger.info(f"Created {len(new_topics)} topics")
            except Exception as e:
                logger.warning(f"Error creating topics (may already exist): {e}")

    @staticmethod
    def _parse_retention(retention_str: str) -> int:
        """Parse retention string to milliseconds (e.g., '24h' -> 86400000)."""
        unit = retention_str[-1]
        value = int(retention_str[:-1])

        if unit == 'h':
            return value * 60 * 60 * 1000
        elif unit == 'd':
            return value * 24 * 60 * 60 * 1000
        elif unit == 'm':
            return value * 60 * 1000
        else:
            raise ValueError(f"Unknown retention unit: {unit}")

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Publish a message to a Kafka topic.

        Args:
            topic: Kafka topic name
            message: Message payload (will be JSON serialized)
            key: Optional message key for partitioning
            headers: Optional message headers
        """
        producer = await self._ensure_producer()

        try:
            # Add timestamp if not present
            if 'timestamp' not in message:
                message['timestamp'] = datetime.utcnow().isoformat()

            # Convert headers to bytes
            kafka_headers = None
            if headers:
                kafka_headers = [(k, v.encode('utf-8')) for k, v in headers.items()]

            # Send message
            await producer.send_and_wait(
                topic=topic,
                value=message,
                key=key,
                headers=kafka_headers
            )

            self._metrics['messages_produced'] += 1
            logger.debug(f"Published message to {topic}: {message.get('event_type', 'unknown')}")

        except KafkaError as e:
            self._metrics['produce_errors'] += 1
            logger.error(f"Failed to publish to {topic}: {e}")
            raise

    async def publish_to_dlq(
        self,
        original_topic: str,
        message: Dict[str, Any],
        error: str,
        validation_errors: Optional[list] = None
    ):
        """
        Publish a failed message to the Dead Letter Queue.

        Args:
            original_topic: Original topic name
            message: Failed message
            error: Error description
            validation_errors: Optional validation error details
        """
        dlq_topic = f"dlq_{original_topic}"
        dlq_message = {
            'original_topic': original_topic,
            'original_message': message,
            'error': error,
            'validation_errors': validation_errors or [],
            'dlq_timestamp': datetime.utcnow().isoformat(),
        }

        try:
            await self.publish(dlq_topic, dlq_message)
            self._metrics['dlq_messages'] += 1
            logger.warning(f"Message sent to DLQ: {dlq_topic}")
        except Exception as e:
            logger.error(f"Failed to publish to DLQ {dlq_topic}: {e}")

    async def consume(
        self,
        topic: str,
        group_id: Optional[str] = None,
        auto_offset_reset: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Consume messages from a Kafka topic.

        Args:
            topic: Kafka topic name
            group_id: Consumer group ID (overrides default)
            auto_offset_reset: Offset reset policy (overrides default)

        Yields:
            Deserialized message payloads
        """
        # Create consumer for this topic if not exists
        consumer_key = f"{topic}:{group_id or self.group_id}"

        if consumer_key not in self._consumers:
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id or self.group_id,
                auto_offset_reset=auto_offset_reset or self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                max_poll_records=self.max_poll_records,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                key_deserializer=lambda k: k.decode('utf-8') if k else None,
            )

            await consumer.start()
            self._consumers[consumer_key] = consumer
            logger.info(f"Started consumer for topic: {topic} (group: {group_id or self.group_id})")

        consumer = self._consumers[consumer_key]

        try:
            async for msg in consumer:
                try:
                    self._metrics['messages_consumed'] += 1
                    logger.debug(f"Consumed message from {topic}: offset={msg.offset}")
                    yield msg.value

                except json.JSONDecodeError as e:
                    self._metrics['consume_errors'] += 1
                    logger.error(f"Failed to decode message from {topic}: {e}")
                    continue

        except Exception as e:
            self._metrics['consume_errors'] += 1
            logger.error(f"Error consuming from {topic}: {e}")
            raise

    async def consume_with_validator(
        self,
        topic: str,
        validator: Callable[[Dict[str, Any]], Any],
        group_id: Optional[str] = None
    ) -> AsyncIterator[Any]:
        """
        Consume messages with automatic validation.

        Args:
            topic: Kafka topic name
            validator: Validation function that returns ValidationResult
            group_id: Consumer group ID (overrides default)

        Yields:
            Validated message objects (only valid messages)
        """
        async for message in self.consume(topic, group_id):
            result = validator(message)

            if result.is_valid:
                yield result.validated_data
            else:
                # Send to DLQ
                await self.publish_to_dlq(
                    original_topic=topic,
                    message=message,
                    error="Validation failed",
                    validation_errors=result.errors
                )

    def health(self) -> Dict[str, Any]:
        """
        Get health status of the Kafka adapter.

        Returns:
            Health status dictionary
        """
        return {
            'connected': self._connected,
            'bootstrap_servers': self.bootstrap_servers,
            'active_consumers': len(self._consumers),
            'metrics': self._metrics.copy(),
        }

    def get_metrics(self) -> Dict[str, int]:
        """Get current metrics."""
        return self._metrics.copy()

    async def close(self):
        """Close all Kafka connections."""
        logger.info("Closing Kafka adapter...")

        # Close producer
        if self._producer:
            await self._producer.stop()
            logger.info("Producer stopped")

        # Close all consumers
        for consumer_key, consumer in self._consumers.items():
            await consumer.stop()
            logger.info(f"Consumer stopped: {consumer_key}")

        # Close admin client
        if self._admin_client:
            await self._admin_client.close()
            logger.info("Admin client closed")

        self._connected = False
        logger.info("Kafka adapter closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
