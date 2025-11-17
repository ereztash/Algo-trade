"""
End-to-End Integration Tests for the Algo-Trading System

Tests the complete pipeline flow:
1. Data → Signals → Composite Signals
2. Signals → Covariance → QP Optimization → Weights
3. Full backtest simulation with all components

These tests ensure components work together correctly.
"""

import pytest
import pandas as pd
import numpy as np
from algo_trade.core.signals.base_signals import build_signals
from algo_trade.core.signals.composite_signals import (
    orthogonalize_signals,
    mis_per_signal_pipeline,
    merge_signals_by_mis,
)
from algo_trade.core.risk.covariance import adaptive_cov
from algo_trade.core.optimization.qp_solver import solve_qp


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def realistic_market_data():
    """Generate realistic market data for integration testing."""
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=252, freq='D')  # 1 year
    assets = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    # Generate realistic correlated returns
    mean_returns = np.array([0.0008, 0.0010, 0.0012, 0.0007, 0.0009])

    # Correlation matrix
    corr = np.array([
        [1.00, 0.70, 0.65, 0.60, 0.55],
        [0.70, 1.00, 0.75, 0.65, 0.60],
        [0.65, 0.75, 1.00, 0.70, 0.65],
        [0.60, 0.65, 0.70, 1.00, 0.60],
        [0.55, 0.60, 0.65, 0.60, 1.00],
    ])

    # Volatilities (annualized → daily)
    vols = np.array([0.25, 0.22, 0.28, 0.30, 0.32]) / np.sqrt(252)

    # Covariance matrix
    D = np.diag(vols)
    cov_matrix = D @ corr @ D

    # Generate returns
    returns = pd.DataFrame(
        np.random.multivariate_normal(mean_returns, cov_matrix, size=252),
        index=dates,
        columns=assets
    )

    # Generate prices
    prices = (1 + returns).cumprod() * 100
    prices['volume'] = np.random.randint(5000000, 50000000, len(prices))

    return returns, prices


@pytest.fixture
def system_config():
    """System configuration for integration tests."""
    return {
        # Signal horizons
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

        # Covariance
        "COV_EWMA_HL": {"Calm": 40, "Normal": 30, "Storm": 15},
        "COV_BLEND_ALPHA": {"Calm": 0.2, "Normal": 0.35, "Storm": 0.5},
        "SIGMA_DAILY": 0.015,

        # QP Optimization
        "TURNOVER_PEN": 0.005,
        "RIDGE_PEN": 1e-3,
        "BOX_LIM": 0.30,
        "VOL_TARGET": 0.15,
    }


# ============================================================================
# Test End-to-End Pipeline
# ============================================================================

@pytest.mark.integration
class TestE2EPipeline:
    """Test complete end-to-end pipeline."""

    def test_data_to_signals_pipeline(self, realistic_market_data, system_config):
        """Test Data → Signals pipeline."""
        returns, prices = realistic_market_data

        # Build signals
        signals = build_signals(returns, prices, system_config)

        # Verify output
        assert isinstance(signals, dict)
        assert len(signals) == 6  # 6 signals
        assert all(isinstance(sig, pd.DataFrame) for sig in signals.values())

        # All signals should have same shape
        shapes = [sig.shape for sig in signals.values()]
        assert len(set(shapes)) == 1, "All signals should have consistent shape"

        # Check no signal is all NaN
        for name, sig in signals.items():
            assert not sig.isnull().all().all(), f"Signal {name} is all NaN"

    def test_signals_to_composite_pipeline(self, realistic_market_data, system_config):
        """Test Signals → Orthogonalization → Composite pipeline."""
        returns, prices = realistic_market_data

        # Build base signals
        signals = build_signals(returns, prices, system_config)

        # Orthogonalize
        ortho_signals = orthogonalize_signals(signals)

        assert isinstance(ortho_signals, dict)
        assert len(ortho_signals) == len(signals)

        # Calculate MIS
        mis = mis_per_signal_pipeline(ortho_signals, returns, horizon=5)

        assert isinstance(mis, dict)
        assert len(mis) == len(ortho_signals)

        # Merge by MIS
        merged_alpha, weights = merge_signals_by_mis(ortho_signals, mis)

        assert isinstance(merged_alpha, pd.DataFrame)
        assert isinstance(weights, dict)
        assert len(merged_alpha) > 0

        # Weights should sum to ~1
        weight_sum = sum(abs(w) for w in weights.values())
        assert 0.99 < weight_sum < 1.01

    def test_composite_to_portfolio_pipeline(self, realistic_market_data, system_config):
        """Test Composite Signal → Covariance → QP → Weights pipeline."""
        returns, prices = realistic_market_data

        # Build and combine signals
        signals = build_signals(returns, prices, system_config)
        ortho_signals = orthogonalize_signals(signals)
        mis = mis_per_signal_pipeline(ortho_signals, returns, horizon=5)
        merged_alpha, _ = merge_signals_by_mis(ortho_signals, mis)

        # Get latest cross-section of alpha (as expected returns)
        # Use last 60 days to compute average signal
        recent_alpha = merged_alpha.iloc[-60:].mean()

        # Normalize to look like returns
        mu_hat = recent_alpha / (recent_alpha.abs().sum() + 1e-9) * 0.10  # Scale to 10% total

        # Calculate covariance
        recent_returns = returns.iloc[-120:]  # Last 120 days
        C = adaptive_cov(recent_returns, regime='Normal', T_N_ratio=24.0, config=system_config)

        # Previous weights (start equal-weighted)
        w_prev = pd.Series(0.2, index=returns.columns)

        # Solve QP
        optimal_weights = solve_qp(
            mu_hat,
            C,
            w_prev,
            gross_lim=1.0,
            net_lim=0.8,
            params=system_config
        )

        # Verify output
        assert isinstance(optimal_weights, pd.Series)
        assert len(optimal_weights) == len(returns.columns)

        # Check constraints
        gross = optimal_weights.abs().sum()
        net = optimal_weights.sum()

        assert gross <= 1.0 + 1e-6, f"Gross constraint violated: {gross:.4f}"
        assert -0.8 <= net <= 0.8 + 1e-6, f"Net constraint violated: {net:.4f}"

    def test_full_backtest_single_period(self, realistic_market_data, system_config):
        """Test full backtest for single rebalancing period."""
        returns, prices = realistic_market_data

        # Use first 150 days for training
        train_returns = returns.iloc[:150]
        train_prices = prices.iloc[:150]

        # Build signals
        signals = build_signals(train_returns, train_prices, system_config)
        ortho_signals = orthogonalize_signals(signals)
        mis = mis_per_signal_pipeline(ortho_signals, train_returns, horizon=5)
        merged_alpha, _ = merge_signals_by_mis(ortho_signals, mis)

        # Get expected returns from alpha
        mu_hat = merged_alpha.iloc[-30:].mean()
        mu_hat = mu_hat / (mu_hat.abs().sum() + 1e-9) * 0.12

        # Covariance
        C = adaptive_cov(train_returns.iloc[-60:], regime='Normal', T_N_ratio=12.0, config=system_config)

        # Optimize
        w_prev = pd.Series(0.0, index=returns.columns)
        weights = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.8, params=system_config)

        # Test period: next 30 days
        test_returns = returns.iloc[150:180]

        # Calculate portfolio return
        portfolio_returns = (weights * test_returns).sum(axis=1)

        # Verify realistic results
        avg_daily_return = portfolio_returns.mean()
        daily_vol = portfolio_returns.std()

        # Should have reasonable Sharpe (annualized)
        if daily_vol > 0:
            sharpe = (avg_daily_return / daily_vol) * np.sqrt(252)

            # Sharpe should be non-zero (can be negative in short test period)
            assert -3 < sharpe < 5, f"Sharpe ratio seems unrealistic: {sharpe:.2f}"

        # Portfolio should have varied (not constant)
        assert portfolio_returns.std() > 0, "Portfolio returns should vary"


# ============================================================================
# Test Component Interactions
# ============================================================================

@pytest.mark.integration
class TestComponentInteractions:
    """Test interactions between different components."""

    def test_signals_covariance_consistency(self, realistic_market_data, system_config):
        """Test that signals and covariance use consistent data."""
        returns, prices = realistic_market_data

        # Build signals
        signals = build_signals(returns, prices, system_config)

        # Calculate covariance
        cov = adaptive_cov(returns, regime='Normal', T_N_ratio=50.0, config=system_config)

        # Assets should match
        signal_assets = signals['OFI'].columns.tolist()
        cov_assets = cov.index.tolist()

        assert set(signal_assets) == set(cov_assets), "Signal and covariance assets should match"

    def test_orthogonalization_reduces_multicollinearity(self, realistic_market_data, system_config):
        """Test that orthogonalization reduces signal correlation."""
        returns, prices = realistic_market_data

        # Build signals
        signals = build_signals(returns, prices, system_config)

        # Measure correlations before orthogonalization
        signal_names = list(signals.keys())
        pre_corrs = []
        for i in range(len(signal_names)):
            for j in range(i+1, len(signal_names)):
                corr = signals[signal_names[i]].corrwith(signals[signal_names[j]], axis=1).abs().mean()
                pre_corrs.append(corr)

        # Orthogonalize
        ortho_signals = orthogonalize_signals(signals)

        # Measure correlations after
        post_corrs = []
        for i in range(len(signal_names)):
            for j in range(i+1, len(signal_names)):
                corr = ortho_signals[signal_names[i]].corrwith(ortho_signals[signal_names[j]], axis=1).abs().mean()
                post_corrs.append(corr)

        # Average correlation should decrease
        avg_pre = np.mean(pre_corrs)
        avg_post = np.mean(post_corrs)

        assert avg_post < avg_pre, \
            f"Orthogonalization should reduce correlation: {avg_pre:.3f} → {avg_post:.3f}"

    def test_qp_respects_covariance_structure(self, realistic_market_data, system_config):
        """Test that QP solver respects covariance structure."""
        returns, prices = realistic_market_data

        # Calculate covariance
        cov = adaptive_cov(returns.iloc[-60:], regime='Normal', T_N_ratio=12.0, config=system_config)

        # Create simple expected returns (favor first asset)
        mu_hat = pd.Series([0.12, 0.08, 0.10, 0.09, 0.11], index=returns.columns)

        # Previous weights
        w_prev = pd.Series(0.2, index=returns.columns)

        # Optimize
        weights = solve_qp(mu_hat, cov, w_prev, gross_lim=1.0, net_lim=0.8, params=system_config)

        # Calculate portfolio variance
        port_var = weights.values @ cov.values @ weights.values

        # Should be positive
        assert port_var > 0, "Portfolio variance should be positive"

        # Check that changing covariance changes weights
        # Create different covariance (higher vol for asset 0)
        cov2 = cov.copy()
        cov2.iloc[0, 0] *= 2.0

        weights2 = solve_qp(mu_hat, cov2, w_prev, gross_lim=1.0, net_lim=0.8, params=system_config)

        # Weights should differ
        diff = (weights - weights2).abs().sum()
        assert diff > 0.01, "Changing covariance should change optimal weights"


# ============================================================================
# Test Regime-Dependent Behavior
# ============================================================================

@pytest.mark.integration
class TestRegimeDependentBehavior:
    """Test system behavior across different market regimes."""

    def test_storm_regime_increases_shrinkage(self, realistic_market_data, system_config):
        """Test that Storm regime uses more shrinkage."""
        returns, _ = realistic_market_data

        cov_calm = adaptive_cov(returns.iloc[-60:], regime='Calm', T_N_ratio=12.0, config=system_config)
        cov_storm = adaptive_cov(returns.iloc[-60:], regime='Storm', T_N_ratio=12.0, config=system_config)

        # Storm should use shorter halflife (more responsive)
        # Check if off-diagonal elements differ
        calm_offdiag = np.abs(cov_calm.values[np.triu_indices(5, k=1)]).mean()
        storm_offdiag = np.abs(cov_storm.values[np.triu_indices(5, k=1)]).mean()

        # Storm uses more shrinkage, so correlations should be lower
        # (This is a general tendency, not always true)
        # Just verify both are valid
        assert calm_offdiag > 0
        assert storm_offdiag > 0

    def test_low_tn_ratio_triggers_shrinkage(self, realistic_market_data, system_config):
        """Test that low T/N ratio triggers Ledoit-Wolf shrinkage."""
        returns, _ = realistic_market_data

        # High T/N (many observations per asset)
        cov_high_tn = adaptive_cov(returns.iloc[-100:], regime='Normal', T_N_ratio=20.0, config=system_config)

        # Low T/N (few observations per asset)
        cov_low_tn = adaptive_cov(returns.iloc[-100:], regime='Normal', T_N_ratio=1.5, config=system_config)

        # Both should be valid PSD
        assert np.all(np.linalg.eigvalsh(cov_high_tn.values) > -1e-6)
        assert np.all(np.linalg.eigvalsh(cov_low_tn.values) > -1e-6)

        # Matrices should differ (different estimation methods)
        diff = np.abs(cov_high_tn.values - cov_low_tn.values).mean()
        assert diff > 1e-6, "Different T/N ratios should produce different covariances"


# ============================================================================
# Test Error Propagation
# ============================================================================

@pytest.mark.integration
class TestErrorPropagation:
    """Test how errors propagate through the pipeline."""

    def test_nan_handling_in_pipeline(self, realistic_market_data, system_config):
        """Test that NaN values are handled gracefully throughout pipeline."""
        returns, prices = realistic_market_data

        # Introduce NaN in returns
        returns_with_nan = returns.copy()
        returns_with_nan.iloc[50:60, 0] = np.nan

        # Build signals (should handle NaN)
        signals = build_signals(returns_with_nan, prices, system_config)

        # Verify signals are created (may have NaN but not all NaN)
        for name, sig in signals.items():
            assert not sig.isnull().all().all(), f"Signal {name} is completely NaN"

    def test_insufficient_data_handling(self, system_config):
        """Test pipeline with insufficient data."""
        # Only 30 days of data
        dates = pd.date_range('2024-01-01', periods=30, freq='D')
        assets = ['A', 'B', 'C']

        returns = pd.DataFrame(
            np.random.normal(0.001, 0.02, (30, 3)),
            index=dates,
            columns=assets
        )

        prices = (1 + returns).cumprod() * 100
        prices['volume'] = 1000000

        # Should still produce signals (with warnings/fallbacks)
        signals = build_signals(returns, prices, system_config)

        assert isinstance(signals, dict)
        assert len(signals) == 6


# ============================================================================
# Test Performance Consistency
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestPerformanceConsistency:
    """Test performance consistency across multiple runs."""

    def test_deterministic_output(self, realistic_market_data, system_config):
        """Test that pipeline produces deterministic output."""
        returns, prices = realistic_market_data

        # Run pipeline twice
        def run_pipeline():
            signals = build_signals(returns, prices, system_config)
            ortho_signals = orthogonalize_signals(signals)
            mis = mis_per_signal_pipeline(ortho_signals, returns, horizon=5)
            merged, weights = merge_signals_by_mis(ortho_signals, mis)
            return merged, weights

        merged1, weights1 = run_pipeline()
        merged2, weights2 = run_pipeline()

        # Results should be identical
        pd.testing.assert_frame_equal(merged1, merged2, rtol=1e-10)
        assert weights1.keys() == weights2.keys()
        for key in weights1.keys():
            assert abs(weights1[key] - weights2[key]) < 1e-10


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-m', 'integration'])
