# Monitoring Stack

Complete monitoring and observability infrastructure for the Algo-Trading system.

## Quick Start

```bash
# Start monitoring stack
./monitoring/start-monitoring.sh

# Access Grafana dashboards
open http://localhost:3000
# Login: admin / algo-trade-2024
```

## Stack Components

- **Prometheus** (port 9091) - Metrics collection and storage
- **Grafana** (port 3000) - Dashboards and visualization
- **Alertmanager** (port 9093) - Alert routing and notifications
- **Node Exporter** (port 9100) - System metrics
- **Pushgateway** (port 9092) - Batch job metrics

## Directory Structure

```
monitoring/
├── prometheus/
│   ├── prometheus.yml              # Prometheus configuration
│   ├── alerts/                     # Alert rules
│   │   ├── system_alerts.yml      # System health alerts
│   │   ├── data_plane_alerts.yml  # Data quality alerts
│   │   ├── strategy_plane_alerts.yml
│   │   └── order_plane_alerts.yml
│   └── recording_rules/           # Pre-computed aggregations
│       └── aggregations.yml
├── alertmanager/
│   └── alertmanager.yml           # Alert routing config
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/          # Prometheus datasource
│   │   └── dashboards/           # Dashboard provisioning
│   └── dashboards/               # Dashboard JSON files
│       ├── system_health.json
│       ├── data_quality.json
│       ├── strategy_performance.json
│       └── risk_monitoring.json
├── start-monitoring.sh           # Startup script
├── INTEGRATION_EXAMPLE.py        # Code examples
└── README.md                     # This file
```

## Available Dashboards

1. **System Health** - Service status, CPU, memory, disk
2. **Data Quality** - Ingestion latency, quality scores, Kafka lag
3. **Strategy Performance** - Portfolio value, PnL, Sharpe ratio, signals
4. **Risk Monitoring** - Kill switch, fill rate, slippage, IBKR status

## Alert Severity Levels

- **Critical** - Immediate action required (Email + Slack + SMS)
- **Warning** - Investigate within 15 minutes (Email + Slack)
- **Info** - Logged for review (Logs only)

## Critical Alerts

- Kill Switch Triggered
- Service Down
- IBKR Disconnected
- Critical Data Latency (p99 > 500ms)
- Critical Portfolio Drop (>10% in 1 hour)
- Critical Drawdown (>15%)
- Out of Memory Risk (>95%)

## Configuration

### Alertmanager Notifications

Edit `alertmanager/alertmanager.yml` to configure:
- Email (SMTP)
- Slack webhooks
- PagerDuty
- SMS (Twilio)

### Custom Metrics

Add metrics to your service:

```python
from data_plane.monitoring.metrics_exporter import init_metrics_exporter

metrics = init_metrics_exporter(port=9090)
metrics.inc("my_counter", labels={"type": "foo"})
metrics.observe("my_histogram", 42.5)
metrics.set_gauge("my_gauge", 123.45)
```

See `INTEGRATION_EXAMPLE.py` for detailed examples.

## Useful Commands

```bash
# Start stack
docker-compose -f docker-compose.monitoring.yml up -d

# Stop stack
docker-compose -f docker-compose.monitoring.yml down

# View logs
docker-compose -f docker-compose.monitoring.yml logs -f prometheus
docker-compose -f docker-compose.monitoring.yml logs -f grafana
docker-compose -f docker-compose.monitoring.yml logs -f alertmanager

# Restart specific service
docker-compose -f docker-compose.monitoring.yml restart prometheus

# Check service status
docker-compose -f docker-compose.monitoring.yml ps

# Reload Prometheus config (without restart)
curl -X POST http://localhost:9091/-/reload

# Query Prometheus
curl 'http://localhost:9091/api/v1/query?query=up'

# Test alert
curl -X POST http://localhost:9093/api/v1/alerts
```

## Metrics Reference

See `/data_plane/monitoring/metrics_exporter.py` for complete metrics list.

**Metrics by Category**:
- System: CPU, memory, disk, service uptime
- Data Plane: Ingestion rate, latency, quality, Kafka lag
- Strategy Plane: Signals, portfolio value, PnL, Sharpe ratio
- Order Plane: Orders, fills, latency, slippage, risk checks
- IBKR: Connection status, API errors, throttling

## Documentation

Full documentation: `/docs/MONITORING.md`

- Metrics reference
- Dashboard guide
- Alert configuration
- Integration examples
- Troubleshooting
- SLAs & SLOs

## Support

For issues:
- GitHub: https://github.com/ereztash/Algo-trade/issues
- Docs: `/docs/MONITORING.md`
- Runbooks: `/docs/runbooks/`
