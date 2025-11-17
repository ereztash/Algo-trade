# Monitoring & Observability Guide

Complete monitoring infrastructure for the Algo-Trade system using Prometheus, Grafana, and Alertmanager.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [Metrics Reference](#metrics-reference)
5. [Dashboards](#dashboards)
6. [Alerts](#alerts)
7. [Using Metrics in Code](#using-metrics-in-code)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The monitoring stack provides comprehensive observability for all system components:

- **Prometheus**: Time-series database for metrics collection and storage
- **Grafana**: Visualization and dashboarding
- **Alertmanager**: Alert routing and notifications
- **Node Exporter**: System-level metrics (CPU, memory, disk)

### Key Features

- ✅ Real-time metrics for all trading planes (Data, Order, Strategy)
- ✅ Pre-configured dashboards for system overview
- ✅ Comprehensive alerting rules for critical scenarios
- ✅ SLA compliance tracking
- ✅ Performance monitoring and bottleneck detection
- ✅ Risk exposure tracking

---

## Quick Start

### 1. Start the Monitoring Stack

```bash
# Start Prometheus, Grafana, Alertmanager, and Node Exporter
docker-compose -f docker-compose.monitoring.yml up -d

# Verify all services are running
docker-compose -f docker-compose.monitoring.yml ps
```

### 2. Access the UIs

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

### 3. Start Your Application

```bash
# The application automatically exposes metrics on port 8000
python -m data_plane.app.main
```

Metrics will be available at: http://localhost:8000/metrics

### 4. View Dashboards

1. Open Grafana (http://localhost:3000)
2. Login with `admin`/`admin`
3. Navigate to Dashboards → Algo-Trade System Overview

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐             │
│  │ Data     │  │ Order     │  │ Strategy     │             │
│  │ Plane    │  │ Plane     │  │ Plane        │             │
│  └────┬─────┘  └─────┬─────┘  └──────┬───────┘             │
│       │              │                │                      │
│       └──────────────┴────────────────┘                      │
│                      │                                       │
│              metrics_exporter.py                             │
│                 :8000/metrics                                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTP scrape (15s interval)
                       ↓
        ┌──────────────────────────────┐
        │       Prometheus :9090       │
        │  - Metrics storage           │
        │  - Alert evaluation          │
        └──────┬───────────────────┬───┘
               │                   │
    ┌──────────↓─────┐    ┌───────↓────────────┐
    │  Grafana :3000 │    │ Alertmanager :9093 │
    │  - Dashboards  │    │ - Alert routing    │
    │  - Visualization│    │ - Notifications    │
    └────────────────┘    └────────────────────┘
```

---

## Metrics Reference

### Data Plane Metrics

#### Market Data

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `market_ticks_total` | Counter | symbol, source | Total market data ticks received |
| `market_data_errors_total` | Counter | symbol, error_type | Market data errors |
| `market_data_latency_seconds` | Histogram | symbol | End-to-end market data latency |
| `market_data_freshness_seconds` | Gauge | symbol | Age of most recent market data |
| `data_completeness_ratio` | Gauge | symbol, timeframe | Data completeness (0-1) |

**Example queries:**
```promql
# Market data tick rate
rate(market_ticks_total[5m])

# P95 market data latency
histogram_quantile(0.95, rate(market_data_latency_seconds_bucket[5m]))

# Stale data detection
market_data_freshness_seconds > 10
```

#### Time Synchronization

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ntp_drift_milliseconds` | Gauge | - | NTP time drift |

#### Storage

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `storage_writes_total` | Counter | status | Storage write operations |
| `storage_write_latency_seconds` | Histogram | - | Storage write latency |

### Order Plane Metrics

#### Order Execution

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `orders_total` | Counter | symbol, side, order_type | Orders placed |
| `order_fills_total` | Counter | symbol, status | Order fills |
| `order_rejections_total` | Counter | symbol, reason | Order rejections |
| `execution_latency_seconds` | Histogram | symbol | Intent-to-fill latency |

**Example queries:**
```promql
# Order fill rate
rate(order_fills_total{status="FILLED"}[5m]) / rate(orders_total[5m])

# Order rejection rate
rate(order_rejections_total[5m]) / rate(orders_total[5m])

# P95 execution latency
histogram_quantile(0.95, rate(execution_latency_seconds_bucket[5m]))
```

#### Risk Management

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `risk_checks_total` | Counter | check_type, result | Risk checks performed |
| `position_exposure_usd` | Gauge | symbol, exposure_type | Position exposure |
| `throttled_orders_total` | Counter | symbol, reason | Throttled orders |

**Example queries:**
```promql
# Total gross exposure
sum(position_exposure_usd{exposure_type="gross"})

# Risk check failure rate
rate(risk_checks_total{result="fail"}[5m]) / rate(risk_checks_total[5m])
```

### Strategy Plane Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `signals_generated_total` | Counter | symbol, signal_type | Trading signals generated |
| `strategy_computation_seconds` | Histogram | strategy_name | Strategy computation time |
| `portfolio_value_usd` | Gauge | - | Current portfolio value |
| `active_positions` | Gauge | - | Number of active positions |

### Message Bus Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `messages_published_total` | Counter | topic | Messages published |
| `messages_consumed_total` | Counter | topic | Messages consumed |
| `message_bus_lag_seconds` | Gauge | topic, consumer_group | Consumer lag |

### Health & SLA Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `service_health` | Gauge | service | Service health (1=healthy, 0=unhealthy) |
| `sla_compliance_ratio` | Gauge | sla_metric | SLA compliance (0-1) |

---

## Dashboards

### System Overview Dashboard

Pre-configured dashboard includes:

1. **Market Data Monitoring**
   - Tick rate by symbol
   - Data freshness gauges
   - Latency percentiles
   - Completeness ratios

2. **Order Execution**
   - Order rate by side
   - Fill rate by status
   - Execution latency (P95)
   - Rejection breakdown

3. **Risk Management**
   - Position exposure gauges
   - Risk check results
   - Throttling events

4. **System Health**
   - CPU usage
   - Memory usage
   - Service status
   - NTP drift

### Creating Custom Dashboards

1. Open Grafana UI
2. Click "+" → "Dashboard"
3. Add panels with PromQL queries
4. Save to `/monitoring/grafana/dashboards/` for persistence

Example panel configuration:
```json
{
  "targets": [
    {
      "expr": "rate(market_ticks_total[5m])",
      "legendFormat": "{{symbol}}"
    }
  ],
  "title": "Market Data Rate"
}
```

---

## Alerts

### Alert Severity Levels

- **Critical**: Requires immediate action (paged 24/7)
- **Warning**: Requires attention within business hours

### Key Alerts

#### Market Data

| Alert | Threshold | Severity | Description |
|-------|-----------|----------|-------------|
| MarketDataStale | >10s | Critical | No fresh data for symbol |
| HighMarketDataLatency | P95 >100ms | Warning | High ingestion latency |
| LowDataCompleteness | <95% | Warning | Missing data points |
| NTPDriftExcessive | >100ms | Critical | Time sync issue |

#### Order Execution

| Alert | Threshold | Severity | Description |
|-------|-----------|----------|-------------|
| HighOrderRejectionRate | >5% | Warning | Many orders rejected |
| HighExecutionLatency | P95 >1s | Warning | Slow execution |
| NoOrderFills | 0 fills for 5m | Critical | Execution pipeline broken |

#### Risk Management

| Alert | Threshold | Severity | Description |
|-------|-----------|----------|-------------|
| ExcessiveGrossExposure | >$1M | Critical | Gross exposure limit breach |
| ExcessiveNetExposure | >±$500K | Critical | Net exposure limit breach |

#### System Resources

| Alert | Threshold | Severity | Description |
|-------|-----------|----------|-------------|
| HighCPUUsage | >80% | Warning | High CPU usage |
| HighMemoryUsage | >85% | Warning | High memory usage |
| DiskSpaceLow | <15% | Warning | Low disk space |

### Configuring Alert Notifications

Edit `/monitoring/alertmanager/alertmanager.yml`:

```yaml
receivers:
  - name: 'critical-alerts'
    email_configs:
      - to: 'your-email@company.com'
    slack_configs:
      - api_url: 'YOUR_SLACK_WEBHOOK_URL'
        channel: '#trading-alerts'
```

---

## Using Metrics in Code

### Basic Usage

```python
from data_plane.monitoring.metrics_exporter import get_metrics

# Get the global metrics instance
metrics = get_metrics()

# Increment a counter
metrics.inc('market_ticks_total', labels={'symbol': 'AAPL', 'source': 'IBKR'})

# Set a gauge
metrics.set('market_data_freshness', 2.5, labels={'symbol': 'AAPL'})

# Observe a histogram
metrics.observe('market_data_latency', 0.015, labels={'symbol': 'AAPL'})
```

### Timing Operations

```python
# Using context manager
with metrics.time_operation('normalization_duration', labels={'normalizer_type': 'OFI'}):
    # Your code here
    result = normalize_data(data)
```

### Market Data Example

```python
async def process_market_tick(symbol: str, tick: MarketTick):
    metrics = get_metrics()

    # Count tick
    metrics.inc('market_ticks_total', labels={'symbol': symbol, 'source': 'IBKR'})

    # Track latency
    latency = time.time() - tick.timestamp
    metrics.observe('market_data_latency', latency, labels={'symbol': symbol})

    # Update freshness
    metrics.set('market_data_freshness', 0, labels={'symbol': symbol})
```

### Order Execution Example

```python
async def place_order(intent: OrderIntent):
    metrics = get_metrics()

    # Count order
    metrics.inc('orders_total', labels={
        'symbol': intent.symbol,
        'side': intent.side,
        'order_type': intent.order_type
    })

    # Perform risk check
    if not risk_checker.validate(intent):
        metrics.inc('order_rejections_total', labels={
            'symbol': intent.symbol,
            'reason': 'RISK_LIMIT'
        })
        return

    metrics.inc('risk_checks_total', labels={
        'check_type': 'exposure',
        'result': 'pass'
    })

    # Place order and track latency
    start_time = time.time()
    order_id = await broker.place(intent)

    # Wait for fill (simplified)
    fill = await wait_for_fill(order_id)

    # Track execution latency
    exec_latency = time.time() - start_time
    metrics.observe('execution_latency', exec_latency, labels={'symbol': intent.symbol})

    # Count fill
    metrics.inc('order_fills_total', labels={
        'symbol': intent.symbol,
        'status': fill.status
    })
```

### Strategy Example

```python
async def run_strategy():
    metrics = get_metrics()

    async for market_event in bus.consume("market_events"):
        # Time strategy computation
        with metrics.time_operation('strategy_computation_time', labels={'strategy_name': 'momentum'}):
            signals = compute_signals(market_event)

        # Count signals generated
        for signal in signals:
            metrics.inc('signals_generated_total', labels={
                'symbol': signal.symbol,
                'signal_type': signal.type
            })

        # Update portfolio metrics
        metrics.set('portfolio_value', calculate_portfolio_value())
        metrics.set('active_positions', count_active_positions())
```

---

## Configuration

### Prometheus Configuration

Edit `/monitoring/prometheus/prometheus.yml` to add new scrape targets:

```yaml
scrape_configs:
  - job_name: 'my-new-service'
    static_configs:
      - targets: ['my-service:8001']
        labels:
          service: 'my-service'
```

### Adding New Alert Rules

Edit `/monitoring/prometheus/alerts.yml`:

```yaml
groups:
  - name: my_alerts
    interval: 30s
    rules:
      - alert: MyCustomAlert
        expr: my_metric > 100
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "My metric is too high"
          description: "Value: {{ $value }}"
```

### Grafana Provisioning

Add new datasources in `/monitoring/grafana/provisioning/datasources/`:

```yaml
apiVersion: 1
datasources:
  - name: MyDataSource
    type: prometheus
    url: http://prometheus:9090
```

---

## Troubleshooting

### Metrics Not Appearing in Prometheus

**Check application is exposing metrics:**
```bash
curl http://localhost:8000/metrics
```

**Check Prometheus targets:**
1. Open http://localhost:9090/targets
2. Verify target status is "UP"
3. Check for scrape errors

**Check Docker networking:**
```bash
# From within Prometheus container
docker exec -it algo-trade-prometheus wget -O- http://host.docker.internal:8000/metrics
```

### Grafana Dashboard Not Loading Data

**Verify datasource connection:**
1. Grafana → Configuration → Data Sources
2. Click "Test" on Prometheus datasource
3. Should show "Data source is working"

**Check PromQL query:**
1. Open Prometheus UI (http://localhost:9090)
2. Test your query in the Graph tab
3. Verify it returns data

### Alerts Not Firing

**Check alert rules are loaded:**
```bash
# View loaded rules
curl http://localhost:9090/api/v1/rules
```

**Check alert evaluation:**
1. Open Prometheus UI → Alerts
2. Find your alert
3. Check "State" and "Active Since"

**Verify Alertmanager connection:**
```bash
curl http://localhost:9090/api/v1/alertmanagers
```

### High Cardinality Issues

If metrics are consuming too much memory:

**Identify high-cardinality metrics:**
```promql
# In Prometheus UI
topk(10, count by (__name__)({__name__!=""}))
```

**Solutions:**
- Reduce label cardinality (fewer unique values)
- Use recording rules for expensive queries
- Increase Prometheus retention settings
- Consider dropping unnecessary labels

### Common Error Messages

**"context deadline exceeded"**
- Query timeout - simplify query or increase timeout
- Check Prometheus performance

**"out of bounds"**
- Requesting data outside retention window
- Check time range in query

**"no data"**
- Application not running
- Metrics endpoint not accessible
- Wrong metric name or labels

---

## Best Practices

### Metric Naming

✅ **Good:**
- `market_data_latency_seconds` (descriptive, includes unit)
- `orders_total` (clear counter name)
- `position_exposure_usd` (includes currency)

❌ **Bad:**
- `latency` (too vague)
- `order_count` (use `_total` suffix for counters)
- `exposure` (missing unit)

### Label Usage

✅ **Good:**
```python
metrics.inc('orders_total', labels={'symbol': 'AAPL', 'side': 'BUY'})
```

❌ **Bad:**
```python
# Don't create separate metrics per symbol
metrics.inc('orders_total_AAPL')  # Creates cardinality explosion
```

### Performance

- Avoid high-cardinality labels (unique values >1000)
- Use histograms for latency tracking, not individual gauges
- Batch metric updates when possible
- Don't record every individual event - use sampling for high-frequency events

---

## Maintenance

### Regular Tasks

**Daily:**
- Check Grafana dashboards for anomalies
- Review recent alerts

**Weekly:**
- Review disk usage (Prometheus data)
- Check alert rule effectiveness
- Update dashboards as needed

**Monthly:**
- Review and optimize high-cardinality metrics
- Update alert thresholds based on actual SLAs
- Archive old metrics data if needed

### Backup

```bash
# Backup Prometheus data
docker cp algo-trade-prometheus:/prometheus ./prometheus-backup

# Backup Grafana dashboards
docker cp algo-trade-grafana:/var/lib/grafana/dashboards ./grafana-backup
```

---

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Guide](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Alerting Best Practices](https://prometheus.io/docs/practices/alerting/)

---

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review Prometheus/Grafana logs: `docker-compose -f docker-compose.monitoring.yml logs`
3. Contact the DevOps/SRE team
