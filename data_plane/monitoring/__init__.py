"""
Monitoring & Observability Module
==================================

Comprehensive monitoring system for Algo-Trade with:
- Prometheus metrics export
- Multi-channel alerting (Slack, Email, PagerDuty)
- Grafana dashboard configurations

Usage:
    from data_plane.monitoring import get_metrics_exporter, AlertManager

    # Initialize metrics
    exporter = get_metrics_exporter(port=8000)
    exporter.record_pnl(cumulative_pnl=0.025)

    # Initialize alerting
    alert_mgr = AlertManager(config_path='monitoring_config.yaml')
    alert_mgr.critical("System Critical", "Kill switch activated", "risk")
"""

from .metrics_exporter import (
    MetricsExporter,
    TradingMetrics,
    init_metrics_exporter,
    get_metrics_exporter,
)

from .alerting import (
    AlertManager,
    Alert,
    AlertConfig,
    AlertTemplates,
)

__all__ = [
    # Metrics
    "MetricsExporter",
    "TradingMetrics",
    "init_metrics_exporter",
    "get_metrics_exporter",

    # Alerting
    "AlertManager",
    "Alert",
    "AlertConfig",
    "AlertTemplates",
]

__version__ = "1.0.0"
