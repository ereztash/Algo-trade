"""
Unit tests for ensemble and simulation modules.

Tests:
- ensemble: Ensemble signal combination and weight management
- simulation: Price and return simulation
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock
from hypothesis import given, strategies as st, settings

from algo_trade.core.ensemble import EnsembleManager


# ============================================================================
# Tests for EnsembleManager
# ============================================================================

@pytest.mark.unit
class TestEnsembleManager:
    """Tests for ensemble signal management."""

    def test_init_default_weights(self):
        """Test initialization with default equal weights."""
        strategies = ['ofi', 'ern', 'vrp']
        ensemble = EnsembleManager(strategies)

        assert ensemble.strategies == strategies
        assert len(ensemble.weights) == 3
        assert all(w == pytest.approx(1/3) for w in ensemble.weights.values())

    def test_init_custom_weights(self):
        """Test initialization with custom weights."""
        strategies = ['ofi', 'ern', 'vrp']
        custom_weights = {'ofi': 0.5, 'ern': 0.3, 'vrp': 0.2}
        ensemble = EnsembleManager(strategies, initial_weights=custom_weights)

        assert ensemble.weights == custom_weights

    def test_init_invalid_custom_weights(self):
        """Test initialization with invalid custom weights (missing strategy)."""
        strategies = ['ofi', 'ern', 'vrp']
        invalid_weights = {'ofi': 0.5, 'ern': 0.5}  # Missing 'vrp'
        ensemble = EnsembleManager(strategies, initial_weights=invalid_weights)

        # Should fall back to equal weights
        assert len(ensemble.weights) == 3
        assert all(w == pytest.approx(1/3) for w in ensemble.weights.values())

    def test_update_weights_basic(self):
        """Test basic weight update."""
        strategies = ['ofi', 'ern']
        ensemble = EnsembleManager(strategies)

        # Add performance data
        for _ in range(25):  # Enough for 20-day window
            ensemble.update_weights({'ofi': 0.01, 'ern': 0.005})

        # OFI performed better, should have higher weight
        assert ensemble.weights['ofi'] > ensemble.weights['ern']

    def test_update_weights_normalization(self):
        """Test that weights sum to 1 after update."""
        strategies = ['ofi', 'ern', 'vrp']
        ensemble = EnsembleManager(strategies)

        for _ in range(25):
            ensemble.update_weights({'ofi': 0.01, 'ern': -0.005, 'vrp': 0.002})

        # Weights should sum to 1
        assert sum(ensemble.weights.values()) == pytest.approx(1.0)

    def test_update_weights_negative_performance(self):
        """Test weight update with negative performance."""
        strategies = ['ofi', 'ern']
        ensemble = EnsembleManager(strategies)

        # Poor performance for ern
        for _ in range(25):
            ensemble.update_weights({'ofi': 0.01, 'ern': -0.02})

        # OFI should dominate
        assert ensemble.weights['ofi'] > 0.6

    def test_update_weights_min_weight(self):
        """Test that weights don't go below minimum."""
        strategies = ['ofi', 'ern']
        ensemble = EnsembleManager(strategies)

        # Very poor performance for ern
        for _ in range(50):
            ensemble.update_weights({'ofi': 0.05, 'ern': -0.10})

        # ERN should still have minimum weight
        assert ensemble.weights['ern'] >= 0.01

    def test_get_ensemble_signal_basic(self):
        """Test basic ensemble signal combination."""
        strategies = ['ofi', 'ern']
        ensemble = EnsembleManager(strategies)

        signals = {
            'ofi': pd.Series([1.0, 2.0, 3.0]),
            'ern': pd.Series([0.5, 1.0, 1.5])
        }

        result = ensemble.get_ensemble_signal(signals)

        assert isinstance(result, pd.Series)
        assert len(result) == 3

        # With equal weights (0.5 each), should be average
        expected = pd.Series([0.75, 1.5, 2.25])
        pd.testing.assert_series_equal(result, expected)

    def test_get_ensemble_signal_weighted(self):
        """Test ensemble signal with custom weights."""
        strategies = ['ofi', 'ern']
        weights = {'ofi': 0.7, 'ern': 0.3}
        ensemble = EnsembleManager(strategies, initial_weights=weights)

        signals = {
            'ofi': pd.Series([1.0, 2.0, 3.0]),
            'ern': pd.Series([0.0, 0.0, 0.0])
        }

        result = ensemble.get_ensemble_signal(signals)

        # Should be 70% of ofi signal
        expected = pd.Series([0.7, 1.4, 2.1])
        pd.testing.assert_series_equal(result, expected, atol=1e-10)

    def test_get_ensemble_signal_missing_signal(self):
        """Test ensemble signal when one signal is missing."""
        strategies = ['ofi', 'ern', 'vrp']
        ensemble = EnsembleManager(strategies)

        signals = {
            'ofi': pd.Series([1.0, 2.0]),
            'ern': pd.Series([0.5, 1.0])
            # 'vrp' is missing
        }

        result = ensemble.get_ensemble_signal(signals)

        # Should handle gracefully
        assert isinstance(result, pd.Series)
        assert len(result) == 2

    def test_get_ensemble_signal_empty(self):
        """Test ensemble signal with empty strategies."""
        ensemble = EnsembleManager([])

        signals = {}
        result = ensemble.get_ensemble_signal(signals)

        assert isinstance(result, pd.Series)

    def test_get_weighted_signals(self):
        """Test getting current weights."""
        strategies = ['ofi', 'ern']
        weights = {'ofi': 0.6, 'ern': 0.4}
        ensemble = EnsembleManager(strategies, initial_weights=weights)

        result = ensemble.get_weighted_signals()

        assert result == weights

    def test_performance_history_tracking(self):
        """Test that performance history is tracked correctly."""
        strategies = ['ofi', 'ern']
        ensemble = EnsembleManager(strategies)

        ensemble.update_weights({'ofi': 0.01, 'ern': 0.02})
        ensemble.update_weights({'ofi': 0.015, 'ern': 0.018})

        assert len(ensemble.performance_history['ofi']) == 2
        assert len(ensemble.performance_history['ern']) == 2
        assert ensemble.performance_history['ofi'][0] == 0.01
        assert ensemble.performance_history['ern'][1] == 0.018


# ============================================================================
# Tests for Simulation Module
# ============================================================================

@pytest.mark.unit
class TestSimulation:
    """Tests for price/return simulation."""

    @patch('algo_trade.core.simulation.CFG')
    def test_simulate_prices_basic(self, mock_cfg):
        """Test basic price simulation."""
        from algo_trade.core.simulation import simulate_prices

        # Mock configuration
        mock_cfg.__getitem__ = lambda self, key: {
            'DAYS': 100,
            'N': 5,
            'MU_DAILY': 0.0005,
            'SIGMA_DAILY': 0.01,
            'START_PRICE': 100.0
        }[key]

        prices, returns = simulate_prices()

        # Check types
        assert isinstance(prices, pd.DataFrame)
        assert isinstance(returns, pd.DataFrame)

        # Check shapes
        assert prices.shape == (100, 5)
        assert returns.shape == (100, 5)

    @patch('algo_trade.core.simulation.CFG')
    def test_simulate_prices_column_names(self, mock_cfg):
        """Test that column names are correct."""
        from algo_trade.core.simulation import simulate_prices

        mock_cfg.__getitem__ = lambda self, key: {
            'DAYS': 50,
            'N': 3,
            'MU_DAILY': 0.0005,
            'SIGMA_DAILY': 0.01,
            'START_PRICE': 100.0
        }[key]

        prices, returns = simulate_prices()

        expected_cols = ['Asset_0', 'Asset_1', 'Asset_2']
        assert list(prices.columns) == expected_cols
        assert list(returns.columns) == expected_cols

    @patch('algo_trade.core.simulation.CFG')
    def test_simulate_prices_positive(self, mock_cfg):
        """Test that simulated prices are positive."""
        from algo_trade.core.simulation import simulate_prices

        mock_cfg.__getitem__ = lambda self, key: {
            'DAYS': 100,
            'N': 5,
            'MU_DAILY': 0.001,
            'SIGMA_DAILY': 0.01,
            'START_PRICE': 100.0
        }[key]

        prices, returns = simulate_prices()

        # All prices should be positive
        assert (prices > 0).all().all()

    @patch('algo_trade.core.simulation.CFG')
    def test_simulate_prices_statistical_properties(self, mock_cfg):
        """Test statistical properties of simulated returns."""
        from algo_trade.core.simulation import simulate_prices

        mock_cfg.__getitem__ = lambda self, key: {
            'DAYS': 1000,
            'N': 1,
            'MU_DAILY': 0.0,
            'SIGMA_DAILY': 0.01,
            'START_PRICE': 100.0
        }[key]

        prices, returns = simulate_prices()

        # Returns should have approximately correct mean and std
        # (with large sample size)
        assert returns.mean().iloc[0] == pytest.approx(0.0, abs=0.002)
        assert returns.std().iloc[0] == pytest.approx(0.01, abs=0.002)


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestEnsembleIntegration:
    """Integration tests for ensemble with signal generation."""

    def test_ensemble_with_real_signals(self):
        """Test ensemble manager with realistic signals."""
        np.random.seed(42)

        # Create signals
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        signals = {
            'ofi': pd.Series(np.random.randn(100) * 0.1, index=dates),
            'ern': pd.Series(np.random.randn(100) * 0.08, index=dates),
            'vrp': pd.Series(np.random.randn(100) * 0.12, index=dates),
        }

        # Initialize ensemble
        ensemble = EnsembleManager(list(signals.keys()))

        # Get combined signal
        combined = ensemble.get_ensemble_signal(signals)

        assert isinstance(combined, pd.Series)
        assert len(combined) == 100
        assert not combined.isna().any()

    def test_ensemble_adaptive_weighting(self):
        """Test that ensemble adapts weights based on performance."""
        np.random.seed(42)

        strategies = ['good', 'bad']
        ensemble = EnsembleManager(strategies)

        # Simulate performance: 'good' consistently positive, 'bad' consistently negative
        for _ in range(30):
            ensemble.update_weights({
                'good': np.random.uniform(0.01, 0.02),
                'bad': np.random.uniform(-0.02, -0.01)
            })

        # 'good' should dominate
        assert ensemble.weights['good'] > 0.7
        assert ensemble.weights['bad'] < 0.3

        # Verify weights sum to 1
        assert sum(ensemble.weights.values()) == pytest.approx(1.0)


# ============================================================================
# Property-Based Tests
# ============================================================================

@pytest.mark.property
class TestEnsembleProperties:
    """Property-based tests for ensemble."""

    @given(
        n_strategies=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=10, deadline=None)
    def test_weights_always_sum_to_one(self, n_strategies):
        """Ensemble weights should always sum to 1."""
        strategies = [f'strat_{i}' for i in range(n_strategies)]
        ensemble = EnsembleManager(strategies)

        # Random performance updates
        for _ in range(30):
            pnl = {s: np.random.uniform(-0.05, 0.05) for s in strategies}
            ensemble.update_weights(pnl)

        # Weights should sum to 1
        assert sum(ensemble.weights.values()) == pytest.approx(1.0, abs=1e-10)

    @given(
        n_strategies=st.integers(min_value=2, max_value=5),
        signal_length=st.integers(min_value=10, max_value=100)
    )
    @settings(max_examples=10, deadline=None)
    def test_ensemble_signal_deterministic(self, n_strategies, signal_length):
        """Ensemble signal should be deterministic."""
        np.random.seed(42)

        strategies = [f's{i}' for i in range(n_strategies)]
        ensemble = EnsembleManager(strategies)

        signals = {
            s: pd.Series(np.random.randn(signal_length))
            for s in strategies
        }

        result1 = ensemble.get_ensemble_signal(signals)
        result2 = ensemble.get_ensemble_signal(signals)

        pd.testing.assert_series_equal(result1, result2)
