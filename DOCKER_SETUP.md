# Docker Setup Guide - Algo-Trade System

Complete guide for running the algo-trading system using Docker containers.

## Overview

The system consists of 10 services running in Docker containers:

### Infrastructure Services (5)
- **Zookeeper**: Kafka coordination
- **Kafka**: Message broker for inter-service communication
- **Vault**: Secrets management (dev mode)
- **Prometheus**: Metrics collection
- **AlertManager**: Alert routing and notification

### Application Services (3)
- **Data Plane**: Market data ingestion and processing
- **Strategy Plane**: Signal generation and portfolio optimization
- **Order Plane**: Order execution and management

### Monitoring (2)
- **Grafana**: Metrics visualization and dashboards
- **Prometheus**: Time-series database

---

## Prerequisites

### Required Software
- Docker (>= 20.10)
- Docker Compose (>= 2.0) or Docker Compose V2
- 8GB RAM minimum (16GB recommended)
- 20GB free disk space

### Verify Installation
```bash
docker --version
docker-compose --version  # or: docker compose version
```

---

## Quick Start

### 1. Configure Environment
```bash
# Copy environment template
cp .env.docker .env

# Edit .env and set your IBKR credentials
nano .env  # or use your preferred editor
```

**Required settings:**
```bash
IBKR_ACCOUNT=DU123456  # Your IBKR paper trading account
IBKR_PORT=4002         # 4002 for paper, 4001 for live
```

### 2. Start the System
```bash
./scripts/docker-start.sh
```

The startup script will:
1. ✅ Run pre-flight checks (Docker, docker-compose, .env)
2. ✅ Build all Docker images
3. ✅ Start infrastructure (Zookeeper, Kafka, Vault)
4. ✅ Start monitoring (Prometheus, Grafana, AlertManager)
5. ✅ Start applications (Data, Strategy, Order planes)
6. ✅ Run health checks on all services

**Estimated startup time**: 2-3 minutes

### 3. Verify System is Running
```bash
docker-compose ps
```

All services should show status `Up` or `Up (healthy)`.

### 4. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | - |
| AlertManager | http://localhost:9093 | - |
| Data Plane Metrics | http://localhost:8000/metrics | - |
| Strategy Plane Metrics | http://localhost:8001/metrics | - |
| Order Plane Metrics | http://localhost:8002/metrics | - |

---

## Architecture

### Network Topology
```
┌─────────────────────────────────────────────────────────────┐
│ Host Machine                                                │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Docker Network: algo-trade-network (172.20.0.0/16)   │  │
│  │                                                       │  │
│  │  ┌──────────────┐     ┌──────────────┐              │  │
│  │  │  Zookeeper   │────▶│    Kafka     │              │  │
│  │  │   :2181      │     │  :9092,:9093 │              │  │
│  │  └──────────────┘     └───────┬──────┘              │  │
│  │                               │                       │  │
│  │  ┌──────────────────────────┬─┴─────┬───────────┐   │  │
│  │  │                          │       │           │   │  │
│  │  ▼                          ▼       ▼           ▼   │  │
│  │ ┌───────────┐      ┌──────────┐ ┌──────────┐ ┌────┴──┐
│  │ │ Data      │      │ Strategy │ │  Order   │ │ Prom- │
│  │ │ Plane     │─────▶│  Plane   │▶│  Plane   │ │ etheus│
│  │ │  :8000    │      │  :8001   │ │  :8002   │ │ :9090 │
│  │ └─────┬─────┘      └──────────┘ └─────┬────┘ └───┬───┘
│  │       │                                │          │    │
│  │       │ IBKR                           │ IBKR     │    │
│  │       ▼                                ▼          ▼    │
│  │  host.docker.internal:4002                    Grafana │
│  │                                                 :3000  │
│  └───────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘
```

### Data Flow
1. **Data Plane** connects to IBKR → ingests market data → publishes to Kafka (`market_events`, `ofi_events`)
2. **Strategy Plane** consumes from Kafka → generates signals → publishes order intents (`order_intents`)
3. **Order Plane** consumes order intents → executes orders via IBKR → publishes execution reports (`exec_reports`)
4. **Prometheus** scrapes metrics from all planes
5. **Grafana** visualizes metrics from Prometheus

---

## Configuration

### Environment Variables (.env)

#### IBKR Configuration
```bash
IBKR_HOST=host.docker.internal  # IBKR Gateway/TWS host
IBKR_PORT=4002                  # 4002=paper, 4001=live
IBKR_ACCOUNT=DU123456           # Your account ID
IBKR_READ_ONLY=true             # Safety flag
```

#### Risk Management
```bash
KILL_PNL_THRESHOLD=-0.05       # -5% PnL kill-switch
MAX_DRAWDOWN_THRESHOLD=0.15     # 15% max drawdown
MIN_PSR_THRESHOLD=0.20          # Minimum PSR
```

#### Strategy Configuration
```bash
SIGNAL_FREQ_SEC=60              # Signal generation interval
MAX_CONCURRENT_ORDERS=10        # Max simultaneous orders
ORDER_TIMEOUT_SEC=30            # Order timeout
```

### Monitoring Configuration

#### Prometheus (`monitoring/prometheus.yml`)
- Scrapes all 3 planes every 10 seconds
- Stores metrics for querying
- Evaluates alert rules every 15 seconds

#### Grafana (`monitoring/grafana/`)
- Auto-configured with Prometheus datasource
- Dashboard provisioning enabled
- Default credentials: `admin/admin`

---

## Common Operations

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f data-plane
docker-compose logs -f strategy-plane
docker-compose logs -f order-plane

# Follow logs with tail
docker-compose logs -f --tail=100 data-plane
```

### Restart a Service
```bash
docker-compose restart data-plane
```

### Stop the System
```bash
./scripts/docker-stop.sh
```

### Complete Cleanup (⚠️ Deletes all data!)
```bash
docker-compose down -v
```

### Rebuild After Code Changes
```bash
# Rebuild specific service
docker-compose build data-plane
docker-compose up -d data-plane

# Rebuild all services
docker-compose build
docker-compose up -d
```

### Execute Commands in Container
```bash
# Open shell in container
docker-compose exec data-plane /bin/bash

# Run Python script
docker-compose exec data-plane python -c "import sys; print(sys.version)"
```

---

## Troubleshooting

### Kafka Not Starting
**Symptoms**: Kafka container keeps restarting

**Solution**:
```bash
# Check Zookeeper is healthy
docker-compose logs zookeeper

# Restart Kafka
docker-compose restart zookeeper
docker-compose restart kafka
```

### Application Plane Not Connecting to Kafka
**Symptoms**: Logs show "Failed to connect to broker"

**Solution**:
```bash
# Verify Kafka is healthy
docker-compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# Check network connectivity
docker-compose exec data-plane ping kafka

# Restart the plane
docker-compose restart data-plane
```

### IBKR Connection Failed
**Symptoms**: "Connection refused" in Data/Order Plane logs

**Solution**:
1. Verify IBKR Gateway/TWS is running on host
2. Check port configuration in `.env`
3. Verify account ID is correct
4. Check IBKR API settings (enable API, trusted IPs)

```bash
# Test connection from container
docker-compose exec data-plane ping host.docker.internal
docker-compose exec data-plane nc -zv host.docker.internal 4002
```

### Prometheus Not Scraping Metrics
**Symptoms**: No data in Grafana

**Solution**:
```bash
# Check Prometheus targets
# Open http://localhost:9090/targets

# Verify plane metrics endpoints
curl http://localhost:8000/metrics
curl http://localhost:8001/metrics
curl http://localhost:8002/metrics

# Restart Prometheus
docker-compose restart prometheus
```

### Out of Disk Space
**Solution**:
```bash
# Clean up unused Docker resources
docker system prune -a

# Remove old volumes (⚠️ deletes data!)
docker volume prune
```

### Container Out of Memory
**Solution**:
Edit `docker-compose.yml` and increase memory limits:
```yaml
services:
  strategy-plane:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

---

## Performance Tuning

### Kafka Performance
```yaml
# docker-compose.yml - Kafka environment
KAFKA_LOG_FLUSH_INTERVAL_MS: 1000
KAFKA_NUM_NETWORK_THREADS: 8
KAFKA_NUM_IO_THREADS: 8
```

### Java Heap Sizes
```yaml
# For memory-constrained environments
environment:
  KAFKA_HEAP_OPTS: "-Xmx2G -Xms2G"
```

---

## Production Deployment

### ⚠️ Security Considerations

**This docker-compose is for DEVELOPMENT/STAGING only!**

For production:
1. **Vault**: Use proper Vault deployment (not dev mode)
2. **Secrets**: Use Docker secrets or external secret management
3. **Network**: Use encrypted overlay networks
4. **TLS**: Enable TLS for Kafka and all services
5. **Authentication**: Enable Kafka SASL/authentication
6. **Monitoring**: Use persistent storage for Prometheus
7. **Backups**: Implement backup strategy for volumes

### Migration to Kubernetes
Use the provided Kubernetes manifests in `k8s/`:
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
```

---

## Monitoring and Alerts

### Key Metrics to Watch

**Data Plane**:
- `data_plane_messages_published_total`: Message throughput
- `data_plane_ibkr_connection_status`: IBKR connectivity
- `data_plane_data_freshness_ms`: Data latency

**Strategy Plane**:
- `strategy_plane_signals_generated_total`: Signal count
- `strategy_plane_pnl_current`: Current PnL
- `strategy_plane_kill_switch_active`: Kill-switch status

**Order Plane**:
- `order_plane_orders_submitted_total`: Order count
- `order_plane_fills_total`: Fill count
- `order_plane_rejection_total`: Rejection count

### Grafana Dashboards

Access Grafana at http://localhost:3000

**Pre-configured dashboards** (when created):
- System Health Overview
- Trading Performance
- Risk Metrics
- Data Quality

---

## Backup and Recovery

### Backup Volumes
```bash
# Backup all data volumes
docker run --rm \
  -v algo-trade_data-plane-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/data-plane-$(date +%Y%m%d).tar.gz /data
```

### Restore from Backup
```bash
# Stop services first
./scripts/docker-stop.sh

# Restore volume
docker run --rm \
  -v algo-trade_data-plane-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/data-plane-20231107.tar.gz -C /
```

---

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Kafka in Docker](https://docs.confluent.io/platform/current/installation/docker/)

---

## Support

For issues with the Docker setup:
1. Check logs: `docker-compose logs [service]`
2. Verify health: `docker-compose ps`
3. Review this guide's troubleshooting section
4. Check GitHub issues

---

**Status**: Docker infrastructure complete and ready for deployment
**Last Updated**: 2025-11-16
