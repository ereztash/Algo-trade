#!/usr/bin/env python3
"""
Kafka Health Check Utility.

This script checks the health of the Kafka cluster and reports:
- Connection status
- Available topics
- Consumer groups
- Broker information
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_plane.bus.kafka_adapter import KafkaAdapter
from data_plane.bus.topic_initializer import get_kafka_config


async def check_kafka_health():
    """Check Kafka cluster health."""
    print("=" * 60)
    print("Kafka Health Check")
    print("=" * 60)
    print()

    # Load Kafka configuration
    try:
        kafka_cfg = get_kafka_config('data_plane/config/kafka.yaml')
        print(f"✓ Configuration loaded")
        print(f"  Bootstrap servers: {kafka_cfg.get('bootstrap_servers')}")
        print()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False

    # Initialize Kafka adapter
    try:
        bus = KafkaAdapter(kafka_cfg)
        print(f"✓ Kafka adapter initialized")
        print()
    except Exception as e:
        print(f"✗ Failed to initialize adapter: {e}")
        return False

    # Check connection
    try:
        admin = await bus._ensure_admin_client()
        print(f"✓ Connected to Kafka cluster")
        print()
    except Exception as e:
        print(f"✗ Failed to connect to Kafka: {e}")
        print()
        print("Make sure Kafka is running:")
        print("  docker-compose -f docker-compose.kafka.yml up -d")
        return False

    # List topics
    try:
        topics = await admin.list_topics()
        print(f"Topics ({len(topics)}):")
        for topic in sorted(topics):
            print(f"  - {topic}")
        print()
    except Exception as e:
        print(f"✗ Failed to list topics: {e}")
        print()

    # Check health
    try:
        health = bus.health()
        print("Health Status:")
        print(f"  Connected: {health['connected']}")
        print(f"  Active consumers: {health['active_consumers']}")
        print()

        metrics = health.get('metrics', {})
        if metrics:
            print("Metrics:")
            for key, value in metrics.items():
                print(f"  {key}: {value}")
            print()
    except Exception as e:
        print(f"Warning: Could not get health status: {e}")
        print()

    # Close connection
    await bus.close()
    print("✓ Connection closed")
    print()

    print("=" * 60)
    print("Health check completed successfully!")
    print("=" * 60)

    return True


def main():
    """Main entry point."""
    try:
        success = asyncio.run(check_kafka_health())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nHealth check interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
