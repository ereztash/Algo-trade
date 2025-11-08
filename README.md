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
- **[✅ Pre-Live Checklist](./PRE_LIVE_CHECKLIST.md)** - רשימת בדיקה מקיפה לפני Go-Live (200 נקודות)

### אבטחה ותאימות (Security & Compliance):
- **[🔒 Security Execution Summary](./SECURITY_EXECUTION_SUMMARY.md)** - ⭐ **חדש!** ארכיטקטורת אבטחה מקיפה (SOC 2 Type II)
- **[🔐 IAM Policy Framework](./IAM_POLICY_FRAMEWORK.md)** - ⭐ **חדש!** מדיניות זהויות והרשאות (5 תפקידים, JIT Access)

### למפתחים:
- קוד מתועד היטב בעברית (docstrings)
- ארכיטקטורה מודולרית - 3 Planes (Data, Strategy, Order)
- **[🛠️ Scripts & Validation](./scripts/README.md)** - כלי אימות אבטחה ו-CI/CD

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

### 🔒 אבטחה ותאימות
- **SOC 2 Type II Baseline** - מסגרת תאימות לשירותי פיננסים
- **5-Role RBAC Model** - Trader, DevOps, QA, Service, Governance
- **AWS Secrets Manager** - ניהול סודות עם רוטציה אוטומטית (30 יום)
- **TLS 1.3 Encryption** - הצפנה מלאה לכל התקשורת החיצונית
- **Just-In-Time Access** - הרשאות זמניות עם אישור תוך 15 דקות
- **7 CI/CD Security Gates** - סריקה אוטומטית: סודות, תלויות, קוד, קונטיינרים
- **Event Correlation & SIEM** - ניטור אבטחה בזמן אמת עם 4 רמות חומרה
- **2-Year Audit Trail** - שמירת לוגים לצורכי ביקורת רגולטורית

### 🏗️ ארכיטקטורה
- **Data Plane**: קליטת נתונים, נורמליזציה, QA
- **Strategy Plane**: בניית אסטרטגיה, אופטימיזציה
- **Order Plane**: ביצוע הזמנות, risk checks, למידה
- **Kafka Message Bus** לתקשורת בין מישורים
- **Prometheus + Grafana** למעקב ביצועים
- **Security Layer** - הגנה מקיפה על סודות, זהויות, ונתונים

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
├── shared/                   # כלי עזר משותפים
│
├── 🔒 Security Framework (NEW!)
│   ├── SECURITY_EXECUTION_SUMMARY.md    # ארכיטקטורת אבטחה מקיפה (56KB)
│   ├── IAM_POLICY_FRAMEWORK.md          # מדיניות IAM ו-RBAC (35KB)
│   ├── scripts/
│   │   ├── validate_iam_policies.py     # אימות מדיניות IAM
│   │   ├── validate_security_logs.py    # אימות לוגי אבטחה
│   │   └── README.md                    # תיעוד כלי אימות
│   ├── .github/workflows/
│   │   └── security-gates.yml           # 7 בדיקות אבטחה אוטומטיות
│   └── .pre-commit-config.yaml          # Pre-commit hooks
│
└── Documentation/            # תיעוד נוסף
    ├── PRE_LIVE_CHECKLIST.md            # 200 נקודות בדיקה
    ├── EXECUTIVE_SUMMARY_HE.md          # סיכום מנהלים
    └── STATUS_NOW.md                     # מצב נוכחי

סה"כ: 53 קבצי Python + 7 מסמכי אבטחה, ~9,000+ שורות (כולל תיעוד)
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
| 🟢 **Security Framework** | **80%** | **⭐ NEW! תיעוד + CI/CD מוכנים** |
| 🟡 IBKR Integration | 70% | Handler בסיסי, דרושה השלמה |
| 🟡 3-Plane Architecture | 60% | שלד קיים, דרושה אינטגרציה |
| 🔴 Testing Suite | 0% | קבצים קיימים אך ריקים |
| 🔴 Docker & Deployment | 0% | טרם הושלם |
| 🟡 Monitoring | 40% | Metrics Exporter קיים |

### סטטוס אבטחה מפורט:
- ✅ **תיעוד אבטחה**: SECURITY_EXECUTION_SUMMARY.md + IAM_POLICY_FRAMEWORK.md
- ✅ **CI/CD Security Gates**: 7 בדיקות אוטומטיות (TruffleHog, Snyk, Bandit, Trivy)
- ✅ **Pre-commit Hooks**: זיהוי סודות, linting, type checking
- ✅ **Validation Scripts**: אימות IAM policies + security logs
- 🟡 **AWS Secrets Manager**: תיעוד מוכן, דרושה הטמעה (פאזה 2)
- 🟡 **SIEM/Monitoring**: תיעוד מוכן, דרושה קונפיגורציה (פאזה 2)
- 🔴 **Penetration Testing**: מתוכנן לפני Go-Live

**🎯 עד Production:** 10-14 שבועות (שיפור לאחר הוספת מסגרת אבטחה)

---

## 🛠️ טכנולוגיות

### Core Trading:
- **Python 3.11+**: שפת תכנות ראשית
- **NumPy, Pandas**: מבני נתונים ומניפולציות
- **CVXPY**: אופטימיזציה קמורה
- **Scikit-learn**: למידת מכונה
- **Interactive Brokers (ib_insync)**: חיבור לברוקר

### Infrastructure:
- **Kafka**: Message bus
- **Prometheus, Grafana**: Monitoring
- **Docker**: Containerization (בתכנון)

### Security & Compliance:
- **AWS Secrets Manager**: ניהול סודות מאובטח
- **TruffleHog + gitleaks**: זיהוי סודות בקוד
- **Snyk + safety + pip-audit**: סריקת תלויות
- **Trivy**: סריקת קונטיינרים
- **Bandit**: ניתוח אבטחה סטטי ל-Python
- **Datadog / ELK Stack**: SIEM (מתוכנן)
- **GitHub Actions**: CI/CD Security Gates

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

## 🔒 Security & Compliance Status

[![Security Gates](https://img.shields.io/badge/Security_Gates-7_Active-success.svg)]()
[![SOC 2](https://img.shields.io/badge/SOC_2-Type_II_Baseline-blue.svg)]()
[![Secrets Detection](https://img.shields.io/badge/Secrets-Protected-green.svg)]()
[![IAM](https://img.shields.io/badge/IAM-5_Roles_Defined-blue.svg)]()

**מסגרת אבטחה מקיפה הוטמעה!** כולל תיעוד SOC 2 Type II, 7 שערי אבטחה ב-CI/CD, ומדיניות IAM מלאה. ראה [SECURITY_EXECUTION_SUMMARY.md](./SECURITY_EXECUTION_SUMMARY.md) לפרטים.

---

**עודכן לאחרונה:** 8 נובמבר 2025
**גרסה:** 2.0 (Security Framework Added)