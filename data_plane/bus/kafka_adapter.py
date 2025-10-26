"""
Kafka message bus adapter for Algo-trade.
מתאם Kafka עבור Algo-trade.
"""

import asyncio
import json
from typing import Dict, Any, Optional, AsyncIterator
from uuid import uuid4
import logging

# Try to import aiokafka, fallback to mock for development
try:
    from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
    from aiokafka.errors import KafkaError
    AIOKAFKA_AVAILABLE = True
except ImportError:
    AIOKAFKA_AVAILABLE = False
    logging.warning("aiokafka not available, using mock Kafka adapter")


class KafkaAdapter:
    """
    Async Kafka message bus adapter.
    מתאם Kafka אסינכרוני.

    Supports:
    - Publishing messages to topics
    - Consuming messages from topics
    - Health checks
    - Graceful shutdown
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        Initialize Kafka adapter.

        Args:
            cfg: Configuration dictionary with:
                - bootstrap_servers: Kafka broker list (default: ['localhost:9092'])
                - client_id: Client identifier
                - group_id: Consumer group ID
                - auto_offset_reset: 'earliest' or 'latest'
                - enable_auto_commit: Auto-commit offsets (default: True)
                - value_serializer: Custom serializer (optional)
                - value_deserializer: Custom deserializer (optional)
        """
        self.cfg = cfg
        self.bootstrap_servers = cfg.get('bootstrap_servers', ['localhost:9092'])
        self.client_id = cfg.get('client_id', f'algo_trade_{uuid4().hex[:8]}')
        self.group_id = cfg.get('group_id', 'algo_trade_group')
        self.auto_offset_reset = cfg.get('auto_offset_reset', 'latest')
        self.enable_auto_commit = cfg.get('enable_auto_commit', True)

        # Producer and consumer instances
        self.producer: Optional[Any] = None
        self.consumers: Dict[str, Any] = {}
        self.running = False

        # Use mock mode if aiokafka not available
        self.mock_mode = not AIOKAFKA_AVAILABLE
        if self.mock_mode:
            self._mock_queues: Dict[str, asyncio.Queue] = {}

        # Logger
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start Kafka producer and prepare for consumption."""
        if self.running:
            return

        if self.mock_mode:
            self.logger.info("Starting Kafka adapter in MOCK mode")
            self.running = True
            return

        try:
            # Initialize producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=f"{self.client_id}_producer",
                value_serializer=self._default_serializer,
                compression_type='gzip',
            )
            await self.producer.start()
            self.running = True
            self.logger.info(f"Kafka producer started: {self.bootstrap_servers}")

        except Exception as e:
            self.logger.error(f"Failed to start Kafka adapter: {e}")
            raise

    async def stop(self):
        """Stop producer and all consumers."""
        if not self.running:
            return

        if self.mock_mode:
            self.running = False
            return

        try:
            # Stop all consumers
            for topic, consumer in self.consumers.items():
                await consumer.stop()
                self.logger.info(f"Stopped consumer for topic: {topic}")

            # Stop producer
            if self.producer:
                await self.producer.stop()
                self.logger.info("Kafka producer stopped")

            self.running = False

        except Exception as e:
            self.logger.error(f"Error stopping Kafka adapter: {e}")
            raise

    async def publish(self, topic: str, msg: Dict[str, Any],
                     key: Optional[str] = None,
                     partition: Optional[int] = None):
        """
        Publish a message to a topic.
        פרסום הודעה לנושא.

        Args:
            topic: Topic name
            msg: Message dictionary
            key: Message key (for partitioning)
            partition: Specific partition (optional)
        """
        if not self.running:
            await self.start()

        # Mock mode
        if self.mock_mode:
            if topic not in self._mock_queues:
                self._mock_queues[topic] = asyncio.Queue()
            await self._mock_queues[topic].put(msg)
            self.logger.debug(f"Published to {topic} (mock): {msg.get('type', 'N/A')}")
            return

        # Real Kafka
        try:
            key_bytes = key.encode('utf-8') if key else None
            await self.producer.send_and_wait(
                topic,
                value=msg,
                key=key_bytes,
                partition=partition
            )
            self.logger.debug(f"Published to {topic}: {msg.get('type', 'N/A')}")

        except KafkaError as e:
            self.logger.error(f"Failed to publish to {topic}: {e}")
            raise

    async def consume(self, topic: str,
                     group_id: Optional[str] = None,
                     auto_offset_reset: Optional[str] = None) -> AsyncIterator[Dict[str, Any]]:
        """
        Consume messages from a topic.
        צריכת הודעות מנושא.

        Args:
            topic: Topic name
            group_id: Consumer group (overrides default)
            auto_offset_reset: Offset reset policy (overrides default)

        Yields:
            Message dictionaries
        """
        if not self.running:
            await self.start()

        # Mock mode
        if self.mock_mode:
            if topic not in self._mock_queues:
                self._mock_queues[topic] = asyncio.Queue()

            queue = self._mock_queues[topic]
            while self.running:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                    self.logger.debug(f"Consumed from {topic} (mock): {msg.get('type', 'N/A')}")
                    yield msg
                except asyncio.TimeoutError:
                    continue
            return

        # Real Kafka
        group = group_id or self.group_id
        offset_reset = auto_offset_reset or self.auto_offset_reset

        # Create consumer for this topic
        consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            client_id=f"{self.client_id}_consumer_{topic}",
            group_id=group,
            auto_offset_reset=offset_reset,
            enable_auto_commit=self.enable_auto_commit,
            value_deserializer=self._default_deserializer,
        )

        try:
            await consumer.start()
            self.consumers[topic] = consumer
            self.logger.info(f"Started consumer for topic: {topic}")

            async for record in consumer:
                msg = record.value
                self.logger.debug(f"Consumed from {topic}: {msg.get('type', 'N/A')}")
                yield msg

        except Exception as e:
            self.logger.error(f"Error consuming from {topic}: {e}")
            raise

        finally:
            if topic in self.consumers:
                await self.consumers[topic].stop()
                del self.consumers[topic]

    def health(self) -> Dict[str, Any]:
        """
        Get health status.
        קבלת סטטוס בריאות.

        Returns:
            Health status dictionary
        """
        return {
            "connected": self.running,
            "mode": "mock" if self.mock_mode else "kafka",
            "bootstrap_servers": self.bootstrap_servers,
            "client_id": self.client_id,
            "active_consumers": list(self.consumers.keys()),
            "producer_active": self.producer is not None,
        }

    @staticmethod
    def _default_serializer(msg: Dict[str, Any]) -> bytes:
        """Serialize message to JSON bytes."""
        return json.dumps(msg, default=str).encode('utf-8')

    @staticmethod
    def _default_deserializer(msg_bytes: bytes) -> Dict[str, Any]:
        """Deserialize JSON bytes to message."""
        return json.loads(msg_bytes.decode('utf-8'))


class MockKafkaAdapter(KafkaAdapter):
    """
    Mock Kafka adapter for testing without Kafka infrastructure.
    מתאם Kafka מדומה לבדיקות ללא תשתית Kafka.
    """

    def __init__(self, cfg: Dict[str, Any]):
        """Initialize mock adapter."""
        cfg_copy = cfg.copy()
        super().__init__(cfg_copy)
        self.mock_mode = True
        self._mock_queues: Dict[str, asyncio.Queue] = {}

    async def start(self):
        """Start mock adapter."""
        self.running = True
        self.logger.info("Mock Kafka adapter started")

    async def stop(self):
        """Stop mock adapter."""
        self.running = False
        self.logger.info("Mock Kafka adapter stopped")


# Factory function
def create_kafka_adapter(cfg: Dict[str, Any],
                        mock: bool = False) -> KafkaAdapter:
    """
    Create Kafka adapter instance.
    יצירת instance של מתאם Kafka.

    Args:
        cfg: Configuration dictionary
        mock: Force mock mode (for testing)

    Returns:
        KafkaAdapter instance
    """
    if mock or not AIOKAFKA_AVAILABLE:
        return MockKafkaAdapter(cfg)
    return KafkaAdapter(cfg)


# Example usage
async def example():
    """Example usage of Kafka adapter."""
    # Configuration
    config = {
        'bootstrap_servers': ['localhost:9092'],
        'client_id': 'test_client',
        'group_id': 'test_group',
    }

    # Create adapter (mock mode for demo)
    adapter = create_kafka_adapter(config, mock=True)
    await adapter.start()

    # Publish messages
    await adapter.publish('test_topic', {'type': 'BAR', 'symbol': 'AAPL', 'price': 150.0})
    await adapter.publish('test_topic', {'type': 'BAR', 'symbol': 'TSLA', 'price': 250.0})

    # Consume messages
    async def consumer_task():
        async for msg in adapter.consume('test_topic'):
            print(f"Received: {msg}")
            if msg['symbol'] == 'TSLA':
                break

    # Run consumer
    await consumer_task()

    # Health check
    print("Health:", adapter.health())

    # Stop
    await adapter.stop()


if __name__ == "__main__":
    asyncio.run(example())
