# AlgoTrader Docker Environment

This directory contains all the Docker configuration and infrastructure for the AlgoTrader platform.

## Overview

The AlgoTrader platform is containerized using Docker and orchestrated with Docker Compose. The architecture consists of:

### Core Services (The Three Planes)
1. **Data Plane** - Market data ingestion, normalization, and quality assurance
2. **Strategy Plane** - Signal generation, portfolio optimization, and decision making
3. **Order Plane** - Order execution, risk checks, and transaction cost learning

### Infrastructure Services
- **Kafka** - Message bus for inter-plane communication
- **Zookeeper** - Kafka coordination service
- **Prometheus** - Metrics collection and storage
- **Grafana** - Metrics visualization and dashboards
- **Kafka UI** - Web interface for Kafka monitoring

## Quick Start

### Prerequisites

- Docker Engine 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose 2.0+ ([Install Docker Compose](https://docs.docker.com/compose/install/))
- At least 8GB of available RAM
- At least 20GB of available disk space

### Initial Setup

1. **Copy the environment file**
   ```bash
   cp .env.example .env
   ```

2. **Configure your settings in `.env`**

   Key settings to configure:
   - `IBKR_HOST` - Interactive Brokers TWS/Gateway host (default: 127.0.0.1)
   - `IBKR_PORT` - IBKR port (7497 for TWS paper, 4002 for Gateway paper)
   - `GRAFANA_ADMIN_PASSWORD` - Grafana admin password
   - `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)

3. **Start the services**
   ```bash
   # Using the helper script (recommended)
   ./docker/docker-helper.sh start

   # Or using docker-compose directly
   docker-compose up -d
   ```

4. **Verify all services are running**
   ```bash
   ./docker/docker-helper.sh status
   ```

## Service URLs

Once the services are running, you can access:

- **Grafana Dashboard**: http://localhost:3000
  - Default credentials: `admin` / `admin` (change on first login)

- **Prometheus**: http://localhost:9090
  - Query metrics and view targets

- **Kafka UI**: http://localhost:8090
  - Monitor Kafka topics and messages

- **Metrics Endpoints**:
  - Data Plane: http://localhost:8000/metrics
  - Strategy Plane: http://localhost:8001/metrics
  - Order Plane: http://localhost:8002/metrics

## Helper Script Usage

The `docker-helper.sh` script provides convenient commands for managing the environment:

```bash
# Start all services
./docker/docker-helper.sh start

# Stop all services
./docker/docker-helper.sh stop

# Restart all services
./docker/docker-helper.sh restart

# View logs (all services)
./docker/docker-helper.sh logs

# View logs for specific service
./docker/docker-helper.sh logs data-plane

# Check service status
./docker/docker-helper.sh status

# Rebuild images
./docker/docker-helper.sh build

# Clean everything (removes volumes)
./docker/docker-helper.sh clean

# Show service URLs
./docker/docker-helper.sh urls

# Show help
./docker/docker-helper.sh help
```

## Docker Compose Commands

If you prefer to use docker-compose directly:

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f data-plane

# Restart a service
docker-compose restart strategy-plane

# Rebuild and restart
docker-compose up -d --build

# Scale a service (if needed)
docker-compose up -d --scale strategy-plane=2
```

## Directory Structure

```
docker/
├── README.md                          # This file
├── docker-helper.sh                   # Helper script for common operations
├── entrypoint/
│   └── entrypoint.sh                  # Service initialization script
├── healthcheck/
│   └── health.py                      # Health check script
├── prometheus/
│   └── prometheus.yml                 # Prometheus configuration
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── prometheus.yml         # Auto-configure Prometheus datasource
    │   └── dashboards/
    │       └── default.yml            # Dashboard provisioning config
    └── dashboards/
        └── algotrader-overview.json   # Main AlgoTrader dashboard
```

## Configuration

### Environment Variables

All environment variables are configured in the `.env` file. See `.env.example` for a complete list of available options.

#### Critical Settings

```bash
# Application Environment
APP_ENV=development          # development, staging, production
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR, CRITICAL

# IBKR Configuration
IBKR_HOST=127.0.0.1         # TWS/Gateway host
IBKR_PORT=7497              # TWS/Gateway port
IBKR_CLIENT_ID=1            # Client ID for IBKR connection

# Risk Limits
MAX_GROSS_EXPOSURE=1000000  # Maximum gross exposure in USD
MAX_NET_EXPOSURE=500000     # Maximum net exposure in USD
MAX_POSITION_SIZE=100000    # Maximum single position size

# Feature Flags
ENABLE_PAPER_TRADING=true   # Enable paper trading mode
ENABLE_LIVE_TRADING=false   # Enable live trading (USE WITH CAUTION)
```

### Kafka Topics

The following Kafka topics are auto-created:

- `market_events` - Market data events from Data Plane
- `ofi_events` - Order Flow Imbalance events
- `order_intents` - Order intents from Strategy Plane
- `exec_reports` - Execution reports from Order Plane

### Volume Mounts

The following directories are mounted as volumes:

- `./data` → `/app/data` - Data storage (CSV, Parquet files)
- `./logs` → `/app/logs` - Application logs
- `./config` → `/app/config` - Configuration files

## Monitoring

### Prometheus

Prometheus scrapes metrics from all three planes every 5 seconds. Access the Prometheus UI at http://localhost:9090 to:

- Query metrics using PromQL
- View active targets
- Check alerts (if configured)

Example queries:

```promql
# Message processing rate (Data Plane)
rate(data_plane_messages_processed_total[1m])

# Signal generation rate (Strategy Plane)
rate(strategy_plane_signals_generated_total[1m])

# Order placement rate (Order Plane)
rate(order_plane_orders_placed_total[1m])

# Total PnL
strategy_plane_pnl_total
```

### Grafana

Grafana provides pre-configured dashboards for monitoring the AlgoTrader platform. Access Grafana at http://localhost:3000.

**Default Dashboard**: AlgoTrader Overview

The dashboard includes:
- Message processing rates
- Signal generation metrics
- Order execution metrics
- PnL tracking
- System health indicators

To create custom dashboards:
1. Navigate to Dashboards → New Dashboard
2. Add panels with Prometheus queries
3. Save the dashboard

## Troubleshooting

### Services Not Starting

1. **Check Docker is running**
   ```bash
   docker info
   ```

2. **Check service logs**
   ```bash
   ./docker/docker-helper.sh logs
   ```

3. **Verify port availability**
   ```bash
   netstat -tulpn | grep -E '(3000|8090|9090|9092|8000|8001|8002)'
   ```

### Kafka Connection Issues

1. **Verify Kafka is healthy**
   ```bash
   docker-compose ps kafka
   ```

2. **Check Kafka logs**
   ```bash
   docker-compose logs kafka
   ```

3. **Test Kafka connectivity**
   ```bash
   docker exec -it algotrader-kafka kafka-broker-api-versions --bootstrap-server localhost:9092
   ```

### IBKR Connection Issues

1. **Ensure TWS/IB Gateway is running**
   - For paper trading: Use TWS Paper Trading or IB Gateway Paper
   - Port 7497 for TWS, 4002 for Gateway

2. **Check IBKR settings**
   - Enable API connections in TWS/Gateway settings
   - Configure "Trusted IPs" if needed
   - Set correct port in `.env` file

3. **Verify connectivity**
   ```bash
   # From data-plane container
   docker exec -it algotrader-data-plane nc -zv $IBKR_HOST $IBKR_PORT
   ```

### High Resource Usage

1. **Check container resource usage**
   ```bash
   docker stats
   ```

2. **Limit container resources** (add to docker-compose.yml):
   ```yaml
   services:
     data-plane:
       deploy:
         resources:
           limits:
             cpus: '2'
             memory: 2G
   ```

3. **Adjust Kafka settings** for lower memory usage:
   ```yaml
   environment:
     KAFKA_HEAP_OPTS: "-Xmx512M -Xms256M"
   ```

### Clean Start

If you encounter persistent issues, perform a clean start:

```bash
# Stop all services
./docker/docker-helper.sh stop

# Remove all volumes (WARNING: This deletes all data)
./docker/docker-helper.sh clean

# Rebuild images
./docker/docker-helper.sh build

# Start services
./docker/docker-helper.sh start
```

## Development

### Building Custom Images

To build images with development dependencies:

```bash
# Set INSTALL_DEV in .env
INSTALL_DEV=true

# Rebuild images
docker-compose build --no-cache
docker-compose up -d
```

### Running Tests

```bash
# Run tests in data-plane container
docker exec -it algotrader-data-plane pytest tests/

# Run tests with coverage
docker exec -it algotrader-data-plane pytest --cov=data_plane tests/
```

### Interactive Shell

```bash
# Access data-plane container
docker exec -it algotrader-data-plane bash

# Access strategy-plane container
docker exec -it algotrader-strategy-plane bash

# Access order-plane container
docker exec -it algotrader-order-plane bash
```

## Production Deployment

For production deployment, consider the following:

1. **Use production-grade secrets management**
   - AWS Secrets Manager
   - HashiCorp Vault
   - Kubernetes Secrets

2. **Enable TLS/SSL**
   - Use reverse proxy (Nginx, Traefik)
   - Configure TLS certificates
   - Enable HTTPS for all endpoints

3. **Configure persistent volumes**
   - Use external volume drivers
   - Set up backup strategies
   - Configure replication

4. **Set resource limits**
   - Define CPU and memory limits
   - Configure restart policies
   - Set up health checks

5. **Enable logging aggregation**
   - Use ELK stack, Loki, or CloudWatch
   - Configure log rotation
   - Set retention policies

6. **Security hardening**
   - Run containers as non-root user ✓ (already configured)
   - Use read-only root filesystems where possible
   - Scan images for vulnerabilities
   - Keep images updated

## Support

For issues and questions:

- Check the main project README
- Review service logs: `./docker/docker-helper.sh logs`
- Open an issue on GitHub

## License

See main project LICENSE file.
