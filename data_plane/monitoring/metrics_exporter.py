"""
Comprehensive Prometheus metrics exporter for the Algo-Trading system.

Implements metrics collection for:
- System health (CPU, memory, disk)
- Data Plane (ingestion, latency, quality)
- Strategy Plane (signals, portfolio, PnL)
- Order Plane (orders, fills, slippage)
- IBKR integration (connection, throttling)
"""

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    Info,
    CollectorRegistry,
    start_http_server,
    REGISTRY,
)
from typing import Dict, Optional, Any
import time
import psutil
import threading


class MetricsExporter:
    """Centralized metrics exporter for all system components."""

    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """Initialize metrics exporter with Prometheus client.

        Args:
            registry: Optional Prometheus registry. Defaults to global REGISTRY.
        """
        self.registry = registry or REGISTRY
        self._init_system_metrics()
        self._init_data_plane_metrics()
        self._init_strategy_plane_metrics()
        self._init_order_plane_metrics()
        self._init_ibkr_metrics()
        self._system_monitor_thread = None
        self._running = False

    # =============================================================================
    # SYSTEM METRICS
    # =============================================================================

    def _init_system_metrics(self):
        """Initialize system health metrics."""
        # System info
        self.system_info = Info(
            "algo_trade_system",
            "System information",
            registry=self.registry
        )

        # CPU metrics
        self.cpu_usage_percent = Gauge(
            "system_cpu_usage_percent",
            "CPU usage percentage",
            registry=self.registry
        )
        self.cpu_count = Gauge(
            "system_cpu_count",
            "Number of CPU cores",
            registry=self.registry
        )

        # Memory metrics
        self.memory_usage_bytes = Gauge(
            "system_memory_usage_bytes",
            "Memory usage in bytes",
            registry=self.registry
        )
        self.memory_available_bytes = Gauge(
            "system_memory_available_bytes",
            "Available memory in bytes",
            registry=self.registry
        )
        self.memory_percent = Gauge(
            "system_memory_usage_percent",
            "Memory usage percentage",
            registry=self.registry
        )

        # Disk metrics
        self.disk_usage_bytes = Gauge(
            "system_disk_usage_bytes",
            "Disk usage in bytes",
            ["mount_point"],
            registry=self.registry
        )
        self.disk_usage_percent = Gauge(
            "system_disk_usage_percent",
            "Disk usage percentage",
            ["mount_point"],
            registry=self.registry
        )

        # Service uptime
        self.service_uptime_seconds = Gauge(
            "service_uptime_seconds",
            "Service uptime in seconds",
            ["service"],
            registry=self.registry
        )

        # Health check
        self.service_health = Gauge(
            "service_health_status",
            "Service health status (1=healthy, 0=unhealthy)",
            ["service"],
            registry=self.registry
        )

    # =============================================================================
    # DATA PLANE METRICS
    # =============================================================================

    def _init_data_plane_metrics(self):
        """Initialize Data Plane metrics."""
        # Ingestion metrics
        self.data_ingestion_total = Counter(
            "data_ingestion_events_total",
            "Total number of ingested events",
            ["event_type", "conid"],
            registry=self.registry
        )
        self.data_ingestion_bytes = Counter(
            "data_ingestion_bytes_total",
            "Total bytes ingested",
            ["event_type"],
            registry=self.registry
        )

        # Latency metrics (end-to-end: market timestamp → system timestamp)
        self.data_latency_histogram = Histogram(
            "data_ingestion_latency_ms",
            "Data ingestion latency in milliseconds",
            ["event_type"],
            buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
            registry=self.registry
        )
        self.data_latency_summary = Summary(
            "data_ingestion_latency_summary_ms",
            "Data ingestion latency summary",
            ["event_type"],
            registry=self.registry
        )

        # Data quality metrics
        self.data_quality_score = Gauge(
            "data_quality_score",
            "Data quality score (0-1)",
            ["conid", "dimension"],  # dimensions: freshness, completeness, accuracy
            registry=self.registry
        )
        self.data_completeness_percent = Gauge(
            "data_completeness_percent",
            "Data completeness percentage",
            ["conid"],
            registry=self.registry
        )
        self.data_gaps_total = Counter(
            "data_gaps_total",
            "Total number of data gaps detected",
            ["conid"],
            registry=self.registry
        )

        # NTP / Time sync
        self.ntp_drift_ms = Gauge(
            "ntp_time_drift_ms",
            "NTP time drift in milliseconds",
            registry=self.registry
        )
        self.ntp_rejects_total = Counter(
            "ntp_rejects_total",
            "Total number of NTP rejects",
            registry=self.registry
        )

        # Kafka metrics
        self.kafka_lag = Gauge(
            "kafka_consumer_lag",
            "Kafka consumer lag",
            ["topic", "partition"],
            registry=self.registry
        )
        self.kafka_messages_total = Counter(
            "kafka_messages_total",
            "Total Kafka messages",
            ["topic", "operation"],  # operation: produced, consumed
            registry=self.registry
        )

        # Normalization metrics
        self.normalization_errors_total = Counter(
            "data_normalization_errors_total",
            "Total normalization errors",
            ["error_type"],
            registry=self.registry
        )

    # =============================================================================
    # STRATEGY PLANE METRICS
    # =============================================================================

    def _init_strategy_plane_metrics(self):
        """Initialize Strategy Plane metrics."""
        # Signal generation
        self.signal_generation_duration_ms = Histogram(
            "signal_generation_duration_ms",
            "Signal generation duration in milliseconds",
            ["signal_type"],  # OFI, ERN, VRP, POS, TSX, SIF
            buckets=[1, 5, 10, 25, 50, 100, 250, 500],
            registry=self.registry
        )
        self.signals_generated_total = Counter(
            "signals_generated_total",
            "Total signals generated",
            ["signal_type"],
            registry=self.registry
        )

        # Portfolio metrics
        self.portfolio_value = Gauge(
            "portfolio_value_usd",
            "Current portfolio value in USD",
            registry=self.registry
        )
        self.portfolio_pnl = Gauge(
            "portfolio_pnl_usd",
            "Portfolio PnL in USD",
            ["period"],  # daily, weekly, monthly, total
            registry=self.registry
        )
        self.portfolio_positions = Gauge(
            "portfolio_positions",
            "Number of open positions",
            registry=self.registry
        )
        self.portfolio_exposure = Gauge(
            "portfolio_exposure_usd",
            "Portfolio exposure in USD",
            ["asset_class"],
            registry=self.registry
        )

        # Position metrics
        self.position_value = Gauge(
            "position_value_usd",
            "Position value in USD",
            ["conid", "symbol"],
            registry=self.registry
        )
        self.position_quantity = Gauge(
            "position_quantity",
            "Position quantity",
            ["conid", "symbol"],
            registry=self.registry
        )

        # Performance metrics
        self.sharpe_ratio = Gauge(
            "portfolio_sharpe_ratio",
            "Portfolio Sharpe ratio",
            ["period"],
            registry=self.registry
        )
        self.max_drawdown = Gauge(
            "portfolio_max_drawdown_percent",
            "Maximum drawdown percentage",
            registry=self.registry
        )
        self.win_rate = Gauge(
            "portfolio_win_rate_percent",
            "Win rate percentage",
            registry=self.registry
        )

        # Optimization metrics
        self.optimization_duration_ms = Histogram(
            "optimization_duration_ms",
            "Portfolio optimization duration",
            ["optimizer"],  # qp, hrp, black_litterman
            buckets=[10, 50, 100, 250, 500, 1000, 2500, 5000],
            registry=self.registry
        )
        self.optimization_errors_total = Counter(
            "optimization_errors_total",
            "Total optimization errors",
            ["optimizer"],
            registry=self.registry
        )

        # Regime detection
        self.market_regime = Gauge(
            "market_regime",
            "Current market regime (0=Calm, 1=Normal, 2=Storm)",
            registry=self.registry
        )
        self.regime_transition_total = Counter(
            "regime_transitions_total",
            "Total regime transitions",
            ["from_regime", "to_regime"],
            registry=self.registry
        )

    # =============================================================================
    # ORDER PLANE METRICS
    # =============================================================================

    def _init_order_plane_metrics(self):
        """Initialize Order Plane metrics."""
        # Order metrics
        self.orders_total = Counter(
            "orders_total",
            "Total orders",
            ["order_type", "side", "status"],  # status: submitted, filled, rejected, cancelled
            registry=self.registry
        )
        self.order_latency_ms = Histogram(
            "order_latency_ms",
            "Order latency from intent to fill (milliseconds)",
            ["order_type"],
            buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
            registry=self.registry
        )

        # Fill metrics
        self.fills_total = Counter(
            "fills_total",
            "Total fills",
            ["conid", "symbol"],
            registry=self.registry
        )
        self.fill_rate = Gauge(
            "fill_rate_percent",
            "Order fill rate percentage",
            ["order_type"],
            registry=self.registry
        )
        self.fill_quantity = Counter(
            "fill_quantity_total",
            "Total filled quantity",
            ["conid", "symbol"],
            registry=self.registry
        )

        # Execution quality
        self.slippage_bps = Histogram(
            "slippage_bps",
            "Slippage in basis points",
            ["conid", "symbol"],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 25, 50, 100],
            registry=self.registry
        )
        self.transaction_cost_bps = Histogram(
            "transaction_cost_bps",
            "Total transaction cost in basis points",
            ["conid", "symbol"],
            buckets=[1, 2, 5, 10, 20, 50, 100],
            registry=self.registry
        )

        # Risk checks
        self.risk_check_rejects_total = Counter(
            "risk_check_rejects_total",
            "Total risk check rejections",
            ["reason"],
            registry=self.registry
        )
        self.kill_switch_triggers_total = Counter(
            "kill_switch_triggers_total",
            "Total kill switch triggers",
            ["trigger_type"],  # max_dd, loss_velocity, position_limit
            registry=self.registry
        )
        self.kill_switch_status = Gauge(
            "kill_switch_status",
            "Kill switch status (1=active/triggered, 0=inactive)",
            ["switch_type"],
            registry=self.registry
        )

    # =============================================================================
    # IBKR METRICS
    # =============================================================================

    def _init_ibkr_metrics(self):
        """Initialize IBKR integration metrics."""
        # Connection metrics
        self.ibkr_connection_status = Gauge(
            "ibkr_connection_status",
            "IBKR connection status (1=connected, 0=disconnected)",
            registry=self.registry
        )
        self.ibkr_connection_uptime_seconds = Gauge(
            "ibkr_connection_uptime_seconds",
            "IBKR connection uptime in seconds",
            registry=self.registry
        )
        self.ibkr_reconnects_total = Counter(
            "ibkr_reconnects_total",
            "Total IBKR reconnection attempts",
            ["success"],
            registry=self.registry
        )

        # API errors
        self.ibkr_api_errors_total = Counter(
            "ibkr_api_errors_total",
            "Total IBKR API errors",
            ["error_code", "error_type"],
            registry=self.registry
        )

        # Throttling / Rate limiting
        self.ibkr_throttle_violations_total = Counter(
            "ibkr_throttle_violations_total",
            "Total IBKR throttle violations",
            ["endpoint"],
            registry=self.registry
        )
        self.ibkr_pacing_delay_ms = Histogram(
            "ibkr_pacing_delay_ms",
            "IBKR pacing delay in milliseconds",
            ["endpoint"],
            buckets=[0, 10, 50, 100, 250, 500, 1000, 2000],
            registry=self.registry
        )

        # Market data subscriptions
        self.ibkr_subscriptions = Gauge(
            "ibkr_active_subscriptions",
            "Number of active IBKR market data subscriptions",
            registry=self.registry
        )

    # =============================================================================
    # METRICS RECORDING METHODS
    # =============================================================================

    def record_system_metrics(self):
        """Record current system metrics."""
        # CPU
        self.cpu_usage_percent.set(psutil.cpu_percent(interval=1))
        self.cpu_count.set(psutil.cpu_count())

        # Memory
        mem = psutil.virtual_memory()
        self.memory_usage_bytes.set(mem.used)
        self.memory_available_bytes.set(mem.available)
        self.memory_percent.set(mem.percent)

        # Disk (root partition)
        disk = psutil.disk_usage('/')
        self.disk_usage_bytes.labels(mount_point='/').set(disk.used)
        self.disk_usage_percent.labels(mount_point='/').set(disk.percent)

    def inc(self, metric_name: str, labels: Optional[Dict[str, str]] = None, value: float = 1):
        """Increment a counter metric.

        Args:
            metric_name: Name of the metric
            labels: Optional labels dict
            value: Increment value (default: 1)
        """
        try:
            # Map metric_name to actual metric object
            metric_map = {
                # Data Plane
                "data_ingestion_events": self.data_ingestion_total,
                "data_gaps": self.data_gaps_total,
                "ntp_rejects": self.ntp_rejects_total,
                "kafka_messages": self.kafka_messages_total,
                "normalization_errors": self.normalization_errors_total,

                # Strategy Plane
                "signals_generated": self.signals_generated_total,
                "optimization_errors": self.optimization_errors_total,
                "regime_transitions": self.regime_transition_total,

                # Order Plane
                "orders": self.orders_total,
                "fills": self.fills_total,
                "risk_check_rejects": self.risk_check_rejects_total,
                "kill_switch_triggers": self.kill_switch_triggers_total,

                # IBKR
                "ibkr_reconnects": self.ibkr_reconnects_total,
                "ibkr_api_errors": self.ibkr_api_errors_total,
                "ibkr_throttle_violations": self.ibkr_throttle_violations_total,
            }

            metric = metric_map.get(metric_name)
            if metric:
                if labels:
                    metric.labels(**labels).inc(value)
                else:
                    metric.inc(value)
        except Exception as e:
            print(f"Error incrementing metric {metric_name}: {e}")

    def observe(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value for histogram/summary metrics.

        Args:
            metric_name: Name of the metric
            value: Value to observe
            labels: Optional labels dict
        """
        try:
            metric_map = {
                # Data Plane
                "data_ingestion_latency_ms": self.data_latency_histogram,

                # Strategy Plane
                "signal_generation_duration_ms": self.signal_generation_duration_ms,
                "optimization_duration_ms": self.optimization_duration_ms,

                # Order Plane
                "order_latency_ms": self.order_latency_ms,
                "slippage_bps": self.slippage_bps,
                "transaction_cost_bps": self.transaction_cost_bps,

                # IBKR
                "ibkr_pacing_delay_ms": self.ibkr_pacing_delay_ms,
            }

            metric = metric_map.get(metric_name)
            if metric:
                if labels:
                    metric.labels(**labels).observe(value)
                else:
                    metric.observe(value)
        except Exception as e:
            print(f"Error observing metric {metric_name}: {e}")

    def set_gauge(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value.

        Args:
            metric_name: Name of the metric
            value: Value to set
            labels: Optional labels dict
        """
        try:
            metric_map = {
                # System
                "service_uptime_seconds": self.service_uptime_seconds,
                "service_health": self.service_health,

                # Data Plane
                "data_quality_score": self.data_quality_score,
                "data_completeness_percent": self.data_completeness_percent,
                "ntp_drift_ms": self.ntp_drift_ms,
                "kafka_lag": self.kafka_lag,

                # Strategy Plane
                "portfolio_value": self.portfolio_value,
                "portfolio_pnl": self.portfolio_pnl,
                "portfolio_positions": self.portfolio_positions,
                "portfolio_exposure": self.portfolio_exposure,
                "position_value": self.position_value,
                "position_quantity": self.position_quantity,
                "sharpe_ratio": self.sharpe_ratio,
                "max_drawdown": self.max_drawdown,
                "win_rate": self.win_rate,
                "market_regime": self.market_regime,

                # Order Plane
                "fill_rate": self.fill_rate,
                "kill_switch_status": self.kill_switch_status,

                # IBKR
                "ibkr_connection_status": self.ibkr_connection_status,
                "ibkr_connection_uptime_seconds": self.ibkr_connection_uptime_seconds,
                "ibkr_subscriptions": self.ibkr_subscriptions,
            }

            metric = metric_map.get(metric_name)
            if metric:
                if labels:
                    metric.labels(**labels).set(value)
                else:
                    metric.set(value)
        except Exception as e:
            print(f"Error setting gauge {metric_name}: {e}")

    def alert(self, alert_name: str, **kwargs):
        """Trigger an alert by setting a gauge to 1.

        Args:
            alert_name: Name of the alert
            **kwargs: Additional context for the alert
        """
        # Alerts are handled by Prometheus alerting rules
        # This is a placeholder for custom application-level alerts
        print(f"ALERT: {alert_name} - {kwargs}")

    # =============================================================================
    # SYSTEM MONITORING THREAD
    # =============================================================================

    def start_system_monitor(self, interval: int = 15):
        """Start background thread to collect system metrics periodically.

        Args:
            interval: Collection interval in seconds (default: 15)
        """
        if self._running:
            return

        self._running = True

        def _monitor_loop():
            while self._running:
                try:
                    self.record_system_metrics()
                except Exception as e:
                    print(f"Error recording system metrics: {e}")
                time.sleep(interval)

        self._system_monitor_thread = threading.Thread(target=_monitor_loop, daemon=True)
        self._system_monitor_thread.start()

    def stop_system_monitor(self):
        """Stop the system monitoring thread."""
        self._running = False
        if self._system_monitor_thread:
            self._system_monitor_thread.join(timeout=5)

    # =============================================================================
    # HTTP SERVER
    # =============================================================================

    def start_http_server(self, port: int = 9090):
        """Start Prometheus HTTP metrics server.

        Args:
            port: Port to listen on (default: 9090)
        """
        start_http_server(port, registry=self.registry)
        print(f"Metrics server started on port {port}")


# Global singleton instance
_metrics_exporter: Optional[MetricsExporter] = None


def init_metrics_exporter(port: int = 9090, start_system_monitor: bool = True) -> MetricsExporter:
    """Initialize and return the global metrics exporter.

    Args:
        port: Port for Prometheus HTTP server (default: 9090)
        start_system_monitor: Whether to start system monitoring thread (default: True)

    Returns:
        MetricsExporter instance
    """
    global _metrics_exporter

    if _metrics_exporter is None:
        _metrics_exporter = MetricsExporter()
        _metrics_exporter.start_http_server(port)

        if start_system_monitor:
            _metrics_exporter.start_system_monitor()

        print(f"✓ Metrics exporter initialized on port {port}")

    return _metrics_exporter


def get_metrics_exporter() -> Optional[MetricsExporter]:
    """Get the global metrics exporter instance.

    Returns:
        MetricsExporter instance or None if not initialized
    """
    return _metrics_exporter
