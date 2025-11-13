# Contributing to Algo-Trade

Thank you for your interest in contributing to the Algo-Trade quantitative trading system! This guide will help you get started with development.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing Guidelines](#testing-guidelines)
- [Documentation](#documentation)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)

---

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- Virtual environment tool (venv or conda)
- Basic knowledge of quantitative finance concepts
- Familiarity with NumPy, Pandas, and optimization libraries

### Setting Up Development Environment

```bash
# Clone the repository
git clone https://github.com/ereztash/Algo-trade.git
cd Algo-trade

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install pytest pytest-cov hypothesis black flake8 mypy isort

# Verify setup
pytest tests/ -v
```

### Project Structure Overview

```
algo_trade/core/     # Core trading engine
data_plane/          # Data ingestion & QA
order_plane/         # Order execution
tests/               # Test suite
docs/                # Documentation
```

See [README_EN.md](./README_EN.md) for detailed structure.

---

## Development Workflow

### 1. Create a Feature Branch

```bash
# Ensure you're on the latest main branch
git checkout main
git pull origin main

# Create a new feature branch
git checkout -b feature/your-feature-name
```

Branch naming conventions:
- `feature/`: New features or enhancements
- `fix/`: Bug fixes
- `docs/`: Documentation updates
- `test/`: Test additions or improvements
- `refactor/`: Code refactoring without behavior changes
- `perf/`: Performance improvements

### 2. Make Your Changes

- Write clean, readable code
- Follow the coding standards (see below)
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 3. Test Your Changes

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v
pytest tests/property/ -v
pytest tests/metamorphic/ -v

# Run with coverage
pytest tests/ --cov=algo_trade --cov-report=html
# View coverage report: open htmlcov/index.html

# Run linting
black --check .
flake8 .
mypy algo_trade/
isort --check .
```

### 4. Commit Your Changes

See [Commit Guidelines](#commit-guidelines) below.

### 5. Push and Create Pull Request

```bash
# Push your branch
git push origin feature/your-feature-name

# Create PR on GitHub
# Provide clear description of changes
```

---

## Code Standards

### Python Style Guide

We follow **PEP 8** with some modifications:

- **Line length**: 100 characters (not 79)
- **Quotes**: Use double quotes for strings (except when single quotes avoid escaping)
- **Indentation**: 4 spaces (no tabs)

### Code Formatting

Use **Black** for automatic formatting:

```bash
# Format all files
black .

# Check formatting without changes
black --check .
```

### Import Organization

Use **isort** for import sorting:

```bash
# Sort imports
isort .

# Check import order
isort --check .
```

Import order:
1. Standard library imports
2. Third-party imports
3. Local application imports

Example:
```python
# Standard library
import os
from typing import Dict, List, Tuple

# Third-party
import numpy as np
import pandas as pd

# Local
from algo_trade.core.signals import base_signals
from algo_trade.core.risk import covariance
```

### Type Hints

Use type hints for all function signatures:

```python
def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0
) -> float:
    """Calculate annualized Sharpe ratio."""
    excess_returns = returns - risk_free_rate
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()
```

### Docstrings

Use **Google-style** docstrings:

```python
def purged_k_fold(
    df: pd.DataFrame,
    n_splits: int = 5,
    embargo_len: int = 10
) -> List[Tuple[pd.Index, pd.Index]]:
    """
    Perform Purged K-Fold Cross-Validation.

    Splits data into k folds with embargo periods to prevent data leakage
    in time-series backtesting.

    Args:
        df: DataFrame with time-series data (index must be time-ordered)
        n_splits: Number of cross-validation folds
        embargo_len: Number of periods to embargo around each test fold

    Returns:
        List of (train_idx, test_idx) tuples for each fold

    Raises:
        ValueError: If n_splits < 2 or embargo_len < 0

    Example:
        >>> returns = pd.DataFrame(...)
        >>> splits = purged_k_fold(returns, n_splits=5, embargo_len=10)
        >>> for train_idx, test_idx in splits:
        >>>     train_data = returns.loc[train_idx]
        >>>     test_data = returns.loc[test_idx]
    """
    # Implementation...
```

Docstrings can be in **Hebrew** or **English**, but be consistent within a module.

### Code Comments

- Use comments to explain **why**, not **what**
- Prefer self-documenting code (clear variable/function names)
- Add comments for complex algorithms or financial formulas
- Include references to academic papers when applicable

Example:
```python
# Use Ledoit-Wolf shrinkage when sample size is small (T/N < 2)
# Reference: Ledoit & Wolf (2004) - "Honey, I Shrunk the Sample Covariance Matrix"
if T_N_ratio < 2.0:
    cov = ledoit_wolf_shrinkage(returns)
```

---

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Fast, isolated tests
├── property/                # Property-based tests (Hypothesis)
├── metamorphic/             # Metamorphic relation tests
├── integration/             # Multi-component tests
├── e2e/                     # End-to-end tests
└── chaos/                   # Chaos engineering tests
```

### Writing Unit Tests

```python
import pytest
from algo_trade.core.signals import base_signals

def test_ofi_signal_basic():
    """Test OFI signal with simple input."""
    returns = pd.DataFrame(...)
    ofi = base_signals.ofi_signal(returns, mom_h=20)

    # Assert shape
    assert ofi.shape == returns.shape

    # Assert no NaNs in valid range
    assert not ofi.iloc[20:].isna().any().any()

    # Assert z-score normalization (mean ≈ 0, std ≈ 1)
    assert abs(ofi.mean().mean()) < 0.1
    assert abs(ofi.std().mean() - 1.0) < 0.2
```

### Writing Property-Based Tests

Use **Hypothesis** for generative testing:

```python
from hypothesis import given, strategies as st

@given(
    gross_lim=st.floats(min_value=1.0, max_value=5.0),
    n_assets=st.integers(min_value=5, max_value=100)
)
def test_qp_gross_constraint(gross_lim, n_assets):
    """QP solver must always respect gross leverage constraint."""
    # Generate random inputs
    mu = np.random.randn(n_assets)
    cov = generate_random_covariance(n_assets)

    # Solve QP
    weights = qp_solver(mu, cov, gross_lim=gross_lim)

    # Property: sum of absolute weights <= gross_lim
    assert np.sum(np.abs(weights)) <= gross_lim + 1e-6
```

### Writing Metamorphic Tests

Test invariant properties under transformations:

```python
def test_signal_scale_invariance():
    """Signal should be invariant to price scaling."""
    prices = generate_prices()

    # Compute signal on original prices
    signal_1 = compute_signal(prices)

    # Compute signal on scaled prices (2x)
    signal_2 = compute_signal(prices * 2.0)

    # Metamorphic relation: signals should be identical
    assert np.allclose(signal_1, signal_2, rtol=1e-5)
```

### Test Coverage

- **Target**: 80%+ coverage for core modules
- **Minimum**: 60% coverage for new code
- Check coverage: `pytest --cov=algo_trade --cov-report=html`

Focus on:
- Core trading logic (signals, optimization, risk)
- Critical paths (order execution, kill-switches)
- Edge cases (empty data, extreme values, NaN handling)

Less critical:
- Visualization code
- Debugging utilities
- Deprecated code

### Test Execution Speed

- **Unit tests**: < 1s total
- **Property tests**: < 30s total
- **Integration tests**: < 2min total
- **E2E tests**: < 5min total

Mark slow tests with `@pytest.mark.slow`.

---

## Documentation

### Code Documentation

- **All public functions** must have docstrings
- **All modules** must have module-level docstrings
- **Complex algorithms** must have detailed comments

### README Updates

Update README files when:
- Adding new features
- Changing architecture
- Modifying configuration parameters
- Adding new dependencies

### Technical Documentation

Create or update docs in `docs/` for:
- New architectural components
- API changes
- Configuration changes
- Deployment procedures

### Inline Code Examples

Include runnable examples in docstrings:

```python
def calculate_ic(signal: pd.DataFrame, returns: pd.DataFrame) -> pd.Series:
    """
    Calculate Information Coefficient.

    Example:
        >>> signal = pd.DataFrame(...)
        >>> returns = pd.DataFrame(...)
        >>> ic = calculate_ic(signal, returns)
        >>> print(f"Mean IC: {ic.mean():.3f}")
        Mean IC: 0.042
    """
```

---

## Commit Guidelines

### Commit Message Format

```
[TYPE] Brief description (max 72 chars)

Detailed explanation (optional, wrap at 72 chars):
- What changed
- Why it changed
- Any breaking changes or migration notes

Refs: #issue-number (if applicable)
```

### Commit Types

- `[FEATURE]`: New feature or enhancement
- `[FIX]`: Bug fix
- `[DOCS]`: Documentation changes only
- `[TEST]`: Adding or updating tests
- `[REFACTOR]`: Code refactoring (no behavior change)
- `[PERF]`: Performance improvements
- `[INFRA]`: Infrastructure changes (CI/CD, Docker, etc.)
- `[STYLE]`: Code style changes (formatting, no logic change)
- `[CHORE]`: Routine tasks (dependency updates, etc.)

### Examples

Good:
```
[FEATURE] Add Ledoit-Wolf covariance shrinkage

Implement Ledoit-Wolf shrinkage estimator for improved covariance
estimation when T/N ratio is low. This reduces estimation error and
improves portfolio stability.

- Add ledoit_wolf_cov() function in risk/covariance.py
- Integrate with adaptive_cov() based on T/N ratio
- Add unit tests with 95% coverage

Refs: #42
```

```
[FIX] Correct EWMA covariance scaling factor

Previous implementation used incorrect scaling (w instead of w^2).
This caused underestimation of volatility by ~sqrt(2).

- Fix EWMA weight normalization
- Add regression test to catch this in future
- Update golden test files

Refs: #87
```

Bad:
```
fix bug
```

```
Added some new stuff to signals
```

### Commit Best Practices

- **Atomic commits**: One logical change per commit
- **Small commits**: Easier to review and revert if needed
- **Clear messages**: Explain the "why", not just the "what"
- **No WIP commits**: Squash before merging
- **Test before commit**: Ensure tests pass

---

## Pull Request Process

### Before Creating PR

1. ✅ All tests pass locally
2. ✅ Code is formatted (Black, isort)
3. ✅ Linting passes (Flake8, MyPy)
4. ✅ Coverage meets minimum threshold
5. ✅ Documentation updated
6. ✅ CHANGELOG updated (if applicable)

### PR Title Format

Same as commit message format:

```
[TYPE] Brief description
```

### PR Description Template

```markdown
## Summary
Brief description of changes

## Motivation
Why is this change necessary?

## Changes
- Specific change 1
- Specific change 2
- ...

## Testing
- [ ] Unit tests added/updated
- [ ] Property tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Documentation
- [ ] Code docstrings updated
- [ ] README updated (if needed)
- [ ] Technical docs updated (if needed)

## Checklist
- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] Coverage >= 80% for new code
- [ ] No breaking changes (or documented if unavoidable)
- [ ] Self-reviewed code

## Related Issues
Closes #issue-number
```

### Code Review Process

1. **Self-review**: Review your own PR first
2. **Automated checks**: Ensure CI passes
3. **Peer review**: Request review from at least 1 team member
4. **Address feedback**: Respond to all comments
5. **Approval**: Obtain approval before merging
6. **Merge**: Use "Squash and merge" for feature branches

### Review Guidelines (for Reviewers)

Focus on:
- **Correctness**: Does the code do what it claims?
- **Tests**: Are there sufficient tests?
- **Readability**: Is the code easy to understand?
- **Performance**: Any obvious inefficiencies?
- **Security**: Any potential vulnerabilities?

Be constructive:
- Praise good code
- Ask questions instead of making demands
- Suggest alternatives
- Focus on the code, not the person

---

## Project-Specific Guidelines

### Financial Algorithms

When implementing financial algorithms:

1. **Reference papers**: Cite academic papers in docstrings
2. **Validate formulas**: Include mathematical notation in comments
3. **Test edge cases**: Zero volatility, perfect correlation, etc.
4. **Use golden tests**: Store expected outputs for complex calculations

Example:
```python
def probabilistic_sharpe_ratio(
    sr_hat: float,
    T: int,
    skew: float = 0.0,
    kurt: float = 3.0,
    sr_bench: float = 0.0
) -> float:
    """
    Calculate Probabilistic Sharpe Ratio.

    Reference:
        Bailey & López de Prado (2012)
        "The Sharpe Ratio Efficient Frontier"
        Journal of Risk, 15(2), 3-44.

    Formula:
        z = (SR_hat - SR_bench) × sqrt(T-1) / sigma_SR
        where sigma_SR = sqrt(1 - skew×SR + (kurt-1)/4 × SR²)
        PSR = Φ(z)  # Standard normal CDF

    Args:
        sr_hat: Observed Sharpe ratio
        T: Number of observations
        skew: Skewness of returns (default: 0.0)
        kurt: Kurtosis of returns (default: 3.0)
        sr_bench: Benchmark Sharpe ratio (default: 0.0)

    Returns:
        Probability that true SR > SR_bench

    Example:
        >>> psr = probabilistic_sharpe_ratio(sr_hat=1.5, T=252)
        >>> print(f"PSR: {psr:.2%}")
        PSR: 98.61%
    """
    if T < 2:
        return 0.0

    # Calculate adjusted standard error
    sigma_sr = np.sqrt(1 - skew*sr_hat + (kurt-1)/4 * sr_hat**2)

    # Calculate z-score
    z = (sr_hat - sr_bench) * np.sqrt(T - 1) / sigma_sr

    # Return CDF of standard normal
    from scipy.stats import norm
    return norm.cdf(z)
```

### Configuration Management

- **Never hardcode** parameters in code
- **Use `targets.yaml`** for all configuration
- **Validate** configuration on load
- **Document** all parameters with units and ranges
- **Use type hints** in config loading functions

### Risk Management

**Critical**: Risk management code requires extra scrutiny:

- **Kill-switches** must be tested with chaos engineering
- **Position limits** must be validated with property tests
- **Leverage calculations** must be exact (no floating point issues)
- **Regime detection** must handle edge cases (empty data, all NaN)

Add `@pytest.mark.critical` to risk management tests.

### Performance

Optimize after correctness:

1. **Profile first**: Use `cProfile` or `line_profiler`
2. **Vectorize**: Use NumPy/Pandas operations
3. **Avoid loops**: Especially in hot paths
4. **Cache**: Expensive calculations (covariance, etc.)
5. **Measure**: Use benchmarks to validate improvements

Mark performance-critical code:
```python
# PERFORMANCE-CRITICAL: This runs in the hot path
# Vectorized implementation 100x faster than loop version
def calculate_signals_vectorized(returns: pd.DataFrame) -> pd.DataFrame:
    ...
```

---

## Questions?

If you have questions about contributing:

1. Check existing documentation (README, docs/)
2. Search existing issues/PRs
3. Ask in the team channel
4. Open a discussion issue

---

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (Private/Proprietary).

---

**Happy Contributing! 🚀**
