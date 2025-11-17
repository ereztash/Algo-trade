# Incident Response Playbook

**Version:** 1.0
**Status:** Pre-Production (P1 - Required before production)
**Last Updated:** 2025-11-16
**Owner:** SRE Team / Risk Officer

---

## Table of Contents

1. [Overview](#overview)
2. [Incident Severity Levels](#incident-severity-levels)
3. [Incident Response Team](#incident-response-team)
4. [General Response Process](#general-response-process)
5. [Playbooks by Scenario](#playbooks-by-scenario)
6. [Post-Incident Review](#post-incident-review)
7. [Communication Templates](#communication-templates)
8. [Escalation Procedures](#escalation-procedures)

---

## Overview

### Purpose

This playbook provides step-by-step procedures for responding to operational incidents in the Algo-Trade system. Each scenario includes detection, response, and recovery steps.

### When to Use This Document

Use this playbook when:
- Kill-switches are triggered
- Trading losses exceed thresholds
- System components fail
- Security breaches occur
- Data quality issues are detected
- Performance degrades significantly

### Core Principles

1. **Safety First** - Stop trading if in doubt
2. **Document Everything** - Log all actions taken
3. **Clear Communication** - Keep stakeholders informed
4. **No Blame Culture** - Focus on resolution, not fault
5. **Learn and Improve** - Conduct post-incident reviews

---

## Incident Severity Levels

| Level | Description | Examples | Response Time | Escalation |
|-------|-------------|----------|---------------|------------|
| **P0 - Critical** | Trading halted, money at risk, security breach | Kill-switch triggered, unauthorized trading, data breach | **Immediate** (< 5 min) | CTO + Risk Officer |
| **P1 - High** | Major functionality broken, trading impaired | IBKR disconnect, Kafka failure, order rejection spike | **< 15 min** | Senior Engineer |
| **P2 - Medium** | Degraded performance, partial functionality | High latency, partial data loss, monitoring gaps | **< 1 hour** | On-Call Engineer |
| **P3 - Low** | Minor issues, no trading impact | Log warnings, cosmetic bugs, documentation gaps | **< 24 hours** | Development Team |

---

## Incident Response Team

### Roles & Responsibilities

| Role | Responsibility | Contact | Availability |
|------|---------------|---------|--------------|
| **Incident Commander (IC)** | Lead response, make decisions, coordinate team | On-Call Engineer | 24/7 |
| **Risk Officer** | Approve trading resume, review PnL impact | TBD | Market Hours |
| **Technical Lead** | Diagnose root cause, implement fixes | Senior Engineer | 24/7 |
| **Communications Lead** | Notify stakeholders, update status | Product Manager | Business Hours |
| **Subject Matter Expert (SME)** | Domain-specific expertise (IBKR, Kafka, etc.) | As needed | On-Call |

### On-Call Rotation

```
Week 1: Engineer A (Primary), Engineer B (Secondary)
Week 2: Engineer B (Primary), Engineer C (Secondary)
Week 3: Engineer C (Primary), Engineer A (Secondary)
```

**Handoff process:** Sunday 9:00 AM
**Handoff checklist:**
- Review open incidents
- Check system health metrics
- Verify access to all systems
- Test alerting chain

---

## General Response Process

### Step 1: Detect & Alert

**How incidents are detected:**
- Automated alerts (Prometheus, Grafana)
- Kill-switch triggers (PnL, Drawdown, PSR)
- Manual reports (team members, users)
- Monitoring dashboards

**Alert channels:**
- PagerDuty (P0/P1)
- Slack #incidents channel (all severities)
- Email (P2/P3)
- SMS (P0 only)

### Step 2: Assess & Classify

```bash
# Quick health check
./scripts/health_check.sh

# Check recent logs
tail -100 logs/*.log | grep -i "error\|fail\|critical"

# Review metrics
curl http://localhost:8000/metrics | grep -E "pnl|drawdown|latency"

# Determine severity
# P0: Trading halted, money at risk
# P1: Major functionality broken
# P2: Degraded performance
# P3: Minor issues
```

**Severity Decision Tree:**

```
Is trading halted or money at risk?
  └─ YES → P0 (Critical)
  └─ NO → Is major functionality broken?
      └─ YES → P1 (High)
      └─ NO → Is performance degraded?
          └─ YES → P2 (Medium)
          └─ NO → P3 (Low)
```

### Step 3: Respond

**For P0/P1 incidents:**

1. **Acknowledge** (within SLA)
   ```bash
   # Update incident status
   echo "$(date): Incident acknowledged by $USER" >> logs/incident_$(date +%Y%m%d_%H%M%S).log
   ```

2. **Assemble Team**
   - Page Incident Commander
   - Notify Risk Officer (if P0)
   - Pull in SMEs as needed

3. **Create War Room**
   - Slack channel: `#incident-YYYYMMDD-description`
   - Zoom/Google Meet link
   - Shared incident doc

4. **Stabilize System**
   - Stop bleeding (halt trading if needed)
   - Gather logs and metrics
   - Implement temporary fix

5. **Communicate**
   - Post initial status update
   - Set next update time (every 30 min for P0)

### Step 4: Recover

1. **Implement Fix**
   - Test in staging first (if time permits)
   - Deploy to production
   - Verify fix worked

2. **Monitor**
   - Watch metrics for 30 minutes
   - Confirm normal operations

3. **Resume Trading** (if halted)
   - Get approval from Risk Officer
   - Gradual ramp-up (start with small positions)
   - Monitor closely for first hour

### Step 5: Document

```bash
# Create incident report
cat > incidents/incident_$(date +%Y%m%d).md <<EOF
# Incident Report - $(date +%Y-%m-%d)

## Summary
- **Date/Time:** $(date)
- **Severity:** P0/P1/P2/P3
- **Duration:** X hours
- **Impact:** Trading halted, \$X PnL impact

## Timeline
- 10:00 - Alert triggered
- 10:05 - Incident acknowledged
- 10:15 - Root cause identified
- 10:30 - Fix deployed
- 11:00 - Incident resolved

## Root Cause
[Description]

## Resolution
[What was done]

## Action Items
- [ ] Implement permanent fix
- [ ] Add monitoring
- [ ] Update documentation
EOF
```

---

## Playbooks by Scenario

### P0-1: Kill-Switch Triggered (PnL Breach)

**Trigger:** Daily PnL < -5% (KILL_PNL = -0.05)

**Symptoms:**
- Trading automatically halted
- Alert: "Kill-switch activated: PnL breach"
- Log entry: `"PnL=-X% < KILL_PNL=-5%"`

**Response:**

```bash
# 1. VERIFY HALT (< 1 min)
ps aux | grep -E "strategy|order_plane"
# Should be no processes running

# 2. CHECK POSITIONS (< 2 min)
python scripts/check_positions.py
# Output: Current positions and PnL

# 3. REVIEW LOGS (< 5 min)
grep -i "kill.switch\|pnl" logs/*.log | tail -50

# 4. CALCULATE TRUE PnL (< 5 min)
python scripts/calculate_pnl.py --date $(date +%Y-%m-%d)

# 5. ASSESS SITUATION
# - Was it a real loss or data error?
# - What caused the loss?
# - Are positions still open?

# 6. NOTIFY STAKEHOLDERS (< 10 min)
# Send Slack message to #incidents
curl -X POST $SLACK_WEBHOOK_URL -d '{
  "text": "🚨 KILL-SWITCH TRIGGERED - PnL Breach",
  "attachments": [{
    "color": "danger",
    "fields": [
      {"title": "Severity", "value": "P0", "short": true},
      {"title": "PnL", "value": "-X%", "short": true},
      {"title": "Status", "value": "Trading Halted", "short": true}
    ]
  }]
}'

# 7. DECISION: Close positions or wait?
# IF positions are bleeding → close immediately
# IF market anomaly → wait for Risk Officer review

# 8. CLOSE POSITIONS (if needed)
python scripts/close_all_positions.py --confirm

# 9. DOCUMENT ROOT CAUSE
# - Review trades that caused loss
# - Check if strategy logic failed
# - Verify data quality

# 10. DO NOT RESTART without Risk Officer approval
```

**Recovery Criteria:**
- [ ] Root cause identified and documented
- [ ] Fix implemented and tested in staging
- [ ] Risk Officer approval obtained
- [ ] Monitoring enhanced to prevent recurrence
- [ ] Gradual restart plan approved

**Expected Resolution Time:** 1-4 hours (do not rush!)

---

### P0-2: Kill-Switch Triggered (Max Drawdown)

**Trigger:** Max Drawdown > 15% (MAX_DD = 0.15)

**Symptoms:**
- Trading halted
- Alert: "Kill-switch activated: Max Drawdown breach"
- Log: `"Drawdown=X% > MAX_DD=15%"`

**Response:**

```bash
# 1. VERIFY HALT
ps aux | grep -E "strategy|order"

# 2. CALCULATE DRAWDOWN
python scripts/calculate_drawdown.py
# Output: Peak equity, current equity, drawdown %

# 3. REVIEW HISTORICAL PERFORMANCE
python scripts/performance_report.py --days 30

# 4. CHECK FOR REGIME CHANGE
python scripts/detect_regime.py
# Has market regime shifted?

# 5. ASSESS RECOVERY PROBABILITY
# - Is this normal variance?
# - Has strategy broken?
# - Is recovery likely?

# 6. RISK OFFICER DECISION
# Option A: Close positions, stop trading
# Option B: Reduce exposure, continue with caution
# Option C: Wait for mean reversion

# 7. IMPLEMENT DECISION
# (see above playbook for closing positions)

# 8. POST-INCIDENT ANALYSIS
# - Backtest strategy on recent data
# - Check if parameters need adjustment
# - Consider regime filters
```

**Recovery Criteria:**
- [ ] Drawdown reason understood
- [ ] Strategy validated or fixed
- [ ] Risk parameters reviewed
- [ ] Approval from Risk Officer + CTO

**Expected Resolution Time:** 4-24 hours

---

### P0-3: Unauthorized Trading Detected

**Trigger:** Manual report, audit alert, unexpected positions

**Symptoms:**
- Positions in unauthorized instruments
- Trades outside market hours
- Orders exceeding position limits
- Unknown order sources

**Response:**

```bash
# 1. EMERGENCY HALT (< 1 min)
pkill -9 -f "strategy\|order_plane"

# 2. CANCEL ALL ORDERS (< 2 min)
python scripts/emergency_cancel_all_orders.py

# 3. REVIEW UNAUTHORIZED TRADES (< 5 min)
python scripts/audit_trades.py --today
# Look for anomalies

# 4. CHECK ORDER SOURCE (< 10 min)
grep -i "place_order" logs/*.log | tail -100
# Identify source of unauthorized orders

# 5. ASSESS SECURITY BREACH
# - Was it a bug or intrusion?
# - Are credentials compromised?
# - Is there malicious code?

# 6. SECURE SYSTEM (< 15 min)
# Rotate IBKR credentials
vault kv put secret/ibkr/live username="NEW" password="NEW"

# Revoke access tokens
vault token revoke <suspicious-token>

# Review audit logs
vault audit log | grep "unauthorized"

# 7. NOTIFY SECURITY TEAM
# Email: security@yourcompany.com
# Subject: URGENT - Unauthorized Trading Detected

# 8. PRESERVE EVIDENCE
# Copy logs
tar -czf evidence/incident_$(date +%Y%m%d).tar.gz logs/

# Freeze git state
git log -n 50 > evidence/git_log.txt

# 9. CLOSE UNAUTHORIZED POSITIONS
python scripts/close_positions.py --filter unauthorized

# 10. LEGAL/COMPLIANCE NOTIFICATION
# Contact: compliance@yourcompany.com
# Required for regulatory reporting
```

**Recovery Criteria:**
- [ ] Security breach contained
- [ ] All credentials rotated
- [ ] Unauthorized code removed
- [ ] Audit trail preserved
- [ ] Regulatory reporting completed
- [ ] External security audit passed

**Expected Resolution Time:** Immediate halt, 1-5 days for full resolution

---

### P1-1: IBKR Disconnection

**Trigger:** "Not connected" errors, no market data

**Symptoms:**
- Log errors: `"IBKRMarketClient connection failed"`
- No market data in Kafka topics
- Orders not executing

**Response:**

```bash
# 1. CHECK TWS/GATEWAY (< 1 min)
nc -zv localhost 7497  # TWS Paper
nc -zv localhost 4002  # Gateway Paper
nc -zv localhost 4001  # Gateway Live

# 2. CHECK IBKR STATUS PAGE
curl https://www.interactivebrokers.com/status
# Is IBKR having an outage?

# 3. CHECK LOCAL NETWORK
ping -c 10 8.8.8.8
# Is network working?

# 4. RESTART TWS/GATEWAY
# If running via Docker:
docker restart ibkr-gateway

# If running locally:
# Kill and restart TWS/Gateway manually

# 5. WAIT FOR RECONNECTION (30 sec)
sleep 30

# 6. VERIFY CONNECTION
tail -f logs/data_plane.log | grep "connected"
# Should see: "IBKR connected successfully"

# 7. CHECK DATA FLOW
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic market_events \
  --from-beginning \
  --max-messages 10

# 8. IF STILL FAILING → Check credentials
python -c "
from data_plane.config.utils import load_data_plane_config
cfg = load_data_plane_config()
print(cfg.broker)
"

# 9. IF PERSISTENT → Escalate
# Contact IBKR support: +1-877-442-2757
# Have account number ready
```

**Recovery Criteria:**
- [ ] Connection restored
- [ ] Market data flowing
- [ ] Orders executing normally
- [ ] Monitoring confirms stability

**Expected Resolution Time:** 5-30 minutes

---

### P1-2: Kafka Failure

**Trigger:** "Broker not available", message delivery failures

**Symptoms:**
- Log errors: `"Failed to send message to Kafka"`
- Consumer lag increasing
- No data in topics

**Response:**

```bash
# 1. CHECK KAFKA STATUS (< 1 min)
docker-compose ps kafka
# Should be "Up"

# 2. CHECK KAFKA LOGS
docker logs kafka | tail -50

# 3. RESTART KAFKA (if needed)
docker-compose restart kafka

# Wait for startup
sleep 30

# 4. VERIFY TOPICS EXIST
kafka-topics.sh --list --bootstrap-server localhost:9092
# Should see: market_events, order_intents, exec_reports

# 5. CHECK CONSUMER LAG
kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group algo_trade_consumer \
  --describe

# 6. IF LAG > 1000 messages → Replay
# Reset offsets to latest
kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group algo_trade_consumer \
  --topic market_events \
  --reset-offsets \
  --to-latest \
  --execute

# 7. RESTART CONSUMERS
pkill -f "data_plane\|strategy\|order_plane"
# Then restart via RUNBOOK.md procedures

# 8. VERIFY DATA FLOW
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic market_events \
  --from-beginning \
  --max-messages 10
```

**Recovery Criteria:**
- [ ] Kafka cluster healthy
- [ ] All topics available
- [ ] Consumer lag < 100 messages
- [ ] Data flowing end-to-end

**Expected Resolution Time:** 10-30 minutes

---

### P1-3: Order Rejection Spike

**Trigger:** >10% order rejection rate

**Symptoms:**
- Alert: "High rejection rate detected"
- Log errors: `"Order rejected: [reason]"`
- Low fill rate

**Response:**

```bash
# 1. CHECK REJECTION REASONS (< 2 min)
grep "reject" logs/order_plane.log | tail -50 | \
  awk '{print $NF}' | sort | uniq -c | sort -rn

# Common reasons:
# - "Insufficient buying power"
# - "Risk limit exceeded"
# - "Invalid order"
# - "Market closed"
# - "Symbol not tradable"

# 2. INSUFFICIENT BUYING POWER
# Check account balance
python scripts/check_account.py
# If low → reduce position sizes or add capital

# 3. RISK LIMITS BREACHED
# Check current exposure
python scripts/check_exposure.py
# If high → reduce exposure via config

# Edit risk limits
nano algo_trade/core/config.py
# Increase BOX_LIM or MAX_GROSS_EXPOSURE

# 4. INVALID ORDERS
# Check order validation logic
grep "validation" logs/order_plane.log | tail -20

# Common issues:
# - Negative quantities
# - Invalid symbols
# - Out-of-hours orders

# 5. MARKET CLOSED
# Check market hours
python -c "
from datetime import datetime
import pytz
now = datetime.now(pytz.timezone('America/New_York'))
print(f'NY time: {now}')
print('Market hours: 9:30 AM - 4:00 PM ET')
"

# 6. FIX ROOT CAUSE
# (depends on rejection reason)

# 7. TEST FIX IN PAPER
# Restart with paper trading
IBKR_PORT=4002 python -m order_plane.app.orchestrator

# 8. MONITOR REJECTION RATE
watch -n 10 "grep 'reject' logs/order_plane.log | wc -l"
```

**Recovery Criteria:**
- [ ] Rejection rate < 5%
- [ ] Root cause identified and fixed
- [ ] Account/risk limits adjusted
- [ ] Validation logic updated

**Expected Resolution Time:** 30 minutes - 2 hours

---

### P2-1: High Latency

**Trigger:** p95 Intent→Ack latency > 1 second

**Symptoms:**
- Alert: "High latency detected"
- Slow order execution
- Missed trading opportunities

**Response:**

```bash
# 1. CHECK SYSTEM LOAD (< 1 min)
top
uptime
# Is CPU/memory high?

# 2. CHECK NETWORK
ping -c 10 localhost
# Is network congested?

# 3. PROFILE SLOW COMPONENTS
# Find bottleneck
python -m cProfile -o profile.stats -m data_plane.app.main

# Analyze profile
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative')
p.print_stats(20)
"

# 4. CHECK KAFKA LAG
kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --group algo_trade_consumer --describe

# 5. OPTIMIZE PERFORMANCE
# Reduce signal frequency
nano algo_trade/core/config.py
# Increase SIGNAL_FREQ_SEC from 60 to 120

# Reduce portfolio size
# (fewer assets = faster computation)

# 6. SCALE RESOURCES
# Add more CPU/memory if needed
# (requires infrastructure change)

# 7. RESTART SERVICES
# (clears memory leaks)
./scripts/graceful_restart.sh
```

**Recovery Criteria:**
- [ ] Latency p95 < 200ms
- [ ] Bottleneck identified and resolved
- [ ] Performance testing passed

**Expected Resolution Time:** 1-4 hours

---

### P2-2: Data Quality Issues

**Trigger:** Validation failures, stale data, missing data

**Symptoms:**
- Alert: "Data quality gate failed"
- Log: `"Staleness > 60s"`
- Signals not generating

**Response:**

```bash
# 1. CHECK DATA FRESHNESS
python -c "
from data_plane.qa.gates import check_staleness
result = check_staleness(df)
print(result)
"

# 2. CHECK DATA COMPLETENESS
python -c "
from data_plane.qa.gates import check_completeness
result = check_completeness(df)
print(result)
"

# 3. CHECK DATA SOURCE
# Is IBKR sending data?
kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic market_events \
  --max-messages 10

# 4. IDENTIFY GAP
# What time range is missing?
python scripts/find_data_gaps.py --start 2025-11-16

# 5. BACKFILL DATA (if possible)
python scripts/backfill_data.py --start 2025-11-16T10:00 --end 2025-11-16T11:00

# 6. ADJUST QA THRESHOLDS (temporary)
# If market volatility is high
nano data_plane/qa/gates.py
# Increase STALENESS_THRESHOLD from 60 to 120

# 7. NOTIFY DATA TEAM
# Email: data-ops@yourcompany.com
```

**Recovery Criteria:**
- [ ] Data freshness < 60 seconds
- [ ] Data completeness > 95%
- [ ] Validation gates passing
- [ ] Root cause identified

**Expected Resolution Time:** 30 minutes - 2 hours

---

## Post-Incident Review

### Timeline: Within 48 Hours

**Required Attendees:**
- Incident Commander
- Technical Lead
- Risk Officer (for P0/P1)
- Engineering Manager
- All responders

### Agenda Template

```markdown
# Post-Incident Review - [Date]

## Incident Summary
- **Date/Time:** [Start - End]
- **Severity:** P0/P1/P2/P3
- **Duration:** X hours
- **Impact:** Trading halted, $X PnL impact, X customers affected

## What Went Well
- Quick detection (alert fired within 1 minute)
- Team assembled rapidly
- Clear communication

## What Went Poorly
- Delayed root cause identification (30 min)
- Lack of runbook for this scenario
- Insufficient monitoring

## Timeline
| Time | Event | Action Taken |
|------|-------|--------------|
| 10:00 | Alert fired | On-call paged |
| 10:05 | IC joined | Started triage |
| 10:15 | Root cause found | Implemented fix |
| 10:30 | Fix deployed | Verified resolution |

## Root Cause Analysis (5 Whys)
1. Why did trading halt? → PnL dropped below -5%
2. Why did PnL drop? → Strategy lost money on 10 trades
3. Why did strategy lose? → Signal logic had a bug
4. Why was there a bug? → Insufficient testing
5. Why insufficient testing? → No property-based tests for signals

**Root Cause:** Lack of property-based tests for signal logic

## Action Items
- [ ] Add property-based tests for all signals (Owner: Dev Team, Due: 1 week)
- [ ] Update INCIDENT_PLAYBOOK.md with this scenario (Owner: SRE, Due: 2 days)
- [ ] Add monitoring for signal quality (Owner: Data Team, Due: 1 week)
- [ ] Review all other signals for similar bugs (Owner: Quant Team, Due: 1 week)

## Lessons Learned
- Property-based testing catches edge cases
- Need better signal validation before trading
- Consider adding "dry run" mode for new signals
```

### Follow-Up

- Schedule follow-up meeting in 2 weeks
- Track action items in project management tool
- Update documentation
- Share learnings with broader team

---

## Communication Templates

### Initial Incident Notification

**Slack Message:**

```
🚨 INCIDENT ALERT 🚨

Severity: P0/P1/P2/P3
Status: Investigating
Impact: [Trading halted / Degraded performance / etc.]
Start Time: YYYY-MM-DD HH:MM UTC

Incident Commander: @username
War Room: #incident-YYYYMMDD-description

Details:
[Brief description of what's happening]

Next update in: 30 minutes
```

### Status Update

```
📊 INCIDENT UPDATE

Status: [Investigating / Identified / Fixing / Monitoring / Resolved]
Time Elapsed: X minutes

Progress:
✅ Root cause identified: [description]
🔄 Fix in progress: [what's being done]
⏳ ETA for resolution: X minutes

Impact:
- Trading: [Halted / Normal]
- PnL: [Amount]
- Data: [Flowing / Stale]

Next update in: 30 minutes
```

### Resolution Notification

```
✅ INCIDENT RESOLVED

Severity: P0/P1/P2/P3
Duration: X hours Y minutes
Impact: [Summary]

Resolution:
[What was done to fix]

Root Cause:
[Brief explanation]

Follow-Up:
- Post-incident review scheduled for [date]
- Action items tracked in [link]
- Documentation updated: [links]

Thanks to: @user1 @user2 @user3
```

---

## Escalation Procedures

### When to Escalate

**From On-Call to Senior Engineer:**
- Can't resolve within 30 minutes
- Need architectural expertise
- Unfamiliar with affected system

**From Senior Engineer to Management:**
- Incident duration > 2 hours
- Customer impact is severe
- Media/PR implications
- Regulatory reporting required

**From Management to Executive:**
- Major financial impact (> $X)
- Legal/compliance issues
- Reputational damage
- Multi-day outage

### Escalation Checklist

Before escalating:
- [ ] Gather all relevant data (logs, metrics, screenshots)
- [ ] Document actions taken so far
- [ ] Prepare concise summary (2-3 sentences)
- [ ] Have specific ask (decision needed, resources required)

### Contact List

| Level | Name | Phone | Email | Availability |
|-------|------|-------|-------|--------------|
| **L1: On-Call** | TBD | +972-XX-XXX-XXXX | oncall@company.com | 24/7 |
| **L2: Senior Engineer** | TBD | +972-XX-XXX-XXXX | senior@company.com | 24/7 |
| **L3: Risk Officer** | TBD | +972-XX-XXX-XXXX | risk@company.com | Market Hours |
| **L4: CTO** | TBD | +972-XX-XXX-XXXX | cto@company.com | 24/7 (urgent) |
| **L5: CEO** | TBD | +972-XX-XXX-XXXX | ceo@company.com | Critical only |

---

## Tools & Resources

### Incident Management

- **PagerDuty:** https://yourcompany.pagerduty.com
- **Incident Dashboard:** http://localhost:3000/incidents
- **Logs:** /var/log/algo-trade/
- **Metrics:** http://localhost:8000/metrics

### Runbooks

- **RUNBOOK.md** - Start/stop procedures
- **ROLLBACK_PROCEDURE.md** - Deployment rollback
- **SECRETS_MANAGEMENT.md** - Credential rotation

### Scripts

```bash
# Health check
./scripts/health_check.sh

# Check positions
./scripts/check_positions.py

# Calculate PnL
./scripts/calculate_pnl.py

# Emergency halt
./scripts/emergency_halt.sh

# Close all positions
./scripts/close_all_positions.py

# Audit trades
./scripts/audit_trades.py
```

---

## Training & Drills

### Quarterly Fire Drills

Schedule quarterly incident response drills:

**Q1:** Kill-switch scenario
**Q2:** IBKR disconnect scenario
**Q3:** Security breach scenario
**Q4:** Multi-component failure

### Drill Format

1. **Preparation** (1 week before)
   - Announce drill date
   - Review playbook
   - Ensure tools accessible

2. **Execution** (1 hour)
   - Inject simulated incident
   - Team responds as if real
   - Facilitator observes

3. **Debrief** (30 minutes)
   - What went well?
   - What needs improvement?
   - Update playbook

4. **Follow-Up** (1 week after)
   - Implement improvements
   - Update documentation
   - Share learnings

---

## Appendix

### Incident Log Template

```bash
# Create new incident log
cat > logs/incident_$(date +%Y%m%d_%H%M%S).log <<EOF
=== INCIDENT LOG ===
Date: $(date)
Severity: [P0/P1/P2/P3]
IC: [Name]
Team: [Names]

=== TIMELINE ===
[HH:MM] Alert fired: [description]
[HH:MM] IC joined war room
[HH:MM] Root cause identified: [description]
[HH:MM] Fix deployed: [description]
[HH:MM] Incident resolved

=== ACTIONS TAKEN ===
1. [Action]
2. [Action]

=== IMPACT ===
Trading: [Halted/Normal]
PnL: [$X]
Duration: [X hours]

=== ROOT CAUSE ===
[Description]

=== LESSONS LEARNED ===
1. [Lesson]
2. [Lesson]

=== ACTION ITEMS ===
- [ ] [Item] (Owner: [Name], Due: [Date])
EOF
```

### Reference Documents

- [RUNBOOK.md](./RUNBOOK.md) - Operational procedures
- [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md) - Secrets handling
- [RACI.md](./RACI.md) - Responsibility matrix
- [PRE_LIVE_CHECKLIST.md](./PRE_LIVE_CHECKLIST.md) - Go-live gates
- [ROLLBACK_PROCEDURE.md](./ROLLBACK_PROCEDURE.md) - Deployment rollback

---

**Document Owner:** SRE Team
**Reviewers:** Risk Officer, CTO, Security Team
**Next Review:** Quarterly or after major incidents
**Status:** Draft → Review → Approved → Live

---

*This document is confidential and intended for internal use only.*
