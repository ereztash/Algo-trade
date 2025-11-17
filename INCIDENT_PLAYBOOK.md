# Incident Playbook - מדריך טיפול בתקלות
## Algorithmic Trading System Incident Response Playbook

**תאריך:** 2025-11-17
**גרסה:** 1.0
**מצב:** 📋 DRAFT - PENDING APPROVAL

---

## 🎯 מטרה

מסמך זה מספק נהלי טיפול מפורטים לתקלות נפוצות במערכת המסחר האלגוריתמית.
**עיקרון:** כל תקלה טופלה תמיד באותו אופן - consistency, speed, documentation.

---

## 📋 רשימת תקלות (Incidents)

| # | תקלה | חומרה | זמן תגובה | עמוד |
|---|------|--------|----------|------|
| **INC-001** | Kill-Switch Triggered | 🔴 CRITICAL | <1 min | [קישור](#inc-001-kill-switch-triggered) |
| **INC-002** | IBKR Connection Lost | 🔴 CRITICAL | <2 min | [קישור](#inc-002-ibkr-connection-lost) |
| **INC-003** | High Order Rejection Rate | 🟡 HIGH | <5 min | [קישור](#inc-003-high-order-rejection-rate) |
| **INC-004** | Kafka Broker Down | 🟡 HIGH | <5 min | [קישור](#inc-004-kafka-broker-down) |
| **INC-005** | High Latency Spike | 🟡 HIGH | <10 min | [קישור](#inc-005-high-latency-spike) |
| **INC-006** | Data Quality Failure | 🟡 HIGH | <10 min | [קישור](#inc-006-data-quality-failure) |
| **INC-007** | Covariance Matrix Singular | 🟢 MEDIUM | <15 min | [קישור](#inc-007-covariance-matrix-singular) |
| **INC-008** | Risk Limit Breach | 🟢 MEDIUM | <15 min | [קישור](#inc-008-risk-limit-breach) |
| **INC-009** | Pacing Violation | 🟢 MEDIUM | <30 min | [קישור](#inc-009-pacing-violation) |
| **INC-010** | Disk Space Low | 🟢 MEDIUM | <30 min | [קישור](#inc-010-disk-space-low) |

---

## 🚨 INC-001: Kill-Switch Triggered

### סימפטומים
- אזעקה: "KILL SWITCH ACTIVATED"
- Strategy Plane הפסיק לשלוח אותות
- Order Plane ביטל כל ההזמנות הפתוחות
- Logs: `grep "kill.switch" logs/*.log`

### חומרה
🔴 **CRITICAL** - עצירה מיידית של המערכת

### זמן תגובה
<1 דקה

### גורמים אחראיים
- **Primary:** Risk Officer
- **Secondary:** CTO
- **Notify:** Trading Desk Manager, Lead Quant

---

### תהליך טיפול

#### שלב 1: אימות (0-30 שניות)
```bash
# בדוק איזה kill-switch הופעל
grep "kill.switch" logs/*.log | tail -5

# בדוק סטטוס נוכחי
ps aux | grep -E "strategy|order_plane"

# בדוק פוזיציות פתוחות
python scripts/check_positions.py
```

**שאלות לבירור:**
- [ ] איזה kill-switch הופעל? (PnL / Max DD / PSR)
- [ ] מה הערך שגרם להפעלה?
- [ ] האם יש פוזיציות פתוחות?
- [ ] האם המערכת עצרה בהצלחה?

---

#### שלב 2: פירוק פוזיציות (30-120 שניות)

**אם יש פוזיציות פתוחות:**
```bash
# הפעל rollback מלא
python scripts/emergency_rollback.py --flatten-all

# עקוב אחרי הביצוע
tail -f logs/rollback.log
```

**בדיקה:**
```bash
# ודא שהכל flat
python scripts/check_positions.py
# Expected output: "All positions flat"
```

---

#### שלב 3: תיעוד (2-5 דקות)

```bash
# צור incident report
cat > logs/incidents/incident_$(date +%Y%m%d_%H%M%S).md <<EOF
# Incident Report: Kill-Switch Activation

**Date:** $(date)
**Kill-Switch:** [PnL / Max DD / PSR]
**Trigger Value:** [ערך שהפעיל]
**Threshold:** [סף]
**Duration:** [כמה זמן המערכת פעלה לפני]

## Timeline
- 09:30 - Trading started
- XX:XX - Kill-switch triggered
- XX:XX - Positions flattened
- XX:XX - Incident closed

## Impact
- P&L at trigger: \$XXXX
- Final P&L: \$XXXX
- Positions closed: X
- Slippage: X%

## Root Cause
[TBD - requires analysis]

## Actions Taken
1. Verified system halt
2. Flattened all positions
3. Archived logs
4. Notified Risk Officer

## Next Steps
1. Root-cause analysis
2. Risk Officer review
3. Decision to resume or halt
EOF
```

---

#### שלב 4: הודעה (מיידית)

```bash
# שלח התראה ל-Risk Officer
python scripts/send_alert.py \
  --severity CRITICAL \
  --incident "Kill-Switch Triggered" \
  --recipients risk_officer,cto,trading_desk

# או ידני:
# Email: risk@company.com
# SMS: +972-XX-XXX-XXXX
# Subject: "CRITICAL: Kill-Switch Activated - Immediate Action Required"
```

---

#### שלב 5: החלטה (תוך 1-4 שעות)

**Risk Officer מחליט:**

**אפשרות A: המשך פעילות**
- [ ] Root cause מזוהה וברור
- [ ] הבעיה נפתרה
- [ ] Paper trading עבר בהצלחה
- [ ] אישור פורמלי ב-Email

```bash
# אם מאושר, התחל מחדש
python scripts/restart_system.py --mode production
```

**אפשרות B: הפסקה זמנית**
- [ ] Root cause לא ברור
- [ ] נדרשת חקירה נוספת
- [ ] נדרש שינוי פרמטרים

```bash
# המתן לאישור, המערכת תישאר עצורה
echo "System halted pending investigation"
```

**אפשרות C: הפסקה מוחלטת**
- [ ] בעיה חמורה שזוהתה
- [ ] סיכון גבוה להמשך
- [ ] דרושה תיקון קוד

```bash
# עצור לחלוטין
sudo systemctl stop algo-trading
echo "System shutdown - manual restart required"
```

---

### Checklist

**במהלך האירוע:**
- [ ] אימות עצירת מערכת
- [ ] פירוק כל הפוזיציות
- [ ] תיעוד האירוע
- [ ] הודעה לגורמים

**לאחר האירוע:**
- [ ] Root-cause analysis
- [ ] דוח ל-Risk Officer
- [ ] החלטה לגבי המשך
- [ ] עדכון Incident Log

---

## 🔌 INC-002: IBKR Connection Lost

### סימפטומים
- אזעקה: "IBKR Connection Lost"
- Logs: `Connection refused`, `Socket closed`
- Order Plane לא מצליח לשלוח orders
- Execution Reports לא מתקבלים

### חומרה
🔴 **CRITICAL**

### זמן תגובה
<2 דקות

### גורמים אחראיים
- **Primary:** Trading Desk Manager
- **Secondary:** DevOps On-Call
- **Notify:** Risk Officer

---

### תהליך טיפול

#### שלב 1: אבחון (0-30 שניות)

```bash
# בדוק סטטוס חיבור
nc -zv localhost 7497  # Paper Trading
nc -zv localhost 7496  # Live Trading

# בדוק logs
grep -i "connection" logs/order_plane.log | tail -10

# בדוק TWS/Gateway
ps aux | grep -i tws
# or
ps aux | grep -i gateway
```

**שאלות לבירור:**
- [ ] TWS/Gateway פועל?
- [ ] האם זה נפילה או disconnect מכוון?
- [ ] יש פוזיציות פתוחות?

---

#### שלב 2: פעולה מיידית (30-90 שניות)

**אם יש פוזיציות פתוחות:**
```bash
# נסה reconnect מהיר
python scripts/ibkr_reconnect.py --timeout 30

# אם נכשל, עצור strategy ל-30 שניות
kill -STOP $STRATEGY_PLANE_PID
```

**אם TWS/Gateway נפל:**
```bash
# הפעל מחדש TWS/Gateway
# (ידני - צריך UI access)

# או אם Gateway בdocker:
docker restart ibkr-gateway
```

---

#### שלב 3: reconnect (90-120 שניות)

```bash
# המתן ל-TWS להתחיל (30 שניות)
sleep 30

# נסה reconnect
python -c "
from algo_trade.core.execution.IBKR_handler import IBKRHandler
handler = IBKRHandler()
handler.connect()
print('Connected:', handler.is_connected())
"

# אם הצליח:
kill -CONT $STRATEGY_PLANE_PID  # Continue strategy
```

---

#### שלב 4: ולידציה

```bash
# בדוק חיבור יציב
for i in {1..10}; do
  nc -zv localhost 7497
  sleep 5
done

# בדוק שהמערכת חזרה לעבודה
grep "connected" logs/order_plane.log | tail -5
```

---

### Recovery Decision

**אם החיבור חזר תוך 2 דקות:**
- ✅ המשך פעילות רגילה
- 📝 תעד את האירוע

**אם החיבור לא חזר תוך 2 דקות:**
- 🛑 הפעל rollback (INC-001)
- 📞 הודע ל-Risk Officer

---

### Checklist

- [ ] TWS/Gateway פועל
- [ ] חיבור יציב
- [ ] Orders זורמים
- [ ] Execution Reports מתקבלים
- [ ] תיעוד האירוע

---

## ⛔ INC-003: High Order Rejection Rate

### סימפטומים
- Metrics: `order_rejection_rate > 10%`
- Logs: `Order rejected`, `Insufficient buying power`
- Strategy ממשיך לייצר אותות אבל Orders נדחים

### חומרה
🟡 **HIGH**

### זמן תגובה
<5 דקות

### גורמים אחראיים
- **Primary:** Trading Desk Manager
- **Secondary:** Lead Quant

---

### תהליך טיפול

#### שלב 1: אבחון

```bash
# מה הסיבות לדחיות?
grep -i "reject" logs/order_plane.log | tail -20

# האם זה buying power?
python scripts/check_account.py

# האם זה risk limits?
grep -i "risk.limit" logs/*.log
```

**סיבות נפוצות:**
1. **Insufficient buying power** → Account issue
2. **Risk limit exceeded** → Exposure too high
3. **Invalid order** → Bug in strategy
4. **Market closed** → Wrong timing

---

#### שלב 2: פתרון

**אם buying power:**
```bash
# בדוק Account Info
python scripts/check_account.py

# האם צריך להפחית exposure?
python scripts/reduce_exposure.py --target 0.5
```

**אם risk limit:**
```bash
# איזה limit?
grep "BOX_LIM\|GROSS_LIM\|NET_LIM" logs/*.log

# האם נכון? אם כן, המתן לפוזיציות לסגור
# אם לא, בדוק config
cat config/risk_params.yaml
```

**אם invalid orders:**
```bash
# בדוק איזה orders
grep "invalid" logs/order_plane.log

# האם bug בקוד?
# אם כן → עצור strategy, תקן, test
kill -TERM $STRATEGY_PLANE_PID
```

---

#### שלב 3: ולידציה

```bash
# בדוק שהrejection rate ירד
python scripts/check_metrics.py --metric order_rejection_rate

# Target: <5%
```

---

### Checklist

- [ ] סיבת דחיות זוהתה
- [ ] פתרון יושם
- [ ] Rejection rate חזר לנורמלי
- [ ] תיעוד

---

## 📊 INC-004: Kafka Broker Down

### סימפטומים
- אזעקה: "Kafka Broker Unavailable"
- Logs: `Connection refused to localhost:9092`
- הודעות לא זורמות בין Planes

### חומרה
🟡 **HIGH**

### זמן תגובה
<5 דקות

### גורמים אחראיים
- **Primary:** DevOps On-Call
- **Secondary:** Trading Desk Manager

---

### תהליך טיפול

#### שלב 1: אבחון

```bash
# בדוק Kafka status
docker-compose ps kafka

# בדוק logs
docker-compose logs kafka --tail 50

# בדוק port
nc -zv localhost 9092
```

---

#### שלב 2: restart

```bash
# אם Kafka נפל:
docker-compose restart kafka

# המתן 30 שניות
sleep 30

# ולידציה
kafka-topics.sh --list --bootstrap-server localhost:9092
```

---

#### שלב 3: verify topics

```bash
# ודא שה-topics קיימים
kafka-topics.sh --list --bootstrap-server localhost:9092

# Expected:
# - market_events
# - order_intents
# - exec_reports
```

---

### Recovery

**אם Kafka חזר:**
- ✅ המשך פעילות
- 📝 בדוק Consumer Lag

**אם לא:**
- 🛑 עצור את כל ה-Planes
- 🔧 בדוק Zookeeper
- 📞 הודע ל-DevOps

---

## ⏱️ INC-005: High Latency Spike

### סימפטומים
- Metrics: `intent_to_ack_latency_p95 > 500ms`
- Logs: `Slow order execution`
- Performance degradation

### חומרה
🟡 **HIGH**

### זמן תגובה
<10 דקות

### תהליך טיפול

#### שלב 1: אבחון

```bash
# בדוק system load
top
uptime

# בדוק network
ping -c 10 localhost

# בדוק disk I/O
iostat -x 5

# בדוק slow queries
grep "slow" logs/*.log | tail -20
```

**סיבות נפוצות:**
1. High CPU usage
2. Memory pressure
3. Disk I/O bottleneck
4. Network issues
5. Heavy computation in strategy

---

#### שלב 2: הקלה מיידית

```bash
# אם CPU גבוה:
# - הפחת signal frequency
# - הפחת portfolio size

# אם Memory גבוה:
# - Restart planes בזה אחר זה
# - Clear caches

# אם Disk I/O:
# - סובב logs
logrotate -f /etc/logrotate.d/algo-trade
```

---

## 📉 INC-006: Data Quality Failure

### סימפטומים
- אזעקה: "Data QA Gate Failed"
- Logs: `Completeness check failed`, `Freshness check failed`
- Strategy לא מקבל נתונים עדכניים

### חומרה
🟡 **HIGH**

### תהליך טיפול

```bash
# בדוק איזה QA gate נכשל
grep "QA.*fail" logs/data_plane.log

# Completeness? Freshness? Anomaly?

# בדוק data source
curl http://data-source-api/health

# אם בעיה ב-source:
# - המתן לתיקון
# - או עבור ל-backup source
```

---

## 🧮 INC-007: Covariance Matrix Singular

### סימפטומים
- Logs: `LinAlgError: Singular matrix`
- Strategy לא יכול לחשב optimization
- No orders generated

### חומרה
🟢 **MEDIUM**

### תהליך טיפול

```bash
# הפעל PSD correction
# (should be automatic in code)

# אם לא עזר:
# - הפחת מספר assets
# - הגדל regularization

# Temporary fix:
python scripts/fix_covariance.py --method ledoit_wolf
```

---

## 🚧 INC-008: Risk Limit Breach

### סימפטומים
- Logs: `Risk limit exceeded: BOX_LIM`
- Orders נדחים בגלל risk checks

### חומרה
🟢 **MEDIUM**

### תהליך טיפול

```bash
# בדוק איזה limit
grep "risk.limit" logs/*.log

# BOX_LIM? GROSS_LIM? NET_LIM?

# פתרון:
# - המתן לסגירת פוזיציות
# - או הפחת exposure ידנית
python scripts/reduce_exposure.py --target 0.7
```

---

## 🚦 INC-009: Pacing Violation

### סימפטומים
- Logs: `Pacing violation: Too many requests`
- IBKR דחה orders בגלל rate limiting

### חומרה
🟢 **MEDIUM**

### תהליך טיפול

```bash
# בדוק rate
grep "pacing" logs/*.log

# פתרון:
# - הפחת signal frequency
# - הוסף rate limiting

# Config:
# MAX_ORDERS_PER_MINUTE = 20 → 10
```

---

## 💾 INC-010: Disk Space Low

### סימפטומים
- אזעקה: "Disk space <10%"
- Logs עלולים להיכשל

### חומרה
🟢 **MEDIUM**

### תהליך טיפול

```bash
# בדוק שימוש
df -h

# מחק logs ישנים
find logs/ -name "*.log" -mtime +30 -delete

# סובב logs
logrotate -f /etc/logrotate.d/algo-trade

# backup ומחק
tar -czf backups/logs_$(date +%F).tar.gz logs/*.log
rm logs/*.log
```

---

## 📊 Incident Severity Matrix

| Severity | Definition | Response Time | Escalation |
|----------|-----------|---------------|------------|
| **🔴 CRITICAL** | System down, data loss, significant P&L impact | <1 min | Immediate: Risk Officer + CTO |
| **🟡 HIGH** | Degraded performance, partial failure | <5 min | <15 min: Risk Officer |
| **🟢 MEDIUM** | Non-critical issues, workarounds available | <15 min | <1 hour: Team Lead |
| **⚪ LOW** | Minor issues, no immediate impact | <1 hour | Next business day |

---

## 📝 Incident Logging Template

```markdown
# Incident Report: [INCIDENT_NAME]

**Incident ID:** INC-YYYYMMDD-NNN
**Date:** YYYY-MM-DD HH:MM:SS
**Severity:** [CRITICAL / HIGH / MEDIUM / LOW]
**Status:** [OPEN / IN_PROGRESS / RESOLVED / CLOSED]

## Summary
[1-2 sentence description]

## Timeline
- HH:MM - Incident detected
- HH:MM - Initial response
- HH:MM - Root cause identified
- HH:MM - Fix applied
- HH:MM - Incident resolved

## Impact
- Duration: XX minutes
- P&L Impact: $XXXX
- Orders affected: XX
- Data loss: Yes/No

## Root Cause
[Detailed explanation]

## Resolution
[What was done to fix]

## Prevention
[How to prevent in the future]

## Action Items
- [ ] Update monitoring
- [ ] Update documentation
- [ ] Update code
- [ ] Train team

**Resolved by:** [Name]
**Reviewed by:** [Risk Officer / CTO]
```

---

## 📚 מסמכים קשורים

- `RUNBOOK.md` - נהלים תפעוליים
- `ROLLBACK_PROCEDURE.md` - נוהל Rollback
- `RISK_POLICY.md` - מדיניות סיכונים
- `RACI_MATRIX.md` - מטריצת אחריות

---

**נוצר על ידי:** Claude Code (AI Assistant)
**תאריך:** 2025-11-17
**לעדכון:** לאחר כל incident מהותי

---

**End of Incident Playbook v1.0**
