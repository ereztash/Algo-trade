"""
Comprehensive test suite for base_signals.py

Tests all 6 alpha signals (OFI, ERN, VRP, POS, TSX, SIF) with:
- Unit tests for individual signal functions
- Edge case testing (empty data, NaN values, single asset)
- Statistical properties verification (z-score normalization)
- Signal strength and direction testing
- Integration testing with build_signals()

Coverage target: 95%+ for base_signals.py
"""

import pytest
import pandas as pd
import numpy as np
from algo_trade.core.signals.base_signals import (
    zscore_dynamic,
    ofi_signal,
    ern_signal,
    vrp_signal,
    pos_signal,
    tsx_signal,
    sif_signal,
    build_signals,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_returns():
    """Generate synthetic returns for 3 assets over 100 days."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    assets = ['AAPL', 'MSFT', 'GOOGL']

    # Generate trending + mean-reverting returns
    returns = pd.DataFrame({
        'AAPL': np.random.normal(0.001, 0.02, 100) + 0.0005 * np.sin(np.arange(100) / 10),
        'MSFT': np.random.normal(0.0005, 0.015, 100) + 0.0003 * np.cos(np.arange(100) / 15),
        'GOOGL': np.random.normal(0.0008, 0.018, 100) - 0.0002 * np.sin(np.arange(100) / 8),
    }, index=dates)

    return returns


@pytest.fixture
def sample_prices(sample_returns):
    """Generate cumulative prices from returns."""
    return (1 + sample_returns).cumprod() * 100


@pytest.fixture
def sample_prices_with_volume(sample_prices):
    """Add volume column to prices."""
    prices_with_vol = sample_prices.copy()
    prices_with_vol['volume'] = np.random.randint(1000000, 10000000, len(sample_prices))
    return prices_with_vol


@pytest.fixture
def horizons_config():
    """Standard horizon configuration for testing."""
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
        "SIF_H_FAST": 5,
        "SIF_H_SLOW": 20,
    }


# ============================================================================
# Test zscore_dynamic
# ============================================================================

class TestZScoreDynamic:
    """Test suite for zscore_dynamic normalization function."""

    def test_zscore_basic(self, sample_returns):
        """Test basic z-score calculation."""
        result = zscore_dynamic(sample_returns, win_vol=10, win_mean=10)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isnull().all().any()  # Not all NaN

    def test_zscore_properties(self, sample_returns):
        """Test statistical properties of z-score."""
        result = zscore_dynamic(sample_returns, win_vol=20, win_mean=20)

        # After warm-up period, mean should be ~0 and std ~1
        stable_period = result.iloc[30:]

        for col in result.columns:
            mean_val = stable_period[col].mean()
            std_val = stable_period[col].std()

            # Relaxed bounds due to rolling windows
            assert -0.5 < mean_val < 0.5, f"Mean for {col} is {mean_val}"
            assert 0.5 < std_val < 1.5, f"Std for {col} is {std_val}"

    def test_zscore_handles_zeros(self):
        """Test handling of zero standard deviation."""
        # Create constant series
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        constant_data = pd.DataFrame({
            'A': [1.0] * 50,
            'B': [2.0] * 50,
        }, index=dates)

        result = zscore_dynamic(constant_data, win_vol=10, win_mean=10)

        # Should return zeros (or handle gracefully)
        assert not result.isnull().all().any()
        assert (result == 0).sum().sum() > 0  # Has zeros due to constant data

    def test_zscore_window_sizes(self, sample_returns):
        """Test with different window sizes."""
        # Small windows
        result_small = zscore_dynamic(sample_returns, win_vol=3, win_mean=3)
        assert result_small.shape == sample_returns.shape

        # Large windows
        result_large = zscore_dynamic(sample_returns, win_vol=50, win_mean=50)
        assert result_large.shape == sample_returns.shape

        # Different vol and mean windows
        result_diff = zscore_dynamic(sample_returns, win_vol=5, win_mean=20)
        assert result_diff.shape == sample_returns.shape


# ============================================================================
# Test OFI Signal
# ============================================================================

class TestOFISignal:
    """Test suite for Order Flow Imbalance signal."""

    def test_ofi_basic_output(self, sample_prices_with_volume):
        """Test basic OFI signal generation."""
        horizons = {"short_h": 5, "medium_h": 10, "long_h": 20}

        result = ofi_signal(sample_prices_with_volume, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape[0] == sample_prices_with_volume.shape[0]
        assert not result.isnull().all().any()

    def test_ofi_normalization(self, sample_prices_with_volume):
        """Test that OFI output is normalized (z-scored)."""
        horizons = {"short_h": 5, "medium_h": 10, "long_h": 20}

        result = ofi_signal(sample_prices_with_volume, horizons)

        # After warm-up, values should be roughly normalized
        stable = result.iloc[25:]

        for col in stable.columns:
            if col != 'volume':  # Skip volume column
                vals = stable[col].dropna()
                if len(vals) > 0:
                    # Most values should be within [-3, 3] for z-scores
                    assert (vals.abs() < 5).sum() / len(vals) > 0.95

    def test_ofi_captures_momentum(self):
        """Test that OFI captures momentum/trend."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Create strong upward trend
        uptrend = pd.DataFrame({
            'A': np.cumsum(np.ones(100) * 0.01) + np.random.normal(0, 0.001, 100),
            'volume': np.ones(100) * 1000000,
        }, index=dates)

        horizons = {"short_h": 5, "medium_h": 10, "long_h": 20}
        result = ofi_signal(uptrend, horizons)

        # In uptrend, signal should be predominantly positive (after warm-up)
        stable = result['A'].iloc[25:]
        assert stable.mean() > 0, "OFI should be positive in uptrend"

    def test_ofi_with_missing_volume(self, sample_prices):
        """Test OFI behavior when volume column is missing."""
        # Should handle gracefully (may use zeros or default behavior)
        horizons = {"short_h": 5, "medium_h": 10, "long_h": 20}

        # This may raise KeyError, which is acceptable
        with pytest.raises(KeyError):
            ofi_signal(sample_prices, horizons)


# ============================================================================
# Test ERN Signal
# ============================================================================

class TestERNSignal:
    """Test suite for Earnings Momentum signal."""

    def test_ern_basic_output(self, sample_returns):
        """Test basic ERN signal generation."""
        horizons = {"short_h": 5, "long_h": 20}

        result = ern_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isnull().all().any()

    def test_ern_information_asymmetry(self):
        """Test that ERN captures information asymmetry (short vs long momentum)."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Create scenario: recent spike after long flat period
        returns = np.zeros(100)
        returns[-10:] = 0.01  # Strong recent returns

        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"short_h": 5, "long_h": 30}
        result = ern_signal(df, horizons)

        # Last values should be positive (short > long)
        assert result['A'].iloc[-5:].mean() > 0

    def test_ern_mean_reversion_signal(self):
        """Test ERN in mean-reverting scenario."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Mean-reverting pattern
        returns = 0.01 * np.sin(np.arange(100) / 5) + np.random.normal(0, 0.001, 100)
        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"short_h": 3, "long_h": 15}
        result = ern_signal(df, horizons)

        # Signal should oscillate with the pattern
        assert result['A'].std() > 0.1  # Non-trivial variation

    def test_ern_normalization(self, sample_returns):
        """Test ERN output normalization."""
        horizons = {"short_h": 5, "long_h": 20}
        result = ern_signal(sample_returns, horizons)

        # Check z-score properties
        stable = result.iloc[25:]
        for col in stable.columns:
            vals = stable[col].dropna()
            if len(vals) > 0:
                assert (vals.abs() < 5).sum() / len(vals) > 0.90


# ============================================================================
# Test VRP Signal
# ============================================================================

class TestVRPSignal:
    """Test suite for Volatility Risk Premium signal."""

    def test_vrp_basic_output(self, sample_returns):
        """Test basic VRP signal generation."""
        horizons = {"short_h": 5, "long_h": 20}

        result = vrp_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isnull().all().any()

    def test_vrp_volatility_regime_change(self):
        """Test VRP captures volatility regime changes."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Low vol ’ High vol transition
        returns = np.concatenate([
            np.random.normal(0, 0.005, 50),  # Low volatility
            np.random.normal(0, 0.03, 50),   # High volatility
        ])

        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"short_h": 5, "long_h": 30}
        result = vrp_signal(df, horizons)

        # In high vol period, short-term vol > long-term vol
        # VRP = sqrt(long_vol) - sqrt(short_vol), so should be negative
        high_vol_period = result['A'].iloc[60:80]
        assert high_vol_period.mean() < 0, "VRP should be negative when short vol > long vol"

    def test_vrp_handles_negative_variance(self):
        """Test VRP handles edge cases with negative variance (due to numerical issues)."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')

        # Very small returns that might cause numerical issues
        tiny_returns = pd.DataFrame({
            'A': np.random.normal(0, 1e-10, 50),
        }, index=dates)

        horizons = {"short_h": 5, "long_h": 20}
        result = vrp_signal(tiny_returns, horizons)

        # Should not have NaN or inf
        assert not result.isnull().all().any()
        assert not np.isinf(result).any().any()

    def test_vrp_normalization(self, sample_returns):
        """Test VRP normalization."""
        horizons = {"short_h": 5, "long_h": 20}
        result = vrp_signal(sample_returns, horizons)

        stable = result.iloc[25:]
        for col in stable.columns:
            vals = stable[col].dropna()
            if len(vals) > 0:
                assert (vals.abs() < 5).sum() / len(vals) > 0.90


# ============================================================================
# Test POS Signal
# ============================================================================

class TestPOSSignal:
    """Test suite for Position Sizing signal."""

    def test_pos_basic_output(self, sample_returns):
        """Test basic POS signal generation."""
        horizons = {"short_h": 5, "long_h": 20}

        result = pos_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isnull().all().any()

    def test_pos_mean_reversion(self):
        """Test that POS captures mean-reversion opportunities."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Oscillating returns around zero
        returns = 0.02 * np.sin(np.arange(100) / 10)
        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"short_h": 5, "long_h": 20}
        result = pos_signal(df, horizons)

        # Signal should oscillate (opposite to current position)
        assert result['A'].std() > 0.1

    def test_pos_stable_trend(self):
        """Test POS in stable trending market."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Stable uptrend
        returns = np.ones(100) * 0.005 + np.random.normal(0, 0.001, 100)
        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"short_h": 5, "long_h": 20}
        result = pos_signal(df, horizons)

        # In stable trend, mean reversion signal should be weak
        stable = result['A'].iloc[25:]
        assert abs(stable.mean()) < 0.5  # Relatively centered


# ============================================================================
# Test TSX Signal
# ============================================================================

class TestTSXSignal:
    """Test suite for Trend-Following signal."""

    def test_tsx_basic_output(self, sample_returns):
        """Test basic TSX signal generation."""
        horizons = {"short_h": 5, "long_h": 20}

        result = tsx_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isnull().all().any()

    def test_tsx_captures_trend(self):
        """Test that TSX captures momentum trend."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Strong uptrend
        returns = 0.005 + np.random.normal(0, 0.002, 100)
        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"short_h": 5, "long_h": 20}
        result = tsx_signal(df, horizons)

        # TSX should be positive in uptrend (short_ma > long_ma)
        stable = result['A'].iloc[25:]
        assert stable.mean() > 0, "TSX should be positive in uptrend"

    def test_tsx_reversal_detection(self):
        """Test TSX detects trend reversals."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Uptrend then downtrend
        returns = np.concatenate([
            np.ones(50) * 0.01 + np.random.normal(0, 0.001, 50),
            np.ones(50) * -0.01 + np.random.normal(0, 0.001, 50),
        ])
        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"short_h": 5, "long_h": 20}
        result = tsx_signal(df, horizons)

        # First half should be positive, second half negative
        first_half = result['A'].iloc[30:50].mean()
        second_half = result['A'].iloc[70:90].mean()

        assert first_half > 0, "First half should show uptrend"
        assert second_half < 0, "Second half should show downtrend"


# ============================================================================
# Test SIF Signal
# ============================================================================

class TestSIFSignal:
    """Test suite for Signal Flow signal."""

    def test_sif_basic_output(self, sample_returns):
        """Test basic SIF signal generation."""
        horizons = {"fast_h": 5, "slow_h": 20}

        result = sif_signal(sample_returns, horizons)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_returns.shape
        assert not result.isnull().all().any()

    def test_sif_fast_slow_divergence(self):
        """Test SIF captures fast/slow MA divergence."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Recent surge after flat period
        returns = np.zeros(100)
        returns[-15:] = 0.01
        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"fast_h": 5, "slow_h": 30}
        result = sif_signal(df, horizons)

        # Last values should be positive (fast > slow)
        assert result['A'].iloc[-5:].mean() > 0

    def test_sif_crossover(self):
        """Test SIF at MA crossover points."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Oscillating pattern
        returns = 0.01 * np.sin(np.arange(100) / 8)
        df = pd.DataFrame({'A': returns}, index=dates)

        horizons = {"fast_h": 3, "slow_h": 12}
        result = sif_signal(df, horizons)

        # Signal should oscillate with crossovers
        assert result['A'].std() > 0.2


# ============================================================================
# Test build_signals Integration
# ============================================================================

class TestBuildSignals:
    """Test suite for build_signals integration function."""

    def test_build_signals_all_outputs(self, sample_returns, sample_prices_with_volume, horizons_config):
        """Test that build_signals produces all 6 signals."""
        result = build_signals(sample_returns, sample_prices_with_volume, horizons_config)

        assert isinstance(result, dict)
        assert len(result) == 6

        expected_keys = {'OFI', 'ERN', 'VRP', 'POS', 'TSX', 'SIF'}
        assert set(result.keys()) == expected_keys

    def test_build_signals_consistent_shape(self, sample_returns, sample_prices_with_volume, horizons_config):
        """Test all signals have consistent shape."""
        result = build_signals(sample_returns, sample_prices_with_volume, horizons_config)

        first_shape = None
        for name, signal in result.items():
            if first_shape is None:
                first_shape = signal.shape

            assert signal.shape == first_shape, f"Signal {name} has inconsistent shape"

    def test_build_signals_no_all_nan(self, sample_returns, sample_prices_with_volume, horizons_config):
        """Test that no signal is entirely NaN."""
        result = build_signals(sample_returns, sample_prices_with_volume, horizons_config)

        for name, signal in result.items():
            assert not signal.isnull().all().all(), f"Signal {name} is all NaN"

    def test_build_signals_with_minimal_data(self, horizons_config):
        """Test build_signals with minimal data (edge case)."""
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        returns = pd.DataFrame({
            'A': np.random.normal(0, 0.01, 30),
        }, index=dates)
        prices = (1 + returns).cumprod() * 100
        prices['volume'] = 1000000

        result = build_signals(returns, prices, horizons_config)

        assert len(result) == 6
        for signal in result.values():
            assert isinstance(signal, pd.DataFrame)

    def test_build_signals_parameter_sensitivity(self, sample_returns, sample_prices_with_volume):
        """Test build_signals with different parameter configurations."""
        # Short horizons
        short_config = {
            "OFI_H_SHORT": 2, "OFI_H_MEDIUM": 5, "OFI_H_LONG": 10,
            "ERN_H_SHORT": 2, "ERN_H_LONG": 10,
            "VRP_H_SHORT": 2, "VRP_H_LONG": 10,
            "POS_H_SHORT": 2, "POS_H_LONG": 10,
            "TSX_H_SHORT": 2, "TSX_H_LONG": 10,
            "SIF_H_FAST": 2, "SIF_H_SLOW": 10,
        }

        result_short = build_signals(sample_returns, sample_prices_with_volume, short_config)

        # Long horizons
        long_config = {
            "OFI_H_SHORT": 10, "OFI_H_MEDIUM": 20, "OFI_H_LONG": 40,
            "ERN_H_SHORT": 10, "ERN_H_LONG": 40,
            "VRP_H_SHORT": 10, "VRP_H_LONG": 40,
            "POS_H_SHORT": 10, "POS_H_LONG": 40,
            "TSX_H_SHORT": 10, "TSX_H_LONG": 40,
            "SIF_H_FAST": 10, "SIF_H_SLOW": 40,
        }

        result_long = build_signals(sample_returns, sample_prices_with_volume, long_config)

        # Both should succeed
        assert len(result_short) == 6
        assert len(result_long) == 6

        # Signals should differ due to different horizons
        for key in result_short.keys():
            short_sig = result_short[key].iloc[45:].values.flatten()
            long_sig = result_long[key].iloc[45:].values.flatten()

            # Remove NaN
            short_clean = short_sig[~np.isnan(short_sig)]
            long_clean = long_sig[~np.isnan(long_sig)]

            if len(short_clean) > 0 and len(long_clean) > 0:
                correlation = np.corrcoef(short_clean[:min(len(short_clean), len(long_clean))],
                                         long_clean[:min(len(short_clean), len(long_clean))])[0, 1]

                # Should be correlated but not identical
                assert 0.3 < abs(correlation) < 0.99, f"Signals for {key} too similar/different"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_dataframe(self):
        """Test signals with empty DataFrame."""
        empty_df = pd.DataFrame()
        horizons = {"short_h": 5, "long_h": 20}

        # Most functions should handle gracefully or raise clear error
        # Testing ERN as example
        with pytest.raises((ValueError, KeyError, IndexError)):
            ern_signal(empty_df, horizons)

    def test_single_row(self):
        """Test signals with single row of data."""
        single_row = pd.DataFrame({'A': [0.01]}, index=pd.date_range('2024-01-01', periods=1))
        horizons = {"short_h": 5, "long_h": 20}

        result = ern_signal(single_row, horizons)
        assert result.shape == single_row.shape

    def test_all_nan_column(self, sample_returns):
        """Test with column containing all NaN."""
        df_with_nan = sample_returns.copy()
        df_with_nan['NAN_COL'] = np.nan

        horizons = {"short_h": 5, "long_h": 20}
        result = ern_signal(df_with_nan, horizons)

        # Should handle gracefully
        assert 'NAN_COL' in result.columns

    def test_extreme_values(self):
        """Test with extreme return values."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        extreme = pd.DataFrame({
            'A': [0.0] * 25 + [10.0] * 25,  # Extreme jump
        }, index=dates)

        horizons = {"short_h": 5, "long_h": 20}
        result = tsx_signal(extreme, horizons)

        # Should handle without inf/nan
        assert not np.isinf(result).any().any()
        assert not result.isnull().all().any()


# ============================================================================
# Performance Tests
# ============================================================================

@pytest.mark.slow
class TestPerformance:
    """Performance tests for signal calculation."""

    def test_large_dataset_performance(self):
        """Test signal calculation on large dataset."""
        import time

        # Large dataset: 1000 days, 50 assets
        dates = pd.date_range('2020-01-01', periods=1000, freq='D')
        assets = [f'ASSET_{i}' for i in range(50)]

        np.random.seed(42)
        large_returns = pd.DataFrame(
            np.random.normal(0.0005, 0.02, (1000, 50)),
            index=dates,
            columns=assets
        )

        large_prices = (1 + large_returns).cumprod() * 100
        large_prices['volume'] = np.random.randint(1000000, 10000000, 1000)

        config = {
            "OFI_H_SHORT": 5, "OFI_H_MEDIUM": 10, "OFI_H_LONG": 20,
            "ERN_H_SHORT": 5, "ERN_H_LONG": 20,
            "VRP_H_SHORT": 5, "VRP_H_LONG": 20,
            "POS_H_SHORT": 5, "POS_H_LONG": 20,
            "TSX_H_SHORT": 5, "TSX_H_LONG": 20,
            "SIF_H_FAST": 5, "SIF_H_SLOW": 20,
        }

        start = time.time()
        result = build_signals(large_returns, large_prices, config)
        elapsed = time.time() - start

        # Should complete in reasonable time (< 5 seconds for 50k data points x 6 signals)
        assert elapsed < 5.0, f"build_signals took {elapsed:.2f}s (too slow)"
        assert len(result) == 6


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
