# IBKR Interface Map
## Interactive Brokers API Integration Specification

**תאריך:** 2025-11-07
**גרסה:** 1.0
**Branch:** claude/ibkr-prelive-validation-gates-011CUto1SmoYBABTX8Qm81TH
**Status:** 📋 Specification

---

## 📋 Overview

מסמך זה מגדיר את המיפוי המלא בין ממשקי IBKR (Interactive Brokers) API לבין המערכת הפנימית.
כולל: endpoints, message flows, error handling, SLAs, ו-pacing limits.

---

## 🔌 Connection Architecture

### Connection Types

| Type | Protocol | Port | Purpose | Latency Target |
|------|----------|------|---------|----------------|
| **TWS (Trader Workstation)** | TCP | 7496 (live), 7497 (paper) | Manual trading, development | <100ms |
| **IB Gateway** | TCP | 4001 (live), 4002 (paper) | Automated trading, production | <50ms |
| **IBKR WebAPI** | HTTPS/REST | 443 | Account info, historical data | <500ms |

**Recommendation:** Use IB Gateway (port 4002) for Paper Trading validation.

### Connection Parameters

```python
# Paper Trading Configuration
IBKR_CONFIG = {
    "host": "127.0.0.1",           # Localhost (Gateway on same machine)
    "port": 4002,                   # Paper Trading port
    "client_id": 1,                 # Unique client ID (1-32)
    "account": "IBKR_PAPER_ACCOUNT_ID",  # Paper account ID (e.g., DU1234567)
    "timeout": 10,                  # Connection timeout (seconds)
    "read_only": True,              # READ-ONLY for Stage 6 Account Probe
}
```

### Connection State Machine

```
[DISCONNECTED] --connect()--> [CONNECTING] --success--> [CONNECTED]
                                    |
                                   fail
                                    |
                                    v
                               [ERROR] --retry--> [CONNECTING]
                                    |
                              max_retries
                                    |
                                    v
                              [FAILED]

[CONNECTED] --disconnect()--> [DISCONNECTED]
[CONNECTED] --network_error--> [RECONNECTING] --success--> [CONNECTED]
```

**Reconnection Policy:**
- Max retries: 3
- Backoff: Exponential (1s, 2s, 4s)
- Timeout per attempt: 10s

---

## 📡 API Operations

### 1. Account Operations

#### 1.1 Get Account Summary
**IBKR Method:** `reqAccountSummary(reqId, "All", tags)`

**System Mapping:**
```python
# System Interface
async def get_account_info() -> AccountInfo:
    """
    Retrieves account summary.

    Returns:
        AccountInfo: {
            "account_id": str,
            "nav": float,           # Net Asset Value
            "cash": float,          # Available cash
            "buying_power": float,  # Total buying power
            "margin_cushion": float, # Margin cushion (%)
            "maintenance_margin": float,
            "equity_with_loan": float,
        }
    """
```

**IBKR Tags:**
- `NetLiquidation` → `nav`
- `TotalCashValue` → `cash`
- `BuyingPower` → `buying_power`
- `Cushion` → `margin_cushion`
- `MaintMarginReq` → `maintenance_margin`
- `EquityWithLoanValue` → `equity_with_loan`

**Latency SLA:** <500ms (p95)
**Pacing Limit:** 50 requests/sec (across all operations)
**Error Codes:** See Section 4

---

#### 1.2 Get Positions
**IBKR Method:** `reqPositions()`

**System Mapping:**
```python
# System Interface
async def get_positions() -> Dict[str, Position]:
    """
    Retrieves current positions.

    Returns:
        Dict[symbol, Position]: {
            "symbol": str,
            "quantity": float,      # Positive=long, Negative=short
            "avg_cost": float,      # Average entry price
            "market_value": float,  # Current market value
            "unrealized_pnl": float,
            "realized_pnl": float,
        }
    """
```

**IBKR Position Fields:**
- `contract.symbol` → `symbol`
- `position` → `quantity`
- `avgCost` → `avg_cost`
- `marketValue` → `market_value`
- `unrealizedPNL` → `unrealized_pnl`
- `realizedPNL` → `realized_pnl`

**Latency SLA:** <300ms (p95)
**Pacing Limit:** Included in 50 req/sec limit
**Refresh Rate:** Real-time updates via callback

---

### 2. Order Operations

#### 2.1 Place Order
**IBKR Method:** `placeOrder(orderId, contract, order)`

**System Mapping:**
```python
# System Interface (from OrderIntent contract)
async def place_order(intent: OrderIntent) -> OrderPlacement:
    """
    Places order with broker.

    Args:
        intent: OrderIntent (see contracts/order_intent.schema.json)

    Returns:
        OrderPlacement: {
            "order_id": str,        # Broker order ID
            "status": str,          # SUBMITTED
            "submitted_at": datetime,
        }
    """
```

**Order Type Mapping:**

| System | IBKR | Notes |
|--------|------|-------|
| `MARKET` | `MKT` | Immediate execution at market price |
| `LIMIT` | `LMT` | Execution at specified price or better |
| `STOP` | `STP` | Stop-loss order |
| `STOP_LIMIT` | `STP LMT` | Stop with limit price |
| `ADAPTIVE` | `REL` | IBKR Adaptive algo (low urgency) |

**Time-in-Force Mapping:**

| System | IBKR | Description |
|--------|------|-------------|
| `DAY` | `DAY` | Valid until end of trading day |
| `GTC` | `GTC` | Good-till-canceled |
| `IOC` | `IOC` | Immediate-or-cancel |
| `FOK` | `FOK` | Fill-or-kill |

**Latency SLA:**
- Intent → Submit: <50ms (p95)
- Submit → Ack: <150ms (p95)
- Total: <200ms (p95)

**Pacing Limit:** 50 orders/sec
**Max Order Size:** Check `ACCOUNT_CONFIG.json` for buying_power

---

#### 2.2 Cancel Order
**IBKR Method:** `cancelOrder(orderId)`

**System Mapping:**
```python
# System Interface
async def cancel_order(order_id: str) -> CancelResponse:
    """
    Cancels pending order.

    Args:
        order_id: Broker order ID

    Returns:
        CancelResponse: {
            "order_id": str,
            "status": str,          # CANCELED | CANNOT_CANCEL
            "reason": str | None,   # Reason if failed
        }
    """
```

**Latency SLA:** <100ms (p95)
**Pacing Limit:** Included in 50 req/sec limit

---

#### 2.3 Get Order Status
**IBKR Method:** `reqOpenOrders()` + callbacks

**System Mapping:**
```python
# System Interface
async def get_order_status(order_id: str) -> ExecutionReport:
    """
    Gets order status.

    Returns:
        ExecutionReport (see contracts/execution_report.schema.json)
    """
```

**Order Status Mapping:**

| IBKR Status | System Status | Description |
|-------------|---------------|-------------|
| `PreSubmitted` | `SUBMITTED` | Order received by IBKR |
| `Submitted` | `ACKNOWLEDGED` | Order sent to exchange |
| `PartiallyFilled` | `PARTIAL_FILL` | Partially filled |
| `Filled` | `FILLED` | Completely filled |
| `Cancelled` | `CANCELED` | Order canceled |
| `Inactive` | `REJECTED` | Order rejected |
| `PendingCancel` | `ACKNOWLEDGED` | Cancel pending |
| `ApiCancelled` | `CANCELED` | Canceled via API |

**Latency SLA:** <50ms (p95)
**Pacing Limit:** Included in 50 req/sec limit

---

### 3. Market Data Operations

#### 3.1 Subscribe to Real-Time Data
**IBKR Method:** `reqMktData(reqId, contract, genericTickList, snapshot, regulatorySnapshot, mktDataOptions)`

**System Mapping:**
```python
# System Interface
async def subscribe_market_data(symbol: str) -> SubscriptionId:
    """
    Subscribes to real-time market data.

    Returns:
        SubscriptionId: int (for unsubscribe)
    """
```

**Data Fields:**
- `bid`, `ask`, `last`, `bidSize`, `askSize`, `lastSize`
- `volume`, `high`, `low`, `close`

**Latency SLA:** <100ms (p95) from exchange to system
**Pacing Limit:** 100 subscriptions max
**Cost:** Market data subscription required (see IBKR pricing)

---

#### 3.2 Get Historical Data
**IBKR Method:** `reqHistoricalData(...)`

**System Mapping:**
```python
# System Interface
async def get_historical_bars(
    symbol: str,
    bar_size: str,      # "1 min", "5 mins", "1 hour", "1 day"
    duration: str,      # "1 D", "1 W", "1 M"
    end_datetime: datetime = None,
) -> List[BarEvent]:
    """
    Retrieves historical bar data.

    Returns:
        List[BarEvent] (see contracts/bar_event.schema.json)
    """
```

**Latency SLA:** <2s (p95)
**Pacing Limit:** 60 requests/10 minutes (IBKR limit)

---

## 🔄 Message Flow Diagrams

### Order Placement Flow

```
Strategy Plane                Order Plane               IBKR
     |                             |                      |
     |-- OrderIntent ------------>|                      |
     |   (Kafka: order_intents)   |                      |
     |                             |-- placeOrder() ---->|
     |                             |                      |
     |                             |<--- orderId --------|
     |                             |   (SUBMITTED)        |
     |<-- ExecutionReport ---------|                      |
     |   (status=SUBMITTED)        |                      |
     |                             |                      |
     |                             |<--- callback --------|
     |                             |   (ACKNOWLEDGED)     |
     |<-- ExecutionReport ---------|                      |
     |   (status=ACKNOWLEDGED)     |                      |
     |                             |                      |
     |                             |<--- callback --------|
     |                             |   (FILLED)           |
     |<-- ExecutionReport ---------|                      |
     |   (status=FILLED)           |                      |
     |                             |                      |
```

**Latency Breakdown:**
- Intent → Kafka: <10ms
- Kafka → Order Plane: <20ms
- Order Plane → IBKR: <50ms
- IBKR → Exchange: <100ms
- **Total Intent-to-Ack:** <180ms (target: <200ms)

---

### Error Handling Flow

```
Order Plane               IBKR
     |                      |
     |-- placeOrder() ---->|
     |                      |
     |<--- ERROR 201 ------|
     |   (REJECT: Insufficient funds)
     |                      |
     |-- retry? NO ------->|
     |   (Permanent error)  |
     |                      |
     |-- ExecutionReport ->| (Kafka)
     |   status=REJECTED    |
     |   reject_reason="Insufficient funds"
     |                      |
```

**Error Classification:**
- **Permanent Errors:** No retry (201, 321, 399)
- **Transient Errors:** Retry with backoff (504, 1100, 2104)
- **Rate Limit Errors:** Backoff + slow down (100, 103)

---

## 🚨 Error Codes & Handling

### IBKR Error Code Mapping

| IBKR Code | Category | System Action | User Message |
|-----------|----------|---------------|--------------|
| **100** | `RATE_LIMIT` | Backoff (5s) | "API rate limit exceeded" |
| **103** | `RATE_LIMIT` | Backoff (10s) | "Duplicate order within 1s" |
| **200** | `REJECT` | No retry | "No security definition found" |
| **201** | `REJECT` | No retry | "Order rejected: insufficient funds" |
| **202** | `REJECT` | No retry | "Order canceled" |
| **321** | `REJECT` | No retry | "Error validating request" |
| **399** | `WARNING` | Log only | "Order message warning" |
| **434** | `REJECT` | No retry | "Order size too small" |
| **504** | `TRANSIENT` | Retry (3x) | "Not connected" |
| **1100** | `TRANSIENT` | Reconnect | "Connectivity lost" |
| **2104** | `INFO` | Log only | "Market data farm connection OK" |
| **2106** | `INFO` | Log only | "HMDS data farm connection OK" |

### Error Handling Strategy

```python
def handle_ibkr_error(error_code: int, error_msg: str) -> ErrorAction:
    """
    Determines action based on error code.

    Returns:
        ErrorAction: RETRY | NO_RETRY | RECONNECT | LOG_ONLY
    """
    if error_code in [100, 103]:  # Rate limit
        return ErrorAction.BACKOFF
    elif error_code in [504, 1100]:  # Connection
        return ErrorAction.RECONNECT
    elif error_code in [201, 321, 399, 434]:  # Permanent
        return ErrorAction.NO_RETRY
    elif error_code in [2104, 2106]:  # Info
        return ErrorAction.LOG_ONLY
    else:
        return ErrorAction.RETRY  # Default: try once
```

---

## ⏱️ Latency SLAs

### Target Latencies (p95)

| Operation | Target | Measured | Status |
|-----------|--------|----------|--------|
| **Connect** | <1s | TBD | ⏳ Stage 6 |
| **Account Info** | <500ms | TBD | ⏳ Stage 6 |
| **Positions** | <300ms | TBD | ⏳ Stage 6 |
| **Place Order** | <200ms | TBD | ⏳ Stage 7 |
| **Cancel Order** | <100ms | TBD | ⏳ Stage 7 |
| **Order Status** | <50ms | TBD | ⏳ Stage 7 |
| **Market Data** | <100ms | TBD | ⏳ Stage 7 |

**Latency Delta Threshold:** <50% vs. Mock (dry-run)

### Latency Monitoring

```python
# Prometheus metrics
intent_to_submit_ms = Histogram("intent_to_submit_ms", buckets=[10, 25, 50, 100, 200])
submit_to_ack_ms = Histogram("submit_to_ack_ms", buckets=[50, 100, 150, 200, 300])
ack_to_fill_ms = Histogram("ack_to_fill_ms", buckets=[100, 500, 1000, 5000, 10000])
total_latency_ms = Histogram("total_latency_ms", buckets=[100, 200, 500, 1000, 5000])
```

---

## 🚦 Pacing Limits

### IBKR Pacing Rules

| Operation | Limit | Window | Burst |
|-----------|-------|--------|-------|
| **Order Messages** | 50/sec | Rolling | N/A |
| **Market Data Subscriptions** | 100 total | - | N/A |
| **Historical Data** | 60 requests | 10 min | N/A |
| **Account Updates** | 50/sec | Rolling | N/A |

**Enforcement:**
- Client-side: Token bucket algorithm
- Server-side: IBKR returns error 100 if violated

### Pacing Implementation

```python
class PacingLimiter:
    """
    Token bucket rate limiter.
    """
    def __init__(self, rate: int = 50, per: int = 1):
        self.rate = rate        # 50 requests
        self.per = per          # per 1 second
        self.tokens = rate
        self.last_refill = time.time()

    async def acquire(self):
        """Wait until token available."""
        while self.tokens < 1:
            await self._refill()
            await asyncio.sleep(0.01)
        self.tokens -= 1

    async def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        refill = (elapsed / self.per) * self.rate
        self.tokens = min(self.rate, self.tokens + refill)
        self.last_refill = now
```

---

## 🔐 Security & Authentication

### Connection Security

```python
# TLS/SSL Configuration
IBKR_CONFIG = {
    "use_tls": False,  # TWS/Gateway use plain TCP (localhost only)
    "host": "127.0.0.1",  # NEVER expose to internet
    "firewall": True,  # Ensure firewall blocks external access
}
```

**Security Notes:**
1. TWS/Gateway uses **plain TCP** (no TLS) → run on localhost only
2. Authentication via account credentials (TWS login)
3. API connection authenticated by client_id (no API key needed)
4. **DO NOT** expose ports 4001/4002/7496/7497 to internet

### Account Isolation

```python
# Paper Trading Safety
assert IBKR_CONFIG["account"].startswith("DU"), "Must use Paper account (DU prefix)"
assert IBKR_CONFIG["port"] in [7497, 4002], "Must use Paper port"
```

---

## 📊 Data Type Conversions

### IBKR → System

| IBKR Type | System Type | Conversion |
|-----------|-------------|------------|
| `Contract` | `str` (symbol) | `contract.symbol` |
| `Order` | `OrderIntent` | Map fields (see contracts) |
| `Execution` | `ExecutionReport` | Map fields (see contracts) |
| `float` (price) | `float` | Round to tick size |
| `int` (orderId) | `str` | `str(orderId)` |
| `datetime` (IBKR format) | `datetime` (UTC ISO8601) | Parse + convert to UTC |

### Tick Size Handling

```python
def round_to_tick_size(price: float, symbol: str) -> float:
    """
    Rounds price to valid tick size.

    IBKR Rules:
    - $0.01 - $1.00: tick size = $0.0001
    - $1.00+: tick size = $0.01
    """
    if price < 1.0:
        return round(price, 4)
    else:
        return round(price, 2)
```

---

## 🧪 Testing Strategy

### Stage 6: Account Probe (Read-Only)

**Operations to Test:**
1. ✅ Connect to Paper account
2. ✅ Get account summary
3. ✅ Get positions
4. ✅ Get buying power
5. ✅ Disconnect

**Expected Results:**
- Connection successful
- Account metadata retrieved
- No orders placed
- Latency <500ms

---

### Stage 7: Paper Trading Validation

**Operations to Test:**
1. ✅ Place market order (small quantity)
2. ✅ Place limit order
3. ✅ Cancel order
4. ✅ Partial fill scenario
5. ✅ Order rejection scenario (insufficient funds)
6. ✅ Network disconnect/reconnect

**Metrics to Collect:**
- Latency: p50, p95, p99
- Fill rate: >98%
- Pacing violations: 0
- Disconnects: Log and recover

**Duration:** 6 hours, 50-200 trades

---

### Stage 8: Go-Live Decision

**Gate Checks:**
- ✅ Latency Δ < 50% (mock vs. real)
- ✅ No pacing violations
- ✅ Fill rate > 98%
- ✅ Error handling verified
- ✅ Reconnection logic verified

---

## 📁 Related Files

| File | Purpose |
|------|---------|
| `algo_trade/core/execution/IBKR_handler.py` | IBKR connection handler |
| `order_plane/broker/ibkr_exec_client.py` | Async IBKR execution client |
| `tests/e2e/ibkr_mock.py` | Mock IBKR for testing |
| `contracts/order_intent.schema.json` | Order intent contract |
| `contracts/execution_report.schema.json` | Execution report contract |
| `ACCOUNT_CONFIG.json` | Paper account configuration (Stage 6 output) |
| `PAPER_TRADING_LOG.json` | Paper trading logs (Stage 7 output) |

---

## ✅ Validation Checklist

- [x] All IBKR operations mapped to system interfaces
- [x] Error codes documented with handling strategy
- [x] Latency SLAs defined
- [x] Pacing limits documented and enforced
- [x] Security considerations documented
- [x] Data type conversions specified
- [x] Testing strategy defined (Stages 6-8)
- [ ] Reviewed by IBKR expert
- [ ] Reviewed by Risk Officer
- [ ] Reviewed by CTO

---

## 📝 References

- [IBKR API Documentation](https://interactivebrokers.github.io/tws-api/)
- [ib_insync Documentation](https://ib-insync.readthedocs.io/)
- [IBKR Pacing Violations](https://ibkr.info/node/971)
- [IBKR Error Codes](https://interactivebrokers.github.io/tws-api/message_codes.html)

---

**Created by:** Claude Code (AI Assistant)
**Date:** 2025-11-07
**Branch:** claude/ibkr-prelive-validation-gates-011CUto1SmoYBABTX8Qm81TH
**Version:** 1.0
**Status:** ✅ Ready for Review
