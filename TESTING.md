# AlgoTrader Testing Guide

## Overview

The AlgoTrader platform has a comprehensive test suite covering unit tests, integration tests, and property-based tests. The test suite is designed to ensure code quality, prevent regressions, and validate system behavior.

## Test Statistics

- **Total Test Functions**: 93+
- **Target Coverage**: ~30%
- **Test Types**: Unit, Integration, Property-Based, Metamorphic
- **CI/CD**: GitHub Actions with automated testing

## Quick Start

### Running All Tests

```bash
# Run all tests with coverage
./run_tests.sh all

# Or use pytest directly
pytest tests/ --cov=algo_trade --cov=data_plane --cov=order_plane -v
```

### Running Specific Test Suites

```bash
# Unit tests only (fast)
./run_tests.sh unit

# Integration tests (requires Kafka)
./run_tests.sh integration

# Property-based tests
./run_tests.sh property

# Fast tests (exclude slow markers)
./run_tests.sh fast
```

### Generating Coverage Reports

```bash
# Generate HTML coverage report
./run_tests.sh coverage

# View in browser
open htmlcov/index.html
```

## Test Structure

```
tests/
├── conftest.py                    # Shared fixtures and configuration
├── test_signals.py                # Signal generation tests (20+ tests)
├── test_qp_solver.py              # QP optimization tests (25+ tests)
├── test_simulation.py             # Simulation tests
├── unit/
│   ├── test_risk_management.py    # Risk management tests (15+ tests)
│   ├── test_data_plane.py         # Data plane tests (15+ tests)
│   └── test_order_plane.py        # Order plane tests (18+ tests)
├── property/
│   └── test_qp_properties.py      # Property-based QP tests
├── metamorphic/
│   ├── test_mt_scaling.py         # Metamorphic scaling tests
│   └── test_mt_noise.py           # Metamorphic noise tests
├── integration/
│   └── (integration tests)
└── e2e/
    └── ibkr_mock.py              # End-to-end test mocks
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)

Fast, isolated tests for individual components:
- **Signals**: OFI, Earnings, VRP, Positioning, Trend, Sentiment
- **Optimization**: QP solver, constraint validation, volatility targeting
- **Risk Management**: Kill-switches, covariance estimation, regime detection
- **Data Plane**: Normalization, OFI calculation, QA gates
- **Order Plane**: Risk checks, throttling, transaction cost learning

### Integration Tests (`@pytest.mark.integration`)

Tests for component interactions:
- Multi-period optimization
- Full signal pipeline
- Risk management integration
- Kafka message flow (requires Kafka)

### Property-Based Tests (`@pytest.mark.property`)

Hypothesis-driven tests for mathematical properties:
- QP solver properties
- Signal stability
- Covariance matrix properties

### Metamorphic Tests (`@pytest.mark.metamorphic`)

Tests that verify system behavior under transformations:
- Scaling invariance
- Noise robustness

## Test Markers

Use markers to run specific test categories:

```bash
# Run only unit tests
pytest -m "unit"

# Run integration tests (excluding IBKR-dependent tests)
pytest -m "integration and not requires_ibkr"

# Run property-based tests
pytest -m "property"

# Run slow tests
pytest -m "slow"

# Run tests that require Kafka
pytest -m "requires_kafka"
```

## Continuous Integration

### GitHub Actions Workflow

The CI pipeline (`.github/workflows/ci.yml`) runs automatically on:
- Push to `main`, `develop`, or `claude/**` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

### CI Jobs

1. **Unit Tests** (Python 3.9, 3.10, 3.11)
   - Run all unit tests with coverage
   - Upload coverage to Codecov
   - Generate test reports

2. **Integration Tests**
   - Spin up Kafka and Zookeeper via Docker
   - Run integration tests
   - Validate Kafka message flow

3. **Code Quality**
   - Black (code formatting)
   - Flake8 (linting)
   - MyPy (type checking)
   - Bandit (security scanning)

4. **Property-Based Tests**
   - Run Hypothesis tests with CI profile
   - Extended test generation

5. **Test Summary**
   - Aggregate all results
   - Fail if critical tests fail

### Viewing CI Results

- **GitHub Actions**: Check the "Actions" tab in GitHub
- **Coverage**: View coverage trends on Codecov
- **Artifacts**: Download test results and coverage HTML

## Writing Tests

### Test Template

```python
import pytest
import numpy as np
import pandas as pd

@pytest.mark.unit
class TestMyFeature:
    """Test suite for MyFeature."""

    def test_basic_functionality(self):
        """Test basic feature behavior."""
        # Arrange
        input_data = ...

        # Act
        result = my_function(input_data)

        # Assert
        assert result is not None
        assert isinstance(result, expected_type)

    def test_edge_case(self):
        """Test edge case handling."""
        # Test with empty data, NaN, extreme values, etc.
        pass
```

### Using Fixtures

```python
def test_with_market_data(sample_market_data):
    """Use the sample_market_data fixture."""
    assert len(sample_market_data) > 0
    assert "close" in sample_market_data.columns

def test_with_config(default_config):
    """Use the default_config fixture."""
    assert default_config["VOL_TARGET"] == 0.10
```

### Property-Based Testing

```python
from hypothesis import given, strategies as st

@pytest.mark.property
@given(st.floats(min_value=0.01, max_value=1.0))
def test_property(value):
    """Test that property holds for all values."""
    result = my_function(value)
    assert result >= 0  # Property: result is always positive
```

## Coverage Goals

### Current Coverage Targets

- **Overall**: ~30% (baseline)
- **Core Modules**: >50%
  - `algo_trade/core/`: Signals, optimization, risk
  - `data_plane/`: Normalization, QA gates
  - `order_plane/`: Risk checks, execution

### Improving Coverage

```bash
# Generate coverage report
pytest --cov=algo_trade --cov-report=html

# Open report
open htmlcov/index.html

# Identify uncovered lines and add tests
```

## Best Practices

### 1. Test Naming

- Use descriptive names: `test_qp_solver_respects_gross_limit`
- Follow pattern: `test_<what>_<condition>_<expected>`

### 2. Test Organization

- One test class per module/feature
- Group related tests in classes
- Use clear docstrings

### 3. Assertions

- One logical assertion per test (where possible)
- Use specific assertions: `assert x == y`, not `assert x`
- Add error messages: `assert x > 0, f"Expected positive, got {x}"`

### 4. Fixtures

- Reuse fixtures from `conftest.py`
- Create module-specific fixtures when needed
- Use appropriate fixture scopes (`function`, `class`, `module`, `session`)

### 5. Mocking

- Mock external dependencies (IBKR, Kafka, network calls)
- Use `unittest.mock.patch` or `pytest-mock`
- Validate mock calls with `assert_called_with()`

### 6. Test Data

- Use deterministic random seeds
- Create minimal test data
- Avoid hardcoding large datasets

## Troubleshooting

### Tests Failing Locally

```bash
# Clean pytest cache
./run_tests.sh clean

# Reinstall dependencies
pip install -r requirements-dev.txt

# Run with verbose output
pytest -vv --tb=long
```

### Import Errors

```bash
# Verify PYTHONPATH
export PYTHONPATH=/path/to/Algo-trade:$PYTHONPATH

# Or install in editable mode
pip install -e .
```

### Kafka Tests Failing

```bash
# Start Kafka services
./docker/docker-helper.sh start

# Wait for services to be healthy
docker ps

# Run integration tests
./run_tests.sh integration
```

### Slow Tests

```bash
# Skip slow tests
pytest -m "not slow"

# Use pytest-xdist for parallel execution
pip install pytest-xdist
pytest -n auto  # Auto-detect CPU count
```

## Performance Testing

### Benchmarking

```python
@pytest.mark.performance
def test_qp_solver_performance(benchmark):
    """Benchmark QP solver performance."""
    result = benchmark(solve_qp, mu_hat, C, w_prev, ...)
    assert result is not None
```

Run benchmarks:

```bash
pytest tests/ -m "performance" --benchmark-only
```

## Resources

- **pytest Documentation**: https://docs.pytest.org/
- **Hypothesis Guide**: https://hypothesis.readthedocs.io/
- **Coverage.py**: https://coverage.readthedocs.io/
- **Codecov**: https://about.codecov.io/

## Contributing

When adding new features:

1. Write tests first (TDD)
2. Ensure tests pass locally
3. Verify CI passes
4. Maintain or improve coverage

Minimum requirements for PR approval:
- All unit tests pass
- No decrease in coverage
- Code quality checks pass
- Integration tests pass (if applicable)

---

**Last Updated**: November 2025
