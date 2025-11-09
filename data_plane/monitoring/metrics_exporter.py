"""
Metrics Exporter - ייצוא מטריקות Prometheus/OpenTelemetry
מטרה: ריכוז מטריקות ביצועים וניטור של Data Plane
"""

import logging
from typing import Dict, Any, Optional, Callable
from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, push_to_gateway
from prometheus_client import start_http_server
import time
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricsExporter:
    """
    מייצא מטריקות Prometheus עבור Data Plane.

    מטריקות עיקריות:
    - Latency: p50, p95, p99 של processing pipeline
    - Throughput: events per second
    - Errors: schema violations, pacing violations, NTP rejects
    - QA Gates: freshness, completeness
    - IBKR: connection status, API errors
    """

    def __init__(self, port: int = 9090, push_gateway: Optional[str] = None):
        """
        אתחול Metrics Exporter.

        Args:
            port: port להרצת Prometheus HTTP server (default: 9090)
            push_gateway: כתובת Prometheus Push Gateway (optional)
        """
        self.port = port
        self.push_gateway = push_gateway
        self.registry = CollectorRegistry()

        # --- Counters ---
        self.events_total = Counter(
            'data_plane_events_total',
            'Total events processed by Data Plane',
            ['event_type', 'source'],
            registry=self.registry
        )

        self.errors_total = Counter(
            'data_plane_errors_total',
            'Total errors in Data Plane',
            ['error_type', 'component'],
            registry=self.registry
        )

        self.qa_rejects_total = Counter(
            'data_plane_qa_rejects_total',
            'Total QA gate rejections',
            ['gate_type', 'reason'],
            registry=self.registry
        )

        # --- Histograms (for latency) ---
        self.latency_seconds = Histogram(
            'data_plane_latency_seconds',
            'Event processing latency in seconds',
            ['stage'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry
        )

        self.ibkr_latency_seconds = Histogram(
            'ibkr_api_latency_seconds',
            'IBKR API call latency in seconds',
            ['operation'],
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
            registry=self.registry
        )

        # --- Gauges (for current state) ---
        self.kafka_lag = Gauge(
            'data_plane_kafka_lag',
            'Kafka consumer lag',
            ['topic'],
            registry=self.registry
        )

        self.active_subscriptions = Gauge(
            'ibkr_active_subscriptions',
            'Number of active IBKR market data subscriptions',
            registry=self.registry
        )

        self.ntp_drift_ms = Gauge(
            'data_plane_ntp_drift_ms',
            'NTP drift in milliseconds',
            registry=self.registry
        )

        self.completeness_rate = Gauge(
            'data_plane_completeness_rate',
            'Data completeness rate (0-1)',
            ['symbol'],
            registry=self.registry
        )

        # --- Summary (for percentiles) ---
        self.event_size_bytes = Summary(
            'data_plane_event_size_bytes',
            'Event size in bytes',
            ['event_type'],
            registry=self.registry
        )

        # Custom metrics storage (for non-Prometheus tracking)
        self.custom_metrics: Dict[str, Any] = defaultdict(int)

        # Start HTTP server for scraping (if port provided)
        if port:
            try:
                start_http_server(port, registry=self.registry)
                logger.info(f"Prometheus metrics server started on port {port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus server on port {port}: {e}")

        logger.info(
            f"MetricsExporter initialized. "
            f"Port: {port}, Push Gateway: {push_gateway or 'None'}"
        )

    def inc(self, metric: str, labels: Optional[Dict[str, str]] = None, value: float = 1):
        """
        הגדלת counter metric.

        Args:
            metric: שם המטריקה
            labels: labels עבור המטריקה
            value: ערך להגדלה (default: 1)
        """
        labels = labels or {}

        try:
            if metric == 'events':
                self.events_total.labels(**labels).inc(value)
            elif metric == 'errors':
                self.errors_total.labels(**labels).inc(value)
            elif metric == 'qa_rejects':
                self.qa_rejects_total.labels(**labels).inc(value)
            else:
                # Custom counter
                key = f"{metric}_{labels}" if labels else metric
                self.custom_metrics[key] += value
                logger.debug(f"Custom counter incremented: {key} += {value}")
        except Exception as e:
            logger.error(f"Failed to increment metric {metric}: {e}")

    def observe(self, metric: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        רישום observation למטריקת histogram או summary.

        Args:
            metric: שם המטריקה
            value: ערך לרישום
            labels: labels עבור המטריקה
        """
        labels = labels or {}

        try:
            if metric == 'latency':
                self.latency_seconds.labels(**labels).observe(value)
            elif metric == 'ibkr_latency':
                self.ibkr_latency_seconds.labels(**labels).observe(value)
            elif metric == 'event_size':
                self.event_size_bytes.labels(**labels).observe(value)
            else:
                # Custom observation
                key = f"{metric}_{labels}"
                self.custom_metrics[key] = value
                logger.debug(f"Custom observation recorded: {key} = {value}")
        except Exception as e:
            logger.error(f"Failed to observe metric {metric}: {e}")

    def set(self, metric: str, value: float, labels: Optional[Dict[str, str]] = None):
        """
        קביעת ערך gauge metric.

        Args:
            metric: שם המטריקה
            value: ערך לקביעה
            labels: labels עבור המטריקה
        """
        labels = labels or {}

        try:
            if metric == 'kafka_lag':
                self.kafka_lag.labels(**labels).set(value)
            elif metric == 'active_subscriptions':
                self.active_subscriptions.set(value)
            elif metric == 'ntp_drift':
                self.ntp_drift_ms.set(value)
            elif metric == 'completeness':
                self.completeness_rate.labels(**labels).set(value)
            else:
                # Custom gauge
                key = f"{metric}_{labels}" if labels else metric
                self.custom_metrics[key] = value
                logger.debug(f"Custom gauge set: {key} = {value}")
        except Exception as e:
            logger.error(f"Failed to set metric {metric}: {e}")

    def alert(self, alert_name: str, **kwargs):
        """
        שליחת alert (מתועד כ-error metric).

        Args:
            alert_name: שם ה-alert
            **kwargs: פרטים נוספים
        """
        logger.warning(f"ALERT: {alert_name} - {kwargs}")
        self.inc('errors', labels={'error_type': 'alert', 'component': alert_name})

        # רשום גם ב-custom metrics
        self.custom_metrics[f"alert_{alert_name}"] = {
            'timestamp': datetime.utcnow().isoformat(),
            'details': kwargs
        }

    def push(self, job_name: str = 'data_plane'):
        """
        דחיפת מטריקות ל-Push Gateway.

        Args:
            job_name: שם ה-job עבור Push Gateway
        """
        if not self.push_gateway:
            logger.warning("Push Gateway not configured, skipping push")
            return

        try:
            push_to_gateway(self.push_gateway, job=job_name, registry=self.registry)
            logger.debug(f"Metrics pushed to gateway: {self.push_gateway}")
        except Exception as e:
            logger.error(f"Failed to push metrics to gateway {self.push_gateway}: {e}")

    def get_custom_metrics(self) -> Dict[str, Any]:
        """
        קבלת כל המטריקות המותאמות אישית.

        Returns:
            Dict עם כל המטריקות
        """
        return dict(self.custom_metrics)

    def reset_custom_metrics(self):
        """
        איפוס מטריקות מותאמות אישית.
        """
        self.custom_metrics.clear()
        logger.info("Custom metrics reset")


# Factory function לאתחול metrics exporter
def init_metrics_exporter(port: int = 9090, push_gateway: Optional[str] = None) -> Callable:
    """
    אתחול Prometheus/OpenTelemetry metrics exporter.

    Args:
        port: port להרצת HTTP server (default: 9090)
        push_gateway: כתובת Push Gateway (optional)

    Returns:
        Callable: פונקציה לרישום מטריקה - metric(name, value, labels)
    """
    exporter = MetricsExporter(port=port, push_gateway=push_gateway)

    # Return a simple callable interface
    def record_metric(metric: str, value: Any, labels: Optional[Dict[str, str]] = None):
        """
        רישום מטריקה.

        Args:
            metric: שם המטריקה
            value: ערך (או 'inc' להגדלה)
            labels: labels (optional)
        """
        if value == 'inc' or isinstance(value, int):
            exporter.inc(metric, labels, value if isinstance(value, int) else 1)
        elif isinstance(value, float):
            # Decide between observe (for histograms) or set (for gauges)
            if 'latency' in metric or 'size' in metric:
                exporter.observe(metric, value, labels)
            else:
                exporter.set(metric, value, labels)
        else:
            logger.warning(f"Unknown metric value type: {type(value)}")

    # Attach exporter to callable for direct access
    record_metric.exporter = exporter

    logger.info("Metrics exporter initialized and ready")
    return record_metric
