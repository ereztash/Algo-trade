"""
pytest configuration and global fixtures.

This file is automatically loaded by pytest and provides:
- Random seed management for reproducibility
- Common fixtures for all tests
- Pytest hooks for custom behavior
"""

import random
from pathlib import Path

import numpy as np
import pytest
import yaml


@pytest.fixture(scope="session", autouse=True)
def set_random_seeds():
    """
    Set all random seeds globally for deterministic tests.

    This fixture runs once per test session and ensures reproducibility
    across all tests.
    """
    # Load seeds from fixtures/seeds.yaml
    seeds_file = Path(__file__).parent.parent / "fixtures" / "seeds.yaml"

    if not seeds_file.exists():
        pytest.fail(f"Seeds file not found: {seeds_file}")

    with open(seeds_file) as f:
        seeds_config = yaml.safe_load(f)

    # Set global seeds
    np.random.seed(seeds_config["numpy_seed"])
    random.seed(seeds_config["random_seed"])

    # If torch is installed, set torch seed
    try:
        import torch

        torch.manual_seed(seeds_config["torch_seed"])
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seeds_config["torch_seed"])
    except ImportError:
        pass  # Torch not installed

    yield

    # Reset seeds after all tests (optional)
    np.random.seed(None)
    random.seed(None)


@pytest.fixture
def seeds():
    """Provide access to seeds configuration."""
    seeds_file = Path(__file__).parent.parent / "fixtures" / "seeds.yaml"
    with open(seeds_file) as f:
        return yaml.safe_load(f)


@pytest.fixture
def fixtures_dir():
    """Provide path to fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def golden_dir():
    """Provide path to golden files directory."""
    return Path(__file__).parent.parent / "golden"


# ============================================================================
# Market Data Fixtures
# ============================================================================


@pytest.fixture
def sample_market_data(fixtures_dir):
    """
    Load sample market data fixture.

    Returns a small deterministic dataset for testing.
    """
    import pandas as pd

    # For now, create synthetic data
    # TODO: Load from fixtures/market_data/ once created
    np.random.seed(5001)  # From seeds.yaml: fixture_seeds.market_data

    dates = pd.date_range("2024-01-01", periods=100, freq="1D")
    data = pd.DataFrame(
        {
            "date": dates,
            "open": 100 + np.random.randn(100).cumsum(),
            "high": 101 + np.random.randn(100).cumsum(),
            "low": 99 + np.random.randn(100).cumsum(),
            "close": 100 + np.random.randn(100).cumsum(),
            "volume": np.random.randint(1000000, 10000000, 100),
        }
    )

    # Ensure OHLC consistency
    data["high"] = data[["open", "high", "close"]].max(axis=1)
    data["low"] = data[["open", "low", "close"]].min(axis=1)

    return data


@pytest.fixture
def sample_returns(sample_market_data):
    """Calculate returns from market data."""
    return sample_market_data["close"].pct_change().dropna()


@pytest.fixture
def sample_assets():
    """Standard list of asset names for testing."""
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "NFLX"]


@pytest.fixture
def sample_returns_multiasset(sample_assets):
    """Multi-asset return data with realistic correlation structure."""
    import pandas as pd

    np.random.seed(42)
    n_days = 252
    n_assets = len(sample_assets)

    # Generate correlated returns
    common_factor = np.random.normal(0, 0.01, size=n_days)
    idiosyncratic = np.random.normal(0, 0.015, size=(n_days, n_assets))

    # 30% common, 70% idiosyncratic
    returns = 0.3 * common_factor[:, np.newaxis] + 0.7 * idiosyncratic

    return pd.DataFrame(returns, columns=sample_assets)


@pytest.fixture
def sample_prices(sample_returns_multiasset):
    """Price data derived from multi-asset returns."""
    import pandas as pd

    start_price = 100.0
    return start_price * np.exp(sample_returns_multiasset.cumsum())


@pytest.fixture
def sample_covariance(sample_assets):
    """Sample covariance matrix with realistic structure."""
    import pandas as pd

    np.random.seed(42)
    n = len(sample_assets)

    # Create valid PSD covariance via Cholesky
    A = np.random.randn(n, n)
    C = (A @ A.T) / n
    C = C * 0.04 + np.eye(n) * 0.01  # Scale to realistic volatility

    return pd.DataFrame(C, index=sample_assets, columns=sample_assets)


@pytest.fixture
def sample_weights(sample_assets):
    """Portfolio weights (long-only, equal-weighted)."""
    import pandas as pd

    n = len(sample_assets)
    return pd.Series([1.0 / n] * n, index=sample_assets)


@pytest.fixture
def sample_signals(sample_returns_multiasset):
    """Sample signal data (6 synthetic signals, z-scored)."""
    import pandas as pd

    signals = {}
    signal_names = ["OFI", "ERN", "VRP", "POS", "TSX", "SIF"]

    np.random.seed(42)
    for name in signal_names:
        # Random signals with autocorrelation
        raw_signal = np.random.randn(*sample_returns_multiasset.shape)

        # Add momentum
        for i in range(1, len(raw_signal)):
            raw_signal[i] = 0.7 * raw_signal[i - 1] + 0.3 * raw_signal[i]

        # Z-score
        signal_df = pd.DataFrame(raw_signal, columns=sample_returns_multiasset.columns)
        signal_df = (signal_df - signal_df.mean()) / (signal_df.std() + 1e-8)

        signals[name] = signal_df

    return signals


@pytest.fixture
def calm_market_returns():
    """Calm market: low volatility, low correlation."""
    import pandas as pd

    np.random.seed(42)
    n_days = 100
    n_assets = 15

    # Independent, low volatility
    returns = np.random.normal(0, 0.005, size=(n_days, n_assets))

    return pd.DataFrame(returns, columns=[f"Asset_{i}" for i in range(n_assets)])


@pytest.fixture
def storm_market_returns():
    """Storm market: high volatility, high correlation."""
    import pandas as pd

    np.random.seed(42)
    n_days = 100
    n_assets = 15

    # Common shock (high correlation) with high volatility
    common_shock = np.random.normal(0, 0.04, size=n_days)
    idiosyncratic = np.random.normal(0, 0.01, size=(n_days, n_assets))

    # 80% common factor
    returns = 0.8 * common_shock[:, np.newaxis] + 0.2 * idiosyncratic

    return pd.DataFrame(returns, columns=[f"Asset_{i}" for i in range(n_assets)])


@pytest.fixture
def trending_market_returns():
    """Trending market: strong upward drift."""
    import pandas as pd

    np.random.seed(42)
    n_days = 100
    n_assets = 10

    # Add drift
    time = np.arange(n_days)
    trend = 0.001 * (time / n_days)

    returns = np.random.normal(0, 0.01, size=(n_days, n_assets))
    returns += trend[:, np.newaxis]

    return pd.DataFrame(returns, columns=[f"Asset_{i}" for i in range(n_assets)])


# Edge case fixtures
@pytest.fixture
def zero_returns(sample_assets):
    """Zero returns (edge case)."""
    import pandas as pd

    n_days = 100
    return pd.DataFrame(0.0, index=range(n_days), columns=sample_assets)


@pytest.fixture
def extreme_returns(sample_assets):
    """Extreme returns with occasional large shocks."""
    import pandas as pd

    np.random.seed(42)
    n_days = 100

    returns = np.random.normal(0, 0.01, size=(n_days, len(sample_assets)))

    # Add shocks
    shock_days = [20, 50, 80]
    for day in shock_days:
        returns[day] *= 10

    return pd.DataFrame(returns, columns=sample_assets)


@pytest.fixture
def single_asset_returns():
    """Single asset returns (minimal case)."""
    import pandas as pd

    np.random.seed(42)
    n_days = 100
    returns = np.random.normal(0.0005, 0.015, size=n_days)

    return pd.DataFrame({"Asset_0": returns})


@pytest.fixture
def short_history_returns(sample_assets):
    """Very short return history (30 days)."""
    import pandas as pd

    np.random.seed(42)
    n_days = 30
    returns = np.random.normal(0, 0.01, size=(n_days, len(sample_assets)))

    return pd.DataFrame(returns, columns=sample_assets)


# ============================================================================
# Configuration Fixtures
# ============================================================================


@pytest.fixture
def default_config():
    """
    Provide default configuration for tests.

    This mirrors algo_trade/core/config.py defaults.
    """
    return {
        "VOL_TARGET": 0.10,
        "BOX_LIM": 0.25,
        "KILL_PNL": -0.05,
        "MAX_DD_KILL_SWITCH": 0.15,
        "PSR_KILL_SWITCH": 0.20,
        "TURNOVER_PEN": 0.002,
        "RIDGE_PEN": 1e-4,
        "LAMBDA_INIT": 5e-4,
        "POV_CAP": 0.08,
        "ADV_CAP": 0.10,
        "GROSS_LIM": {"Calm": 2.5, "Normal": 2.0, "Storm": 1.0},
        "NET_LIM": {"Calm": 1.0, "Normal": 0.8, "Storm": 0.4},
    }


@pytest.fixture
def optimization_params():
    """Parameters for portfolio optimization."""
    return {
        "VOL_TARGET": 0.10,
        "BOX_LIM": 0.25,
        "TURNOVER_PEN": 0.002,
        "RIDGE_PEN": 1e-4,
    }


@pytest.fixture
def signal_params():
    """Parameters for signal generation."""
    return {
        "MOM_H": 20,
        "VOL_H": 20,
        "POS_H": 60,
        "TSX_H": 30,
        "SIF_H_FAST": 5,
        "SIF_H_SLOW": 20,
    }


# ============================================================================
# Performance Metrics Fixtures
# ============================================================================


@pytest.fixture
def sample_pnl_history():
    """Sample P&L history for metric calculations."""
    np.random.seed(42)
    # Positive drift, moderate volatility
    returns = np.random.normal(0.0005, 0.01, size=252)
    return list(returns)


@pytest.fixture
def losing_pnl_history():
    """Losing P&L history (for kill switch testing)."""
    np.random.seed(42)
    # Negative drift
    returns = np.random.normal(-0.001, 0.015, size=100)
    return list(returns)


@pytest.fixture
def high_sharpe_pnl():
    """P&L history with high Sharpe ratio."""
    np.random.seed(42)
    # High return, low volatility
    returns = np.random.normal(0.002, 0.005, size=252)
    return list(returns)


# ============================================================================
# Mock Fixtures
# ============================================================================


@pytest.fixture
def mock_ibkr_client():
    """
    Mock IBKR client for testing without real broker connection.

    Returns a mock object with common IBKR client methods.
    """
    from unittest.mock import MagicMock

    mock_client = MagicMock()

    # Mock common methods
    mock_client.connect.return_value = True
    mock_client.is_connected.return_value = True
    mock_client.disconnect.return_value = None

    # Mock account info
    mock_client.get_account_info.return_value = {
        "nav": 100000.0,
        "cash": 50000.0,
        "buying_power": 200000.0,
    }

    # Mock order placement
    def place_order_side_effect(symbol, quantity, order_type, **kwargs):
        return {
            "order_id": "TEST_ORDER_123",
            "symbol": symbol,
            "quantity": quantity,
            "order_type": order_type,
            "status": "submitted",
        }

    mock_client.place_order.side_effect = place_order_side_effect

    return mock_client


# ============================================================================
# Pytest Hooks
# ============================================================================


def pytest_configure(config):
    """
    Pytest configuration hook.

    Register custom markers.
    """
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "property: Property-based tests")
    config.addinivalue_line("markers", "metamorphic: Metamorphic tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "chaos: Chaos engineering tests")
    config.addinivalue_line("markers", "performance: Performance/benchmark tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")


def pytest_collection_modifyitems(config, items):
    """
    Pytest hook to modify test collection.

    Auto-mark tests based on their location.
    """
    for item in items:
        # Auto-mark based on directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "property" in str(item.fspath):
            item.add_marker(pytest.mark.property)
        elif "metamorphic" in str(item.fspath):
            item.add_marker(pytest.mark.metamorphic)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)
        elif "chaos" in str(item.fspath):
            item.add_marker(pytest.mark.chaos)
            item.add_marker(pytest.mark.slow)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)


# ============================================================================
# Hypothesis Configuration
# ============================================================================

from hypothesis import HealthCheck, Phase, Verbosity, settings

# Register Hypothesis profiles
settings.register_profile(
    "default",
    max_examples=100,
    stateful_step_count=50,
    deadline=None,  # No deadline for complex tests
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "ci",
    max_examples=200,
    stateful_step_count=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "dev",
    max_examples=10,
    stateful_step_count=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    verbosity=Verbosity.verbose,
)

# Activate profile based on environment
import os

profile = os.getenv("HYPOTHESIS_PROFILE", "default")
settings.load_profile(profile)
