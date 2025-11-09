"""Metrics and performance tracking."""

import time
from contextlib import contextmanager
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Simple metrics collector.

    Tracks:
    - Latency (per phase: tick, signal, order, etc.)
    - Success rate (orders filled vs rejected)
    - Event counts
    """

    def __init__(self):
        self.latencies: Dict[str, list] = {}
        self.counters: Dict[str, int] = {}

    @contextmanager
    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            if operation_name not in self.latencies:
                self.latencies[operation_name] = []
            self.latencies[operation_name].append(elapsed)

    def increment(self, counter_name: str, value: int = 1):
        """Increment a counter."""
        if counter_name not in self.counters:
            self.counters[counter_name] = 0
        self.counters[counter_name] += value

    def get_summary(self) -> dict:
        """Get metrics summary."""
        summary = {
            "latencies": {
                name: {
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }
                for name, values in self.latencies.items()
                if values
            },
            "counters": self.counters
        }
        return summary
