"""
Performance monitoring and metrics collection.

Provides comprehensive latency tracking, throughput metrics, and
performance monitoring for the trading system with <200ms target.
"""
import time
import asyncio
from typing import Dict, Any, Optional, List
from collections import deque, defaultdict
from dataclasses import dataclass, field
import statistics


@dataclass
class LatencyMetrics:
    """Track latency statistics with percentiles."""
    measurements: deque = field(default_factory=lambda: deque(maxlen=10000))

    def record(self, latency_ms: float):
        """Record a latency measurement."""
        self.measurements.append(latency_ms)

    def get_stats(self) -> Dict[str, float]:
        """Get percentile statistics."""
        if not self.measurements:
            return {}

        sorted_vals = sorted(self.measurements)
        n = len(sorted_vals)

        return {
            'count': n,
            'mean': statistics.mean(sorted_vals),
            'median': statistics.median(sorted_vals),
            'p50': sorted_vals[int(n * 0.50)] if n > 0 else 0,
            'p95': sorted_vals[int(n * 0.95)] if n > 0 else 0,
            'p99': sorted_vals[int(n * 0.99)] if n > 0 else 0,
            'min': min(sorted_vals),
            'max': max(sorted_vals)
        }


@dataclass
class ThroughputMetrics:
    """Track throughput and rate metrics."""
    count: int = 0
    start_time: float = field(default_factory=time.time)
    last_reset: float = field(default_factory=time.time)

    def increment(self, amount: int = 1):
        """Increment counter."""
        self.count += amount

    def get_rate(self) -> float:
        """Get events per second since last reset."""
        elapsed = time.time() - self.last_reset
        if elapsed == 0:
            return 0.0
        return self.count / elapsed

    def reset(self):
        """Reset counter and timer."""
        self.count = 0
        self.last_reset = time.time()


class PerformanceMonitor:
    """
    Comprehensive performance monitoring for trading system.

    Tracks:
    - End-to-end latency (intent → execution)
    - Per-component latency breakdown
    - Throughput metrics
    - Error rates
    - SLA violations (<200ms target)
    """

    def __init__(self, sla_target_ms: float = 200.0):
        self.sla_target_ms = sla_target_ms

        # Latency tracking
        self.latencies: Dict[str, LatencyMetrics] = defaultdict(LatencyMetrics)

        # Throughput tracking
        self.throughput: Dict[str, ThroughputMetrics] = defaultdict(ThroughputMetrics)

        # Error tracking
        self.errors: Dict[str, int] = defaultdict(int)

        # SLA violations
        self.sla_violations: int = 0
        self.total_measurements: int = 0

        # In-flight tracking for end-to-end latency
        self.in_flight: Dict[str, float] = {}  # order_id -> start_time

    def start_timer(self, operation_id: str) -> float:
        """Start timing an operation. Returns start timestamp."""
        start_time = time.time() * 1000  # Convert to milliseconds
        self.in_flight[operation_id] = start_time
        return start_time

    def end_timer(self, operation_id: str, metric_name: str) -> Optional[float]:
        """
        End timing an operation and record latency.
        Returns latency in ms if operation was found, None otherwise.
        """
        if operation_id not in self.in_flight:
            return None

        end_time = time.time() * 1000
        latency_ms = end_time - self.in_flight[operation_id]

        # Record latency
        self.latencies[metric_name].record(latency_ms)

        # Track SLA violations
        self.total_measurements += 1
        if latency_ms > self.sla_target_ms:
            self.sla_violations += 1

        # Cleanup
        del self.in_flight[operation_id]

        return latency_ms

    def record_latency(self, metric_name: str, latency_ms: float):
        """Record a latency measurement directly."""
        self.latencies[metric_name].record(latency_ms)

        # Track SLA violations for end-to-end metrics
        if 'end_to_end' in metric_name or 'total' in metric_name:
            self.total_measurements += 1
            if latency_ms > self.sla_target_ms:
                self.sla_violations += 1

    def increment(self, metric_name: str, amount: int = 1):
        """Increment a counter metric."""
        self.throughput[metric_name].increment(amount)

    def record_error(self, error_type: str):
        """Record an error."""
        self.errors[error_type] += 1

    def get_sla_compliance_rate(self) -> float:
        """Get percentage of operations meeting SLA target."""
        if self.total_measurements == 0:
            return 100.0
        return 100.0 * (1 - self.sla_violations / self.total_measurements)

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        metrics = {
            'sla_target_ms': self.sla_target_ms,
            'sla_compliance_rate': self.get_sla_compliance_rate(),
            'sla_violations': self.sla_violations,
            'total_measurements': self.total_measurements,
            'latencies': {},
            'throughput': {},
            'errors': dict(self.errors),
            'in_flight_count': len(self.in_flight)
        }

        # Add latency stats
        for name, latency_tracker in self.latencies.items():
            metrics['latencies'][name] = latency_tracker.get_stats()

        # Add throughput stats
        for name, throughput_tracker in self.throughput.items():
            metrics['throughput'][name] = {
                'count': throughput_tracker.count,
                'rate_per_sec': throughput_tracker.get_rate()
            }

        return metrics

    def print_summary(self):
        """Print a human-readable summary of metrics."""
        metrics = self.get_metrics()

        print("\n" + "="*80)
        print("PERFORMANCE METRICS SUMMARY")
        print("="*80)

        print(f"\nSLA Target: {self.sla_target_ms}ms")
        print(f"SLA Compliance Rate: {metrics['sla_compliance_rate']:.2f}%")
        print(f"SLA Violations: {metrics['sla_violations']} / {metrics['total_measurements']}")

        print("\n" + "-"*80)
        print("LATENCY METRICS (ms)")
        print("-"*80)
        for name, stats in metrics['latencies'].items():
            if stats:
                print(f"\n{name}:")
                print(f"  Count: {stats['count']}")
                print(f"  Mean:   {stats['mean']:.2f}ms")
                print(f"  Median: {stats['median']:.2f}ms")
                print(f"  P95:    {stats['p95']:.2f}ms")
                print(f"  P99:    {stats['p99']:.2f}ms")
                print(f"  Min:    {stats['min']:.2f}ms")
                print(f"  Max:    {stats['max']:.2f}ms")

        print("\n" + "-"*80)
        print("THROUGHPUT METRICS")
        print("-"*80)
        for name, stats in metrics['throughput'].items():
            print(f"{name}: {stats['count']} events ({stats['rate_per_sec']:.2f}/sec)")

        if metrics['errors']:
            print("\n" + "-"*80)
            print("ERROR METRICS")
            print("-"*80)
            for error_type, count in metrics['errors'].items():
                print(f"{error_type}: {count}")

        print("\n" + "="*80 + "\n")


def init_metrics_exporter(sla_target_ms: float = 200.0) -> PerformanceMonitor:
    """
    Initialize performance monitoring system.

    Args:
        sla_target_ms: Target latency in milliseconds (default: 200ms)

    Returns:
        PerformanceMonitor instance for tracking metrics
    """
    return PerformanceMonitor(sla_target_ms=sla_target_ms)
