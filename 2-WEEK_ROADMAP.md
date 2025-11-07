# Cloudecode: 2-Week PR Roadmap (2025-11-07 → 2025-11-21)

## תקציר ניהולי

**יעד**: סגירת הפערים הקריטיים ביותר שחוסמים את המעבר ל-Paper Trading
**משאבים נדרשים**: 2-3 developers, 1 DevOps engineer (50%)
**תוצאה צפויה**: 6 PRs merged, צמצום פערים ב-40%, מוכנות להתחלת Paper Trading

---

## שבוע 1: תשתיות קריטיות (Nov 7–14)

### PR-001: [תחום 6+8] Docker & Kafka Setup
**Owner**: DevOps
**Due**: Nov 10 (יום ה')
**עדיפות**: 🔴 P0 - חוסם כל פיתוח נוסף

**תיאור**:
התקנת תשתית containerization ו-message bus לפיתוח מקומי.

**Deliverables**:
- [ ] `Dockerfile` מולטי-שלבי (multi-stage build):
  - Stage 1: build dependencies
  - Stage 2: runtime optimized
- [ ] `docker-compose.yml` עם 5 שירותים:
  - Kafka + Zookeeper
  - Prometheus
  - Grafana (basic setup)
  - data_plane (placeholder)
  - strategy_plane (placeholder)
- [ ] `.env.example` template עם:
  - `IBKR_HOST`, `IBKR_PORT`, `IBKR_CLIENT_ID`
  - `KAFKA_BROKER`
  - `PROMETHEUS_PORT`
- [ ] `requirements.txt` מלא עם כל התלויות:
  - `ib-insync`
  - `kafka-python`
  - `prometheus-client`
  - `pyyaml`, `numpy`, `pandas`, `cvxpy`, `scipy`, `scikit-learn` (existing)
  - `pytest`, `pytest-cov`, `black`, `mypy` (dev dependencies)

**קריטריונים להצלחה**:
- `docker-compose up` מתחיל את כל השירותים ללא שגיאות
- Kafka broker accessible ב-localhost:9092
- Prometheus scraping metrics מ-placeholder services

**קבצים מושפעים**:
- (new) `Dockerfile`
- (new) `docker-compose.yml`
- (new) `.env.example`
- (update) `requirements.txt`
- (new) `docs/DOCKER_SETUP.md` - הוראות התקנה

**תחומים**: #1 (ארכיטקטורה), #8 (קונטיינריזציה)

---

### PR-002: [תחום 6] Basic Unit Tests (Phase 1)
**Owner**: QA Lead
**Due**: Nov 11 (יום ו')
**עדיפות**: 🔴 P0 - חוסם merge עתידי

**תיאור**:
יצירת תשתית בדיקות ו-3 test suites ראשונים.

**Deliverables**:
- [ ] `tests/conftest.py` עם fixtures:
  - `synthetic_data_fixture` - נתונים סינתטיים עם seed=42
  - `mock_ibkr_client` - mock של IBKR connection
  - `sample_config` - config fixture
- [ ] `tests/test_signals.py` (10+ tests):
  - test OFI calculation
  - test signal normalization
  - test IC computation
  - test orthogonalization
- [ ] `tests/test_qp_solver.py` (8+ tests):
  - test basic QP solution
  - test constraints (box, gross, net)
  - test infeasible scenario → fallback
  - test volatility targeting
- [ ] `tests/test_risk.py` (6+ tests):
  - test kill-switch triggers (PnL, PSR, DD)
  - test regime detection
  - test covariance drift
- [ ] GitHub Actions CI config:
  - `.github/workflows/test.yml`
  - Run tests ב-every push
  - Generate coverage report (target: 30%+ בphase 1)

**קריטריונים להצלחה**:
- כל 24+ tests עוברים
- Coverage ≥ 30% (baseline)
- CI pipeline רץ בהצלחה

**קבצים מושפעים**:
- (update) `tests/test_signals.py` - מריק ל-10+ tests
- (update) `tests/test_qp_solver.py` - מריק ל-8+ tests
- (new) `tests/test_risk.py`
- (new) `tests/conftest.py`
- (new) `.github/workflows/test.yml`

**תחומים**: #6 (CI/CD ובדיקות)

---

### PR-003: [תחום 5] IBKR Account Info & Connection
**Owner**: Lead Developer
**Due**: Nov 12 (שבת)
**עדיפות**: 🔴 P0 - חוסם Paper Trading

**תיאור**:
השלמת IBKR integration - חיבור + account info API.

**Deliverables**:
- [ ] עדכון `algo_trade/core/execution/IBKR_handler.py`:
  - `get_account_summary()` - NAV, cash, buying power
  - `get_positions()` - current positions
  - `get_orders()` - open orders
  - Error handling & reconnection logic (exponential backoff)
  - Health check method: `is_healthy()`
- [ ] תצורה `config/ibkr_config.yaml`:
  ```yaml
  ibkr:
    host: 127.0.0.1
    port: 7497  # Paper Trading (4002 for live)
    client_id: 100
    timeout: 30
    reconnect_attempts: 5
    reconnect_backoff: [1, 2, 4, 8, 16]
  ```
- [ ] Unit tests ב-`tests/test_ibkr_handler.py`:
  - Mock של IB connection
  - Test account info retrieval
  - Test reconnection logic
  - Test error scenarios
- [ ] Documentation: `docs/IBKR_SETUP.md`
  - הוראות פתיחת חשבון Paper
  - התקנת TWS/Gateway
  - בדיקת חיבור ראשונה

**קריטריונים להצלחה**:
- חיבור מוצלח לחשבון Paper Trading
- קבלת account summary ללא שגיאות
- Tests עם mock client עוברים

**קבצים מושפעים**:
- (update) `algo_trade/core/execution/IBKR_handler.py` - מ-34 שורות ל-~150 שורות
- (new) `config/ibkr_config.yaml`
- (new) `tests/test_ibkr_handler.py`
- (new) `docs/IBKR_SETUP.md`

**תחומים**: #5 (אינטגרציה Broker)

---

### PR-004: [תחום 1] Schema Definitions & Contracts
**Owner**: Engineer
**Due**: Nov 13 (א')
**עדיפות**: 🟡 P1 - נדרש לאינטגרציה

**תיאור**:
השלמת message schemas ל-Kafka topics.

**Deliverables**:
- [ ] `contracts/market_events.schema.json` - פירוט מלא:
  ```json
  {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MarketEvent",
    "type": "object",
    "required": ["event_type", "timestamp", "conid"],
    "properties": {
      "event_type": {"enum": ["bar", "tick", "quote", "ofi"]},
      "timestamp": {"type": "string", "format": "date-time"},
      "conid": {"type": "integer"},
      "symbol": {"type": "string"},
      "open": {"type": "number"},
      "high": {"type": "number"},
      "low": {"type": "number"},
      "close": {"type": "number"},
      "volume": {"type": "integer"}
    }
  }
  ```
- [ ] `contracts/orders.schema.json` - פירוט מלא:
  - OrderIntent: symbol, side, quantity, order_type, limit_price
  - ExecutionReport: order_id, fill_price, fill_qty, status
  - Cancel, Amend events
- [ ] `contracts/validators.py` - פונקציות validation:
  - `validate_market_event(event: dict) -> bool`
  - `validate_order_intent(intent: dict) -> bool`
- [ ] Unit tests: `tests/test_validators.py`
  - Valid schemas pass
  - Invalid schemas raise ValidationError

**קריטריונים להצלחה**:
- כל schemas תקפים (JSON Schema validator)
- Validators עובדים עם דוגמאות

**קבצים מושפעים**:
- (update) `contracts/market_events.schema.json` - מ-6 שורות ל-~50 שורות
- (update) `contracts/orders.schema.json` - מ-6 שורות ל-~80 שורות
- (update) `contracts/validators.py` - הוספת validation logic
- (new) `tests/test_validators.py`

**תחומים**: #1 (ארכיטקטורה)

---

## שבוע 2: Risk & Monitoring (Nov 14–21)

### PR-005: [תחום 4+7] Prometheus Metrics & Basic Monitoring
**Owner**: SRE
**Due**: Nov 18 (ה')
**עדיפות**: 🟡 P1 - נדרש לobservability

**תיאור**:
יצירת metrics exporter ו-Grafana dashboard בסיסי.

**Deliverables**:
- [ ] עדכון `data_plane/monitoring/metrics_exporter.py`:
  - Prometheus client setup
  - 20+ metrics:
    - `data_ingestion_latency_ms` (histogram)
    - `kafka_messages_produced_total` (counter)
    - `ibkr_connection_status` (gauge)
    - `signal_generation_time_ms` (histogram)
    - `portfolio_value_usd` (gauge)
    - `daily_pnl_usd` (gauge)
    - `kill_switch_triggered_total` (counter)
  - `/metrics` endpoint (Flask או FastAPI)
- [ ] `monitoring/prometheus.yml` - scrape config:
  ```yaml
  scrape_configs:
    - job_name: 'data_plane'
      static_configs:
        - targets: ['data_plane:8000']
    - job_name: 'strategy_plane'
      static_configs:
        - targets: ['strategy_plane:8001']
  ```
- [ ] `monitoring/grafana_dashboard.json`:
  - Panel 1: Data Ingestion Latency (p50, p95, p99)
  - Panel 2: Portfolio Value (time series)
  - Panel 3: Daily PnL (bar chart)
  - Panel 4: Kill-Switch Status (stat)
- [ ] Documentation: `docs/MONITORING.md`
  - הוראות גישה ל-Grafana
  - רשימת metrics ומשמעותם

**קריטריונים להצלחה**:
- `/metrics` endpoint מחזיר 20+ metrics
- Grafana dashboard מציג נתונים (אפילו mock)

**קבצים מושפעים**:
- (update) `data_plane/monitoring/metrics_exporter.py` - מ-4 שורות ל-~100 שורות
- (new) `monitoring/prometheus.yml`
- (new) `monitoring/grafana_dashboard.json`
- (new) `docs/MONITORING.md`
- (update) `docker-compose.yml` - volume mounts למדדים

**תחומים**: #7 (ניתור ו-SRE), #4 (ניהול סיכונים - metrics)

---

### PR-006: [תחום 9+12] Secrets Management & Documentation
**Owner**: Security + Tech Lead
**Due**: Nov 21 (ה')
**עדיפות**: 🟡 P1 - נדרש לפני live deployment

**תיאור**:
יצירת מנגנון secrets management ותיעוד תהליכים.

**Deliverables**:
- [ ] `.env.example` מעודכן עם כל secrets:
  - `IBKR_USERNAME=<your_username>`
  - `IBKR_PASSWORD=<masked>`
  - `KAFKA_SASL_USERNAME=<if_using_auth>`
  - הוראות: "NEVER commit .env to git!"
- [ ] `.gitignore` עדכון:
  - `.env`
  - `*.pem`
  - `*_secret.*`
- [ ] `docs/SECRETS_MANAGEMENT.md`:
  - Local development: `.env` file
  - Production: AWS Secrets Manager (planned)
  - Rotation policy: every 90 days
- [ ] `docs/RUNBOOK.md` - נהלים תפעוליים:
  - Startup procedure (6 steps)
  - Shutdown procedure (4 steps)
  - Troubleshooting (5 common issues)
  - Emergency contacts
- [ ] `docs/INCIDENT_PLAYBOOK.md`:
  - Scenario 1: Kill-Switch Triggered
  - Scenario 2: IBKR Disconnect
  - Scenario 3: Data Feed Stale
  - Scenario 4: High Latency (p99 > 500ms)
  - Scenario 5: Memory Leak / OOM
- [ ] `PRE_LIVE_CHECKLIST.md`:
  - 25 items עם checkboxes
  - Sign-off section (Quant, Risk, DevOps, Trader)

**קריטריונים להצלחה**:
- `.env` לא נמצא בgit history
- כל מסמכי documentation reviewed ו-approved

**קבצים מושפעים**:
- (update) `.env.example`
- (update) `.gitignore`
- (new) `docs/SECRETS_MANAGEMENT.md`
- (new) `docs/RUNBOOK.md`
- (new) `docs/INCIDENT_PLAYBOOK.md`
- (new) `PRE_LIVE_CHECKLIST.md`

**תחומים**: #9 (אבטחה), #12 (תיעוד)

---

## סיכום שבועי

### שבוע 1 (Nov 7–14): תשתיות
- PR-001: Docker & Kafka ✅
- PR-002: Unit Tests (Phase 1) ✅
- PR-003: IBKR Account Info ✅
- PR-004: Schemas & Contracts ✅

**תוצאה צפויה**:
- סביבת פיתוח containerized
- 30%+ test coverage
- חיבור פעיל ל-IBKR Paper
- Message schemas מוגדרים

### שבוע 2 (Nov 14–21): Monitoring & Security
- PR-005: Prometheus & Grafana ✅
- PR-006: Secrets & Docs ✅

**תוצאה צפויה**:
- ניטור בסיסי פעיל
- Secrets מאובטחים
- תיעוד תהליכים שלם

---

## מדדי הצלחה (Definition of Done)

### תחום 6: CI/CD
- ✅ All tests pass
- ✅ Coverage ≥ 30% (baseline)
- ✅ CI pipeline runs ב-every push

### תחום 8: Deployment
- ✅ `docker-compose up` succeeds
- ✅ Kafka accessible
- ✅ Prometheus scraping

### תחום 5: IBKR Integration
- ✅ Connection to Paper Trading stable
- ✅ Account info retrieval works
- ✅ Reconnection logic tested

### תחום 7: Monitoring
- ✅ 20+ metrics exported
- ✅ Grafana dashboard displays data

### תחום 9: Security
- ✅ `.env` not in git
- ✅ Secrets rotation policy documented

### תחום 12: Documentation
- ✅ 4 new docs created
- ✅ Pre-Live Checklist ready

---

## סיכונים ומיטיגציה

| סיכון | Impact | Probability | Mitigation |
|-------|--------|-------------|------------|
| IBKR Paper חשבון לוקח >3 ימים לאישור | 🔴 High | Medium | התחל הגשה **מיד** (Nov 7) |
| Docker networking issues | 🟡 Medium | Low | Use `host` network mode as fallback |
| Kafka learning curve | 🟡 Medium | Medium | Start עם simple producer/consumer examples |
| Schema validation breaks existing code | 🟡 Medium | Low | Make validation **opt-in** בשלב ראשון |
| Insufficient testing time | 🔴 High | Medium | Prioritize P0 tests, defer nice-to-haves |

---

## תלויות חיצוניות

1. **IBKR Paper Account** → Lead Dev צריך להגיש בקשה ביום ה-Nov 7
2. **GitHub Actions Quota** → Verify free tier sufficient (2,000 minutes/month)
3. **AWS Account** → לא נדרש ב-2 שבועות אלה (development מקומי)

---

## Beyond 2 Weeks: שבוע 3-4 (Nov 21–Dec 5)

### שלב 2: Integration & Stability
- PR-007: Order Placement Full Flow (תחום 5)
- PR-008: End-to-End Test (Data → Strategy → Order) (תחום 6)
- PR-009: Additional Unit Tests (coverage 30% → 60%) (תחום 6)
- PR-010: Alerting Rules (Telegram/Email) (תחום 7)

### שלב 3: Pre-Production (Dec 5–19)
- PR-011: Risk Policy Document (תחום 4)
- PR-012: Load Testing & Performance (תחום 10)
- PR-013: Backtest Results Documentation (תחום 11)
- PR-014: AWS Deployment Prep (תחום 8)

**Target**: Paper Trading ב-production-like environment עד Dec 25.

---

## טבלת PRs - סיכום

| PR | תחומים | Owner | Due | Status | KPIs מושפעים |
|----|---------|-------|-----|--------|---------------|
| PR-001 | 1, 8 | DevOps | Nov 10 | 🟡 Ready | Docker/Deployment: 0% → 40% |
| PR-002 | 6 | QA | Nov 11 | 🟡 Ready | Test Coverage: 0% → 30% |
| PR-003 | 5 | Lead Dev | Nov 12 | 🟡 Ready | IBKR Integration: 20% → 50% |
| PR-004 | 1 | Engineer | Nov 13 | 🟡 Ready | ארכיטקטורה: schemas complete |
| PR-005 | 7, 4 | SRE | Nov 18 | 🟡 Planned | Monitoring: 10% → 40% |
| PR-006 | 9, 12 | Security+Tech | Nov 21 | 🟡 Planned | Security: 0% → 50%, Docs: 40% → 70% |

---

## קריטריונים ל-Go/No-Go (End of Week 2)

### GO (Continue to Paper Trading)
- ✅ כל 6 PRs merged
- ✅ CI pipeline ירוק
- ✅ IBKR Paper connection stable
- ✅ Test coverage ≥ 30%
- ✅ Monitoring dashboard פעיל

### NO-GO (Continue Infrastructure Work)
- ❌ <4 PRs merged
- ❌ IBKR connection לא יציב
- ❌ Kafka או Docker issues
- ❌ Test coverage < 20%

---

## נקודות פעולה - התחלה מיידית (Nov 7)

### דחוף - היום!
1. [ ] **Lead Dev**: הגש בקשה לחשבון IBKR Paper (3-5 business days)
2. [ ] **DevOps**: התקן Docker Desktop + docker-compose
3. [ ] **QA**: התקן pytest, pytest-cov
4. [ ] **All**: pull latest code, checkout branch `claude/trading-algorithm-readiness-framework-011CUtaoFacr1sXTx6qpQipA`

### מחר (Nov 8)
1. [ ] **DevOps**: התחל PR-001 (Dockerfile skeleton)
2. [ ] **QA**: התחל PR-002 (conftest.py + first test)
3. [ ] **Lead Dev**: קרא IBKR API docs (account info methods)

### מחרתיים (Nov 9-10)
1. [ ] **All**: Daily standup (15 min) - דווח progress ו-blockers
2. [ ] **DevOps**: PR-001 review מוכן
3. [ ] **QA**: PR-002 draft עם 10+ tests

---

## משאבים נוספים

- [IBKR Paper Trading Docs](https://www.interactivebrokers.com/en/index.php?f=1286)
- [Kafka Quickstart](https://kafka.apache.org/quickstart)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Pytest Documentation](https://docs.pytest.org/)

---

**נוצר על ידי**: Claude Code (AI Assistant)
**תאריך**: 2025-11-07
**Branch**: claude/trading-algorithm-readiness-framework-011CUtaoFacr1sXTx6qpQipA
**לאישור**: Project Lead / CTO

**Next Review**: Nov 14 (end of Week 1) - progress check על PRs 1-4
