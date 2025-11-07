# Runbook - מערכת המסחר האלגוריתמית
## Operational Runbook

**תאריך:** 2025-11-07
**גרסה:** 1.0
**מצב:** Pre-Production

---

## 🎯 מטרה

מסמך זה מספק נהלים תפעוליים למערכת המסחר האלגוריתמית, כולל:
- הרצה והפסקה
- ניטור ובעיות שכיחות
- נהלי חירום
- תחזוקה שוטפת

---

## 📋 רשימת קשר (On-Call)

| תפקיד | אחראי | טלפון | שעות זמינות |
|-------|-------|-------|-------------|
| **On-Call Engineer** | TBD | +972-XX-XXX-XXXX | 24/7 |
| **Risk Officer** | TBD | +972-XX-XXX-XXXX | Market hours |
| **CTO** | TBD | +972-XX-XXX-XXXX | Escalation |

---

## 🚀 הרצת המערכת (Startup)

### Pre-Start Checklist

```bash
# 1. Verify environment
echo "Checking environment..."
which python3
python3 --version  # Should be ≥3.9

# 2. Verify dependencies
pip list | grep -E "numpy|pandas|cvxpy|kafka-python"

# 3. Check configuration
cat fixtures/seeds.yaml  # Verify seeds
cat algo_trade/core/config.py | grep -E "KILL|BOX_LIM"

# 4. Verify IBKR connection (if live)
# Check TWS/Gateway is running on port 7497 (Paper) or 7496 (Live)
nc -zv localhost 7497

# 5. Check Kafka
nc -zv localhost 9092
```

### Startup Sequence

**Order matters! Follow sequence:**

#### 1. Start Kafka (if not running)
```bash
# Start Zookeeper
docker-compose up -d zookeeper

# Wait 10 seconds
sleep 10

# Start Kafka
docker-compose up -d kafka

# Verify
docker-compose ps
kafka-topics.sh --list --bootstrap-server localhost:9092
```

#### 2. Start Data Plane
```bash
cd /home/user/Algo-trade
python -m data_plane.app.main &
DATA_PLANE_PID=$!
echo "Data Plane PID: $DATA_PLANE_PID"

# Verify logs
tail -f logs/data_plane.log
# Look for: "Data Plane started successfully"
```

#### 3. Start Strategy Plane
```bash
python -m apps.strategy_loop.main &
STRATEGY_PLANE_PID=$!
echo "Strategy Plane PID: $STRATEGY_PLANE_PID"

# Verify logs
tail -f logs/strategy_plane.log
# Look for: "Strategy Plane started successfully"
```

#### 4. Start Order Plane
```bash
python -m order_plane.app.orchestrator &
ORDER_PLANE_PID=$!
echo "Order Plane PID: $ORDER_PLANE_PID"

# Verify logs
tail -f logs/order_plane.log
# Look for: "Order Plane started successfully"
```

#### 5. Verify System Health

```bash
# Check all processes running
ps aux | grep -E "data_plane|strategy|order_plane"

# Check Kafka topics active
kafka-topics.sh --list --bootstrap-server localhost:9092
# Should see: market_events, order_intents, exec_reports

# Check Prometheus metrics
curl http://localhost:8000/metrics | grep "system_health"

# Check logs for errors
tail -f logs/*.log | grep -i error
```

---

## 🛑 הפסקת המערכת (Shutdown)

### Graceful Shutdown

**Order matters! Reverse of startup:**

#### 1. Stop Order Plane (first)
```bash
# Send SIGTERM for graceful shutdown
kill -TERM $ORDER_PLANE_PID

# Wait for pending orders to complete (max 30s)
sleep 30

# Force kill if still running
kill -9 $ORDER_PLANE_PID 2>/dev/null || true
```

#### 2. Stop Strategy Plane
```bash
kill -TERM $STRATEGY_PLANE_PID
sleep 10
kill -9 $STRATEGY_PLANE_PID 2>/dev/null || true
```

#### 3. Stop Data Plane
```bash
kill -TERM $DATA_PLANE_PID
sleep 10
kill -9 $DATA_PLANE_PID 2>/dev/null || true
```

#### 4. Verify Clean Shutdown
```bash
# Check no orphan processes
ps aux | grep -E "data_plane|strategy|order_plane"

# Check logs
grep -i "shutdown" logs/*.log
```

### Emergency Shutdown (Kill-Switch)

**Use only in emergency!**

```bash
# Kill all planes immediately
pkill -9 -f "data_plane"
pkill -9 -f "strategy_loop"
pkill -9 -f "order_plane"

# Cancel all open orders (if connected to IBKR)
python scripts/emergency_cancel_all_orders.py

# Log incident
echo "$(date): Emergency shutdown triggered by $USER" >> logs/incidents.log
```

---

## 📊 ניטור (Monitoring)

### Metrics to Watch

#### System Health
```bash
# CPU usage
top -p $DATA_PLANE_PID,$STRATEGY_PLANE_PID,$ORDER_PLANE_PID

# Memory usage
ps aux | grep -E "data_plane|strategy|order" | awk '{print $6}'

# Disk I/O
iostat -x 5
```

#### Trading Metrics
```bash
# Check Grafana dashboards
# URL: http://localhost:3000

# Key metrics:
# - PnL: Current cumulative PnL
# - Sharpe: Rolling 30-day Sharpe
# - Drawdown: Current drawdown %
# - Exposure: Gross and Net exposure
# - Latency: p95 Intent→Ack latency
```

#### Alerts
```bash
# Check alert status
curl http://localhost:9093/api/v1/alerts | jq '.'

# Active alerts
curl http://localhost:9093/api/v1/alerts | jq '.data[] | select(.state=="firing")'
```

### Log Monitoring

```bash
# Tail all logs
tail -f logs/*.log

# Error patterns
grep -i "error\|exception\|fail" logs/*.log

# Kill-switch triggers
grep -i "kill.switch" logs/*.log

# Order rejections
grep -i "reject" logs/order_plane.log
```

---

## 🚨 נהלי חירום (Emergency Procedures)

### Scenario 1: Kill-Switch Triggered

**Symptoms:** PnL < -5%, or Max DD > 15%, or PSR < 0.20

**Actions:**
1. **DO NOT PANIC** - system halted automatically
2. Verify all planes stopped:
   ```bash
   ps aux | grep -E "strategy|order"
   ```
3. Check open positions:
   ```bash
   python scripts/check_positions.py
   ```
4. Review logs:
   ```bash
   grep "kill.switch" logs/*.log
   ```
5. Notify Risk Officer immediately
6. Document incident in `logs/incidents.log`
7. **DO NOT restart** without Risk Officer approval

### Scenario 2: IBKR Disconnect

**Symptoms:** "Not connected" errors in logs

**Actions:**
1. Check TWS/Gateway:
   ```bash
   nc -zv localhost 7497
   ```
2. If down, restart TWS/Gateway
3. Wait 30 seconds for reconnection
4. Verify connection:
   ```bash
   grep "connected" logs/order_plane.log
   ```
5. If still failing, perform graceful shutdown

### Scenario 3: Kafka Failure

**Symptoms:** "Broker not available" errors

**Actions:**
1. Check Kafka:
   ```bash
   docker-compose ps kafka
   ```
2. Restart if needed:
   ```bash
   docker-compose restart kafka
   ```
3. Verify topics:
   ```bash
   kafka-topics.sh --list --bootstrap-server localhost:9092
   ```
4. Resume data flow

### Scenario 4: High Latency (p95 > 1s)

**Symptoms:** Slow order execution

**Actions:**
1. Check system load:
   ```bash
   top
   uptime
   ```
2. Check network:
   ```bash
   ping -c 10 localhost
   ```
3. Review slow queries:
   ```bash
   grep "slow" logs/*.log
   ```
4. Consider reducing load:
   - Decrease signal frequency
   - Reduce portfolio size
5. If persistent, escalate

### Scenario 5: Order Rejection Spike

**Symptoms:** >10% order rejection rate

**Actions:**
1. Check rejection reasons:
   ```bash
   grep "reject" logs/order_plane.log | tail -20
   ```
2. Common causes:
   - Insufficient buying power → Check account
   - Risk limits breached → Review exposure
   - Invalid orders → Check order logic
3. Fix root cause before resuming
4. Document in incident log

---

## 🔧 תחזוקה שוטפת (Routine Maintenance)

### Daily Tasks

```bash
# 1. Check logs for errors
grep -i "error\|warn" logs/*.log | wc -l

# 2. Verify backups
ls -lh backups/ | tail -5

# 3. Check disk space
df -h | grep -E "/$|/var"

# 4. Review performance
curl http://localhost:8000/metrics | grep "latency_p95"

# 5. Monitor open positions
python scripts/check_positions.py
```

### Weekly Tasks

```bash
# 1. Rotate logs
logrotate /etc/logrotate.d/algo-trade

# 2. Update dependencies
pip list --outdated

# 3. Run full test suite
pytest tests/ -v

# 4. Review performance metrics
python scripts/weekly_report.py

# 5. Backup configurations
tar -czf backups/config_$(date +%F).tar.gz algo_trade/core/config.py fixtures/
```

### Monthly Tasks

```bash
# 1. Update risk parameters (with approval)
# Review and adjust: KILL_PNL, MAX_DD, BOX_LIM

# 2. Retrain models (if applicable)
python scripts/retrain_models.py

# 3. Full system health check
python scripts/health_check_full.py

# 4. Review incidents log
cat logs/incidents.log

# 5. Update documentation
# Review and update this RUNBOOK
```

---

## 📈 Performance Tuning

### Optimization Checklist

- [ ] **Latency**: p95 Intent→Ack < 50ms
- [ ] **Throughput**: >500 msg/sec peak
- [ ] **CPU**: <70% average utilization
- [ ] **Memory**: <80% usage
- [ ] **Disk I/O**: <50% utilization
- [ ] **Network**: <10% packet loss

### Tuning Parameters

```python
# data_plane/config.py
KAFKA_BATCH_SIZE = 1000  # Increase for throughput
KAFKA_LINGER_MS = 10     # Decrease for latency

# strategy_plane/config.py
SIGNAL_FREQ_SEC = 60     # Decrease for faster signals

# order_plane/config.py
MAX_CONCURRENT_ORDERS = 10  # Increase for throughput
```

---

## 🔍 Troubleshooting Guide

### Problem: High Memory Usage

**Diagnosis:**
```bash
ps aux --sort=-%mem | head -10
python scripts/memory_profile.py
```

**Solutions:**
- Reduce data retention window
- Optimize DataFrame operations
- Add garbage collection calls

### Problem: Slow Signal Computation

**Diagnosis:**
```bash
python -m cProfile -o profile.stats algo_trade/core/signals/base_signals.py
python scripts/analyze_profile.py profile.stats
```

**Solutions:**
- Vectorize operations
- Use NumPy instead of loops
- Cache intermediate results

### Problem: Kafka Lag

**Diagnosis:**
```bash
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group strategy_plane_group --describe
```

**Solutions:**
- Increase consumer parallelism
- Optimize message processing
- Scale Kafka brokers

---

## 📞 Escalation Path

1. **Level 1: On-Call Engineer**
   - Handle routine issues
   - Monitor alerts
   - Execute standard procedures

2. **Level 2: Senior Engineer**
   - Complex technical issues
   - System architecture problems
   - Performance tuning

3. **Level 3: CTO + Risk Officer**
   - Critical failures
   - Kill-switch triggers
   - Risk parameter changes
   - Production incidents

---

**נוצר על ידי:** Claude Code (AI Assistant)
**תאריך:** 2025-11-07
**לעדכון:** מדי חודש או לאחר incidents
