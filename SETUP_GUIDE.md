# Paper Trading Environment - Quick Setup Guide

This guide will help you get the Paper Trading environment up and running quickly.

## 📋 Prerequisites

1. **Docker & Docker Compose** installed
2. **Python 3.10+** installed
3. **Git** (already installed)

## 🚀 Quick Start (5 minutes)

### Step 1: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Step 2: Set Up Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and fill in required values (especially IBKR_ACCOUNT_ID)
# For initial testing, you can leave most values as defaults
```

### Step 3: Start Kafka Infrastructure

```bash
# Start Kafka, Zookeeper, Prometheus, Grafana, and Kafka UI
docker-compose up -d

# Wait for services to be ready (takes ~30 seconds)
docker-compose ps

# Check logs if needed
docker-compose logs -f kafka
```

### Step 4: Create Kafka Topics

```bash
# Run the topic initialization script
./scripts/init-kafka-topics.sh

# Verify topics were created
docker-compose exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list
```

### Step 5: Verify Setup

Access the monitoring dashboards:

- **Kafka UI:** http://localhost:8080 (view topics, messages, consumer groups)
- **Prometheus:** http://localhost:9090 (metrics database)
- **Grafana:** http://localhost:3000 (dashboards - login: admin/admin)

## 🔌 IBKR Paper Account Setup

### Prerequisites
You need an Interactive Brokers Paper Trading account to run the full system.

### Steps:

1. **Sign up for IBKR Paper Trading:**
   - Go to: https://www.interactivebrokers.com/en/trading/paper-trading.php
   - Create a Paper Trading account
   - Note your account ID (starts with `DU`, e.g., `DU1234567`)

2. **Install TWS or IB Gateway:**
   - Download from: https://www.interactivebrokers.com/en/trading/tws.php
   - Choose IB Gateway (lighter) or TWS (full platform)
   - Install and launch

3. **Configure API Access:**
   - In TWS/Gateway: Edit → Global Configuration → API → Settings
   - Enable "Enable ActiveX and Socket Clients"
   - Add trusted IP: `127.0.0.1`
   - Set Socket Port:
     - **Paper Trading:** Port `4002` (Gateway) or `7497` (TWS)
     - **Live Trading:** Port `4001` (Gateway) or `7496` (TWS) - DO NOT USE YET
   - Read-Only API: **No** (we need order placement)
   - Click OK and restart TWS/Gateway

4. **Update .env File:**
   ```bash
   IBKR_HOST=127.0.0.1
   IBKR_PORT=4002                    # Paper Gateway
   IBKR_ACCOUNT_ID=DU1234567         # Your account ID
   IBKR_PAPER_MODE=true              # CRITICAL: Must be true
   ```

5. **Test Connection:**
   ```bash
   # Run Stage 6 validation (read-only test)
   python tests/stages/stage6_account_probe.py
   ```

## 📊 Running the System

### Development Mode (with mocks - no IBKR needed)

```bash
# Set mock mode in .env
MOCK_MODE=true

# Start Data Plane
python -m data_plane.app.main

# In another terminal, start Strategy Plane
python -m apps.strategy_loop.main

# In another terminal, start Order Plane
python -m order_plane.app.main
```

### Paper Trading Mode (with real IBKR Paper account)

**Prerequisites:**
- IBKR Paper account created
- TWS/Gateway running and connected
- API access configured

```bash
# Ensure MOCK_MODE=false in .env
MOCK_MODE=false
IBKR_PAPER_MODE=true

# Start all planes (same as dev mode)
python -m data_plane.app.main
python -m apps.strategy_loop.main
python -m order_plane.app.main
```

## 🧪 Testing & Validation

### Unit Tests
```bash
# Run all unit tests
pytest tests/

# Run specific test file
pytest tests/test_schema_validation.py

# Run with coverage
pytest --cov=. tests/
```

### Integration Tests
```bash
# Run end-to-end tests (uses mock IBKR)
pytest tests/e2e/

# Run specific E2E test
pytest tests/e2e/test_full_flow.py
```

### Stage 6: Account Config Probe (Read-Only)
```bash
# Validates IBKR Paper account connectivity
# READ-ONLY mode - no orders placed
python tests/stages/stage6_account_probe.py
```

### Stage 7: 6-Hour Paper Trading Validation
```bash
# Full 6-hour trading session
# Generates real orders in Paper account
# ONLY run after Stage 6 passes
python tests/stages/stage7_paper_trading.py
```

## 📈 Monitoring

### Kafka Monitoring
- **Kafka UI:** http://localhost:8080
  - View topics, partitions, messages
  - Monitor consumer groups and lag
  - Inspect message contents

### Application Metrics
- **Prometheus:** http://localhost:9090
  - Query metrics directly
  - View targets and health

- **Grafana:** http://localhost:3000
  - Username: `admin`
  - Password: `admin` (change in .env: `GRAFANA_ADMIN_PASSWORD`)
  - Pre-configured dashboards for Kafka, trading metrics, system health

### Logs
```bash
# View all logs
tail -f logs/algo-trade.log

# View specific plane logs
docker-compose logs -f data-plane
docker-compose logs -f strategy-plane
docker-compose logs -f order-plane
```

## 🛠️ Troubleshooting

### Kafka won't start
```bash
# Check if port 9092 is already in use
lsof -i :9092

# Remove old volumes and restart
docker-compose down -v
docker-compose up -d
```

### IBKR connection fails
- Ensure TWS/Gateway is running
- Verify API access is enabled in TWS/Gateway settings
- Check port is correct (4002 for Paper Gateway)
- Verify account ID in .env matches TWS login
- Check TWS/Gateway logs for errors

### Topics not created
```bash
# Re-run topic initialization
./scripts/init-kafka-topics.sh

# Check Kafka logs
docker-compose logs kafka
```

### Missing dependencies
```bash
# Reinstall all dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Or reinstall specific package
pip install confluent-kafka ib-insync
```

## 🔒 Security Checklist

Before deploying:

- [ ] Change Grafana admin password (in .env)
- [ ] Never commit .env file to git
- [ ] Keep IBKR_HOST=127.0.0.1 (localhost only)
- [ ] Use Vault for production credentials
- [ ] Enable Kafka SASL/SSL for production
- [ ] Keep IBKR_PAPER_MODE=true until all validations pass
- [ ] Review risk limits in .env (PnL kill-switch, drawdown, position sizing)

## 📚 Next Steps

1. **Complete Phase 1 (Week 1):**
   - ✅ Dependencies installed
   - ✅ Docker infrastructure running
   - ⏳ Implement KafkaAdapter (next task)
   - ⏳ Implement IBKR Handler (next task)

2. **Phase 2 (Week 2):**
   - End-to-end integration testing
   - Performance tuning
   - Monitoring setup

3. **Phase 3 (Week 3):**
   - IBKR Paper account setup (manual)
   - Stage 6 validation
   - Stage 7 preparation

4. **Phase 4 (Week 4):**
   - Execute Stage 7 (6-hour Paper session)
   - Post-session analysis
   - Go-Live Decision Gate

## 📖 Reference Documents

- **Full Setup Plan:** `/PAPER_TRADING_SETUP_PLAN.md`
- **IBKR Integration:** `/docs/IBKR_INTEGRATION_FLOW.md`
- **Runbook:** `/docs/RUNBOOK.md`
- **Message Contracts:** `/contracts/README.md`

## 🆘 Getting Help

- **Check logs:** `docker-compose logs -f [service_name]`
- **Kafka UI:** http://localhost:8080 for message inspection
- **Review documentation:** See `/docs/` directory
- **Run tests:** `pytest tests/ -v` for detailed error messages

---

**Current Status:** Phase 1 - Infrastructure Ready ✅
**Next Task:** Implement KafkaAdapter and IBKR Handler
