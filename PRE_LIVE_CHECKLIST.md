# Pre-Live Checklist - בדיקה לפני Production
## Production Readiness Checklist

**תאריך:** 2025-11-07
**גרסה:** 1.0
**מצב:** Template

---

## 🎯 מטרה

רשימת בדיקה מקיפה לאימות מוכנות המערכת ל-Production.
**חובה לעבור על כל הסעיפים לפני Go-Live!**

---

## ✅ רשימת בדיקה

### 0. גורמי החתימה (Sign-Off)

- [ ] **CTO** - אישור טכני כללי
- [ ] **Risk Officer** - אישור Risk Policy ופרמטרי סיכון
- [ ] **Lead Quant** - אישור תוצאות Backtest ו-Paper Trading
- [ ] **DevOps Lead** - אישור תשתית ו-Deployment
- [ ] **QA Lead** - אישור Test Coverage ו-Quality Gates

**תאריך אישור:** _______________

---

### 1. Code Quality & Testing (80 נקודות)

#### 1.1 Test Coverage
- [ ] Unit Test Coverage ≥ 80%
- [ ] Integration Test Coverage ≥ 70%
- [ ] End-to-End Tests pass (6 scenarios)
- [ ] Property-Based Tests pass (MR-pass-rate ≥ 90%)
- [ ] Metamorphic Tests pass (4 relations validated)
- [ ] Chaos Tests pass (recovery ≤ 30s)
- [ ] Performance Tests pass (p95 latency ≤ 50ms)

**Score:** ____/7 (100% required)

#### 1.2 Code Quality
- [ ] All linters pass (black, flake8, isort)
- [ ] Type checking passes (mypy)
- [ ] Static analysis passes (pylint ≥ 8.0)
- [ ] Security scan passes (bandit, safety)
- [ ] No high-severity vulnerabilities
- [ ] Code review completed by 2+ engineers

**Score:** ____/6 (100% required)

#### 1.3 CI/CD
- [ ] GitHub Actions pipeline green
- [ ] Coverage gate enforced (≥80%)
- [ ] Governance gate enforced (risk params)
- [ ] Schema compatibility checks enabled
- [ ] Automated deployment scripts tested
- [ ] Rollback procedure documented and tested

**Score:** ____/6 (100% required)

---

### 2. Configuration & Secrets (60 נקודות)

#### 2.1 Configuration
- [ ] `targets.yaml` reviewed and approved
- [ ] Risk parameters (KILL_PNL, MAX_DD, BOX_LIM) signed off
- [ ] Trading hours configured correctly
- [ ] Market calendar updated (holidays, DST)
- [ ] Asset universe validated (assets.csv)
- [ ] Lot sizes and tick sizes verified

**Score:** ____/6 (100% required)

#### 2.2 Secrets Management
- [ ] API keys stored in Vault/Secrets Manager
- [ ] No hardcoded secrets in code
- [ ] `.env` files gitignored
- [ ] Secrets rotation policy documented
- [ ] Access control (RBAC) configured
- [ ] Audit logging enabled

**Score:** ____/6 (100% required)

---

### 3. IBKR Integration (100 נקודות)

#### 3.1 Connection
- [ ] IBKR Paper Trading account active
- [ ] TWS/Gateway version verified (≥10.19)
- [ ] Connection stable (uptime >99%)
- [ ] Reconnection logic tested
- [ ] Pacing limits respected (<50 req/sec)
- [ ] Market data subscriptions active

**Score:** ____/6

#### 3.2 Order Execution
- [ ] Order placement tested (Market, Limit)
- [ ] Order cancellation tested
- [ ] Partial fills handled correctly
- [ ] Order rejections handled gracefully
- [ ] Execution reports parsed correctly
- [ ] Commission calculations verified

**Score:** ____/6

#### 3.3 Account & Positions
- [ ] Account info API working
- [ ] Position tracking accurate
- [ ] Cash balance updated correctly
- [ ] Buying power checks working
- [ ] P&L calculations verified
- [ ] NAV updates real-time

**Score:** ____/6

---

### 4. Data Pipeline (70 נקודות)

#### 4.1 Data Ingestion
- [ ] Real-time data flowing (latency <100ms)
- [ ] Historical data loaded correctly
- [ ] Data normalization working
- [ ] QA Gates passing (Completeness, Freshness, NTP)
- [ ] Dead Letter Queue configured
- [ ] Data backup strategy in place

**Score:** ____/6

#### 4.2 Kafka Infrastructure
- [ ] Kafka cluster healthy
- [ ] Topics created (market_events, order_intents, exec_reports)
- [ ] Retention policies configured (7 days)
- [ ] Replication factor = 3 (production)
- [ ] Consumer groups configured
- [ ] Monitoring enabled

**Score:** ____/6

---

### 5. Algorithms & Strategies (90 נקודות)

#### 5.1 Backtesting
- [ ] Backtests completed (2020-2025)
- [ ] Sharpe Ratio > 1.5
- [ ] Max Drawdown < 10%
- [ ] PSR (Probabilistic Sharpe) > 0.95
- [ ] DSR (Deflated Sharpe) > 1.0
- [ ] PBO (Prob. Backtest Overfitting) < 0.5

**Score:** ____/6 (100% required)

#### 5.2 Walk-Forward Validation
- [ ] CSCV completed (M=16 splits)
- [ ] Median Sharpe > 0.8
- [ ] Consistent performance across splits
- [ ] No significant overfitting detected
- [ ] Parameter sensitivity analyzed
- [ ] Robustness verified

**Score:** ____/6 (100% required)

#### 5.3 Paper Trading
- [ ] Paper trading completed (30 days minimum)
- [ ] Paper Sharpe ≥ 1.0
- [ ] Paper P&L > 0
- [ ] Hit rate > 60%
- [ ] Order fill rate > 98%
- [ ] No unexpected behaviors

**Score:** ____/6 (100% required)

---

### 6. Risk Management (100 נקודות)

#### 6.1 Risk Policy
- [ ] Risk Policy document signed
- [ ] Kill-Switches configured:
  - [ ] PnL Kill (default: -5%)
  - [ ] PSR Kill (default: <0.20)
  - [ ] Max DD Kill (default: >15%)
- [ ] Exposure limits configured:
  - [ ] BOX_LIM (default: 25%)
  - [ ] GROSS_LIM (Calm: 2.5, Normal: 2.0, Storm: 1.0)
  - [ ] NET_LIM (Calm: 1.0, Normal: 0.8, Storm: 0.4)
- [ ] Regime detection validated
- [ ] Blind-Spot agent working
- [ ] Covariance estimation verified

**Score:** ____/9 (100% required)

---

### 7. Monitoring & Observability (80 נקודות)

#### 7.1 Metrics
- [ ] Prometheus `/metrics` endpoint active
- [ ] Key metrics exposed:
  - [ ] intent_to_ack_latency_ms
  - [ ] pnl_cumulative
  - [ ] sharpe_ratio_rolling_30d
  - [ ] max_drawdown_current
  - [ ] error_rate
  - [ ] throughput_msg_per_sec
- [ ] Metrics scraped successfully

**Score:** ____/7

#### 7.2 Dashboards
- [ ] Grafana dashboards created:
  - [ ] System Health
  - [ ] Strategy Performance
  - [ ] Risk Monitor
  - [ ] Data Quality
- [ ] Dashboards accessible
- [ ] Dashboards updating real-time

**Score:** ____/6

#### 7.3 Alerting
- [ ] Alert rules configured (≥10 rules)
- [ ] Slack/Email notifications working
- [ ] PagerDuty/On-call setup
- [ ] Alert escalation policy defined
- [ ] Alert playbooks documented
- [ ] Alert testing completed

**Score:** ____/6

---

### 8. Infrastructure & Deployment (70 נקודות)

#### 8.1 Containerization
- [ ] Dockerfiles created and tested
- [ ] docker-compose.yml working
- [ ] Multi-stage builds optimized
- [ ] Image size < 1GB
- [ ] Health checks configured
- [ ] Resource limits defined

**Score:** ____/6

#### 8.2 Cloud Deployment
- [ ] AWS/Cloud account configured
- [ ] EC2/ECS instances provisioned
- [ ] Auto-scaling policies defined
- [ ] Load balancers configured (if needed)
- [ ] VPC/Security groups configured
- [ ] Cost monitoring enabled

**Score:** ____/6

#### 8.3 Disaster Recovery
- [ ] Backup strategy documented
- [ ] Daily snapshots to S3
- [ ] Disaster recovery plan tested
- [ ] RTO (Recovery Time Objective) < 1 hour
- [ ] RPO (Recovery Point Objective) < 15 minutes
- [ ] Failover tested

**Score:** ____/6

---

### 9. Security & Compliance (60 נקודות)

#### 9.1 Security
- [ ] TLS/SSL enabled for all connections
- [ ] Encryption at rest enabled
- [ ] Network firewall configured
- [ ] Access logs enabled
- [ ] Intrusion detection configured
- [ ] Penetration testing completed

**Score:** ____/6

#### 9.2 Compliance (if applicable)
- [ ] MiFID II compliance (if EU)
- [ ] SEC compliance (if US)
- [ ] Audit trail complete
- [ ] Trade reporting configured
- [ ] Record retention policy defined
- [ ] Compliance review completed

**Score:** ____/6 (if applicable)

---

### 10. Documentation (50 נקודות)

- [ ] README.md up to date
- [ ] ARCHITECTURE.md complete
- [ ] RUNBOOK.md complete
- [ ] PRE_LIVE_CHECKLIST.md (this document)
- [ ] API documentation (Sphinx)
- [ ] Configuration guide
- [ ] Troubleshooting guide
- [ ] Incident response procedures
- [ ] Change management process
- [ ] Runbook reviewed by team

**Score:** ____/10 (100% required)

---

## 📊 סיכום ציונים (Score Summary)

| Category | Score | Weight | Weighted Score |
|----------|-------|--------|----------------|
| 1. Code Quality & Testing | ___/19 | 15% | ___ |
| 2. Configuration & Secrets | ___/12 | 10% | ___ |
| 3. IBKR Integration | ___/18 | 15% | ___ |
| 4. Data Pipeline | ___/12 | 10% | ___ |
| 5. Algorithms & Strategies | ___/18 | 20% | ___ |
| 6. Risk Management | ___/9 | 15% | ___ |
| 7. Monitoring & Observability | ___/19 | 10% | ___ |
| 8. Infrastructure & Deployment | ___/18 | 10% | ___ |
| 9. Security & Compliance | ___/12 | 5% | ___ |
| 10. Documentation | ___/10 | 5% | ___ |
| **TOTAL** | | **100%** | **___** |

**Minimum passing score: 95/100**

---

## ✅ Final Sign-Off

**Production Go-Live Approved:** ☐ YES  ☐ NO

**Conditions (if NO):**
_______________________________________________________________________
_______________________________________________________________________

**Signatures:**

| Role | Name | Signature | Date |
|------|------|-----------|------|
| CTO | ____________ | ____________ | ________ |
| Risk Officer | ____________ | ____________ | ________ |
| Lead Quant | ____________ | ____________ | ________ |
| DevOps Lead | ____________ | ____________ | ________ |
| QA Lead | ____________ | ____________ | ________ |

---

## 📅 Post-Go-Live

- [ ] **Day 1 Review:** Check all metrics after 1st trading day
- [ ] **Week 1 Review:** Weekly performance report
- [ ] **Month 1 Review:** Full system review and optimization
- [ ] **Incident Log:** Document all issues in `logs/incidents.log`
- [ ] **Continuous Improvement:** Update checklist based on learnings

---

**נוצר על ידי:** Claude Code (AI Assistant)
**תאריך:** 2025-11-07
**לעדכון:** לאחר כל production release
