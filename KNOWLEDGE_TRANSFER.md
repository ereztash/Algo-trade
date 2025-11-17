# Knowledge Transfer Document
## Algo-Trade Quantitative Trading System

**מסמך העברת ידע מקיף**

**גרסה:** 1.0
**תאריך:** 17 נובמבר 2025
**מטרה:** העברת ידע מלאה לחברי צוות חדשים והמשכיות ידע

---

## 📑 תוכן עניינים

1. [סקירה כללית](#1-סקירה-כללית)
2. [ארכיטקטורת המערכת](#2-ארכיטקטורת-המערכת)
3. [IBKR Pre-Live Validation Framework](#3-ibkr-pre-live-validation-framework)
4. [Message Contracts & Schema Validation](#4-message-contracts--schema-validation)
5. [Testing Infrastructure](#5-testing-infrastructure)
6. [ארגון קוד ומודולים מרכזיים](#6-ארגון-קוד-ומודולים-מרכזיים)
7. [Risk Controls & Kill Switches](#7-risk-controls--kill-switches)
8. [Deployment & Operations](#8-deployment--operations)
9. [Troubleshooting Guide](#9-troubleshooting-guide)
10. [Common Workflows](#10-common-workflows)
11. [Design Decisions & Rationale](#11-design-decisions--rationale)
12. [Critical Dependencies](#12-critical-dependencies)
13. [Future Work & Roadmap](#13-future-work--roadmap)

---

## 1. סקירה כללית

### 1.1 מהי המערכת?

**Algo-Trade** היא מערכת מסחר אלגוריתמית כמותית מתקדמת המשלבת:
- **למידת מכונה** לניבוי תנועות שוק
- **אופטימיזציה מתמטית** לבניית פורטפוליו
- **ניהול סיכונים מבוסס-נתונים** עם Kill-Switches
- **אינטגרציה עם IBKR** (Interactive Brokers) לביצוע הזמנות

### 1.2 מטרות עיקריות

1. **יצירת Alpha**: ניצול אותות כמותיים (OFI, ERN, VRP, וכו') להשגת תשואות עודפות
2. **ניהול סיכונים**: הגבלת חשיפה, זיהוי רגימות שוק, Kill-Switches אוטומטיים
3. **ביצוע אמין**: חיבור ל-IBKR עם latency נמוך, fill rate גבוה
4. **Scale**: תמיכה במסחר רב-נכסים (מניות, אופציות, עתידים, מט"ח, קריפטו)

### 1.3 סטטוס נוכחי (נובמבר 2025)

| רכיב | סטטוס | הערות |
|------|--------|-------|
| Core Trading Engine | ✅ 100% | מושלם, ~3,100 שורות |
| Signal Generation | ✅ 100% | 6 אסטרטגיות פעילות |
| Portfolio Optimization | ✅ 100% | QP, HRP, Black-Litterman |
| Risk Management | ✅ 100% | 3 Kill-Switches, Regime Detection |
| **Message Contracts** | ✅ 100% | 5 סוגי הודעות + validation |
| **IBKR Pre-Live Gates** | ✅ 100% | 8 שלבים + artifacts |
| IBKR Integration | 🟡 70% | Handler בסיסי, דרושה השלמה |
| 3-Plane Architecture | 🟡 75% | Scaffolding + validation |
| Testing Suite | 🟡 40% | Schema + Stage tests הושלמו |
| Monitoring | 🟡 40% | Metrics Exporter קיים |
| Docker & Deployment | 🔴 0% | טרם הושלם |

**זמן משוער עד Production:** 10-14 שבועות

---

## 2. ארכיטקטורת המערכת

### 2.1 ארכיטקטורת 3 Planes

המערכת בנויה בארכיטקטורת **3 מישורים (Planes)** המתקשרים דרך Kafka Message Bus:

```
┌─────────────────────────────────────────────────────────────────┐
│                        KAFKA MESSAGE BUS                        │
│   (Topics: market_events, order_intents, execution_reports)    │
└─────────────────────────────────────────────────────────────────┘
         ▲                      ▲                        ▲
         │                      │                        │
┌────────┴────────┐   ┌────────┴────────┐   ┌──────────┴────────┐
│   DATA PLANE    │   │ STRATEGY PLANE  │   │   ORDER PLANE     │
│                 │   │                 │   │                   │
│ • IBKR Client   │   │ • Signals (6)   │   │ • Risk Checks     │
│ • Normalization │   │ • Optimization  │   │ • IBKR Execution  │
│ • QA Gates      │   │ • Regime        │   │ • Pacing          │
│ • Storage       │   │ • Ensemble      │   │ • Learning        │
└─────────────────┘   └─────────────────┘   └───────────────────┘
```

#### **Data Plane** (קליטת נתונים)
- **מטרה**: קליטת נתוני שוק מ-IBKR, נורמליזציה, בדיקות QA
- **קבצים מרכזיים**:
  - `data_plane/connectors/ibkr/client.py` - חיבור ל-IBKR
  - `data_plane/normalization/normalize.py` - נורמליזציה
  - `data_plane/qa/freshness_monitor.py` - בדיקת רעננות
  - `data_plane/qa/completeness_gate.py` - בדיקת שלמות
- **הודעות פלט**: `BarEvent`, `TickEvent`, `OFIEvent` → Kafka topic: `market_events`

#### **Strategy Plane** (בניית אסטרטגיה)
- **מטרה**: יצירת אותות, אופטימיזציה, בניית פורטפוליו
- **קבצים מרכזיים**:
  - `algo_trade/core/signals/*.py` - 6 אסטרטגיות אותות
  - `algo_trade/core/optimization/qp_solver.py` - אופטימיזציה
  - `algo_trade/core/risk/regime_detection.py` - זיהוי רגימות
  - `algo_trade/core/ensemble.py` - מיזוג אותות
- **הודעות פלט**: `OrderIntent` → Kafka topic: `order_intents`

#### **Order Plane** (ביצוע הזמנות)
- **מטרה**: ביצוע הזמנות דרך IBKR, Risk checks, למידה
- **קבצים מרכזיים**:
  - `order_plane/broker/ibkr_exec_client.py` - ביצוע IBKR
  - `order_plane/intents/risk_checks.py` - בדיקות סיכון
  - `order_plane/broker/throttling.py` - Pacing limiter
  - `order_plane/learning/lambda_online.py` - למידה מקוונת
- **הודעות פלט**: `ExecutionReport` → Kafka topic: `execution_reports`

### 2.2 Message Flow

```
1. IBKR → Data Plane: Market data (quotes, bars, trades)
2. Data Plane → Kafka: BarEvent, TickEvent, OFIEvent
3. Strategy Plane ← Kafka: Reads market events
4. Strategy Plane: Generates signals → Optimization → Portfolio
5. Strategy Plane → Kafka: OrderIntent
6. Order Plane ← Kafka: Reads order intents
7. Order Plane: Risk checks → Execution → IBKR
8. Order Plane → Kafka: ExecutionReport
9. Strategy Plane ← Kafka: Reads execution reports (feedback loop)
```

### 2.3 Key Design Principles

1. **Low Coupling**: כל Plane עצמאי, מתקשר רק דרך Kafka
2. **High Cohesion**: כל Plane אחראי על תחום ברור
3. **Event-Driven**: כל תקשורת דרך events (הודעות Kafka)
4. **Schema Validation**: כל הודעה מאומתת לפני שליחה/קבלה
5. **Observability**: Metrics ב-Prometheus, Logs מובנים

---

## 3. IBKR Pre-Live Validation Framework

### 3.1 סקירה

**מסגרת אימות 8-שלבית** לוולידציה מלאה של אינטגרציית IBKR לפני דיפלוי ל-Production.

**מטרה**: למנוע כשלים בייצור, להבטיח ביצועים, לאשר go-live רק לאחר אישור כל השערים.

### 3.2 שלבי הוולידציה (Stages 1-8)

#### **Stage 1: Artifact Validation** ✅
- **תפקיד**: אימות שכל התיעוד והקבצים הדרושים קיימים
- **תנאי מעבר (Gate 1)**: `coverage ≥ 80% AND governance_signed AND fixtures_valid`
- **פלט**: `IBKR_ARTIFACT_VALIDATION_REPORT.md`

#### **Stage 2: Hierarchical Breakdown** ✅
- **תפקיד**: פירוק תהליך האינטגרציה ל-8 שלבים עצמאיים
- **תנאי מעבר (Gate 2)**: `all_stages_defined AND input_output_clear`
- **פלט**: `IBKR_INTEGRATION_FLOW.md`

#### **Stage 3: Interface Mapping** ✅
- **תפקיד**: מיפוי ממשקי IBKR API → מערכת פנימית
- **תנאי מעבר (Gate 3)**: `all_operations_mapped AND error_codes_documented`
- **פלט**: `IBKR_INTERFACE_MAP.md`
- **פעולות**: `placeOrder`, `cancelOrder`, `getAccountSummary`, `getPositions`, `subscribe_market_data`

#### **Stage 4: Implementation Prep** ⏳ (Pending)
- **תפקיד**: מימוש הקוד (handlers, clients, error handling, reconnection)
- **תנאי מעבר (Gate 4)**: `implementation_complete AND unit_tests_pass`
- **פלט**: קוד ב-`IBKR_handler.py`, `ibkr_exec_client.py` + Unit tests

#### **Stage 5: Test Infrastructure** ⏳ (Pending)
- **תפקיד**: יצירת סקריפטים לבדיקת Stages 6-8
- **תנאי מעבר (Gate 5)**: `all_stage_tests_exist AND tests_runnable`
- **פלט**: `stage6_account_probe.py`, `stage7_paper_trading.py`, `stage8_go_live_decision.py`

#### **Stage 6: Account Config Probe** (READ-ONLY)
- **תפקיד**: בדיקת חיבור ל-Paper account, קבלת metadata
- **תנאי מעבר (Gate 6)**: `connection_successful AND buying_power > 0`
- **פלט**: `ACCOUNT_CONFIG.json`
- **הרצה**: `pytest tests/stage6_account_probe.py -m stage6`
- **⚠️ חשוב**: READ-ONLY בלבד, ללא ביצוע הזמנות!

#### **Stage 7: Paper Trading Validation**
- **תפקיד**: סשן מסחר בפועל ב-Paper account (6 שעות, 50-200 עסקאות)
- **תנאי מעבר (Gate 7)**:
  - `latency_delta < 50%` (מול mock baseline)
  - `pacing_violations == 0`
  - `fill_rate > 98%`
  - `sharpe_paper ≥ 0.5 * sharpe_backtest`
- **פלט**: `PAPER_TRADING_LOG.json`, `PAPER_TRADING_METRICS.csv`
- **הרצה**: `pytest tests/stage7_paper_trading.py -m stage7`

#### **Stage 8: Go-Live Decision**
- **תפקיד**: אימות כל השערים (1-7) + החלטה סופית
- **תנאי מעבר (Gate 8)**:
  - `all_gates_1_to_7_pass == True`
  - `rollback_plan_verified == True`
  - `kill_switch_verified == True`
  - `governance_signed == True` (Risk Officer, CTO, Lead Trader)
- **פלט**: `GO_LIVE_DECISION_GATE.md` (עודכן), `PRELIVE_VERIFICATION_LOG.json`
- **הרצה**: `pytest tests/stage8_go_live_decision.py -m stage8`

### 3.3 Artifacts (קבצים שנוצרים)

| קובץ | תיאור | שלב |
|------|-------|-----|
| `IBKR_ARTIFACT_VALIDATION_REPORT.md` | דו"ח אימות artifacts | 1 |
| `IBKR_INTEGRATION_FLOW.md` | פירוט 8 השלבים | 2 |
| `IBKR_INTERFACE_MAP.md` | מיפוי API operations | 3 |
| `ACCOUNT_CONFIG.json` | קונפיגורציית Paper account | 6 |
| `PAPER_TRADING_LOG.json` | לוג עסקאות trade-by-trade | 7 |
| `PAPER_TRADING_METRICS.csv` | מטריקות ביצועים | 7 |
| `GO_LIVE_DECISION_GATE.md` | החלטת go-live | 8 |
| `ROLLBACK_PROCEDURE.md` | תהליך rollback חירום | 8 |
| `PRELIVE_VERIFICATION_LOG.json` | לוג אימות מלא (JSON Schema) | 8 |

### 3.4 תרשים זרימת Stages

```
Stage 1 (Artifacts) ──────┐
                          ▼
Stage 2 (Breakdown) ──────┤
                          ▼
Stage 3 (Interface) ──────┤
                          ▼
Stage 4 (Implementation) ─┤
                          ▼
Stage 5 (Tests) ──────────┤
                          ▼
Stage 6 (Account Probe) ──┤ ← Paper Trading Prerequisites
                          ▼
Stage 7 (Paper Trading) ──┤ ← Live Testing
                          ▼
Stage 8 (Go-Live) ────────┘ ← Final Gate
         ▼
   ✅ PRODUCTION READY
```

### 3.5 סטטוס נוכחי

- ✅ **Stages 1-3**: הושלמו (artifacts, architecture, interface mapping)
- ✅ **Stage 5**: תשתית בדיקות הושלמה (stage6-8 tests)
- ⏳ **Stage 4**: Implementation Prep - דרוש השלמה (2-3 ימים)
- ⏳ **Stage 6-8**: מוכן לביצוע לאחר השלמת Stage 4

---

## 4. Message Contracts & Schema Validation

### 4.1 סקירה

**מסגרת אימות הודעות Kafka** המבטיחה תקינות נתונים בין ה-Planes.

**טכנולוגיות**:
- **Pydantic v2**: Runtime validation + type safety
- **JSON Schema**: Structural validation
- **Dead Letter Queue (DLQ)**: תור להודעות לא תקינות

### 4.2 סוגי הודעות (5)

#### **1. BarEvent** (נתוני Bar)
```python
{
    "event_type": "bar_event",
    "symbol": "AAPL",
    "timestamp": "2025-11-17T09:30:00Z",
    "open": 450.25,
    "high": 452.80,
    "low": 449.50,
    "close": 451.75,
    "volume": 85234567,
    "bar_size": "1min"  # Optional
}
```
- **Schema**: `contracts/bar_event.schema.json`
- **Validator**: `contracts/validators.py::BarEvent`
- **Producer**: Data Plane
- **Consumer**: Strategy Plane

#### **2. TickEvent** (נתוני Tick)
```python
{
    "event_type": "tick_event",
    "symbol": "MSFT",
    "timestamp": "2025-11-17T09:30:05.123Z",
    "price": 378.25,
    "size": 100,
    "tick_type": "TRADE"  # TRADE | BID | ASK | LAST
}
```
- **Schema**: `contracts/tick_event.schema.json`
- **Validator**: `contracts/validators.py::TickEvent`

#### **3. OFIEvent** (Order Flow Imbalance)
```python
{
    "event_type": "ofi_event",
    "symbol": "TSLA",
    "timestamp": "2025-11-17T09:30:10Z",
    "ofi_value": 0.123,
    "volume_imbalance": 15000,
    "bid_volume": 50000,
    "ask_volume": 35000
}
```
- **Schema**: `contracts/ofi_event.schema.json`
- **Validator**: `contracts/validators.py::OFIEvent`

#### **4. OrderIntent** (כוונת הזמנה)
```python
{
    "event_type": "order_intent",
    "intent_id": "550e8400-e29b-41d4-a716-446655440000",
    "symbol": "GOOGL",
    "direction": "BUY",  # BUY | SELL
    "quantity": 100,
    "order_type": "LIMIT",  # MARKET | LIMIT | STOP | STOP_LIMIT | ADAPTIVE
    "limit_price": 2850.50,  # Optional (required for LIMIT)
    "timestamp": "2025-11-17T09:30:15Z"
}
```
- **Schema**: `contracts/order_intent.schema.json`
- **Validator**: `contracts/validators.py::OrderIntent`
- **Producer**: Strategy Plane
- **Consumer**: Order Plane

#### **5. ExecutionReport** (דו"ח ביצוע)
```python
{
    "event_type": "execution_report",
    "intent_id": "550e8400-e29b-41d4-a716-446655440000",
    "order_id": "1001",
    "symbol": "AMZN",
    "status": "FILLED",  # SUBMITTED | ACKNOWLEDGED | PARTIAL_FILL | FILLED | CANCELED | REJECTED
    "filled_quantity": 100,
    "avg_fill_price": 3250.75,
    "timestamp": "2025-11-17T09:30:18.456Z",
    "reject_reason": null  # Optional (if REJECTED)
}
```
- **Schema**: `contracts/execution_report.schema.json`
- **Validator**: `contracts/validators.py::ExecutionReport`
- **Producer**: Order Plane
- **Consumer**: Strategy Plane (feedback loop)

### 4.3 שימוש ב-Validation Framework

#### **אימות לפני שליחה (Producer)**
```python
from contracts.schema_validator import validate_order_intent

# יצירת intent
intent_data = {
    "event_type": "order_intent",
    "intent_id": str(uuid4()),
    "symbol": "AAPL",
    "direction": "BUY",
    "quantity": 100,
    "order_type": "MARKET",
    "timestamp": datetime.now(timezone.utc).isoformat(),
}

# אימות
result = validate_order_intent(intent_data)

if result.is_valid:
    # שליחה ל-Kafka
    await bus.publish('order_intents', result.validated_data.dict())
else:
    # שליחה ל-DLQ + logging
    logger.error(f"Validation failed: {result.errors}")
    await bus.publish('dlq_order_intents', intent_data)
```

#### **אימות לאחר קבלה (Consumer)**
```python
from contracts.schema_validator import validate_order_intent

# קבלה מ-Kafka
message = await bus.consume('order_intents')

# אימות
result = validate_order_intent(message)

if result.is_valid:
    # עיבוד ההודעה
    process_order(result.validated_data)
else:
    # שליחה ל-DLQ
    await bus.publish('dlq_order_intents', message)
```

### 4.4 DLQ (Dead Letter Queue)

**מטרה**: תור נפרד להודעות שנכשלו באימות

**Topics**:
- `dlq_market_events` - הודעות BarEvent/TickEvent/OFIEvent לא תקינות
- `dlq_order_intents` - הודעות OrderIntent לא תקינות
- `dlq_execution_reports` - הודעות ExecutionReport לא תקינות

**Workflow**:
1. הודעה נכשלת באימות
2. נשלחת ל-DLQ topic
3. Alert ל-monitoring
4. ניתן לבדוק ידנית, לתקן, ולשלוח מחדש

### 4.5 Testing

**18 Unit Tests** ב-`tests/test_schema_validation.py`:
- BarEvent: 3 tests (valid, invalid, edge cases)
- TickEvent: 3 tests
- OFIEvent: 3 tests
- OrderIntent: 5 tests (כולל limit_price validation)
- ExecutionReport: 4 tests (כולל reject_reason)

**הרצה**:
```bash
pytest tests/test_schema_validation.py -v
pytest tests/test_schema_validation.py::TestOrderIntent -v
pytest tests/test_schema_validation.py --cov=contracts
```

---

## 5. Testing Infrastructure

### 5.1 סוגי בדיקות

#### **Unit Tests**
- **מטרה**: בדיקת פונקציות בודדות
- **מיקום**: `tests/test_*.py`
- **דוגמאות**:
  - `test_signals.py` - בדיקות לאותות (OFI, ERN, VRP, וכו')
  - `test_qp_solver.py` - בדיקות לאופטימיזציה
  - `test_schema_validation.py` - בדיקות לאימות הודעות
- **הרצה**: `pytest tests/test_signals.py -v`

#### **Property-Based Tests** (Hypothesis)
- **מטרה**: בדיקת תכונות מתמטיות עם קלט רנדומלי
- **מיקום**: `tests/property/`
- **דוגמה**: `test_qp_properties.py` - בדיקת convexity, feasibility
- **הרצה**: `pytest tests/property/ -v`

#### **Metamorphic Tests**
- **מטרה**: בדיקת יציבות תחת טרנספורמציות
- **מיקום**: `tests/metamorphic/`
- **דוגמאות**:
  - `test_mt_scaling.py` - scaling של נתונים לא משנה אותות
  - `test_mt_noise.py` - רעש קטן לא משנה החלטות
- **הרצה**: `pytest tests/metamorphic/ -v`

#### **Stage Tests** (IBKR Pre-Live)
- **מטרה**: אימות Stages 6-8 של IBKR integration
- **מיקום**: `tests/stage*.py`
- **דוגמאות**:
  - `stage6_account_probe.py` - בדיקת חיבור ל-Paper account
  - `stage7_paper_trading.py` - סשן מסחר מלא
  - `stage8_go_live_decision.py` - החלטת go-live
- **הרצה**: `pytest tests/stage6_account_probe.py -m stage6`

#### **E2E Tests** (End-to-End)
- **מטרה**: בדיקת זרימה מלאה: Data → Strategy → Order
- **מיקום**: `tests/e2e/`
- **סטטוס**: בתכנון (טרם מומש)

### 5.2 Pytest Configuration

#### **Markers** (ב-`tests/conftest.py`)
```python
markers = [
    "unit",           # Unit tests
    "property",       # Property-based tests
    "metamorphic",    # Metamorphic tests
    "integration",    # Integration tests
    "e2e",            # End-to-end tests
    "stage6",         # Stage 6 - Account Probe
    "stage7",         # Stage 7 - Paper Trading
    "stage8",         # Stage 8 - Go-Live Decision
    "slow",           # Slow-running tests
]
```

#### **Fixtures** (ב-`tests/conftest.py`)
- `set_random_seeds()` - קביעת seeds לשחזוריות
- `sample_market_data()` - נתוני שוק לדוגמה
- `mock_ibkr_client()` - Mock של IBKR client
- `default_config()` - קונפיגורציה דיפולטיבית

### 5.3 הרצת בדיקות

```bash
# כל הבדיקות
pytest

# בדיקות ספציפיות
pytest tests/test_schema_validation.py -v

# בדיקות עם marker
pytest -m unit -v
pytest -m stage6 -v

# בדיקות עם coverage
pytest --cov=contracts --cov-report=html

# Hypothesis profile
HYPOTHESIS_PROFILE=ci pytest tests/property/ -v
```

---

## 6. ארגון קוד ומודולים מרכזיים

### 6.1 מבנה תיקיות

```
Algo-trade/
├── algo_trade/core/          # ⭐ Core Trading Engine
│   ├── main.py               # אורקסטרציה ראשית (~3,100 שורות)
│   ├── config.py             # קונפיגורציה (60+ פרמטרים)
│   ├── signals/              # ⭐ 6 אסטרטגיות אותות
│   ├── optimization/         # ⭐ אופטימיזציה (QP, HRP, BL)
│   ├── risk/                 # ⭐ ניהול סיכונים
│   ├── validation/           # ולידציה (CSCV, PSR, DSR)
│   └── execution/            # ביצוע (IBKR_handler.py)
├── contracts/                # ⭐ Message Contracts & Validation
│   ├── validators.py         # Pydantic v2 validators (394 שורות)
│   ├── schema_validator.py   # מנוע אימות (481 שורות)
│   └── *.schema.json         # JSON schemas (5 types)
├── data_plane/               # ⭐ Data Plane
│   ├── connectors/ibkr/      # חיבור ל-IBKR
│   ├── normalization/        # נורמליזציה
│   ├── qa/                   # QA gates (freshness, completeness)
│   ├── validation/           # אימות הודעות
│   └── app/orchestrator.py   # אורקסטרציה Data Plane
├── order_plane/              # ⭐ Order Plane
│   ├── broker/               # ביצוע IBKR + throttling
│   ├── intents/              # risk checks
│   ├── learning/             # למידה מקוונת (lambda)
│   ├── validation/           # אימות הודעות
│   └── app/orchestrator.py   # אורקסטרציה Order Plane
├── apps/strategy_loop/       # ⭐ Strategy Plane
│   ├── main.py               # לולאת אסטרטגיה
│   └── validation/           # אימות הודעות
├── tests/                    # ⭐ Testing Infrastructure
│   ├── test_*.py             # Unit tests
│   ├── property/             # Property-based tests
│   ├── metamorphic/          # Metamorphic tests
│   ├── stage*.py             # IBKR Pre-Live stage tests
│   └── conftest.py           # Pytest configuration
├── fixtures/                 # Fixtures (seeds.yaml, וכו')
├── shared/                   # כלי עזר משותפים (logging)
└── data/                     # נתוני נכסים (assets.csv)
```

### 6.2 מודולים מרכזיים

#### **algo_trade/core/main.py** (3,100 שורות)
**אחראי על**: אורקסטרציה מרכזית של Trading Engine

**פונקציות מרכזיות**:
- `run_backtest()` - הרצת backtest מלא
- `generate_signals()` - יצירת 6 אותות
- `optimize_portfolio()` - אופטימיזציית QP
- `apply_risk_controls()` - Kill-Switches, regime detection
- `execute_trades()` - ביצוע הזמנות (dry-run או live)

**תלויות**:
- `signals/` - כל 6 האותות
- `optimization/qp_solver.py` - QP optimization
- `risk/regime_detection.py` - HMM regime detection
- `execution/IBKR_handler.py` - IBKR handler

#### **algo_trade/core/signals/** (6 אסטרטגיות)

1. **OFI (Order Flow Imbalance)** - `base_signals.py`
   ```python
   ofi = (bid_volume - ask_volume) / (bid_volume + ask_volume)
   ```

2. **ERN (Earnings Signals)** - `base_signals.py`
   - SUE (Standardized Unexpected Earnings)
   - REV (Revenue Surprise)

3. **VRP (Volatility Risk Premium)** - `composite_signals.py`
   ```python
   vrp = implied_volatility - realized_volatility
   ```

4. **POS (Positioning Signals)** - `composite_signals.py`
   - Short interest, institutional ownership

5. **TSX (Technical Signals)** - `composite_signals.py`
   - Momentum, mean reversion, trend

6. **SIF (Sentiment/Info Flows)** - `composite_signals.py`
   - News sentiment, analyst upgrades/downgrades

**IC Weighting**: משקלול דינמי לפי Information Coefficient

#### **algo_trade/core/optimization/qp_solver.py**
**אחראי על**: אופטימיזציית פורטפוליו (Quadratic Programming)

**בעיית אופטימיזציה**:
```
min    (1/2) * w^T * Σ * w - λ * (μ^T * w)
s.t.   sum(|w_i|) ≤ gross_lim
       sum(w_i) ≤ net_lim
       |w_i| ≤ box_lim
       vol_target constraint
```

**פרמטרים**:
- `LAMBDA_INIT` - risk aversion (5e-4)
- `VOL_TARGET` - יעד תנודתיות (0.10)
- `BOX_LIM` - מגבלת פוזיציה בודדת (0.25)
- `GROSS_LIM` - מגבלת חשיפה ברוטו (2.0-2.5)
- `NET_LIM` - מגבלת חשיפה נטו (0.4-1.0)

**Solver**: CVXPY (קמור)

#### **algo_trade/core/risk/regime_detection.py**
**אחראי על**: זיהוי רגימות שוק (Calm/Normal/Storm)

**שיטה**: Hidden Markov Model (HMM) עם 3 מצבים

**States**:
- **Calm** (שקט): low volatility → gross_lim = 2.5, net_lim = 1.0
- **Normal** (רגיל): medium volatility → gross_lim = 2.0, net_lim = 0.8
- **Storm** (סערה): high volatility → gross_lim = 1.0, net_lim = 0.4

**Observations**: תנודתיות, drawdown, correlation breakdown

#### **contracts/schema_validator.py** (481 שורות)
**אחראי על**: אימות הודעות Kafka (Pydantic + JSON Schema)

**פונקציות מרכזיות**:
- `validate_bar_event(data)` - אימות BarEvent
- `validate_order_intent(data)` - אימות OrderIntent
- `validate_execution_report(data)` - אימות ExecutionReport
- `ValidationResult` - תוצאת אימות (is_valid, validated_data, errors)

#### **order_plane/broker/ibkr_exec_client.py**
**אחראי על**: ביצוע הזמנות דרך IBKR (async)

**פונקציות**:
- `connect()` - חיבור ל-IBKR Gateway
- `place_order(intent)` - ביצוע הזמנה
- `cancel_order(order_id)` - ביטול הזמנה
- `get_order_status(order_id)` - בדיקת סטטוס

**Pacing**: Token bucket (50 orders/sec)

**Error Handling**: retry logic, exponential backoff

---

## 7. Risk Controls & Kill Switches

### 7.1 סקירה

המערכת כוללת **3 Kill-Switches** אוטומטיים להגנה מפני הפסדים גדולים.

### 7.2 Kill-Switches

#### **1. PnL Kill-Switch** (הפסד מקסימלי)
- **תנאי**: `pnl < -0.05` (הפסד של 5%)
- **פעולה**: `HALT_AND_FLATTEN` - עצירה + סגירת כל הפוזיציות
- **מימוש**: `algo_trade/core/main.py::check_pnl_kill_switch()`

```python
if portfolio.pnl < KILL_PNL:
    logger.critical("PnL Kill-Switch triggered!")
    flatten_all_positions()
    halt_trading()
```

#### **2. Max Drawdown Kill-Switch**
- **תנאי**: `max_drawdown > 0.15` (15% drawdown)
- **פעולה**: `HALT_AND_FLATTEN`
- **מימוש**: `algo_trade/core/risk/drawdown.py`

```python
if current_drawdown > MAX_DD_KILL_SWITCH:
    logger.critical("Max Drawdown Kill-Switch triggered!")
    flatten_all_positions()
    halt_trading()
```

#### **3. PSR Kill-Switch** (Probabilistic Sharpe Ratio)
- **תנאי**: `psr < 0.20` (ביצועים גרועים מדי)
- **פעולה**: `HALT_AND_INVESTIGATE` - עצירה + חקירה
- **מימוש**: `algo_trade/core/validation/cross_validation.py`

```python
psr = calculate_psr(returns, sharpe_ratio, n_periods)
if psr < PSR_KILL_SWITCH:
    logger.warning("PSR Kill-Switch triggered!")
    halt_trading()
    investigate_degradation()
```

### 7.3 Rollback Procedure

**תרחיש**: Kill-Switch מופעל או בעיה בייצור

**צעדים** (ב-`ROLLBACK_PROCEDURE.md`):

1. **STOP**: ביטול כל ההזמנות הפתוחות
   ```bash
   python scripts/cancel_all_orders.py
   ```

2. **DISCONNECT**: ניתוק מ-IBKR
   ```bash
   python scripts/disconnect_ibkr.py
   ```

3. **FLATTEN**: סגירת כל הפוזיציות (market orders)
   ```bash
   python scripts/flatten_positions.py
   ```

4. **VERIFY**: בדיקת P&L חשבון
   ```bash
   python scripts/verify_account.py
   ```

5. **INVESTIGATE**: ניתוח שורש הבעיה
   - בדיקת לוגים ב-`logs/`
   - בדיקת metrics ב-Grafana
   - בדיקת DLQ ב-Kafka

6. **REPORT**: דיווח ל-Risk Officer

7. **FIX**: תיקון הבעיה לפני חזרה ל-live

**זמן יעד**: <2 דקות להשלמת FLATTEN

### 7.4 Monitoring & Alerts

**Metrics** (Prometheus):
- `pnl_current` - P&L נוכחי
- `drawdown_current` - Drawdown נוכחי
- `psr_current` - PSR נוכחי
- `kill_switch_triggered{type="pnl|dd|psr"}` - מונה triggers

**Alerts** (Grafana):
- PnL < -3%: WARNING
- PnL < -5%: CRITICAL + Kill-Switch
- Drawdown > 10%: WARNING
- Drawdown > 15%: CRITICAL + Kill-Switch
- PSR < 0.30: WARNING
- PSR < 0.20: CRITICAL + Kill-Switch

---

## 8. Deployment & Operations

### 8.1 סביבות

| סביבה | תיאור | IBKR Account | Kafka | Monitoring |
|-------|-------|--------------|-------|------------|
| **Development** | פיתוח מקומי | Mock/Paper | Local | Local Prometheus |
| **Staging** | בדיקות אינטגרציה | Paper (DU) | Staging Cluster | Staging Grafana |
| **Production** | ייצור | Live (U) | Production Cluster | Production Grafana |

### 8.2 Deployment Workflow (מתוכנן)

```bash
# 1. Build Docker images
docker build -t algo-trade-data-plane:latest data_plane/
docker build -t algo-trade-strategy-plane:latest apps/strategy_loop/
docker build -t algo-trade-order-plane:latest order_plane/

# 2. Push to registry
docker push <registry>/algo-trade-data-plane:latest
docker push <registry>/algo-trade-strategy-plane:latest
docker push <registry>/algo-trade-order-plane:latest

# 3. Deploy to Kubernetes
kubectl apply -f k8s/data-plane.yaml
kubectl apply -f k8s/strategy-plane.yaml
kubectl apply -f k8s/order-plane.yaml

# 4. Verify deployment
kubectl get pods -n algo-trade
kubectl logs -f <pod-name> -n algo-trade

# 5. Run health checks
curl http://<service>/health
```

### 8.3 Gradual Scale-Up (Post Go-Live)

**Week 1: Pilot (10% capital)**
- Capital: $10,000
- Max position: $2,500
- Review: Daily

**Week 2-3: Ramp (30% capital)**
- Capital: $30,000
- Max position: $7,500
- Review: Every 3 days

**Week 4+: Full Scale (100% capital)**
- Capital: $100,000
- Max position: $25,000
- Review: Weekly

### 8.4 Health Checks

**Endpoints** (מתוכנן):
- `/health` - בדיקת בריאות בסיסית
- `/ready` - בדיקת מוכנות (חיבור ל-Kafka, IBKR)
- `/metrics` - Prometheus metrics

**Liveness Probe**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10
```

**Readiness Probe**:
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

## 9. Troubleshooting Guide

### 9.1 בעיות נפוצות

#### **Validation Errors (הודעות לא תקינות)**

**תסמינים**:
- הודעות ב-DLQ
- Errors ב-logs: "Validation failed"

**פתרון**:
1. בדוק logs של Producer/Consumer
2. בדוק DLQ topic:
   ```bash
   kafka-console-consumer --topic dlq_order_intents --bootstrap-server localhost:9092
   ```
3. אמת schema:
   ```python
   result = validate_order_intent(message)
   print(result.errors)
   ```
4. תקן את ה-schema או הנתונים

#### **IBKR Connection Failed**

**תסמינים**:
- Error: "Not connected"
- Stage 6 test fails

**פתרון**:
1. בדוק ש-IBKR Gateway פועל:
   ```bash
   netstat -an | grep 4002
   ```
2. בדוק credentials ב-`.env`:
   ```bash
   echo $IBKR_PAPER_ACCOUNT_ID
   ```
3. בדוק Paper account port (4002, לא 4001):
   ```python
   assert IBKR_CONFIG["port"] == 4002
   ```
4. Restart IBKR Gateway

#### **Latency Issues (Gate 7 fails)**

**תסמינים**:
- `latency_delta > 50%`
- `p95_latency > 200ms`

**פתרון**:
1. בדוק network latency:
   ```bash
   ping <ibkr-gateway-host>
   ```
2. בדוק IBKR pacing violations:
   ```bash
   grep "pacing_violation" logs/order_plane.log
   ```
3. בדוק system load:
   ```bash
   top
   ```
4. אופטימיזציה:
   - הפחת logging
   - הוסף connection pooling
   - שדרג instance type

#### **Kill-Switch Triggered**

**תסמינים**:
- Alert: "Kill-Switch triggered"
- Trading halted

**פתרון**:
1. בדוק איזה Kill-Switch:
   ```bash
   grep "Kill-Switch triggered" logs/main.log | tail -1
   ```
2. בדוק metrics:
   - PnL: `curl http://localhost:9090/api/v1/query?query=pnl_current`
   - Drawdown: `curl http://localhost:9090/api/v1/query?query=drawdown_current`
   - PSR: `curl http://localhost:9090/api/v1/query?query=psr_current`
3. Follow rollback procedure (Section 7.3)
4. חקירה:
   - בדוק execution reports ב-Kafka
   - בדוק market conditions (volatility spike?)
   - בדוק signal degradation

### 9.2 Logging

**מיקום**: `logs/`
- `logs/main.log` - Main trading engine
- `logs/data_plane.log` - Data Plane
- `logs/order_plane.log` - Order Plane
- `logs/strategy_plane.log` - Strategy Plane

**רמות**:
- `DEBUG` - פרטים מלאים (dev only)
- `INFO` - מידע כללי
- `WARNING` - אזהרות
- `ERROR` - שגיאות
- `CRITICAL` - שגיאות קריטיות (Kill-Switches)

**חיפוש**:
```bash
# חיפוש errors
grep "ERROR" logs/main.log

# חיפוש Kill-Switches
grep "Kill-Switch" logs/*.log

# חיפוש validation failures
grep "Validation failed" logs/*.log
```

---

## 10. Common Workflows

### 10.1 הוספת אות חדש (Signal)

1. **צור קובץ חדש**: `algo_trade/core/signals/new_signal.py`
2. **הגדר פונקציה**:
   ```python
   def calculate_new_signal(data):
       """תיעוד..."""
       signal = ...  # לוגיקה
       return signal
   ```
3. **הוסף ל-`main.py`**:
   ```python
   from algo_trade.core.signals.new_signal import calculate_new_signal

   signals['NEW'] = calculate_new_signal(data)
   ```
4. **הוסף IC Weighting**:
   ```python
   ic_weights['NEW'] = calculate_ic(signals['NEW'], returns)
   ```
5. **כתוב בדיקה**: `tests/test_new_signal.py`
6. **הרץ backtest**: `python algo_trade/core/main.py`

### 10.2 שינוי פרמטר (Configuration)

1. **ערוך**: `algo_trade/core/config.py`
   ```python
   VOL_TARGET = 0.12  # שנה מ-0.10
   ```
2. **או**: ערוך `targets.yaml` (אם קיים)
3. **הרץ backtest**: `python algo_trade/core/main.py`
4. **השווה תוצאות**: בדוק Sharpe, Drawdown

### 10.3 הרצת Stage Tests

```bash
# Stage 6: Account Probe
pytest tests/stage6_account_probe.py -m stage6 -v

# Stage 7: Paper Trading (6 hours!)
pytest tests/stage7_paper_trading.py -m stage7 -v

# Stage 7: Latency Benchmark
pytest tests/stage7_latency_benchmark.py -m stage7 -v

# Stage 8: Go-Live Decision
pytest tests/stage8_go_live_decision.py -m stage8 -v

# כל Stages
pytest tests/stage*.py -v
```

### 10.4 בדיקת Validation Errors

```bash
# הרץ validation tests
pytest tests/test_schema_validation.py -v

# בדוק DLQ
kafka-console-consumer --topic dlq_order_intents \
  --bootstrap-server localhost:9092 \
  --from-beginning

# debug validation
python -c "
from contracts.schema_validator import validate_order_intent
result = validate_order_intent({...})
print(result.errors)
"
```

---

## 11. Design Decisions & Rationale

### 11.1 למה 3-Plane Architecture?

**החלטה**: הפרדה ל-Data, Strategy, Order Planes

**הנמקה**:
1. **Low Coupling**: כל Plane עצמאי, ניתן לפתח/לעדכן בנפרד
2. **Scalability**: ניתן לשדרג (scale) כל Plane בנפרד
3. **Fault Isolation**: כשל ב-Plane אחד לא משפיע על אחרים
4. **Team Structure**: צוותים שונים יכולים לעבוד על Planes שונים

**חלופה נדחתה**: Monolith - יותר פשוט, אך פחות גמיש

### 11.2 למה Kafka Message Bus?

**החלטה**: שימוש ב-Kafka לתקשורת בין Planes

**הנמקה**:
1. **Event-Driven**: ארכיטקטורת events מתאימה למסחר
2. **Durability**: הודעות נשמרות (replay אפשרי)
3. **Throughput**: Kafka מטפל ב-high throughput
4. **Standard**: תעשייתי, מתועד היטב

**חלופה נדחתה**: RabbitMQ - פחות throughput, יותר מורכב

### 11.3 למה Pydantic v2 + JSON Schema?

**החלטה**: שימוש ב-Pydantic v2 לvalidation + JSON Schema

**הנמקה**:
1. **Type Safety**: Pydantic מבטיח type safety בruntime
2. **Performance**: Pydantic v2 פי 5-10 מהיר מ-v1
3. **Interoperability**: JSON Schema מאפשר validation מחוץ ל-Python
4. **Documentation**: schemas משמשות גם כתיעוד

**חלופה נדחתה**: Marshmallow - ישן יותר, פחות מהיר

### 11.4 למה QP (Quadratic Programming)?

**החלטה**: שימוש ב-QP לאופטימיזציית פורטפוליו

**הנמקה**:
1. **Convex**: QP קמור → optimal solution מובטח
2. **Constraints**: תמיכה מלאה באילוצים (box, gross, net)
3. **Solver**: CVXPY מהיר ויציב
4. **Theory**: מבוסס תיאוריה (Markowitz)

**חלופה נדחתה**: HRP (Hierarchical Risk Parity) - לא מטפל באילוצים

### 11.5 למה 8-Stage Pre-Live Framework?

**החלטה**: מסגרת 8-שלבית לפני go-live

**הנמקה**:
1. **Risk Mitigation**: מונע כשלים בייצור
2. **Governance**: אישורים פורמליים (CTO, Risk Officer)
3. **Metrics**: בדיקת ביצועים מול baseline
4. **Rollback Plan**: הכנה לכשל

**חלופה נדחתה**: "Deploy and monitor" - מסוכן מדי

---

## 12. Critical Dependencies

### 12.1 External Services

| Service | מטרה | Criticality | Fallback |
|---------|------|-------------|----------|
| **IBKR Gateway** | ביצוע הזמנות | 🔴 CRITICAL | N/A (no fallback) |
| **Kafka** | Message bus | 🔴 CRITICAL | N/A (central dependency) |
| **Prometheus** | Metrics | 🟡 HIGH | Local logs |
| **Grafana** | Dashboards | 🟢 MEDIUM | Prometheus API |

### 12.2 Python Packages

**Core**:
- `numpy>=1.24.0` - מבני נתונים
- `pandas>=2.0.0` - dataframes
- `cvxpy>=1.3.0` - QP solver
- `pydantic>=2.0.0` - validation
- `ib_insync>=0.9.85` - IBKR client
- `kafka-python>=2.0.0` - Kafka client

**Testing**:
- `pytest>=7.4.0`
- `hypothesis>=6.82.0` - property-based testing
- `pytest-cov>=4.1.0` - coverage

**Optional**:
- `torch>=2.0.0` - deep learning (future)
- `prometheus-client>=0.17.0` - metrics

**התקנה**:
```bash
pip install -r requirements.txt
```

### 12.3 Data Dependencies

| נתונים | מקור | עדכון | חובה/אופציונלי |
|--------|------|--------|----------------|
| **Market Data (real-time)** | IBKR | Real-time | 🔴 חובה (live) |
| **Historical Data** | IBKR / CSV | Daily | 🟡 חובה (backtest) |
| **Assets List** | `data/assets.csv` | Manual | 🔴 חובה |
| **Seeds** | `fixtures/seeds.yaml` | Manual | 🟡 חובה (tests) |

### 12.4 Configuration Files

| קובץ | תיאור | חובה/אופציונלי |
|------|-------|----------------|
| `algo_trade/core/config.py` | קונפיגורציה ראשית | 🔴 חובה |
| `data/assets.csv` | רשימת נכסים | 🔴 חובה |
| `contracts/*.schema.json` | JSON schemas | 🔴 חובה |
| `fixtures/seeds.yaml` | Random seeds | 🟡 חובה (tests) |
| `.env` | Environment variables | 🟡 אופציונלי |
| `targets.yaml` | פרמטרים (future) | 🟢 אופציונלי |

---

## 13. Future Work & Roadmap

### 13.1 שבועיים הבאים (High Priority)

1. **Complete Stage 4** (Implementation Prep)
   - מימוש IBKR handlers
   - Unit tests
   - 2-3 ימים

2. **Run Stages 6-8** (Pre-Live Validation)
   - Account probe
   - Paper trading (6 hours)
   - Go-live decision
   - 2 ימים

3. **Docker & CI/CD**
   - Dockerfiles לכל Plane
   - GitHub Actions CI
   - 3-5 ימים

### 13.2 חודש הבא (Medium Priority)

4. **Monitoring Enhancement**
   - Prometheus metrics מלא
   - Grafana dashboards
   - Alerts configuration
   - 3-5 ימים

5. **E2E Tests**
   - בדיקות End-to-End מלאות
   - Data → Strategy → Order
   - 3-5 ימים

6. **Documentation**
   - API documentation (Swagger)
   - Runbooks
   - 2-3 ימים

### 13.3 Long-Term (3+ חודשים)

7. **Deep Learning Signals**
   - LSTM/Transformer אותות
   - 2-3 שבועות

8. **Multi-Asset Support**
   - אופציות, עתידים, מט"ח
   - 4-6 שבועות

9. **High-Frequency Features**
   - Latency optimization (<10ms)
   - FPGA (future)
   - 6-8 שבועות

10. **Knowledge Transfer Plan** ✅
    - מסמך זה!

---

## 14. נקודות קשר

### 14.1 לחברי צוות חדשים

**שלב 1: קריאה** (2-3 שעות)
1. קרא מסמך זה במלואו
2. קרא `README.md`
3. קרא `contracts/README.md`

**שלב 2: Setup** (1-2 שעות)
1. Clone repository
2. התקן dependencies: `pip install -r requirements.txt`
3. הרץ backtest: `python algo_trade/core/main.py`
4. הרץ tests: `pytest tests/test_schema_validation.py -v`

**שלב 3: תרגול** (1-2 ימים)
1. שנה פרמטר (למשל VOL_TARGET) והרץ backtest
2. הוסף unit test פשוט
3. צור signal חדש פשוט
4. הרץ Stage 6 test (account probe)

**שלב 4: העמקה** (1 שבוע)
1. למד את ה-3 Planes לעומק
2. צלול לקוד ב-`algo_trade/core/main.py`
3. נסה להוסיף feature קטן
4. פרזנטציה לצוות על מה שלמדת

### 14.2 שאלות נפוצות

**ש: איך אני מריץ backtest?**
```bash
python algo_trade/core/main.py
```

**ש: איך אני מוסיף signal חדש?**
ראה Section 10.1

**ש: איך אני בודק validation?**
```bash
pytest tests/test_schema_validation.py -v
```

**ש: מה זה DLQ?**
Dead Letter Queue - תור להודעות שנכשלו באימות (ראה Section 4.4)

**ש: איך אני מריץ Stage tests?**
```bash
pytest tests/stage6_account_probe.py -m stage6 -v
```

**ש: מה הזמן עד Production?**
10-14 שבועות (ראה Section 1.3)

---

## 15. סיכום

### 15.1 נקודות מפתח

1. **3-Plane Architecture**: Data, Strategy, Order - מופרדים דרך Kafka
2. **Message Contracts**: 5 סוגי הודעות מאומתים (Pydantic + JSON Schema)
3. **IBKR Pre-Live**: 8 שלבים לפני go-live, כולל Paper trading
4. **Risk Controls**: 3 Kill-Switches (PnL, Drawdown, PSR)
5. **Testing**: Unit, Property, Metamorphic, Stage tests

### 15.2 הצעד הבא

אם אתה חבר צוות חדש:
1. ✅ קרא מסמך זה
2. ⏭️ Setup environment
3. ⏭️ הרץ backtest ראשון
4. ⏭️ דבר עם Lead Developer

אם אתה מחפש feature ספציפי:
- **Signals** → Section 6.2
- **Validation** → Section 4
- **IBKR** → Section 3
- **Testing** → Section 5
- **Risk** → Section 7

---

**עודכן לאחרונה:** 17 נובמבר 2025
**גרסה:** 1.0
**נוצר על ידי:** Claude Code (AI Assistant)

**להצלחה! 🚀**
