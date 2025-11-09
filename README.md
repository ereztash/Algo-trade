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
- **[🎯 מצב נוכחי (Status Now)](./STATUS_NOW.md)** - הערכת מצב End-to-End בן 15 תחומים, פערים קריטיים, ו-KPIs
- **[🚀 Roadmap שבועיים (2-Week Roadmap)](./2-WEEK_ROADMAP.md)** - 6 PRs ממופה לסגירת פערים קריטיים

### תיעוד IBKR ו-Production Readiness:
- **[🔌 IBKR Integration Flow](./IBKR_INTEGRATION_FLOW.md)** - מיפוי מלא של תהליך האינטגרציה עם Interactive Brokers
- **[🗺️ IBKR Interface Map](./IBKR_INTERFACE_MAP.md)** - מפת ממשקים מפורטת
- **[📋 IBKR Pre-Live Execution Summary](./IBKR_PRELIVE_EXECUTION_SUMMARY.md)** - ⭐ **חדש!** דוח מצב הכנות Pre-Live (37.5% הושלם)
- **[✅ Pre-Live Checklist](./PRE_LIVE_CHECKLIST.md)** - רשימת ביקורת לפני עליה ל-Production
- **[🚦 Go-Live Decision Gate](./GO_LIVE_DECISION_GATE.md)** - קריטריוני החלטה לעליה Live

### QA ו-Testing:
- **[🧪 QA Plan](./QA_PLAN.md)** - ⭐ **חדש!** תוכנית אבטחת איכות מקיפה (80%+ coverage יעד)
- **[📊 QA Gap Analysis](./QA_GAP_ANALYSIS.md)** - ניתוח פערי QA והמלצות
- **[📈 QA Execution Summary](./QA_EXECUTION_SUMMARY.md)** - סיכום ביצוע בדיקות
- **[📝 Test Execution Report](./TEST_EXECUTION_REPORT.md)** - דוח ביצוע בדיקות (15/16 passed - 93.75%)

### תיעוד תפעולי:
- **[📖 Runbook](./RUNBOOK.md)** - ⭐ **חדש!** נהלים תפעוליים להרצה, ניטור וטיפול בתקלות
- **[🔄 Rollback Procedure](./ROLLBACK_PROCEDURE.md)** - נוהל rollback במקרה של בעיות

### למפתחים:
- קוד מתועד היטב בעברית (docstrings)
- ארכיטקטורה מודולרית - 3 Planes (Data, Strategy, Order)
- בדיקות אוטומטיות עם pytest (בפיתוח מתמשך)

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
- **Prometheus + Grafana** למעקב ביצועים

---

## 🚀 התחלה מהירה

### דרישות מקדימות
```bash
Python 3.9+
Interactive Brokers TWS/Gateway (לחיבור אמיתי)
```

### התקנה
```bash
# Clone the repository
git clone <repository-url>
cd Algo-trade

# Install dependencies
pip install -r requirements.txt

# טען תצורה (יווצר אוטומטית אם לא קיים)
python algo_trade/core/main.py
```

### הרצה (Backtest)
```bash
# הרץ backtest מלא עם נתונים סינתטיים
python algo_trade/core/main.py
```

### הגדרות
- **`targets.yaml`**: קובץ תצורה מרכזי עם 60+ פרמטרים
- **`data/assets.csv`**: הגדרת נכסים למסחר

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
├── data_plane/               # קליטת נתונים, נורמליזציה, QA
├── order_plane/              # ביצוע הזמנות, risk checks, למידה
├── apps/strategy_loop/       # לולאת אסטרטגיה
├── data/                     # נתוני נכסים
├── tests/                    # בדיקות (בתהליך פיתוח)
└── shared/                   # כלי עזר משותפים

סה"כ: 53 קבצי Python, ~4,470 שורות קוד
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
| 🟡 IBKR Integration | 85% | ⬆️ ארכיטקטורה מלאה + מיפוי ממשקים (PR #4) |
| 🟡 3-Plane Architecture | 70% | ⬆️ תיעוד מלא, בתהליך אימפלמנטציה |
| 🟡 Testing Suite | 25% | ⬆️ תוכנית QA מקיפה + 16 בדיקות ראשוניות (93.75% passed) |
| 🟡 Documentation | 95% | ⬆️ Runbook, Pre-Live Checklist, QA Plan |
| 🔴 Docker & Deployment | 10% | ⬆️ תכנית פריסה מתועדת, טרם מיושם |
| 🟡 Monitoring | 50% | ⬆️ מטריקות מוגדרות, Grafana dashboards מתוכננים |

**🎯 עד Production:** 10-14 שבועות (ראה [IBKR Pre-Live Execution Summary](./IBKR_PRELIVE_EXECUTION_SUMMARY.md))

**התקדמות אחרונה (נובמבר 2025):**
- ✅ תשתית IBKR Pre-Live validation הושלמה (3/8 stages)
- ✅ תוכנית QA מקיפה פותחה
- ✅ 16 בדיקות ראשוניות עברו בהצלחה
- ✅ תיעוד תפעולי (Runbook) נוצר

---

## 🛠️ טכנולוגיות

- **Python 3.9+**: שפת תכנות ראשית
- **NumPy, Pandas**: מבני נתונים ומניפולציות
- **CVXPY**: אופטימיזציה קמורה
- **Scikit-learn**: למידת מכונה
- **Interactive Brokers (ib_insync)**: חיבור לברוקר
- **Kafka**: Message bus
- **Prometheus, Grafana**: Monitoring
- **Docker**: Containerization (בתכנון)

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

## 🎯 מצב נוכחי ושלבים הבאים

### מצב Pre-Production
המערכת נמצאת כעת ב-**Pre-Production** עם:
- ✅ Core Engine מושלם (100%)
- 🟡 Infrastructure ו-Integration (60-85%)
- 🟡 Testing & QA (25%)
- 🔴 Deployment (10%)

### שלבים הבאים (Priority)
1. **השלמת Testing Suite** (Target: 80%+ coverage)
   - Unit tests לכל מודול
   - Integration tests ל-IBKR
   - E2E tests לזרימה מלאה

2. **IBKR Paper Trading**
   - השלמת חיבור ל-TWS/Gateway
   - ולידציה עם חשבון Paper
   - 30 ימי Paper trading לפני Live

3. **Docker & Deployment**
   - Containerization מלאה
   - CI/CD pipeline
   - Staging environment

4. **Monitoring & Alerting**
   - Grafana dashboards
   - Prometheus metrics
   - Alert rules

למידע מפורט, ראה [IBKR Pre-Live Execution Summary](./IBKR_PRELIVE_EXECUTION_SUMMARY.md) ו-[2-Week Roadmap](./2-WEEK_ROADMAP.md).

---

## 🔄 Pull Requests אחרונים

| PR # | תיאור | מצב | תאריך |
|------|-------|-----|-------|
| #4 | IBKR Pre-Live Validation Framework | ✅ Merged | 2025-11-08 |
| #3 | QA Readiness Testing Framework | ✅ Merged | 2025-11-07 |
| #2 | Comprehensive .gitignore | ✅ Merged | 2025-11-07 |

**Branch נוכחי:** `claude/update-readme-011CUx7f3h9TKBRA67EEoYAt`

---

**עודכן לאחרונה:** 9 נובמבר 2025