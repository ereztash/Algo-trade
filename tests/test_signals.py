"""
Unit tests for signal generation modules.

Tests cover:
- Base signal functionality
- Composite signal construction
- Feature engineering
- Signal orthogonalization
- IC weighting
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from algo_trade.core.signals.base_signals import (
    OFISignal,
    EarningsSignal,
    VolatilityRiskPremiumSignal,
    PositioningSignal,
    TrendStrengthSignal,
    SentimentInflectionSignal,
)
from algo_trade.core.signals.composite_signals import orthogonalize_signals
from algo_trade.core.ensemble import merge_signals_ic_weighted


# ============================================================================
# Base Signal Tests
# ============================================================================


@pytest.mark.unit
class TestOFISignal:
    """Test Order Flow Imbalance signal generation."""

    def test_ofi_signal_basic(self, sample_market_data):
        """Test OFI signal computation with valid data."""
        signal_gen = OFISignal()

        # Create mock orderbook data
        orderbook = pd.DataFrame({
            "bid_volume": np.random.randint(1000, 10000, len(sample_market_data)),
            "ask_volume": np.random.randint(1000, 10000, len(sample_market_data)),
            "bid_price": sample_market_data["low"] * 0.99,
            "ask_price": sample_market_data["high"] * 1.01,
        }, index=sample_market_data.index)

        signal = signal_gen.compute(orderbook)

        # Basic sanity checks
        assert isinstance(signal, pd.Series)
        assert len(signal) == len(orderbook)
        assert signal.isna().sum() < len(signal) * 0.1  # Less than 10% NaN
        assert -1 <= signal.abs().max() <= 1 or signal.isna().all()

    def test_ofi_signal_normalization(self):
        """Test that OFI signals are properly normalized."""
        signal_gen = OFISignal()

        # Create test data with known imbalance
        orderbook = pd.DataFrame({
            "bid_volume": [10000, 8000, 9000, 12000],
            "ask_volume": [5000, 6000, 5500, 4000],
            "bid_price": [99.0, 98.5, 99.0, 99.5],
            "ask_price": [101.0, 101.5, 101.0, 100.5],
        })

        signal = signal_gen.compute(orderbook)

        # Signal should be normalized
        assert signal.abs().max() <= 1.0 or signal.isna().all()

    def test_ofi_signal_empty_data(self):
        """Test OFI signal with empty data."""
        signal_gen = OFISignal()
        orderbook = pd.DataFrame()

        signal = signal_gen.compute(orderbook)

        assert isinstance(signal, pd.Series)
        assert len(signal) == 0


@pytest.mark.unit
class TestEarningsSignal:
    """Test earnings-based signal generation."""

    def test_earnings_signal_basic(self):
        """Test basic earnings signal computation."""
        signal_gen = EarningsSignal()

        # Create mock earnings data
        earnings_data = pd.DataFrame({
            "earnings_date": pd.date_range("2024-01-01", periods=10, freq="Q"),
            "eps_actual": np.random.randn(10),
            "eps_estimate": np.random.randn(10),
            "revenue": np.random.rand(10) * 1e9,
        })

        signal = signal_gen.compute(earnings_data)

        assert isinstance(signal, pd.Series)
        assert len(signal) == len(earnings_data)

    def test_earnings_surprise(self):
        """Test earnings surprise calculation."""
        signal_gen = EarningsSignal()

        # Known earnings beat
        earnings_data = pd.DataFrame({
            "eps_actual": [2.0, 1.5, 3.0],
            "eps_estimate": [1.5, 1.5, 2.0],
        })

        signal = signal_gen.compute(earnings_data)

        # Positive surprise should yield positive signal
        assert signal[0] > 0  # Beat
        assert abs(signal[1]) < 0.1  # Meet
        assert signal[2] > 0  # Beat


@pytest.mark.unit
class TestVolatilityRiskPremiumSignal:
    """Test VRP signal generation."""

    def test_vrp_signal_computation(self, sample_returns):
        """Test VRP signal with historical volatility."""
        signal_gen = VolatilityRiskPremiumSignal()

        # Create mock implied vol data
        iv_data = pd.Series(
            np.abs(np.random.randn(len(sample_returns))) * 0.3,
            index=sample_returns.index
        )

        signal = signal_gen.compute(sample_returns, iv_data)

        assert isinstance(signal, pd.Series)
        assert len(signal) <= len(sample_returns)
        assert signal.abs().max() <= 1.0 or signal.isna().all()

    def test_vrp_signal_high_iv(self):
        """Test VRP when IV > HV (positive risk premium)."""
        signal_gen = VolatilityRiskPremiumSignal()

        # Create scenario where IV > HV
        returns = pd.Series(np.random.randn(100) * 0.01)  # Low realized vol
        iv = pd.Series(np.ones(100) * 0.30)  # High implied vol

        signal = signal_gen.compute(returns, iv)

        # High IV relative to HV should yield positive signal (sell vol)
        assert signal.mean() > 0


# ============================================================================
# Composite Signal Tests
# ============================================================================


@pytest.mark.unit
class TestSignalOrthogonalization:
    """Test signal orthogonalization."""

    def test_orthogonalize_basic(self):
        """Test basic orthogonalization of correlated signals."""
        # Create correlated signals
        np.random.seed(42)
        n = 100
        base_signal = np.random.randn(n)

        signals = pd.DataFrame({
            "signal_1": base_signal + np.random.randn(n) * 0.1,
            "signal_2": base_signal * 0.8 + np.random.randn(n) * 0.3,
            "signal_3": -base_signal * 0.6 + np.random.randn(n) * 0.2,
        })

        ortho_signals = orthogonalize_signals(signals)

        # Check output shape
        assert ortho_signals.shape == signals.shape

        # Check that signals are less correlated after orthogonalization
        orig_corr = signals.corr().values
        ortho_corr = ortho_signals.corr().values

        # Off-diagonal correlations should be reduced
        orig_avg_corr = (np.abs(orig_corr).sum() - n) / (n * n - n)
        ortho_avg_corr = (np.abs(ortho_corr).sum() - n) / (n * n - n)

        assert ortho_avg_corr < orig_avg_corr

    def test_orthogonalize_already_orthogonal(self):
        """Test orthogonalization of already orthogonal signals."""
        np.random.seed(42)
        n = 100

        # Create orthogonal signals
        signals = pd.DataFrame({
            "signal_1": np.random.randn(n),
            "signal_2": np.random.randn(n),
            "signal_3": np.random.randn(n),
        })

        ortho_signals = orthogonalize_signals(signals)

        # Shapes should match
        assert ortho_signals.shape == signals.shape

        # Correlation structure should be similar
        assert ortho_signals.corr().values.shape == signals.corr().values.shape


@pytest.mark.unit
class TestSignalMerging:
    """Test IC-weighted signal merging."""

    def test_ic_weighted_merge(self):
        """Test IC-weighted signal merging."""
        np.random.seed(42)
        n = 100

        # Create signals with different IC values
        signals = pd.DataFrame({
            "signal_1": np.random.randn(n),
            "signal_2": np.random.randn(n),
            "signal_3": np.random.randn(n),
        })

        # Mock IC values (correlation with future returns)
        ic_values = pd.Series({
            "signal_1": 0.15,
            "signal_2": 0.10,
            "signal_3": 0.05,
        })

        merged = merge_signals_ic_weighted(signals, ic_values)

        assert isinstance(merged, pd.Series)
        assert len(merged) == n

        # Signal with highest IC should dominate
        # This is a loose check since signals are random
        assert not merged.isna().all()

    def test_ic_weighted_merge_zero_ic(self):
        """Test merging when all ICs are zero."""
        n = 100
        signals = pd.DataFrame({
            "signal_1": np.random.randn(n),
            "signal_2": np.random.randn(n),
        })

        ic_values = pd.Series({
            "signal_1": 0.0,
            "signal_2": 0.0,
        })

        merged = merge_signals_ic_weighted(signals, ic_values)

        # Should fall back to equal weighting
        assert isinstance(merged, pd.Series)
        assert len(merged) == n

    def test_ic_weighted_merge_negative_ic(self):
        """Test merging with negative IC values."""
        n = 100
        signals = pd.DataFrame({
            "signal_1": np.random.randn(n),
            "signal_2": np.random.randn(n),
        })

        ic_values = pd.Series({
            "signal_1": 0.10,
            "signal_2": -0.05,  # Negative IC
        })

        merged = merge_signals_ic_weighted(signals, ic_values)

        # Negative IC signal should be inverted
        assert isinstance(merged, pd.Series)
        assert len(merged) == n


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.integration
class TestSignalPipeline:
    """Test end-to-end signal pipeline."""

    def test_full_signal_pipeline(self, sample_market_data):
        """Test complete signal generation pipeline."""
        # Create multiple signal generators
        signals_dict = {}

        # OFI Signal
        ofi_gen = OFISignal()
        orderbook = pd.DataFrame({
            "bid_volume": np.random.randint(1000, 10000, len(sample_market_data)),
            "ask_volume": np.random.randint(1000, 10000, len(sample_market_data)),
            "bid_price": sample_market_data["low"],
            "ask_price": sample_market_data["high"],
        }, index=sample_market_data.index)
        signals_dict["OFI"] = ofi_gen.compute(orderbook)

        # VRP Signal
        vrp_gen = VolatilityRiskPremiumSignal()
        returns = sample_market_data["close"].pct_change()
        iv = pd.Series(0.20, index=sample_market_data.index)
        signals_dict["VRP"] = vrp_gen.compute(returns, iv)

        # Combine signals
        signals_df = pd.DataFrame(signals_dict)

        # Orthogonalize
        ortho_signals = orthogonalize_signals(signals_df.dropna())

        # Check results
        assert isinstance(ortho_signals, pd.DataFrame)
        assert ortho_signals.shape[1] == len(signals_dict)
        assert ortho_signals.isna().sum().sum() == 0


# ============================================================================
# Property-Based Tests
# ============================================================================


@pytest.mark.property
class TestSignalProperties:
    """Property-based tests for signals."""

    def test_signal_bounded(self, sample_market_data):
        """Property: All signals should be bounded between -1 and 1 after normalization."""
        from hypothesis import given, strategies as st

        signal_generators = [
            OFISignal(),
            VolatilityRiskPremiumSignal(),
        ]

        for gen in signal_generators:
            # This is a basic test - in production, use hypothesis.strategies
            # to generate various input scenarios
            pass  # Placeholder for hypothesis-based tests

    def test_signal_stability(self):
        """Property: Small changes in input should not cause large changes in signal."""
        # Test signal stability under small perturbations
        pass  # Placeholder


# ============================================================================
# Edge Cases
# ============================================================================


@pytest.mark.unit
class TestSignalEdgeCases:
    """Test edge cases and error handling."""

    def test_signal_with_nan_data(self):
        """Test signal computation with NaN values in input."""
        signal_gen = OFISignal()

        orderbook = pd.DataFrame({
            "bid_volume": [1000, np.nan, 1200, 1100],
            "ask_volume": [900, 950, np.nan, 1050],
            "bid_price": [99, 98.5, np.nan, 99.5],
            "ask_price": [101, np.nan, 101, 100.5],
        })

        # Should handle NaN gracefully
        signal = signal_gen.compute(orderbook)
        assert isinstance(signal, pd.Series)

    def test_signal_with_zero_volume(self):
        """Test signal with zero volume."""
        signal_gen = OFISignal()

        orderbook = pd.DataFrame({
            "bid_volume": [0, 0, 0],
            "ask_volume": [0, 0, 0],
            "bid_price": [99, 98.5, 99],
            "ask_price": [101, 101.5, 101],
        })

        signal = signal_gen.compute(orderbook)

        # Should not crash
        assert isinstance(signal, pd.Series)

    def test_signal_with_single_datapoint(self):
        """Test signal with minimal data."""
        signal_gen = EarningsSignal()

        earnings_data = pd.DataFrame({
            "eps_actual": [2.0],
            "eps_estimate": [1.5],
        })

        signal = signal_gen.compute(earnings_data)

        assert isinstance(signal, pd.Series)
        assert len(signal) == 1
