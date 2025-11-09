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

### 9. Security & Compliance (150 נקודות)

#### 9.1 Security Strategy & Threat Model
- [ ] **SECURITY_EXECUTION_SUMMARY.md** reviewed and approved
- [ ] Compliance framework defined (SOC 2 Type II baseline)
- [ ] Threat model documented (Insider-threat-first)
- [ ] Attack vectors ranked and mitigated
- [ ] Security event definitions documented (4 severity levels)
- [ ] Incident response playbook tested (≤30 days)

**Score:** ____/6 (100% required)

#### 9.2 Secrets Management
- [ ] AWS Secrets Manager configured (or HashiCorp Vault)
- [ ] No secrets in code/env files (validated via gitleaks)
- [ ] Secrets rotation policy: Prod (30d), Paper (90d)
- [ ] Runtime-only secret injection (never build-time)
- [ ] Secret access audit trail enabled (2-year retention)
- [ ] Secrets detection in CI/CD (TruffleHog + gitleaks)
- [ ] Log sanitization tested (no API keys/passwords in logs)

**Score:** ____/7 (100% required)

#### 9.3 Identity & Access Management (IAM)
- [ ] **IAM_POLICY_FRAMEWORK.md** reviewed and approved
- [ ] 5 roles defined: Trader, DevOps, QA, Service, Governance
- [ ] Permission matrix documented and validated
- [ ] Just-In-Time (JIT) access configured (15-min approval window)
- [ ] Least privilege validation in CI/CD
- [ ] Governance approval workflow for permission escalations
- [ ] Service accounts use STS temporary credentials (1-hour TTL)
- [ ] IAM policy linter passing (no wildcard resources/actions)

**Score:** ____/8 (100% required)

#### 9.4 Encryption & Keys
- [ ] TLS 1.3 enforced for all external connections
- [ ] Cipher suites whitelisted (AES-256-GCM, ChaCha20)
- [ ] Digital signatures: Ed25519 for orders, ECDSA-P384 for code
- [ ] Key rotation: 90-day schedule with 15-min grace period
- [ ] Encryption at rest: AES-256 (RDS, S3, CloudWatch Logs)
- [ ] Key lifecycle management documented
- [ ] File integrity verification (SHA-256 + Ed25519 signatures)

**Score:** ____/7 (100% required)

#### 9.5 Security Monitoring & Observability
- [ ] Security event log schema validated
- [ ] SIEM configured (Datadog or ELK Stack)
- [ ] 4-level alert severity matrix implemented
- [ ] Alert thresholds configured (P0: <5min, P1: <1hour)
- [ ] Event correlation rules defined (≥5 rules)
- [ ] On-call rotation scheduled (Trader: 9-18 UTC, Security: 24/7)
- [ ] Data retention policy: Critical (2yr), Sensitive (1yr), Routine (7d)
- [ ] Log purge automation tested

**Score:** ____/8 (100% required)

#### 9.6 CI/CD Security Gates
- [ ] GitHub Actions security gates enabled
- [ ] Secrets detection: TruffleHog + gitleaks (blocking)
- [ ] Dependency scanning: Snyk + safety + pip-audit
- [ ] Container scanning: Trivy for Docker images
- [ ] Code security: Bandit for Python (no high/critical issues)
- [ ] IAM policy validation: Automated least privilege checks
- [ ] Pre-commit hooks configured (detect-secrets)
- [ ] License compliance check (no GPL/AGPL violations)

**Score:** ____/8 (100% required)

#### 9.7 Compliance & Audit (if applicable)
- [ ] SOC 2 Type II baseline requirements met
- [ ] MiFID II compliance (if EU trading)
- [ ] Audit trail complete (2-year retention)
- [ ] Trade reporting configured (if required)
- [ ] Record retention policy defined and automated
- [ ] Monthly compliance reports generated
- [ ] Governance sign-offs obtained (CTO, Security, Governance Officer)

**Score:** ____/7 (if applicable)

#### 9.8 Penetration Testing & Security Audit
- [ ] Security framework reviewed by external auditor
- [ ] Red-team exercise: Extract API key from logs (should fail)
- [ ] Simulation: Malicious dependency update (should trigger alert)
- [ ] Stress test: 100 failed login attempts (should trigger lockout)
- [ ] Chaos test: Kill IBKR connection mid-trade (should reconnect)
- [ ] JIT access approval workflow tested
- [ ] Kill-switch activation tested (emergency halt)
- [ ] Rollback procedure tested (<30s recovery)

**Score:** ____/8 (100% required)

**Total Security Score:** ____/59 (100% required for sections 9.1-9.6, 9.8)

---

### 10. Documentation (70 נקודות)

#### 10.1 Core Documentation
- [ ] README.md up to date
- [ ] ARCHITECTURE.md complete
- [ ] RUNBOOK.md complete
- [ ] PRE_LIVE_CHECKLIST.md (this document)
- [ ] API documentation (Sphinx)

**Score:** ____/5 (100% required)

#### 10.2 Security Documentation
- [ ] **SECURITY_EXECUTION_SUMMARY.md** complete
- [ ] **IAM_POLICY_FRAMEWORK.md** complete
- [ ] **SECRETS_MANAGEMENT_POLICY.md** complete (optional for Phase 1)
- [ ] **ENCRYPTION_KEY_POLICY.md** complete (optional for Phase 1)
- [ ] **SECURITY_MONITORING_POLICY.md** complete (optional for Phase 1)

**Score:** ____/5 (SECURITY_EXECUTION_SUMMARY.md + IAM_POLICY_FRAMEWORK.md required)

#### 10.3 Operational Documentation
- [ ] Configuration guide
- [ ] Troubleshooting guide
- [ ] Incident response procedures
- [ ] Change management process
- [ ] Rollback procedure (ROLLBACK_PROCEDURE.md)
- [ ] On-call runbook

**Score:** ____/6 (100% required)

---

## 📊 סיכום ציונים (Score Summary)

| Category | Score | Weight | Weighted Score |
|----------|-------|--------|----------------|
| 1. Code Quality & Testing | ___/19 | 12% | ___ |
| 2. Configuration & Secrets | ___/12 | 8% | ___ |
| 3. IBKR Integration | ___/18 | 12% | ___ |
| 4. Data Pipeline | ___/12 | 8% | ___ |
| 5. Algorithms & Strategies | ___/18 | 15% | ___ |
| 6. Risk Management | ___/9 | 12% | ___ |
| 7. Monitoring & Observability | ___/19 | 8% | ___ |
| 8. Infrastructure & Deployment | ___/18 | 8% | ___ |
| **9. Security & Compliance** | **___/59** | **15%** | **___** |
| 10. Documentation | ___/16 | 5% | ___ |
| **TOTAL** | | **100%** | **___** |

**Minimum passing score: 95/100**
**Security is now 15% of total score** (reflecting critical importance for Go-Live)

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
| **Security Officer** | ____________ | ____________ | ________ |
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
