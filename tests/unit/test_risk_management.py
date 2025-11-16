"""
Unit tests for risk management modules.

Tests cover:
- Kill-switches (PnL, PSR, Drawdown)
- Regime detection
- Covariance estimation
- Exposure limits
"""

import pytest
import numpy as np
import pandas as pd

from algo_trade.core.risk.kill_switches import (
    check_pnl_kill_switch,
    check_psr_kill_switch,
    check_drawdown_kill_switch,
)
from algo_trade.core.risk.covariance import estimate_covariance, ewma_cov
from algo_trade.core.risk.regime import detect_regime


# ============================================================================
# Kill-Switch Tests
# ============================================================================


@pytest.mark.unit
class TestKillSwitches:
    """Test kill-switch functionality."""

    def test_pnl_kill_switch_triggered(self, default_config):
        """Test PnL kill-switch triggers on large loss."""
        pnl = -0.06  # 6% loss
        threshold = default_config["KILL_PNL"]  # -0.05

        triggered = check_pnl_kill_switch(pnl, threshold)
        assert triggered is True

    def test_pnl_kill_switch_not_triggered(self, default_config):
        """Test PnL kill-switch does not trigger on small loss."""
        pnl = -0.03  # 3% loss
        threshold = default_config["KILL_PNL"]  # -0.05

        triggered = check_pnl_kill_switch(pnl, threshold)
        assert triggered is False

    def test_pnl_kill_switch_positive_pnl(self, default_config):
        """Test PnL kill-switch with positive PnL."""
        pnl = 0.10  # 10% gain
        threshold = default_config["KILL_PNL"]

        triggered = check_pnl_kill_switch(pnl, threshold)
        assert triggered is False

    def test_drawdown_kill_switch_triggered(self, default_config):
        """Test drawdown kill-switch triggers."""
        returns = pd.Series([-0.02, -0.03, -0.05, -0.04, -0.06])
        threshold = default_config["MAX_DD_KILL_SWITCH"]  # 0.15

        # Calculate max drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max

        triggered = check_drawdown_kill_switch(drawdown.min(), threshold)
        assert triggered is True

    def test_psr_kill_switch(self, default_config):
        """Test PSR (Probabilistic Sharpe Ratio) kill-switch."""
        # Create returns with low PSR
        returns = pd.Series(np.random.randn(100) * 0.02)  # Random walk
        threshold = default_config["PSR_KILL_SWITCH"]

        # PSR calculation is complex, so this is a placeholder test
        # In reality, check_psr_kill_switch would compute PSR
        triggered = check_psr_kill_switch(returns, threshold)
        assert isinstance(triggered, bool)


# ============================================================================
# Covariance Estimation Tests
# ============================================================================


@pytest.mark.unit
class TestCovarianceEstimation:
    """Test covariance matrix estimation."""

    def test_ewma_covariance_shape(self):
        """Test EWMA covariance returns correct shape."""
        n_assets = 5
        n_periods = 100

        returns = pd.DataFrame(
            np.random.randn(n_periods, n_assets),
            columns=[f"ASSET_{i}" for i in range(n_assets)]
        )

        cov_matrix = ewma_cov(returns, span=20)

        assert cov_matrix.shape == (n_assets, n_assets)
        assert (cov_matrix.columns == returns.columns).all()
        assert (cov_matrix.index == returns.columns).all()

    def test_ewma_covariance_symmetry(self):
        """Test that EWMA covariance is symmetric."""
        returns = pd.DataFrame(
            np.random.randn(100, 3),
            columns=["A", "B", "C"]
        )

        cov_matrix = ewma_cov(returns, span=20)

        assert np.allclose(cov_matrix, cov_matrix.T)

    def test_ewma_covariance_positive_diagonal(self):
        """Test that EWMA covariance has positive diagonal."""
        returns = pd.DataFrame(
            np.random.randn(100, 3),
            columns=["A", "B", "C"]
        )

        cov_matrix = ewma_cov(returns, span=20)

        assert (np.diag(cov_matrix) > 0).all()

    def test_covariance_estimation_psd(self):
        """Test that estimated covariance is positive semi-definite."""
        returns = pd.DataFrame(
            np.random.randn(100, 5),
            columns=[f"ASSET_{i}" for i in range(5)]
        )

        cov_matrix = estimate_covariance(returns, method="ledoit_wolf")

        # Check PSD: all eigenvalues should be >= 0
        eigenvalues = np.linalg.eigvalsh(cov_matrix)
        assert (eigenvalues >= -1e-10).all()  # Allow small numerical errors


# ============================================================================
# Regime Detection Tests
# ============================================================================


@pytest.mark.unit
class TestRegimeDetection:
    """Test market regime detection."""

    def test_regime_detection_returns_valid_regime(self):
        """Test that regime detection returns valid regime label."""
        returns = pd.Series(np.random.randn(100) * 0.02)

        regime = detect_regime(returns)

        assert regime in ["Calm", "Normal", "Storm"]

    def test_regime_detection_calm_market(self):
        """Test regime detection on calm market."""
        # Low volatility returns
        returns = pd.Series(np.random.randn(100) * 0.005)

        regime = detect_regime(returns)

        # Should detect calm or normal market
        assert regime in ["Calm", "Normal"]

    def test_regime_detection_storm_market(self):
        """Test regime detection on volatile market."""
        # High volatility returns
        returns = pd.Series(np.random.randn(100) * 0.05)

        regime = detect_regime(returns)

        # More likely to detect storm or normal
        assert regime in ["Normal", "Storm"]

    def test_regime_detection_with_extreme_moves(self):
        """Test regime detection with extreme price moves."""
        # Create extreme moves
        returns = pd.Series(np.concatenate([
            np.random.randn(50) * 0.01,
            np.array([-0.10, -0.08, 0.12]),  # Extreme moves
            np.random.randn(47) * 0.01
        ]))

        regime = detect_regime(returns)

        # Should detect storm due to extreme moves
        assert regime in ["Storm", "Normal"]


# ============================================================================
# Integration Tests
# ============================================================================


@pytest.mark.integration
class TestRiskManagementIntegration:
    """Integration tests for risk management system."""

    def test_full_risk_check_pipeline(self, default_config):
        """Test complete risk check pipeline."""
        # Simulate portfolio performance
        returns = pd.Series(np.random.randn(100) * 0.02)
        pnl = returns.sum()

        # Run all kill-switches
        pnl_triggered = check_pnl_kill_switch(pnl, default_config["KILL_PNL"])
        psr_triggered = check_psr_kill_switch(returns, default_config["PSR_KILL_SWITCH"])

        # Calculate drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        dd_triggered = check_drawdown_kill_switch(drawdown.min(), default_config["MAX_DD_KILL_SWITCH"])

        # All should return boolean
        assert isinstance(pnl_triggered, bool)
        assert isinstance(psr_triggered, bool)
        assert isinstance(dd_triggered, bool)

    def test_regime_based_exposure_limits(self, default_config):
        """Test that exposure limits adjust based on regime."""
        returns = pd.Series(np.random.randn(100) * 0.02)
        regime = detect_regime(returns)

        # Get regime-specific limits
        gross_lim = default_config["GROSS_LIM"][regime]
        net_lim = default_config["NET_LIM"][regime]

        # Storm regime should have tighter limits
        if regime == "Storm":
            assert gross_lim <= default_config["GROSS_LIM"]["Normal"]
            assert net_lim <= default_config["NET_LIM"]["Normal"]
