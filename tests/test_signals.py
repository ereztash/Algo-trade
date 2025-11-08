"""
Unit Tests for Signal Generation

Tests the 6 core signal strategies:
- OFI: Order Flow Imbalance
- ERN: Earnings Momentum
- VRP: Volatility Risk Premium
- POS: Position Sizing (mean reversion)
- TSX: Trend Following
- SIF: Signal Flow (mean reversion)
"""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from algo_trade.core.signals.base_signals import (
    zscore_dynamic,
    ofi_signal,
    ern_signal,
    vrp_signal,
    pos_signal,
    tsx_signal,
    sif_signal,
    build_signals
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_returns():
    """Generate sample returns for testing."""
    np.random.seed(42)
    n_periods = 100
    n_assets = 5

    # Generate realistic returns (2% daily vol)
    returns = pd.DataFrame(
        np.random.randn(n_periods, n_assets) * 0.02,
        columns=[f"asset_{i}" for i in range(n_assets)]
    )
    return returns


@pytest.fixture
def sample_prices():
    """Generate sample prices from returns."""
    np.random.seed(42)
    n_periods = 100
    n_assets = 5

    returns = np.random.randn(n_periods, n_assets) * 0.02
    prices = pd.DataFrame(
        100 * np.exp(np.cumsum(returns, axis=0)),
        columns=[f"asset_{i}" for i in range(n_assets)]
    )

    # Add volume column for OFI signal
    prices['volume'] = np.random.randint(1000, 10000, size=n_periods)

    return prices


@pytest.fixture
def default_horizons():
    """Default horizon parameters."""
    return {
        "short_h": 5,
        "medium_h": 10,
        "long_h": 20,
        "fast_h": 3,
        "slow_h": 15
    }


@pytest.fixture
def full_params():
    """Full parameter set for build_signals()."""
    return {
        "OFI_H_SHORT": 5,
        "OFI_H_MEDIUM": 10,
        "OFI_H_LONG": 20,
        "ERN_H_SHORT": 5,
        "ERN_H_LONG": 20,
        "VRP_H_SHORT": 5,
        "VRP_H_LONG": 20,
        "POS_H_SHORT": 5,
        "POS_H_LONG": 20,
        "TSX_H_SHORT": 5,
        "TSX_H_LONG": 20,
        "SIF_H_FAST": 3,
        "SIF_H_SLOW": 15
    }


# ============================================================================
# Test: zscore_dynamic()
# ============================================================================

def test_zscore_dynamic_basic(sample_returns):
    """Test basic zscore_dynamic calculation."""
    result = zscore_dynamic(sample_returns, win_vol=10, win_mean=10)

    # Output should have same shape as input
    assert result.shape == sample_returns.shape

    # Should not have NaN in later periods (after window)
    assert result.iloc[-20:].isna().sum().sum() == 0

    # Z-scores should be roughly centered around 0
    mean_zscore = result.iloc[-50:].mean().mean()
    assert abs(mean_zscore) < 0.5, f"Z-scores not centered: mean={mean_zscore}"


def test_zscore_dynamic_zero_std():
    """Test zscore_dynamic handles zero std deviation."""
    # Create constant series (zero std)
    df = pd.DataFrame(np.ones((50, 3)), columns=["A", "B", "C"])

    result = zscore_dynamic(df, win_vol=10, win_mean=10)

    # Should return zeros when std is zero (fillna(0))
    assert result.iloc[-10:].sum().sum() == 0


def test_zscore_dynamic_different_windows():
    """Test zscore_dynamic with different window sizes."""
    df = pd.DataFrame(np.random.randn(100, 2))

    # Short window should be more responsive
    z_short = zscore_dynamic(df, win_vol=5, win_mean=5)
    z_long = zscore_dynamic(df, win_vol=20, win_mean=20)

    # Short window should have higher variability
    std_short = z_short.iloc[-50:].std().mean()
    std_long = z_long.iloc[-50:].std().mean()

    assert std_short >= std_long * 0.8, "Short window should be more variable"


# ============================================================================
# Test: OFI Signal (Order Flow Imbalance)
# ============================================================================

def test_ofi_signal_shape(sample_prices, default_horizons):
    """Test OFI signal returns correct shape."""
    signal = ofi_signal(sample_prices, default_horizons)

    # Should match input shape (minus volume column)
    expected_shape = (sample_prices.shape[0], sample_prices.shape[1] - 1)
    assert signal.shape == expected_shape


def test_ofi_signal_no_nan(sample_prices, default_horizons):
    """Test OFI signal has no NaN in later periods."""
    signal = ofi_signal(sample_prices, default_horizons)

    # After warm-up period, should have no NaN
    warmup = default_horizons["long_h"] + 10
    assert signal.iloc[warmup:].isna().sum().sum() == 0


def test_ofi_signal_normalized(sample_prices, default_horizons):
    """Test OFI signal is approximately normalized (z-scored)."""
    signal = ofi_signal(sample_prices, default_horizons)

    # Z-scored signals should have mean H 0, std H 1
    recent_signal = signal.iloc[-50:]
    mean_abs = recent_signal.mean().abs().mean()
    std_mean = recent_signal.std().mean()

    assert mean_abs < 0.3, f"OFI signal not centered: mean={mean_abs}"
    assert 0.5 < std_mean < 1.5, f"OFI signal std unexpected: std={std_mean}"


# ============================================================================
# Test: ERN Signal (Earnings Momentum)
# ============================================================================

def test_ern_signal_shape(sample_returns, default_horizons):
    """Test ERN signal returns correct shape."""
    signal = ern_signal(sample_returns, default_horizons)
    assert signal.shape == sample_returns.shape


def test_ern_signal_information_asymmetry(sample_returns):
    """Test ERN captures information asymmetry (short MA - long MA)."""
    horizons = {"short_h": 5, "long_h": 20}
    signal = ern_signal(sample_returns, horizons)

    # Manually compute asymmetry for verification
    short_ma = sample_returns.rolling(5).mean()
    long_ma = sample_returns.rolling(20).mean()
    asymmetry = short_ma - long_ma

    # Signal should be based on this asymmetry
    # (exact match not required due to z-scoring, but correlation should be high)
    correlation = signal.iloc[-50:].corrwith(asymmetry.iloc[-50:], axis=0).mean()
    assert correlation > 0.8, f"ERN signal correlation with asymmetry: {correlation}"


def test_ern_signal_range(sample_returns, default_horizons):
    """Test ERN signal stays in reasonable range."""
    signal = ern_signal(sample_returns, default_horizons)

    # Z-scored signals should rarely exceed |3|
    extreme_values = (signal.abs() > 5).sum().sum()
    total_values = signal.shape[0] * signal.shape[1]

    assert extreme_values / total_values < 0.01, "Too many extreme values in ERN signal"


# ============================================================================
# Test: VRP Signal (Volatility Risk Premium)
# ============================================================================

def test_vrp_signal_shape(sample_returns, default_horizons):
    """Test VRP signal returns correct shape."""
    signal = vrp_signal(sample_returns, default_horizons)
    assert signal.shape == sample_returns.shape


def test_vrp_signal_volatility_based(sample_returns):
    """Test VRP is based on realized volatility difference."""
    horizons = {"short_h": 5, "long_h": 20}
    signal = vrp_signal(sample_returns, horizons)

    # Compute realized volatilities
    rv_short = sample_returns.pow(2).rolling(5).mean()
    rv_long = sample_returns.pow(2).rolling(20).mean()

    # VRP = sqrt(rv_long) - sqrt(rv_short)
    vrp_raw = np.sqrt(rv_long.clip(lower=0)) - np.sqrt(rv_short.clip(lower=0))

    # Should be correlated
    correlation = signal.iloc[-50:].corrwith(vrp_raw.iloc[-50:], axis=0).mean()
    assert correlation > 0.8, f"VRP signal correlation with volatility diff: {correlation}"


def test_vrp_signal_positive_when_vol_increases():
    """Test VRP signal is positive when volatility increases."""
    # Create returns with increasing volatility
    n_periods = 100
    vol_increasing = np.linspace(0.01, 0.05, n_periods)
    returns = pd.DataFrame(
        np.random.randn(n_periods, 1) * vol_increasing[:, np.newaxis],
        columns=["asset"]
    )

    horizons = {"short_h": 5, "long_h": 20}
    signal = vrp_signal(returns, horizons)

    # VRP should be positive in later periods (long vol > short vol)
    mean_signal_late = signal.iloc[-20:].mean().iloc[0]
    assert mean_signal_late > 0, f"VRP should be positive when vol increases: {mean_signal_late}"


# ============================================================================
# Test: POS Signal (Position Sizing / Mean Reversion)
# ============================================================================

def test_pos_signal_shape(sample_returns, default_horizons):
    """Test POS signal returns correct shape."""
    signal = pos_signal(sample_returns, default_horizons)
    assert signal.shape == sample_returns.shape


def test_pos_signal_mean_reversion(sample_returns):
    """Test POS signal captures mean reversion."""
    horizons = {"long_h": 20}
    signal = pos_signal(sample_returns, horizons)

    # POS = long_ma - current_returns (mean reversion factor)
    long_ma = sample_returns.rolling(20).mean()
    reversion = long_ma - sample_returns

    # Should be correlated
    correlation = signal.iloc[-50:].corrwith(reversion.iloc[-50:], axis=0).mean()
    assert correlation > 0.8, f"POS signal correlation with mean reversion: {correlation}"


# ============================================================================
# Test: TSX Signal (Trend Following)
# ============================================================================

def test_tsx_signal_shape(sample_returns, default_horizons):
    """Test TSX signal returns correct shape."""
    signal = tsx_signal(sample_returns, default_horizons)
    assert signal.shape == sample_returns.shape


def test_tsx_signal_trend_following(sample_returns):
    """Test TSX signal captures trends (short MA - long MA)."""
    horizons = {"short_h": 5, "long_h": 20}
    signal = tsx_signal(sample_returns, horizons)

    # TSX = short_ma - long_ma (trend indicator)
    short_ma = sample_returns.rolling(5).mean()
    long_ma = sample_returns.rolling(20).mean()
    trend = short_ma - long_ma

    # Should be correlated
    correlation = signal.iloc[-50:].corrwith(trend.iloc[-50:], axis=0).mean()
    assert correlation > 0.8, f"TSX signal correlation with trend: {correlation}"


def test_tsx_signal_positive_in_uptrend():
    """Test TSX signal is positive in uptrend."""
    # Create uptrending returns
    n_periods = 100
    trend = np.linspace(0, 0.05, n_periods)
    returns = pd.DataFrame(
        trend[:, np.newaxis] + np.random.randn(n_periods, 1) * 0.01,
        columns=["asset"]
    )

    horizons = {"short_h": 5, "long_h": 20}
    signal = tsx_signal(returns, horizons)

    # TSX should be positive in uptrend
    mean_signal = signal.iloc[-20:].mean().iloc[0]
    assert mean_signal > 0, f"TSX should be positive in uptrend: {mean_signal}"


# ============================================================================
# Test: SIF Signal (Signal Flow / Mean Reversion)
# ============================================================================

def test_sif_signal_shape(sample_returns, default_horizons):
    """Test SIF signal returns correct shape."""
    signal = sif_signal(sample_returns, default_horizons)
    assert signal.shape == sample_returns.shape


def test_sif_signal_fast_slow_difference(sample_returns):
    """Test SIF signal is based on fast - slow MA."""
    horizons = {"fast_h": 3, "slow_h": 15}
    signal = sif_signal(sample_returns, horizons)

    # SIF = fast_ma - slow_ma
    fast_ma = sample_returns.rolling(3).mean()
    slow_ma = sample_returns.rolling(15).mean()
    flow = fast_ma - slow_ma

    # Should be correlated
    correlation = signal.iloc[-50:].corrwith(flow.iloc[-50:], axis=0).mean()
    assert correlation > 0.8, f"SIF signal correlation with fast-slow: {correlation}"


# ============================================================================
# Test: build_signals() Integration
# ============================================================================

def test_build_signals_returns_all_six(sample_returns, sample_prices, full_params):
    """Test build_signals returns all 6 signal types."""
    signals = build_signals(sample_returns, sample_prices, full_params)

    # Should have all 6 signals
    assert len(signals) == 6
    assert set(signals.keys()) == {"OFI", "ERN", "VRP", "POS", "TSX", "SIF"}


def test_build_signals_consistent_shapes(sample_returns, sample_prices, full_params):
    """Test all signals have consistent shapes."""
    signals = build_signals(sample_returns, sample_prices, full_params)

    # All signals should have same number of periods
    n_periods = sample_returns.shape[0]
    for name, signal in signals.items():
        assert signal.shape[0] == n_periods, f"{name} has wrong number of periods"


def test_build_signals_no_inf(sample_returns, sample_prices, full_params):
    """Test signals don't contain inf values."""
    signals = build_signals(sample_returns, sample_prices, full_params)

    for name, signal in signals.items():
        assert not np.isinf(signal).any().any(), f"{name} contains inf values"


def test_build_signals_with_missing_params():
    """Test build_signals raises error with missing parameters."""
    returns = pd.DataFrame(np.random.randn(50, 3))
    prices = pd.DataFrame(np.random.randn(50, 3))

    # Missing some parameters
    incomplete_params = {
        "OFI_H_SHORT": 5,
        "OFI_H_MEDIUM": 10,
        # Missing other params...
    }

    with pytest.raises(KeyError):
        build_signals(returns, prices, incomplete_params)


# ============================================================================
# Test: Edge Cases
# ============================================================================

def test_signals_with_zero_returns():
    """Test signals handle zero returns gracefully."""
    # All zeros
    returns = pd.DataFrame(np.zeros((50, 3)), columns=["A", "B", "C"])
    horizons = {"short_h": 5, "long_h": 20}

    # Should not crash
    signal_ern = ern_signal(returns, horizons)
    signal_vrp = vrp_signal(returns, horizons)
    signal_tsx = tsx_signal(returns, horizons)

    # All should be zero or very close
    assert signal_ern.abs().sum().sum() < 0.01
    assert signal_vrp.abs().sum().sum() < 0.01
    assert signal_tsx.abs().sum().sum() < 0.01


def test_signals_with_single_asset():
    """Test signals work with single asset."""
    returns = pd.DataFrame(np.random.randn(100, 1), columns=["asset"])
    horizons = {"short_h": 5, "long_h": 20}

    signal = ern_signal(returns, horizons)

    assert signal.shape == (100, 1)
    assert signal.iloc[-50:].isna().sum().sum() == 0


def test_signals_with_extreme_volatility():
    """Test signals handle extreme volatility."""
    # Very high volatility
    returns = pd.DataFrame(np.random.randn(100, 3) * 0.5, columns=["A", "B", "C"])
    horizons = {"short_h": 5, "long_h": 20}

    signal_vrp = vrp_signal(returns, horizons)

    # Should still be finite
    assert np.isfinite(signal_vrp.iloc[-50:]).all().all()

    # Should still be roughly normalized
    std_mean = signal_vrp.iloc[-50:].std().mean()
    assert 0.3 < std_mean < 3.0, f"VRP signal std with extreme vol: {std_mean}"


# ============================================================================
# Test: Signal Properties
# ============================================================================

def test_all_signals_are_stationary():
    """Test that all signals are approximately stationary (z-scored)."""
    np.random.seed(123)
    returns = pd.DataFrame(np.random.randn(200, 3) * 0.02)
    prices = pd.DataFrame(100 * np.exp(np.cumsum(returns.values, axis=0)))
    prices['volume'] = np.random.randint(1000, 10000, size=200)

    horizons = {"short_h": 5, "medium_h": 10, "long_h": 20, "fast_h": 3, "slow_h": 15}

    signals = {
        "ERN": ern_signal(returns, horizons),
        "VRP": vrp_signal(returns, horizons),
        "POS": pos_signal(returns, horizons),
        "TSX": tsx_signal(returns, horizons),
        "SIF": sif_signal(returns, horizons),
    }

    for name, signal in signals.items():
        # Check stationarity via mean and std
        recent = signal.iloc[-100:]
        mean_abs = recent.mean().abs().mean()
        std_mean = recent.std().mean()

        assert mean_abs < 0.5, f"{name} not stationary: mean={mean_abs}"
        assert 0.5 < std_mean < 2.0, f"{name} std unexpected: std={std_mean}"


def test_signals_correlation_structure():
    """Test that signals have reasonable cross-correlation."""
    np.random.seed(456)
    returns = pd.DataFrame(np.random.randn(200, 1) * 0.02, columns=["asset"])
    prices = pd.DataFrame(100 * np.exp(np.cumsum(returns.values, axis=0)))
    prices['volume'] = np.random.randint(1000, 10000, size=200)

    horizons = {"short_h": 5, "long_h": 20}

    # Generate multiple signals on same data
    ern = ern_signal(returns, horizons).iloc[-100:, 0]
    vrp = vrp_signal(returns, horizons).iloc[-100:, 0]
    tsx = tsx_signal(returns, horizons).iloc[-100:, 0]

    # Signals should not be perfectly correlated (diverse strategies)
    corr_ern_vrp = ern.corr(vrp)
    corr_ern_tsx = ern.corr(tsx)

    assert abs(corr_ern_vrp) < 0.95, f"ERN and VRP too correlated: {corr_ern_vrp}"
    assert abs(corr_ern_tsx) < 0.95, f"ERN and TSX too correlated: {corr_ern_tsx}"


# ============================================================================
# Integration Test: Full Pipeline
# ============================================================================

def test_full_signal_pipeline():
    """Integration test: Generate signals for realistic multi-asset portfolio."""
    np.random.seed(999)

    # Generate realistic multi-asset data
    n_periods = 250  # ~1 year daily
    n_assets = 10

    returns = pd.DataFrame(
        np.random.randn(n_periods, n_assets) * 0.015,
        columns=[f"asset_{i}" for i in range(n_assets)]
    )

    prices = pd.DataFrame(
        100 * np.exp(np.cumsum(returns.values, axis=0)),
        columns=[f"asset_{i}" for i in range(n_assets)]
    )
    prices['volume'] = np.random.randint(5000, 50000, size=n_periods)

    params = {
        "OFI_H_SHORT": 5,
        "OFI_H_MEDIUM": 10,
        "OFI_H_LONG": 20,
        "ERN_H_SHORT": 5,
        "ERN_H_LONG": 20,
        "VRP_H_SHORT": 5,
        "VRP_H_LONG": 20,
        "POS_H_SHORT": 5,
        "POS_H_LONG": 20,
        "TSX_H_SHORT": 5,
        "TSX_H_LONG": 20,
        "SIF_H_FAST": 3,
        "SIF_H_SLOW": 15
    }

    # Build all signals
    signals = build_signals(returns, prices, params)

    # Validate all signals
    assert len(signals) == 6

    for name, signal in signals.items():
        # Correct shape
        assert signal.shape == (n_periods, n_assets), f"{name} wrong shape"

        # No NaN in recent data
        assert signal.iloc[-100:].isna().sum().sum() == 0, f"{name} has NaN"

        # No inf
        assert not np.isinf(signal).any().any(), f"{name} has inf"

        # Reasonable range (z-scored)
        extreme_ratio = (signal.abs() > 5).sum().sum() / (signal.shape[0] * signal.shape[1])
        assert extreme_ratio < 0.05, f"{name} too many extreme values: {extreme_ratio:.2%}"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
