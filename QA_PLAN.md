# QA Plan - תוכנית אבטחת איכות מקיפה
## Comprehensive QA & Testing Strategy

**תאריך:** 2025-11-07
**גרסה:** 1.0
**Branch:** claude/qa-readiness-testing-framework-011CUtjXHuN4ySpCupVkPfAx
**מצב:** Pre-Implementation

---

## 🎯 מטרת-על (North Star Goal)

**העלאת המערכת ל-QA מוכנות מלאה:**
- ✅ Coverage ≥ 80%
- ✅ CI/CD עם Quality Gates
- ✅ דוחות אוטומטיים
- ✅ Fixtures חתומים + דטרמיניסטיים
- ✅ Governance Gate לסיכונים
- ✅ בדיקות Robustness (Metamorphic/Chaos)
- ✅ תצפיתיות מלאה (Observability)

---

## 📊 ארכיטקטורת בדיקות (Testing Architecture)

### פירמידת הבדיקות (Test Pyramid)

```
                    ╱╲
                   ╱E2╲
                  ╱────╲
                 ╱ Chaos╲
                ╱────────╲
               ╱Integration╲
              ╱────────────╲
             ╱  Property-  ╲
            ╱   Based (PBT) ╲
           ╱─────────────────╲
          ╱   Unit Tests     ╱
         ╱─────────────────────╲
        ╱    Metamorphic (MT)  ╱
       ╱───────────────────────╱
```

### שכבות בדיקה

#### 1. **Unit Tests** (בסיס הפירמידה)
- **יעד:** 80%+ coverage
- **היקף:** כל מודול בנפרד
- **כלים:** pytest, pytest-cov
- **תדירות:** בכל commit
- **דוגמאות:**
  - `test_signals.py` - בדיקת 6 אותות בנפרד
  - `test_qp_solver.py` - פתרון QP עם constraints
  - `test_risk.py` - Kill-Switches, Drawdown, Covariance
  - `test_validation.py` - PSR, DSR, CSCV

#### 2. **Property-Based Tests (PBT)** (שכבה 2)
- **יעד:** 50%+ מודולים כמותיים
- **כלים:** Hypothesis
- **תדירות:** בכל PR
- **Properties:**
  - **QP Solver:** ∑weights = 1±ε, box constraints מכובדים
  - **Risk:** VaR/MaxDD בתוך מגבלות
  - **Signals:** קורלציה חיובית עם returns
  - **Portfolio:** Gross/Net exposure בגבולות

#### 3. **Metamorphic Tests (MT)** (שכבה 3)
- **יעד:** MR-pass-rate ≥ 90%
- **כלים:** pytest + custom framework
- **תדירות:** בכל PR
- **Metamorphic Relations:**
  - **MR1-Scaling:** P'=α·P → Signal(P')≈Signal(P)
  - **MR2-TimeShift:** Data+Δt → Decision consistency
  - **MR3-Noise:** Symmetric noise → Stability
  - **MR4-Tail:** Tail zeroing → Regime stability

#### 4. **Integration Tests** (שכבה 4)
- **יעד:** 70%+ של זרימות בין-מודולים
- **תדירות:** בכל PR
- **תרחישים:**
  - Data Plane → Strategy Plane
  - Strategy Plane → Order Plane
  - Kafka message flow
  - Contract validation

#### 5. **Chaos/Resilience Tests** (שכבה 5)
- **יעד:** Recovery ≤ 30s
- **תדירות:** Nightly + pre-release
- **תקלות:**
  - Network disconnect (3s, 10s, 30s)
  - High latency (500ms, 2s, 5s)
  - Exception injection
  - Message loss (5%, 20%)

#### 6. **End-to-End Tests** (פסגה)
- **יעד:** 6 תרחישים מלאים
- **תדירות:** Pre-merge + nightly
- **תרחישים:**
  - Full trading loop
  - Kill-Switch activation
  - IBKR Mock lifecycle
  - Recovery scenarios

---

## 📁 מבנה תיקיות (Directory Structure)

```
Algo-trade/
├── tests/                          # כל הבדיקות
│   ├── __init__.py
│   ├── conftest.py                 # pytest fixtures גלובליות
│   │
│   ├── unit/                       # Unit tests
│   │   ├── __init__.py
│   │   ├── test_signals.py         # 6 אותות
│   │   ├── test_qp_solver.py       # QP optimization
│   │   ├── test_risk.py            # Risk management
│   │   ├── test_covariance.py      # Covariance estimation
│   │   ├── test_regime.py          # Regime detection
│   │   ├── test_validation.py      # PSR, DSR, CSCV
│   │   ├── test_ensemble.py        # Signal merging
│   │   └── test_execution.py       # Execution logic
│   │
│   ├── property/                   # Property-Based Tests
│   │   ├── __init__.py
│   │   ├── test_qp_properties.py   # QP invariants
│   │   ├── test_risk_properties.py # Risk constraints
│   │   ├── test_signal_properties.py # Signal properties
│   │   └── test_portfolio_properties.py # Portfolio constraints
│   │
│   ├── metamorphic/                # Metamorphic Tests
│   │   ├── __init__.py
│   │   ├── test_mt_scaling.py      # MR1: Linear scaling
│   │   ├── test_mt_timeshift.py    # MR2: Time shift
│   │   ├── test_mt_noise.py        # MR3: Noise injection
│   │   ├── test_mt_tail.py         # MR4: Tail zeroing
│   │   └── metamorphic_utils.py    # Helper functions
│   │
│   ├── integration/                # Integration Tests
│   │   ├── __init__.py
│   │   ├── test_data_to_strategy.py
│   │   ├── test_strategy_to_order.py
│   │   ├── test_kafka_flow.py
│   │   └── test_contracts.py       # Contract validation
│   │
│   ├── e2e/                        # End-to-End Tests
│   │   ├── __init__.py
│   │   ├── test_full_trading_loop.py
│   │   ├── test_kill_switch_activation.py
│   │   ├── test_regime_transition.py
│   │   ├── test_order_lifecycle.py
│   │   ├── test_recovery.py
│   │   └── ibkr_mock.py            # IBKR Mock implementation
│   │
│   ├── chaos/                      # Chaos/Resilience Tests
│   │   ├── __init__.py
│   │   ├── test_network_failures.py
│   │   ├── test_latency_injection.py
│   │   ├── test_exception_injection.py
│   │   ├── test_message_loss.py
│   │   ├── test_backoff_retry.py
│   │   ├── test_recovery_time.py
│   │   └── chaos_utils.py          # Chaos helpers
│   │
│   ├── performance/                # Performance Tests
│   │   ├── __init__.py
│   │   ├── test_latency.py         # p50, p95, p99
│   │   ├── test_throughput.py      # msg/sec
│   │   └── test_stress.py          # Load testing
│   │
│   └── contracts/                  # Contract Tests
│       ├── __init__.py
│       ├── test_bar_event_schema.py
│       ├── test_order_intent_schema.py
│       └── test_execution_report_schema.py
│
├── fixtures/                       # Test Data (deterministic)
│   ├── __init__.py
│   ├── market_data/
│   │   ├── bars_spy_2024.csv       # SPY bars
│   │   ├── bars_tsla_2024.csv      # TSLA bars
│   │   └── synthetic_prices.json   # Synthetic data
│   ├── signals/
│   │   ├── ofi_expected.json       # Expected OFI outputs
│   │   ├── ern_expected.json       # Expected ERN outputs
│   │   └── vrp_expected.json       # Expected VRP outputs
│   ├── portfolio/
│   │   ├── weights_expected.json   # Expected portfolio weights
│   │   └── qp_solutions.json       # QP solutions
│   └── seeds.yaml                  # Random seeds
│
├── golden/                         # Golden Traces (regression)
│   ├── __init__.py
│   ├── traces/
│   │   ├── full_trading_loop_v1.0.json
│   │   ├── kill_switch_scenario_v1.0.json
│   │   └── regime_transition_v1.0.json
│   └── compare.py                  # Golden trace comparison
│
├── contracts/                      # Message Contracts
│   ├── bar_event.schema.json       # BarEvent schema
│   ├── order_intent.schema.json    # OrderIntent schema
│   ├── execution_report.schema.json # ExecutionReport schema
│   ├── topics.yaml                 # Kafka topics
│   └── validators.py               # Schema validators
│
├── .github/
│   └── workflows/
│       ├── test.yml                # Main CI pipeline
│       ├── coverage.yml            # Coverage reporting
│       ├── chaos-nightly.yml       # Nightly chaos tests
│       ├── governance.yml          # Governance gates
│       └── release.yml             # Release pipeline
│
├── grafana/                        # Grafana Dashboards
│   ├── system_health.json
│   ├── strategy_performance.json
│   ├── risk_monitor.json
│   └── data_quality.json
│
├── docs/                           # Documentation
│   ├── QA_PLAN.md                  # This document
│   ├── PROPERTY_GUIDE.md           # Property-Based Testing guide
│   ├── METAMORPHIC_GUIDE.md        # Metamorphic Testing guide
│   ├── CHAOS_GUIDE.md              # Chaos Testing guide
│   ├── RUNBOOK.md                  # Operational runbook
│   └── PRE_LIVE_CHECKLIST.md       # Pre-live checklist
│
├── scripts/                        # Utility Scripts
│   ├── run_all_tests.sh            # Run complete test suite
│   ├── generate_coverage_report.sh # Coverage HTML report
│   ├── validate_contracts.sh       # Validate all schemas
│   └── chaos_runner.sh             # Chaos test runner
│
└── reports/                        # Test Reports (gitignored)
    ├── coverage/
    ├── junit/
    ├── chaos/
    └── performance/
```

---

## 🛠️ ספריות וכלים (Tools & Libraries)

### Testing Frameworks
```yaml
pytest: ">=7.4.0"                  # Test runner
pytest-cov: ">=4.1.0"              # Coverage plugin
pytest-xdist: ">=3.3.0"            # Parallel testing
pytest-timeout: ">=2.1.0"          # Test timeout
pytest-benchmark: ">=4.0.0"        # Performance benchmarking
```

### Property-Based Testing
```yaml
hypothesis: ">=6.82.0"             # PBT framework
hypothesis[numpy]: ">=6.82.0"      # NumPy strategies
hypothesis[pandas]: ">=6.82.0"     # Pandas strategies
```

### Metamorphic Testing
```yaml
# No external library - custom implementation
# Based on research: Chen et al., "Metamorphic Testing: A Review"
```

### Chaos Engineering
```yaml
chaos-toolkit: ">=1.14.0"          # Optional: Chaos orchestration
pytest-chaos: ">=0.1.0"            # Custom chaos plugin
```

### Contracts & Validation
```yaml
jsonschema: ">=4.19.0"             # JSON Schema validation
avro-python3: ">=1.10.0"           # Avro schema support (optional)
pydantic: ">=2.3.0"                # Data validation
```

### Mocking & Fixtures
```yaml
pytest-mock: ">=3.11.0"            # Mock fixtures
faker: ">=19.3.0"                  # Fake data generation
factory-boy: ">=3.3.0"             # Factory fixtures
freezegun: ">=1.2.2"               # Time mocking
```

### Performance & Monitoring
```yaml
prometheus-client: ">=0.17.0"      # Metrics export
pytest-monitor: ">=1.6.6"          # Test performance tracking
memory-profiler: ">=0.61.0"        # Memory profiling
```

### CI/CD
```yaml
coverage[toml]: ">=7.3.0"          # Coverage reporting
pytest-html: ">=3.2.0"             # HTML reports
pytest-json-report: ">=1.5.0"      # JSON reports
bandit: ">=1.7.5"                  # Security linting
safety: ">=2.3.0"                  # Dependency vulnerability scanner
```

### Type Checking & Linting
```yaml
mypy: ">=1.5.0"                    # Type checker
black: ">=23.7.0"                  # Code formatter
flake8: ">=6.1.0"                  # Linter
isort: ">=5.12.0"                  # Import sorter
pylint: ">=2.17.0"                 # Static analyzer
```

---

## 🔐 נוהל נתונים דטרמיניסטי (Deterministic Data Protocol)

### עקרונות
1. **Reproducibility:** כל בדיקה חייבת לתת אותה תוצאה בכל run
2. **Isolation:** כל בדיקה עצמאית (לא תלויה באחרות)
3. **Fixtures Versioning:** כל fixture חתום עם hash
4. **Seed Management:** seeds קבועים ומתועדים

### Seeds Configuration

**קובץ:** `fixtures/seeds.yaml`
```yaml
# Random Seeds for Deterministic Testing
# DO NOT MODIFY without updating golden files

global_seed: 42                   # Master seed
numpy_seed: 42
random_seed: 42
torch_seed: 42                    # If using PyTorch

# Module-specific seeds
seeds:
  signals: 1001
  qp_solver: 1002
  risk: 1003
  simulation: 1004
  validation: 1005
  metamorphic: 2000
  chaos: 3000

# Fixture generation seeds
fixture_seeds:
  market_data: 5001
  synthetic_prices: 5002
  order_flow: 5003
```

### Fixture Signing

כל fixture file כולל hash signature:
```python
# fixtures/__init__.py
import hashlib
import json

def sign_fixture(data: dict) -> dict:
    """Add signature to fixture data."""
    data_str = json.dumps(data, sort_keys=True)
    signature = hashlib.sha256(data_str.encode()).hexdigest()
    return {
        "data": data,
        "signature": signature,
        "created_at": "2025-11-07T00:00:00Z",
        "version": "1.0"
    }

def verify_fixture(fixture_file: str) -> bool:
    """Verify fixture signature."""
    with open(fixture_file) as f:
        content = json.load(f)

    data = content["data"]
    expected_sig = content["signature"]

    data_str = json.dumps(data, sort_keys=True)
    actual_sig = hashlib.sha256(data_str.encode()).hexdigest()

    return actual_sig == expected_sig
```

### Fixture Loading

**pytest conftest.py:**
```python
# tests/conftest.py
import pytest
import numpy as np
import random
import yaml
from pathlib import Path

@pytest.fixture(scope="session", autouse=True)
def set_random_seeds():
    """Set all random seeds globally."""
    seeds_file = Path(__file__).parent.parent / "fixtures" / "seeds.yaml"
    with open(seeds_file) as f:
        seeds = yaml.safe_load(f)

    np.random.seed(seeds["numpy_seed"])
    random.seed(seeds["random_seed"])

    # Set seeds for specific libraries if used
    # torch.manual_seed(seeds["torch_seed"])

    yield

    # Reset seeds after tests
    np.random.seed(None)
    random.seed(None)

@pytest.fixture
def market_data_fixture():
    """Load deterministic market data."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "market_data" / "bars_spy_2024.csv"

    # Verify signature
    from fixtures import verify_fixture
    assert verify_fixture(fixture_path), "Fixture signature verification failed!"

    import pandas as pd
    return pd.read_csv(fixture_path)

@pytest.fixture
def expected_signal_output():
    """Load expected signal outputs."""
    fixture_path = Path(__file__).parent.parent / "fixtures" / "signals" / "ofi_expected.json"

    import json
    with open(fixture_path) as f:
        content = json.load(f)

    # Verify
    from fixtures import verify_fixture
    assert verify_fixture(fixture_path), "Fixture signature verification failed!"

    return content["data"]
```

### Golden Files Protocol

**Golden Trace Structure:**
```json
{
  "version": "1.0",
  "test_name": "test_full_trading_loop",
  "created_at": "2025-11-07T00:00:00Z",
  "signature": "sha256_hash",
  "inputs": {
    "market_data": "fixtures/market_data/bars_spy_2024.csv",
    "config": {
      "VOL_TARGET": 0.10,
      "BOX_LIM": 0.25
    }
  },
  "outputs": {
    "signals": [...],
    "portfolio_weights": [...],
    "order_intents": [...],
    "final_pnl": 1234.56
  },
  "metrics": {
    "execution_time_ms": 245,
    "memory_peak_mb": 512
  }
}
```

**Golden Comparison:**
```python
# golden/compare.py
import json
import numpy as np
from pathlib import Path

def compare_with_golden(test_name: str, actual_output: dict, tolerance: float = 1e-6) -> bool:
    """Compare test output with golden trace."""
    golden_path = Path(__file__).parent / "traces" / f"{test_name}_v1.0.json"

    if not golden_path.exists():
        # First run - create golden file
        save_golden(test_name, actual_output)
        return True

    with open(golden_path) as f:
        golden = json.load(f)

    # Compare outputs
    golden_out = golden["outputs"]

    # Numeric comparison with tolerance
    for key in golden_out:
        if isinstance(golden_out[key], (list, np.ndarray)):
            if not np.allclose(golden_out[key], actual_output[key], atol=tolerance):
                print(f"Mismatch in {key}")
                return False
        else:
            if golden_out[key] != actual_output[key]:
                print(f"Mismatch in {key}")
                return False

    return True

def save_golden(test_name: str, output: dict):
    """Save new golden trace."""
    golden_path = Path(__file__).parent / "traces" / f"{test_name}_v1.0.json"

    from fixtures import sign_fixture
    golden_data = sign_fixture(output)
    golden_data["test_name"] = test_name

    with open(golden_path, "w") as f:
        json.dump(golden_data, f, indent=2)
```

---

## 🔄 CI/CD Pipeline (GitHub Actions)

### Main Test Workflow

**קובץ:** `.github/workflows/test.yml`
```yaml
name: Test Suite

on:
  push:
    branches: [ main, develop, claude/** ]
  pull_request:
    branches: [ main, develop ]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install black flake8 mypy isort pylint
      - name: Black check
        run: black --check .
      - name: Flake8
        run: flake8 algo_trade/ data_plane/ order_plane/ tests/
      - name: MyPy
        run: mypy algo_trade/ data_plane/ order_plane/
      - name: isort check
        run: isort --check-only .
      - name: Pylint
        run: pylint algo_trade/ data_plane/ order_plane/ --fail-under=8.0

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install bandit safety
      - name: Bandit security scan
        run: bandit -r algo_trade/ data_plane/ order_plane/ -ll
      - name: Safety vulnerability check
        run: safety check --json

  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11']
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-xdist pytest-timeout
      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=algo_trade --cov=data_plane --cov=order_plane \
            --cov-report=xml --cov-report=html --cov-report=term \
            -n auto --timeout=60
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unit-tests
      - name: Archive coverage report
        uses: actions/upload-artifact@v3
        with:
          name: coverage-report-${{ matrix.python-version }}
          path: htmlcov/

  property-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install hypothesis pytest
      - name: Run property-based tests
        run: pytest tests/property/ -v --hypothesis-show-statistics

  metamorphic-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run metamorphic tests
        run: pytest tests/metamorphic/ -v
      - name: Calculate MR-pass-rate
        run: python scripts/calculate_mr_pass_rate.py

  integration-tests:
    runs-on: ubuntu-latest
    services:
      kafka:
        image: confluentinc/cp-kafka:latest
        ports:
          - 9092:9092
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run integration tests
        run: pytest tests/integration/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run E2E tests
        run: pytest tests/e2e/ -v --timeout=300

  coverage-gate:
    needs: [unit-tests, integration-tests, e2e-tests]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Download coverage reports
        uses: actions/download-artifact@v3
      - name: Check coverage threshold
        run: |
          coverage combine
          coverage report --fail-under=80
      - name: Comment PR with coverage
        if: github.event_name == 'pull_request'
        uses: py-cov-action/python-coverage-comment-action@v3
        with:
          GITHUB_TOKEN: ${{ github.token }}
          MINIMUM_GREEN: 80
          MINIMUM_ORANGE: 60

  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install jsonschema avro-python3
      - name: Validate schemas
        run: python scripts/validate_contracts.sh
      - name: Run contract tests
        run: pytest tests/contracts/ -v
```

### Chaos Testing Workflow (Nightly)

**קובץ:** `.github/workflows/chaos-nightly.yml`
```yaml
name: Chaos Tests (Nightly)

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
  workflow_dispatch:      # Manual trigger

jobs:
  chaos-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run chaos tests
        run: pytest tests/chaos/ -v --timeout=600
      - name: Generate chaos scorecard
        run: python scripts/generate_chaos_scorecard.py
      - name: Upload chaos report
        uses: actions/upload-artifact@v3
        with:
          name: chaos-report
          path: reports/chaos/
      - name: Notify on failure
        if: failure()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Chaos tests failed! Check report.'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Governance Gate Workflow

**קובץ:** `.github/workflows/governance.yml`
```yaml
name: Governance Gate

on:
  pull_request:
    branches: [ main, develop ]

jobs:
  check-risk-params:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Full history
      - name: Check risk parameter changes
        run: |
          # Check if config.py changed
          if git diff --name-only origin/${{ github.base_ref }} | grep -q "algo_trade/core/config.py"; then
            echo "Risk parameters changed!"
            # Extract changed params
            CHANGED_PARAMS=$(git diff origin/${{ github.base_ref }} algo_trade/core/config.py | grep -E "KILL_PNL|MAX_DD|BOX_LIM|PSR_KILL_SWITCH")
            if [ -n "$CHANGED_PARAMS" ]; then
              echo "Critical risk parameters modified:"
              echo "$CHANGED_PARAMS"
              echo "::error::Risk parameter change requires approval from Risk Officer"
              exit 1
            fi
          fi
      - name: Check schema breaking changes
        run: python scripts/check_schema_compatibility.py
      - name: Verify all tests passed
        run: |
          # This job depends on all test jobs passing
          echo "All tests must pass before governance approval"
```

---

## 📈 מדדי איכות (Quality Metrics)

### KPIs ראשיים

| מדד | יעד | מדידה | תדירות |
|-----|-----|-------|---------|
| **Test Coverage** | ≥80% | pytest-cov | כל commit |
| **MR-pass-rate** | ≥90% | custom script | כל PR |
| **Chaos Recovery** | ≤30s | chaos tests | nightly |
| **p95 Latency** | ≤50ms | performance tests | pre-release |
| **Flaky Rate** | ≤2% | test history | weekly |
| **CI Success Rate** | ≥95% | GitHub Actions | weekly |
| **Mean Time to Fix** | ≤4h | incident tracking | monthly |

### דוחות

1. **Coverage Report:** HTML + XML (Codecov)
2. **Chaos Scorecard:** JSON + PDF
3. **Performance Report:** CSV + plots
4. **MR Report:** Pass/fail rates per relation
5. **CI Dashboard:** GitHub Actions insights

---

## 🚀 תהליך הרצה (Execution Process)

### Local Development

```bash
# 1. התקנת dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. הרצת unit tests
pytest tests/unit/ -v

# 3. הרצת property tests
pytest tests/property/ -v --hypothesis-show-statistics

# 4. הרצת metamorphic tests
pytest tests/metamorphic/ -v

# 5. הרצת כל הבדיקות עם coverage
pytest tests/ -v --cov=algo_trade --cov-report=html

# 6. פתיחת coverage report
open htmlcov/index.html
```

### CI Pipeline

1. **PR Creation:** אוטומטית מריץ lint + type-check + unit tests
2. **PR Update:** מריץ full test suite (unit + property + metamorphic + integration)
3. **Coverage Gate:** חוסם merge אם coverage < 80%
4. **Governance Gate:** חוסם merge אם שינויי risk params ללא approval
5. **Merge to develop:** מריץ E2E + chaos tests
6. **Nightly:** מריץ chaos tests + performance tests
7. **Release:** מריץ full suite + generates reports

---

## 📚 מסמכים נוספים

1. **PROPERTY_GUIDE.md** - מדריך Property-Based Testing
2. **METAMORPHIC_GUIDE.md** - מדריך Metamorphic Testing
3. **CHAOS_GUIDE.md** - מדריך Chaos Engineering
4. **RUNBOOK.md** - נהלי תפעול
5. **PRE_LIVE_CHECKLIST.md** - רשימת בדיקה לפני production

---

**נוצר על ידי:** Claude Code (AI Assistant)
**תאריך:** 2025-11-07
**Branch:** claude/qa-readiness-testing-framework-011CUtjXHuN4ySpCupVkPfAx
**לאישור:** QA Lead / Project Lead
