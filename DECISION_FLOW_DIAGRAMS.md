# תרשימי זרימה - לוגיקת קבלת החלטות
## Decision Flow Diagrams

**תאריך:** 28 אוקטובר 2025
**גרסה:** 1.0

---

## 📊 תרשים 1: זרימה כוללת (High-Level Decision Flow)

```mermaid
graph TD
    Start[התחלה: קבלת נתוני שוק] --> DataIngestion[Data Plane: קליטת נתונים]
    DataIngestion --> QA{QA Gates<br/>Completeness<br/>Freshness<br/>NTP Sync}
    QA -->|Failed| DLQ[Dead Letter Queue]
    QA -->|Passed| Normalization[נורמליזציה]

    Normalization --> Storage[אחסון במאגר]
    Storage --> MarketEvents[פרסום Market Events]

    MarketEvents --> StrategyPlane[Strategy Plane:<br/>בניית אסטרטגיה]

    StrategyPlane --> SignalGen[ייצור אותות<br/>6 Signals]
    SignalGen --> SignalMerge[מיזוג ואורתוגונליזציה]
    SignalMerge --> RegimeDetect[זיהוי רגימת שוק<br/>Calm/Normal/Storm]

    RegimeDetect --> PortfolioOpt[אופטימיזציית פורטפוליו<br/>QP Solver]
    PortfolioOpt --> TargetWeights[Target Weights]

    TargetWeights --> RiskChecks{בדיקות סיכון<br/>Kill-Switches}
    RiskChecks -->|Kill Switch Activated| Halt[עצירת מסחר<br/>HALT MODE]
    RiskChecks -->|Reduce Exposure| Reduce[הפחתת חשיפה<br/>REDUCE MODE]
    RiskChecks -->|Normal| OrderIntents[הרכבת Order Intents]

    OrderIntents --> OrderPlane[Order Plane:<br/>ביצוע הזמנות]

    OrderPlane --> PreTradeRisk{Pre-Trade<br/>Risk Checks}
    PreTradeRisk -->|Failed| Reject[דחיית הזמנה]
    PreTradeRisk -->|Passed| Throttling[Throttling<br/>POV/ADV Caps]

    Throttling --> Execution[ביצוע הזמנה<br/>IBKR API]
    Execution --> ExecReports[קבלת דוחות ביצוע]

    ExecReports --> OnlineLearning[Online Learning:<br/>עדכון Lambda]
    OnlineLearning --> Metrics[Metrics Export<br/>Prometheus]

    Metrics --> Monitoring[Monitoring & Alerting<br/>Grafana]
    Monitoring --> End[סוף מחזור]

    End -.->|Loop| Start

    style Start fill:#90EE90
    style End fill:#FFB6C1
    style Halt fill:#FF6B6B
    style Reduce fill:#FFA07A
    style DLQ fill:#FFA500
    style Reject fill:#FF6B6B
```

---

## 🎯 תרשים 2: Signal Generation Flow (ייצור אותות)

```mermaid
graph TD
    MarketData[נתוני שוק:<br/>Prices, Returns, Volume] --> Window[חלון מתגלגל<br/>Rolling Window]

    Window --> OFI[OFI Signal:<br/>Order Flow Imbalance]
    Window --> ERN[ERN Signal:<br/>Earnings Momentum]
    Window --> VRP[VRP Signal:<br/>Volatility Risk Premium]
    Window --> POS[POS Signal:<br/>Position Sizing]
    Window --> TSX[TSX Signal:<br/>Cross-Asset]
    Window --> SIF[SIF Signal:<br/>Systematic Inflow]

    OFI --> ICCalc1[חישוב IC<br/>Information Coefficient]
    ERN --> ICCalc2[חישוב IC]
    VRP --> ICCalc3[חישוב IC]
    POS --> ICCalc4[חישוב IC]
    TSX --> ICCalc5[חישוב IC]
    SIF --> ICCalc6[חישוב IC]

    ICCalc1 --> MIS1[MIS Score:<br/>Material Information]
    ICCalc2 --> MIS2[MIS Score]
    ICCalc3 --> MIS3[MIS Score]
    ICCalc4 --> MIS4[MIS Score]
    ICCalc5 --> MIS5[MIS Score]
    ICCalc6 --> MIS6[MIS Score]

    MIS1 --> SignalMatrix[Signal Matrix<br/>N x 6]
    MIS2 --> SignalMatrix
    MIS3 --> SignalMatrix
    MIS4 --> SignalMatrix
    MIS5 --> SignalMatrix
    MIS6 --> SignalMatrix

    SignalMatrix --> Orthogonalize[אורתוגונליזציה<br/>Gram-Schmidt]
    Orthogonalize --> WeightedMerge[מיזוג משוקלל<br/>IC-Weighted]

    WeightedMerge --> MuHat[μ̂: Expected Returns<br/>per Asset]

    MuHat --> LinUCB{LinUCB Gate Selection:<br/>Contextual Bandit}
    LinUCB -->|Gate: Micro| MicroSignals[אותות Micro]
    LinUCB -->|Gate: Slow| SlowSignals[אותות Slow]
    LinUCB -->|Gate: XAsset| XAssetSignals[אותות Cross-Asset]
    LinUCB -->|Gate: Sector| SectorSignals[אותות Sector]

    MicroSignals --> FinalMu[μ Final]
    SlowSignals --> FinalMu
    XAssetSignals --> FinalMu
    SectorSignals --> FinalMu

    style MarketData fill:#E6F3FF
    style FinalMu fill:#90EE90
    style SignalMatrix fill:#FFE6CC
```

---

## ⚙️ תרשים 3: Portfolio Optimization Flow (אופטימיזציית פורטפוליו)

```mermaid
graph TD
    MuInput[μ: Expected Returns] --> QPSetup[הכנת QP Problem]
    SigmaInput[Σ: Covariance Matrix] --> QPSetup
    RegimeInput[Regime: Calm/Normal/Storm] --> QPSetup
    PrevWeights[w_prev: Previous Weights] --> QPSetup

    QPSetup --> Objective[Objective Function:<br/>max μ'w - λ*w'Σw - τ*turnover]

    Objective --> Constraints{Constraints}

    Constraints --> BoxConst[Box Constraints:<br/>-0.25 ≤ w_i ≤ 0.25]
    Constraints --> GrossConst[Gross Exposure:<br/>Σ|w_i| ≤ Gross_Lim]
    Constraints --> NetConst[Net Exposure:<br/>|Σw_i| ≤ Net_Lim]
    Constraints --> SumConst[Sum to 1:<br/>Σw_i = 1.0]

    BoxConst --> Solver[CVXPY Solver:<br/>Convex Optimization]
    GrossConst --> Solver
    NetConst --> Solver
    SumConst --> Solver

    Solver --> CheckFeasible{Solution<br/>Feasible?}
    CheckFeasible -->|No| Fallback[Fallback:<br/>Equal Weights /<br/>Previous Weights]
    CheckFeasible -->|Yes| WTarget[w_target: Target Weights]

    Fallback --> VolTargeting[Volatility Targeting:<br/>Scale to VOL_TARGET]
    WTarget --> VolTargeting

    VolTargeting --> PortVol[Portfolio Volatility:<br/>σ_p = √(w'Σw)]
    PortVol --> CheckVol{σ_p > VOL_TARGET?}

    CheckVol -->|Yes| ScaleDown[Scale Down:<br/>w *= VOL_TARGET / σ_p]
    CheckVol -->|No| Final[w_final: Final Weights]

    ScaleDown --> Final

    Final --> Output[Output to Order Plane]

    style MuInput fill:#E6F3FF
    style SigmaInput fill:#E6F3FF
    style RegimeInput fill:#FFE6CC
    style Final fill:#90EE90
    style Fallback fill:#FFA07A
```

---

## 🛡️ תרשים 4: Risk Management & Kill-Switches (ניהול סיכונים)

```mermaid
graph TD
    Start[קבלת Target Weights] --> CalcMetrics[חישוב מטריקות:<br/>PnL, Sharpe, Drawdown]

    CalcMetrics --> PnLCheck{PnL Check:<br/>Cumulative PnL < KILL_PNL?}
    PnLCheck -->|Yes| KillPnL[🚨 Kill Switch: PnL<br/>HALT Trading]
    PnLCheck -->|No| PSRCheck{PSR Check:<br/>PSR < PSR_KILL_SWITCH?}

    PSRCheck -->|Yes| KillPSR[🚨 Kill Switch: PSR<br/>HALT Trading]
    PSRCheck -->|No| DDCheck{Drawdown Check:<br/>DD > MAX_DD_KILL_SWITCH?}

    DDCheck -->|Yes| KillDD[🚨 Kill Switch: DD<br/>HALT Trading]
    DDCheck -->|No| CovDriftCheck{Covariance Drift:<br/>Blind-Spot Agent}

    CovDriftCheck -->|Drift > COV_DRIFT| ReduceExposure[⚠️ Reduce Exposure:<br/>Scale Weights * 0.5]
    CovDriftCheck -->|Normal| RegimeCheck{Regime<br/>Classification}

    RegimeCheck -->|Storm| StormMode[Storm Mode:<br/>Gross Lim = 1.0<br/>Net Lim = 0.4<br/>EWMA HL = 10]
    RegimeCheck -->|Normal| NormalMode[Normal Mode:<br/>Gross Lim = 2.0<br/>Net Lim = 0.8<br/>EWMA HL = 30]
    RegimeCheck -->|Calm| CalmMode[Calm Mode:<br/>Gross Lim = 2.5<br/>Net Lim = 1.0<br/>EWMA HL = 60]

    StormMode --> ApplyLimits[Apply Regime-Specific Limits]
    NormalMode --> ApplyLimits
    CalmMode --> ApplyLimits
    ReduceExposure --> ApplyLimits

    ApplyLimits --> FinalWeights[Final Adjusted Weights]

    KillPnL --> HaltState[HALT STATE:<br/>No Trading<br/>Alert Sent]
    KillPSR --> HaltState
    KillDD --> HaltState

    HaltState --> ManualReview[Manual Review Required]

    FinalWeights --> Proceed[Proceed to Order Plane]

    style Start fill:#E6F3FF
    style KillPnL fill:#FF6B6B
    style KillPSR fill:#FF6B6B
    style KillDD fill:#FF6B6B
    style HaltState fill:#FF6B6B
    style ReduceExposure fill:#FFA07A
    style StormMode fill:#FFA07A
    style FinalWeights fill:#90EE90
    style Proceed fill:#90EE90
```

---

## 🔄 תרשים 5: Covariance Estimation Flow (אומדן קובריאנס)

```mermaid
graph TD
    Returns[Return Matrix:<br/>T x N] --> RegimeInput{Current Regime}

    RegimeInput -->|Calm| EWMA_Calm[EWMA with HL=60]
    RegimeInput -->|Normal| EWMA_Normal[EWMA with HL=30]
    RegimeInput -->|Storm| EWMA_Storm[EWMA with HL=10]

    EWMA_Calm --> RawCov[Raw Covariance<br/>Matrix]
    EWMA_Normal --> RawCov
    EWMA_Storm --> RawCov

    RawCov --> SampleCheck{Sample Size<br/>T < 2*N?}

    SampleCheck -->|Yes| LedoitWolf[Ledoit-Wolf<br/>Shrinkage]
    SampleCheck -->|No| SkipShrinkage[Skip Shrinkage]

    LedoitWolf --> CovShrunk[Shrunk Covariance]
    SkipShrinkage --> CovShrunk

    CovShrunk --> PSDCheck{Is Positive<br/>Semi-Definite?}

    PSDCheck -->|No| NearestPSD[Nearest PSD<br/>Correction]
    PSDCheck -->|Yes| FinalCov[Final Covariance Σ]

    NearestPSD --> FinalCov

    FinalCov --> Output[Output to QP Solver]

    style Returns fill:#E6F3FF
    style EWMA_Calm fill:#B2DFDB
    style EWMA_Normal fill:#FFE082
    style EWMA_Storm fill:#FFAB91
    style FinalCov fill:#90EE90
```

---

## 🎰 תרשים 6: LinUCB Contextual Bandit (בחירת Gates)

```mermaid
graph TD
    Context[Market Context:<br/>Regime, Correlation, Vol] --> FeatureVector[Build Feature Vector<br/>x_t ∈ ℝ^d]

    FeatureVector --> Gates{Available Gates}

    Gates --> Gate1[Gate 1: Micro<br/>Fast signals]
    Gates --> Gate2[Gate 2: Slow<br/>Long-term signals]
    Gates --> Gate3[Gate 3: XAsset<br/>Cross-asset signals]
    Gates --> Gate4[Gate 4: Sector<br/>Sector rotation]

    Gate1 --> UCB1[Compute UCB:<br/>θ₁'x + α√(x'A₁⁻¹x)]
    Gate2 --> UCB2[Compute UCB:<br/>θ₂'x + α√(x'A₂⁻¹x)]
    Gate3 --> UCB3[Compute UCB:<br/>θ₃'x + α√(x'A₃⁻¹x)]
    Gate4 --> UCB4[Compute UCB:<br/>θ₄'x + α√(x'A₄⁻¹x)]

    UCB1 --> SelectMax[Select Gate:<br/>arg max UCB_i]
    UCB2 --> SelectMax
    UCB3 --> SelectMax
    UCB4 --> SelectMax

    SelectMax --> SelectedGate[Selected Gate<br/>with highest UCB]

    SelectedGate --> UseSignals[Use Signals<br/>from Selected Gate]

    UseSignals --> Observe[Observe Reward:<br/>r_t = PnL / Vol]

    Observe --> UpdateParams[Update Parameters:<br/>A_i ← A_i + xx'<br/>b_i ← b_i + r·x<br/>θ_i = A_i⁻¹b_i]

    UpdateParams --> NextPeriod[Next Time Period]
    NextPeriod -.->|Loop| Context

    style Context fill:#E6F3FF
    style SelectMax fill:#FFE6CC
    style SelectedGate fill:#90EE90
    style UpdateParams fill:#B2DFDB
```

---

## 📈 תרשים 7: Validation & Overfitting Detection (ולידציה)

```mermaid
graph TD
    Strategy[Strategy Parameters] --> HistData[Historical Data:<br/>T days]

    HistData --> CSCV[CSCV Split:<br/>M=16 blocks]

    CSCV --> Train1[Train Block 1]
    CSCV --> Train2[Train Block 2]
    CSCV --> TrainM[Train Block M]

    Train1 --> Test1[Test Block 1]
    Train2 --> Test2[Test Block 2]
    TrainM --> TestM[Test Block M]

    Test1 --> Sharpe1[Sharpe Ratio 1]
    Test2 --> Sharpe2[Sharpe Ratio 2]
    TestM --> SharpeM[Sharpe Ratio M]

    Sharpe1 --> CalcPSR[Calculate PSR:<br/>Probabilistic Sharpe]
    Sharpe2 --> CalcPSR
    SharpeM --> CalcPSR

    CalcPSR --> PSRValue[PSR Value]

    PSRValue --> PSRCheck{PSR > 0.95?}

    PSRCheck -->|Yes| CalcDSR[Calculate DSR:<br/>Deflated Sharpe]
    PSRCheck -->|No| Reject[Reject Strategy:<br/>Not Statistically Significant]

    CalcDSR --> DSRValue[DSR Value]

    DSRValue --> DSRCheck{DSR > 1.0?}

    DSRCheck -->|Yes| CalcPBO[Calculate PBO:<br/>Prob. Backtest Overfitting]
    DSRCheck -->|No| Reject

    CalcPBO --> PBOValue[PBO Value]

    PBOValue --> PBOCheck{PBO < 0.5?}

    PBOCheck -->|Yes| Accept[Accept Strategy:<br/>Robust Performance]
    PBOCheck -->|No| Overfit[Reject Strategy:<br/>Likely Overfitted]

    Accept --> Deploy[Deploy to Paper Trading]

    style HistData fill:#E6F3FF
    style Accept fill:#90EE90
    style Reject fill:#FF6B6B
    style Overfit fill:#FFA500
    style Deploy fill:#90EE90
```

---

## 📊 תרשים 8: Execution & Online Learning (ביצוע ולמידה)

```mermaid
graph TD
    OrderIntent[Order Intent:<br/>Asset, Qty, Direction] --> PreTradeRisk{Pre-Trade<br/>Risk Checks}

    PreTradeRisk -->|Failed| RejectOrder[Reject Order:<br/>Log to Metrics]
    PreTradeRisk -->|Passed| CheckPOV{Exceeds POV Cap?<br/>Qty > POV_CAP * Volume}

    CheckPOV -->|Yes| DownScale[Downscale Quantity:<br/>Qty = POV_CAP * Volume]
    CheckPOV -->|No| CheckADV{Exceeds ADV Cap?<br/>Qty > ADV_CAP * ADV}

    DownScale --> CheckADV

    CheckADV -->|Yes| DownScaleADV[Downscale Quantity:<br/>Qty = ADV_CAP * ADV]
    CheckADV -->|No| EstimateCost[Estimate Transaction Cost:<br/>TC = λ * |Qty|^β]

    DownScaleADV --> EstimateCost

    EstimateCost --> PlaceOrder[Place Order:<br/>IBKR API]

    PlaceOrder --> WaitFill[Wait for Fill]

    WaitFill --> ExecReport[Execution Report:<br/>Fill Price, Qty, Time]

    ExecReport --> CalcSlippage[Calculate Realized Slippage:<br/>S = |Fill Price - Expected|]

    CalcSlippage --> UpdateLambda[Update Lambda:<br/>λ_new = ρ*λ_old + (1-ρ)*S/|Qty|^β]

    UpdateLambda --> StoreMetrics[Store Metrics:<br/>Prometheus]

    StoreMetrics --> NextOrder[Ready for Next Order]

    RejectOrder --> AlertRisk[Alert: Risk Violation]

    style OrderIntent fill:#E6F3FF
    style PlaceOrder fill:#FFE6CC
    style UpdateLambda fill:#B2DFDB
    style NextOrder fill:#90EE90
    style RejectOrder fill:#FF6B6B
```

---

## 🏗️ תרשים 9: Architecture - 3 Planes (ארכיטקטורה)

```mermaid
graph TD
    subgraph DataPlane[Data Plane]
        IBKR_RT[IBKR Real-Time<br/>Market Data] --> RawData[Raw Market Data]
        IBKR_Hist[IBKR Historical<br/>Data] --> RawData

        RawData --> Pacing[Pacing Manager:<br/>Rate Limiting]
        Pacing --> Normalize[Normalization]

        Normalize --> QA_Comp[QA: Completeness Gate]
        QA_Comp --> QA_Fresh[QA: Freshness Monitor]
        QA_Fresh --> QA_NTP[QA: NTP Guard]

        QA_NTP --> Storage[Storage: Time-Series DB]
        Storage --> Kafka_Market[Kafka: market_events]
    end

    subgraph StrategyPlane[Strategy Plane]
        Kafka_Market --> Strategy[Strategy Loop]

        Strategy --> BuildContext[Build Context:<br/>Rolling Windows]
        BuildContext --> GenSignals[Generate Signals:<br/>6 Strategies]
        GenSignals --> MergeSignals[Merge & Orthogonalize]
        MergeSignals --> DetectRegime[Detect Regime]
        DetectRegime --> SolveQP[Solve QP:<br/>Target Weights]
        SolveQP --> AssembleIntents[Assemble Order Intents]

        AssembleIntents --> Kafka_Intents[Kafka: order_intents]
    end

    subgraph OrderPlane[Order Plane]
        Kafka_Intents --> OrderOrch[Order Orchestrator]

        OrderOrch --> RiskCheck[Pre-Trade Risk Checks]
        RiskCheck --> Throttle[Throttling:<br/>POV/ADV Caps]
        Throttle --> IBKRExec[IBKR Execution Client]

        IBKRExec --> ExecAPI[IBKR API:<br/>Place Orders]
        ExecAPI --> ExecReports[Execution Reports]

        ExecReports --> Kafka_Exec[Kafka: exec_reports]
        Kafka_Exec --> Learning[Online Learning:<br/>Update Lambda]
    end

    subgraph Monitoring[Monitoring & Observability]
        Metrics[Prometheus Metrics] --> Grafana[Grafana Dashboards]
        Logs[Centralized Logs] --> ELK[ELK Stack / Loki]
        Traces[Distributed Traces] --> Jaeger[Jaeger / Tempo]
    end

    DataPlane -.->|Metrics| Metrics
    StrategyPlane -.->|Metrics| Metrics
    OrderPlane -.->|Metrics| Metrics

    DataPlane -.->|Logs| Logs
    StrategyPlane -.->|Logs| Logs
    OrderPlane -.->|Logs| Logs

    style DataPlane fill:#E3F2FD
    style StrategyPlane fill:#FFF3E0
    style OrderPlane fill:#F3E5F5
    style Monitoring fill:#E8F5E9
```

---

## 📝 הסברים נוספים

### סמלים בתרשימים:
- 🟢 **ירוק**: מצב תקין, המשך זרימה
- 🟡 **צהוב**: אזהרה, הפחתת חשיפה
- 🔴 **אדום**: עצירה, Kill-Switch
- 🔵 **כחול**: קלט נתונים
- 🟠 **כתום**: עיבוד ביניים

### מונחים מרכזיים:
- **IC (Information Coefficient)**: מתאם בין אות לתשואות עתידיות
- **MIS (Material Information Score)**: ציון חשיבות האות
- **QP (Quadratic Programming)**: אופטימיזציה קמורה
- **PSR (Probabilistic Sharpe Ratio)**: הסתברות ש-Sharpe > 0
- **DSR (Deflated Sharpe Ratio)**: Sharpe מתוקן למבחנים מרובים
- **PBO (Probability of Backtest Overfitting)**: הסתברות ל-overfitting
- **UCB (Upper Confidence Bound)**: גבול בטחון עליון (LinUCB)
- **EWMA (Exponentially Weighted Moving Average)**: ממוצע משוקלל מעריכי
- **PSD (Positive Semi-Definite)**: מטריצה חיובית-חצי-מוגדרת

---

## 🎯 נתיבי החלטה קריטיים

### נתיב 1: מצב תקין (Normal Flow)
```
נתונים → QA → אותות → אופטימיזציה → בדיקות סיכון [OK] → ביצוע → למידה
```

### נתיב 2: Kill-Switch (Emergency Halt)
```
נתונים → ... → בדיקות סיכון [FAILED] → HALT → התראה → בדיקה ידנית
```

### נתיב 3: Regime Storm (High Volatility)
```
נתונים → זיהוי רגימה [Storm] → הפחתת מגבלות → EWMA מהיר → המשך זהיר
```

### נתיב 4: Blind-Spot Detection (Covariance Drift)
```
נתונים → זיהוי סטייה בקובריאנס → הפחתת חשיפה ב-50% → המשך
```

---

**נוצר על ידי:** Claude Code (AI Assistant)
**תאריך:** 28 אוקטובר 2025
**לשימוש:** צוות הפיתוח, מנהלים, stakeholders

---

## 📌 הערות לקריאה

1. **תרשימי Mermaid** ניתנים לצפייה ב-GitHub, GitLab, Obsidian, ו-VS Code (עם extension)
2. לצפייה מקוונת: [Mermaid Live Editor](https://mermaid.live)
3. ניתן לייצא לתמונות PNG/SVG דרך Mermaid CLI
4. התרשימים מעודכנים נכון למצב הקוד ב-28 אוקטובר 2025

---

## 🔄 עדכונים עתידיים

כאשר הקוד משתנה, יש לעדכן תרשימים אלה:
- [ ] הוספת Multi-Broker Support (Alpaca, Tradier)
- [ ] הוספת Real-Time News Sentiment Analysis
- [ ] הוספת Machine Learning Signals (Deep Learning)
- [ ] הוספת Multi-Currency Support
- [ ] הוספת Options & Derivatives Strategies
