"""
Comprehensive Prometheus Metrics Exporter for Algo-Trade System
Exposes metrics for all planes: Data, Order, and Strategy
"""

from prometheus_client import (
    Counter, Gauge, Histogram, Summary, Info,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
from prometheus_client import make_wsgi_app
from typing import Dict, Any, Optional
import time
import threading
from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Thread per request HTTP server."""
    daemon_threads = True


class MetricsExporter:
    """
    Centralized metrics exporter using Prometheus client.
    Provides counters, gauges, histograms for all system components.
    """

    def __init__(self, registry: Optional[CollectorRegistry] = None, port: int = 8000):
        self.registry = registry or CollectorRegistry()
        self.port = port
        self.server = None
        self._init_metrics()

    def _init_metrics(self):
        """Initialize all Prometheus metrics."""

        # ============ System Info ============
        self.system_info = Info(
            'algo_trade_system',
            'System information',
            registry=self.registry
        )
        self.system_info.info({
            'version': '1.0.0',
            'environment': 'production'
        })

        # ============ Data Plane Metrics ============

        # Market data ingestion
        self.market_ticks_total = Counter(
            'market_ticks_total',
            'Total market data ticks received',
            ['symbol', 'source'],
            registry=self.registry
        )

        self.market_data_errors = Counter(
            'market_data_errors_total',
            'Total market data errors',
            ['symbol', 'error_type'],
            registry=self.registry
        )

        self.market_data_latency = Histogram(
            'market_data_latency_seconds',
            'Market data end-to-end latency',
            ['symbol'],
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
            registry=self.registry
        )

        self.market_data_freshness = Gauge(
            'market_data_freshness_seconds',
            'Age of most recent market data',
            ['symbol'],
            registry=self.registry
        )

        self.data_completeness = Gauge(
            'data_completeness_ratio',
            'Data completeness ratio (0-1)',
            ['symbol', 'timeframe'],
            registry=self.registry
        )

        # NTP drift monitoring
        self.ntp_drift_ms = Gauge(
            'ntp_drift_milliseconds',
            'NTP time drift in milliseconds',
            registry=self.registry
        )

        # Normalization pipeline
        self.normalization_duration = Histogram(
            'normalization_duration_seconds',
            'Time to normalize market data',
            ['normalizer_type'],
            buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1),
            registry=self.registry
        )

        # Storage operations
        self.storage_writes_total = Counter(
            'storage_writes_total',
            'Total storage write operations',
            ['status'],
            registry=self.registry
        )

        self.storage_write_latency = Histogram(
            'storage_write_latency_seconds',
            'Storage write latency',
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
            registry=self.registry
        )

        # ============ Order Plane Metrics ============

        # Order execution
        self.orders_total = Counter(
            'orders_total',
            'Total orders placed',
            ['symbol', 'side', 'order_type'],
            registry=self.registry
        )

        self.order_fills = Counter(
            'order_fills_total',
            'Total order fills',
            ['symbol', 'status'],
            registry=self.registry
        )

        self.order_rejections = Counter(
            'order_rejections_total',
            'Total order rejections',
            ['symbol', 'reason'],
            registry=self.registry
        )

        self.execution_latency = Histogram(
            'execution_latency_seconds',
            'Order execution latency (intent to fill)',
            ['symbol'],
            buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry
        )

        # Risk management
        self.risk_checks_total = Counter(
            'risk_checks_total',
            'Total risk checks performed',
            ['check_type', 'result'],
            registry=self.registry
        )

        self.position_exposure = Gauge(
            'position_exposure_usd',
            'Current position exposure in USD',
            ['symbol', 'exposure_type'],
            registry=self.registry
        )

        # Throttling
        self.throttled_orders = Counter(
            'throttled_orders_total',
            'Orders throttled due to rate limits',
            ['symbol', 'reason'],
            registry=self.registry
        )

        # ============ Strategy Plane Metrics ============

        self.signals_generated = Counter(
            'signals_generated_total',
            'Total trading signals generated',
            ['symbol', 'signal_type'],
            registry=self.registry
        )

        self.strategy_computation_time = Histogram(
            'strategy_computation_seconds',
            'Strategy computation time',
            ['strategy_name'],
            buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
            registry=self.registry
        )

        self.portfolio_value = Gauge(
            'portfolio_value_usd',
            'Current portfolio value in USD',
            registry=self.registry
        )

        self.active_positions = Gauge(
            'active_positions',
            'Number of active positions',
            registry=self.registry
        )

        # ============ Message Bus Metrics ============

        self.messages_published = Counter(
            'messages_published_total',
            'Total messages published to bus',
            ['topic'],
            registry=self.registry
        )

        self.messages_consumed = Counter(
            'messages_consumed_total',
            'Total messages consumed from bus',
            ['topic'],
            registry=self.registry
        )

        self.message_lag = Gauge(
            'message_bus_lag_seconds',
            'Message bus consumer lag',
            ['topic', 'consumer_group'],
            registry=self.registry
        )

        # ============ Health & SLA Metrics ============

        self.service_health = Gauge(
            'service_health',
            'Service health status (1=healthy, 0=unhealthy)',
            ['service'],
            registry=self.registry
        )

        self.sla_compliance = Gauge(
            'sla_compliance_ratio',
            'SLA compliance ratio (0-1)',
            ['sla_metric'],
            registry=self.registry
        )

    # ============ Convenience Methods ============

    def inc(self, metric_name: str, labels: Optional[Dict[str, str]] = None, value: float = 1):
        """Increment a counter metric."""
        metric = getattr(self, metric_name, None)
        if metric is None:
            return

        if labels:
            metric.labels(**labels).inc(value)
        else:
            metric.inc(value)

    def set(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric."""
        metric = getattr(self, metric_name, None)
        if metric is None:
            return

        if labels:
            metric.labels(**labels).set(value)
        else:
            metric.set(value)

    def observe(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a histogram/summary metric."""
        metric = getattr(self, metric_name, None)
        if metric is None:
            return

        if labels:
            metric.labels(**labels).observe(value)
        else:
            metric.observe(value)

    def time_operation(self, metric_name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager to time an operation."""
        return _TimingContext(self, metric_name, labels)

    def start_http_server(self):
        """Start HTTP server to expose metrics on /metrics endpoint."""
        app = make_wsgi_app(self.registry)
        self.server = make_server('0.0.0.0', self.port, app, ThreadingWSGIServer)

        # Run server in background thread
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        print(f"✓ Metrics server started on http://0.0.0.0:{self.port}/metrics")

    def stop_http_server(self):
        """Stop the HTTP metrics server."""
        if self.server:
            self.server.shutdown()
            self.server = None

    def get_metrics_text(self) -> bytes:
        """Get current metrics in Prometheus text format."""
        return generate_latest(self.registry)


class _TimingContext:
    """Context manager for timing operations."""

    def __init__(self, exporter: MetricsExporter, metric_name: str, labels: Optional[Dict[str, str]] = None):
        self.exporter = exporter
        self.metric_name = metric_name
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.exporter.observe(self.metric_name, duration, self.labels)


# Global singleton instance
_metrics_instance: Optional[MetricsExporter] = None


def init_metrics_exporter(port: int = 8000, start_server: bool = True) -> MetricsExporter:
    """
    Initialize the global metrics exporter instance.

    Args:
        port: HTTP port for metrics endpoint
        start_server: Whether to start HTTP server immediately

    Returns:
        MetricsExporter instance
    """
    global _metrics_instance

    if _metrics_instance is None:
        _metrics_instance = MetricsExporter(port=port)
        if start_server:
            _metrics_instance.start_http_server()

    return _metrics_instance


def get_metrics() -> Optional[MetricsExporter]:
    """Get the global metrics exporter instance."""
    return _metrics_instance
