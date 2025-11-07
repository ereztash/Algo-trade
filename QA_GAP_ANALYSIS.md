# מטריצת ניתוח פערים - QA Readiness
## Gap Analysis Matrix: As-Is / To-Be / Gap / Owner / Due

**תאריך:** 2025-11-07
**Branch:** claude/qa-readiness-testing-framework-011CUtjXHuN4ySpCupVkPfAx
**מטרה:** העלאת המערכת ל-QA מוכנות מלאה

---

## 📊 מטריצת פערים מרכזית

| תחום | As-Is (מצב נוכחי) | To-Be (מצב יעד) | Gap (פער) | Owner | Due Date |
|------|-----------------|----------------|-----------|-------|----------|
| **Test Coverage** | 0% - קבצי test ריקים | ≥80% עם unit/integration/E2E | -80% ❌ | QA Lead | 2025-11-28 |
| **Property-Based Testing** | לא קיים | Hypothesis עם Properties למודולי ליבה | -100% ❌ | QA Lead | 2025-11-21 |
| **Metamorphic Testing** | לא קיים | MR-pass-rate ≥90% | -100% ❌ | QA Lead | 2025-11-21 |
| **Chaos/Resilience** | לא קיים | Recovery ≤30s, Chaos Scorecard | -100% ❌ | QA Lead | 2025-11-28 |
| **CI/CD Pipeline** | לא קיים | GitHub Actions עם Gates | -100% ❌ | DevOps | 2025-11-14 |
| **Coverage Gates** | לא קיים | Block merge אם coverage <80% | -100% ❌ | DevOps | 2025-11-14 |
| **Fixtures** | לא קיימים | Deterministic fixtures + golden files | -100% ❌ | QA Lead | 2025-11-14 |
| **Contracts/Schemas** | כמעט ריקים | JSON/Avro Schemas מלאים + validation | -90% ❌ | Lead Dev | 2025-11-21 |
| **E2E Tests** | לא קיימים | E2E מלא עם IBKR-Mock + Golden-Traces | -100% ❌ | QA Lead | 2025-11-28 |
| **Performance Tests** | לא נמדד | p95 Intent→Ack ≤50ms | N/A ⚠️ | QA Lead | 2025-12-05 |
| **Observability** | 10% - stub בלבד | /metrics + Grafana + Structured Logging | -90% ❌ | SRE | 2025-11-28 |
| **Governance Gate** | לא קיים | CI gate לשינויי risk params | -100% ❌ | Risk Officer | 2025-11-28 |

---

## 🎯 Definition of Done - QA Readiness

### KPI ראשיים
1. **Test Coverage** ≥ 80% (unit + integration)
2. **MR-pass-rate** (Metamorphic Relations) ≥ 90%
3. **Chaos Recovery Time** ≤ 30 seconds
4. **p95 Latency** Intent→Ack ≤ 50ms
5. **Flaky Test Rate** ≤ 2%
6. **CI Success Rate** ≥ 95%

### תרחישי E2E (סט מינימום)
1. ✅ End-to-End: Data→Signals→Portfolio→OrderIntent→Execution
2. ✅ Kill-Switch Activation: PnL Drop -5%
3. ✅ Regime Detection: Storm Mode Transition
4. ✅ Order Lifecycle: Place→Ack→Partial→Fill→Report
5. ✅ Recovery: IBKR Disconnect→Reconnect→Resume
6. ✅ Chaos: Network Timeout→Backoff→Retry→Success

### Stop-Rules (תנאי עצירה)
1. 🛑 **PSR < 0.20** → Kill-Switch activated
2. 🛑 **Max Drawdown > 15%** → Halt trading
3. 🛑 **Covariance Drift > threshold** → Reduce exposure
4. 🛑 **Data Freshness > 1s** → Fallback to cache
5. 🛑 **3 consecutive test failures** → Block deployment

---

## 📋 פירוט פערים לפי שלב

### שלב 0: Intake ובסיס

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| מסמכי בסיס | ✅ קיימים | ✅ נקראו | 0% | - |
| Gap Matrix | ❌ לא קיים | ✅ טבלה מפורטת | -100% | ✅ נוצר במסמך זה |
| Definition of Done | ❌ לא מוגדר | ✅ KPIs + E2E scenarios | -100% | ✅ מוגדר לעיל |
| QA_PLAN.md | ❌ לא קיים | ✅ מסמך ארכיטקטורה | -100% | 🔄 ייווצר הבא |

---

### שלב 1: תשתיות CI/CD ו-Determinism

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| GitHub Actions | ❌ לא קיים | ✅ .github/workflows/test.yml | -100% | צור workflow |
| Lint + Type-check | ❌ לא רץ | ✅ black, mypy, flake8 | -100% | הוסף jobs |
| Test Execution | ❌ לא רץ | ✅ pytest עם coverage | -100% | הוסף job |
| Coverage Report | ❌ לא קיים | ✅ HTML + badge | -100% | pytest-cov |
| Coverage Gate | ❌ לא קיים | ✅ min 80%, block merge | -100% | צור gate |
| Artifacts | ❌ לא נשמרים | ✅ reports + logs | -100% | upload-artifact |
| Seeds | ❌ לא נקבעו | ✅ קבועים בfixtures | -100% | הגדר SEED=42 |
| Fixtures | ❌ לא קיימים | ✅ fixtures/ dir | -100% | צור מבנה |
| Golden Files | ❌ לא קיימים | ✅ golden/ dir | -100% | צור מבנה |
| Dependency Lock | ⚠️ requirements.txt | ✅ poetry lock או pip-compile | -50% | נעל גרסאות |

**Owner:** DevOps + QA Lead
**Due:** 2025-11-14

---

### שלב 2: Property-Based Testing

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| Hypothesis Setup | ❌ לא מותקן | ✅ hypothesis>=6.0 | -100% | pip install |
| PBT: Signals | ❌ לא קיים | ✅ Properties לכל 6 signals | -100% | כתוב tests |
| PBT: QP Solver | ❌ לא קיים | ✅ Constraints invariants | -100% | כתוב tests |
| PBT: Risk | ❌ לא קיים | ✅ Kill-Switch properties | -100% | כתוב tests |
| PBT: Portfolio | ❌ לא קיים | ✅ Weight sum, bounds | -100% | כתוב tests |
| Shrinking | ❌ לא מופעל | ✅ אוטומטי עם Hypothesis | -100% | הפעל |
| Property Docs | ❌ לא קיים | ✅ PROPERTY_GUIDE.md | -100% | צור מסמך |
| CI Integration | ❌ לא רץ | ✅ רץ בכל PR | -100% | הוסף ל-workflow |

**Properties מרכזיים:**
1. **QP Solver:** סכום משקולות = 1±ε, אי-חציית box constraints
2. **Risk:** VaR/MaxDD בתוך מגבלות, monotonicity
3. **Signals:** קורלציה עם returns, normalization
4. **Portfolio:** Gross/Net exposure בגבולות

**Owner:** QA Lead
**Due:** 2025-11-21

---

### שלב 3: Metamorphic Testing

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| MT Framework | ❌ לא קיים | ✅ tests/metamorphic/ | -100% | צור תיקייה |
| MR: Scaling | ❌ לא קיים | ✅ Linear price scaling | -100% | implement |
| MR: Time Shift | ❌ לא קיים | ✅ Temporal consistency | -100% | implement |
| MR: Noise Injection | ❌ לא קיים | ✅ Symmetric noise stability | -100% | implement |
| MR: Tail Zeroing | ❌ לא קיים | ✅ Regime stability | -100% | implement |
| MR-pass-rate | ❌ לא נמדד | ✅ ≥90% | -100% | מדוד |
| CI Integration | ❌ לא רץ | ✅ רץ בכל PR | -100% | הוסף ל-workflow |
| MT Guide | ❌ לא קיים | ✅ תיעוד MRs | -100% | צור מסמך |

**Metamorphic Relations:**
1. **MR1-Scaling:** P' = α·P → Signal(P') ≈ Signal(P) (up to normalization)
2. **MR2-TimeShift:** Data shifted by Δt → Decision consistency within window
3. **MR3-Noise:** Small symmetric noise → Decision stability
4. **MR4-Tail:** Zeroing tail series → Regime stability

**Owner:** QA Lead
**Due:** 2025-11-21

---

### שלב 4: Integration & Contracts

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| Schema: BarEvent | ⚠️ כמעט ריק | ✅ JSON Schema מלא | -90% | השלם schema |
| Schema: OrderIntent | ⚠️ כמעט ריק | ✅ JSON Schema מלא | -90% | השלם schema |
| Schema: ExecutionReport | ⚠️ כמעט ריק | ✅ JSON Schema מלא | -90% | השלם schema |
| Schema Validation | ❌ לא רץ | ✅ validate בCI | -100% | הוסף tests |
| Contract Tests | ❌ לא קיימים | ✅ tests/contracts/ | -100% | צור tests |
| Schema Diff | ❌ לא רץ | ✅ Block breaking changes | -100% | הוסף gate |
| Avro Support | ❌ לא קיים | ✅ Optional Avro schemas | -100% | אופציונלי |

**Owner:** Lead Dev
**Due:** 2025-11-21

---

### שלב 5: E2E עם Broker-Mock

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| IBKR Mock | ❌ לא קיים | ✅ Mock עם state machine | -100% | בנה Mock |
| State: Ack | ❌ | ✅ Order acknowledged | -100% | implement |
| State: Partial | ❌ | ✅ Partial fill | -100% | implement |
| State: Cancel | ❌ | ✅ Order canceled | -100% | implement |
| State: Reject | ❌ | ✅ Order rejected | -100% | implement |
| State: Timeout | ❌ | ✅ Timeout simulation | -100% | implement |
| State: Disconnect | ❌ | ✅ Connection lost | -100% | implement |
| State: Recovery | ❌ | ✅ Reconnect + resume | -100% | implement |
| Golden Traces | ❌ לא קיימים | ✅ golden/ traces | -100% | צור traces |
| E2E Tests | ❌ לא קיימים | ✅ 6 תרחישים | -100% | כתוב tests |
| Latency Metrics | ❌ לא נמדד | ✅ Intent→Ack p95 | -100% | מדוד |
| Fill Ratio | ❌ לא נמדד | ✅ % מילוי הזמנות | -100% | מדוד |

**Owner:** QA Lead + Lead Dev
**Due:** 2025-11-28

---

### שלב 6: Chaos/Resilience Tests

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| Chaos Framework | ❌ לא קיים | ✅ tests/chaos/ | -100% | צור תיקייה |
| Network Disconnect | ❌ | ✅ Simulate network loss | -100% | implement |
| Latency Injection | ❌ | ✅ Slow response simulation | -100% | implement |
| Exception Injection | ❌ | ✅ Controlled exceptions | -100% | implement |
| Message Loss | ❌ | ✅ Bus message drop | -100% | implement |
| Backoff Test | ❌ | ✅ Exponential backoff | -100% | verify |
| Recovery Test | ❌ | ✅ Recovery <30s | -100% | verify |
| Queue Limits | ❌ | ✅ Queue overflow handling | -100% | verify |
| Safe Shutdown | ❌ | ✅ Graceful degradation | -100% | verify |
| Chaos Scorecard | ❌ לא קיים | ✅ Report with scores | -100% | צור |

**Chaos Scenarios:**
1. Network disconnect (3s, 10s, 30s)
2. High latency (500ms, 2s, 5s)
3. Memory pressure (80%, 95%)
4. CPU saturation (90%, 100%)
5. Message loss (5%, 20%)
6. Cascading failures

**Owner:** QA Lead
**Due:** 2025-11-28

---

### שלב 7: Performance & Observability

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| /metrics Endpoint | ⚠️ stub | ✅ Prometheus-compatible | -90% | השלם |
| Structured Logging | ⚠️ print() | ✅ JSON + traceId | -90% | השלם |
| Grafana Dashboards | ❌ לא קיימים | ✅ 4 dashboards (JSON) | -100% | צור |
| Dashboard: System | ❌ | ✅ CPU, Memory, Latency | -100% | צור |
| Dashboard: Strategy | ❌ | ✅ PnL, Sharpe, DD | -100% | צור |
| Dashboard: Risk | ❌ | ✅ Exposure, VaR, Regime | -100% | צור |
| Dashboard: Data | ❌ | ✅ Freshness, Completeness | -100% | צור |
| Alerts | ❌ לא קיימים | ✅ 10+ rules | -100% | צור |
| SLO Definition | ⚠️ חלקי | ✅ Latency, Availability, Errors | -80% | השלם |
| P50/P95 Tracking | ❌ | ✅ מעקב רציף | -100% | implement |

**Metrics רשימה:**
- `intent_to_ack_latency_ms` (p50, p95, p99)
- `signal_computation_duration_ms`
- `qp_solver_duration_ms`
- `order_fill_ratio`
- `error_rate` (per component)
- `throughput_msg_per_sec`
- `pnl_cumulative`
- `sharpe_ratio_rolling_30d`
- `max_drawdown_current`
- `regime_state` (Calm/Normal/Storm)

**Owner:** SRE + QA Lead
**Due:** 2025-11-28

---

### שלב 8: Governance & Risk Gates

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| Governance Gate | ❌ לא קיים | ✅ CI gate לשינויי risk | -100% | implement |
| Risk Policy | ❌ לא חתום | ✅ RiskPolicy.pdf חתום | -100% | צור ואשר |
| Parameter Change | ❌ לא נשלט | ✅ דורש אישור | -100% | הוסף gate |
| Schema Freshness | ❌ לא נבדק | ✅ עדכניות סכמות | -100% | הוסף gate |
| PRE_LIVE_CHECKLIST | ❌ לא קיים | ✅ 20+ items | -100% | צור |
| RUNBOOK | ❌ לא קיים | ✅ Operational procedures | -100% | צור |
| Change Log | ❌ לא קיים | ✅ CHANGELOG.md | -100% | צור |
| Version Tagging | ❌ לא קיים | ✅ Semantic versioning | -100% | הוסף |

**Governance Gate Rules:**
1. שינוי KILL_PNL, MAX_DD, BOX_LIM → דורש approval
2. שינוי schema breaking → חוסם merge
3. כל הבדיקות (PBT/MT/Chaos) ירוקות → חובה
4. Coverage ≥80% → חובה
5. No high-severity vulnerabilities → חובה

**Owner:** Risk Officer + DevOps
**Due:** 2025-11-28

---

### שלב 9: Delivery

| מטרה | As-Is | To-Be | Gap | Action |
|------|-------|-------|-----|--------|
| QA_PLAN.md | ❌ | ✅ ארכיטקטורה מלאה | -100% | צור |
| tests/ Directory | ⚠️ ריק | ✅ מאות tests | -100% | מלא |
| .github/workflows/ | ❌ | ✅ CI/CD pipelines | -100% | צור |
| contracts/ | ⚠️ כמעט ריק | ✅ schemas מלאים | -90% | השלם |
| fixtures/ | ❌ | ✅ deterministic data | -100% | צור |
| golden/ | ❌ | ✅ golden traces | -100% | צור |
| grafana/ | ❌ | ✅ dashboard JSONs | -100% | צור |
| RUNBOOK.md | ❌ | ✅ operational guide | -100% | צור |
| Coverage Report | ❌ | ✅ HTML report | -100% | צור |
| Chaos Report | ❌ | ✅ Scorecard | -100% | צור |
| QA_EXECUTION_SUMMARY | ❌ | ✅ KPIs summary | -100% | צור |

**Owner:** QA Lead
**Due:** 2025-12-05

---

## 📈 Timeline Summary

| שלב | זמן משוערך | תלויות | קריטיות |
|------|-----------|---------|----------|
| 0. Intake | ✅ הושלם | - | ⭐⭐⭐ |
| 1. CI/CD + Determinism | 2 ימים | - | ⭐⭐⭐ |
| 2. Property-Based Testing | 3 ימים | שלב 1 | ⭐⭐⭐ |
| 3. Metamorphic Testing | 3 ימים | שלב 1 | ⭐⭐⭐ |
| 4. Contracts | 2 ימים | - | ⭐⭐ |
| 5. E2E + Mock | 4 ימים | שלבים 1-4 | ⭐⭐⭐ |
| 6. Chaos/Resilience | 3 ימים | שלב 5 | ⭐⭐⭐ |
| 7. Observability | 3 ימים | - | ⭐⭐ |
| 8. Governance | 2 ימים | כל השלבים | ⭐⭐⭐ |
| 9. Delivery | 1 יום | כל השלבים | ⭐⭐⭐ |

**סה"כ:** ~23 ימי עבודה (≈4-5 שבועות בקצב נורמלי)

---

## 🎯 קריטריוני הצלחה (Exit Criteria)

### חובה (Must-Have)
- ✅ Coverage ≥ 80%
- ✅ MR-pass-rate ≥ 90%
- ✅ Chaos recovery ≤ 30s
- ✅ p95 Intent→Ack ≤ 50ms (target TBD)
- ✅ כל Gates ירוקים
- ✅ כל Contracts עקביים
- ✅ 0 high-severity vulnerabilities

### רצוי (Nice-to-Have)
- 📊 Coverage ≥ 90%
- 📊 Flaky rate ≤ 1%
- 📊 CI runtime ≤ 10min
- 📊 Performance regression tests

---

## 🔄 לולאת שיפור רקורסיבית (Auto-Refine)

**תהליך:**
1. בכל Merge: נתח כשלי PBT/MT/Chaos
2. הפק Top-3 Fixes מתוך הניתוח
3. עדכן Properties/MRs/Failure-budgets
4. בצע hardening ממוקד
5. Re-score KPIs
6. חזור על התהליך עד שראשי-המדדים ≥ ספים ב-2 רצפים

**Threshold Values:**
- Coverage: 80% → 85% → 90%
- MR-pass-rate: 90% → 95%
- Chaos-recovery: 30s → 20s → 15s

---

## 📞 Stakeholders & Ownership

| תפקיד | אחריות | KPIs |
|-------|--------|------|
| **QA Lead** | Testing strategy, PBT/MT/Chaos, E2E | Coverage, MR-pass-rate |
| **DevOps** | CI/CD, Gates, Artifacts | CI success rate, build time |
| **Lead Dev** | Contracts, Mock, Integration | Schema coverage |
| **SRE** | Observability, Metrics, Dashboards | SLO compliance |
| **Risk Officer** | Governance, Risk Policy, Approvals | Policy compliance |

---

**נוצר על ידי:** Claude Code (AI Assistant)
**תאריך:** 2025-11-07
**Branch:** claude/qa-readiness-testing-framework-011CUtjXHuN4ySpCupVkPfAx
**לאישור:** Project Lead / CTO
