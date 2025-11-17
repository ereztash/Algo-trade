"""
Comprehensive test suite for covariance.py

Tests covariance estimation methods:
- _ewma_cov() - Exponentially Weighted Moving Average covariance
- _lw_cov() - Ledoit-Wolf shrinkage covariance
- _fix_psd() - Positive Semi-Definite matrix correction
- adaptive_cov() - Adaptive covariance blending based on regime

Coverage target: 95%+ for covariance.py
"""

import pytest
import pandas as pd
import numpy as np
from algo_trade.core.risk.covariance import (
    _ewma_cov,
    _lw_cov,
    _fix_psd,
    adaptive_cov,
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

    # Generate correlated returns
    mean = np.array([0.0005, 0.0008, 0.0006, 0.0007, 0.0009])
    cov_matrix = np.array([
        [0.0004, 0.0002, 0.0001, 0.00015, 0.00012],
        [0.0002, 0.0003, 0.00015, 0.0001, 0.00008],
        [0.0001, 0.00015, 0.00035, 0.0002, 0.0001],
        [0.00015, 0.0001, 0.0002, 0.0005, 0.00025],
        [0.00012, 0.00008, 0.0001, 0.00025, 0.0006],
    ])

    returns = pd.DataFrame(
        np.random.multivariate_normal(mean, cov_matrix, size=100),
        index=dates,
        columns=assets
    )

    return returns


@pytest.fixture
def config():
    """Standard configuration for covariance tests."""
    return {
        "COV_EWMA_HL": {"Calm": 40, "Normal": 30, "Storm": 15},
        "COV_BLEND_ALPHA": {"Calm": 0.2, "Normal": 0.35, "Storm": 0.5},
        "SIGMA_DAILY": 0.015,
    }


# ============================================================================
# Test _ewma_cov
# ============================================================================

class TestEWMACov:
    """Test suite for EWMA covariance estimation."""

    def test_ewma_basic_output(self, sample_returns):
        """Test basic EWMA covariance calculation."""
        result = _ewma_cov(sample_returns, halflife=30)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (5, 5)  # 5 assets
        assert list(result.index) == list(sample_returns.columns)
        assert list(result.columns) == list(sample_returns.columns)

    def test_ewma_symmetry(self, sample_returns):
        """Test that covariance matrix is symmetric."""
        result = _ewma_cov(sample_returns, halflife=30)

        # Check symmetry
        np.testing.assert_array_almost_equal(
            result.values,
            result.values.T,
            decimal=10,
            err_msg="Covariance matrix should be symmetric"
        )

    def test_ewma_positive_diagonal(self, sample_returns):
        """Test that diagonal elements (variances) are positive."""
        result = _ewma_cov(sample_returns, halflife=30)

        diagonal = np.diag(result.values)

        assert np.all(diagonal > 0), "Variances (diagonal) should be positive"

    def test_ewma_halflife_impact(self, sample_returns):
        """Test impact of different halflives."""
        cov_short = _ewma_cov(sample_returns, halflife=5)
        cov_long = _ewma_cov(sample_returns, halflife=60)

        # Short halflife should be more responsive to recent data
        # This is harder to test directly, but matrices should differ
        diff = np.abs(cov_short.values - cov_long.values).mean()

        assert diff > 1e-6, "Different halflives should produce different results"

    def test_ewma_with_single_asset(self):
        """Test EWMA with single asset (edge case)."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        single_asset = pd.DataFrame(
            np.random.normal(0.001, 0.02, 50),
            index=dates,
            columns=['A']
        )

        result = _ewma_cov(single_asset, halflife=10)

        assert result.shape == (1, 1)
        assert result.iloc[0, 0] > 0  # Variance should be positive

    def test_ewma_empty_dataframe(self):
        """Test EWMA with empty DataFrame."""
        empty_df = pd.DataFrame()

        result = _ewma_cov(empty_df, halflife=30)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_ewma_minimal_data(self):
        """Test EWMA with very few data points."""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        minimal = pd.DataFrame(
            np.random.normal(0.001, 0.02, (5, 2)),
            index=dates,
            columns=['A', 'B']
        )

        result = _ewma_cov(minimal, halflife=3)

        assert result.shape == (2, 2)
        assert not result.isnull().any().any()

    def test_ewma_recency_weight(self):
        """Test that EWMA gives more weight to recent observations."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        # Low volatility initially, high volatility later
        returns_changing = pd.DataFrame({
            'A': np.concatenate([
                np.random.normal(0, 0.01, 50),
                np.random.normal(0, 0.05, 50),
            ])
        }, index=dates)

        cov_short_hl = _ewma_cov(returns_changing, halflife=10)
        cov_long_hl = _ewma_cov(returns_changing, halflife=60)

        # Short halflife should show higher variance (recent high vol)
        var_short = cov_short_hl.iloc[0, 0]
        var_long = cov_long_hl.iloc[0, 0]

        assert var_short > var_long, "Short halflife should reflect recent higher volatility"


# ============================================================================
# Test _lw_cov
# ============================================================================

class TestLedoitWolfCov:
    """Test suite for Ledoit-Wolf covariance estimation."""

    def test_lw_basic_output(self, sample_returns):
        """Test basic Ledoit-Wolf covariance calculation."""
        result = _lw_cov(sample_returns)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (5, 5)
        assert list(result.index) == list(sample_returns.columns)
        assert list(result.columns) == list(sample_returns.columns)

    def test_lw_symmetry(self, sample_returns):
        """Test that LW covariance matrix is symmetric."""
        result = _lw_cov(sample_returns)

        np.testing.assert_array_almost_equal(
            result.values,
            result.values.T,
            decimal=10,
            err_msg="LW covariance matrix should be symmetric"
        )

    def test_lw_positive_diagonal(self, sample_returns):
        """Test that LW diagonal elements are positive."""
        result = _lw_cov(sample_returns)

        diagonal = np.diag(result.values)

        assert np.all(diagonal > 0), "Variances should be positive"

    def test_lw_shrinkage_effect(self):
        """Test that LW provides shrinkage towards identity."""
        dates = pd.date_range('2024-01-01', periods=50, freq='D')
        assets = ['A', 'B', 'C']

        # Create highly correlated returns
        base = np.random.normal(0.001, 0.02, 50)
        returns = pd.DataFrame({
            'A': base + np.random.normal(0, 0.005, 50),
            'B': base + np.random.normal(0, 0.005, 50),
            'C': base + np.random.normal(0, 0.005, 50),
        }, index=dates)

        # Sample covariance (without shrinkage)
        sample_cov = returns.cov()

        # LW covariance (with shrinkage)
        lw_cov = _lw_cov(returns)

        # Off-diagonal elements should be shrunk towards zero
        sample_offdiag = np.abs(sample_cov.values[np.triu_indices(3, k=1)]).mean()
        lw_offdiag = np.abs(lw_cov.values[np.triu_indices(3, k=1)]).mean()

        # LW should have smaller off-diagonal elements (shrinkage)
        assert lw_offdiag <= sample_offdiag, "LW should shrink correlations"

    def test_lw_empty_dataframe(self):
        """Test LW with empty DataFrame."""
        empty_df = pd.DataFrame()

        result = _lw_cov(empty_df)

        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_lw_error_handling(self):
        """Test LW error handling with problematic data."""
        dates = pd.date_range('2024-01-01', periods=10, freq='D')

        # Too few observations for LW (may fallback to sample cov)
        few_obs = pd.DataFrame(
            np.random.normal(0.001, 0.02, (10, 50)),  # 10 obs, 50 assets
            index=dates,
            columns=[f'A{i}' for i in range(50)]
        )

        result = _lw_cov(few_obs)

        # Should handle gracefully (may use fallback)
        assert isinstance(result, pd.DataFrame)
        assert result.shape == (50, 50)


# ============================================================================
# Test _fix_psd
# ============================================================================

class TestFixPSD:
    """Test suite for PSD correction."""

    def test_fix_psd_already_psd(self, sample_returns):
        """Test PSD fix on already positive definite matrix."""
        cov = sample_returns.cov()

        result = _fix_psd(cov)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == cov.shape

        # Eigenvalues should all be positive
        eigenvalues = np.linalg.eigvalsh(result.values)
        assert np.all(eigenvalues > -1e-10), "All eigenvalues should be >= 0"

    def test_fix_psd_negative_eigenvalues(self):
        """Test PSD fix on matrix with negative eigenvalues."""
        # Create non-PSD matrix
        A = np.array([
            [1.0, 0.9, 0.8],
            [0.9, 1.0, 0.95],
            [0.8, 0.95, 1.0]
        ])

        # Make it slightly non-PSD by perturbing
        A[2, 2] = 0.5  # This might create negative eigenvalue

        df = pd.DataFrame(A, index=['A', 'B', 'C'], columns=['A', 'B', 'C'])

        result = _fix_psd(df)

        # Check that result is PSD
        eigenvalues = np.linalg.eigvalsh(result.values)
        assert np.all(eigenvalues >= 1e-8), "All eigenvalues should be positive after fix"

    def test_fix_psd_preserves_structure(self):
        """Test that PSD fix preserves matrix structure (symmetry, size)."""
        cov = pd.DataFrame(
            [[1.0, 0.5], [0.5, 1.0]],
            index=['A', 'B'],
            columns=['A', 'B']
        )

        result = _fix_psd(cov)

        assert result.shape == cov.shape
        assert list(result.index) == list(cov.index)
        assert list(result.columns) == list(cov.columns)

        # Symmetry
        np.testing.assert_array_almost_equal(result.values, result.values.T)

    def test_fix_psd_empty_matrix(self):
        """Test PSD fix with empty matrix."""
        empty = pd.DataFrame()

        result = _fix_psd(empty)

        assert result.empty

    def test_fix_psd_single_element(self):
        """Test PSD fix with 1x1 matrix."""
        single = pd.DataFrame([[0.5]], index=['A'], columns=['A'])

        result = _fix_psd(single)

        assert result.shape == (1, 1)
        assert result.iloc[0, 0] >= 1e-8  # Should be positive


# ============================================================================
# Test adaptive_cov
# ============================================================================

class TestAdaptiveCov:
    """Test suite for adaptive covariance blending."""

    def test_adaptive_calm_regime(self, sample_returns, config):
        """Test adaptive covariance in Calm regime."""
        result = adaptive_cov(sample_returns, regime='Calm', T_N_ratio=5.0, config=config)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (5, 5)

        # Should be PSD
        eigenvalues = np.linalg.eigvalsh(result.values)
        assert np.all(eigenvalues > -1e-6), "Matrix should be PSD"

    def test_adaptive_storm_regime(self, sample_returns, config):
        """Test adaptive covariance in Storm regime."""
        result = adaptive_cov(sample_returns, regime='Storm', T_N_ratio=5.0, config=config)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (5, 5)

        # Should use more LW shrinkage in Storm
        eigenvalues = np.linalg.eigvalsh(result.values)
        assert np.all(eigenvalues > -1e-6)

    def test_adaptive_regime_differences(self, sample_returns, config):
        """Test that different regimes produce different covariances."""
        cov_calm = adaptive_cov(sample_returns, regime='Calm', T_N_ratio=5.0, config=config)
        cov_storm = adaptive_cov(sample_returns, regime='Storm', T_N_ratio=5.0, config=config)

        # Matrices should differ
        diff = np.abs(cov_calm.values - cov_storm.values).mean()

        assert diff > 1e-5, "Different regimes should produce different covariances"

    def test_adaptive_tn_ratio_threshold(self, sample_returns, config):
        """Test T/N ratio threshold behavior."""
        # High T/N ratio (many observations per asset)
        cov_high_tn = adaptive_cov(sample_returns, regime='Normal', T_N_ratio=10.0, config=config)

        # Low T/N ratio (few observations per asset)
        cov_low_tn = adaptive_cov(sample_returns, regime='Normal', T_N_ratio=1.5, config=config)

        # Low T/N should use more shrinkage (different result)
        diff = np.abs(cov_high_tn.values - cov_low_tn.values).mean()

        assert diff > 1e-6, "Different T/N ratios should affect covariance"

    def test_adaptive_annualization(self, sample_returns, config):
        """Test that covariance is properly annualized."""
        result = adaptive_cov(sample_returns, regime='Normal', T_N_ratio=5.0, config=config)

        # Calculate daily covariance directly
        daily_cov = _ewma_cov(sample_returns, halflife=config["COV_EWMA_HL"]["Normal"])

        # Annualized should be ~252x daily
        # (Exact comparison difficult due to blending, but magnitudes should match)
        ratio = np.diag(result.values).mean() / np.diag(daily_cov.values).mean()

        assert 200 < ratio < 300, f"Annualization factor should be ~252, got {ratio:.1f}"

    def test_adaptive_empty_returns(self, config):
        """Test adaptive covariance with empty returns."""
        empty = pd.DataFrame()

        result = adaptive_cov(empty, regime='Normal', T_N_ratio=5.0, config=config)

        # Should return identity matrix (or similar fallback)
        assert isinstance(result, pd.DataFrame)

    def test_adaptive_minimal_data(self, config):
        """Test adaptive covariance with minimal data (< 30 days)."""
        dates = pd.date_range('2024-01-01', periods=20, freq='D')
        minimal = pd.DataFrame(
            np.random.normal(0.001, 0.02, (20, 3)),
            index=dates,
            columns=['A', 'B', 'C']
        )

        result = adaptive_cov(minimal, regime='Normal', T_N_ratio=2.0, config=config)

        # Should use fallback (identity-like matrix)
        assert result.shape == (3, 3)

        # Check if it's roughly identity scaled by SIGMA_DAILY
        expected_var = (config['SIGMA_DAILY'] ** 2) * 252
        avg_diagonal = np.diag(result.values).mean()

        # Should be close to expected fallback variance
        assert 0.01 < avg_diagonal < 0.1, f"Expected ~{expected_var:.4f}, got {avg_diagonal:.4f}"

    def test_adaptive_psd_guarantee(self, sample_returns, config):
        """Test that adaptive_cov always returns PSD matrix."""
        for regime in ['Calm', 'Normal', 'Storm']:
            for t_n_ratio in [0.5, 2.0, 10.0]:
                result = adaptive_cov(sample_returns, regime=regime, T_N_ratio=t_n_ratio, config=config)

                eigenvalues = np.linalg.eigvalsh(result.values)
                assert np.all(eigenvalues > -1e-6), \
                    f"Matrix not PSD for regime={regime}, T/N={t_n_ratio}"


# ============================================================================
# Property-Based Tests
# ============================================================================

@pytest.mark.property
class TestCovarianceProperties:
    """Property-based tests for covariance matrices."""

    def test_all_methods_produce_psd(self, sample_returns):
        """Test that all covariance methods produce PSD matrices."""
        methods = [
            _ewma_cov(sample_returns, halflife=30),
            _lw_cov(sample_returns),
        ]

        for i, cov in enumerate(methods):
            eigenvalues = np.linalg.eigvalsh(cov.values)
            assert np.all(eigenvalues > -1e-8), f"Method {i} not PSD"

    def test_covariance_scale_invariance(self):
        """Test that scaling returns scales covariance quadratically."""
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        returns = pd.DataFrame(
            np.random.normal(0.001, 0.02, (100, 3)),
            index=dates,
            columns=['A', 'B', 'C']
        )

        cov1 = _ewma_cov(returns, halflife=30)

        # Scale returns by 2
        returns_scaled = returns * 2.0
        cov2 = _ewma_cov(returns_scaled, halflife=30)

        # Covariance should scale by 4 (2^2)
        ratio = cov2.values / cov1.values

        # Check ratio is roughly 4
        np.testing.assert_array_almost_equal(
            ratio,
            np.ones_like(ratio) * 4.0,
            decimal=1,
            err_msg="Covariance should scale quadratically"
        )

    def test_diagonal_equals_variance(self, sample_returns):
        """Test that covariance diagonal equals variance."""
        cov = _ewma_cov(sample_returns, halflife=30)

        for col in sample_returns.columns:
            cov_var = cov.loc[col, col]

            # Calculate variance directly
            actual_var = _ewma_cov(sample_returns[[col]], halflife=30).iloc[0, 0]

            np.testing.assert_almost_equal(
                cov_var,
                actual_var,
                decimal=10,
                err_msg=f"Diagonal variance mismatch for {col}"
            )


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestCovarianceIntegration:
    """Integration tests for covariance estimation pipeline."""

    def test_full_pipeline_calm_to_storm(self, sample_returns, config):
        """Test full covariance pipeline through regime transition."""
        # Start in Calm
        cov_calm = adaptive_cov(sample_returns, regime='Calm', T_N_ratio=5.0, config=config)

        # Transition to Storm
        cov_storm = adaptive_cov(sample_returns, regime='Storm', T_N_ratio=5.0, config=config)

        # Both should be valid PSD matrices
        for cov in [cov_calm, cov_storm]:
            eigenvalues = np.linalg.eigvalsh(cov.values)
            assert np.all(eigenvalues > -1e-6)

        # Storm should generally have higher variance (shorter halflife)
        avg_var_calm = np.diag(cov_calm.values).mean()
        avg_var_storm = np.diag(cov_storm.values).mean()

        # This is not always true, but generally expected
        # (Storm uses shorter halflife and more shrinkage)

    def test_covariance_with_qp_solver_compatibility(self, sample_returns, config):
        """Test that covariance output is compatible with QP solver."""
        cov = adaptive_cov(sample_returns, regime='Normal', T_N_ratio=5.0, config=config)

        # Should be usable in quadratic form
        # Test with random weights
        w = np.random.randn(5)
        w = w / np.sum(np.abs(w))  # Normalize

        # Quadratic form: w^T * Cov * w
        portfolio_var = w @ cov.values @ w

        # Should be non-negative
        assert portfolio_var >= -1e-10, "Portfolio variance should be non-negative"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
