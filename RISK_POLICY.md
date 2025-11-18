# Risk Policy - מדיניות ניהול סיכונים
## Algorithmic Trading System Risk Management Policy

**תאריך:** 2025-11-17
**גרסה:** 1.0
**מצב:** 📋 DRAFT - PENDING APPROVAL
**תוקף:** עד 2026-11-17 (שנה אחת)

---

## 🎯 מטרה

מסמך זה מגדיר את מדיניות ניהול הסיכונים של מערכת המסחר האלגוריתמית, כולל:
- פרמטרי סיכון מאושרים
- מנגנוני Kill-Switch
- מגבלות חשיפה (Exposure Limits)
- נהלי אישור ושינוי פרמטרים
- חובות דיווח

**עיקרון מנחה:** Safety First - הגנה על ההון היא בעדיפות עליונה.

---

## 📊 גורמי אישור (Governance)

### תפקידים

| תפקיד | אחראי | אחריות | חובת דיווח |
|-------|-------|---------|-------------|
| **Risk Officer** | TBD | אישור פרמטרי סיכון, חקירת תקלות | יומי |
| **CTO** | TBD | אישור שינויים ארכיטקטוניים | שבועי |
| **Lead Quant** | TBD | אישור אסטרטגיות, ניתוח ביצועים | יומי |
| **Compliance Officer** | TBD | ציות רגולטורי, ביקורת | חודשי |
| **Trading Desk Manager** | TBD | פיקוח על ביצוע מסחר | יומי |

### מטריצת אישורים

| פעולה | Risk Officer | CTO | Lead Quant | דרגת דחיפות |
|-------|-------------|-----|-----------|-------------|
| **שינוי פרמטר סיכון** | ✅ חובה | ✅ חובה | ⚠️ יעוץ | 🔴 HIGH |
| **הוספת נכס למסחר** | ✅ חובה | ⚠️ יעוץ | ✅ חובה | 🟡 MEDIUM |
| **שינוי אסטרטגיה** | ⚠️ יעוץ | ⚠️ יעוץ | ✅ חובה | 🟡 MEDIUM |
| **Go-Live ל-Production** | ✅ חובה | ✅ חובה | ✅ חובה | 🔴 CRITICAL |
| **Kill-Switch Manual** | ✅ חובה | 🔔 התראה | 🔔 התראה | 🔴 CRITICAL |

---

## 🛡️ פרמטרי סיכון מאושרים

### 1. Kill-Switches (מתגי חירום)

#### 1.1 PnL Kill Switch
**תיאור:** עצירה אוטומטית במקרה של הפסד מצטבר.

| פרמטר | ערך | יחידה | סביבה |
|-------|-----|-------|--------|
| **KILL_PNL** | -5% | % מה-NAV | Production |
| **KILL_PNL** | -10% | % מה-NAV | Paper Trading |
| **התראה מוקדמת** | -3% | % מה-NAV | Production |

**תנאי הפעלה:**
```python
IF (current_pnl / initial_nav) < KILL_PNL:
    TRIGGER_IMMEDIATE_HALT()
    FLATTEN_ALL_POSITIONS()
    NOTIFY_RISK_OFFICER()
```

**אישור שינוי:** Risk Officer + CTO (שניהם חובה)

---

#### 1.2 Max Drawdown Kill Switch
**תיאור:** עצירה אוטומטית במקרה של ירידה מקסימלית.

| פרמטר | ערך | יחידה | סביבה |
|-------|-----|-------|--------|
| **MAX_DD** | 15% | % מה-Peak NAV | Production |
| **MAX_DD** | 20% | % מה-Peak NAV | Paper Trading |
| **התראה מוקדמת** | 10% | % מה-Peak NAV | Production |

**תנאי הפעלה:**
```python
IF (peak_nav - current_nav) / peak_nav > MAX_DD:
    TRIGGER_IMMEDIATE_HALT()
    FLATTEN_ALL_POSITIONS()
    NOTIFY_RISK_OFFICER()
```

**אישור שינוי:** Risk Officer + CTO (שניהם חובה)

---

#### 1.3 PSR Kill Switch
**תיאור:** עצירה במקרה של Probabilistic Sharpe Ratio נמוך.

| פרמטר | ערך | יחידה | סביבה |
|-------|-----|-------|--------|
| **PSR_MIN** | 0.20 | Probability | Production |
| **PSR_MIN** | 0.15 | Probability | Paper Trading |
| **חישוב כל** | 30 | ימי מסחר | כל הסביבות |

**תנאי הפעלה:**
```python
IF psr_30d < PSR_MIN:
    TRIGGER_IMMEDIATE_HALT()
    REQUIRE_RISK_OFFICER_REVIEW()
```

**אישור שינוי:** Risk Officer + Lead Quant (שניהם חובה)

---

### 2. Exposure Limits (מגבלות חשיפה)

#### 2.1 Position Size Limits
**תיאור:** מגבלות על גודל פוזיציה בנכס בודד.

| פרמטר | Calm | Normal | Storm | יחידה |
|-------|------|--------|-------|-------|
| **BOX_LIM** | 25% | 20% | 15% | % מה-NAV |
| **MAX_SINGLE_STOCK** | 15% | 10% | 5% | % מה-NAV |
| **MAX_SECTOR** | 40% | 30% | 20% | % מה-NAV |

**הגדרת רגימות:**
- **Calm**: VIX < 15
- **Normal**: 15 ≤ VIX < 25
- **Storm**: VIX ≥ 25

**תנאי הפעלה:**
```python
IF abs(position_value / nav) > BOX_LIM[regime]:
    REJECT_ORDER()
    LOG_VIOLATION()
```

**אישור שינוי:** Risk Officer (חובה)

---

#### 2.2 Portfolio Limits
**תיאור:** מגבלות על רמת החשיפה הכוללת.

| פרמטר | Calm | Normal | Storm | יחידה |
|-------|------|--------|-------|-------|
| **GROSS_LIM** | 2.5 | 2.0 | 1.0 | × NAV |
| **NET_LIM** | 1.0 | 0.8 | 0.4 | × NAV |
| **LEVERAGE_MAX** | 2.0 | 1.5 | 1.0 | × NAV |

**הגדרות:**
- **Gross Exposure**: sum(abs(position_value)) / nav
- **Net Exposure**: abs(sum(position_value)) / nav
- **Leverage**: total_borrowed / nav

**תנאי הפעלה:**
```python
IF gross_exposure > GROSS_LIM[regime]:
    REDUCE_POSITIONS()
    LOG_VIOLATION()

IF net_exposure > NET_LIM[regime]:
    REBALANCE_TO_NEUTRAL()
```

**אישור שינוי:** Risk Officer + CTO (שניהם חובה)

---

#### 2.3 Concentration Limits
**תיאור:** מגבלות על ריכוז בנכסים ספציפיים.

| פרמטר | ערך | יחידה | הערות |
|-------|-----|-------|-------|
| **TOP_5_POSITIONS** | ≤60% | % מה-NAV | 5 הפוזיציות הגדולות |
| **TOP_10_POSITIONS** | ≤80% | % מה-NAV | 10 הפוזיציות הגדולות |
| **MIN_DIVERSIFICATION** | ≥8 | מניות | מספר מינימלי של נכסים |

**תנאי הפעלה:**
```python
IF top_5_concentration > 0.60:
    WARN_CONCENTRATION_RISK()
    REBALANCE_IF_POSSIBLE()
```

**אישור שינוי:** Risk Officer (חובה)

---

### 3. Trading Limits (מגבלות מסחר)

#### 3.1 Order Size Limits

| פרמטר | ערך | יחידה | הערות |
|-------|-----|-------|-------|
| **MAX_ORDER_SIZE** | 5% | % מה-NAV | פר Order |
| **MAX_DAILY_TURNOVER** | 100% | % מה-NAV | סה"כ יומי |
| **MAX_ORDERS_PER_MINUTE** | 20 | orders/min | Rate limiting |

**תנאי הפעלה:**
```python
IF order_size > MAX_ORDER_SIZE * nav:
    REJECT_ORDER()
    LOG_VIOLATION("Order size exceeds limit")
```

---

#### 3.2 Market Impact Limits

| פרמטר | ערך | יחידה | הערות |
|-------|-----|-------|-------|
| **MAX_ADV_PERCENT** | 5% | % של ADV | Average Daily Volume |
| **SLIPPAGE_TOLERANCE** | 0.5% | % מהמחיר | התראה בלבד |
| **TIMEOUT_LIMIT** | 300 | שניות | Cancel אחרי |

**הגדרות:**
- **ADV**: Average Daily Volume (30 ימים)
- **Slippage**: (execution_price - intended_price) / intended_price

---

### 4. Risk Monitoring (ניטור סיכונים)

#### 4.1 Daily Risk Checks

**חובה לבצע פעם ביום (לפני פתיחת שוק):**

- [ ] בדיקת NAV ו-PnL מצטבר
- [ ] בדיקת Max Drawdown
- [ ] בדיקת Exposure (Gross, Net)
- [ ] בדיקת Concentration
- [ ] בדיקת PSR ו-Sharpe
- [ ] סקירת אירועים יוצאי דופן מהיום הקודם

**אחראי:** Trading Desk Manager + Risk Officer

---

#### 4.2 Weekly Risk Review

**חובה לבצע פעם בשבוע (ימי שישי):**

- [ ] ניתוח ביצועים שבועי (PnL, Sharpe, DD)
- [ ] סקירת תקלות וIncidents
- [ ] סקירת פרמטרי סיכון (האם צריך שינוי?)
- [ ] בדיקת Correlation Matrix
- [ ] סקירת Covariance Estimation
- [ ] בדיקת Blind-Spot Agent (אזעקות)

**אחראי:** Risk Officer + Lead Quant

**תיעוד:** דוח שבועי ב-`logs/weekly_risk_report_YYYY-MM-DD.md`

---

#### 4.3 Monthly Risk Audit

**חובה לבצע פעם בחודש:**

- [ ] ביקורת מלאה של פרמטרי סיכון
- [ ] סקירת Backtest vs. Live Performance
- [ ] ניתוח שינויים ברגימת שוק
- [ ] בדיקת ציות ל-Risk Policy
- [ ] עדכון Risk Policy (אם נדרש)

**אחראי:** Risk Officer + Compliance Officer

**תיעוד:** דוח חודשי ב-`audits/monthly_risk_audit_YYYY-MM.md`

---

## 🚨 נהלי חירום

### Kill-Switch Activation

**במקרה של הפעלת Kill-Switch:**

1. **רגע 0-10 שניות:**
   - המערכת עוצרת אוטומטית
   - כל ההזמנות הפתוחות מבוטלות
   - התראה נשלחת ל-Risk Officer + Trading Desk Manager

2. **רגע 10-120 שניות:**
   - ביצוע Rollback (ראה `ROLLBACK_PROCEDURE.md`)
   - פירוק כל הפוזיציות (flatten)
   - תיעוד האירוע ב-`logs/incidents.log`

3. **תוך 1-4 שעות:**
   - Root-Cause Analysis
   - דוח ל-Risk Officer
   - החלטה האם להמשיך או להפסיק

4. **תוך 1-5 ימים:**
   - תיקון הבעיה שזוהתה
   - בדיקה מחודשת ב-Paper Trading
   - אישור Risk Officer לחידוש פעילות

**חובת הודעה:**
- Risk Officer: מיידי (SMS + Email)
- CTO: תוך 15 דקות (Email)
- Compliance Officer: תוך 1 שעה (Email)

---

### Risk Limit Breaches

**במקרה של הפרת מגבלת סיכון (ללא Kill-Switch):**

| חומרה | תגובה | זמן תגובה | דיווח |
|-------|--------|----------|-------|
| **CRITICAL** | Halt + Flatten | <1 דקה | Risk Officer (מיידי) |
| **HIGH** | Reduce Position | <5 דקות | Trading Desk (מיידי) |
| **MEDIUM** | Warning + Monitor | <30 דקות | Log only |
| **LOW** | Log only | - | סקירה שבועית |

---

## 📝 נהלי שינוי פרמטרים

### תהליך שינוי פרמטר סיכון

**שלבים:**

1. **הצעה:**
   - Lead Quant או Risk Officer מציעים שינוי
   - מסמך הצעה כולל נימוק, השפעה צפויה, ניתוח Backtest

2. **סקירה:**
   - Risk Officer + CTO + Lead Quant סוקרים את ההצעה
   - בדיקה: האם יש השפעה על ביצועים? על סיכון?
   - החלטה: אישור / דחייה / בקשת שינויים

3. **אישור:**
   - אישור פורמלי בכתב (Email)
   - עדכון `RISK_POLICY.md` עם גרסה חדשה
   - עדכון `config/risk_params.yaml`

4. **בדיקה:**
   - בדיקה ב-Paper Trading (מינימום 5 ימי מסחר)
   - השוואה לביצועי Baseline
   - אישור סופי

5. **יישום:**
   - Deploy ל-Production
   - ניטור הדוק (7 ימי מסחר)
   - דוח סיכום

**זמן משוער:** 2-3 שבועות

---

### Log of Changes

| תאריך | פרמטר | ערך ישן | ערך חדש | אישור | נימוק |
|-------|--------|---------|---------|-------|-------|
| 2025-11-17 | KILL_PNL | N/A | -5% | Risk Officer + CTO | אתחול ראשוני |
| 2025-11-17 | MAX_DD | N/A | 15% | Risk Officer + CTO | אתחול ראשוני |
| 2025-11-17 | BOX_LIM | N/A | 25%/20%/15% | Risk Officer | אתחול ראשוני |
| - | - | - | - | - | - |

**הערה:** כל שינוי חייב להיות מתועד כאן!

---

## 📊 KPIs ומדדי ביצועים

### מדדי סיכון (Risk Metrics)

| מדד | יעד | התראה | קריטי |
|-----|-----|-------|-------|
| **Sharpe Ratio (30d)** | >1.5 | <1.0 | <0.5 |
| **Max Drawdown (YTD)** | <10% | >10% | >15% |
| **PSR (30d)** | >0.95 | <0.50 | <0.20 |
| **Hit Rate** | >60% | <55% | <50% |
| **Profit Factor** | >1.5 | <1.2 | <1.0 |

### מדדי תפעול (Operational Metrics)

| מדד | יעד | התראה | קריטי |
|-----|-----|-------|-------|
| **Order Fill Rate** | >98% | <95% | <90% |
| **Latency (p95)** | <50ms | >100ms | >500ms |
| **Kill-Switch Triggers** | 0/חודש | 1/חודש | >2/חודש |
| **Risk Limit Breaches** | 0/שבוע | 1/שבוע | >3/שבוע |
| **System Uptime** | >99.5% | <99% | <95% |

---

## ✅ Compliance & Audit

### Audit Trail

**כל הפעולות הבאות חייבות להיות מתועדות:**

- שינויי פרמטרי סיכון
- הפעלת Kill-Switch (אוטומטית או ידנית)
- הפרות מגבלות סיכון
- שינויים באסטרטגיות מסחר
- אישורי Go-Live / Rollback

**מיקום לוגים:** `logs/audit_trail.log`

**שמירה:** 5 שנים (דרישה רגולטורית)

---

### Regulatory Compliance

**רגולציות רלוונטיות (ככל שרלוונטי):**

- [ ] MiFID II (אם מסחר באירופה)
- [ ] SEC Rule 15c3-5 (אם מסחר בארה"ב)
- [ ] רשות ניירות ערך ישראלית (אם רלוונטי)

**Compliance Officer אחראי על:**
- בדיקת ציות רגולטורי רבעוני
- הכנת דוחות לרגולטור (אם נדרש)
- עדכון מדיניות לפי שינויי חקיקה

---

## 📞 חובות דיווח

### דיווח יומי

**אחראי:** Trading Desk Manager

**נמענים:** Risk Officer

**תוכן:**
- PnL יומי
- מספר עסקאות
- Exposure נוכחי
- אירועים יוצאי דופן

**פורמט:** Email קצר או Dashboard

---

### דיווח שבועי

**אחראי:** Risk Officer

**נמענים:** CTO + Lead Quant

**תוכן:**
- סיכום ביצועים שבועי
- מדדי סיכון (Sharpe, DD, PSR)
- תקלות וIncidents
- המלצות לשינויים (אם יש)

**פורמט:** `logs/weekly_risk_report_YYYY-MM-DD.md`

---

### דיווח חודשי

**אחראי:** Risk Officer + Compliance Officer

**נמענים:** CTO + הנהלה

**תוכן:**
- ביקורת חודשית מלאה
- ניתוח ביצועים vs. Benchmark
- ציות ל-Risk Policy
- המלצות אסטרטגיות

**פורמט:** `audits/monthly_risk_audit_YYYY-MM.md`

---

## 📋 חתימות ואישורים

### גרסה 1.0 - אתחול ראשוני

**מסמך זה נוצר על ידי:** Claude Code (AI Assistant)
**תאריך יצירה:** 2025-11-17
**מצב:** 📋 DRAFT - PENDING APPROVAL

---

### אישור פורמלי (חובה לפני Production!)

| תפקיד | שם | חתימה | תאריך | הערות |
|-------|-----|-------|-------|-------|
| **Risk Officer** | __________ | __________ | _______ | ________________________ |
| **CTO** | __________ | __________ | _______ | ________________________ |
| **Lead Quant** | __________ | __________ | _______ | ________________________ |
| **Compliance Officer** | __________ | __________ | _______ | ________________________ |

---

### תוקף המדיניות

**תוקף:** 1 שנה מיום האישור
**סקירה הבאה:** לא יאוחר מ-2026-11-17
**גרסאות:** גרסה חדשה נדרשת לכל שינוי מהותי בפרמטרים

---

## 📚 מסמכים קשורים

- `PRE_LIVE_CHECKLIST.md` - רשימת בדיקה לפני Production
- `ROLLBACK_PROCEDURE.md` - נוהל Rollback חירום
- `RUNBOOK.md` - נהלים תפעוליים
- `INCIDENT_PLAYBOOK.md` - טיפול בתקלות
- `RACI_MATRIX.md` - מטריצת אחריות
- `GO_LIVE_DECISION_GATE.md` - אישור Go-Live

---

**הערה חשובה:**
מסמך זה הוא טיוטה ודורש אישור פורמלי מכל הגורמים הרלוונטיים לפני כניסה ל-Production.
**אין להפעיל את המערכת ב-Production ללא אישור Risk Officer + CTO!**

---

**End of Risk Policy v1.0**
