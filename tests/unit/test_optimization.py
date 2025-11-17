"""
Unit tests for optimization modules.

Tests:
- qp_solver: Quadratic programming portfolio optimization
- hrp: Hierarchical Risk Parity
- black_litterman: Black-Litterman model
- bayesian_optimization: Hyperparameter optimization
"""

import pytest
import numpy as np
import pandas as pd
from hypothesis import given, strategies as st, settings, assume

from algo_trade.core.optimization.qp_solver import solve_qp


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_portfolio_data():
    """Create sample portfolio optimization data."""
    np.random.seed(42)
    n_assets = 5

    # Expected returns
    mu = pd.Series(
        np.random.randn(n_assets) * 0.1,
        index=[f'Asset_{i}' for i in range(n_assets)]
    )

    # Covariance matrix (ensure PSD)
    A = np.random.randn(n_assets, n_assets)
    C = pd.DataFrame(
        A @ A.T / n_assets,
        index=mu.index,
        columns=mu.index
    )

    # Previous weights
    w_prev = pd.Series(
        np.zeros(n_assets),
        index=mu.index
    )

    return mu, C, w_prev


@pytest.fixture
def qp_params():
    """Standard QP solver parameters."""
    return {
        'TURNOVER_PEN': 0.002,
        'RIDGE_PEN': 1e-4,
        'BOX_LIM': 0.25,
        'VOL_TARGET': 0.10,
    }


# ============================================================================
# Tests for QP Solver
# ============================================================================

@pytest.mark.unit
class TestQPSolver:
    """Tests for Quadratic Programming solver."""

    def test_qp_basic(self, sample_portfolio_data, qp_params):
        """Test basic QP optimization."""
        mu, C, w_prev = sample_portfolio_data

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=0.5,
            params=qp_params
        )

        assert isinstance(result, pd.Series)
        assert len(result) == len(mu)
        assert result.index.equals(mu.index)

    def test_qp_weights_sum_constraint(self, sample_portfolio_data, qp_params):
        """Test that weights respect sum constraints."""
        mu, C, w_prev = sample_portfolio_data
        net_lim = 0.5

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=net_lim,
            params=qp_params
        )

        # Net exposure constraint
        assert result.sum() <= net_lim + 1e-6
        assert result.sum() >= -net_lim - 1e-6

    def test_qp_gross_exposure_constraint(self, sample_portfolio_data, qp_params):
        """Test gross exposure constraint."""
        mu, C, w_prev = sample_portfolio_data
        gross_lim = 1.0

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=gross_lim,
            net_lim=0.5,
            params=qp_params
        )

        # Gross exposure = sum of absolute weights
        assert result.abs().sum() <= gross_lim + 1e-6

    def test_qp_box_constraints(self, sample_portfolio_data, qp_params):
        """Test individual position box constraints."""
        mu, C, w_prev = sample_portfolio_data
        box_lim = qp_params['BOX_LIM']

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=0.5,
            params=qp_params
        )

        # Each weight should be within [-box_lim, box_lim]
        assert (result >= -box_lim - 1e-6).all()
        assert (result <= box_lim + 1e-6).all()

    def test_qp_turnover_penalty(self, sample_portfolio_data, qp_params):
        """Test that turnover penalty reduces position changes."""
        mu, C, w_prev = sample_portfolio_data

        # Set previous weights to non-zero
        w_prev_nonzero = pd.Series(
            np.random.uniform(-0.1, 0.1, len(mu)),
            index=mu.index
        )

        # High turnover penalty
        params_high_turnover = qp_params.copy()
        params_high_turnover['TURNOVER_PEN'] = 0.1

        result_high = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev_nonzero,
            gross_lim=1.0,
            net_lim=0.5,
            params=params_high_turnover
        )

        # Low turnover penalty
        params_low_turnover = qp_params.copy()
        params_low_turnover['TURNOVER_PEN'] = 0.0001

        result_low = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev_nonzero,
            gross_lim=1.0,
            net_lim=0.5,
            params=params_low_turnover
        )

        # High penalty should result in less change from previous
        turnover_high = (result_high - w_prev_nonzero).abs().sum()
        turnover_low = (result_low - w_prev_nonzero).abs().sum()

        assert turnover_high <= turnover_low + 1e-6

    def test_qp_volatility_targeting(self, sample_portfolio_data, qp_params):
        """Test volatility targeting rescales portfolio."""
        mu, C, w_prev = sample_portfolio_data

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=0.5,
            params=qp_params
        )

        # Calculate realized volatility
        port_vol = np.sqrt(result.values @ C.values @ result.values)

        # Should be close to VOL_TARGET
        # (may not be exact due to constraints)
        assert port_vol <= qp_params['VOL_TARGET'] * 2  # Reasonable upper bound

    def test_qp_empty_universe(self, qp_params):
        """Test QP with empty universe."""
        mu = pd.Series([], dtype=float)
        C = pd.DataFrame([], dtype=float)
        w_prev = pd.Series([], dtype=float)

        # Should handle gracefully
        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=0.5,
            params=qp_params
        )

        assert len(result) == 0

    def test_qp_single_asset(self, qp_params):
        """Test QP with single asset."""
        mu = pd.Series([0.1], index=['Asset_0'])
        C = pd.DataFrame([[0.04]], index=['Asset_0'], columns=['Asset_0'])
        w_prev = pd.Series([0.0], index=['Asset_0'])

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=0.5,
            params=qp_params
        )

        assert len(result) == 1
        assert -qp_params['BOX_LIM'] - 1e-6 <= result.iloc[0] <= qp_params['BOX_LIM'] + 1e-6

    def test_qp_non_psd_covariance(self, qp_params):
        """Test QP handles non-PSD covariance matrix."""
        mu = pd.Series([0.1, 0.2], index=['A', 'B'])
        # Intentionally non-PSD
        C = pd.DataFrame(
            [[1.0, 2.0],
             [2.0, 1.0]],
            index=['A', 'B'],
            columns=['A', 'B']
        )
        w_prev = pd.Series([0.0, 0.0], index=['A', 'B'])

        # Should handle with PSD correction
        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=0.5,
            params=qp_params
        )

        assert isinstance(result, pd.Series)
        assert len(result) == 2

    def test_qp_extreme_returns(self, qp_params):
        """Test QP with extreme expected returns."""
        mu = pd.Series([100.0, -100.0, 50.0], index=['A', 'B', 'C'])
        C = pd.DataFrame(
            np.eye(3) * 0.04,
            index=['A', 'B', 'C'],
            columns=['A', 'B', 'C']
        )
        w_prev = pd.Series([0.0, 0.0, 0.0], index=['A', 'B', 'C'])

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=0.5,
            params=qp_params
        )

        # Should still respect box constraints
        assert (result.abs() <= qp_params['BOX_LIM'] + 1e-6).all()

    def test_qp_zero_covariance(self, qp_params):
        """Test QP with near-zero covariance."""
        mu = pd.Series([0.1, 0.2], index=['A', 'B'])
        C = pd.DataFrame(
            np.eye(2) * 1e-10,
            index=['A', 'B'],
            columns=['A', 'B']
        )
        w_prev = pd.Series([0.0, 0.0], index=['A', 'B'])

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=0.5,
            params=qp_params
        )

        assert isinstance(result, pd.Series)
        assert not np.isnan(result.values).any()


# ============================================================================
# Property-Based Tests for QP
# ============================================================================

@pytest.mark.property
class TestQPProperties:
    """Property-based tests for QP solver."""

    @given(
        n_assets=st.integers(min_value=2, max_value=10),
        gross_lim=st.floats(min_value=0.5, max_value=2.0),
        net_lim=st.floats(min_value=0.2, max_value=1.0),
    )
    @settings(max_examples=20, deadline=None)
    def test_qp_constraints_always_satisfied(self, n_assets, gross_lim, net_lim, qp_params):
        """QP should always satisfy constraints."""
        np.random.seed(42)

        # Generate valid data
        mu = pd.Series(
            np.random.randn(n_assets) * 0.1,
            index=[f'A{i}' for i in range(n_assets)]
        )
        A = np.random.randn(n_assets, n_assets)
        C = pd.DataFrame(
            A @ A.T / n_assets + np.eye(n_assets) * 0.01,
            index=mu.index,
            columns=mu.index
        )
        w_prev = pd.Series(np.zeros(n_assets), index=mu.index)

        result = solve_qp(
            mu_hat=mu,
            C=C,
            w_prev=w_prev,
            gross_lim=gross_lim,
            net_lim=net_lim,
            params=qp_params
        )

        # Check all constraints
        box_lim = qp_params['BOX_LIM']

        assert result.abs().sum() <= gross_lim + 1e-5, "Gross exposure"
        assert -net_lim - 1e-5 <= result.sum() <= net_lim + 1e-5, "Net exposure"
        assert (result >= -box_lim - 1e-5).all(), "Box lower bound"
        assert (result <= box_lim + 1e-5).all(), "Box upper bound"

    @given(
        n_assets=st.integers(min_value=2, max_value=8),
    )
    @settings(max_examples=10, deadline=None)
    def test_qp_deterministic(self, n_assets, qp_params):
        """QP should give same result for same input."""
        np.random.seed(42)

        mu = pd.Series(
            np.random.randn(n_assets) * 0.1,
            index=[f'A{i}' for i in range(n_assets)]
        )
        A = np.random.randn(n_assets, n_assets)
        C = pd.DataFrame(
            A @ A.T / n_assets + np.eye(n_assets) * 0.01,
            index=mu.index,
            columns=mu.index
        )
        w_prev = pd.Series(np.zeros(n_assets), index=mu.index)

        result1 = solve_qp(mu, C, w_prev, 1.0, 0.5, qp_params)
        result2 = solve_qp(mu, C, w_prev, 1.0, 0.5, qp_params)

        # Should be identical
        assert np.allclose(result1.values, result2.values, atol=1e-6)


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestOptimizationIntegration:
    """Integration tests for optimization module."""

    def test_qp_full_workflow(self, sample_portfolio_data, qp_params):
        """Test full optimization workflow."""
        mu, C, w_prev = sample_portfolio_data

        # Initial optimization
        w1 = solve_qp(mu, C, w_prev, 1.0, 0.5, qp_params)

        # Reoptimize with previous weights
        w2 = solve_qp(mu, C, w1, 1.0, 0.5, qp_params)

        # Should converge (low turnover)
        turnover = (w2 - w1).abs().sum()
        assert turnover < 0.5  # Some change allowed but not drastic
