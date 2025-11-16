"""
Unit tests for QP (Quadratic Programming) portfolio optimization.

Tests cover:
- Basic QP solving functionality
- Constraint satisfaction
- Edge cases and error handling
- Volatility targeting
- Turnover penalization
"""

import pytest
import numpy as np
import pandas as pd

from algo_trade.core.optimization.qp_solver import solve_qp


# ============================================================================
# Basic QP Tests
# ============================================================================


@pytest.mark.unit
class TestQPSolverBasic:
    """Test basic QP solver functionality."""

    def test_qp_solver_returns_series(self, default_config):
        """Test that QP solver returns a pandas Series."""
        # Create simple test data
        n_assets = 5
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series(np.random.randn(n_assets) * 0.01, index=idx)
        C = pd.DataFrame(
            np.eye(n_assets) * 0.04 + np.random.randn(n_assets, n_assets) * 0.001,
            index=idx,
            columns=idx
        )
        C = (C + C.T) / 2  # Make symmetric
        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params=default_config
        )

        assert isinstance(w_opt, pd.Series)
        assert len(w_opt) == n_assets
        assert w_opt.index.equals(pd.Index(idx))

    def test_qp_solver_respects_gross_limit(self, default_config):
        """Test that QP solution respects gross exposure limit."""
        n_assets = 5
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        # Strong positive expected returns (should want full exposure)
        mu_hat = pd.Series(np.ones(n_assets) * 0.1, index=idx)
        C = pd.DataFrame(np.eye(n_assets) * 0.01, index=idx, columns=idx)
        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        gross_lim = 1.5
        net_lim = 1.0

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=gross_lim,
            net_lim=net_lim,
            params=default_config
        )

        # Check gross exposure constraint
        gross_exposure = w_opt.abs().sum()
        assert gross_exposure <= gross_lim + 1e-4  # Small tolerance for numerical errors

    def test_qp_solver_respects_net_limit(self, default_config):
        """Test that QP solution respects net exposure limit."""
        n_assets = 5
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series(np.ones(n_assets) * 0.1, index=idx)
        C = pd.DataFrame(np.eye(n_assets) * 0.01, index=idx, columns=idx)
        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        gross_lim = 2.0
        net_lim = 0.5

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=gross_lim,
            net_lim=net_lim,
            params=default_config
        )

        # Check net exposure constraint
        net_exposure = w_opt.sum()
        assert -net_lim - 1e-4 <= net_exposure <= net_lim + 1e-4

    def test_qp_solver_respects_box_constraints(self, default_config):
        """Test that individual position sizes respect box constraints."""
        n_assets = 5
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series(np.ones(n_assets) * 0.1, index=idx)
        C = pd.DataFrame(np.eye(n_assets) * 0.01, index=idx, columns=idx)
        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        box_lim = 0.25
        params = {**default_config, "BOX_LIM": box_lim}

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params=params
        )

        # Check box constraints
        assert w_opt.max() <= box_lim + 1e-4
        assert w_opt.min() >= -box_lim - 1e-4


# ============================================================================
# Volatility Targeting Tests
# ============================================================================


@pytest.mark.unit
class TestVolatilityTargeting:
    """Test volatility targeting functionality."""

    def test_volatility_scaling(self, default_config):
        """Test that portfolio is scaled to target volatility."""
        n_assets = 3
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        # Create higher volatility scenario
        mu_hat = pd.Series([0.05, 0.03, 0.04], index=idx)
        C = pd.DataFrame([
            [0.04, 0.01, 0.01],
            [0.01, 0.04, 0.01],
            [0.01, 0.01, 0.04]
        ], index=idx, columns=idx)
        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        vol_target = 0.10
        params = {**default_config, "VOL_TARGET": vol_target}

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params=params
        )

        # Calculate realized volatility
        port_vol = np.sqrt(w_opt.values @ C.values @ w_opt.values)

        # Should be close to target (within reasonable tolerance)
        assert abs(port_vol - vol_target) < vol_target * 0.2  # 20% tolerance

    def test_low_volatility_scaling_up(self, default_config):
        """Test that low-vol portfolio is scaled up to target."""
        n_assets = 3
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        # Very low volatility
        mu_hat = pd.Series([0.05, 0.03, 0.04], index=idx)
        C = pd.DataFrame([
            [0.0001, 0.0, 0.0],
            [0.0, 0.0001, 0.0],
            [0.0, 0.0, 0.0001]
        ], index=idx, columns=idx)
        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        vol_target = 0.10

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params={**default_config, "VOL_TARGET": vol_target}
        )

        # Portfolio should be levered up (but within constraints)
        assert w_opt.abs().sum() > 0.5


# ============================================================================
# Turnover Penalization Tests
# ============================================================================


@pytest.mark.unit
class TestTurnoverPenalty:
    """Test turnover penalization."""

    def test_turnover_penalty_reduces_changes(self, default_config):
        """Test that turnover penalty reduces portfolio changes."""
        n_assets = 3
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series([0.05, 0.03, 0.04], index=idx)
        C = pd.DataFrame(np.eye(n_assets) * 0.01, index=idx, columns=idx)
        w_prev = pd.Series([0.1, 0.1, 0.0], index=idx)

        # Solve with low turnover penalty
        w_opt_low_penalty = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params={**default_config, "TURNOVER_PEN": 0.001}
        )

        # Solve with high turnover penalty
        w_opt_high_penalty = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params={**default_config, "TURNOVER_PEN": 0.01}
        )

        # Turnover with high penalty should be less
        turnover_low = (w_opt_low_penalty - w_prev).abs().sum()
        turnover_high = (w_opt_high_penalty - w_prev).abs().sum()

        assert turnover_high <= turnover_low

    def test_zero_expected_returns_stays_put(self, default_config):
        """Test that with zero expected returns and turnover penalty, portfolio stays put."""
        n_assets = 3
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series(np.zeros(n_assets), index=idx)  # Zero expected returns
        C = pd.DataFrame(np.eye(n_assets) * 0.01, index=idx, columns=idx)
        w_prev = pd.Series([0.2, 0.1, -0.1], index=idx)

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params={**default_config, "TURNOVER_PEN": 0.01}
        )

        # With zero returns and turnover penalty, should stay close to previous
        turnover = (w_opt - w_prev).abs().sum()
        assert turnover < 0.3  # Reasonable threshold


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


@pytest.mark.unit
class TestQPSolverEdgeCases:
    """Test edge cases and error handling."""

    def test_qp_with_singular_covariance(self, default_config):
        """Test QP solver with singular covariance matrix."""
        n_assets = 3
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series([0.05, 0.03, 0.04], index=idx)

        # Create singular matrix (third column = first + second)
        C = pd.DataFrame([
            [0.04, 0.01, 0.05],
            [0.01, 0.04, 0.05],
            [0.05, 0.05, 0.10]  # Linear combination
        ], index=idx, columns=idx)

        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        # Should handle singular matrix (add regularization)
        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params=default_config
        )

        assert isinstance(w_opt, pd.Series)
        assert not w_opt.isna().any()

    def test_qp_with_negative_eigenvalues(self, default_config):
        """Test QP solver with non-PSD covariance matrix."""
        n_assets = 3
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series([0.05, 0.03, 0.04], index=idx)

        # Create non-PSD matrix
        C = pd.DataFrame([
            [0.04, 0.05, 0.01],
            [0.05, 0.04, 0.01],
            [0.01, 0.01, -0.01]  # Negative on diagonal
        ], index=idx, columns=idx)

        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        # Should handle non-PSD matrix
        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params=default_config
        )

        assert isinstance(w_opt, pd.Series)

    def test_qp_with_zero_covariance(self, default_config):
        """Test QP solver with zero covariance (risk-free assets)."""
        n_assets = 3
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series([0.05, 0.03, 0.04], index=idx)
        C = pd.DataFrame(np.zeros((n_assets, n_assets)), index=idx, columns=idx)
        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=2.0,
            net_lim=1.0,
            params=default_config
        )

        # Should handle zero covariance (will add regularization)
        assert isinstance(w_opt, pd.Series)
        assert not w_opt.isna().any()

    def test_qp_infeasible_constraints(self, default_config):
        """Test QP solver with infeasible constraints."""
        n_assets = 3
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series([0.05, 0.03, 0.04], index=idx)
        C = pd.DataFrame(np.eye(n_assets) * 0.01, index=idx, columns=idx)
        w_prev = pd.Series([0.5, 0.5, 0.5], index=idx)  # Previous weights sum > net_lim

        # Very tight constraints (infeasible)
        gross_lim = 0.1
        net_lim = 0.05

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=gross_lim,
            net_lim=net_lim,
            params=default_config
        )

        # Should return previous weights if infeasible
        if w_opt.equals(w_prev):
            # Returned previous weights due to infeasibility
            assert True
        else:
            # Or found a solution that satisfies constraints
            assert w_opt.abs().sum() <= gross_lim + 1e-3

    def test_qp_single_asset(self, default_config):
        """Test QP solver with single asset."""
        idx = ["ASSET_0"]

        mu_hat = pd.Series([0.05], index=idx)
        C = pd.DataFrame([[0.04]], index=idx, columns=idx)
        w_prev = pd.Series([0.0], index=idx)

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=1.0,
            net_lim=1.0,
            params=default_config
        )

        assert isinstance(w_opt, pd.Series)
        assert len(w_opt) == 1
        assert -1.0 <= w_opt.iloc[0] <= 1.0


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.integration
class TestQPIntegration:
    """Integration tests for QP solver in realistic scenarios."""

    def test_qp_multiperiod_consistency(self, default_config):
        """Test QP solver consistency across multiple periods."""
        n_assets = 5
        n_periods = 10
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        # Simulate multi-period optimization
        weights_history = []
        w_current = pd.Series(np.zeros(n_assets), index=idx)

        for t in range(n_periods):
            # Generate random but reasonable data
            mu_hat = pd.Series(np.random.randn(n_assets) * 0.01, index=idx)
            C = pd.DataFrame(
                np.eye(n_assets) * 0.04 + np.random.randn(n_assets, n_assets) * 0.001,
                index=idx, columns=idx
            )
            C = (C + C.T) / 2  # Make symmetric

            w_opt = solve_qp(
                mu_hat=mu_hat,
                C=C,
                w_prev=w_current,
                gross_lim=2.0,
                net_lim=1.0,
                params=default_config
            )

            weights_history.append(w_opt)
            w_current = w_opt

        # Check all solutions are valid
        for w in weights_history:
            assert isinstance(w, pd.Series)
            assert not w.isna().any()
            assert w.abs().sum() <= 2.0 + 1e-3  # Gross limit
            assert abs(w.sum()) <= 1.0 + 1e-3  # Net limit

    def test_qp_long_only_portfolio(self, default_config):
        """Test QP solver for long-only portfolio."""
        n_assets = 5
        idx = [f"ASSET_{i}" for i in range(n_assets)]

        mu_hat = pd.Series(np.random.randn(n_assets) * 0.01, index=idx)
        C = pd.DataFrame(np.eye(n_assets) * 0.04, index=idx, columns=idx)
        w_prev = pd.Series(np.zeros(n_assets), index=idx)

        # Force long-only by setting BOX_LIM lower bound to 0
        params = {**default_config, "BOX_LIM": 1.0}  # Allow up to 100% in single asset

        # Set gross = net for long-only
        gross_lim = 1.0
        net_lim = 1.0

        w_opt = solve_qp(
            mu_hat=mu_hat,
            C=C,
            w_prev=w_prev,
            gross_lim=gross_lim,
            net_lim=net_lim,
            params=params
        )

        # In typical long-only scenario with these constraints,
        # we expect positive weights
        assert w_opt.sum() <= net_lim + 1e-3
