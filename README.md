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

### 🐳 הרצה עם Docker (מומלץ!)

הדרך המומלצת להריץ את המערכת היא באמצעות Docker:

```bash
# העתק קובץ הגדרות
cp .env.example .env

# ערוך את .env עם ההגדרות שלך (IBKR_HOST, IBKR_PORT, וכו')

# הרץ את כל השירותים
./docker/docker-helper.sh start

# בדוק סטטוס
./docker/docker-helper.sh status
```

**גישה לממשקי Web:**
- Grafana (דשבורד): http://localhost:3000 (admin/admin)
- Prometheus (מטריקות): http://localhost:9090
- Kafka UI (ניטור הודעות): http://localhost:8090

**למידע מפורט**, ראה [docker/README.md](./docker/README.md)

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
| 🟡 IBKR Integration | 70% | Handler בסיסי, דרושה השלמה |
| 🟡 3-Plane Architecture | 60% | שלד קיים, דרושה אינטגרציה |
| 🔴 Testing Suite | 0% | קבצים קיימים אך ריקים |
| ✅ Docker & Deployment | 100% | Dockerfile, docker-compose, Kafka, Prometheus, Grafana |
| 🟡 Monitoring | 40% | Metrics Exporter קיים |

**🎯 עד Production:** 12-16 שבועות (ראה מסמך מנהלים)

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

**עודכן לאחרונה:** 28 אוקטובר 2025