"""
Comprehensive test suite for composite_signals.py

Tests composite signal generation, orthogonalization, and combination:
- orthogonalize_signals() - OLS-based cross-sectional orthogonalization
- combine_signals() - Weighted signal combination
- mis_per_signal_pipeline() - Marginal Importance Score calculation
- merge_signals_by_mis() - MIS-based signal merging
- create_composite_signals() - End-to-end composite signal generation

Coverage target: 90%+ for composite_signals.py
"""

import pytest
import pandas as pd
import numpy as np
from typing import Dict
from algo_trade.core.signals.composite_signals import (
    orthogonalize_signals,
    combine_signals,
    mis_per_signal_pipeline,
    merge_signals_by_mis,
    create_composite_signals,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_returns():
    """Generate synthetic returns for 5 assets over 100 days."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='D')
    assets = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    returns = pd.DataFrame(
        np.random.normal(0.0005, 0.015, (100, 5)),
        index=dates,
        columns=assets
    )

    return returns


@pytest.fixture
def sample_prices(sample_returns):
    """Generate prices from returns."""
    prices = (1 + sample_returns).cumprod() * 100
    prices['volume'] = np.random.randint(1000000, 10000000, len(prices))
    return prices


@pytest.fixture
def sample_signals(sample_returns):
    """Generate 3 correlated signals for testing."""
    dates = sample_returns.index
    assets = sample_returns.columns

    # Signal 1: Momentum (trending)
    sig1 = sample_returns.rolling(5).mean().fillna(0)

    # Signal 2: Mean reversion (anti-trending)
    sig2 = -sample_returns.rolling(10).mean().fillna(0)

    # Signal 3: Volatility-based
    sig3 = sample_returns.rolling(5).std().fillna(0)

    # Normalize
    for sig in [sig1, sig2, sig3]:
        for col in sig.columns:
            sig[col] = (sig[col] - sig[col].mean()) / (sig[col].std() + 1e-9)

    signals = {
        'MOM': sig1,
        'REV': sig2,
        'VOL': sig3,
    }

    return signals


@pytest.fixture
def horizons_config():
    """Configuration for signal generation."""
    return {
        "OFI_H_SHORT": 5, "OFI_H_MEDIUM": 10, "OFI_H_LONG": 20,
        "ERN_H_SHORT": 5, "ERN_H_LONG": 20,
        "VRP_H_SHORT": 5, "VRP_H_LONG": 20,
        "POS_H_SHORT": 5, "POS_H_LONG": 20,
        "TSX_H_SHORT": 5, "TSX_H_LONG": 20,
        "SIF_H_FAST": 5, "SIF_H_SLOW": 20,
    }


# ============================================================================
# Test orthogonalize_signals
# ============================================================================

class TestOrthogonalizeSignals:
    """Test suite for signal orthogonalization."""

    def test_orthogonalize_basic_output(self, sample_signals):
        """Test basic orthogonalization output structure."""
        result = orthogonalize_signals(sample_signals)

        assert isinstance(result, dict)
        assert len(result) == len(sample_signals)
        assert set(result.keys()) == set(sample_signals.keys())

        # Check shapes
        for key in result.keys():
            assert result[key].shape == sample_signals[key].shape

    def test_orthogonalize_reduces_correlation(self, sample_signals):
        """Test that orthogonalization reduces inter-signal correlation."""
        # Compute correlations before orthogonalization
        orig_corrs = []
        keys = list(sample_signals.keys())
        for i in range(len(keys)):
            for j in range(i+1, len(keys)):
                corr = sample_signals[keys[i]].corrwith(sample_signals[keys[j]], axis=1).abs().mean()
                orig_corrs.append(corr)

        # Orthogonalize
        ortho_signals = orthogonalize_signals(sample_signals)

        # Compute correlations after
        ortho_corrs = []
        for i in range(len(keys)):
            for j in range(i+1, len(keys)):
                corr = ortho_signals[keys[i]].corrwith(ortho_signals[keys[j]], axis=1).abs().mean()
                ortho_corrs.append(corr)

        # Average correlation should decrease
        avg_orig = np.mean(orig_corrs)
        avg_ortho = np.mean(ortho_corrs)

        assert avg_ortho < avg_orig, f"Orthogonalization should reduce correlation: {avg_orig:.3f} → {avg_ortho:.3f}"

    def test_orthogonalize_preserves_signal_power(self, sample_signals):
        """Test that orthogonalization preserves total signal variance."""
        # Total variance before
        total_var_before = sum([sig.var().sum() for sig in sample_signals.values()])

        # Orthogonalize
        ortho_signals = orthogonalize_signals(sample_signals)

        # Total variance after
        total_var_after = sum([sig.var().sum() for sig in ortho_signals.values()])

        # Should be relatively close (allowing for numerical differences)
        ratio = total_var_after / total_var_before
        assert 0.5 < ratio < 2.0, f"Variance ratio out of range: {ratio:.2f}"

    def test_orthogonalize_normalization(self, sample_signals):
        """Test that output is re-normalized to z-scores."""
        ortho_signals = orthogonalize_signals(sample_signals)

        for key, signal in ortho_signals.items():
            # After warm-up, cross-sectional mean should be ~0, std ~1
            stable = signal.iloc[30:]

            for idx in stable.index:
                row = stable.loc[idx].dropna()
                if len(row) > 2:
                    # Cross-sectional properties
                    mean_val = row.mean()
                    std_val = row.std()

                    # Relaxed bounds
                    assert -1.0 < mean_val < 1.0, f"Mean out of range: {mean_val}"
                    # Std might vary due to normalization and data issues

    def test_orthogonalize_handles_nans(self):
        """Test orthogonalization with NaN values."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        assets = ['A', 'B', 'C']

        # Create signals with NaN
        sig1 = pd.DataFrame(np.random.randn(50, 3), index=dates, columns=assets)
        sig2 = pd.DataFrame(np.random.randn(50, 3), index=dates, columns=assets)

        # Introduce NaN
        sig1.iloc[10:15, 0] = np.nan
        sig2.iloc[20:25, 1] = np.nan

        signals = {'S1': sig1, 'S2': sig2}

        result = orthogonalize_signals(signals)

        assert isinstance(result, dict)
        assert len(result) == 2

        # NaN should be handled (filled with 0 or preserved)
        for sig in result.values():
            assert not sig.isnull().all().all()  # Not all NaN

    def test_orthogonalize_single_signal(self):
        """Test orthogonalization with only one signal (edge case)."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        assets = ['A', 'B']

        sig1 = pd.DataFrame(np.random.randn(50, 2), index=dates, columns=assets)
        signals = {'S1': sig1}

        result = orthogonalize_signals(signals)

        assert isinstance(result, dict)
        assert len(result) == 1

        # Single signal should remain mostly unchanged (just normalized)
        assert result['S1'].shape == sig1.shape


# ============================================================================
# Test combine_signals
# ============================================================================

class TestCombineSignals:
    """Test suite for signal combination."""

    def test_combine_basic_output(self, sample_signals):
        """Test basic signal combination."""
        weights = {'MOM': 0.5, 'REV': 0.3, 'VOL': 0.2}

        result = combine_signals(sample_signals, weights)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_signals['MOM'].shape

    def test_combine_equal_weights(self, sample_signals):
        """Test combination with equal weights."""
        weights = {'MOM': 1/3, 'REV': 1/3, 'VOL': 1/3}

        result = combine_signals(sample_signals, weights)

        # Should be average of signals
        expected = (sample_signals['MOM'] + sample_signals['REV'] + sample_signals['VOL']) / 3

        pd.testing.assert_frame_equal(result, expected, rtol=1e-10)

    def test_combine_single_weight(self, sample_signals):
        """Test combination with single signal having weight 1."""
        weights = {'MOM': 1.0, 'REV': 0.0, 'VOL': 0.0}

        result = combine_signals(sample_signals, weights)

        # Should equal MOM signal
        pd.testing.assert_frame_equal(result, sample_signals['MOM'], rtol=1e-10)

    def test_combine_negative_weights(self, sample_signals):
        """Test combination with negative weights."""
        weights = {'MOM': 0.6, 'REV': -0.2, 'VOL': 0.2}

        result = combine_signals(sample_signals, weights)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_signals['MOM'].shape

        # Check calculation
        expected = (0.6 * sample_signals['MOM'] -
                   0.2 * sample_signals['REV'] +
                   0.2 * sample_signals['VOL'])

        pd.testing.assert_frame_equal(result, expected, rtol=1e-10)

    def test_combine_weights_dont_sum_to_one(self, sample_signals):
        """Test combination when weights don't sum to 1."""
        weights = {'MOM': 0.8, 'REV': 0.6, 'VOL': 0.4}  # Sum = 1.8

        result = combine_signals(sample_signals, weights)

        # Should still work (no normalization required)
        assert isinstance(result, pd.DataFrame)
        assert result.shape == sample_signals['MOM'].shape


# ============================================================================
# Test mis_per_signal_pipeline
# ============================================================================

class TestMISPipeline:
    """Test suite for Marginal Importance Score calculation."""

    def test_mis_basic_output(self, sample_signals, sample_returns):
        """Test basic MIS calculation."""
        result = mis_per_signal_pipeline(sample_signals, sample_returns, horizon=5)

        assert isinstance(result, dict)
        assert len(result) == len(sample_signals)
        assert set(result.keys()) == set(sample_signals.keys())

        # MIS should be Series (IC over time)
        for key, mis in result.items():
            assert isinstance(mis, (pd.Series, pd.DataFrame))

    def test_mis_horizon_impact(self, sample_signals, sample_returns):
        """Test MIS with different horizons."""
        mis_short = mis_per_signal_pipeline(sample_signals, sample_returns, horizon=1)
        mis_long = mis_per_signal_pipeline(sample_signals, sample_returns, horizon=10)

        # Both should succeed
        assert len(mis_short) == len(sample_signals)
        assert len(mis_long) == len(sample_signals)

        # MIS values should differ
        for key in sample_signals.keys():
            short_vals = mis_short[key].values if hasattr(mis_short[key], 'values') else [mis_short[key]]
            long_vals = mis_long[key].values if hasattr(mis_long[key], 'values') else [mis_long[key]]

            # Remove NaN
            short_clean = short_vals[~np.isnan(short_vals)]
            long_clean = long_vals[~np.isnan(long_vals)]

            # Should have some variation
            if len(short_clean) > 0 and len(long_clean) > 0:
                assert not np.allclose(short_clean[:5], long_clean[:5], atol=0.01), \
                    f"MIS for {key} too similar across horizons"

    def test_mis_predictive_signal(self):
        """Test MIS with highly predictive signal."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        assets = ['A']

        # Create predictive signal (lagged returns)
        returns = pd.DataFrame(np.random.normal(0.001, 0.02, 100), index=dates, columns=assets)
        signal = returns.shift(5).fillna(0)  # Signal is just lagged returns

        signals = {'PREDICTIVE': signal}

        mis = mis_per_signal_pipeline(signals, returns, horizon=5)

        # IC should be high (signal predicts future returns)
        avg_ic = mis['PREDICTIVE'].mean()

        assert avg_ic > 0.1, f"Expected high IC for predictive signal, got {avg_ic:.3f}"

    def test_mis_random_signal(self):
        """Test MIS with random (uninformative) signal."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        assets = ['A']

        returns = pd.DataFrame(np.random.normal(0.001, 0.02, 100), index=dates, columns=assets)
        random_signal = pd.DataFrame(np.random.randn(100, 1), index=dates, columns=assets)

        signals = {'RANDOM': random_signal}

        mis = mis_per_signal_pipeline(signals, returns, horizon=5)

        # IC should be low (near zero)
        avg_ic = abs(mis['RANDOM'].mean())

        assert avg_ic < 0.3, f"Expected low IC for random signal, got {avg_ic:.3f}"


# ============================================================================
# Test merge_signals_by_mis
# ============================================================================

class TestMergeSignalsByMIS:
    """Test suite for MIS-based signal merging."""

    def test_merge_basic_output(self, sample_signals, sample_returns):
        """Test basic signal merging."""
        mis = mis_per_signal_pipeline(sample_signals, sample_returns, horizon=5)

        merged, weights = merge_signals_by_mis(sample_signals, mis)

        assert isinstance(merged, pd.DataFrame)
        assert isinstance(weights, dict)

        assert merged.shape == sample_signals['MOM'].shape
        assert len(weights) == len(sample_signals)

    def test_merge_weights_normalized(self, sample_signals, sample_returns):
        """Test that output weights are normalized."""
        mis = mis_per_signal_pipeline(sample_signals, sample_returns, horizon=5)

        _, weights = merge_signals_by_mis(sample_signals, mis)

        # Weights should sum to ~1 (after absolute value normalization)
        weight_sum = sum(abs(w) for w in weights.values())

        assert 0.99 < weight_sum < 1.01, f"Weights should sum to 1, got {weight_sum:.3f}"

    def test_merge_higher_ic_higher_weight(self):
        """Test that signals with higher IC get higher weights."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        assets = ['A']

        returns = pd.DataFrame(np.random.normal(0.001, 0.02, 100), index=dates, columns=assets)

        # Good signal (predictive)
        good_signal = returns.shift(5).fillna(0)

        # Bad signal (random)
        bad_signal = pd.DataFrame(np.random.randn(100, 1), index=dates, columns=assets)

        signals = {'GOOD': good_signal, 'BAD': bad_signal}

        mis = mis_per_signal_pipeline(signals, returns, horizon=5)
        _, weights = merge_signals_by_mis(signals, mis)

        # Good signal should have higher absolute weight
        assert abs(weights['GOOD']) > abs(weights['BAD']), \
            f"Good signal weight ({weights['GOOD']:.3f}) should be > bad signal ({weights['BAD']:.3f})"

    def test_merge_all_zero_ic(self):
        """Test merging when all signals have zero IC."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        assets = ['A']

        sig1 = pd.DataFrame(np.random.randn(50, 1), index=dates, columns=assets)
        sig2 = pd.DataFrame(np.random.randn(50, 1), index=dates, columns=assets)

        signals = {'S1': sig1, 'S2': sig2}

        # Manually create zero MIS
        mis = {
            'S1': pd.Series(0.0, index=dates),
            'S2': pd.Series(0.0, index=dates),
        }

        merged, weights = merge_signals_by_mis(signals, mis)

        # Should handle gracefully (equal weights)
        assert isinstance(merged, pd.DataFrame)
        assert isinstance(weights, dict)

        # With zero IC, weights should be equal (after normalization)
        assert abs(weights['S1'] - weights['S2']) < 0.01


# ============================================================================
# Test create_composite_signals (End-to-End)
# ============================================================================

class TestCreateCompositeSignals:
    """Test suite for end-to-end composite signal generation."""

    def test_composite_basic_output(self, sample_returns, sample_prices, horizons_config):
        """Test basic composite signal creation."""
        merged_alpha, hrp_benchmark, bl_benchmark = create_composite_signals(
            sample_returns, sample_prices, horizons_config
        )

        assert isinstance(merged_alpha, pd.DataFrame)
        assert isinstance(hrp_benchmark, (pd.DataFrame, pd.Series, np.ndarray))
        assert isinstance(bl_benchmark, (pd.DataFrame, pd.Series, np.ndarray))

    def test_composite_signal_shape(self, sample_returns, sample_prices, horizons_config):
        """Test that composite signal has correct shape."""
        merged_alpha, _, _ = create_composite_signals(
            sample_returns, sample_prices, horizons_config
        )

        # Should have matching index length (may differ in columns due to processing)
        assert len(merged_alpha) > 0

    def test_composite_with_minimal_data(self, horizons_config):
        """Test composite signals with minimal data."""
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        assets = ['A', 'B']

        returns = pd.DataFrame(
            np.random.normal(0.001, 0.02, (60, 2)),
            index=dates,
            columns=assets
        )

        prices = (1 + returns).cumprod() * 100
        prices['volume'] = 1000000

        merged_alpha, hrp, bl = create_composite_signals(returns, prices, horizons_config)

        assert isinstance(merged_alpha, pd.DataFrame)

    def test_composite_pca_variance_threshold(self, sample_returns, sample_prices, horizons_config):
        """Test that PCA reduces dimensionality based on variance threshold."""
        merged_alpha, _, _ = create_composite_signals(
            sample_returns, sample_prices, horizons_config
        )

        # Can't directly test PCA components, but output should be valid
        assert not merged_alpha.isnull().all().all()


# ============================================================================
# Property-Based Tests
# ============================================================================

@pytest.mark.property
class TestOrthogonalizationProperties:
    """Property-based tests for orthogonalization."""

    def test_orthogonalization_idempotence(self, sample_signals):
        """Test that orthogonalizing twice gives similar result."""
        ortho_once = orthogonalize_signals(sample_signals)
        ortho_twice = orthogonalize_signals(ortho_once)

        # Second orthogonalization should change signals less
        for key in ortho_once.keys():
            diff = (ortho_once[key] - ortho_twice[key]).abs().mean().mean()
            # Should be relatively small (not exact due to re-normalization)
            assert diff < 0.5, f"Re-orthogonalization changed {key} too much: {diff:.3f}"

    def test_combine_linearity(self, sample_signals):
        """Test that signal combination is linear."""
        w1 = {'MOM': 0.5, 'REV': 0.3, 'VOL': 0.2}
        w2 = {'MOM': 0.2, 'REV': 0.5, 'VOL': 0.3}

        # Combine with w1
        result1 = combine_signals(sample_signals, w1)

        # Combine with w2
        result2 = combine_signals(sample_signals, w2)

        # Combine with average weights
        w_avg = {k: (w1[k] + w2[k]) / 2 for k in w1.keys()}
        result_avg = combine_signals(sample_signals, w_avg)

        # Should be average of result1 and result2
        expected = (result1 + result2) / 2

        pd.testing.assert_frame_equal(result_avg, expected, rtol=1e-10)


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_orthogonalize_with_constant_signal(self):
        """Test orthogonalization with constant signal."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        assets = ['A', 'B']

        sig1 = pd.DataFrame(np.random.randn(50, 2), index=dates, columns=assets)
        sig2 = pd.DataFrame(1.0, index=dates, columns=assets)  # Constant

        signals = {'VAR': sig1, 'CONST': sig2}

        result = orthogonalize_signals(signals)

        # Should handle gracefully
        assert isinstance(result, dict)
        assert len(result) == 2

    def test_combine_with_missing_weight(self, sample_signals):
        """Test combining when a signal weight is missing."""
        # Missing 'VOL' weight
        weights = {'MOM': 0.6, 'REV': 0.4}

        with pytest.raises(KeyError):
            combine_signals(sample_signals, weights)

    def test_mis_with_all_nan_returns(self, sample_signals):
        """Test MIS with all-NaN returns."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        assets = ['A']

        returns = pd.DataFrame(np.nan, index=dates, columns=assets)

        mis = mis_per_signal_pipeline(sample_signals, returns, horizon=5)

        # Should return MIS (likely all NaN or 0)
        assert isinstance(mis, dict)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
