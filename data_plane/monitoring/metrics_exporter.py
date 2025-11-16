"""
Prometheus metrics exporter for the 3-plane trading system.

Provides centralized metrics collection for:
- Data Plane: Ingestion rates, data quality, latency
- Order Plane: Order execution, fills, rejections
- Strategy Plane: Signal generation, portfolio metrics, PnL

Each plane has its own MetricsCollector with dedicated metrics.
Metrics are exposed via HTTP /metrics endpoint in Prometheus format.
"""

import logging
from typing import Dict, List, Optional, Any
from enum import Enum

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Summary,
    Info,
    CollectorRegistry,
    REGISTRY,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


logger = logging.getLogger(__name__)


# ============================================================================
# Metric Buckets Configuration
# ============================================================================

# Latency buckets: 1ms, 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s
LATENCY_BUCKETS = (
    0.001, 0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500,
    1.0, 2.5, 5.0, 10.0, float('inf')
)

# Data freshness buckets: 10ms, 50ms, 100ms, 250ms, 500ms, 1s, 5s, 10s
FRESHNESS_BUCKETS = (
    0.010, 0.050, 0.100, 0.250, 0.500, 1.0, 5.0, 10.0, float('inf')
)

# PnL buckets: -10k, -5k, -1k, -500, -100, 0, 100, 500, 1k, 5k, 10k, 50k, 100k
PNL_BUCKETS = (
    -10000, -5000, -1000, -500, -100, 0, 100, 500, 1000, 5000, 10000, 50000, 100000, float('inf')
)


# ============================================================================
# Service Labels
# ============================================================================

class ServiceType(str, Enum):
    """Service type labels for metrics."""
    DATA_PLANE = 'data_plane'
    STRATEGY_PLANE = 'strategy_plane'
    ORDER_PLANE = 'order_plane'


# ============================================================================
# Base Metrics Collector
# ============================================================================

class MetricsCollector:
    """
    Base metrics collector with common functionality.

    Each plane (Data, Strategy, Order) extends this class and adds
    plane-specific metrics.
    """

    def __init__(
        self,
        service_name: str,
        service_type: ServiceType,
        registry: Optional[CollectorRegistry] = None,
    ):
        """
        Initialize metrics collector.

        Args:
            service_name: Service name (e.g., "data_plane_1")
            service_type: Service type enum
            registry: Prometheus registry (default: global REGISTRY)
        """
        self.service_name = service_name
        self.service_type = service_type
        self.registry = registry or REGISTRY

        # Service info
        self.info = Info(
            'service_info',
            'Service information',
            registry=self.registry,
        )
        self.info.info({
            'service_name': service_name,
            'service_type': service_type.value,
            'version': '1.0.0',
        })

        logger.info(f"Initialized MetricsCollector for {service_name} ({service_type.value})")

    def inc(self, metric_name: str, value: float = 1.0, **labels) -> None:
        """Increment a counter metric."""
        raise NotImplementedError("Subclass must implement inc()")

    def set(self, metric_name: str, value: float, **labels) -> None:
        """Set a gauge metric."""
        raise NotImplementedError("Subclass must implement set()")

    def observe(self, metric_name: str, value: float, **labels) -> None:
        """Observe a value for histogram/summary metric."""
        raise NotImplementedError("Subclass must implement observe()")

    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry)


# ============================================================================
# Data Plane Metrics
# ============================================================================

class DataPlaneMetrics(MetricsCollector):
    """
    Metrics collector for Data Plane.

    Tracks:
    - Data ingestion rates (ticks, bars)
    - Data quality (freshness, completeness)
    - Validation errors
    - NTP clock drift
    - Storage operations
    """

    def __init__(self, service_name: str = 'data_plane', registry: Optional[CollectorRegistry] = None):
        super().__init__(service_name, ServiceType.DATA_PLANE, registry)

        # Ingestion metrics
        self.ticks_received = Counter(
            'data_ticks_received_total',
            'Total number of tick events received',
            ['source', 'symbol'],
            registry=self.registry,
        )

        self.bars_received = Counter(
            'data_bars_received_total',
            'Total number of bar events received',
            ['source', 'symbol', 'duration'],
            registry=self.registry,
        )

        self.ofi_events_generated = Counter(
            'data_ofi_events_generated_total',
            'Total number of OFI events generated',
            ['symbol'],
            registry=self.registry,
        )

        # Data quality metrics
        self.data_freshness = Histogram(
            'data_freshness_seconds',
            'Data freshness in seconds',
            ['source', 'symbol'],
            buckets=FRESHNESS_BUCKETS,
            registry=self.registry,
        )

        self.completeness_score = Gauge(
            'data_completeness_score',
            'Data completeness score (0-1)',
            ['symbol'],
            registry=self.registry,
        )

        # Validation metrics
        self.validation_errors = Counter(
            'data_validation_errors_total',
            'Total number of validation errors',
            ['error_type', 'symbol'],
            registry=self.registry,
        )

        self.ntp_rejects = Counter(
            'data_ntp_rejects_total',
            'Total number of NTP clock drift rejections',
            registry=self.registry,
        )

        self.normalization_errors = Counter(
            'data_normalization_errors_total',
            'Total number of normalization errors',
            ['source'],
            registry=self.registry,
        )

        # Storage metrics
        self.storage_writes = Counter(
            'data_storage_writes_total',
            'Total number of storage writes',
            ['event_type'],
            registry=self.registry,
        )

        self.storage_write_latency = Histogram(
            'data_storage_write_latency_seconds',
            'Storage write latency in seconds',
            ['event_type'],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )

        # DLQ metrics
        self.dlq_messages = Counter(
            'data_dlq_messages_total',
            'Total number of messages sent to DLQ',
            ['reason'],
            registry=self.registry,
        )

        logger.info("Initialized Data Plane metrics")

    def inc(self, metric_name: str, value: float = 1.0, **labels) -> None:
        """Increment a counter metric."""
        metric_map = {
            'ticks_received': self.ticks_received,
            'bars_received': self.bars_received,
            'ofi_events_generated': self.ofi_events_generated,
            'validation_errors': self.validation_errors,
            'ntp_rejects': self.ntp_rejects,
            'normalization_errors': self.normalization_errors,
            'storage_writes': self.storage_writes,
            'dlq_messages': self.dlq_messages,
        }

        metric = metric_map.get(metric_name)
        if metric:
            metric.labels(**labels).inc(value)
        else:
            logger.warning(f"Unknown counter metric: {metric_name}")

    def set(self, metric_name: str, value: float, **labels) -> None:
        """Set a gauge metric."""
        metric_map = {
            'completeness_score': self.completeness_score,
        }

        metric = metric_map.get(metric_name)
        if metric:
            metric.labels(**labels).set(value)
        else:
            logger.warning(f"Unknown gauge metric: {metric_name}")

    def observe(self, metric_name: str, value: float, **labels) -> None:
        """Observe a histogram metric."""
        metric_map = {
            'data_freshness': self.data_freshness,
            'storage_write_latency': self.storage_write_latency,
        }

        metric = metric_map.get(metric_name)
        if metric:
            metric.labels(**labels).observe(value)
        else:
            logger.warning(f"Unknown histogram metric: {metric_name}")


# ============================================================================
# Order Plane Metrics
# ============================================================================

class OrderPlaneMetrics(MetricsCollector):
    """
    Metrics collector for Order Plane.

    Tracks:
    - Order execution (submitted, filled, rejected)
    - Fill latency
    - Execution costs
    - Risk rejections
    - Learning metrics
    """

    def __init__(self, service_name: str = 'order_plane', registry: Optional[CollectorRegistry] = None):
        super().__init__(service_name, ServiceType.ORDER_PLANE, registry)

        # Order execution metrics
        self.orders_received = Counter(
            'orders_received_total',
            'Total number of order intents received',
            ['strategy', 'symbol'],
            registry=self.registry,
        )

        self.orders_submitted = Counter(
            'orders_submitted_total',
            'Total number of orders submitted to broker',
            ['order_type', 'direction', 'symbol'],
            registry=self.registry,
        )

        self.orders_filled = Counter(
            'orders_filled_total',
            'Total number of orders filled',
            ['status', 'symbol'],
            registry=self.registry,
        )

        self.orders_rejected = Counter(
            'orders_rejected_total',
            'Total number of orders rejected',
            ['reason', 'symbol'],
            registry=self.registry,
        )

        # Latency metrics
        self.intent_to_submit_latency = Histogram(
            'orders_intent_to_submit_latency_seconds',
            'Latency from intent receipt to order submission',
            ['symbol'],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )

        self.submit_to_ack_latency = Histogram(
            'orders_submit_to_ack_latency_seconds',
            'Latency from submission to broker acknowledgment',
            ['symbol'],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )

        self.ack_to_fill_latency = Histogram(
            'orders_ack_to_fill_latency_seconds',
            'Latency from acknowledgment to fill',
            ['symbol'],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )

        self.total_fill_latency = Histogram(
            'orders_total_fill_latency_seconds',
            'Total latency from intent to fill',
            ['symbol'],
            buckets=LATENCY_BUCKETS,
            registry=self.registry,
        )

        # Execution cost metrics
        self.slippage_bps = Histogram(
            'orders_slippage_bps',
            'Order slippage in basis points',
            ['symbol'],
            buckets=(0, 1, 5, 10, 20, 50, 100, 200, 500, float('inf')),
            registry=self.registry,
        )

        self.commission_total = Counter(
            'orders_commission_total_usd',
            'Total commission paid in USD',
            ['symbol'],
            registry=self.registry,
        )

        # Risk metrics
        self.risk_rejections = Counter(
            'orders_risk_rejections_total',
            'Total number of risk check rejections',
            ['check_type'],
            registry=self.registry,
        )

        self.pov_downscales = Counter(
            'orders_pov_downscales_total',
            'Total number of orders downscaled due to POV limits',
            ['symbol'],
            registry=self.registry,
        )

        logger.info("Initialized Order Plane metrics")

    def inc(self, metric_name: str, value: float = 1.0, **labels) -> None:
        """Increment a counter metric."""
        metric_map = {
            'orders_received': self.orders_received,
            'orders_submitted': self.orders_submitted,
            'orders_filled': self.orders_filled,
            'orders_rejected': self.orders_rejected,
            'risk_rejections': self.risk_rejections,
            'pov_downscales': self.pov_downscales,
            'commission_total': self.commission_total,
        }

        metric = metric_map.get(metric_name)
        if metric:
            metric.labels(**labels).inc(value)
        else:
            logger.warning(f"Unknown counter metric: {metric_name}")

    def observe(self, metric_name: str, value: float, **labels) -> None:
        """Observe a histogram metric."""
        metric_map = {
            'intent_to_submit_latency': self.intent_to_submit_latency,
            'submit_to_ack_latency': self.submit_to_ack_latency,
            'ack_to_fill_latency': self.ack_to_fill_latency,
            'total_fill_latency': self.total_fill_latency,
            'slippage_bps': self.slippage_bps,
        }

        metric = metric_map.get(metric_name)
        if metric:
            metric.labels(**labels).observe(value)
        else:
            logger.warning(f"Unknown histogram metric: {metric_name}")


# ============================================================================
# Strategy Plane Metrics
# ============================================================================

class StrategyPlaneMetrics(MetricsCollector):
    """
    Metrics collector for Strategy Plane.

    Tracks:
    - Signal generation
    - Portfolio metrics (exposure, PnL)
    - Regime detection
    - QP optimization
    - Kill switches
    """

    def __init__(self, service_name: str = 'strategy_plane', registry: Optional[CollectorRegistry] = None):
        super().__init__(service_name, ServiceType.STRATEGY_PLANE, registry)

        # Signal generation metrics
        self.signals_generated = Counter(
            'strategy_signals_generated_total',
            'Total number of signals generated',
            ['strategy', 'direction'],
            registry=self.registry,
        )

        self.signal_strength = Histogram(
            'strategy_signal_strength',
            'Signal strength distribution',
            ['strategy'],
            buckets=(0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, float('inf')),
            registry=self.registry,
        )

        # Portfolio metrics
        self.portfolio_gross_exposure = Gauge(
            'strategy_portfolio_gross_exposure_usd',
            'Portfolio gross exposure in USD',
            registry=self.registry,
        )

        self.portfolio_net_exposure = Gauge(
            'strategy_portfolio_net_exposure_usd',
            'Portfolio net exposure in USD',
            registry=self.registry,
        )

        self.portfolio_value = Gauge(
            'strategy_portfolio_value_usd',
            'Total portfolio value in USD',
            registry=self.registry,
        )

        # PnL metrics
        self.pnl_realized = Gauge(
            'strategy_pnl_realized_usd',
            'Realized PnL in USD',
            registry=self.registry,
        )

        self.pnl_unrealized = Gauge(
            'strategy_pnl_unrealized_usd',
            'Unrealized PnL in USD',
            registry=self.registry,
        )

        self.pnl_total = Gauge(
            'strategy_pnl_total_usd',
            'Total PnL (realized + unrealized) in USD',
            registry=self.registry,
        )

        # Regime detection
        self.regime_state = Gauge(
            'strategy_regime_state',
            'Current market regime (0=Calm, 1=Normal, 2=Storm)',
            registry=self.registry,
        )

        self.regime_transitions = Counter(
            'strategy_regime_transitions_total',
            'Total number of regime transitions',
            ['from_regime', 'to_regime'],
            registry=self.registry,
        )

        # QP optimization metrics
        self.qp_solve_time = Histogram(
            'strategy_qp_solve_time_seconds',
            'Time to solve QP optimization problem',
            buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, float('inf')),
            registry=self.registry,
        )

        self.qp_solve_status = Counter(
            'strategy_qp_solve_status_total',
            'QP solver status results',
            ['status'],
            registry=self.registry,
        )

        # Kill switch metrics
        self.kill_switches_triggered = Counter(
            'strategy_kill_switches_triggered_total',
            'Total number of kill switch triggers',
            ['switch_type'],
            registry=self.registry,
        )

        self.kill_switch_active = Gauge(
            'strategy_kill_switch_active',
            'Kill switch active status (0=inactive, 1=active)',
            ['switch_type'],
            registry=self.registry,
        )

        logger.info("Initialized Strategy Plane metrics")

    def inc(self, metric_name: str, value: float = 1.0, **labels) -> None:
        """Increment a counter metric."""
        metric_map = {
            'signals_generated': self.signals_generated,
            'regime_transitions': self.regime_transitions,
            'qp_solve_status': self.qp_solve_status,
            'kill_switches_triggered': self.kill_switches_triggered,
        }

        metric = metric_map.get(metric_name)
        if metric:
            metric.labels(**labels).inc(value)
        else:
            logger.warning(f"Unknown counter metric: {metric_name}")

    def set(self, metric_name: str, value: float, **labels) -> None:
        """Set a gauge metric."""
        metric_map = {
            'portfolio_gross_exposure': self.portfolio_gross_exposure,
            'portfolio_net_exposure': self.portfolio_net_exposure,
            'portfolio_value': self.portfolio_value,
            'pnl_realized': self.pnl_realized,
            'pnl_unrealized': self.pnl_unrealized,
            'pnl_total': self.pnl_total,
            'regime_state': self.regime_state,
            'kill_switch_active': self.kill_switch_active,
        }

        metric = metric_map.get(metric_name)
        if metric:
            if labels:
                metric.labels(**labels).set(value)
            else:
                metric.set(value)
        else:
            logger.warning(f"Unknown gauge metric: {metric_name}")

    def observe(self, metric_name: str, value: float, **labels) -> None:
        """Observe a histogram metric."""
        metric_map = {
            'signal_strength': self.signal_strength,
            'qp_solve_time': self.qp_solve_time,
        }

        metric = metric_map.get(metric_name)
        if metric:
            metric.labels(**labels).observe(value)
        else:
            logger.warning(f"Unknown histogram metric: {metric_name}")


# ============================================================================
# Factory Functions
# ============================================================================

def init_metrics_exporter(
    service_type: str = 'data_plane',
    service_name: Optional[str] = None,
    registry: Optional[CollectorRegistry] = None,
) -> MetricsCollector:
    """
    Initialize metrics exporter for a specific service.

    Args:
        service_type: Type of service ('data_plane', 'strategy_plane', 'order_plane')
        service_name: Optional custom service name
        registry: Optional custom registry (default: global REGISTRY)

    Returns:
        MetricsCollector instance for the service

    Example:
        >>> metrics = init_metrics_exporter('data_plane')
        >>> metrics.inc('ticks_received', source='ibkr_rt', symbol='SPY')
        >>> metrics.observe('data_freshness', 0.150, source='ibkr_rt', symbol='SPY')
    """
    service_name = service_name or service_type

    if service_type == 'data_plane':
        return DataPlaneMetrics(service_name, registry)
    elif service_type == 'strategy_plane':
        return StrategyPlaneMetrics(service_name, registry)
    elif service_type == 'order_plane':
        return OrderPlaneMetrics(service_name, registry)
    else:
        raise ValueError(f"Unknown service type: {service_type}")


def get_metrics_content_type() -> str:
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST
