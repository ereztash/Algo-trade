# AlgoX Hybrid MVP - ארכיטקטורה

## גישה: Best of Both Worlds

משלב את הקוד העובד של Algo-trade עם האסטרטגיות המתקדמות של AlgoX.

---

## 🏗️ ארכיטקטורה כללית

```
┌─────────────────────────────────────────────────────────┐
│                    AlgoX Hybrid MVP                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────┐  ┌────────────────┐               │
│  │  Data Layer    │  │  Signal Layer  │               │
│  │                │  │                │               │
│  │ • IBKR API     │→ │ • Structural   │               │
│  │ • FDA Data     │  │ • Event-Driven │               │
│  │ • Market Data  │  │ • Ricci Curve  │               │
│  └────────────────┘  └────────────────┘               │
│           ↓                    ↓                        │
│  ┌─────────────────────────────────────┐               │
│  │      Strategy Orchestrator           │               │
│  │                                      │               │
│  │  • WFO Protocol (8 steps)           │               │
│  │  • LinUCB Gate Selection            │               │
│  │  • Regime Detection                 │               │
│  └─────────────────────────────────────┘               │
│           ↓                                             │
│  ┌─────────────────────────────────────┐               │
│  │    Portfolio Optimization            │               │
│  │                                      │               │
│  │  • QP Solver (existing)             │               │
│  │  • Risk Management                  │               │
│  │  • Position Sizing                  │               │
│  └─────────────────────────────────────┘               │
│           ↓                                             │
│  ┌─────────────────────────────────────┐               │
│  │      Execution Layer                 │               │
│  │                                      │               │
│  │  • IBKR Order Execution             │               │
│  │  • Slippage Tracking                │               │
│  │  • Fill Reports                     │               │
│  └─────────────────────────────────────┘               │
│           ↓                                             │
│  ┌─────────────────────────────────────┐               │
│  │    Monitoring & Analytics            │               │
│  │                                      │               │
│  │  • Performance Metrics              │               │
│  │  • Risk Metrics                     │               │
│  │  • Kill-Switches                    │               │
│  └─────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 מבנה קבצים חדש

```
algo-x-mvp/
├── algox/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── ibkr_client.py          # IBKR API wrapper
│   │   ├── fda_scraper.py          # FDA calendar scraper
│   │   └── market_data.py          # Market data utilities
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── structural.py           # Structural Arbitrage (REMX→URNM→QTUM)
│   │   ├── event_driven.py         # Event-Driven (FDA)
│   │   ├── ricci_curvature.py      # Forman-Ricci Curvature
│   │   └── legacy.py               # Original 6 signals (fallback)
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # Main strategy orchestrator
│   │   ├── wfo.py                  # Walk-Forward Optimization
│   │   ├── regime.py               # Regime detection
│   │   └── gates.py                # LinUCB gate selection
│   ├── portfolio/
│   │   ├── __init__.py
│   │   ├── optimizer.py            # QP optimization (from Algo-trade)
│   │   ├── risk.py                 # Risk management
│   │   └── sizing.py               # Position sizing
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── ibkr_executor.py        # IBKR order execution
│   │   └── slippage.py             # Slippage tracking
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── metrics.py              # Performance metrics
│   │   └── killswitch.py           # Kill-switches
│   └── utils/
│       ├── __init__.py
│       ├── validation.py           # CSCV, PSR, DSR
│       └── logging.py              # Structured logging
├── config/
│   ├── mvp_config.yaml             # MVP configuration
│   └── symbols.yaml                # Trading symbols
├── tests/
│   └── (unit tests)
├── notebooks/
│   ├── 01_research_structural.ipynb
│   ├── 02_research_events.ipynb
│   └── 03_backtest.ipynb
├── scripts/
│   ├── download_data.py
│   └── run_backtest.py
├── requirements_mvp.txt
└── README_MVP.md
```

---

## 🎯 3 אסטרטגיות ליבה

### 1. Structural Arbitrage

**מטרה**: ניצול קשרי lead-lag בין ETFs קשורים

**שרשרת סיבתית**:
```
REMX (Rare Earth Metals) → URNM (Uranium Miners) → QTUM (Quantum Computing)
```

**הגיון**:
- REMX מכיל מתכות אדמה נדירות (REE) הנדרשות לייצור מגנטים
- URNM תלוי באנרגיה גרעינית (צורך גבוה ב-REE)
- QTUM תלוי בחומרה קוונטית (צורך ב-REE ואנרגיה)

**אות**:
- חישוב Granger Causality: REMX → URNM → QTUM
- מעקב אחר lead time (בדרך כלל 1-3 ימים)
- זיהוי breakouts ב-REMX → פוזיציה ב-URNM/QTUM

**Position Sizing**: 10-15% per ETF

---

### 2. Event-Driven (FDA Approvals)

**מטרה**: ניצול אירועי FDA לביוטק

**אות**:
- מעקב אחר FDA calendar (PDUFA dates)
- Entry: T-5 days (לפני החלטה)
- **Exit: T-2 days** (למניעת סיכון בינארי)

**סינון**:
- רק Phase III+ (success rate > 60%)
- Market cap > $500M
- Volume > $5M daily

**Position Sizing**: 10% per position, max 2 concurrent

---

### 3. Ricci Curvature (Early Warning System)

**מטרה**: זיהוי שבריריות מערכתית לפני קריסה

**חישוב**:
- בניית גרף קורלציות (nodes = stocks, edges = correlation)
- חישוב Forman-Ricci Curvature לכל edge
- זיהוי negative curvature (סימן לשבריריות)

**אות**:
- כאשר avg(Ricci) < -0.2 → צמצום חשיפה
- כאשר avg(Ricci) > 0.1 → הגדלת חשיפה

**שימוש**: Risk filter, לא אות עצמאי

---

## 📊 Walk-Forward Optimization (8 שלבים)

```python
# פרוטוקול WFO מלא

Step 1: Data Split (chronological)
  - Training: 12 months
  - Validation: 3 months
  - Test: 3 months

Step 2: Feature Engineering (on training only)
  - Granger causality tests
  - Ricci curvature computation
  - Event calendar alignment

Step 3: Normalization (fit on training)
  - Z-score parameters
  - Covariance matrix

Step 4: Model Training
  - Optimize hyperparameters (Bayesian)
  - Train on training set
  - Validate on validation set

Step 5: Out-of-Sample Testing
  - Test on test set (never seen)
  - Calculate OOS metrics

Step 6: Statistical Validation
  - CSCV (M=8)
  - PSR, DSR
  - WFE calculation

Step 7: Roll Forward
  - Shift window by 3 months
  - Repeat Steps 1-6

Step 8: Aggregate Results
  - Calculate overall WFE
  - Decision: Deploy if WFE > 60%
```

---

## 💰 Risk Management

### Position Sizing Rules

```yaml
MAX_POSITION_SIZE: 0.15        # 15% per position
MAX_GROSS_EXPOSURE: 0.50       # 50% total capital
MAX_CONCURRENT_POSITIONS: 5
MAX_SECTOR_EXPOSURE: 0.30      # 30% per sector

BIOTECH_MAX: 0.10              # 10% for event-driven
ETF_MAX: 0.15                  # 15% for structural
```

### Kill-Switches

```yaml
CIRCUIT_BREAKERS:
  MAX_DD: 0.20                 # Stop if DD > 20%
  MIN_SHARPE: 0.5              # Stop if SR < 0.5 for 3 months
  MAX_DAILY_LOSS: 0.03         # Stop if daily loss > 3%
  PSR_THRESHOLD: 0.2           # Stop if PSR < 0.2
```

---

## 📈 Performance Targets (12 months)

```yaml
TARGETS:
  SHARPE_RATIO: 0.5-0.9
  ANNUAL_RETURN: 8-15%
  MAX_DRAWDOWN: 15-20%
  WIN_RATE: 50-60%
  NUM_TRADES: 15-20
  WFE: "> 60%"
```

---

## 🛠️ Technology Stack

### Core
- Python 3.10+
- pandas, numpy, scipy
- cvxpy (QP optimization)
- ib_insync (IBKR)

### New Dependencies
- networkx (graph analysis)
- scikit-learn (Granger causality)
- requests (FDA scraping)
- beautifulsoup4 (web scraping)
- yfinance (market data fallback)

### Optional (Phase 2)
- FastAPI (REST API)
- Kafka (messaging)
- PostgreSQL (time-series data)
- Grafana (monitoring)

---

## 🚦 Development Roadmap

### Week 1: Research & Design
- [x] Architecture document
- [ ] Research REMX/URNM/QTUM correlations
- [ ] Research FDA data sources
- [ ] Design WFO protocol

### Week 2: Core Implementation
- [ ] IBKR API integration
- [ ] Structural Arbitrage signals
- [ ] Event-Driven signals
- [ ] Ricci Curvature computation

### Week 3: Strategy & Portfolio
- [ ] WFO implementation
- [ ] Portfolio optimizer (adapt from Algo-trade)
- [ ] Risk management
- [ ] Kill-switches

### Week 4: Testing
- [ ] Unit tests
- [ ] Integration tests
- [ ] Backtest 2022-2024
- [ ] Walk-Forward validation

### Week 5-6: Paper Trading
- [ ] Connect to IBKR Paper Account
- [ ] Run live simulation
- [ ] Monitor performance
- [ ] Iterate on parameters

### Week 7-8: Live Deployment (if successful)
- [ ] Deploy with $8K-$10K
- [ ] Daily monitoring
- [ ] Weekly performance review

---

## ✅ Success Criteria (MVP)

```
MUST HAVE:
✓ OOS Sharpe > 0.5 (on 2022-2024 backtest)
✓ WFE > 60%
✓ Max DD < 25%
✓ Successfully execute 10+ trades in paper trading

NICE TO HAVE:
◇ Sharpe > 0.7
◇ Win Rate > 55%
◇ Positive returns in 2022 (bear market)
```

---

## 🔄 Next Steps (Today)

1. ✅ Create architecture document
2. [ ] Create project structure
3. [ ] Research structural arbitrage (REMX/URNM/QTUM)
4. [ ] Implement IBKR client wrapper
5. [ ] Implement first signal (Structural Arbitrage)

---

**Author**: Claude + Erez
**Date**: 2025-10-27
**Version**: 0.1.0 (MVP)
