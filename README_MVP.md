# AlgoX Hybrid MVP

**A hybrid algorithmic trading system combining proven infrastructure with advanced strategies.**

[![Status](https://img.shields.io/badge/status-MVP-yellow)](.)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 🎯 Project Overview

**AlgoX Hybrid MVP** takes the **working infrastructure** from Algo-trade and combines it with **advanced strategies** from the AlgoX specification to create a practical, deployable trading system.

### Key Innovations

1. **Structural Arbitrage**: Exploits lead-lag relationships (REMX → URNM → QTUM)
2. **Ricci Curvature**: Early Warning System for market fragility
3. **Event-Driven**: FDA approval calendar trading (biotech)

### Architecture

```
Data Layer (IBKR API + FDA) → Signals (3 strategies) → Portfolio (QP optimizer)
→ Execution (IBKR) → Monitoring (Kill-switches)
```

---

## 📊 Performance Targets

| Metric | Target (12 months) |
|--------|-------------------|
| **Sharpe Ratio** | 0.5 - 0.9 |
| **Annual Return** | 8% - 15% |
| **Max Drawdown** | < 20% |
| **Win Rate** | 50% - 60% |
| **Number of Trades** | 15 - 20 |
| **Walk-Forward Efficiency** | > 60% |

---

## 🚀 Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/ereztash/Algo-trade.git
cd Algo-trade

# Install dependencies
pip install -r requirements_mvp.txt

# Verify installation
python -c "import algox; print(algox.__version__)"
```

### 2. Configuration

Edit `config/mvp_config.yaml`:

```yaml
CAPITAL:
  INITIAL: 10000.0  # Starting capital

EXECUTION:
  PORT: 7497  # 7497 for IBKR paper trading, 7496 for live
```

### 3. Connect IBKR

#### Paper Trading (Recommended for MVP)
1. Download [IB Gateway](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) or TWS
2. Log in to your IBKR paper trading account
3. Enable API: **Configure** → **Settings** → **API** → **Enable ActiveX and Socket Clients**
4. Set port to **7497** (paper) or **7496** (live)

### 4. Run Backtest

```bash
# Run backtest on 2022-2024 data
python scripts/run_backtest.py --config config/mvp_config.yaml --start 2022-01-01 --end 2024-12-31
```

### 5. Paper Trading

```bash
# Run live paper trading
python scripts/run_live.py --mode paper --config config/mvp_config.yaml
```

---

## 📁 Project Structure

```
algo-x-mvp/
├── algox/                    # Main package
│   ├── data/                 # Data sources
│   │   ├── ibkr_client.py   # IBKR API wrapper
│   │   ├── fda_scraper.py   # FDA calendar
│   │   └── market_data.py   # Market data utilities
│   ├── signals/              # Signal generators
│   │   ├── structural.py    # Structural arbitrage
│   │   ├── ricci_curvature.py  # Ricci curvature EWS
│   │   ├── event_driven.py  # FDA events
│   │   └── legacy.py        # Original 6 signals (fallback)
│   ├── strategy/             # Strategy orchestration
│   │   ├── orchestrator.py  # Main orchestrator
│   │   ├── wfo.py          # Walk-Forward Optimization
│   │   ├── regime.py       # Regime detection
│   │   └── gates.py        # LinUCB gate selection
│   ├── portfolio/            # Portfolio management
│   │   ├── optimizer.py    # QP optimization
│   │   ├── risk.py         # Risk management
│   │   └── sizing.py       # Position sizing
│   ├── execution/            # Order execution
│   │   ├── ibkr_executor.py  # IBKR execution
│   │   └── slippage.py      # Slippage tracking
│   └── monitoring/           # Performance monitoring
│       ├── metrics.py       # Performance metrics
│       └── killswitch.py    # Circuit breakers
├── config/
│   ├── mvp_config.yaml      # Main configuration
│   └── symbols.yaml         # Trading universe
├── scripts/
│   ├── run_backtest.py      # Backtest script
│   └── run_live.py          # Live trading script
├── notebooks/                # Research notebooks
│   ├── 01_research_structural.ipynb
│   ├── 02_research_ricci.ipynb
│   └── 03_backtest_analysis.ipynb
└── tests/                    # Unit tests
```

---

## 🧠 Strategy Details

### 1. Structural Arbitrage

**Concept**: Exploit lead-lag relationships in supply chains

**Chain**: `REMX → URNM → QTUM`

- **REMX**: Rare Earth Metals ETF (upstream)
- **URNM**: Uranium Miners ETF (midstream)
- **QTUM**: Quantum Computing ETF (downstream)

**Signal Logic**:
1. Test Granger causality: REMX → URNM, URNM → QTUM
2. Detect breakout in REMX (> 2% move)
3. Enter positions in URNM/QTUM with lag-adjusted timing

**Position Sizing**: 15% per ETF

**Example**:
```python
from algox.signals.structural import StructuralArbitrageSignal

signal = StructuralArbitrageSignal(config)
signals = signal.generate(price_data)
# Returns: {"REMX": 0.0, "URNM": 0.65, "QTUM": 0.42}
```

---

### 2. Ricci Curvature (Early Warning System)

**Concept**: Detect systemic fragility before market crashes

**Theory**: Markets are correlation networks. Negative Ricci curvature indicates fragility.

**Signal Logic**:
1. Build correlation network (SPY, QQQ, IWM, DIA)
2. Calculate Forman-Ricci curvature for each edge
3. If avg(curvature) < -0.2 → **Reduce exposure** (0.5x)
4. If avg(curvature) > 0.1 → **Increase exposure** (1.2x)

**Usage**: Risk filter, not standalone signal

**Example**:
```python
from algox.signals.ricci_curvature import RicciCurvatureEWS

ews = RicciCurvatureEWS(config)
stats, adjustment = ews.calculate(price_data)
# adjustment = 0.5 (reduce), 1.0 (neutral), or 1.2 (increase)
```

---

### 3. Event-Driven (FDA Approvals)

**Concept**: Trade around FDA PDUFA dates for biotech

**Strategy**:
- **Entry**: T-5 days before PDUFA
- **Exit**: T-2 days before PDUFA (avoid binary risk)
- **Filter**: Phase III+, Market cap > $500M, Volume > $5M/day

**Rationale**: Pre-announcement volatility creates opportunities; exit before unpredictable outcome

**Position Sizing**: 10% per position, max 2 concurrent

**Example**:
```python
from algox.signals.event_driven import EventDrivenSignal
from datetime import datetime

signal = EventDrivenSignal(config)
opportunities = signal.scan_calendar(datetime.now(), price_data)
# Returns: [{"symbol": "ABCD", "action": "ENTRY", "pdufa_date": ..., "signal_strength": 0.75}]
```

---

## 🔬 Walk-Forward Optimization (WFO)

**Goal**: Ensure out-of-sample performance is robust

**Protocol** (8 steps):

1. **Data Split**: Train (12m) → Validate (3m) → Test (3m)
2. **Feature Engineering**: Granger tests, Ricci curvature (on training only)
3. **Normalization**: Fit z-score params on training
4. **Model Training**: Bayesian hyperparameter optimization
5. **OOS Testing**: Test on unseen data
6. **Statistical Validation**: CSCV, PSR, DSR
7. **Roll Forward**: Shift window by 3 months
8. **Aggregate**: Calculate Walk-Forward Efficiency (WFE)

**Success Criteria**: WFE > 60%, OOS Sharpe > 0.5

---

## 💰 Risk Management

### Position Limits

```yaml
MAX_POSITION_SIZE: 15%      # Per position
MAX_GROSS_EXPOSURE: 50%     # Total capital
MAX_CONCURRENT: 5           # Max positions
MAX_SECTOR: 30%             # Per sector
```

### Circuit Breakers

| Trigger | Threshold | Action |
|---------|-----------|--------|
| **Max Drawdown** | > 20% | STOP ALL TRADING |
| **Sharpe Ratio** | < 0.5 for 3 months | STOP ALL TRADING |
| **Daily Loss** | > 3% | PAUSE FOR DAY |
| **PSR** | < 0.2 | REVIEW STRATEGY |

---

## 📈 Monitoring

### Daily Metrics

- P&L (gross, net)
- Positions (current, overnight)
- Exposure (gross, net, sector)
- Slippage (actual vs. expected)

### Weekly Reports

- Sharpe Ratio (rolling 1M, 3M)
- Win Rate
- Max Drawdown
- Signal Performance (per strategy)

### Monthly Reviews

- Walk-Forward Efficiency
- Alpha Decay Detection
- Strategy Rebalancing

---

## 🧪 Testing

### Unit Tests

```bash
pytest tests/ -v
```

### Integration Tests

```bash
pytest tests/integration/ -v
```

### Backtest

```bash
python scripts/run_backtest.py --config config/mvp_config.yaml --start 2022-01-01 --end 2024-12-31
```

---

## 🛣️ Roadmap

### Week 1-2: Research & Design
- [x] Architecture document
- [x] IBKR client wrapper
- [x] Structural Arbitrage signal
- [x] Ricci Curvature signal
- [x] Event-Driven signal
- [ ] Research REMX/URNM/QTUM correlations
- [ ] Build FDA calendar

### Week 3-4: Core Implementation
- [ ] Portfolio optimizer (adapt from Algo-trade)
- [ ] WFO protocol
- [ ] Strategy orchestrator
- [ ] Risk management module

### Week 5-6: Testing
- [ ] Unit tests
- [ ] Backtest 2022-2024
- [ ] Walk-Forward validation

### Week 7-8: Paper Trading
- [ ] Deploy to IBKR paper account
- [ ] Daily monitoring
- [ ] Performance review

### Week 9+: Live (if successful)
- [ ] Deploy with $8K-$10K capital
- [ ] Weekly reports
- [ ] Continuous optimization

---

## 📚 References

### Structural Arbitrage
- Granger, C. W. J. (1969). "Investigating causal relations by econometric models and cross-spectral methods"
- Lo, A. W., & MacKinlay, A. C. (1988). "Stock market prices do not follow random walks: Evidence from a simple specification test"

### Ricci Curvature
- Sandhu, R., et al. (2016). "Market fragility, systemic risk, and Ricci curvature"
- Ollivier, Y. (2009). "Ricci curvature of Markov chains on metric spaces"

### Event-Driven
- Kolchinsky, A., et al. (2020). "The anatomy of FDA drug approvals"
- Hwang, T. J., et al. (2016). "Failure of investigational drugs in late-stage clinical development and publication of trial results"

### Anti-Overfitting
- Bailey, D. H., et al. (2014). "Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance"
- Lopez de Prado, M. (2018). "Advances in Financial Machine Learning"

---

## ⚠️ Disclaimers

1. **Past performance is not indicative of future results.**
2. **Trading involves substantial risk of loss.**
3. **This is an MVP for research purposes.**
4. **Always start with paper trading.**
5. **Consult a financial advisor before live trading.**

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📧 Contact

**Author**: Erez + Claude

**Issues**: [GitHub Issues](https://github.com/ereztash/Algo-trade/issues)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **Algo-trade**: Original codebase providing infrastructure
- **AlgoX Specification**: Advanced strategies and architecture
- **Interactive Brokers**: Market data and execution
- **Lopez de Prado**: Walk-Forward Optimization methodology

---

**Built with ❤️ using Python, IBKR API, and mathematical finance**
