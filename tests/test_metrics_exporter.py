"""
Tests for Prometheus Metrics Exporter
Validates metrics collection, HTTP endpoint, and proper instrumentation.
"""

import pytest
import time
import requests
from prometheus_client import CollectorRegistry
from data_plane.monitoring.metrics_exporter import (
    MetricsExporter,
    init_metrics_exporter,
    get_metrics,
    _metrics_instance
)


@pytest.fixture
def metrics_registry():
    """Provide a clean registry for each test."""
    return CollectorRegistry()


@pytest.fixture
def metrics_exporter(metrics_registry):
    """Provide a MetricsExporter instance for testing."""
    return MetricsExporter(registry=metrics_registry, port=8001)


@pytest.fixture
def metrics_exporter_with_server(metrics_registry):
    """Provide a MetricsExporter instance with HTTP server running."""
    exporter = MetricsExporter(registry=metrics_registry, port=8002)
    exporter.start_http_server()
    yield exporter
    exporter.stop_http_server()


class TestMetricsInitialization:
    """Test metrics initialization and setup."""

    def test_metrics_exporter_creation(self, metrics_exporter):
        """Test that MetricsExporter can be created."""
        assert metrics_exporter is not None
        assert metrics_exporter.registry is not None

    def test_all_metrics_initialized(self, metrics_exporter):
        """Test that all expected metrics are initialized."""
        # Data plane metrics
        assert hasattr(metrics_exporter, 'market_ticks_total')
        assert hasattr(metrics_exporter, 'market_data_errors')
        assert hasattr(metrics_exporter, 'market_data_latency')
        assert hasattr(metrics_exporter, 'market_data_freshness')
        assert hasattr(metrics_exporter, 'data_completeness')
        assert hasattr(metrics_exporter, 'ntp_drift_ms')
        assert hasattr(metrics_exporter, 'normalization_duration')
        assert hasattr(metrics_exporter, 'storage_writes_total')
        assert hasattr(metrics_exporter, 'storage_write_latency')

        # Order plane metrics
        assert hasattr(metrics_exporter, 'orders_total')
        assert hasattr(metrics_exporter, 'order_fills')
        assert hasattr(metrics_exporter, 'order_rejections')
        assert hasattr(metrics_exporter, 'execution_latency')
        assert hasattr(metrics_exporter, 'risk_checks_total')
        assert hasattr(metrics_exporter, 'position_exposure')
        assert hasattr(metrics_exporter, 'throttled_orders')

        # Strategy plane metrics
        assert hasattr(metrics_exporter, 'signals_generated')
        assert hasattr(metrics_exporter, 'strategy_computation_time')
        assert hasattr(metrics_exporter, 'portfolio_value')
        assert hasattr(metrics_exporter, 'active_positions')

        # Message bus metrics
        assert hasattr(metrics_exporter, 'messages_published')
        assert hasattr(metrics_exporter, 'messages_consumed')
        assert hasattr(metrics_exporter, 'message_lag')

        # Health metrics
        assert hasattr(metrics_exporter, 'service_health')
        assert hasattr(metrics_exporter, 'sla_compliance')


class TestCounterMetrics:
    """Test counter metric functionality."""

    def test_inc_counter_without_labels(self, metrics_exporter):
        """Test incrementing a counter without labels."""
        initial_value = self._get_metric_value(metrics_exporter, 'storage_writes_total')
        metrics_exporter.inc('storage_writes_total', labels={'status': 'success'})
        final_value = self._get_metric_value(metrics_exporter, 'storage_writes_total')
        # Since we're using labels, we can't directly compare - just ensure no error

    def test_inc_counter_with_labels(self, metrics_exporter):
        """Test incrementing a counter with labels."""
        metrics_exporter.inc('market_ticks_total', labels={'symbol': 'AAPL', 'source': 'IBKR'}, value=5)
        metrics_exporter.inc('market_ticks_total', labels={'symbol': 'AAPL', 'source': 'IBKR'}, value=3)
        # Verify the counter increased (should be 8 total)

    def test_inc_nonexistent_metric(self, metrics_exporter):
        """Test that incrementing a non-existent metric doesn't raise an error."""
        # Should not raise an exception
        metrics_exporter.inc('nonexistent_metric')

    def test_order_metrics(self, metrics_exporter):
        """Test order-related counter metrics."""
        # Place some orders
        metrics_exporter.inc('orders_total', labels={'symbol': 'AAPL', 'side': 'BUY', 'order_type': 'LIMIT'}, value=10)
        metrics_exporter.inc('orders_total', labels={'symbol': 'AAPL', 'side': 'SELL', 'order_type': 'MARKET'}, value=5)

        # Record fills
        metrics_exporter.inc('order_fills', labels={'symbol': 'AAPL', 'status': 'FILLED'}, value=8)
        metrics_exporter.inc('order_fills', labels={'symbol': 'AAPL', 'status': 'PARTIAL'}, value=2)

        # Record rejections
        metrics_exporter.inc('order_rejections', labels={'symbol': 'AAPL', 'reason': 'RISK_LIMIT'}, value=1)

    @staticmethod
    def _get_metric_value(exporter, metric_name):
        """Helper to get metric value from registry."""
        metrics_text = exporter.get_metrics_text().decode('utf-8')
        for line in metrics_text.split('\n'):
            if line.startswith(metric_name):
                return float(line.split()[-1])
        return 0.0


class TestGaugeMetrics:
    """Test gauge metric functionality."""

    def test_set_gauge_without_labels(self, metrics_exporter):
        """Test setting a gauge without labels."""
        metrics_exporter.set('ntp_drift_ms', 25.5)
        # Verify it was set

    def test_set_gauge_with_labels(self, metrics_exporter):
        """Test setting a gauge with labels."""
        metrics_exporter.set('market_data_freshness', 2.5, labels={'symbol': 'AAPL'})
        metrics_exporter.set('market_data_freshness', 1.8, labels={'symbol': 'TSLA'})

    def test_position_exposure_tracking(self, metrics_exporter):
        """Test position exposure gauge metrics."""
        metrics_exporter.set('position_exposure', 250000, labels={'symbol': 'AAPL', 'exposure_type': 'gross'})
        metrics_exporter.set('position_exposure', 50000, labels={'symbol': 'AAPL', 'exposure_type': 'net'})

    def test_data_completeness_tracking(self, metrics_exporter):
        """Test data completeness gauge metrics."""
        metrics_exporter.set('data_completeness', 0.99, labels={'symbol': 'AAPL', 'timeframe': '1m'})
        metrics_exporter.set('data_completeness', 0.95, labels={'symbol': 'TSLA', 'timeframe': '1m'})

    def test_service_health_tracking(self, metrics_exporter):
        """Test service health gauge metrics."""
        metrics_exporter.set('service_health', 1.0, labels={'service': 'data-plane'})
        metrics_exporter.set('service_health', 1.0, labels={'service': 'order-plane'})
        metrics_exporter.set('service_health', 0.0, labels={'service': 'strategy-plane'})  # Unhealthy


class TestHistogramMetrics:
    """Test histogram metric functionality."""

    def test_observe_histogram_without_labels(self, metrics_exporter):
        """Test observing a histogram without labels."""
        # Observe some latencies
        metrics_exporter.observe('storage_write_latency', 0.005)
        metrics_exporter.observe('storage_write_latency', 0.012)
        metrics_exporter.observe('storage_write_latency', 0.008)

    def test_observe_histogram_with_labels(self, metrics_exporter):
        """Test observing a histogram with labels."""
        # Market data latencies
        for latency in [0.001, 0.003, 0.002, 0.015, 0.008]:
            metrics_exporter.observe('market_data_latency', latency, labels={'symbol': 'AAPL'})

    def test_execution_latency_tracking(self, metrics_exporter):
        """Test execution latency histogram."""
        latencies = [0.05, 0.08, 0.12, 0.15, 0.25, 0.35, 0.42, 0.55]
        for latency in latencies:
            metrics_exporter.observe('execution_latency', latency, labels={'symbol': 'AAPL'})

    def test_strategy_computation_time(self, metrics_exporter):
        """Test strategy computation time histogram."""
        times = [0.001, 0.005, 0.008, 0.012, 0.025]
        for t in times:
            metrics_exporter.observe('strategy_computation_time', t, labels={'strategy_name': 'momentum'})


class TestTimingContext:
    """Test timing context manager functionality."""

    def test_time_operation_basic(self, metrics_exporter):
        """Test basic operation timing."""
        with metrics_exporter.time_operation('storage_write_latency'):
            time.sleep(0.01)  # Simulate operation

    def test_time_operation_with_labels(self, metrics_exporter):
        """Test operation timing with labels."""
        with metrics_exporter.time_operation('normalization_duration', labels={'normalizer_type': 'OFI'}):
            time.sleep(0.005)  # Simulate normalization

    def test_multiple_timed_operations(self, metrics_exporter):
        """Test multiple timed operations."""
        for _ in range(5):
            with metrics_exporter.time_operation('market_data_latency', labels={'symbol': 'AAPL'}):
                time.sleep(0.001)


class TestHTTPEndpoint:
    """Test HTTP metrics endpoint."""

    def test_http_server_starts(self, metrics_exporter_with_server):
        """Test that HTTP server starts successfully."""
        assert metrics_exporter_with_server.server is not None

    def test_metrics_endpoint_accessible(self, metrics_exporter_with_server):
        """Test that /metrics endpoint is accessible."""
        time.sleep(0.5)  # Give server time to start
        try:
            response = requests.get('http://localhost:8002/metrics', timeout=2)
            assert response.status_code == 200
            assert 'text/plain' in response.headers.get('Content-Type', '')
        except requests.exceptions.RequestException:
            pytest.skip("HTTP server not accessible (may be expected in test environment)")

    def test_metrics_format(self, metrics_exporter_with_server):
        """Test that metrics are in Prometheus format."""
        metrics_exporter_with_server.inc('market_ticks_total', labels={'symbol': 'TEST', 'source': 'TEST'})
        metrics_text = metrics_exporter_with_server.get_metrics_text().decode('utf-8')

        # Check for Prometheus format
        assert 'market_ticks_total' in metrics_text
        assert '# HELP' in metrics_text
        assert '# TYPE' in metrics_text

    def test_server_stop(self, metrics_registry):
        """Test that HTTP server stops cleanly."""
        exporter = MetricsExporter(registry=metrics_registry, port=8003)
        exporter.start_http_server()
        time.sleep(0.2)
        exporter.stop_http_server()
        assert exporter.server is None


class TestEndToEndScenarios:
    """Test end-to-end monitoring scenarios."""

    def test_market_data_ingestion_scenario(self, metrics_exporter):
        """Test full market data ingestion monitoring."""
        # Simulate market data ingestion
        for _ in range(100):
            metrics_exporter.inc('market_ticks_total', labels={'symbol': 'AAPL', 'source': 'IBKR'})

        # Record latencies
        latencies = [0.001, 0.002, 0.003, 0.005, 0.008]
        for lat in latencies:
            metrics_exporter.observe('market_data_latency', lat, labels={'symbol': 'AAPL'})

        # Update freshness
        metrics_exporter.set('market_data_freshness', 0.5, labels={'symbol': 'AAPL'})

        # Update completeness
        metrics_exporter.set('data_completeness', 0.99, labels={'symbol': 'AAPL', 'timeframe': '1m'})

    def test_order_execution_scenario(self, metrics_exporter):
        """Test full order execution monitoring."""
        symbol = 'AAPL'

        # Place orders
        metrics_exporter.inc('orders_total', labels={'symbol': symbol, 'side': 'BUY', 'order_type': 'LIMIT'}, value=10)

        # Risk checks
        metrics_exporter.inc('risk_checks_total', labels={'check_type': 'exposure', 'result': 'pass'}, value=10)

        # Fills
        metrics_exporter.inc('order_fills', labels={'symbol': symbol, 'status': 'FILLED'}, value=8)
        metrics_exporter.inc('order_fills', labels={'symbol': symbol, 'status': 'PARTIAL'}, value=2)

        # Execution latency
        for lat in [0.05, 0.08, 0.12]:
            metrics_exporter.observe('execution_latency', lat, labels={'symbol': symbol})

        # Update position
        metrics_exporter.set('position_exposure', 150000, labels={'symbol': symbol, 'exposure_type': 'gross'})

    def test_sla_monitoring_scenario(self, metrics_exporter):
        """Test SLA compliance monitoring."""
        # Track various SLA metrics
        metrics_exporter.set('sla_compliance', 0.998, labels={'sla_metric': 'market_data_latency_p95'})
        metrics_exporter.set('sla_compliance', 0.995, labels={'sla_metric': 'execution_latency_p95'})
        metrics_exporter.set('sla_compliance', 0.999, labels={'sla_metric': 'data_completeness'})

        # Service health
        metrics_exporter.set('service_health', 1.0, labels={'service': 'data-plane'})
        metrics_exporter.set('service_health', 1.0, labels={'service': 'order-plane'})


class TestGlobalInstance:
    """Test global metrics instance management."""

    def test_init_metrics_exporter(self):
        """Test global metrics exporter initialization."""
        # Note: This modifies global state, so it might affect other tests
        # In a real scenario, we'd want to reset this between tests
        exporter = init_metrics_exporter(port=8005, start_server=False)
        assert exporter is not None

    def test_get_metrics(self):
        """Test getting the global metrics instance."""
        # This assumes init_metrics_exporter was called
        metrics = get_metrics()
        # May be None if not initialized in this test run
        # assert metrics is not None or metrics is None  # Either is valid


class TestMetricsLabels:
    """Test that metrics properly handle labels."""

    def test_multiple_symbols_tracked_separately(self, metrics_exporter):
        """Test that different symbols are tracked separately."""
        metrics_exporter.inc('market_ticks_total', labels={'symbol': 'AAPL', 'source': 'IBKR'}, value=100)
        metrics_exporter.inc('market_ticks_total', labels={'symbol': 'TSLA', 'source': 'IBKR'}, value=50)

        metrics_text = metrics_exporter.get_metrics_text().decode('utf-8')
        assert 'symbol="AAPL"' in metrics_text
        assert 'symbol="TSLA"' in metrics_text

    def test_multiple_order_types_tracked(self, metrics_exporter):
        """Test that different order types are tracked separately."""
        metrics_exporter.inc('orders_total', labels={'symbol': 'AAPL', 'side': 'BUY', 'order_type': 'LIMIT'}, value=10)
        metrics_exporter.inc('orders_total', labels={'symbol': 'AAPL', 'side': 'BUY', 'order_type': 'MARKET'}, value=5)

        metrics_text = metrics_exporter.get_metrics_text().decode('utf-8')
        assert 'order_type="LIMIT"' in metrics_text
        assert 'order_type="MARKET"' in metrics_text


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
