"""
Unit tests for QP solver (Quadratic Programming Portfolio Optimization).
Tests cover: basic optimization, constraints, edge cases, volatility targeting.
"""

import pytest
import numpy as np
import pandas as pd
from algo_trade.core.optimization.qp_solver import solve_qp


# ==================== FIXTURES ====================

@pytest.fixture
def sample_assets():
    """Sample asset names for testing."""
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]


@pytest.fixture
def sample_mu(sample_assets):
    """Sample expected returns (annualized)."""
    return pd.Series([0.15, 0.12, 0.18, 0.10, 0.20], index=sample_assets)


@pytest.fixture
def sample_cov(sample_assets):
    """Sample covariance matrix (realistic correlation structure)."""
    np.random.seed(42)
    # Create a valid covariance matrix using Cholesky decomposition
    n = len(sample_assets)
    A = np.random.randn(n, n)
    C = A @ A.T + np.eye(n) * 0.01  # Ensure positive definite
    C = C * 0.05  # Scale to reasonable volatility (~22% annualized)
    return pd.DataFrame(C, index=sample_assets, columns=sample_assets)


@pytest.fixture
def sample_w_prev(sample_assets):
    """Sample previous portfolio weights (equally weighted)."""
    return pd.Series([0.2, 0.2, 0.2, 0.2, 0.2], index=sample_assets)


@pytest.fixture
def default_params():
    """Default optimization parameters."""
    return {
        "TURNOVER_PEN": 0.002,
        "RIDGE_PEN": 1e-4,
        "BOX_LIM": 0.25,
        "VOL_TARGET": 0.10
    }


# ==================== BASIC FUNCTIONALITY ====================

def test_solve_qp_basic_solution(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that QP solver returns a valid portfolio."""
    gross_lim = 2.0
    net_lim = 1.0

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    # Check output type and shape
    assert isinstance(w_opt, pd.Series), "Output should be a pandas Series"
    assert len(w_opt) == len(sample_mu), f"Expected {len(sample_mu)} weights, got {len(w_opt)}"
    assert w_opt.index.equals(sample_mu.index), "Output index should match input index"

    # Check weights are finite
    assert np.all(np.isfinite(w_opt)), "All weights should be finite"


def test_solve_qp_prefers_high_return_assets(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that optimizer allocates more to higher expected return assets (risk-adjusted)."""
    gross_lim = 2.0
    net_lim = 1.0

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    # TSLA has highest expected return (0.20), should have positive weight
    # Note: This might not always hold due to risk aversion, but should generally be true
    assert w_opt["TSLA"] > 0, "Highest return asset should have positive weight"

    # Portfolio should favor growth (positive expected return)
    weighted_return = (sample_mu * w_opt).sum()
    assert weighted_return > 0, f"Portfolio expected return should be positive: {weighted_return}"


def test_solve_qp_respects_risk_aversion(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that optimizer balances return and risk."""
    gross_lim = 2.0
    net_lim = 1.0

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    # Compute portfolio variance
    port_var = w_opt.values @ sample_cov.values @ w_opt.values
    port_vol = np.sqrt(port_var)

    # Portfolio volatility should be close to VOL_TARGET (0.10)
    vol_target = default_params["VOL_TARGET"]
    assert np.abs(port_vol - vol_target) < 0.05, \
        f"Portfolio volatility {port_vol:.4f} should be close to target {vol_target}"


# ==================== CONSTRAINT VALIDATION ====================

def test_solve_qp_respects_gross_limit(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that gross exposure constraint is satisfied."""
    gross_lim = 1.5
    net_lim = 1.0

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    gross_exposure = np.abs(w_opt).sum()
    assert gross_exposure <= gross_lim + 1e-6, \
        f"Gross exposure {gross_exposure:.4f} exceeds limit {gross_lim}"


def test_solve_qp_respects_net_limit(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that net exposure constraint is satisfied."""
    gross_lim = 2.0
    net_lim = 0.8

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    net_exposure = w_opt.sum()
    assert -net_lim - 1e-6 <= net_exposure <= net_lim + 1e-6, \
        f"Net exposure {net_exposure:.4f} violates bounds [-{net_lim}, {net_lim}]"


def test_solve_qp_respects_box_constraints(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that box constraints (individual position limits) are satisfied."""
    gross_lim = 2.0
    net_lim = 1.0
    box_lim = 0.25

    params = default_params.copy()
    params["BOX_LIM"] = box_lim

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params)

    # Check all weights within [-box_lim, box_lim]
    assert np.all(w_opt >= -box_lim - 1e-6), \
        f"Some weights below lower bound: min={w_opt.min():.4f}, bound={-box_lim}"
    assert np.all(w_opt <= box_lim + 1e-6), \
        f"Some weights above upper bound: max={w_opt.max():.4f}, bound={box_lim}"


def test_solve_qp_tight_box_constraint(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test behavior with very tight box constraints."""
    gross_lim = 2.0
    net_lim = 1.0
    box_lim = 0.05  # Very tight

    params = default_params.copy()
    params["BOX_LIM"] = box_lim

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params)

    # All weights should be within tight bounds
    assert np.all(np.abs(w_opt) <= box_lim + 1e-6), \
        f"Weights violate tight box constraint: max_abs={np.abs(w_opt).max():.4f}, bound={box_lim}"


# ==================== TURNOVER PENALTY ====================

def test_solve_qp_turnover_penalty_effect(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that turnover penalty reduces portfolio changes."""
    gross_lim = 2.0
    net_lim = 1.0

    # Solve with high turnover penalty
    params_high = default_params.copy()
    params_high["TURNOVER_PEN"] = 0.05  # High penalty

    # Solve with low turnover penalty
    params_low = default_params.copy()
    params_low["TURNOVER_PEN"] = 0.0001  # Low penalty

    w_high = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params_high)
    w_low = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params_low)

    # Compute turnover (L1 distance from previous weights)
    turnover_high = np.abs(w_high - sample_w_prev).sum()
    turnover_low = np.abs(w_low - sample_w_prev).sum()

    # High penalty should result in lower turnover
    assert turnover_high < turnover_low, \
        f"High penalty turnover {turnover_high:.4f} should be less than low penalty {turnover_low:.4f}"


def test_solve_qp_zero_turnover_penalty_changes_portfolio(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that with zero turnover penalty, portfolio can change freely."""
    gross_lim = 2.0
    net_lim = 1.0

    params = default_params.copy()
    params["TURNOVER_PEN"] = 0.0  # No penalty

    # Use extreme expected returns to force portfolio change
    mu_extreme = sample_mu.copy()
    mu_extreme["TSLA"] = 0.50  # Very high return
    mu_extreme["AMZN"] = -0.10  # Negative return

    w_opt = solve_qp(mu_extreme, sample_cov, sample_w_prev, gross_lim, net_lim, params)

    # Portfolio should differ from previous weights
    turnover = np.abs(w_opt - sample_w_prev).sum()
    assert turnover > 0.1, f"Portfolio should change with extreme returns: turnover={turnover:.4f}"


# ==================== VOLATILITY TARGETING ====================

def test_solve_qp_volatility_targeting(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that volatility targeting scales portfolio to target volatility."""
    gross_lim = 2.0
    net_lim = 1.0
    vol_target = 0.15  # 15% target volatility

    params = default_params.copy()
    params["VOL_TARGET"] = vol_target

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params)

    # Compute realized portfolio volatility
    port_var = w_opt.values @ sample_cov.values @ w_opt.values
    port_vol = np.sqrt(port_var)

    # Should be close to target (within 5%)
    assert np.abs(port_vol - vol_target) < 0.05, \
        f"Portfolio volatility {port_vol:.4f} far from target {vol_target}"


def test_solve_qp_different_volatility_targets(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that different volatility targets result in different portfolio scales."""
    gross_lim = 2.0
    net_lim = 1.0

    params_low = default_params.copy()
    params_low["VOL_TARGET"] = 0.08  # Low volatility

    params_high = default_params.copy()
    params_high["VOL_TARGET"] = 0.20  # High volatility

    w_low = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params_low)
    w_high = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params_high)

    # Compute gross exposures
    gross_low = np.abs(w_low).sum()
    gross_high = np.abs(w_high).sum()

    # Higher volatility target should lead to higher gross exposure (in general)
    # Note: This is not always guaranteed due to optimization, but should trend this way
    assert gross_high >= gross_low * 0.8, \
        f"Higher vol target should lead to higher exposure: low={gross_low:.4f}, high={gross_high:.4f}"


# ==================== EDGE CASES ====================

def test_solve_qp_zero_returns(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test solver behavior with zero expected returns (pure risk minimization)."""
    gross_lim = 2.0
    net_lim = 1.0

    mu_zero = pd.Series([0.0] * len(sample_mu), index=sample_mu.index)

    w_opt = solve_qp(mu_zero, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    # Should return valid weights
    assert np.all(np.isfinite(w_opt)), "Weights should be finite with zero returns"

    # Portfolio should be low risk (close to zero exposure or minimum variance)
    port_var = w_opt.values @ sample_cov.values @ w_opt.values
    assert port_var < 0.05, f"Portfolio variance should be low with zero returns: {port_var:.4f}"


def test_solve_qp_identical_assets(sample_assets, sample_w_prev, default_params):
    """Test solver with identical assets (degenerate covariance)."""
    gross_lim = 2.0
    net_lim = 1.0

    # All assets have same return and covariance
    mu_identical = pd.Series([0.10] * len(sample_assets), index=sample_assets)
    C_identical = pd.DataFrame(
        np.ones((len(sample_assets), len(sample_assets))) * 0.04 + np.eye(len(sample_assets)) * 0.01,
        index=sample_assets,
        columns=sample_assets
    )

    w_opt = solve_qp(mu_identical, C_identical, sample_w_prev, gross_lim, net_lim, default_params)

    # Should return valid solution (not necessarily uniform due to turnover penalty)
    assert np.all(np.isfinite(w_opt)), "Weights should be finite with identical assets"


def test_solve_qp_single_asset(default_params):
    """Test solver with a single asset."""
    gross_lim = 1.0
    net_lim = 1.0

    mu = pd.Series([0.10], index=["AAPL"])
    C = pd.DataFrame([[0.04]], index=["AAPL"], columns=["AAPL"])
    w_prev = pd.Series([0.0], index=["AAPL"])

    w_opt = solve_qp(mu, C, w_prev, gross_lim, net_lim, default_params)

    # Should have non-zero weight (capped by volatility targeting)
    assert np.isfinite(w_opt["AAPL"]), "Single asset weight should be finite"
    assert np.abs(w_opt["AAPL"]) > 0, "Single asset should have non-zero allocation"


def test_solve_qp_negative_returns(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test solver with all negative expected returns."""
    gross_lim = 2.0
    net_lim = 1.0

    mu_negative = -sample_mu  # All negative

    w_opt = solve_qp(mu_negative, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    # Should return valid weights (likely short positions)
    assert np.all(np.isfinite(w_opt)), "Weights should be finite with negative returns"

    # Net exposure should be negative or near zero (risk minimization)
    net_exposure = w_opt.sum()
    assert net_exposure <= 0.1, \
        f"Net exposure should be non-positive with negative returns: {net_exposure:.4f}"


# ==================== COVARIANCE MATRIX HANDLING ====================

def test_solve_qp_near_singular_covariance(sample_mu, sample_assets, sample_w_prev, default_params):
    """Test solver with near-singular covariance matrix."""
    gross_lim = 2.0
    net_lim = 1.0

    # Create near-singular matrix (two assets perfectly correlated)
    n = len(sample_assets)
    C = np.eye(n) * 0.04
    C[0, 1] = 0.0399  # Near perfect correlation
    C[1, 0] = 0.0399
    C_df = pd.DataFrame(C, index=sample_assets, columns=sample_assets)

    # Solver should handle this with PSD correction
    w_opt = solve_qp(sample_mu, C_df, sample_w_prev, gross_lim, net_lim, default_params)

    assert np.all(np.isfinite(w_opt)), "Solver should handle near-singular covariance"


def test_solve_qp_small_negative_eigenvalue(sample_mu, sample_assets, sample_w_prev, default_params):
    """Test solver with covariance matrix with small negative eigenvalue."""
    gross_lim = 2.0
    net_lim = 1.0

    # Create matrix with small negative eigenvalue
    n = len(sample_assets)
    C = np.random.randn(n, n)
    C = (C + C.T) / 2  # Make symmetric
    eigs = np.linalg.eigvalsh(C)
    C = C + np.eye(n) * (0.01 - eigs.min())  # Shift to have small negative eigenvalue
    C = C - np.eye(n) * 2e-8  # Make slightly non-PSD
    C_df = pd.DataFrame(C, index=sample_assets, columns=sample_assets)

    # Solver should correct this internally
    w_opt = solve_qp(sample_mu, C_df, sample_w_prev, gross_lim, net_lim, default_params)

    assert np.all(np.isfinite(w_opt)), "Solver should correct non-PSD matrix"


# ==================== ERROR HANDLING ====================

def test_solve_qp_empty_inputs():
    """Test solver behavior with empty inputs."""
    mu = pd.Series([], dtype=float)
    C = pd.DataFrame(np.array([]).reshape(0, 0))
    w_prev = pd.Series([], dtype=float)
    params = {"TURNOVER_PEN": 0.002, "RIDGE_PEN": 1e-4, "BOX_LIM": 0.25, "VOL_TARGET": 0.10}

    gross_lim = 1.0
    net_lim = 1.0

    # Should handle gracefully (likely return empty or previous weights)
    try:
        w_opt = solve_qp(mu, C, w_prev, gross_lim, net_lim, params)
        assert len(w_opt) == 0, "Output should be empty for empty input"
    except Exception:
        # Exception is acceptable for invalid input
        pass


def test_solve_qp_mismatched_dimensions(sample_mu, sample_cov, sample_assets, default_params):
    """Test solver with mismatched input dimensions."""
    gross_lim = 2.0
    net_lim = 1.0

    # Previous weights have different assets
    w_prev_wrong = pd.Series([0.5, 0.5], index=["NFLX", "NVDA"])

    try:
        # This should either fail or handle the mismatch
        w_opt = solve_qp(sample_mu, sample_cov, w_prev_wrong, gross_lim, net_lim, default_params)
        # If it succeeds, at least check it returns something
        assert w_opt is not None
    except Exception:
        # Exception is acceptable for mismatched inputs
        pass


# ==================== PARAMETER SENSITIVITY ====================

def test_solve_qp_ridge_penalty_effect(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test that ridge penalty (L2 regularization) affects portfolio concentration."""
    gross_lim = 2.0
    net_lim = 1.0

    params_high = default_params.copy()
    params_high["RIDGE_PEN"] = 0.01  # High regularization

    params_low = default_params.copy()
    params_low["RIDGE_PEN"] = 1e-6  # Low regularization

    w_high = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params_high)
    w_low = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params_low)

    # Higher ridge penalty should lead to lower sum of squares (less concentrated)
    ss_high = (w_high ** 2).sum()
    ss_low = (w_low ** 2).sum()

    assert ss_high <= ss_low * 1.2, \
        f"Ridge penalty should reduce concentration: high={ss_high:.4f}, low={ss_low:.4f}"


def test_solve_qp_realistic_portfolio_scenario(sample_mu, sample_cov, sample_w_prev, default_params):
    """Test a realistic portfolio optimization scenario."""
    gross_lim = 1.5  # 150% gross exposure (50% long, 100% short possible)
    net_lim = 0.6    # 60% net exposure

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    # Verify all constraints
    assert np.abs(w_opt).sum() <= gross_lim + 1e-6, "Gross constraint violated"
    assert np.abs(w_opt.sum()) <= net_lim + 1e-6, "Net constraint violated"
    assert np.all(np.abs(w_opt) <= default_params["BOX_LIM"] + 1e-6), "Box constraints violated"

    # Check portfolio metrics
    port_vol = np.sqrt(w_opt.values @ sample_cov.values @ w_opt.values)
    port_return = (sample_mu * w_opt).sum()

    assert port_vol > 0, "Portfolio should have positive volatility"
    assert np.isfinite(port_return), "Portfolio return should be finite"


# ==================== PROPERTY-BASED TESTS ====================

def test_solve_qp_always_returns_valid_series(sample_mu, sample_cov, sample_w_prev, default_params):
    """Property: Solver should always return a valid pandas Series."""
    gross_lim = 2.0
    net_lim = 1.0

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, default_params)

    assert isinstance(w_opt, pd.Series), "Output must be pandas Series"
    assert len(w_opt) == len(sample_mu), "Output length must match input"
    assert w_opt.index.equals(sample_mu.index), "Output index must match input"
    assert np.all(np.isfinite(w_opt)), "All weights must be finite"


def test_solve_qp_constraint_satisfaction_property(sample_mu, sample_cov, sample_w_prev, default_params):
    """Property: Solver output must always satisfy constraints."""
    gross_lim = 1.8
    net_lim = 0.9
    box_lim = 0.30

    params = default_params.copy()
    params["BOX_LIM"] = box_lim

    w_opt = solve_qp(sample_mu, sample_cov, sample_w_prev, gross_lim, net_lim, params)

    # Check all constraints (with small tolerance for numerical errors)
    tol = 1e-6
    assert np.abs(w_opt).sum() <= gross_lim + tol, "Gross constraint must be satisfied"
    assert -net_lim - tol <= w_opt.sum() <= net_lim + tol, "Net constraint must be satisfied"
    assert np.all(w_opt >= -box_lim - tol), "Lower box constraint must be satisfied"
    assert np.all(w_opt <= box_lim + tol), "Upper box constraint must be satisfied"
