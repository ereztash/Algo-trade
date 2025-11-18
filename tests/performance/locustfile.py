"""
Locust Load Testing for Algo-Trade System
===========================================

Usage:
    # Run locust with web UI
    locust -f tests/performance/locustfile.py --host=http://localhost:8000

    # Run headless with specific load
    locust -f tests/performance/locustfile.py --host=http://localhost:8000 \
           --users 100 --spawn-rate 10 --run-time 5m --headless

    # Run with distributed workers
    locust -f tests/performance/locustfile.py --master
    locust -f tests/performance/locustfile.py --worker --master-host=localhost

Requirements:
    pip install locust>=2.15.0
"""

from locust import HttpUser, task, between, events
import json
import time
from datetime import datetime, timezone


class AlgoTradeUser(HttpUser):
    """
    Simulates a user interacting with the Algo-Trade system.

    This includes:
    - Market data ingestion
    - Strategy signal generation
    - Order placement
    - Position monitoring
    """

    # Wait between 0.1 and 0.5 seconds between tasks
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """Called when a user starts (login, setup, etc.)"""
        self.user_id = f"user_{int(time.time() * 1000)}"
        print(f"User {self.user_id} started")

    @task(5)  # Weight = 5 (runs 5x more often than other tasks)
    def ingest_market_data(self):
        """
        Simulate market data ingestion (most frequent task).

        Tests:
        - Throughput: Can handle 500+ msg/sec?
        - Latency: p95 < 50ms?
        """
        bar_event = {
            "event_type": "bar_event",
            "symbol": "SPY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "open": 450.25,
            "high": 452.80,
            "low": 449.50,
            "close": 451.75,
            "volume": 1000000,
        }

        with self.client.post(
            "/api/v1/data/ingest",
            json=bar_event,
            catch_response=True,
            name="Ingest Market Data",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 503:
                # Service overloaded - mark as failure
                response.failure("Service overloaded (503)")
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    @task(3)  # Weight = 3
    def generate_signal(self):
        """
        Simulate strategy signal generation.

        Tests:
        - Computation time: Can handle complex calculations?
        - Throughput: Signals per second?
        """
        signal_request = {
            "strategy": "OFI",
            "symbols": ["SPY", "QQQ", "IWM"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with self.client.post(
            "/api/v1/strategy/generate_signal",
            json=signal_request,
            catch_response=True,
            name="Generate Signal",
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "signal" in data:
                        response.success()
                    else:
                        response.failure("Missing 'signal' in response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")

    @task(2)  # Weight = 2
    def place_order(self):
        """
        Simulate order placement.

        Tests:
        - Intent-to-ack latency: p95 < 200ms?
        - Order validation speed?
        - Risk check performance?
        """
        order_intent = {
            "symbol": "SPY",
            "direction": "BUY",
            "quantity": 100,
            "order_type": "MARKET",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with self.client.post(
            "/api/v1/orders/place",
            json=order_intent,
            catch_response=True,
            name="Place Order",
        ) as response:
            if response.status_code == 201:
                # Order accepted
                response.success()
            elif response.status_code == 400:
                # Validation error - log but don't fail test
                response.failure("Order validation failed")
            elif response.status_code == 429:
                # Rate limited
                response.failure("Rate limited (429)")

    @task(1)  # Weight = 1 (least frequent)
    def get_positions(self):
        """
        Simulate position query.

        Tests:
        - Read performance
        - Concurrent reads
        """
        with self.client.get(
            "/api/v1/positions",
            catch_response=True,
            name="Get Positions",
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, (list, dict)):
                        response.success()
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")

    @task(1)
    def get_metrics(self):
        """
        Simulate metrics query (Prometheus endpoint).

        Tests:
        - Metrics collection performance
        - Concurrent metrics queries
        """
        self.client.get(
            "/metrics",
            name="Get Metrics",
        )


class KafkaMessageLoadUser(HttpUser):
    """
    Simulates Kafka message load testing.

    Tests the Kafka producer/consumer throughput and latency.
    """

    wait_time = between(0.01, 0.1)  # Very high frequency

    @task
    def publish_kafka_message(self):
        """
        Publish a message to Kafka topic.

        Target: 1000+ msg/sec
        """
        message = {
            "topic": "market_events",
            "key": "SPY",
            "value": {
                "symbol": "SPY",
                "price": 451.25,
                "timestamp": time.time(),
            },
        }

        with self.client.post(
            "/api/v1/kafka/publish",
            json=message,
            catch_response=True,
            name="Publish Kafka Message",
        ) as response:
            if response.status_code == 200:
                response.success()


# Event listeners for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when the test starts."""
    print("=" * 60)
    print("🚀 Algo-Trade Load Test Starting")
    print("=" * 60)
    print(f"Target host: {environment.host}")
    print(f"Number of users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when the test stops - print summary."""
    print("=" * 60)
    print("📊 Algo-Trade Load Test Summary")
    print("=" * 60)

    stats = environment.stats

    print(f"\n📈 Overall Statistics:")
    print(f"  Total Requests: {stats.total.num_requests}")
    print(f"  Total Failures: {stats.total.num_failures}")
    print(f"  Failure Rate: {stats.total.fail_ratio * 100:.2f}%")
    print(f"  RPS: {stats.total.current_rps:.2f}")

    print(f"\n⏱️  Response Times:")
    print(f"  Median: {stats.total.get_response_time_percentile(0.5):.0f} ms")
    print(f"  p95: {stats.total.get_response_time_percentile(0.95):.0f} ms")
    print(f"  p99: {stats.total.get_response_time_percentile(0.99):.0f} ms")
    print(f"  Max: {stats.total.max_response_time:.0f} ms")

    print("\n🎯 Performance Targets:")
    p95 = stats.total.get_response_time_percentile(0.95)
    print(f"  {'✅' if p95 < 200 else '❌'} p95 latency < 200ms: {p95:.0f} ms")
    print(f"  {'✅' if stats.total.current_rps > 500 else '❌'} RPS > 500: {stats.total.current_rps:.2f}")
    print(f"  {'✅' if stats.total.fail_ratio < 0.01 else '❌'} Failure rate < 1%: {stats.total.fail_ratio * 100:.2f}%")

    print("=" * 60)


# Custom test scenarios
class QuickTest(AlgoTradeUser):
    """Quick smoke test - low load, short duration."""
    wait_time = between(1, 2)


class SteadyStateTest(AlgoTradeUser):
    """Steady state test - normal expected load."""
    wait_time = between(0.1, 0.5)


class StressTest(AlgoTradeUser):
    """Stress test - high load to find breaking point."""
    wait_time = between(0.01, 0.05)


class SpikeTest(AlgoTradeUser):
    """Spike test - sudden surge in traffic."""
    wait_time = between(0, 0.01)


# Run configuration examples (can be added to locust.conf or command line):
"""
# Quick Smoke Test (5 users, 1 min)
locust -f locustfile.py --users 5 --spawn-rate 1 --run-time 1m --headless

# Steady State Test (50 users, 10 min)
locust -f locustfile.py --users 50 --spawn-rate 5 --run-time 10m --headless

# Stress Test (200 users, 30 min)
locust -f locustfile.py --users 200 --spawn-rate 20 --run-time 30m --headless

# Spike Test (500 users, 5 min)
locust -f locustfile.py --users 500 --spawn-rate 100 --run-time 5m --headless
"""
