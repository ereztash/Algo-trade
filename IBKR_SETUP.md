# IBKR Integration Setup Guide

Complete guide for setting up Interactive Brokers (IBKR) integration with the AlgoTrader platform for paper trading and live trading.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [TWS/Gateway Installation](#twsgateway-installation)
3. [API Configuration](#api-configuration)
4. [Paper Trading Setup](#paper-trading-setup)
5. [Connection Testing](#connection-testing)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Configuration](#advanced-configuration)

---

## Prerequisites

### Required Software

- **Interactive Brokers Account** (Paper Trading or Live)
- **TWS (Trader Workstation)** or **IB Gateway** - Latest version
- **Python 3.9+** with `ib_insync` library
- **AlgoTrader Platform** with Docker (optional but recommended)

### Install Dependencies

```bash
# Install ib_insync
pip install ib_insync>=0.9.86

# Or install all requirements
pip install -r requirements.txt
```

---

## TWS/Gateway Installation

### Option 1: TWS (Trader Workstation) - Recommended for Beginners

1. **Download TWS**
   - Visit: https://www.interactivebrokers.com/en/trading/tws.php
   - Download latest stable version for your OS

2. **Install TWS**
   - Run installer and follow prompts
   - Accept license agreement
   - Choose installation directory

3. **Launch TWS**
   - **Paper Trading**: Login with paper trading credentials
   - **Live Trading**: Login with live account credentials

### Option 2: IB Gateway - Recommended for Production

1. **Download IB Gateway**
   - Visit: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
   - Download latest stable version

2. **Install IB Gateway**
   - Lighter weight than TWS
   - Headless operation (no GUI required)
   - Better for production servers

3. **Launch IB Gateway**
   - Start with paper or live credentials

---

## API Configuration

### Enable API Access in TWS

1. **Open TWS/Gateway**

2. **Navigate to API Settings**
   - TWS: File → Global Configuration → API → Settings
   - Gateway: Configure → Settings → API → Settings

3. **Configure API Settings**

   **Required Settings:**
   - ☑ Enable ActiveX and Socket Clients
   - ☑ Allow connections from localhost
   - ☑ Read-Only API (recommended for testing)

   **Socket Port:**
   - Paper TWS: **7497** (default)
   - Live TWS: **7496** (default)
   - Paper Gateway: **4002** (default)
   - Live Gateway: **4001** (default)

   **Master API Client ID:** Leave blank (0) or specify if needed

   **Trusted IPs:** Add `127.0.0.1` (localhost)

4. **Apply and Restart**
   - Click OK/Apply
   - Restart TWS/Gateway for changes to take effect

### Important Security Notes

⚠️ **Never expose API ports to the internet!**
- Always use localhost (127.0.0.1)
- Use firewall rules if needed
- Enable read-only mode for testing
- Use separate client IDs for each connection

---

## Paper Trading Setup

### Step 1: Get Paper Trading Account

1. **Request Paper Trading Account**
   - Login to IBKR Client Portal
   - Go to Account Management
   - Request Paper Trading Account
   - Wait for approval (usually instant)

2. **Note Credentials**
   - Paper trading username
   - Paper trading password
   - These are different from live account credentials

### Step 2: Configure AlgoTrader

1. **Update Environment Variables**

   Edit `.env` file:

   ```bash
   # IBKR Configuration
   IBKR_HOST=127.0.0.1
   IBKR_PORT=7497              # TWS Paper Trading
   IBKR_CLIENT_ID=1

   # Use 4002 for IB Gateway Paper Trading
   # IBKR_PORT=4002

   # Risk Management
   ENABLE_PAPER_TRADING=true
   ENABLE_LIVE_TRADING=false   # Keep false for paper trading!
   ```

2. **Update IBKR Config File**

   Edit `config/ibkr_config.yaml`:

   ```yaml
   # Use paper_trading environment
   default_environment: "paper_trading"

   paper_trading:
     host: "127.0.0.1"
     port: 7497
     client_id_data: 1
     client_id_exec: 2
     account: null  # Auto-detected
     readonly: false
     auto_reconnect: true
   ```

### Step 3: Test Connection

```bash
# Run validation script
python scripts/validate_paper_trading.py

# Or with Docker
docker exec -it algotrader-data-plane python scripts/validate_paper_trading.py
```

Expected output:
```
✅ Connected to IBKR at 127.0.0.1:7497
✅ Account summary retrieved
   Account Details:
   ├─ Net Liquidation: $1,000,000.00
   ├─ Cash: $1,000,000.00
   └─ Buying Power: $4,000,000.00
```

---

## Connection Testing

### Manual Connection Test

```python
from algo_trade.core.execution.IBKR_handler import IBKRHandler

# Create handler
handler = IBKRHandler(
    host='127.0.0.1',
    port=7497,        # Paper trading
    client_id=999,
    readonly=True     # Read-only for safety
)

# Connect
success = handler.connect()
print(f"Connected: {success}")

# Get account info
if success:
    summary = handler.get_account_summary()
    print(f"NAV: ${summary['net_liquidation']:,.2f}")

    positions = handler.get_positions()
    print(f"Positions: {len(positions)}")

    handler.disconnect()
```

### Integration Test

```bash
# Run IBKR integration tests
pytest tests/integration/test_ibkr_integration.py -m "requires_ibkr" -v

# Run with full output
pytest tests/integration/test_ibkr_integration.py::TestIBKRHandlerIntegration::test_connection -v -s
```

### Full Validation

```bash
# Run complete validation (includes test order)
python scripts/validate_paper_trading.py --full-test
```

---

## Troubleshooting

### Common Issues

#### 1. Connection Refused

**Error:** `ConnectionRefusedError: [Errno 111] Connection refused`

**Solutions:**
- Ensure TWS/Gateway is running
- Verify correct port number (7497 for paper TWS)
- Check API settings are enabled
- Confirm localhost (127.0.0.1) connections allowed
- Restart TWS/Gateway after changing settings

#### 2. API Not Enabled

**Error:** `error code 504: Not connected`

**Solutions:**
- Enable API in TWS settings (see [API Configuration](#api-configuration))
- Click "Enable ActiveX and Socket Clients"
- Restart TWS/Gateway

#### 3. Client ID Conflict

**Error:** `error code 326: Client ID already in use`

**Solutions:**
- Use different client ID for each connection
- Data Plane: client_id=1
- Order Plane: client_id=2
- Manual tests: client_id=999
- Wait 30 seconds between connections with same ID

#### 4. Read-Only API

**Error:** `error code 200: No security definition has been found`

**Solutions:**
- Uncheck "Read-Only API" in TWS settings
- Or use `readonly=True` in handler initialization
- Restart TWS after changing

#### 5. Account Not Found

**Error:** Account returns empty or None

**Solutions:**
- Wait a few seconds after connection
- Specify account manually: `account="DU123456"`
- Check paper trading account is active
- Verify logged into correct account

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

handler = IBKRHandler(port=7497)
handler.connect()
```

### Check TWS Logs

- TWS: Help → Support Tools → Activity Log
- Look for connection attempts
- Check for error codes

---

## Advanced Configuration

### Multiple Connections

Use different client IDs for concurrent connections:

```python
# Data Plane (Market Data)
data_handler = IBKRHandler(port=7497, client_id=1)

# Order Plane (Execution)
exec_handler = IBKRHandler(port=7497, client_id=2)

# Manual Testing
test_handler = IBKRHandler(port=7497, client_id=999)
```

### Automatic Reconnection

```python
handler = IBKRHandler(
    port=7497,
    auto_reconnect=True,        # Enable auto-reconnect
    max_reconnect_attempts=5    # Max 5 attempts
)

# Handler will automatically reconnect on disconnection
# Uses exponential backoff: 2s, 4s, 8s, 16s, 32s
```

### Event Callbacks

```python
handler = IBKRHandler(port=7497)

# Register callbacks
handler.on_connected(lambda: print("Connected!"))
handler.on_disconnected(lambda: print("Disconnected!"))
handler.on_error(lambda req, code, msg, contract: print(f"Error {code}: {msg}"))

handler.connect()
```

### Context Manager

```python
# Automatic connection and disconnection
with IBKRHandler(port=7497) as handler:
    summary = handler.get_account_summary()
    positions = handler.get_positions()
    # Auto-disconnects on exit
```

---

## Production Checklist

Before deploying to production:

- [ ] Test thoroughly in paper trading environment
- [ ] Verify all risk limits are configured correctly
- [ ] Enable kill-switches (PnL, drawdown, PSR)
- [ ] Set up monitoring and alerting
- [ ] Document emergency shutdown procedures
- [ ] Test reconnection logic
- [ ] Verify order throttling (POV/ADV limits)
- [ ] Review and test error handling
- [ ] Set up backup internet connection
- [ ] Configure firewall rules
- [ ] Implement proper logging
- [ ] Set up backup IBKR Gateway instance
- [ ] Test disaster recovery procedures

### Recommended Settings for Production

```yaml
# config/ibkr_config.yaml
production:
  host: "127.0.0.1"
  port: 7496  # Live TWS or 4001 for Gateway
  client_id_data: 1
  client_id_exec: 2
  account: "U1234567"  # Specify account explicitly
  readonly: false
  auto_reconnect: true
  max_reconnect_attempts: 3  # Lower for production
  timeout: 10

  # Strict order settings
  order_settings:
    default_order_type: "LIMIT"
    limit_offset_percent: 0.001
    time_in_force: "DAY"
    outside_rth: false

  # Health monitoring
  health_check:
    interval_seconds: 30
    timeout_seconds: 5
    alert_on_disconnect: true
```

---

## Resources

- **IB API Documentation**: https://interactivebrokers.github.io/tws-api/
- **ib_insync Documentation**: https://ib-insync.readthedocs.io/
- **TWS Download**: https://www.interactivebrokers.com/en/trading/tws.php
- **IB Gateway Download**: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php
- **IBKR API Forum**: https://groups.io/g/twsapi

---

## Support

For issues specific to:

- **TWS/Gateway**: Contact IBKR support
- **API Configuration**: Check IBKR API documentation
- **AlgoTrader Integration**: Open GitHub issue or check logs

---

**Last Updated**: November 2025
**Platform Version**: AlgoTrader v1.0
