"""
Kafka Topic Initializer.

This module handles automatic creation and configuration of Kafka topics
based on the topics.yaml configuration file.
"""

import logging
from typing import Dict, Any
from data_plane.config.utils import load_yaml


logger = logging.getLogger(__name__)


async def initialize_kafka_topics(kafka_adapter, config_path: str = 'data_plane/config/kafka.yaml'):
    """
    Initialize Kafka topics based on configuration.

    This function:
    1. Loads topic configuration from YAML
    2. Creates main topics (market_raw, market_events, etc.)
    3. Creates DLQ topics
    4. Logs creation status

    Args:
        kafka_adapter: KafkaAdapter instance
        config_path: Path to Kafka configuration YAML file
    """
    logger.info("Initializing Kafka topics...")

    # Load Kafka configuration
    config = load_yaml(config_path)
    topics_config = config.get('topics', {})
    dlq_topics_config = config.get('dlq_topics', {})

    # Merge main topics and DLQ topics
    all_topics = {**topics_config, **dlq_topics_config}

    # Create topics
    await kafka_adapter.create_topics(all_topics)

    logger.info(f"Kafka topics initialized: {len(all_topics)} topics configured")

    return all_topics


def get_topic_config(topic_name: str, config_path: str = 'data_plane/config/kafka.yaml') -> Dict[str, Any]:
    """
    Get configuration for a specific topic.

    Args:
        topic_name: Name of the topic
        config_path: Path to Kafka configuration YAML file

    Returns:
        Topic configuration dictionary
    """
    config = load_yaml(config_path)
    topics_config = config.get('topics', {})
    dlq_topics_config = config.get('dlq_topics', {})

    all_topics = {**topics_config, **dlq_topics_config}

    return all_topics.get(topic_name, {})


def get_kafka_config(config_path: str = 'data_plane/config/kafka.yaml') -> Dict[str, Any]:
    """
    Get Kafka connection configuration.

    Args:
        config_path: Path to Kafka configuration YAML file

    Returns:
        Kafka configuration dictionary
    """
    config = load_yaml(config_path)
    return config.get('kafka', {})
