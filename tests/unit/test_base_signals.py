"""
Unit tests for base_signals module.

Tests all 6 signal generation strategies:
- OFI (Order Flow Imbalance)
- ERN (Earnings Momentum)
- VRP (Volatility Risk Premium)
- POS (Position Sizing)
- TSX (Trend-Following)
- SIF (Signal Flow)
"""

import pytest
import numpy as np
import pandas as pd
from hypothesis import given, strategies as st, settings
from hypothesis.extra.pandas import data_frames, column, range_indexes

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
    """Create sample return data for testing."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    data = {
        'AAPL': np.random.randn(100) * 0.02,
        'MSFT': np.random.randn(100) * 0.015,
        'GOOGL': np.random.randn(100) * 0.018,
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def sample_prices():
    """Create sample price data for testing."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    prices = {
        'AAPL': 100 + np.random.randn(100).cumsum(),
        'MSFT': 200 + np.random.randn(100).cumsum(),
        'GOOGL': 150 + np.random.randn(100).cumsum(),
    }
    df = pd.DataFrame(prices, index=dates)
    # Add volume column for OFI signal
    df['volume'] = np.random.randint(1000000, 10000000, 100)
    return df


@pytest.fixture
def horizons():
    """Standard horizons for signals."""
    return {
        'short_h': 5,
        'medium_h': 10,
        'long_h': 20,
        'fast_h': 3,
        'slow_h': 15
    }


@pytest.fixture
def signal_params(horizons):
    """Standard signal parameters."""
    return {
        'horizons': horizons,
        'BOX_LIM': 0.25,
        'GROSS_LIM': 1.0,
        'NET_LIM': 0.5,
    }


# ============================================================================
# Tests for zscore_dynamic
# ============================================================================

@pytest.mark.unit
class TestZScoreDynamic:
    """Tests for zscore_dynamic function."""

    def test_zscore_basic(self, sample_returns):
        """Test basic z-score calculation."""
        result = zscore_dynamic(sample_returns, win_vol=10, win_mean=10)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isna().all().any()

    def test_zscore_output_range(self, sample_returns):
        """Z-scores should typically be in range [-3, 3]."""
        result = zscore_dynamic(sample_returns, win_vol=10, win_mean=10)

        # Most z-scores should be within ±3
        assert (np.abs(result) < 3).sum().sum() > 0.9 * result.size

    def test_zscore_zero_volatility(self):
        """Test handling of zero volatility."""
        # Create data with zero volatility
        df = pd.DataFrame({
            'A': [1.0] * 20,
            'B': [2.0] * 20
        })
        result = zscore_dynamic(df, win_vol=5, win_mean=5)

        assert isinstance(result, pd.DataFrame)
        # Should fill NaN with 0
        assert (result == 0).all().all()

    def test_zscore_different_windows(self, sample_returns):
        """Test with different window sizes."""
        result1 = zscore_dynamic(sample_returns, win_vol=5, win_mean=5)
        result2 = zscore_dynamic(sample_returns, win_vol=20, win_mean=20)

        # Different windows should produce different results
        assert not result1.equals(result2)


# ============================================================================
# Tests for OFI Signal
# ============================================================================

@pytest.mark.unit
class TestOFISignal:
    """Tests for Order Flow Imbalance signal."""

    def test_ofi_basic(self, sample_prices, horizons):
        """Test basic OFI signal generation."""
        result = ofi_signal(sample_prices, horizons)

        assert isinstance(result, pd.DataFrame)
        assert not result.isna().all().any()

    def test_ofi_shape(self, sample_prices, horizons):
        """OFI should preserve data shape."""
        result = ofi_signal(sample_prices, horizons)
        assert result.shape == sample_prices.shape

    def test_ofi_zero_volume_handling(self, horizons):
        """Test OFI handles zero volume gracefully."""
        df = pd.DataFrame({
            'price': [100, 101, 102, 103, 104],
            'volume': [0, 0, 0, 0, 0]
        })
        result = ofi_signal(df, horizons)

        assert isinstance(result, pd.DataFrame)
        assert not np.isinf(result.values).any()


# ============================================================================
# Tests for ERN Signal
# ============================================================================

@pytest.mark.unit
class TestERNSignal:
    """Tests for Earnings Momentum signal."""

    def test_ern_basic(self, sample_returns, horizons):
        """Test basic ERN signal generation."""
        result = ern_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isna().all().any()

    def test_ern_information_asymmetry(self, horizons):
        """Test ERN captures information asymmetry."""
        # Create data with clear short vs long trend difference
        returns = pd.DataFrame({
            'A': np.concatenate([
                np.ones(10) * 0.01,   # short-term up
                -np.ones(90) * 0.001  # long-term down
            ])
        })
        result = ern_signal(returns, horizons)

        # Early values should show positive asymmetry
        assert result['A'].iloc[20:30].mean() != 0


# ============================================================================
# Tests for VRP Signal
# ============================================================================

@pytest.mark.unit
class TestVRPSignal:
    """Tests for Volatility Risk Premium signal."""

    def test_vrp_basic(self, sample_returns, horizons):
        """Test basic VRP signal generation."""
        result = vrp_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isna().all().any()

    def test_vrp_volatility_change(self, horizons):
        """Test VRP captures volatility changes."""
        # Create data with changing volatility
        low_vol = np.random.randn(50) * 0.01
        high_vol = np.random.randn(50) * 0.05
        returns = pd.DataFrame({'A': np.concatenate([low_vol, high_vol])})

        result = vrp_signal(returns, horizons)

        # Should detect volatility change
        assert result['A'].std() > 0

    def test_vrp_negative_variance_handling(self, horizons):
        """Test VRP handles negative variance (clipping)."""
        result = vrp_signal(pd.DataFrame({'A': np.random.randn(100)}), horizons)

        # Should not have NaN or inf
        assert not np.isnan(result.values).any()
        assert not np.isinf(result.values).any()


# ============================================================================
# Tests for POS Signal
# ============================================================================

@pytest.mark.unit
class TestPOSSignal:
    """Tests for Position Sizing signal."""

    def test_pos_basic(self, sample_returns, horizons):
        """Test basic POS signal generation."""
        result = pos_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isna().all().any()

    def test_pos_mean_reversion(self, horizons):
        """Test POS captures mean-reversion."""
        # Create mean-reverting data
        returns = pd.DataFrame({
            'A': np.sin(np.linspace(0, 4*np.pi, 100)) * 0.02
        })
        result = pos_signal(returns, horizons)

        # Should produce signal
        assert result['A'].std() > 0


# ============================================================================
# Tests for TSX Signal
# ============================================================================

@pytest.mark.unit
class TestTSXSignal:
    """Tests for Trend-Following signal."""

    def test_tsx_basic(self, sample_returns, horizons):
        """Test basic TSX signal generation."""
        result = tsx_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isna().all().any()

    def test_tsx_trend_detection(self, horizons):
        """Test TSX detects trends."""
        # Create trending data
        trend_up = np.linspace(0, 0.1, 100)
        noise = np.random.randn(100) * 0.01
        returns = pd.DataFrame({'A': trend_up + noise})

        result = tsx_signal(returns, horizons)

        # Later values should be positive (uptrend detected)
        assert result['A'].iloc[-20:].mean() > 0


# ============================================================================
# Tests for SIF Signal
# ============================================================================

@pytest.mark.unit
class TestSIFSignal:
    """Tests for Signal Flow signal."""

    def test_sif_basic(self, sample_returns, horizons):
        """Test basic SIF signal generation."""
        result = sif_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isna().all().any()

    def test_sif_fast_slow_difference(self, horizons):
        """Test SIF captures fast vs slow MA difference."""
        # Create data with pattern
        returns = pd.DataFrame({
            'A': np.concatenate([
                np.ones(20) * 0.01,
                -np.ones(80) * 0.005
            ])
        })
        result = sif_signal(returns, horizons)

        # Should produce signal
        assert result['A'].std() > 0


# ============================================================================
# Tests for build_signals
# ============================================================================

@pytest.mark.unit
class TestBuildSignals:
    """Tests for build_signals function."""

    def test_build_signals_basic(self, sample_returns, sample_prices, signal_params):
        """Test building all signals."""
        result = build_signals(sample_returns, sample_prices, signal_params)

        assert isinstance(result, dict)
        # Should have all 6 signal types
        expected_signals = ['ofi', 'ern', 'vrp', 'pos', 'tsx', 'sif']
        for sig in expected_signals:
            assert sig in result
            assert isinstance(result[sig], pd.DataFrame)

    def test_build_signals_shapes(self, sample_returns, sample_prices, signal_params):
        """All signals should have same shape as input."""
        result = build_signals(sample_returns, sample_prices, signal_params)

        for sig_name, sig_df in result.items():
            if sig_name != 'ofi':  # OFI uses prices which has volume column
                assert sig_df.shape == sample_returns.shape


# ============================================================================
# Property-Based Tests
# ============================================================================

@pytest.mark.property
class TestSignalsProperties:
    """Property-based tests using Hypothesis."""

    @given(
        data=data_frames(
            columns=[column('A', dtype=float), column('B', dtype=float)],
            index=range_indexes(min_size=50, max_size=100)
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_zscore_deterministic(self, data):
        """Z-score should be deterministic."""
        result1 = zscore_dynamic(data, win_vol=5, win_mean=5)
        result2 = zscore_dynamic(data, win_vol=5, win_mean=5)

        assert result1.equals(result2)

    @given(
        returns=data_frames(
            columns=[column('A', dtype=float)],
            index=range_indexes(min_size=50, max_size=100)
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_signals_no_inf(self, returns, horizons):
        """Signals should never produce inf values."""
        signals = [
            ern_signal(returns, horizons),
            vrp_signal(returns, horizons),
            pos_signal(returns, horizons),
            tsx_signal(returns, horizons),
            sif_signal(returns, horizons)
        ]

        for sig in signals:
            assert not np.isinf(sig.values).any()
