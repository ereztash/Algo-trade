# Rollback Procedure
## IBKR Production Emergency Rollback

**תאריך:** 2025-11-07
**גרסה:** 1.0
**Branch:** claude/ibkr-prelive-validation-gates-011CUto1SmoYBABTX8Qm81TH
**Status:** 📋 PROCEDURE TEMPLATE

---

## 🎯 Overview

מסמך זה מגדיר את נוהל הRollback המלא במקרה של כשל במערכת IBKR במהלך Production או Paper Trading.
**עיקרון:** Safety First - פירוק מהיר של פוזיציות ובדיקת נזקים.

---

## 🚨 Rollback Trigger Conditions

### Critical Triggers (Immediate Rollback)

| Trigger | Condition | Severity | Auto-Rollback |
|---------|-----------|----------|---------------|
| **PnL Kill Switch** | `pnl < -5%` | 🔴 CRITICAL | ✅ YES |
| **Max Drawdown** | `max_drawdown > 15%` | 🔴 CRITICAL | ✅ YES |
| **PSR Kill Switch** | `psr < 0.20` | 🔴 CRITICAL | ✅ YES |
| **Connection Failures** | `failures > 3/hour` | 🔴 CRITICAL | ✅ YES |
| **Pacing Violations** | `violations > 10/hour` | 🟡 HIGH | ⚠️ MANUAL |
| **Order Rejections** | `rejections > 20%` | 🟡 HIGH | ⚠️ MANUAL |
| **Latency Spike** | `p95_latency > 2× baseline` | 🟡 HIGH | ⚠️ MANUAL |

### Manual Triggers

| Trigger | Reason | Authorized By |
|---------|--------|---------------|
| **Strategy Malfunction** | Unexpected behavior | Risk Officer |
| **Market Anomaly** | Black swan event | CTO + Risk Officer |
| **Regulatory Issue** | Compliance violation | Compliance Officer |
| **Operational Error** | Human error | Trading Desk Manager |

---

## 🔄 Rollback Flow Diagram

```
TRIGGER DETECTED
     |
     ▼
[AUTO-DETECT] OR [MANUAL TRIGGER]
     |
     ▼
🚨 STEP 1: IMMEDIATE HALT
     |
     ├─ Stop strategy execution
     ├─ Cancel all pending orders
     └─ Log trigger event
     |
     ▼
🛑 STEP 2: DISCONNECT IBKR
     |
     ├─ Close IBKR connection
     ├─ Prevent new orders
     └─ Log disconnect time
     |
     ▼
📊 STEP 3: ASSESS POSITIONS
     |
     ├─ Query current positions
     ├─ Calculate P&L
     └─ Determine flatten strategy
     |
     ▼
💰 STEP 4: FLATTEN POSITIONS
     |
     ├─ Submit market orders to close
     ├─ Monitor fills
     └─ Verify all flat
     |
     ▼
✅ STEP 5: VERIFY RECOVERY
     |
     ├─ Confirm all positions flat
     ├─ Confirm no open orders
     ├─ Verify account P&L
     └─ Archive logs
     |
     ▼
📝 STEP 6: ROOT-CAUSE ANALYSIS
     |
     ├─ Investigate trigger cause
     ├─ Document findings
     └─ Report to Risk Officer
     |
     ▼
🎯 STEP 7: REMEDIATION PLAN
     |
     ├─ Fix identified issues
     ├─ Re-test in Paper
     └─ Obtain approval to resume
```

---

## 🛠️ Rollback Steps (Detailed)

### STEP 1: IMMEDIATE HALT ⏱️ 0-10 seconds

**Actions:**
1. **Stop Strategy Execution**
   ```python
   strategy.stop()
   risk_manager.activate_kill_switch(reason="ROLLBACK_TRIGGERED")
   ```

2. **Cancel All Pending Orders**
   ```python
   for order_id in open_orders:
       ibkr_client.cancel_order(order_id)
   ```

3. **Log Trigger Event**
   ```python
   logger.critical(f"ROLLBACK TRIGGERED: {trigger_condition}")
   logger.critical(f"Trigger Value: {trigger_value}")
   logger.critical(f"Timestamp: {datetime.utcnow()}")
   ```

**Verification:**
- ✅ Strategy stopped
- ✅ No new orders generated
- ✅ All cancellations submitted

**Time Target:** <10 seconds

---

### STEP 2: DISCONNECT IBKR ⏱️ 10-20 seconds

**Actions:**
1. **Close IBKR Connection**
   ```python
   ibkr_client.disconnect()
   connection_manager.prevent_reconnect()
   ```

2. **Prevent Reconnection**
   ```python
   config.IBKR_AUTO_RECONNECT = False
   connection_manager.blacklist_until_manual_approval()
   ```

3. **Log Disconnection**
   ```python
   logger.critical("IBKR connection closed for rollback")
   logger.critical(f"Disconnect time: {datetime.utcnow()}")
   ```

**Verification:**
- ✅ IBKR disconnected
- ✅ Auto-reconnect disabled
- ✅ Disconnect logged

**Time Target:** <10 seconds (cumulative: 20s)

---

### STEP 3: ASSESS POSITIONS ⏱️ 20-30 seconds

**Actions:**
1. **Query Current Positions**
   ```python
   # Reconnect in READ-ONLY mode
   ibkr_client.connect(read_only=True)
   positions = ibkr_client.get_positions()
   ```

2. **Calculate P&L**
   ```python
   total_pnl = sum(pos.unrealized_pnl for pos in positions.values())
   total_exposure = sum(abs(pos.market_value) for pos in positions.values())
   ```

3. **Determine Flatten Strategy**
   ```python
   if total_exposure < 10000:
       flatten_strategy = "MARKET_ORDERS"  # Fast
   else:
       flatten_strategy = "LIMIT_ORDERS_WITH_TIMEOUT"  # Minimize slippage
   ```

**Verification:**
- ✅ Positions retrieved
- ✅ P&L calculated
- ✅ Flatten strategy determined

**Time Target:** <10 seconds (cumulative: 30s)

---

### STEP 4: FLATTEN POSITIONS ⏱️ 30-120 seconds

**Actions:**
1. **Submit Flatten Orders**
   ```python
   for symbol, position in positions.items():
       if position.quantity != 0:
           # Close position
           direction = "SELL" if position.quantity > 0 else "BUY"
           quantity = abs(position.quantity)

           flatten_order = {
               "symbol": symbol,
               "direction": direction,
               "quantity": quantity,
               "order_type": "MARKET",  # or LIMIT with aggressive price
               "urgency": "URGENT",
               "reason": "ROLLBACK_FLATTEN"
           }

           order_id = ibkr_client.place_order(flatten_order)
           logger.critical(f"Flatten order submitted: {order_id} for {symbol}")
   ```

2. **Monitor Fills**
   ```python
   timeout = 90  # seconds
   start_time = time.time()

   while time.time() - start_time < timeout:
       fills = ibkr_client.get_fills()
       if all_positions_flat(fills):
           logger.critical("All positions flattened successfully")
           break
       time.sleep(1)
   else:
       logger.critical("WARNING: Timeout flattening positions!")
       # Manual intervention required
   ```

3. **Verify All Flat**
   ```python
   final_positions = ibkr_client.get_positions()
   assert all(pos.quantity == 0 for pos in final_positions.values()), "Not all flat!"
   ```

**Verification:**
- ✅ All positions closed
- ✅ No open orders
- ✅ Account flat

**Time Target:** <90 seconds (cumulative: 120s = 2 minutes)

---

### STEP 5: VERIFY RECOVERY ⏱️ 120-180 seconds

**Actions:**
1. **Confirm All Positions Flat**
   ```python
   positions = ibkr_client.get_positions()
   assert len(positions) == 0 or all(pos.quantity == 0 for pos in positions.values())
   logger.critical("✅ All positions confirmed flat")
   ```

2. **Confirm No Open Orders**
   ```python
   open_orders = ibkr_client.get_open_orders()
   assert len(open_orders) == 0
   logger.critical("✅ No open orders")
   ```

3. **Verify Account P&L**
   ```python
   account_info = ibkr_client.get_account_info()
   final_pnl = account_info["nav"] - initial_nav
   logger.critical(f"Final P&L: ${final_pnl:.2f}")

   # Check if within acceptable loss
   if final_pnl < -0.05 * initial_nav:
       logger.critical("⚠️ P&L loss exceeds 5% threshold!")
   ```

4. **Archive Logs**
   ```python
   log_archive_path = f"logs/rollback_{datetime.utcnow().isoformat()}.log"
   archive_logs(log_archive_path)
   logger.critical(f"Logs archived to {log_archive_path}")
   ```

**Verification:**
- ✅ All flat
- ✅ No open orders
- ✅ P&L within tolerance (or documented)
- ✅ Logs archived

**Time Target:** <60 seconds (cumulative: 180s = 3 minutes)

---

### STEP 6: ROOT-CAUSE ANALYSIS ⏱️ 1-4 hours

**Actions:**
1. **Investigate Trigger Cause**
   - Review logs (`logs/rollback_*.log`)
   - Analyze market data (price spikes, volatility)
   - Check system metrics (latency, error rates)
   - Review strategy signals

2. **Document Findings**
   ```markdown
   # Rollback Root-Cause Analysis

   **Date:** 2025-11-07
   **Trigger:** PnL Kill Switch (-5.2%)
   **Duration:** 3 trading hours

   ## Timeline
   - 09:30 - Trading started
   - 11:45 - Large position in TSLA
   - 12:00 - TSLA dropped 8%
   - 12:03 - Kill switch triggered (-5.2%)
   - 12:06 - Positions flattened

   ## Root Cause
   - Position sizing too aggressive (40% of NAV in single stock)
   - Stop-loss not triggered (IBKR delay)
   - Volatility spike not detected in time

   ## Contributing Factors
   - Market volatility (VIX spike to 35)
   - News event (earnings miss)

   ## Lessons Learned
   - Reduce single-stock exposure to <25%
   - Implement tighter stop-losses
   - Add volatility circuit breaker

   ## Recommended Actions
   1. Update risk params (BOX_LIM = 0.20 → 0.15)
   2. Add pre-trade volatility check
   3. Test new params in Paper
   ```

3. **Report to Risk Officer**
   - Email summary to Risk Officer
   - Schedule post-mortem meeting
   - Update risk policy if needed

**Verification:**
- ✅ Root cause identified
- ✅ Findings documented
- ✅ Risk Officer notified

**Time Target:** 1-4 hours

---

### STEP 7: REMEDIATION PLAN ⏱️ 1-5 days

**Actions:**
1. **Fix Identified Issues**
   - Update risk parameters
   - Fix bugs in code
   - Improve monitoring

2. **Re-Test in Paper**
   - Run Paper Trading session (6 hours minimum)
   - Verify fixes work
   - Collect new metrics

3. **Obtain Approval to Resume**
   - Submit remediation report to Risk Officer
   - Obtain CTO sign-off
   - Update `GO_LIVE_DECISION_GATE.md`

**Verification:**
- ✅ Issues fixed
- ✅ Paper testing passed
- ✅ Approval obtained

**Time Target:** 1-5 days

---

## 📊 Rollback Checklist

### Pre-Rollback (Preparation)
- [ ] Rollback procedure documented and reviewed
- [ ] Auto-rollback logic tested in staging
- [ ] Emergency contacts list updated
- [ ] Log archival system working
- [ ] Kill-switches configured and tested

### During Rollback
- [ ] **Step 1:** Strategy stopped (<10s)
- [ ] **Step 1:** All orders canceled (<10s)
- [ ] **Step 2:** IBKR disconnected (<20s)
- [ ] **Step 3:** Positions assessed (<30s)
- [ ] **Step 4:** Positions flattened (<120s)
- [ ] **Step 5:** Recovery verified (<180s)

### Post-Rollback
- [ ] **Step 6:** Root-cause analysis completed
- [ ] **Step 6:** Findings documented
- [ ] **Step 6:** Risk Officer notified
- [ ] **Step 7:** Remediation plan created
- [ ] **Step 7:** Fixes implemented
- [ ] **Step 7:** Re-tested in Paper
- [ ] **Step 7:** Approval obtained to resume

---

## 🚨 Emergency Contacts

| Role | Name | Phone | Email | Priority |
|------|------|-------|-------|----------|
| **Risk Officer** | TBD | +1-XXX-XXX-XXXX | risk@company.com | 1 |
| **CTO** | TBD | +1-XXX-XXX-XXXX | cto@company.com | 1 |
| **Trading Desk Manager** | TBD | +1-XXX-XXX-XXXX | trading@company.com | 2 |
| **DevOps On-Call** | TBD | +1-XXX-XXX-XXXX | devops@company.com | 2 |
| **IBKR Support** | - | +1-877-442-2757 | - | 3 |

**Escalation:**
1. First contact: Risk Officer + Trading Desk Manager
2. If no response (15 min): CTO + DevOps
3. If critical (>$10k loss): ALL contacts immediately

---

## 📝 Rollback Log Template

```json
{
  "rollback_id": "rollback_20251107_001",
  "timestamp": "2025-11-07T12:03:45Z",
  "trigger": "PnL Kill Switch",
  "trigger_value": -0.052,
  "trigger_threshold": -0.05,
  "steps": [
    {
      "step": 1,
      "name": "Immediate Halt",
      "start_time": "2025-11-07T12:03:45Z",
      "end_time": "2025-11-07T12:03:50Z",
      "duration_seconds": 5,
      "status": "SUCCESS",
      "actions": [
        "Strategy stopped",
        "Orders canceled (12 orders)"
      ]
    },
    {
      "step": 2,
      "name": "Disconnect IBKR",
      "start_time": "2025-11-07T12:03:50Z",
      "end_time": "2025-11-07T12:03:55Z",
      "duration_seconds": 5,
      "status": "SUCCESS",
      "actions": ["IBKR disconnected"]
    },
    {
      "step": 3,
      "name": "Assess Positions",
      "start_time": "2025-11-07T12:03:55Z",
      "end_time": "2025-11-07T12:04:05Z",
      "duration_seconds": 10,
      "status": "SUCCESS",
      "positions": {
        "TSLA": {"quantity": 500, "unrealized_pnl": -5200},
        "AAPL": {"quantity": -200, "unrealized_pnl": -300}
      },
      "total_pnl": -5500,
      "flatten_strategy": "MARKET_ORDERS"
    },
    {
      "step": 4,
      "name": "Flatten Positions",
      "start_time": "2025-11-07T12:04:05Z",
      "end_time": "2025-11-07T12:05:20Z",
      "duration_seconds": 75,
      "status": "SUCCESS",
      "orders": [
        {"symbol": "TSLA", "direction": "SELL", "quantity": 500, "filled": true},
        {"symbol": "AAPL", "direction": "BUY", "quantity": 200, "filled": true}
      ]
    },
    {
      "step": 5,
      "name": "Verify Recovery",
      "start_time": "2025-11-07T12:05:20Z",
      "end_time": "2025-11-07T12:05:40Z",
      "duration_seconds": 20,
      "status": "SUCCESS",
      "verification": {
        "all_positions_flat": true,
        "no_open_orders": true,
        "final_pnl": -5650,
        "logs_archived": "logs/rollback_20251107_001.log"
      }
    }
  ],
  "total_duration_seconds": 115,
  "final_status": "SUCCESS",
  "final_pnl": -5650,
  "root_cause": "Large position in TSLA during volatility spike",
  "remediation_plan": "Reduce single-stock exposure to 15% max"
}
```

---

## 🔄 Auto-Rollback Configuration

### Kill-Switch Configuration

```python
# config/risk_params.yaml
kill_switches:
  pnl:
    enabled: true
    threshold: -0.05  # -5%
    auto_rollback: true

  drawdown:
    enabled: true
    threshold: 0.15  # 15%
    auto_rollback: true

  psr:
    enabled: true
    threshold: 0.20
    auto_rollback: true

  connection_failures:
    enabled: true
    threshold: 3  # per hour
    auto_rollback: true

  pacing_violations:
    enabled: true
    threshold: 10  # per hour
    auto_rollback: false  # Manual review
    alert: true
```

### Monitoring

```python
# Monitor kill-switches every 10 seconds
@scheduled(interval=10)
def check_kill_switches():
    pnl = portfolio.get_pnl()
    if pnl < config.KILL_PNL:
        trigger_rollback(reason="PnL Kill Switch", value=pnl)

    dd = portfolio.get_max_drawdown()
    if dd > config.MAX_DD:
        trigger_rollback(reason="Max Drawdown", value=dd)

    # ... etc
```

---

## ✅ Rollback Testing

### Test Scenarios

1. **Test 1: PnL Kill Switch**
   - Simulate -5.5% loss
   - Verify auto-rollback triggers
   - Verify positions flatten

2. **Test 2: Connection Failure**
   - Simulate network disconnect
   - Verify reconnection attempts
   - Verify rollback after 3 failures

3. **Test 3: Manual Rollback**
   - Trigger manual rollback
   - Verify all steps execute
   - Verify logs archived

**Test Schedule:** Monthly (or after any code changes)

---

## 📁 Related Documents

- `GO_LIVE_DECISION_GATE.md` - Go-live approval
- `IBKR_INTEGRATION_FLOW.md` - Integration architecture
- `PRE_LIVE_CHECKLIST.md` - Pre-live checklist
- `PRELIVE_VERIFICATION_LOG.json` - Gate verification log

---

**Created by:** Claude Code (AI Assistant)
**Date:** 2025-11-07
**Branch:** claude/ibkr-prelive-validation-gates-011CUto1SmoYBABTX8Qm81TH
**Version:** 1.0
**Status:** 📋 PROCEDURE TEMPLATE - TO BE TESTED
