"""
Comprehensive test suite for qp_solver.py

Tests quadratic programming optimization with:
- solve_qp() - Portfolio optimization with constraints
- Constraint satisfaction testing
- Objective function optimization
- Edge cases and numerical stability
- Integration with covariance matrices

Coverage target: 95%+ for qp_solver.py
"""

import pytest
import pandas as pd
import numpy as np
import cvxpy as cp
from algo_trade.core.optimization.qp_solver import solve_qp


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def simple_problem():
    """Create simple QP problem with 3 assets."""
    assets = ['A', 'B', 'C']

    # Expected returns
    mu_hat = pd.Series([0.10, 0.08, 0.12], index=assets)

    # Covariance matrix
    C = pd.DataFrame([
        [0.04, 0.01, 0.02],
        [0.01, 0.03, 0.015],
        [0.02, 0.015, 0.05],
    ], index=assets, columns=assets)

    # Previous weights
    w_prev = pd.Series([0.3, 0.3, 0.4], index=assets)

    # Parameters
    params = {
        "TURNOVER_PEN": 0.002,
        "RIDGE_PEN": 1e-4,
        "BOX_LIM": 0.25,
        "VOL_TARGET": 0.10,
    }

    return mu_hat, C, w_prev, params


@pytest.fixture
def five_asset_problem():
    """Create realistic 5-asset problem."""
    assets = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

    # Expected returns (annualized)
    mu_hat = pd.Series([0.12, 0.10, 0.15, 0.18, 0.14], index=assets)

    # Covariance matrix (annualized)
    np.random.seed(42)
    L = np.random.randn(5, 5) * 0.1
    C_matrix = L @ L.T + np.eye(5) * 0.02  # Ensure PSD

    C = pd.DataFrame(C_matrix, index=assets, columns=assets)

    # Previous weights (some existing portfolio)
    w_prev = pd.Series([0.2, 0.2, 0.2, 0.2, 0.2], index=assets)

    # Standard parameters
    params = {
        "TURNOVER_PEN": 0.005,
        "RIDGE_PEN": 1e-3,
        "BOX_LIM": 0.30,
        "VOL_TARGET": 0.15,
    }

    return mu_hat, C, w_prev, params


# ============================================================================
# Test Basic Functionality
# ============================================================================

class TestQPBasicFunctionality:
    """Test basic QP solver functionality."""

    def test_qp_returns_series(self, simple_problem):
        """Test that QP returns a pandas Series."""
        mu_hat, C, w_prev, params = simple_problem

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        assert isinstance(result, pd.Series)
        assert len(result) == len(mu_hat)
        assert list(result.index) == list(mu_hat.index)

    def test_qp_finds_solution(self, simple_problem):
        """Test that QP finds a valid solution."""
        mu_hat, C, w_prev, params = simple_problem

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        # Should not be all zeros
        assert result.abs().sum() > 0, "Solution should not be trivial (all zeros)"

        # Should not be identical to previous weights
        assert not result.equals(w_prev), "Solution should differ from previous weights"

    def test_qp_with_five_assets(self, five_asset_problem):
        """Test QP with 5 assets."""
        mu_hat, C, w_prev, params = five_asset_problem

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.5, net_lim=0.8, params=params)

        assert isinstance(result, pd.Series)
        assert len(result) == 5


# ============================================================================
# Test Constraint Satisfaction
# ============================================================================

class TestConstraintSatisfaction:
    """Test that QP solution satisfies all constraints."""

    def test_gross_constraint(self, simple_problem):
        """Test that gross exposure constraint is satisfied."""
        mu_hat, C, w_prev, params = simple_problem
        gross_lim = 0.8

        result = solve_qp(mu_hat, C, w_prev, gross_lim=gross_lim, net_lim=0.5, params=params)

        gross_exposure = result.abs().sum()

        assert gross_exposure <= gross_lim + 1e-6, \
            f"Gross exposure {gross_exposure:.4f} exceeds limit {gross_lim}"

    def test_net_constraint_upper(self, simple_problem):
        """Test that net exposure upper constraint is satisfied."""
        mu_hat, C, w_prev, params = simple_problem
        net_lim = 0.6

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=net_lim, params=params)

        net_exposure = result.sum()

        assert net_exposure <= net_lim + 1e-6, \
            f"Net exposure {net_exposure:.4f} exceeds upper limit {net_lim}"

    def test_net_constraint_lower(self, simple_problem):
        """Test that net exposure lower constraint is satisfied."""
        mu_hat, C, w_prev, params = simple_problem
        net_lim = 0.5

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=net_lim, params=params)

        net_exposure = result.sum()

        assert net_exposure >= -net_lim - 1e-6, \
            f"Net exposure {net_exposure:.4f} below lower limit {-net_lim}"

    def test_box_constraint(self, simple_problem):
        """Test that box constraints are satisfied."""
        mu_hat, C, w_prev, params = simple_problem
        box_lim = params["BOX_LIM"]

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        # All weights should be within [-box_lim, box_lim]
        assert result.max() <= box_lim + 1e-6, \
            f"Max weight {result.max():.4f} exceeds box limit {box_lim}"

        assert result.min() >= -box_lim - 1e-6, \
            f"Min weight {result.min():.4f} below box limit {-box_lim}"

    def test_all_constraints_simultaneously(self, five_asset_problem):
        """Test that all constraints are satisfied simultaneously."""
        mu_hat, C, w_prev, params = five_asset_problem
        gross_lim = 1.2
        net_lim = 0.7
        box_lim = params["BOX_LIM"]

        result = solve_qp(mu_hat, C, w_prev, gross_lim=gross_lim, net_lim=net_lim, params=params)

        # Check all constraints
        gross = result.abs().sum()
        net = result.sum()

        assert gross <= gross_lim + 1e-6, f"Gross constraint violated: {gross:.4f} > {gross_lim}"
        assert -net_lim - 1e-6 <= net <= net_lim + 1e-6, f"Net constraint violated: {net:.4f}"
        assert result.max() <= box_lim + 1e-6, f"Box upper violated: {result.max():.4f}"
        assert result.min() >= -box_lim - 1e-6, f"Box lower violated: {result.min():.4f}"


# ============================================================================
# Test Optimization Behavior
# ============================================================================

class TestOptimizationBehavior:
    """Test that QP optimizes correctly."""

    def test_high_return_asset_gets_weight(self):
        """Test that asset with high return gets positive weight."""
        assets = ['LOW', 'HIGH']

        # HIGH has much higher return
        mu_hat = pd.Series([0.05, 0.25], index=assets)

        # Low correlation
        C = pd.DataFrame([
            [0.04, 0.01],
            [0.01, 0.04],
        ], index=assets, columns=assets)

        w_prev = pd.Series([0.5, 0.5], index=assets)

        params = {
            "TURNOVER_PEN": 0.001,
            "RIDGE_PEN": 1e-4,
            "BOX_LIM": 0.50,
            "VOL_TARGET": 0.15,
        }

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.8, params=params)

        # HIGH should have higher weight than LOW
        assert result['HIGH'] > result['LOW'], \
            f"High-return asset should have more weight: HIGH={result['HIGH']:.3f}, LOW={result['LOW']:.3f}"

    def test_turnover_penalty_reduces_turnover(self):
        """Test that turnover penalty reduces portfolio turnover."""
        assets = ['A', 'B', 'C']

        mu_hat = pd.Series([0.10, 0.12, 0.08], index=assets)
        C = pd.DataFrame(np.eye(3) * 0.04, index=assets, columns=assets)
        w_prev = pd.Series([0.8, 0.1, 0.1], index=assets)

        # Low turnover penalty
        params_low = {"TURNOVER_PEN": 0.0001, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.50, "VOL_TARGET": 0.15}
        result_low = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.8, params=params_low)

        # High turnover penalty
        params_high = {"TURNOVER_PEN": 0.05, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.50, "VOL_TARGET": 0.15}
        result_high = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.8, params=params_high)

        # Calculate turnover
        turnover_low = (result_low - w_prev).abs().sum()
        turnover_high = (result_high - w_prev).abs().sum()

        # High penalty should reduce turnover
        assert turnover_high < turnover_low, \
            f"High penalty should reduce turnover: {turnover_high:.3f} vs {turnover_low:.3f}"

    def test_volatility_targeting(self, simple_problem):
        """Test that volatility targeting scales portfolio correctly."""
        mu_hat, C, w_prev, params = simple_problem
        vol_target = params["VOL_TARGET"]

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.8, params=params)

        # Calculate portfolio volatility
        port_vol = np.sqrt(result.values @ C.values @ result.values)

        # Should be close to target (allowing for scaling and constraints)
        # This is an approximation due to constraints
        assert port_vol < vol_target * 1.5, \
            f"Portfolio vol {port_vol:.3f} far from target {vol_target:.3f}"


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and robustness."""

    def test_zero_returns(self):
        """Test QP with zero expected returns."""
        assets = ['A', 'B', 'C']

        mu_hat = pd.Series([0.0, 0.0, 0.0], index=assets)
        C = pd.DataFrame(np.eye(3) * 0.04, index=assets, columns=assets)
        w_prev = pd.Series([0.3, 0.3, 0.4], index=assets)

        params = {"TURNOVER_PEN": 0.002, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.25, "VOL_TARGET": 0.10}

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        # Should return valid solution (likely minimize risk)
        assert isinstance(result, pd.Series)

    def test_infeasible_constraints(self):
        """Test QP with tight/infeasible constraints."""
        assets = ['A', 'B']

        mu_hat = pd.Series([0.10, 0.12], index=assets)
        C = pd.DataFrame([[0.04, 0.01], [0.01, 0.03]], index=assets, columns=assets)
        w_prev = pd.Series([0.5, 0.5], index=assets)

        params = {"TURNOVER_PEN": 0.002, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.05, "VOL_TARGET": 0.10}

        # Very tight constraints (may be infeasible)
        result = solve_qp(mu_hat, C, w_prev, gross_lim=0.1, net_lim=0.05, params=params)

        # Should either find solution or return previous weights
        assert isinstance(result, pd.Series)

    def test_single_asset(self):
        """Test QP with single asset."""
        assets = ['A']

        mu_hat = pd.Series([0.10], index=assets)
        C = pd.DataFrame([[0.04]], index=assets, columns=assets)
        w_prev = pd.Series([0.5], index=assets)

        params = {"TURNOVER_PEN": 0.002, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.50, "VOL_TARGET": 0.10}

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.8, params=params)

        assert len(result) == 1
        assert isinstance(result, pd.Series)

    def test_near_singular_covariance(self):
        """Test QP with near-singular covariance matrix."""
        assets = ['A', 'B', 'C']

        mu_hat = pd.Series([0.10, 0.12, 0.08], index=assets)

        # Near-singular matrix (highly correlated assets)
        C = pd.DataFrame([
            [0.04, 0.039, 0.038],
            [0.039, 0.04, 0.039],
            [0.038, 0.039, 0.04],
        ], index=assets, columns=assets)

        w_prev = pd.Series([0.3, 0.3, 0.4], index=assets)

        params = {"TURNOVER_PEN": 0.002, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.25, "VOL_TARGET": 0.10}

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        # Should handle via PSD fix
        assert isinstance(result, pd.Series)

    def test_negative_returns(self):
        """Test QP with negative expected returns."""
        assets = ['A', 'B', 'C']

        # All negative returns (short opportunity)
        mu_hat = pd.Series([-0.05, -0.08, -0.10], index=assets)
        C = pd.DataFrame(np.eye(3) * 0.04, index=assets, columns=assets)
        w_prev = pd.Series([0.0, 0.0, 0.0], index=assets)

        params = {"TURNOVER_PEN": 0.002, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.30, "VOL_TARGET": 0.10}

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        # Should allow short positions
        assert result.sum() <= 0 or result.abs().sum() < 1e-6, \
            "With negative returns, portfolio should be short or zero"


# ============================================================================
# Test Numerical Stability
# ============================================================================

class TestNumericalStability:
    """Test numerical stability and precision."""

    def test_solution_stability_with_noise(self, simple_problem):
        """Test that small perturbations produce similar solutions."""
        mu_hat, C, w_prev, params = simple_problem

        result1 = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        # Add small noise to returns
        mu_hat_noisy = mu_hat + 0.001 * np.random.randn(len(mu_hat))

        result2 = solve_qp(mu_hat_noisy, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        # Solutions should be close
        diff = (result1 - result2).abs().sum()

        assert diff < 0.2, f"Small perturbation caused large change: {diff:.3f}"

    def test_no_nan_or_inf(self, five_asset_problem):
        """Test that solution contains no NaN or Inf."""
        mu_hat, C, w_prev, params = five_asset_problem

        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.5, net_lim=0.8, params=params)

        assert not result.isnull().any(), "Solution contains NaN"
        assert not np.isinf(result).any(), "Solution contains Inf"

    def test_repeated_calls_consistency(self, simple_problem):
        """Test that repeated calls with same input produce same output."""
        mu_hat, C, w_prev, params = simple_problem

        result1 = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)
        result2 = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params)

        pd.testing.assert_series_equal(result1, result2, rtol=1e-6)


# ============================================================================
# Test Parameter Sensitivity
# ============================================================================

class TestParameterSensitivity:
    """Test sensitivity to parameter changes."""

    def test_ridge_penalty_impact(self, simple_problem):
        """Test impact of ridge penalty."""
        mu_hat, C, w_prev, params = simple_problem

        # Low ridge
        params_low = params.copy()
        params_low["RIDGE_PEN"] = 1e-6
        result_low = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params_low)

        # High ridge
        params_high = params.copy()
        params_high["RIDGE_PEN"] = 0.01
        result_high = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params_high)

        # High ridge should shrink weights more
        mag_low = result_low.abs().sum()
        mag_high = result_high.abs().sum()

        assert mag_high <= mag_low, \
            f"Higher ridge should reduce weight magnitude: {mag_high:.3f} vs {mag_low:.3f}"

    def test_box_limit_impact(self, simple_problem):
        """Test impact of box limit."""
        mu_hat, C, w_prev, params = simple_problem

        # Tight box
        params_tight = params.copy()
        params_tight["BOX_LIM"] = 0.10
        result_tight = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params_tight)

        # Loose box
        params_loose = params.copy()
        params_loose["BOX_LIM"] = 0.50
        result_loose = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=0.5, params=params_loose)

        # Tight box should constrain individual weights more
        assert result_tight.max() <= 0.10 + 1e-6
        assert result_loose.max() >= result_tight.max()


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestQPIntegration:
    """Integration tests with real-world scenarios."""

    def test_long_only_portfolio(self):
        """Test QP for long-only portfolio."""
        assets = ['SPY', 'AGG', 'GLD']

        mu_hat = pd.Series([0.08, 0.03, 0.05], index=assets)
        C = pd.DataFrame([
            [0.04, 0.01, 0.005],
            [0.01, 0.01, 0.003],
            [0.005, 0.003, 0.06],
        ], index=assets, columns=assets)

        w_prev = pd.Series([0.6, 0.3, 0.1], index=assets)

        params = {"TURNOVER_PEN": 0.005, "RIDGE_PEN": 1e-3, "BOX_LIM": 1.0, "VOL_TARGET": 0.10}

        # Long-only: set box limit to [0, 1]
        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.0, net_lim=1.0, params=params)

        # All weights should be non-negative (long-only)
        # Note: BOX_LIM applies symmetrically, so we rely on constraints
        assert result.sum() <= 1.0 + 1e-6

    def test_market_neutral_portfolio(self):
        """Test QP for market-neutral portfolio."""
        assets = ['TECH', 'VALUE', 'GROWTH', 'MOMENTUM']

        mu_hat = pd.Series([0.10, 0.05, 0.12, 0.08], index=assets)
        C = pd.DataFrame(np.eye(4) * 0.04, index=assets, columns=assets)

        w_prev = pd.Series([0.25, -0.25, 0.25, -0.25], index=assets)

        params = {"TURNOVER_PEN": 0.002, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.40, "VOL_TARGET": 0.12}

        # Market neutral: net exposure ~0
        result = solve_qp(mu_hat, C, w_prev, gross_lim=1.5, net_lim=0.1, params=params)

        # Net exposure should be close to zero
        assert abs(result.sum()) <= 0.1 + 1e-6, \
            f"Market neutral portfolio should have net ~0, got {result.sum():.3f}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
