# Algo-trade
## מערכת מסחר אלגוריתמית מתקדמת

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Pre--Production-yellow.svg)]()
[![License](https://img.shields.io/badge/License-Private-red.svg)]()

**מערכת מסחר אלגוריתמית כמותית** המשלבת למידת מכונה, ניהול סיכונים מבוסס-נתונים, ואופטימיזציה מתמטית למסחר רב-נכסים (מניות, נגזרים, מט"ח, קריפטו).

---

## 📚 תיעוד מרכזי

### למנהלים ומקבלי החלטות:
- **[📊 מסמך מנהלים (Executive Summary)](./EXECUTIVE_SUMMARY_HE.md)** - סיכום מקיף של המערכת, מצב נוכחי, ותוכנית עבודה לדיפלוי
- **[📈 תרשימי זרימה (Decision Flow Diagrams)](./DECISION_FLOW_DIAGRAMS.md)** - תרשימים מפורטים של לוגיקת קבלת ההחלטות
- **[🎯 מצב נוכחי (Status Now)](./STATUS_NOW.md)** - ⭐ **חדש!** הערכת מצב End-to-End בן 15 תחומים, פערים קריטיים, ו-KPIs
- **[🚀 Roadmap שבועיים (2-Week Roadmap)](./2-WEEK_ROADMAP.md)** - ⭐ **חדש!** 6 PRs ממופה לסגירת פערים קריטיים

### למפתחים:
- קוד מתועד היטב בעברית (docstrings)
- ארכיטקטורה מודולרית - 3 Planes (Data, Strategy, Order)

---

## 🎯 תכונות עיקריות

### 🧠 מנוע קבלת החלטות
- **6 אסטרטגיות אותות** (OFI, ERN, VRP, POS, TSX, SIF)
- **מיזוג אותות חכם** עם שקלול דינמי (IC Weighting)
- **אורתוגונליזציה** להסרת קורלציות פנימיות
- **זיהוי רגימות שוק** (Calm/Normal/Storm) עם HMM
- **אופטימיזציה קמורה** (Quadratic Programming)

### 🛡️ ניהול סיכונים
- **3 Kill-Switches**: PnL, PSR, Max Drawdown
- **Blind-Spot Agent** לזיהוי סטיות בקובריאנס
- **Covariance Estimation** עם EWMA, Ledoit-Wolf, PSD Correction
- **Regime-Adaptive** התאמת פרמטרים בזמן אמת

### 📊 למידה וולידציה
- **Purged K-Fold Cross-Validation** למניעת data leakage
- **CSCV** לזיהוי overfitting
- **PSR & DSR** להערכת מובהקות סטטיסטית
- **Bayesian Optimization** לכיוונון היפר-פרמטרים
- **LinUCB Contextual Bandit** לבחירה אדפטיבית של אותות

### 🏗️ ארכיטקטורה
- **Data Plane**: קליטת נתונים, נורמליזציה, QA
- **Strategy Plane**: בניית אסטרטגיה, אופטימיזציה
- **Order Plane**: ביצוע הזמנות, risk checks, למידה
- **Kafka Message Bus** לתקשורת בין מישורים
- **Message Contracts & Schema Validation** - ⭐ **חדש!** אימות מלא של הודעות Kafka
- **Prometheus + Grafana** למעקב ביצועים

### ✅ חוזי הודעות ואימות סכמה (Message Contracts)
- **5 סוגי הודעות** מאומתות: BarEvent, TickEvent, OFIEvent, OrderIntent, ExecutionReport
- **Pydantic v2 Validators** לאימות runtime עם type safety
- **JSON Schema Validation** לאימות מבני
- **Dead Letter Queue (DLQ)** להודעות לא תקינות
- **Validation Metrics** למעקב ואזעקות
- **18 Unit Tests** מכסים את כל התרחישים
- **ביצועים**: <1.5ms overhead לכל הודעה

---

## 🚀 התחלה מהירה

### דרישות מקדימות
```bash
Python 3.9+
Interactive Brokers TWS/Gateway (לחיבור אמיתי)
Docker (אופציונלי, עבור Kafka)
```

### התקנה והגדרה

#### אוטומטי (מומלץ)
```bash
# Clone the repository
git clone <repository-url>
cd Algo-trade

# הרץ סקריפט הגדרה אוטומטי
./scripts/setup_env.sh

# עקוב אחר ההוראות על המסך
```

#### ידני
```bash
# Clone the repository
git clone <repository-url>
cd Algo-trade

# Install dependencies
pip install -r requirements.txt

# הגדר סביבת פיתוח
cp .env.example .env
nano .env  # ערוך עם הגדרות שלך

# צור תיקיות נדרשות
mkdir -p logs data backups reports incidents
```

### הרצה (Backtest)
```bash
# הרץ backtest מלא עם נתונים סינתטיים
python algo_trade/core/main.py
```

### בדיקות (Testing)
```bash
# הרץ את כל בדיקות האימות
pytest tests/test_schema_validation.py -v

# הרץ בדיקות ספציפיות
pytest tests/test_schema_validation.py::TestBarEvent -v

# הרץ עם coverage report
pytest tests/test_schema_validation.py --cov=contracts --cov-report=html
```

### דוגמת שימוש ב-Validation Framework
```python
from contracts.schema_validator import validate_bar_event

# אמת BarEvent לפני שליחה ל-Kafka
bar_data = {
    'event_type': 'bar_event',
    'symbol': 'SPY',
    'timestamp': '2025-11-16T16:00:00Z',
    'open': 450.25,
    'high': 452.80,
    'low': 449.50,
    'close': 451.75,
    'volume': 85234567,
}

result = validate_bar_event(bar_data)
if result.is_valid:
    # שלח ל-Kafka
    await bus.publish('market_events', result.validated_data.dict())
else:
    logger.error(f"Validation failed: {result.errors}")
```

### הגדרות
- **`targets.yaml`**: קובץ תצורה מרכזי עם 60+ פרמטרים
- **`data/assets.csv`**: הגדרת נכסים למסחר
- **`contracts/*.schema.json`**: JSON schemas לאימות הודעות Kafka

---

## 📊 מבנה הפרויקט

```
Algo-trade/
├── algo_trade/core/          # מנוע מסחר מרכזי
│   ├── signals/              # ייצור אותות (6 אסטרטגיות)
│   ├── optimization/         # אופטימיזציית פורטפוליו (QP, HRP, BL)
│   ├── risk/                 # ניהול סיכונים (DD, Covariance, Regime)
│   ├── validation/           # ולידציה (CSCV, PSR, DSR)
│   ├── execution/            # ביצוע והתחברות ל-IBKR
│   └── main.py               # אורקסטרציה ראשית (~3,100 שורות)
├── contracts/                # ⭐ חוזי הודעות ואימות סכמה
│   ├── validators.py         # Pydantic v2 validators (394 שורות)
│   ├── schema_validator.py   # מנוע אימות מרכזי (481 שורות)
│   ├── *.schema.json         # JSON schemas (BarEvent, OrderIntent, ExecutionReport)
│   └── README.md             # תיעוד מלא (453 שורות)
├── data_plane/               # קליטת נתונים, נורמליזציה, QA
│   └── validation/           # ⭐ אימות הודעות Data Plane
├── order_plane/              # ביצוע הזמנות, risk checks, למידה
│   └── validation/           # ⭐ אימות הודעות Order Plane
├── apps/strategy_loop/       # לולאת אסטרטגיה
│   └── validation/           # ⭐ אימות הודעות Strategy Plane
├── data/                     # נתוני נכסים
├── tests/                    # בדיקות
│   └── test_schema_validation.py  # ⭐ 18 unit tests (628 שורות)
└── shared/                   # כלי עזר משותפים

סה"כ: 60 קבצי Python, ~7,200 שורות קוד (כולל validation framework)
```

---

## 📈 סטטוס פיתוח

| רכיב | סטטוס | הערות |
|------|--------|-------|
| ✅ Core Trading Engine | 100% | מושלם |
| ✅ Signal Generation | 100% | 6 אסטרטגיות פעילות |
| ✅ Portfolio Optimization | 100% | QP, HRP, Black-Litterman |
| ✅ Risk Management | 100% | Kill-Switches, Regime Detection |
| ✅ Validation Framework | 100% | CSCV, PSR, DSR, Bayesian Opt |
| ✅ **Message Contracts & Schema Validation** | **100%** | **⭐ חדש! 5 סוגי הודעות, DLQ, 18 tests** |
| 🟡 IBKR Integration | 70% | Handler בסיסי, דרושה השלמה |
| 🟡 3-Plane Architecture | 75% | שלד + Validation, דרושה אינטגרציה |
| 🟡 Testing Suite | 25% | Schema validation tests הושלמו |
| 🔴 Docker & Deployment | 0% | טרם הושלם |
| 🟡 Monitoring | 40% | Metrics Exporter קיים |

**🎯 עד Production:** 10-14 שבועות (ראה מסמך מנהלים)

### עדכונים אחרונים (נובמבר 2025):
- ✅ **Message Contracts & Schema Validation** - מערכת אימות מקיפה עם Pydantic v2 ו-JSON Schema
- ✅ **18 Unit Tests** מכסים כל תרחישי האימות
- ✅ **DLQ Integration** להודעות לא תקינות
- ✅ **Validation Metrics** למעקב ואזעקות

---

## 🛠️ טכנולוגיות

- **Python 3.9+**: שפת תכנות ראשית
- **NumPy, Pandas**: מבני נתונים ומניפולציות
- **CVXPY**: אופטימיזציה קמורה
- **Scikit-learn**: למידת מכונה
- **Pydantic v2**: ⭐ אימות נתונים ו-type safety
- **JSON Schema**: ⭐ אימות מבנה הודעות
- **Interactive Brokers (ib_insync)**: חיבור לברוקר
- **Kafka**: Message bus
- **Prometheus, Grafana**: Monitoring
- **Docker**: Containerization (בתכנון)
- **pytest**: Testing framework

---

## 📞 תמיכה ויצירת קשר

לשאלות, בעיות, או תרומות:
- פתח Issue ב-GitHub
- צור Pull Request
- צור קשר עם צוות הפיתוח

---

## 📝 רישיון

פרויקט פרטי. כל הזכויות שמורות.

---

## 🙏 תודות

מערכת זו פותחה בעזרת:
- ספרות אקדמית בפיננסים כמותיים
- Best practices בפיתוח מערכות Trading
- Claude Code (AI Assistant) לסיוע בפיתוח

---

**עודכן לאחרונה:** 16 נובמבר 2025

---

## 📚 תיעוד נוסף

### ⚙️ תפעול ואבטחה
- **[🔐 Secrets Management](./SECRETS_MANAGEMENT.md)** - ⭐ ניהול Secrets מלא: .env, Vault, AWS Secrets Manager
- **[📖 Runbook](./RUNBOOK.md)** - נהלי הפעלה והפסקה, ניטור, ותחזוקה שוטפת
- **[🚨 Incident Playbook](./INCIDENT_PLAYBOOK.md)** - ⭐ תגובה לאירועים, playbooks לתרחישים שונים
- **[👥 RACI Matrix](./RACI.md)** - ⭐ הגדרת אחריות ותפקידים בארגון
- **[✅ Pre-Live Checklist](./PRE_LIVE_CHECKLIST.md)** - שערי בקרה להפעלה בפועל
- **[🔄 Rollback Procedure](./ROLLBACK_PROCEDURE.md)** - נהלי החזרה לגרסה קודמת

### 🚀 Deployment & Infrastructure (**חדש!**)
- **[📦 Deployment Guide](./DEPLOYMENT.md)** - ⭐ מדריך deployment מקיף: Docker, Kubernetes, AWS ECS/EC2
- **[🔒 Security Audit Report](./SECURITY_AUDIT_REPORT.md)** - ⭐ דוח בדיקת אבטחה מלא (Bandit scan passed)

### 🔌 אינטגרציה עם IBKR
- **[📊 IBKR Integration Flow](./IBKR_INTEGRATION_FLOW.md)** - 8 שלבי אינטגרציה מלאים
- **[🗺️ IBKR Interface Map](./IBKR_INTERFACE_MAP.md)** - מפת API ופונקציונליות מפורטת
- **[✅ IBKR Artifact Validation](./IBKR_ARTIFACT_VALIDATION_REPORT.md)** - דוח אימות artifacts
- **[🎯 IBKR Pre-Live Execution](./IBKR_PRELIVE_EXECUTION_SUMMARY.md)** - סיכום ביצוע בדיקות

### 🧪 בדיקות ואיכות
- **[📋 QA Plan](./QA_PLAN.md)** - תוכנית בדיקות מקיפה
- **[📊 QA Execution Summary](./QA_EXECUTION_SUMMARY.md)** - סיכום ביצוע בדיקות
- **[📉 QA Gap Analysis](./QA_GAP_ANALYSIS.md)** - ניתוח פערים

### 💬 חוזי הודעות
- **[Message Contracts & Schema Validation](./contracts/README.md)** - מדריך מקיף לשימוש במערכת האימות