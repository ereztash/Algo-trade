"""
Prometheus Metrics Exporter for Algo-Trade System
==================================================

Exports key trading metrics to Prometheus for monitoring and alerting.

Metric Categories:
1. Latency Metrics - Order placement and execution timing
2. Performance Metrics - P&L, Sharpe, drawdown
3. Risk Metrics - Exposure, volatility, kill switch status
4. System Health - Error rates, throughput, resource usage
5. Data Quality - Completeness, freshness, staleness

Usage:
    from data_plane.monitoring.metrics_exporter import MetricsExporter

    exporter = MetricsExporter(port=8000)
    exporter.start()

    # Record metrics
    exporter.record_order_latency(latency_ms=45.3)
    exporter.record_pnl(cumulative_pnl=0.025)
"""

import time
import logging
from typing import Dict, Optional, List
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    Info,
    start_http_server,
    CollectorRegistry,
    REGISTRY,
)
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# Metric Definitions
# ============================================================================

@dataclass
class TradingMetrics:
    """Container for all Prometheus metrics."""

    # Latency Metrics (Histogram for percentiles)
    intent_to_ack_latency: Histogram = field(default=None)
    order_placement_latency: Histogram = field(default=None)
    order_fill_latency: Histogram = field(default=None)
    signal_generation_latency: Histogram = field(default=None)
    portfolio_optimization_latency: Histogram = field(default=None)

    # Performance Metrics (Gauge for current values)
    pnl_cumulative: Gauge = field(default=None)
    pnl_daily: Gauge = field(default=None)
    sharpe_ratio_rolling_30d: Gauge = field(default=None)
    sharpe_ratio_rolling_90d: Gauge = field(default=None)
    max_drawdown_current: Gauge = field(default=None)
    max_drawdown_historical: Gauge = field(default=None)
    win_rate: Gauge = field(default=None)
    profit_factor: Gauge = field(default=None)

    # Risk Metrics
    gross_exposure: Gauge = field(default=None)
    net_exposure: Gauge = field(default=None)
    portfolio_volatility: Gauge = field(default=None)
    portfolio_beta: Gauge = field(default=None)
    largest_position_pct: Gauge = field(default=None)
    var_95: Gauge = field(default=None)  # Value at Risk 95%
    cvar_95: Gauge = field(default=None)  # Conditional VaR 95%

    # Kill Switch Status (Gauge 0/1)
    kill_switch_pnl_active: Gauge = field(default=None)
    kill_switch_psr_active: Gauge = field(default=None)
    kill_switch_drawdown_active: Gauge = field(default=None)

    # Market Regime (Info metric)
    market_regime: Info = field(default=None)

    # Order Metrics (Counter for cumulative counts)
    orders_submitted_total: Counter = field(default=None)
    orders_filled_total: Counter = field(default=None)
    orders_cancelled_total: Counter = field(default=None)
    orders_rejected_total: Counter = field(default=None)

    # Error Metrics
    errors_total: Counter = field(default=None)
    ibkr_connection_errors: Counter = field(default=None)
    data_quality_errors: Counter = field(default=None)
    optimization_failures: Counter = field(default=None)

    # System Health
    cpu_usage_percent: Gauge = field(default=None)
    memory_usage_mb: Gauge = field(default=None)
    throughput_msg_per_sec: Gauge = field(default=None)
    active_positions: Gauge = field(default=None)
    connected_clients: Gauge = field(default=None)

    # Data Quality Metrics
    data_completeness: Gauge = field(default=None)  # % of expected data received
    data_staleness_seconds: Gauge = field(default=None)  # Time since last update
    missing_ticks_count: Counter = field(default=None)
    data_gaps_total: Counter = field(default=None)

    # Trading Strategy Metrics
    signal_count_active: Gauge = field(default=None)
    signal_strength_avg: Gauge = field(default=None)
    correlation_breakdown_events: Counter = field(default=None)
    rebalance_count: Counter = field(default=None)

    # IBKR Specific
    ibkr_pacing_violations: Counter = field(default=None)
    ibkr_reconnections: Counter = field(default=None)
    ibkr_api_rate: Gauge = field(default=None)  # Requests per second


class MetricsExporter:
    """
    Prometheus Metrics Exporter for Trading System.

    Provides methods to record various metrics and exposes them
    via HTTP endpoint for Prometheus scraping.
    """

    def __init__(
        self,
        port: int = 8000,
        registry: Optional[CollectorRegistry] = None,
        namespace: str = "algo_trade",
    ):
        """
        Initialize metrics exporter.

        Args:
            port: HTTP port for /metrics endpoint
            registry: Prometheus registry (default: global REGISTRY)
            namespace: Metric name prefix
        """
        self.port = port
        self.registry = registry or REGISTRY
        self.namespace = namespace
        self.started = False

        # Initialize all metrics
        self.metrics = self._init_metrics()

        # Cache for derived metrics
        self._trade_count = 0
        self._win_count = 0
        self._gross_profit = 0.0
        self._gross_loss = 0.0

        logger.info(f"MetricsExporter initialized on port {port}")

    def _init_metrics(self) -> TradingMetrics:
        """Initialize all Prometheus metrics."""

        # Latency metrics (histogram with custom buckets for ms)
        latency_buckets = [5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]

        return TradingMetrics(
            # Latency
            intent_to_ack_latency=Histogram(
                f"{self.namespace}_intent_to_ack_latency_ms",
                "Latency from order intent to broker acknowledgment (ms)",
                buckets=latency_buckets,
                registry=self.registry,
            ),
            order_placement_latency=Histogram(
                f"{self.namespace}_order_placement_latency_ms",
                "Latency for order placement (ms)",
                buckets=latency_buckets,
                registry=self.registry,
            ),
            order_fill_latency=Histogram(
                f"{self.namespace}_order_fill_latency_ms",
                "Latency from order submission to fill (ms)",
                buckets=[100, 500, 1000, 5000, 10000, 30000, 60000],
                registry=self.registry,
            ),
            signal_generation_latency=Histogram(
                f"{self.namespace}_signal_generation_latency_ms",
                "Latency for signal generation (ms)",
                buckets=latency_buckets,
                registry=self.registry,
            ),
            portfolio_optimization_latency=Histogram(
                f"{self.namespace}_portfolio_optimization_latency_ms",
                "Latency for portfolio optimization (ms)",
                buckets=[10, 50, 100, 250, 500, 1000, 2000],
                registry=self.registry,
            ),

            # Performance
            pnl_cumulative=Gauge(
                f"{self.namespace}_pnl_cumulative",
                "Cumulative P&L (fractional)",
                registry=self.registry,
            ),
            pnl_daily=Gauge(
                f"{self.namespace}_pnl_daily",
                "Daily P&L (fractional)",
                registry=self.registry,
            ),
            sharpe_ratio_rolling_30d=Gauge(
                f"{self.namespace}_sharpe_ratio_rolling_30d",
                "30-day rolling Sharpe ratio",
                registry=self.registry,
            ),
            sharpe_ratio_rolling_90d=Gauge(
                f"{self.namespace}_sharpe_ratio_rolling_90d",
                "90-day rolling Sharpe ratio",
                registry=self.registry,
            ),
            max_drawdown_current=Gauge(
                f"{self.namespace}_max_drawdown_current",
                "Current drawdown from peak (fractional)",
                registry=self.registry,
            ),
            max_drawdown_historical=Gauge(
                f"{self.namespace}_max_drawdown_historical",
                "Historical maximum drawdown (fractional)",
                registry=self.registry,
            ),
            win_rate=Gauge(
                f"{self.namespace}_win_rate",
                "Win rate (fraction of winning trades)",
                registry=self.registry,
            ),
            profit_factor=Gauge(
                f"{self.namespace}_profit_factor",
                "Profit factor (gross profit / gross loss)",
                registry=self.registry,
            ),

            # Risk
            gross_exposure=Gauge(
                f"{self.namespace}_gross_exposure",
                "Gross exposure (sum of absolute position values)",
                registry=self.registry,
            ),
            net_exposure=Gauge(
                f"{self.namespace}_net_exposure",
                "Net exposure (sum of signed position values)",
                registry=self.registry,
            ),
            portfolio_volatility=Gauge(
                f"{self.namespace}_portfolio_volatility",
                "Portfolio volatility (annualized)",
                registry=self.registry,
            ),
            portfolio_beta=Gauge(
                f"{self.namespace}_portfolio_beta",
                "Portfolio beta relative to benchmark",
                registry=self.registry,
            ),
            largest_position_pct=Gauge(
                f"{self.namespace}_largest_position_pct",
                "Largest single position as % of portfolio",
                registry=self.registry,
            ),
            var_95=Gauge(
                f"{self.namespace}_var_95",
                "Value at Risk 95% (1-day)",
                registry=self.registry,
            ),
            cvar_95=Gauge(
                f"{self.namespace}_cvar_95",
                "Conditional Value at Risk 95% (1-day)",
                registry=self.registry,
            ),

            # Kill Switches
            kill_switch_pnl_active=Gauge(
                f"{self.namespace}_kill_switch_pnl_active",
                "PnL kill switch status (1=active, 0=inactive)",
                registry=self.registry,
            ),
            kill_switch_psr_active=Gauge(
                f"{self.namespace}_kill_switch_psr_active",
                "PSR kill switch status (1=active, 0=inactive)",
                registry=self.registry,
            ),
            kill_switch_drawdown_active=Gauge(
                f"{self.namespace}_kill_switch_drawdown_active",
                "Drawdown kill switch status (1=active, 0=inactive)",
                registry=self.registry,
            ),

            # Market Regime
            market_regime=Info(
                f"{self.namespace}_market_regime",
                "Current market regime (Calm/Normal/Storm)",
                registry=self.registry,
            ),

            # Orders
            orders_submitted_total=Counter(
                f"{self.namespace}_orders_submitted_total",
                "Total orders submitted",
                registry=self.registry,
            ),
            orders_filled_total=Counter(
                f"{self.namespace}_orders_filled_total",
                "Total orders filled",
                registry=self.registry,
            ),
            orders_cancelled_total=Counter(
                f"{self.namespace}_orders_cancelled_total",
                "Total orders cancelled",
                registry=self.registry,
            ),
            orders_rejected_total=Counter(
                f"{self.namespace}_orders_rejected_total",
                "Total orders rejected",
                registry=self.registry,
            ),

            # Errors
            errors_total=Counter(
                f"{self.namespace}_errors_total",
                "Total errors",
                ["error_type"],
                registry=self.registry,
            ),
            ibkr_connection_errors=Counter(
                f"{self.namespace}_ibkr_connection_errors_total",
                "IBKR connection errors",
                registry=self.registry,
            ),
            data_quality_errors=Counter(
                f"{self.namespace}_data_quality_errors_total",
                "Data quality errors",
                ["error_type"],
                registry=self.registry,
            ),
            optimization_failures=Counter(
                f"{self.namespace}_optimization_failures_total",
                "Portfolio optimization failures",
                registry=self.registry,
            ),

            # System Health
            cpu_usage_percent=Gauge(
                f"{self.namespace}_cpu_usage_percent",
                "CPU usage percentage",
                registry=self.registry,
            ),
            memory_usage_mb=Gauge(
                f"{self.namespace}_memory_usage_mb",
                "Memory usage in MB",
                registry=self.registry,
            ),
            throughput_msg_per_sec=Gauge(
                f"{self.namespace}_throughput_msg_per_sec",
                "Message throughput (messages per second)",
                registry=self.registry,
            ),
            active_positions=Gauge(
                f"{self.namespace}_active_positions",
                "Number of active positions",
                registry=self.registry,
            ),
            connected_clients=Gauge(
                f"{self.namespace}_connected_clients",
                "Number of connected clients",
                registry=self.registry,
            ),

            # Data Quality
            data_completeness=Gauge(
                f"{self.namespace}_data_completeness",
                "Data completeness (0-1)",
                registry=self.registry,
            ),
            data_staleness_seconds=Gauge(
                f"{self.namespace}_data_staleness_seconds",
                "Time since last data update (seconds)",
                registry=self.registry,
            ),
            missing_ticks_count=Counter(
                f"{self.namespace}_missing_ticks_total",
                "Total missing market ticks",
                registry=self.registry,
            ),
            data_gaps_total=Counter(
                f"{self.namespace}_data_gaps_total",
                "Total data gaps detected",
                registry=self.registry,
            ),

            # Trading Strategy
            signal_count_active=Gauge(
                f"{self.namespace}_signal_count_active",
                "Number of active signals",
                registry=self.registry,
            ),
            signal_strength_avg=Gauge(
                f"{self.namespace}_signal_strength_avg",
                "Average signal strength",
                registry=self.registry,
            ),
            correlation_breakdown_events=Counter(
                f"{self.namespace}_correlation_breakdown_events_total",
                "Correlation breakdown events",
                registry=self.registry,
            ),
            rebalance_count=Counter(
                f"{self.namespace}_rebalance_count_total",
                "Portfolio rebalance count",
                registry=self.registry,
            ),

            # IBKR Specific
            ibkr_pacing_violations=Counter(
                f"{self.namespace}_ibkr_pacing_violations_total",
                "IBKR pacing violations",
                registry=self.registry,
            ),
            ibkr_reconnections=Counter(
                f"{self.namespace}_ibkr_reconnections_total",
                "IBKR reconnection count",
                registry=self.registry,
            ),
            ibkr_api_rate=Gauge(
                f"{self.namespace}_ibkr_api_rate",
                "IBKR API request rate (requests/sec)",
                registry=self.registry,
            ),
        )

    def start(self):
        """Start HTTP server for /metrics endpoint."""
        if not self.started:
            start_http_server(self.port, registry=self.registry)
            self.started = True
            logger.info(f"Metrics endpoint started at http://0.0.0.0:{self.port}/metrics")

    # ========================================================================
    # Recording Methods - Latency
    # ========================================================================

    def record_order_latency(self, latency_ms: float, latency_type: str = "intent_to_ack"):
        """Record order latency."""
        if latency_type == "intent_to_ack":
            self.metrics.intent_to_ack_latency.observe(latency_ms)
        elif latency_type == "placement":
            self.metrics.order_placement_latency.observe(latency_ms)
        elif latency_type == "fill":
            self.metrics.order_fill_latency.observe(latency_ms)

    def record_signal_generation_latency(self, latency_ms: float):
        """Record signal generation latency."""
        self.metrics.signal_generation_latency.observe(latency_ms)

    def record_optimization_latency(self, latency_ms: float):
        """Record portfolio optimization latency."""
        self.metrics.portfolio_optimization_latency.observe(latency_ms)

    # ========================================================================
    # Recording Methods - Performance
    # ========================================================================

    def record_pnl(self, cumulative_pnl: float, daily_pnl: Optional[float] = None):
        """Record P&L."""
        self.metrics.pnl_cumulative.set(cumulative_pnl)
        if daily_pnl is not None:
            self.metrics.pnl_daily.set(daily_pnl)

    def record_sharpe_ratio(self, sharpe_30d: float, sharpe_90d: Optional[float] = None):
        """Record Sharpe ratios."""
        self.metrics.sharpe_ratio_rolling_30d.set(sharpe_30d)
        if sharpe_90d is not None:
            self.metrics.sharpe_ratio_rolling_90d.set(sharpe_90d)

    def record_drawdown(self, current_dd: float, max_dd: float):
        """Record drawdown metrics."""
        self.metrics.max_drawdown_current.set(current_dd)
        self.metrics.max_drawdown_historical.set(max_dd)

    def record_trade(self, pnl: float):
        """Record a trade and update win rate, profit factor."""
        self._trade_count += 1
        if pnl > 0:
            self._win_count += 1
            self._gross_profit += pnl
        elif pnl < 0:
            self._gross_loss += abs(pnl)

        # Update win rate
        if self._trade_count > 0:
            win_rate = self._win_count / self._trade_count
            self.metrics.win_rate.set(win_rate)

        # Update profit factor
        if self._gross_loss > 0:
            profit_factor = self._gross_profit / self._gross_loss
            self.metrics.profit_factor.set(profit_factor)

    # ========================================================================
    # Recording Methods - Risk
    # ========================================================================

    def record_exposure(self, gross: float, net: float):
        """Record portfolio exposure."""
        self.metrics.gross_exposure.set(gross)
        self.metrics.net_exposure.set(net)

    def record_portfolio_risk(
        self,
        volatility: float,
        beta: Optional[float] = None,
        largest_position_pct: Optional[float] = None,
        var_95: Optional[float] = None,
        cvar_95: Optional[float] = None,
    ):
        """Record portfolio risk metrics."""
        self.metrics.portfolio_volatility.set(volatility)
        if beta is not None:
            self.metrics.portfolio_beta.set(beta)
        if largest_position_pct is not None:
            self.metrics.largest_position_pct.set(largest_position_pct)
        if var_95 is not None:
            self.metrics.var_95.set(var_95)
        if cvar_95 is not None:
            self.metrics.cvar_95.set(cvar_95)

    def set_kill_switch(self, switch_type: str, active: bool):
        """Set kill switch status."""
        value = 1.0 if active else 0.0
        if switch_type == "pnl":
            self.metrics.kill_switch_pnl_active.set(value)
        elif switch_type == "psr":
            self.metrics.kill_switch_psr_active.set(value)
        elif switch_type == "drawdown":
            self.metrics.kill_switch_drawdown_active.set(value)

    def set_market_regime(self, regime: str):
        """Set market regime (Calm/Normal/Storm)."""
        self.metrics.market_regime.info({"regime": regime})

    # ========================================================================
    # Recording Methods - Orders
    # ========================================================================

    def record_order_event(self, event_type: str):
        """Record order event (submitted/filled/cancelled/rejected)."""
        if event_type == "submitted":
            self.metrics.orders_submitted_total.inc()
        elif event_type == "filled":
            self.metrics.orders_filled_total.inc()
        elif event_type == "cancelled":
            self.metrics.orders_cancelled_total.inc()
        elif event_type == "rejected":
            self.metrics.orders_rejected_total.inc()

    # ========================================================================
    # Recording Methods - Errors
    # ========================================================================

    def record_error(self, error_type: str):
        """Record error by type."""
        self.metrics.errors_total.labels(error_type=error_type).inc()

    def record_ibkr_error(self, error_type: str):
        """Record IBKR-specific error."""
        if error_type == "connection":
            self.metrics.ibkr_connection_errors.inc()
        elif error_type == "pacing":
            self.metrics.ibkr_pacing_violations.inc()
        elif error_type == "reconnection":
            self.metrics.ibkr_reconnections.inc()

    def record_data_quality_error(self, error_type: str):
        """Record data quality error."""
        self.metrics.data_quality_errors.labels(error_type=error_type).inc()
        if error_type == "missing_tick":
            self.metrics.missing_ticks_count.inc()
        elif error_type == "gap":
            self.metrics.data_gaps_total.inc()

    def record_optimization_failure(self):
        """Record portfolio optimization failure."""
        self.metrics.optimization_failures.inc()

    # ========================================================================
    # Recording Methods - System Health
    # ========================================================================

    def record_system_health(
        self,
        cpu_percent: float,
        memory_mb: float,
        throughput: Optional[float] = None,
    ):
        """Record system health metrics."""
        self.metrics.cpu_usage_percent.set(cpu_percent)
        self.metrics.memory_usage_mb.set(memory_mb)
        if throughput is not None:
            self.metrics.throughput_msg_per_sec.set(throughput)

    def set_active_positions(self, count: int):
        """Set active position count."""
        self.metrics.active_positions.set(count)

    def set_connected_clients(self, count: int):
        """Set connected client count."""
        self.metrics.connected_clients.set(count)

    # ========================================================================
    # Recording Methods - Data Quality
    # ========================================================================

    def record_data_quality(self, completeness: float, staleness_seconds: float):
        """Record data quality metrics."""
        self.metrics.data_completeness.set(completeness)
        self.metrics.data_staleness_seconds.set(staleness_seconds)

    # ========================================================================
    # Recording Methods - Trading Strategy
    # ========================================================================

    def record_signal_metrics(self, active_count: int, avg_strength: float):
        """Record signal metrics."""
        self.metrics.signal_count_active.set(active_count)
        self.metrics.signal_strength_avg.set(avg_strength)

    def record_correlation_breakdown(self):
        """Record correlation breakdown event."""
        self.metrics.correlation_breakdown_events.inc()

    def record_rebalance(self):
        """Record portfolio rebalance."""
        self.metrics.rebalance_count.inc()

    # ========================================================================
    # Recording Methods - IBKR
    # ========================================================================

    def set_ibkr_api_rate(self, rate: float):
        """Set IBKR API request rate."""
        self.metrics.ibkr_api_rate.set(rate)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_metrics_summary(self) -> Dict:
        """Get current snapshot of key metrics."""
        return {
            "pnl_cumulative": self.metrics.pnl_cumulative._value.get(),
            "sharpe_ratio_30d": self.metrics.sharpe_ratio_rolling_30d._value.get(),
            "max_drawdown_current": self.metrics.max_drawdown_current._value.get(),
            "gross_exposure": self.metrics.gross_exposure._value.get(),
            "net_exposure": self.metrics.net_exposure._value.get(),
            "active_positions": self.metrics.active_positions._value.get(),
            "orders_submitted": self.metrics.orders_submitted_total._value.get(),
            "orders_filled": self.metrics.orders_filled_total._value.get(),
            "errors_total": sum(
                metric._value.get()
                for metric in self.metrics.errors_total._metrics.values()
            ),
        }


# ============================================================================
# Convenience Functions
# ============================================================================

def init_metrics_exporter(port: int = 8000) -> MetricsExporter:
    """
    Initialize and start metrics exporter.

    Args:
        port: HTTP port for /metrics endpoint

    Returns:
        MetricsExporter instance
    """
    exporter = MetricsExporter(port=port)
    exporter.start()
    return exporter


# Singleton instance for global access
_global_exporter: Optional[MetricsExporter] = None


def get_metrics_exporter(port: int = 8000) -> MetricsExporter:
    """
    Get or create global metrics exporter.

    Args:
        port: HTTP port (only used if creating new instance)

    Returns:
        MetricsExporter instance
    """
    global _global_exporter
    if _global_exporter is None:
        _global_exporter = init_metrics_exporter(port=port)
    return _global_exporter
