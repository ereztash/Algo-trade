# Algo-Trade System - Operational Guide

This guide provides step-by-step instructions for running, testing, and monitoring the 3-plane algorithmic trading system.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Running the System](#running-the-system)
4. [Testing](#testing)
5. [Monitoring & Dashboards](#monitoring--dashboards)
6. [Troubleshooting](#troubleshooting)
7. [Production Deployment](#production-deployment)

---

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Python 3.9+ with pip
- Git

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd Algo-trade

# Install Python dependencies
pip install -r requirements.txt

# Start infrastructure services
docker compose up -d

# Wait for services to be healthy (30-60 seconds)
docker compose ps

# Run the system
python -m data_plane.app.main
```

---

## Infrastructure Setup

### 1. Kafka Message Bus

The Kafka broker is the backbone of the 3-plane architecture, handling all inter-plane communication.

```bash
# Start Kafka and Zookeeper
docker compose up -d zookeeper kafka

# Verify Kafka is running
docker compose logs kafka | grep "started (kafka.server.KafkaServer)"

# View Kafka UI (optional, for debugging)
open http://localhost:8080
```

**Topics Created Automatically:**
- `market_events` - Data Plane → Strategy Plane
- `market_raw` - Raw market data storage
- `order_intents` - Strategy Plane → Order Plane
- `exec_reports` - Order Plane → Strategy Plane (feedback)
- `dlq` - Dead Letter Queue for invalid messages

### 2. Monitoring Stack (Prometheus + Grafana)

```bash
# Start monitoring services
docker compose up -d prometheus grafana

# Access Grafana
open http://localhost:3000
# Default credentials: admin/admin
```

**Prometheus Endpoints:**
- Prometheus UI: http://localhost:9090
- Data Plane metrics: http://localhost:8000/metrics
- Order Plane metrics: http://localhost:8001/metrics
- Strategy Plane metrics: http://localhost:8002/metrics

---

## Running the System

### Full System (All 3 Planes)

```bash
# Ensure infrastructure is running
docker compose ps

# Run the main application
python -m data_plane.app.main
```

This starts all three planes concurrently:
1. **Data Plane**: Ingests market data from IBKR, validates, normalizes, and publishes to `market_events`
2. **Strategy Plane**: Consumes `market_events`, generates signals, publishes `order_intents`
3. **Order Plane**: Consumes `order_intents`, executes orders, publishes `exec_reports`

### Individual Planes (for development/debugging)

```bash
# Data Plane only
python -m data_plane.app.orchestrator

# Strategy Plane only
python -m apps.strategy_loop.main

# Order Plane only
python -m order_plane.app.orchestrator
```

### Environment Variables

Create a `.env` file for configuration:

```bash
# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Interactive Brokers
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

# Database
DB_CONNECTION_STRING=postgresql://user:pass@localhost/algo_trade

# Monitoring
PROMETHEUS_PORT=8000
LOG_LEVEL=INFO
```

---

## Testing

### Unit Tests

```bash
# Run all unit tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Schema Validation Tests

```bash
# Test message contracts
pytest tests/test_schema_validation.py -v

# Expected output: 18 passed, 1 skipped
```

### End-to-End Integration Tests

**Prerequisites**: Kafka must be running

```bash
# Start Kafka
docker compose up -d kafka

# Wait for Kafka to be ready
sleep 30

# Run E2E tests
pytest tests/e2e/test_kafka_e2e.py -v --log-cli-level=INFO

# Run specific test
pytest tests/e2e/test_kafka_e2e.py::test_full_3_plane_message_flow -v
```

**E2E Test Coverage:**
- ✅ Kafka connection lifecycle
- ✅ Message publish/consume roundtrip
- ✅ Validation on publish and consume
- ✅ Data Plane → Strategy Plane flow
- ✅ Strategy Plane → Order Plane flow
- ✅ Order Plane → Strategy Plane feedback loop
- ✅ Full 3-plane message flow
- ✅ High-throughput scenario (1000 messages)
- ✅ Invalid message handling
- ✅ Consumer auto-skip behavior

### Performance Tests

```bash
# High-throughput test
pytest tests/e2e/test_kafka_e2e.py::test_high_throughput_message_flow -v

# Latency benchmarks
pytest tests/e2e/test_kafka_e2e.py -v -k latency
```

### Property-Based Tests

```bash
# Run hypothesis property tests
pytest tests/property/ -v

# Run metamorphic tests
pytest tests/metamorphic/ -v
```

---

## Monitoring & Dashboards

### Grafana Dashboards

1. **Access Grafana**: http://localhost:3000
2. **Login**: admin/admin
3. **Navigate**: Dashboards → Algo-Trade - Main Dashboard

**Dashboard Panels:**

**Overview Section:**
- Current PnL (stat)
- PnL Over Time (time series)
- P95 Order Fill Latency (stat)
- Order Intents Rate (stat)
- Kill Switch Status (stat)
- Trading Enabled Status (stat)

**Data Plane Metrics:**
- Market Data Ingestion Rate (ticks/bars per second)
- Data Freshness (seconds)
- Data Completeness Score (0-1)
- Validation Errors (errors per second)

**Strategy Plane Metrics:**
- Signal Generation Rate (signals per second)
- Portfolio Weights (percentage allocation)
- Market Regime Probabilities
- Sharpe Ratio

**Order Plane Metrics:**
- Order Execution Rate (orders per second)
- Order Fill Latency (P50, P95, P99)
- Slippage (basis points)
- Transaction Costs (hourly)

### Prometheus Queries

Access Prometheus at http://localhost:9090 and try these queries:

```promql
# Data ingestion rate
rate(data_ticks_received_total[1m])

# Strategy signal generation
rate(strategy_signals_generated_total[1m])

# Order fill latency P95
histogram_quantile(0.95, sum(rate(order_fill_latency_ms_bucket[5m])) by (le))

# Current PnL
strategy_pnl_dollars

# Kill switch status
strategy_kill_switch_triggered
```

### Metrics Endpoints

Each plane exposes a `/metrics` endpoint:

```bash
# Data Plane metrics
curl http://localhost:8000/metrics

# Order Plane metrics
curl http://localhost:8001/metrics

# Strategy Plane metrics
curl http://localhost:8002/metrics

# Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

---

## Troubleshooting

### Kafka Issues

**Problem**: Kafka broker not starting

```bash
# Check logs
docker compose logs kafka

# Restart Kafka
docker compose restart kafka

# Verify Zookeeper is running
docker compose ps zookeeper
```

**Problem**: Topics not created

```bash
# Manually create topics
docker compose up kafka-init

# List topics
docker exec -it algo-trade-kafka kafka-topics --list --bootstrap-server localhost:9092
```

**Problem**: Consumer lag

```bash
# Check consumer groups
docker exec -it algo-trade-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe --group strategy_plane

# Reset offsets (use with caution)
docker exec -it algo-trade-kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group strategy_plane \
  --reset-offsets --to-earliest --execute --topic market_events
```

### Validation Errors

**Problem**: Messages failing validation

```bash
# Check DLQ topic
docker exec -it algo-trade-kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dlq \
  --from-beginning

# View validation error metrics
curl http://localhost:8000/metrics | grep validation_errors
```

**Problem**: Schema mismatch

```bash
# Verify JSON schemas
cat contracts/json_schemas/bar_event.json | jq .

# Test validation manually
python -c "
from contracts.schema_validator import MessageValidator
from contracts.validators import BarEvent

validator = MessageValidator()
data = {
    'event_type': 'bar_event',
    'symbol': 'SPY',
    # ... your test data
}
result = validator.validate_message(data)
print(f'Valid: {result.is_valid}')
print(f'Errors: {result.errors}')
"
```

### Connection Issues

**Problem**: Cannot connect to IBKR

```bash
# Check IBKR TWS/Gateway is running
# Verify API settings in TWS:
# - Enable ActiveX and Socket Clients
# - Socket port: 7497 (paper) or 7496 (live)
# - Trusted IPs: 127.0.0.1

# Test connection
python -c "
from data_plane.connectors.ibkr.client import IBKRMarketClient
client = IBKRMarketClient({'host': '127.0.0.1', 'port': 7497})
# Should connect without errors
"
```

**Problem**: Metrics not appearing in Prometheus

```bash
# Check Prometheus targets
open http://localhost:9090/targets

# Verify metrics server is running
curl http://localhost:8000/metrics

# Check Prometheus config
cat infrastructure/prometheus/prometheus.yml
```

### Performance Issues

**Problem**: High latency

```bash
# Check Kafka lag
docker compose logs kafka | grep -i lag

# Monitor system resources
docker stats

# Check Python GC
python -m data_plane.app.main --debug-gc
```

**Problem**: Memory issues

```bash
# Check memory usage
docker stats

# Limit rolling window sizes
# Edit apps/strategy_loop/main.py
# Reduce maxlen in MarketState dataclasses
```

---

## Production Deployment

### Checklist

- [ ] Configure production Kafka cluster (3+ brokers, replication factor 3)
- [ ] Set up SSL/TLS for Kafka connections
- [ ] Configure authentication (SASL/SCRAM)
- [ ] Set up persistent volumes for Prometheus/Grafana
- [ ] Configure alerting (PagerDuty, Slack, etc.)
- [ ] Set up log aggregation (ELK, Loki)
- [ ] Configure kill switches and circuit breakers
- [ ] Implement graceful shutdown handlers
- [ ] Set up database backups
- [ ] Configure monitoring retention (30 days+)
- [ ] Implement message replay capability
- [ ] Set up DLQ processing workflows
- [ ] Configure auto-scaling for Strategy Plane
- [ ] Implement canary deployments
- [ ] Set up disaster recovery procedures

### Production Configuration

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 3
      KAFKA_MIN_INSYNC_REPLICAS: 2
      KAFKA_LOG_RETENTION_HOURS: 168  # 7 days
      KAFKA_LOG_SEGMENT_BYTES: 1073741824  # 1GB
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G

  prometheus:
    environment:
      PROMETHEUS_RETENTION_TIME: 30d
      PROMETHEUS_RETENTION_SIZE: 50GB
    volumes:
      - prometheus-prod:/prometheus
```

### Security Hardening

```bash
# Enable Kafka ACLs
docker exec -it kafka kafka-acls \
  --bootstrap-server localhost:9092 \
  --add \
  --allow-principal User:data_plane \
  --operation Write \
  --topic market_events

# Configure Grafana HTTPS
# Edit infrastructure/grafana/grafana.ini
[server]
protocol = https
cert_file = /etc/grafana/ssl/cert.pem
cert_key = /etc/grafana/ssl/key.pem

# Set up network policies
# Isolate planes on separate networks
```

### Monitoring & Alerting

```yaml
# alertmanager.yml
route:
  receiver: 'pagerduty'
  group_by: ['alertname', 'service']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 12h

receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '<your-key>'
        description: '{{ .CommonAnnotations.summary }}'

# Prometheus alert rules
groups:
  - name: trading_alerts
    rules:
      - alert: HighOrderLatency
        expr: histogram_quantile(0.95, rate(order_fill_latency_ms_bucket[5m])) > 200
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High order fill latency detected"

      - alert: KillSwitchTriggered
        expr: strategy_kill_switch_triggered > 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Kill switch has been triggered!"

      - alert: HighValidationErrors
        expr: rate(data_validation_errors_total[5m]) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High rate of validation errors"
```

---

## Additional Resources

- [Architecture Documentation](docs/architecture.md)
- [Message Contracts README](contracts/README.md)
- [Monitoring Infrastructure Guide](infrastructure/README.md)
- [API Documentation](docs/api.md)
- [Development Guide](CONTRIBUTING.md)

---

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/your-org/algo-trade/issues
- Documentation: https://docs.your-org.com/algo-trade
- Slack: #algo-trade-support
