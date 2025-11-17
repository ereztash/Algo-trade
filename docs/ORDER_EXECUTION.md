# Order Execution System - IBKR Integration

## Overview

The Order Execution system implements the complete flow of order placement and tracking with Interactive Brokers (IBKR). This enables live and paper trading through the Order Plane.

### Architecture

```
Strategy Plane                Order Plane                IBKR
     │                            │                       │
     │  ┌──────────────┐          │                       │
     ├─→│ OrderIntent  │──────────┤                       │
     │  └──────────────┘          │                       │
     │                             │                       │
     │                    ┌────────▼────────┐             │
     │                    │  Risk Checks    │             │
     │                    │  + Throttling   │             │
     │                    └────────┬────────┘             │
     │                             │                       │
     │                    ┌────────▼────────┐             │
     │                    │ IBKRExecClient  │             │
     │                    │   .place()      │─────────────┤
     │                    └────────┬────────┘             │
     │                             │                   Submit
     │                             │                   Order
     │                    ┌────────▼────────┐             │
     │                    │ Order Tracking  │             │
     │                    │ (intent ↔ ID)   │             │
     │                    └────────┬────────┘             │
     │                             │                       │
     │                    ┌────────▼────────┐             │
     │                    │ .poll_reports() │◄────────────┤
     │                    └────────┬────────┘         Fill
     │                             │                  Events
     │  ┌──────────────┐           │                       │
     │◄─│ExecutionRpt  │◄──────────┤                       │
     │  └──────────────┘           │                       │
```

## Components

### 1. IBKRExecClient

Main execution client that handles order placement and tracking.

**Location:** `order_plane/broker/ibkr_exec_client.py`

**Key Methods:**
- `connect()` - Connect to IBKR TWS/Gateway
- `place(intent)` - Place order from OrderIntent
- `poll_reports()` - Get execution reports
- `cancel(order_id)` - Cancel an order
- `disconnect()` - Disconnect from IBKR

### 2. TrackedOrder

Internal data structure for tracking order lifecycle.

**Fields:**
- `intent_id` - Links to original OrderIntent
- `order_id` - IBKR order ID
- `status` - Current order status
- `filled_quantity` - Amount filled so far
- `average_fill_price` - Average execution price
- `fills` - List of individual fill records
- Timestamps for latency tracking

### 3. Message Contracts

**OrderIntent** (Strategy → Order Plane)
```python
{
  "event_type": "order_intent",
  "intent_id": "UUID",
  "symbol": "AAPL",
  "direction": "BUY",
  "quantity": 100,
  "order_type": "MARKET",  # or LIMIT, STOP, STOP_LIMIT, ADAPTIVE
  "limit_price": 150.00,   # required for LIMIT orders
  "timestamp": "2025-11-17T...",
  "strategy_id": "COMPOSITE",
  "time_in_force": "DAY",  # DAY, GTC, IOC, FOK
  "urgency": "NORMAL"
}
```

**ExecutionReport** (Order Plane → Strategy)
```python
{
  "event_type": "execution_report",
  "report_id": "UUID",
  "intent_id": "UUID",      # Links back to OrderIntent
  "order_id": "IBKR_12345", # Broker order ID
  "symbol": "AAPL",
  "status": "FILLED",       # SUBMITTED, ACKNOWLEDGED, PARTIAL_FILL, FILLED, etc.
  "filled_quantity": 100,
  "average_fill_price": 150.25,
  "commission": 1.50,
  "latency_metrics": {
    "intent_to_submit_ms": 50,
    "submit_to_ack_ms": 120,
    "ack_to_fill_ms": 250,
    "total_latency_ms": 420
  }
}
```

## Configuration

### IBKR Connection Config

```python
config = {
    'host': '127.0.0.1',      # IBKR Gateway/TWS host
    'port': 7497,             # 7497 = paper, 7496 = live
    'client_id': 1,           # Unique client ID
    'account': None,          # Optional: IBKR account number
    'timeout': 10             # Connection timeout (seconds)
}
```

### Prerequisites

1. **Install IBKR Gateway or TWS**
   - Download from Interactive Brokers
   - Configure for paper or live trading

2. **Enable API Access**
   - In TWS/Gateway: Edit → Global Configuration → API → Settings
   - Enable "ActiveX and Socket Clients"
   - Set socket port: 7497 (paper) or 7496 (live)
   - Add trusted IP: 127.0.0.1

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Example

```python
import asyncio
from datetime import datetime
from uuid import uuid4
from order_plane.broker.ibkr_exec_client import IBKRExecClient
from contracts.validators import OrderIntent

async def place_market_order():
    # Create order intent
    intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100,
        order_type='MARKET',
        timestamp=datetime.utcnow(),
        strategy_id='COMPOSITE',
    )

    # Initialize client
    config = {'host': '127.0.0.1', 'port': 7497, 'client_id': 1}
    client = IBKRExecClient(config)

    try:
        # Connect
        await client.connect()

        # Place order
        order_id = await client.place(intent)
        print(f"Order placed: {order_id}")

        # Poll for fills
        for _ in range(30):  # Poll for 30 seconds
            await asyncio.sleep(1.0)
            reports = await client.poll_reports()

            for report in reports:
                print(f"Status: {report.status}")
                if report.status == 'FILLED':
                    print(f"Filled {report.filled_quantity} @ ${report.average_fill_price}")
                    return report

    finally:
        await client.disconnect()

# Run
asyncio.run(place_market_order())
```

### Order Types

#### MARKET Order
```python
intent = OrderIntent(
    intent_id=str(uuid4()),
    symbol='AAPL',
    direction='BUY',
    quantity=100,
    order_type='MARKET',
    timestamp=datetime.utcnow(),
    strategy_id='COMPOSITE',
)
```

#### LIMIT Order
```python
intent = OrderIntent(
    intent_id=str(uuid4()),
    symbol='TSLA',
    direction='SELL',
    quantity=50,
    order_type='LIMIT',
    limit_price=245.50,  # Required!
    time_in_force='GTC',
    timestamp=datetime.utcnow(),
    strategy_id='OFI',
)
```

#### STOP_LIMIT Order
```python
intent = OrderIntent(
    intent_id=str(uuid4()),
    symbol='SPY',
    direction='BUY',
    quantity=200,
    order_type='STOP_LIMIT',
    stop_price=450.00,   # Trigger price
    limit_price=451.00,  # Limit price after trigger
    timestamp=datetime.utcnow(),
    strategy_id='VRP',
)
```

### Order Cancellation

```python
# Cancel an order
success = await client.cancel(order_id)

if success:
    print("Order cancelled")
else:
    print("Cancellation failed (order may be filled)")
```

## Order Status Flow

```
PENDING → SUBMITTED → ACKNOWLEDGED → PARTIAL_FILL → FILLED
                  ↓                       ↓
              REJECTED                CANCELED
```

**Status Descriptions:**
- `PENDING` - Order created, not yet submitted
- `SUBMITTED` - Order sent to broker
- `ACKNOWLEDGED` - Broker confirmed receipt
- `PARTIAL_FILL` - Partially filled (quantity < requested)
- `FILLED` - Fully filled
- `CANCELED` - Order cancelled
- `REJECTED` - Broker rejected order
- `TIMEOUT` - Order timed out
- `ERROR` - Error occurred

## Latency Tracking

The system automatically tracks latency at each stage:

```python
latency_metrics = report.latency_metrics

print(f"Intent → Submit: {latency_metrics.intent_to_submit_ms}ms")
print(f"Submit → Ack: {latency_metrics.submit_to_ack_ms}ms")
print(f"Ack → Fill: {latency_metrics.ack_to_fill_ms}ms")
print(f"Total: {latency_metrics.total_latency_ms}ms")
```

## Integration with Order Plane Orchestrator

The orchestrator integrates the execution client:

```python
# order_plane/app/orchestrator.py

async def run_order_plane(bus, ib_exec, logger, metrics):
    async for intent in bus.consume("order_intents"):
        # 1. Risk checks
        if not risk_checker.validate(intent, limits):
            logger.warn("risk_reject")
            continue

        # 2. Throttling
        if exceeds_pov(intent):
            intent = downscale_qty(intent)

        # 3. Place order
        try:
            order_id = await ib_exec.place(intent)
            logger.info("placed_order", order_id=order_id)
        except Exception as e:
            logger.error("place_failed", reason=str(e))

    # Separate task polls for reports
    async for rpt in ib_exec.poll_reports():
        await bus.publish("exec_reports", rpt)
```

## Error Handling

### Connection Errors
```python
try:
    await client.connect()
except ConnectionError as e:
    print(f"Failed to connect: {e}")
    # Retry logic or alert
```

### Order Placement Errors
```python
try:
    order_id = await client.place(intent)
except ValueError as e:
    # Invalid order parameters
    print(f"Order validation failed: {e}")
except ConnectionError as e:
    # Not connected to IBKR
    print(f"Connection error: {e}")
```

### Order Rejection
```python
for report in reports:
    if report.status == 'REJECTED':
        print(f"Order rejected: {report.reject_reason}")
        # Handle rejection (alert, retry, etc.)
```

## Testing

### Unit Tests
```bash
pytest tests/test_ibkr_exec_client.py -v
```

### Integration Tests with Mock
```bash
python examples/order_execution_example.py --mock
```

### Live Paper Trading
```bash
# Make sure TWS/Gateway is running on port 7497
python examples/order_execution_example.py --live
```

## Performance Metrics

Expected latencies (paper trading):
- Intent → Submit: 10-50ms
- Submit → Ack: 50-200ms
- Ack → Fill (MARKET): 100-500ms
- Total: 200-800ms

For live trading, latencies may be higher depending on market conditions.

## Monitoring

The client provides health status:

```python
health = client.health()

{
  "connected": True,
  "session": "exec",
  "tracked_orders": 5,
  "host": "127.0.0.1",
  "port": 7497,
  "client_id": 1
}
```

## Security Notes

1. **API Credentials**: IBKR API uses IP whitelisting, not credentials
2. **Firewall**: Ensure firewall allows localhost connections
3. **Paper vs Live**: Double-check port configuration!
   - 7497 = Paper trading (safe for testing)
   - 7496 = Live trading (real money!)

## Troubleshooting

### "Not connected to IBKR"
- Ensure TWS/Gateway is running
- Check API settings are enabled
- Verify port number (7497 for paper, 7496 for live)
- Check firewall settings

### "Order submission timeout"
- IBKR may be slow to respond
- Check network connection
- Verify contract details (symbol exists)

### "Order rejected"
- Check buying power in IBKR account
- Verify order parameters (price, quantity)
- Check market hours (if order requires market to be open)

### Connection refused
- TWS/Gateway not running
- Wrong port number
- API not enabled in TWS/Gateway settings

## Next Steps

1. **Add Adaptive Algo Orders**: Implement TWAP, VWAP, POV algorithms
2. **Add Futures/Options Support**: Extend beyond stocks
3. **Add Partial Fill Handling**: More sophisticated partial fill logic
4. **Add Reconnection Logic**: Auto-reconnect on disconnect
5. **Add Order Amendments**: Modify existing orders

## References

- [ib_insync Documentation](https://ib-insync.readthedocs.io/)
- [IBKR API Guide](https://interactivebrokers.github.io/tws-api/)
- Message Contracts: `contracts/validators.py`
- Mock Implementation: `tests/e2e/ibkr_mock.py`
