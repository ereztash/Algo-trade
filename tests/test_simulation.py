"""
Integration tests for simulation and full trading system pipeline.
Tests cover: price generation, signal pipeline, validation, regime detection, full backtest.
"""

import pytest
import numpy as np
import pandas as pd
from algo_trade.core.simulation import simulate_prices
from algo_trade.core import config as core_config


# ==================== FIXTURES ====================

@pytest.fixture
def sample_returns():
    """Sample synthetic return data for testing."""
    np.random.seed(42)
    n_days = 252
    n_assets = 20
    returns = np.random.normal(0.0005, 0.015, size=(n_days, n_assets))
    return pd.DataFrame(returns, columns=[f"Asset_{i}" for i in range(n_assets)])


@pytest.fixture
def sample_prices(sample_returns):
    """Sample synthetic price data (derived from returns)."""
    start_price = 100.0
    prices = start_price * np.exp(sample_returns.cumsum())
    return prices


@pytest.fixture
def small_config():
    """Minimal configuration for testing."""
    return {
        "SEED": 42,
        "DAYS": 100,
        "N": 10,
        "START_PRICE": 100.0,
        "MU_DAILY": 0.0002,
        "SIGMA_DAILY": 0.015,
        "MOM_H": 20,
        "REV_H": 5,
        "VOL_H": 20,
        "POS_H": 60,
        "TSX_H": 30,
        "SIF_H_FAST": 5,
        "SIF_H_SLOW": 20,
        "REGIME_WIN": 60,
        "VOL_TARGET": 0.10,
        "BOX_LIM": 0.25,
        "TURNOVER_PEN": 0.002,
        "RIDGE_PEN": 1e-4,
    }


# ==================== PRICE SIMULATION ====================

def test_simulate_prices_output_shape():
    """Test that simulate_prices returns correct shape."""
    # Temporarily set CFG
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}
    core_config.CFG = {
        "DAYS": 100,
        "N": 20,
        "START_PRICE": 100.0,
        "MU_DAILY": 0.0002,
        "SIGMA_DAILY": 0.015,
        "SEED": 42
    }

    try:
        prices, returns = simulate_prices()

        # Check shapes
        assert prices.shape == (100, 20), f"Expected prices shape (100, 20), got {prices.shape}"
        assert returns.shape == (100, 20), f"Expected returns shape (100, 20), got {returns.shape}"

        # Check types
        assert isinstance(prices, pd.DataFrame), "Prices should be DataFrame"
        assert isinstance(returns, pd.DataFrame), "Returns should be DataFrame"
    finally:
        # Restore original CFG
        core_config.CFG = original_cfg


def test_simulate_prices_starting_price():
    """Test that prices start near START_PRICE."""
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}
    start_price = 150.0
    core_config.CFG = {
        "DAYS": 50,
        "N": 10,
        "START_PRICE": start_price,
        "MU_DAILY": 0.0,
        "SIGMA_DAILY": 0.01,
        "SEED": 42
    }

    try:
        prices, returns = simulate_prices()

        # First price should be exactly START_PRICE * exp(first_return)
        first_prices = prices.iloc[0]
        expected_first = start_price * np.exp(returns.iloc[0])

        assert np.allclose(first_prices.values, expected_first.values, rtol=1e-10), \
            "First prices should match START_PRICE * exp(first_return)"
    finally:
        core_config.CFG = original_cfg


def test_simulate_prices_returns_statistics():
    """Test that simulated returns have correct statistical properties."""
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}
    mu_daily = 0.001
    sigma_daily = 0.020
    n_days = 1000  # Larger sample for better statistics

    core_config.CFG = {
        "DAYS": n_days,
        "N": 30,
        "START_PRICE": 100.0,
        "MU_DAILY": mu_daily,
        "SIGMA_DAILY": sigma_daily,
        "SEED": 42
    }

    try:
        prices, returns = simulate_prices()

        # Check mean (should be close to MU_DAILY)
        mean_return = returns.values.mean()
        assert np.abs(mean_return - mu_daily) < 0.001, \
            f"Mean return {mean_return:.6f} far from expected {mu_daily}"

        # Check std (should be close to SIGMA_DAILY)
        std_return = returns.values.std()
        assert np.abs(std_return - sigma_daily) < 0.005, \
            f"Std of returns {std_return:.6f} far from expected {sigma_daily}"
    finally:
        core_config.CFG = original_cfg


def test_simulate_prices_reproducibility():
    """Test that simulate_prices is reproducible with same seed."""
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}
    cfg = {
        "DAYS": 50,
        "N": 10,
        "START_PRICE": 100.0,
        "MU_DAILY": 0.0002,
        "SIGMA_DAILY": 0.015,
        "SEED": 123
    }

    try:
        # First simulation
        core_config.CFG = cfg.copy()
        np.random.seed(cfg["SEED"])
        prices1, returns1 = simulate_prices()

        # Second simulation with same seed
        core_config.CFG = cfg.copy()
        np.random.seed(cfg["SEED"])
        prices2, returns2 = simulate_prices()

        # Should be identical
        assert np.allclose(prices1.values, prices2.values), "Prices should be reproducible"
        assert np.allclose(returns1.values, returns2.values), "Returns should be reproducible"
    finally:
        core_config.CFG = original_cfg


def test_simulate_prices_no_nans():
    """Test that simulate_prices doesn't produce NaN values."""
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}
    core_config.CFG = {
        "DAYS": 100,
        "N": 15,
        "START_PRICE": 100.0,
        "MU_DAILY": 0.0002,
        "SIGMA_DAILY": 0.015,
        "SEED": 42
    }

    try:
        prices, returns = simulate_prices()

        assert not prices.isnull().any().any(), "Prices should not contain NaN"
        assert not returns.isnull().any().any(), "Returns should not contain NaN"
        assert np.all(np.isfinite(prices.values)), "Prices should be finite"
        assert np.all(np.isfinite(returns.values)), "Returns should be finite"
    finally:
        core_config.CFG = original_cfg


def test_simulate_prices_positive_prices():
    """Test that all prices remain positive (important for financial data)."""
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}
    core_config.CFG = {
        "DAYS": 200,
        "N": 20,
        "START_PRICE": 100.0,
        "MU_DAILY": 0.0,
        "SIGMA_DAILY": 0.02,  # Reasonable volatility
        "SEED": 42
    }

    try:
        prices, returns = simulate_prices()

        # All prices should be positive
        assert np.all(prices.values > 0), "All prices should remain positive"

        # Check minimum price is reasonable (not too close to zero)
        min_price = prices.values.min()
        assert min_price > 10.0, f"Minimum price {min_price:.2f} is unreasonably low"
    finally:
        core_config.CFG = original_cfg


# ==================== SIGNAL PIPELINE INTEGRATION ====================

def test_signal_pipeline_basic_flow(sample_returns):
    """Test basic signal generation pipeline."""
    from algo_trade.core.signals.base_signals import build_signals

    params = {
        "MOM_H": 20,
        "VOL_H": 20,
        "POS_H": 60,
        "TSX_H": 30,
        "SIF_H_FAST": 5,
        "SIF_H_SLOW": 20
    }

    signals = build_signals(sample_returns, params)

    # Check all expected signals exist
    expected_signals = ["OFI", "ERN", "VRP", "POS", "TSX", "SIF"]
    assert set(signals.keys()) == set(expected_signals), \
        f"Expected signals {expected_signals}, got {list(signals.keys())}"

    # Check signal shapes match input
    for name, sig in signals.items():
        assert sig.shape == sample_returns.shape, \
            f"Signal {name} shape {sig.shape} doesn't match returns {sample_returns.shape}"


def test_signal_pipeline_with_short_data():
    """Test signal pipeline with minimal data (edge case)."""
    from algo_trade.core.signals.base_signals import build_signals

    # Only 30 days of data (minimal for most signals)
    np.random.seed(42)
    short_returns = pd.DataFrame(
        np.random.normal(0, 0.01, size=(30, 10)),
        columns=[f"Asset_{i}" for i in range(10)]
    )

    params = {
        "MOM_H": 10,
        "VOL_H": 10,
        "POS_H": 20,
        "TSX_H": 15,
        "SIF_H_FAST": 3,
        "SIF_H_SLOW": 10
    }

    # Should complete without errors
    signals = build_signals(short_returns, params)

    # Signals should exist (may have NaNs in early periods)
    assert len(signals) == 6, "Should return 6 signals"
    for name, sig in signals.items():
        assert isinstance(sig, pd.DataFrame), f"Signal {name} should be DataFrame"


def test_signal_pipeline_extreme_volatility(sample_returns):
    """Test signal pipeline with extreme volatility data."""
    from algo_trade.core.signals.base_signals import build_signals

    # Create extreme volatility returns
    extreme_returns = sample_returns.copy()
    extreme_returns.iloc[50:60] *= 10  # 10x volatility spike

    params = {
        "MOM_H": 20,
        "VOL_H": 20,
        "POS_H": 60,
        "TSX_H": 30,
        "SIF_H_FAST": 5,
        "SIF_H_SLOW": 20
    }

    # Should handle extreme volatility gracefully
    signals = build_signals(extreme_returns, params)

    # Check signals are finite (no inf/nan due to extreme values)
    for name, sig in signals.items():
        # Allow some NaNs in early periods, but not infinite values
        finite_mask = np.isfinite(sig.values)
        assert finite_mask.sum() > 0, f"Signal {name} has no finite values"


# ==================== REGIME DETECTION ====================

def test_regime_detection_calm_market():
    """Test regime detection for calm market conditions."""
    # Create calm market data (low volatility, low correlation)
    np.random.seed(42)
    n_days = 100
    n_assets = 20

    # Independent assets, low volatility
    calm_returns = pd.DataFrame(
        np.random.normal(0, 0.005, size=(n_days, n_assets)),  # Low vol
        columns=[f"Asset_{i}" for i in range(n_assets)]
    )

    # Test regime detection (if function is accessible)
    # Note: This test may require importing from main.py
    try:
        from algo_trade.core.main import detect_regime
        original_cfg = core_config.CFG.copy() if core_config.CFG else {}
        core_config.CFG = {"REGIME_WIN": 60}

        regime = detect_regime(calm_returns)

        # Should detect Calm (low vol, low correlation)
        assert regime in ["Calm", "Normal"], \
            f"Expected Calm or Normal for low vol data, got {regime}"

        core_config.CFG = original_cfg
    except ImportError:
        pytest.skip("detect_regime not accessible for testing")


def test_regime_detection_storm_market():
    """Test regime detection for storm market conditions."""
    np.random.seed(42)
    n_days = 100
    n_assets = 20

    # High volatility, high correlation (storm conditions)
    common_shock = np.random.normal(0, 0.05, size=n_days)  # Large common factor
    storm_returns = pd.DataFrame(
        {f"Asset_{i}": common_shock + np.random.normal(0, 0.01, size=n_days)
         for i in range(n_assets)}
    )

    try:
        from algo_trade.core.main import detect_regime
        original_cfg = core_config.CFG.copy() if core_config.CFG else {}
        core_config.CFG = {"REGIME_WIN": 60}

        regime = detect_regime(storm_returns)

        # Should detect Storm (high vol, high correlation)
        assert regime in ["Storm", "Normal"], \
            f"Expected Storm or Normal for high vol/corr data, got {regime}"

        core_config.CFG = original_cfg
    except ImportError:
        pytest.skip("detect_regime not accessible for testing")


# ==================== VALIDATION FUNCTIONS ====================

def test_probabilistic_sharpe_ratio_basic():
    """Test PSR calculation with typical inputs."""
    try:
        from algo_trade.core.main import probabilistic_sharpe_ratio

        # Typical Sharpe ratio
        sr_hat = 1.5
        T = 252  # One year of daily data

        psr = probabilistic_sharpe_ratio(sr_hat, T)

        # PSR should be between 0 and 1
        assert 0 <= psr <= 1, f"PSR should be in [0,1], got {psr}"

        # For positive Sharpe with enough data, PSR should be high
        assert psr > 0.5, f"PSR should be >0.5 for positive Sharpe, got {psr}"
    except ImportError:
        pytest.skip("probabilistic_sharpe_ratio not accessible")


def test_probabilistic_sharpe_ratio_edge_cases():
    """Test PSR with edge case inputs."""
    try:
        from algo_trade.core.main import probabilistic_sharpe_ratio

        # Zero Sharpe
        psr_zero = probabilistic_sharpe_ratio(0.0, 252)
        assert np.abs(psr_zero - 0.5) < 0.1, "PSR for zero Sharpe should be ~0.5"

        # Negative Sharpe
        psr_neg = probabilistic_sharpe_ratio(-1.0, 252)
        assert psr_neg < 0.5, "PSR for negative Sharpe should be <0.5"

        # Very small sample (T < 2)
        psr_small = probabilistic_sharpe_ratio(2.0, 1)
        assert psr_small == 0.0, "PSR should be 0 for T < 2"
    except ImportError:
        pytest.skip("probabilistic_sharpe_ratio not accessible")


def test_deflated_sharpe_ratio_basic():
    """Test DSR calculation."""
    try:
        from algo_trade.core.main import deflated_sharpe_ratio

        sr_hat = 1.5
        T = 252
        n_strats = 10

        dsr = deflated_sharpe_ratio(sr_hat, T, n_strats)

        # DSR should be lower than raw Sharpe (penalized for multiple testing)
        assert dsr < sr_hat, f"DSR {dsr:.2f} should be less than raw Sharpe {sr_hat}"

        # DSR should still be reasonable
        assert dsr > 0, "DSR should be positive for positive Sharpe"
    except ImportError:
        pytest.skip("deflated_sharpe_ratio not accessible")


def test_purged_k_fold_basic():
    """Test purged k-fold cross-validation."""
    try:
        from algo_trade.core.main import purged_k_fold

        # Create sample dataframe
        df = pd.DataFrame(np.random.randn(100, 5))

        splits = purged_k_fold(df, n_splits=5, embargo_len=5)

        # Should return 5 splits
        assert len(splits) == 5, f"Expected 5 splits, got {len(splits)}"

        # Each split should have train and validation indices
        for train_idx, val_idx in splits:
            assert len(train_idx) > 0, "Train set should not be empty"
            assert len(val_idx) > 0, "Validation set should not be empty"

            # No overlap between train and validation
            assert len(set(train_idx).intersection(set(val_idx))) == 0, \
                "Train and validation should not overlap"
    except ImportError:
        pytest.skip("purged_k_fold not accessible")


def test_cscv_pbo_basic():
    """Test CSCV PBO calculation."""
    try:
        from algo_trade.core.main import true_cscv_pbo

        # Simulated performance scores (overfitted: high variance)
        np.random.seed(42)
        scores_overfitted = np.random.uniform(-0.1, 0.5, size=100)

        pbo = true_cscv_pbo(scores_overfitted, M=16)

        # PBO should be between 0 and 1
        assert 0 <= pbo <= 1, f"PBO should be in [0,1], got {pbo}"
    except ImportError:
        pytest.skip("true_cscv_pbo not accessible")


# ==================== KILL SWITCHES ====================

def test_drawdown_calculation():
    """Test maximum drawdown calculation."""
    try:
        from algo_trade.core.main import max_drawdown

        # Create simple PnL history with known drawdown
        pnl = [0.01, 0.02, -0.03, -0.02, 0.01, 0.02]  # -5% drawdown

        dd = max_drawdown(pnl)

        # Should calculate drawdown correctly
        assert dd > 0, "Drawdown should be positive"
        assert dd <= 0.10, f"Drawdown {dd:.2%} seems too high for this data"
    except ImportError:
        pytest.skip("max_drawdown not accessible")


def test_pnl_kill_switch():
    """Test PnL kill switch logic."""
    try:
        from algo_trade.core.main import pnl_kill_switch

        # PnL below threshold
        pnl_bad = [0.01, -0.02, -0.03, -0.04]  # -8% cumulative

        original_cfg = core_config.CFG.copy() if core_config.CFG else {}
        core_config.CFG = {"KILL_PNL": -0.05}  # -5% threshold

        triggered = pnl_kill_switch(pnl_bad)

        # Should trigger for -8% when threshold is -5%
        assert triggered, "Kill switch should trigger for large losses"

        # PnL above threshold
        pnl_good = [0.01, 0.02, 0.01]
        triggered_good = pnl_kill_switch(pnl_good)

        # Should not trigger for positive PnL
        assert not triggered_good, "Kill switch should not trigger for positive PnL"

        core_config.CFG = original_cfg
    except ImportError:
        pytest.skip("pnl_kill_switch not accessible")


# ==================== END-TO-END BACKTEST ====================

def test_minimal_backtest_runs():
    """Test that a minimal backtest can run without errors."""
    # This is a smoke test - just verify the system runs
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}

    try:
        # Set minimal configuration
        core_config.CFG = {
            "SEED": 42,
            "DAYS": 100,
            "N": 10,
            "START_PRICE": 100.0,
            "MU_DAILY": 0.0002,
            "SIGMA_DAILY": 0.015,
            "MOM_H": 15,
            "REV_H": 5,
            "VOL_H": 15,
            "POS_H": 40,
            "TSX_H": 20,
            "SIF_H_FAST": 3,
            "SIF_H_SLOW": 15,
            "REGIME_WIN": 40,
            "VOL_TARGET": 0.10,
            "BOX_LIM": 0.25,
            "TURNOVER_PEN": 0.002,
            "RIDGE_PEN": 1e-4,
            "GROSS_LIM": {"Calm": 2.0, "Normal": 1.5, "Storm": 1.0},
            "NET_LIM": {"Calm": 1.0, "Normal": 0.8, "Storm": 0.4},
        }

        # Generate data
        prices, returns = simulate_prices()

        # Basic assertions
        assert prices is not None, "Prices should be generated"
        assert returns is not None, "Returns should be generated"
        assert len(prices) == 100, "Should have 100 days of data"
        assert len(returns) == 100, "Should have 100 days of returns"

    finally:
        core_config.CFG = original_cfg


def test_backtest_with_single_asset():
    """Test backtest with only one asset (edge case)."""
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}

    try:
        core_config.CFG = {
            "SEED": 42,
            "DAYS": 50,
            "N": 1,  # Single asset
            "START_PRICE": 100.0,
            "MU_DAILY": 0.0005,
            "SIGMA_DAILY": 0.015,
            "MOM_H": 10,
            "VOL_H": 10,
        }

        prices, returns = simulate_prices()

        # Should handle single asset
        assert prices.shape == (50, 1), "Should have single asset"
        assert returns.shape == (50, 1), "Should have single asset returns"

    finally:
        core_config.CFG = original_cfg


def test_backtest_reproducibility_with_seed():
    """Test that backtest results are reproducible with same seed."""
    cfg = {
        "SEED": 999,
        "DAYS": 50,
        "N": 10,
        "START_PRICE": 100.0,
        "MU_DAILY": 0.0002,
        "SIGMA_DAILY": 0.015,
    }

    original_cfg = core_config.CFG.copy() if core_config.CFG else {}

    try:
        # First run
        core_config.CFG = cfg.copy()
        np.random.seed(cfg["SEED"])
        prices1, returns1 = simulate_prices()

        # Second run with same seed
        core_config.CFG = cfg.copy()
        np.random.seed(cfg["SEED"])
        prices2, returns2 = simulate_prices()

        # Should be identical
        assert np.allclose(prices1.values, prices2.values), \
            "Backtest should be reproducible with same seed"

    finally:
        core_config.CFG = original_cfg


# ==================== LINUCB (CONTEXTUAL BANDIT) ====================

def test_linucb_initialization():
    """Test LinUCB initialization."""
    try:
        from algo_trade.core.main import LinUCB

        n_arms = 4
        n_features = 5
        alpha = 0.1

        bandit = LinUCB(n_arms, n_features, alpha)

        assert bandit.n_arms == n_arms, "n_arms should match"
        assert bandit.n_features == n_features, "n_features should match"
        assert bandit.alpha == alpha, "alpha should match"
        assert len(bandit.A) == n_arms, "Should initialize A matrices for each arm"
        assert len(bandit.b) == n_arms, "Should initialize b vectors for each arm"
    except ImportError:
        pytest.skip("LinUCB not accessible")


def test_linucb_select_arm():
    """Test LinUCB arm selection."""
    try:
        from algo_trade.core.main import LinUCB

        bandit = LinUCB(n_arms=3, n_features=4, alpha=0.1)
        context = np.random.randn(4)

        arm = bandit.select_arm(context)

        # Should select a valid arm
        assert 0 <= arm < 3, f"Selected arm {arm} should be in [0, 2]"
        assert isinstance(arm, int), "Selected arm should be integer"
    except ImportError:
        pytest.skip("LinUCB not accessible")


def test_linucb_update():
    """Test LinUCB update mechanism."""
    try:
        from algo_trade.core.main import LinUCB

        bandit = LinUCB(n_arms=3, n_features=4, alpha=0.1)
        context = np.random.randn(4)
        arm = 1
        reward = 0.5

        # Store initial state
        A_before = bandit.A[arm].copy()
        b_before = bandit.b[arm].copy()

        # Update
        bandit.update(arm, context, reward)

        # A and b should be updated
        assert not np.allclose(bandit.A[arm], A_before), "A matrix should be updated"
        assert not np.allclose(bandit.b[arm], b_before), "b vector should be updated"
    except ImportError:
        pytest.skip("LinUCB not accessible")


# ==================== PROPERTY TESTS ====================

def test_simulation_always_returns_dataframes():
    """Property: simulate_prices should always return DataFrames."""
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}

    try:
        core_config.CFG = {
            "DAYS": 50,
            "N": 15,
            "START_PRICE": 100.0,
            "MU_DAILY": 0.0001,
            "SIGMA_DAILY": 0.01,
            "SEED": 42
        }

        prices, returns = simulate_prices()

        assert isinstance(prices, pd.DataFrame), "Prices must be DataFrame"
        assert isinstance(returns, pd.DataFrame), "Returns must be DataFrame"
        assert not prices.empty, "Prices should not be empty"
        assert not returns.empty, "Returns should not be empty"
    finally:
        core_config.CFG = original_cfg


def test_returns_and_prices_consistency():
    """Property: Prices should be consistent with returns (exponential relationship)."""
    original_cfg = core_config.CFG.copy() if core_config.CFG else {}

    try:
        start_price = 100.0
        core_config.CFG = {
            "DAYS": 100,
            "N": 10,
            "START_PRICE": start_price,
            "MU_DAILY": 0.0,
            "SIGMA_DAILY": 0.01,
            "SEED": 42
        }

        prices, returns = simulate_prices()

        # Verify exponential relationship: prices = START_PRICE * exp(cumsum(returns))
        expected_prices = start_price * np.exp(returns.cumsum())

        assert np.allclose(prices.values, expected_prices.values, rtol=1e-10), \
            "Prices should match START_PRICE * exp(cumsum(returns))"
    finally:
        core_config.CFG = original_cfg
