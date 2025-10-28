# מסמך מנהלים - מערכת המסחר האלגוריתמית
## סיכום תמציתי לקובעי מדיניות

**תאריך:** 28 אוקטובר 2025
**גרסה:** 1.0
**סטטוס פרויקט:** Pre-Production (שלב פיתוח מתקדם)

---

## 📊 תקציר ניהולי (Executive Summary)

מערכת המסחר האלגוריתמית היא פלטפורמה כמותית מתקדמת לניהול פורטפוליו אוטומטי, המבוססת על טכניקות למידת מכונה, ניהול סיכונים מבוסס-נתונים, ואופטימיזציה מתמטית. המערכת מיועדת למסחר רב-נכסים (מניות, אג"ח, מט"ח, קריפטו, נגזרים) בשווקים גלובליים תוך שימוש בחיבור ישיר לברוקר Interactive Brokers (IBKR).

**יעדי המערכת:**
- השגת תשואות עודפות (alpha) יציבות תוך ניהול סיכון פעיל
- הפעלת מסחר אוטומטי 24/7 עם פיקוח אנושי מינימלי
- הסתגלות דינמית לתנאי שוק משתנים (רגימות)
- למידה מתמשכת מביצועי מסחר בפועל (online learning)

**היקף הפרויקט:**
- **53 קבצי Python** עם כ-**4,470 שורות קוד**
- **7 נכסים פעילים** במסחר (TSLA, SPY, ESM25, EURUSD, BTC, TLT ועוד)
- **6 אסטרטגיות אותות** (Signals) בו-זמניות
- **3 מישורים ארכיטקטוניים**: Data Plane, Strategy Plane, Order Plane

---

## 🎯 מצב נוכחי (Current State)

### ✅ מה שהושלם

#### 1. **מנוע קבלת החלטות (Core Trading Engine)**
המנוע המרכזי מושלם ב-100% וכולל:

- **ייצור אותות (Signal Generation)**: 6 אסטרטגיות טכניות מבוססות-נתונים
  - Order Flow Imbalance (OFI) - איזון פעילות קנייה/מכירה
  - Earnings Momentum (ERN) - מומנטום דוחות רווח
  - Volatility Risk Premium (VRP) - פרמיית סיכון תנודתיות
  - Position Sizing (POS) - התאמת גודל פוזיציה
  - Cross-Asset (TSX) - קורלציות בין-נכסיות
  - Systematic Inflow (SIF) - זרימות כסף שיטתיות

- **מיזוג אותות חכם**: שקלול דינמי של אותות לפי איכות היסטורית (IC Weighting)
- **אורתוגונליזציה**: הסרת קורלציות פנימיות בין אותות למניעת רדונדנטיות
- **זיהוי רגימות שוק**: 3 מצבי שוק (Calm/Normal/Storm) מבוססי HMM וסטטיסטיקות
- **אופטימיזציה קמורה (QP Solver)**: חישוב משקלות פורטפוליו אופטימליות עם אילוצים:
  - מגבלות חשיפה (Gross/Net Exposure)
  - מגבלות פוזיציה לנכס (Box Constraints: 25% max)
  - קנס על תנודתיות (Turnover Penalty)
  - יעד תנודתיות (Volatility Targeting: 10% annual)

#### 2. **ניהול סיכונים (Risk Management)**
מערכת סיכונים רב-שכבתית מושלמת:

- **ניתוח Drawdown**: מעקב אחר ירידות מצטברות בזמן אמת
- **Kill-Switches (מנגנוני חירום)**:
  - PnL Kill Switch: עצירה אוטומטית בירידה של 5%
  - PSR Kill Switch: עצירה כשיחס שארפ הסתברותי < 0.20
  - Max Drawdown Kill Switch: עצירה בירידה מקסימלית > 15%
- **Blind-Spot Agent**: זיהוי סטיות בקובריאנס (covariance drift) להפחתת חשיפה
- **Covariance Estimation**: שילוב EWMA, Ledoit-Wolf Shrinkage, ו-PSD Correction
- **Regime Detection**: HMM עם 3 מצבים להתאמת פרמטרים בזמן אמת

#### 3. **למידה וולידציה (Learning & Validation)**
מערכת למידה וולידציה שלמה:

- **Purged K-Fold Cross-Validation**: מניעת data leakage בבדיקת backtest
- **CSCV (Combinatorially Symmetric Cross-Validation)**: זיהוי overfitting סטטיסטי
- **Probabilistic Sharpe Ratio (PSR)**: הערכת מובהקות סטטיסטית של ביצועים
- **Deflated Sharpe Ratio (DSR)**: תיקון bias ממבחנים מרובים
- **Bayesian Optimization**: כיוונון היפר-פרמטרים (MOM_H, REV_H, TURNOVER_PEN, וכו')
- **LinUCB Contextual Bandit**: בחירה אדפטיבית של קבוצות אותות ("Gates")

#### 4. **ארכיטקטורה מודולרית (3-Plane Architecture)**
עיצוב מבוזר שלם בשלב ראשוני:

##### **Data Plane** (מישור נתונים)
- חיבור ל-IBKR (TWS/Gateway) לנתונים היסטוריים וזמן-אמת
- נורמליזציה של נתונים גולמיים לפורמט סטנדרטי
- QA Gates: בדיקות שלמות (Completeness), עדכניות (Freshness), סינכרון זמן (NTP)
- Kafka Message Bus לזרימת נתונים
- Kappa Engine לעיבוד זמן-אמת
- Prometheus Metrics Exporter למעקב ביצועים

##### **Strategy Plane** (מישור אסטרטגיה)
- בניית context וחישוב אותות מנתונים מצטברים
- אורתוגונליזציה ומיזוג אותות
- פתרון QP לחישוב target weights
- הרכבת Order Intents (כוונות מסחר)

##### **Order Plane** (מישור הזמנות)
- בדיקות סיכון pre-trade (Risk Checks)
- Throttling (POV/ADV caps) למניעת השפעת שוק
- ביצוע הזמנות דרך IBKR Execution API
- Online Learning של עלויות טרנזקציה (Lambda Update)
- צריכת דוחות ביצוע (Execution Reports) לאימות ולמידה

#### 5. **ניהול תצורה (Configuration)**
- קובץ `targets.yaml` לניהול פרמטרים מרכזי
- 60+ פרמטרים ניתנים לכיוונון
- ברירות מחדל מותאמות לפי מחקר כמותי

#### 6. **ניהול נכסים (Asset Management)**
- קובץ `assets.csv` עם מטא-דאטה מלאה:
  - ISIN, FIGI codes לזיהוי חד-משמעי
  - פרופילי עמלות (Standard, ETF, Futures, FX, Crypto)
  - Risk Weighting לכל נכס
  - Lot Sizes ומגבלות מסחר מינימליות

---

### ⚠️ מה שבתהליך / חסר (Gaps & Work In Progress)

#### 1. **אינטגרציה מלאה עם IBKR (70% מושלם)**
**סטטוס:** קבצי Handler ו-Client בסיסיים קיימים, אך לא מלאים

**חסר:**
- ✅ `IBKRHandler` קיים ל-connection/disconnection
- ❌ **הוספת Account Info API**: קריאת NAV, Cash, Positions נוכחיות
- ❌ **Order Placement Full Flow**: הגשת הזמנות Limit/Market/Adaptive
- ❌ **Execution Reports Parsing**: קריאה ועיבוד של דוחות מילוי
- ❌ **Error Handling & Reconnection**: טיפול בניתוקים ו-retries
- ❌ **Live vs Paper Trading Mode**: מתג להפרדה בין מסחר אמיתי לסימולציה

**זמן משוער:** 2-3 שבועות

#### 2. **בדיקות (Testing) (0% מושלם)**
**סטטוס:** קבצי test קיימים אך **ריקים** לחלוטין

**חסר:**
- ❌ Unit tests למודולי Core (Signals, QP, Risk, Validation)
- ❌ Integration tests ל-3 Planes
- ❌ End-to-End tests לתרחישי backtest מלאים
- ❌ Mock IBKR Client לבדיקות ללא חיבור אמיתי
- ❌ Performance tests (latency, throughput)

**זמן משוער:** 3-4 שבועות

#### 3. **Docker ו-Deployment (0% מושלם)**
**סטטוס:** אין קבצי containerization או deployment

**חסר:**
- ❌ `Dockerfile` למערכת
- ❌ `docker-compose.yml` לאורקסטרציה של Planes + Kafka
- ❌ קבצי `.env` לניהול credentials ו-secrets
- ❌ Kubernetes manifests (optional, לפי צורך)
- ❌ CI/CD pipeline (GitHub Actions / GitLab CI)
- ❌ Deployment scripts לסביבות Staging/Production

**זמן משוער:** 2-3 שבועות

#### 4. **Monitoring ו-Observability (40% מושלם)**
**סטטוס:** קיימת תשתית Metrics Exporter, אך לא מלאה

**חסר:**
- ✅ Prometheus Exporter קיים
- ❌ **Grafana Dashboards**: תצוגות ויזואליות לביצועים
- ❌ **Alerting Rules**: התרעות על אירועים קריטיים (DD, Kill-Switches, Errors)
- ❌ **Distributed Tracing**: OpenTelemetry לאבחון בעיות latency
- ❌ **Log Aggregation**: ELK Stack או Loki לניתוח logs מרוכז
- ❌ **Health Checks**: endpoints ל-liveness/readiness

**זמן משוער:** 2-3 שבועות

#### 5. **Documentation (20% מושלם)**
**סטטוס:** קוד מתועד היטב (docstrings בעברית), אך אין תיעוד מקיף

**חסר:**
- ✅ קוד מתועד היטב בעברית
- ❌ **User Manual**: מדריך התקנה והפעלה
- ❌ **API Documentation**: תיעוד פונקציות ומודולים (Sphinx)
- ❌ **Architecture Diagrams**: דיאגרמות של זרימת נתונים והחלטות
- ❌ **Configuration Guide**: הסבר מפורט על כל פרמטר ב-`targets.yaml`
- ❌ **Runbook**: נהלים לטיפול בתקלות

**זמן משוער:** 2 שבועות

#### 6. **Security ו-Compliance (10% מושלם)**
**סטטוס:** אין מנגנוני אבטחה או ניהול secrets

**חסר:**
- ❌ **Secrets Management**: Vault/AWS Secrets Manager ל-API Keys
- ❌ **Encryption at Rest**: הצפנת נתונים רגישים בדיסק
- ❌ **Encryption in Transit**: TLS/SSL לכל תקשורת רשת
- ❌ **Access Control**: RBAC לגישה למודולים שונים
- ❌ **Audit Logging**: רישום כל פעולות המסחר לביקורת
- ❌ **Compliance Checks**: בדיקות רגולטוריות (MiFID II, SEC)

**זמן משוער:** 3-4 שבועות

#### 7. **Backtesting Infrastructure (60% מושלם)**
**סטטוס:** מנוע backtest קיים, אך לא ממוקד-משתמש

**חסר:**
- ✅ Simulation Engine קיים (`simulation.py`)
- ✅ QP Solver עובד עם נתונים סינתטיים
- ❌ **Historical Data Loader**: טעינה אוטומטית של נתונים היסטוריים מ-IBKR
- ❌ **Backtest Report Generator**: יצירת דוחות PDF/HTML עם גרפים
- ❌ **Parameter Sensitivity Analysis**: ניתוח רגישות לשינויים בפרמטרים
- ❌ **Scenario Testing**: בדיקת תרחישי קיצון (2008, COVID-19, וכו')

**זמן משוער:** 2-3 שבועות

---

## 🚀 דרך אל Production (Path to Deployment)

### שלב 1: השלמת אינטגרציה (Integration Completion) - **4-5 שבועות**
**עדיפות: קריטית**

1. **השלמת IBKR Integration** (2-3 שבועות)
   - Account Info API
   - Full Order Placement Flow
   - Execution Reports Consumption
   - Error Handling & Reconnection Logic
   - Paper Trading Mode Toggle

2. **חיבור 3 Planes** (1-2 שבועות)
   - Kafka Setup מקומי
   - E2E Flow: Data → Strategy → Order → Execution
   - Message Schema Validation (Contracts)

3. **End-to-End Testing בסביבת Paper Trading** (1 שבוע)
   - הרצה מלאה עם IBKR Paper Account
   - וולידציה של תוצאות מול backtest סימולטיבי

---

### שלב 2: איכות ויציבות (Quality & Stability) - **5-6 שבועות**
**עדיפות: גבוהה**

1. **פיתוח Test Suite** (3-4 שבועות)
   - Unit Tests: 80%+ coverage למודולי Core
   - Integration Tests ל-3 Planes
   - Mock IBKR Client
   - Continuous Testing ב-CI/CD

2. **Monitoring ו-Observability** (2-3 שבועות)
   - Grafana Dashboards (PnL, Sharpe, Drawdown, Exposure)
   - Alerting Rules (Telegram/Email)
   - Distributed Tracing
   - Log Aggregation

3. **Error Handling ו-Resilience** (1 שבוע)
   - Retry Logic עם Exponential Backoff
   - Circuit Breakers למניעת cascading failures
   - Graceful Degradation (פעולה חלקית בכשלים)

---

### שלב 3: Deployment Infrastructure - **3-4 שבועות**
**עדיפות: בינונית-גבוהה**

1. **Containerization** (1-2 שבועות)
   - Dockerfile אופטימלי (multi-stage builds)
   - docker-compose.yml עם Kafka, Prometheus, Grafana
   - Environment-specific configs (.env files)

2. **CI/CD Pipeline** (1 שבוע)
   - GitHub Actions לבדיקות אוטומטיות
   - Automated builds ו-pushes ל-Docker Registry
   - Deployment scripts לסביבות Staging/Production

3. **Secrets Management** (1 שבוע)
   - HashiCorp Vault או AWS Secrets Manager
   - Rotation policy ל-API keys
   - Audit logging של גישות

---

### שלב 4: Security ו-Compliance - **3-4 שבועות**
**עדיפות: בינונית** (תלוי ברגולציה)

1. **Encryption & Access Control** (2 שבועות)
   - TLS/SSL לכל תקשורת
   - Encrypted storage לנתונים רגישים
   - RBAC למודולים קריטיים

2. **Audit & Compliance** (1-2 שבועות)
   - Audit logs לכל פעולות מסחר
   - Compliance reports (MiFID II, אם רלוונטי)
   - Disaster Recovery Plan

---

### שלב 5: Documentation ו-Knowledge Transfer - **2 שבועות**
**עדיפות: בינונית**

1. **User & Developer Documentation** (1 שבוע)
   - Installation & Configuration Guide
   - API Documentation (Sphinx)
   - Architecture Diagrams

2. **Runbook & Training** (1 שבוע)
   - Incident Response Procedures
   - Training sessions לצוות תפעול
   - Video tutorials (optional)

---

### שלב 6: Production Rollout - **2-3 שבועות**
**עדיפות: קריטית**

1. **Staging Environment Testing** (1 שבוע)
   - הרצה מלאה בסביבת Staging עם נתונים אמיתיים
   - Load testing (אם רלוונטי)

2. **Phased Production Deployment** (1-2 שבועות)
   - **Week 1**: Paper Trading בסביבת Production (ללא כסף אמיתי)
   - **Week 2**: Pilot עם סכום קטן ($1K-$5K)
   - **Week 3**: Gradual Ramp-Up לפי ביצועים

3. **Post-Deployment Monitoring** (רציף)
   - Daily PnL reviews
   - Weekly performance reports
   - Monthly strategy optimization

---

## ⏱️ Timeline Summary (סיכום ציר זמן)

| שלב | משך זמן | תלות | סטטוס |
|-----|---------|------|-------|
| 1. Integration Completion | 4-5 שבועות | אין | 🟡 בתהליך |
| 2. Quality & Stability | 5-6 שבועות | אחרי שלב 1 | 🔴 לא התחיל |
| 3. Deployment Infra | 3-4 שבועות | במקביל לשלב 2 | 🔴 לא התחיל |
| 4. Security & Compliance | 3-4 שבועות | במקביל לשלב 2-3 | 🔴 לא התחיל |
| 5. Documentation | 2 שבועות | במקביל לשלב 2-3 | 🔴 לא התחיל |
| 6. Production Rollout | 2-3 שבועות | אחרי שלבים 1-5 | 🔴 לא התחיל |

**סה"כ זמן עד Production:** **12-16 שבועות** (3-4 חודשים)

**זמן עד Pilot ראשון:** **9-11 שבועות** (2-2.5 חודשים)

---

## 💡 המלצות קריטיות (Critical Recommendations)

### 1. **הקצאת משאבים (Resource Allocation)**
- **מפתח מוביל 1**: IBKR Integration + Order Plane (full-time)
- **מפתח 2**: Testing + CI/CD (full-time)
- **DevOps Engineer**: Docker + Monitoring (50% allocation)
- **Quant Researcher**: Strategy optimization + Validation (25% allocation)

### 2. **סדרי עדיפויות (Prioritization)**
**Must-Have לפני Production:**
1. ✅ IBKR Integration מלא
2. ✅ E2E Testing עם Paper Trading
3. ✅ Monitoring & Alerting
4. ✅ Secrets Management
5. ✅ Kill-Switches Validation

**Nice-to-Have (ניתן לדחות):**
- Compliance Reports (אלא אם רגולציה דורשת)
- Advanced Backtesting UI
- Kubernetes Deployment (Docker Compose מספיק בהתחלה)

### 3. **ניהול סיכונים (Risk Management)**
**סיכונים טכנולוגיים:**
- ❌ **אין redundancy**: IBKR הוא single point of failure
  - **פתרון:** Multi-broker support (Alpaca, Tradier) - תכנון ארוך-טווח
- ❌ **אין disaster recovery**: נתונים ותוכנה לא מגובים
  - **פתרון:** Daily backups + Cloud replication

**סיכונים פיננסיים:**
- ⚠️ **אין backtesting עם נתונים אמיתיים**: תוצאות סימולטיביות עלולות להטעות
  - **פתרון:** Historical data download מ-IBKR לוולידציה
- ⚠️ **Transaction costs לא מוולידים**: Lambda ו-slippage מוערכים
  - **פתרון:** Online learning ממסחר Paper Trading

**סיכונים תפעוליים:**
- ❌ **אין runbook**: אין נהלים לטיפול בתקלות
  - **פתרון:** Runbook כחלק משלב 5
- ❌ **אין on-call rotation**: אין מי שיטפל בבעיות 24/7
  - **פתרון:** PagerDuty + on-call schedule

### 4. **KPIs למעקב (Key Performance Indicators)**
**Pre-Production:**
- Test Coverage ≥ 80%
- Paper Trading Sharpe ≥ 1.0 (30 days)
- Max Drawdown ≤ 10% (Paper Trading)
- Latency: Data → Order < 500ms (p95)

**Production:**
- Daily PnL > 0 (60% של הימים)
- Annual Sharpe ≥ 1.5
- Max Drawdown ≤ 15%
- Uptime ≥ 99.5%
- Order Fill Rate ≥ 98%

---

## 📈 יתרונות תחרותיים (Competitive Advantages)

1. **Multi-Signal Ensemble**: שילוב 6 אסטרטגיות לפיזור סיכון ויציבות
2. **Regime-Adaptive**: הסתגלות דינמית לתנאי שוק משתנים
3. **Online Learning**: שיפור מתמשך מביצועים בפועל
4. **Overfitting Protection**: CSCV + PSR למניעת curve-fitting
5. **3-Plane Architecture**: הפרדה נקייה בין נתונים, החלטות, וביצוע
6. **Cross-Asset**: מסחר בנכסים מרובים (equity, futures, FX, crypto)

---

## 🔍 נספחים (Appendices)

### נספח א': רשימת טכנולוגיות
- **שפת תכנות:** Python 3.9+
- **אופטימיזציה:** CVXPY (convex optimization)
- **מבני נתונים:** NumPy, Pandas
- **למידת מכונה:** Scikit-learn, HMM (hmmlearn)
- **ברוקר:** Interactive Brokers (ib_insync)
- **Message Bus:** Kafka (kafka-python)
- **Monitoring:** Prometheus, Grafana
- **Containerization:** Docker, Docker Compose
- **CI/CD:** GitHub Actions

### נספח ב': רשימת פרמטרים קריטיים
| פרמטר | ערך ברירת מחדל | תיאור |
|-------|----------------|--------|
| VOL_TARGET | 0.10 | יעד תנודתיות שנתי (10%) |
| BOX_LIM | 0.25 | מגבלת פוזיציה מקסימלית לנכס (25%) |
| KILL_PNL | -0.05 | סף הפסד להפעלת Kill-Switch (-5%) |
| MAX_DD_KILL_SWITCH | 0.15 | Drawdown מקסימלי להפעלת Kill-Switch (15%) |
| TURNOVER_PEN | 0.002 | קנס על turnover (0.2%) |
| LAMBDA_INIT | 5e-4 | פרמטר עלות טרנזקציה התחלתי |
| POV_CAP | 0.08 | מגבלת POV (8% מ-volume) |

### נספח ג': אנשי קשר
| תפקיד | אחריות |
|-------|--------|
| Project Lead | אדריכלות, strategy design, deployment |
| Lead Developer | Core engine, IBKR integration |
| DevOps Engineer | Infrastructure, monitoring, CI/CD |
| Quant Researcher | Signal development, validation |

---

## 📞 נקודות פעולה (Action Items)

### דחוף (Immediate - השבוע הקרוב)
1. ✅ סיום מסמך מנהלים זה
2. 🔲 הקצאת משאבי פיתוח (developers, infrastructure)
3. 🔲 הגדרת סביבת Paper Trading ב-IBKR
4. 🔲 הקמת Kafka מקומי לפיתוח

### קצר-טווח (1-2 שבועות)
1. 🔲 השלמת IBKR Account Info API
2. 🔲 פיתוח Order Placement Full Flow
3. 🔲 הקמת Grafana Dashboard ראשוני
4. 🔲 כתיבת Unit Tests ראשונים (Signals, QP)

### בינוני-טווח (1-2 חודשים)
1. 🔲 E2E Testing עם נתונים אמיתיים
2. 🔲 Dockerization מלא
3. 🔲 CI/CD Pipeline
4. 🔲 Security Audit ראשוני

### ארוך-טווח (3-4 חודשים)
1. 🔲 Production Deployment
2. 🔲 Pilot Trading עם סכום קטן
3. 🔲 Gradual Ramp-Up
4. 🔲 Post-deployment optimization

---

**סיכום:** המערכת נמצאת בשלב פיתוח מתקדם עם core engine מושלם, אך דורשת 3-4 חודשי עבודה נוספים להשלמת אינטגרציה, בדיקות, ו-deployment infrastructure לפני שניתן להפעילה ב-production. ההשקעה הנדרשת היא 2-3 מפתחים ל-3-4 חודשים.

---

**נכון ליום:** 28 אוקטובר 2025
**נוצר על ידי:** Claude Code (AI Assistant)
**לאישור:** Project Lead / CTO
