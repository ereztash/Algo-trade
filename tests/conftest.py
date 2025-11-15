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

    # Load from fixtures/market_data/sample_data.csv
    # Generated using seed 5001 from seeds.yaml: fixture_seeds.market_data
    market_data_file = fixtures_dir / "market_data" / "sample_data.csv"

    if not market_data_file.exists():
        pytest.fail(f"Market data fixture not found: {market_data_file}")

    data = pd.read_csv(market_data_file)
    data["date"] = pd.to_datetime(data["date"])

    return data


@pytest.fixture
def sample_returns(sample_market_data):
    """Calculate returns from market data."""
    return sample_market_data["close"].pct_change().dropna()


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
        "LAMBDA_INIT": 5e-4,
        "POV_CAP": 0.08,
        "ADV_CAP": 0.10,
        "GROSS_LIM": {"Calm": 2.5, "Normal": 2.0, "Storm": 1.0},
        "NET_LIM": {"Calm": 1.0, "Normal": 0.8, "Storm": 0.4},
    }


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
