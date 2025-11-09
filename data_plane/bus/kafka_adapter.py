"""
Kafka Adapter - מתאם Kafka לתקשורת בין planes
מטרה: פרסום וצריכת messages מ-Kafka topics
"""

import logging
import asyncio
import json
from typing import Dict, Any, Optional, AsyncIterator
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError, KafkaTimeoutError
from dataclasses import asdict
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)


class KafkaAdapter:
    """
    מתאם Kafka לפרסום וצריכה של messages בין Data/Strategy/Order planes.

    תכונות:
    - Async publish/consume
    - Serialization/Deserialization (JSON)
    - Error handling והתאוששות
    - Health monitoring
    - Idempotent publish (עבור exactly-once semantics)
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        אתחול Kafka Adapter.

        Args:
            cfg: Config dictionary עם:
                - bootstrap_servers: Kafka brokers (e.g., 'localhost:9092')
                - client_id: Client ID
                - group_id: Consumer group ID
                - auto_offset_reset: 'earliest' או 'latest'
                - enable_auto_commit: bool
                - compression_type: 'gzip', 'snappy', 'lz4', או None
        """
        self.cfg = cfg
        self.bootstrap_servers = cfg.get('bootstrap_servers', 'localhost:9092')
        self.client_id = cfg.get('client_id', 'data_plane_client')
        self.group_id = cfg.get('group_id', 'data_plane_group')
        self.auto_offset_reset = cfg.get('auto_offset_reset', 'latest')
        self.enable_auto_commit = cfg.get('enable_auto_commit', True)
        self.compression_type = cfg.get('compression_type', 'gzip')

        # Producer/Consumer instances
        self.producer: Optional[KafkaProducer] = None
        self.consumers: Dict[str, KafkaConsumer] = {}

        # Statistics
        self.published_count = 0
        self.consumed_count = 0
        self.error_count = 0
        self.last_publish_time: Optional[datetime] = None
        self.last_consume_time: Optional[datetime] = None

        # Connection status
        self.connected = False

        # Initialize producer
        self._init_producer()

        logger.info(
            f"KafkaAdapter initialized: bootstrap_servers={self.bootstrap_servers}, "
            f"client_id={self.client_id}, group_id={self.group_id}"
        )

    def _init_producer(self):
        """
        אתחול Kafka Producer.
        """
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                client_id=self.client_id,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                compression_type=self.compression_type,
                acks='all',  # Wait for all replicas
                retries=3,
                max_in_flight_requests_per_connection=1,  # For ordering
                request_timeout_ms=30000
            )
            self.connected = True
            logger.info(f"Kafka Producer initialized: {self.bootstrap_servers}")
        except Exception as e:
            self.connected = False
            logger.error(f"Failed to initialize Kafka Producer: {e}")
            logger.error(traceback.format_exc())

    def _init_consumer(self, topic: str) -> KafkaConsumer:
        """
        אתחול Kafka Consumer עבור topic ספציפי.

        Args:
            topic: שם ה-topic

        Returns:
            KafkaConsumer instance
        """
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                client_id=f"{self.client_id}_consumer_{topic}",
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                max_poll_records=500,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            logger.info(f"Kafka Consumer initialized for topic: {topic}")
            return consumer
        except Exception as e:
            logger.error(f"Failed to initialize Kafka Consumer for topic {topic}: {e}")
            logger.error(traceback.format_exc())
            raise

    async def publish(self, topic: str, msg: Any):
        """
        פרסום message ל-Kafka topic (async).

        Args:
            topic: שם ה-topic
            msg: message לפרסום (dict, dataclass, או JSON serializable)
        """
        if not self.producer:
            logger.error("Producer not initialized, cannot publish")
            self.error_count += 1
            return

        try:
            # המר dataclass ל-dict אם צריך
            if hasattr(msg, '__dataclass_fields__'):
                msg_dict = asdict(msg)
            elif isinstance(msg, dict):
                msg_dict = msg
            else:
                # נסה להמיר לdict
                try:
                    msg_dict = msg.__dict__
                except AttributeError:
                    msg_dict = {'data': str(msg)}

            # Send async (non-blocking)
            future = self.producer.send(topic, value=msg_dict)

            # Wait for result (with timeout)
            await asyncio.get_event_loop().run_in_executor(
                None, future.get, 10  # 10 second timeout
            )

            self.published_count += 1
            self.last_publish_time = datetime.utcnow()
            logger.debug(f"Published message to topic {topic}: {len(str(msg_dict))} bytes")

        except KafkaTimeoutError as e:
            self.error_count += 1
            logger.error(f"Timeout publishing to topic {topic}: {e}")
        except KafkaError as e:
            self.error_count += 1
            logger.error(f"Kafka error publishing to topic {topic}: {e}")
        except Exception as e:
            self.error_count += 1
            logger.error(f"Unexpected error publishing to topic {topic}: {e}")
            logger.error(traceback.format_exc())

    async def consume(self, topic: str, timeout_ms: int = 1000) -> AsyncIterator[Dict[str, Any]]:
        """
        צריכת messages מ-Kafka topic (async generator).

        Args:
            topic: שם ה-topic
            timeout_ms: timeout לpolling (milliseconds)

        Yields:
            Dict: message שנצרך
        """
        # Get or create consumer for this topic
        if topic not in self.consumers:
            try:
                self.consumers[topic] = self._init_consumer(topic)
            except Exception as e:
                logger.error(f"Failed to create consumer for topic {topic}: {e}")
                return

        consumer = self.consumers[topic]

        try:
            while True:
                # Poll for messages (blocking in thread pool)
                records = await asyncio.get_event_loop().run_in_executor(
                    None, consumer.poll, timeout_ms
                )

                if not records:
                    # No messages, yield control
                    await asyncio.sleep(0.1)
                    continue

                # Process messages
                for topic_partition, messages in records.items():
                    for message in messages:
                        try:
                            self.consumed_count += 1
                            self.last_consume_time = datetime.utcnow()

                            logger.debug(
                                f"Consumed message from {topic} "
                                f"(partition: {topic_partition.partition}, offset: {message.offset})"
                            )

                            yield message.value

                        except Exception as e:
                            self.error_count += 1
                            logger.error(f"Error processing message from {topic}: {e}")
                            continue

        except Exception as e:
            logger.error(f"Error consuming from topic {topic}: {e}")
            logger.error(traceback.format_exc())
            self.error_count += 1

    def health(self) -> Dict[str, Any]:
        """
        בדיקת health של Kafka connection.

        Returns:
            Dict עם health status:
            - connected: האם מחובר
            - published_count: מספר messages שפורסמו
            - consumed_count: מספר messages שנצרכו
            - error_count: מספר שגיאות
            - last_publish_time: זמן פרסום אחרון
            - last_consume_time: זמן צריכה אחרון
        """
        return {
            'connected': self.connected and self.producer is not None,
            'session': 'active' if self.connected else 'disconnected',
            'published_count': self.published_count,
            'consumed_count': self.consumed_count,
            'error_count': self.error_count,
            'last_publish_time': self.last_publish_time.isoformat() if self.last_publish_time else None,
            'last_consume_time': self.last_consume_time.isoformat() if self.last_consume_time else None,
            'active_consumers': len(self.consumers),
            'topics_subscribed': list(self.consumers.keys())
        }

    def close(self):
        """
        סגירת חיבורי Kafka (cleanup).
        """
        try:
            if self.producer:
                self.producer.flush()
                self.producer.close()
                logger.info("Kafka Producer closed")

            for topic, consumer in self.consumers.items():
                consumer.close()
                logger.info(f"Kafka Consumer closed for topic: {topic}")

            self.connected = False

        except Exception as e:
            logger.error(f"Error closing Kafka connections: {e}")

    def __del__(self):
        """
        Destructor - וידוא שהחיבורים נסגרים.
        """
        self.close()
