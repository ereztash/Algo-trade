"""
Unit tests for risk management modules.

Tests:
- covariance: Adaptive covariance estimation (EWMA, Ledoit-Wolf, PSD correction)
- drawdown: Drawdown calculation and analysis
- regime_detection: Market regime detection with HMM
"""

import pytest
import numpy as np
import pandas as pd
from hypothesis import given, strategies as st, settings

from algo_trade.core.risk.covariance import (
    _ewma_cov,
    _lw_cov,
    _fix_psd,
    adaptive_cov
)
from algo_trade.core.risk.drawdown import (
    calculate_drawdown,
    max_drawdown,
    analyze_drawdowns
)
from algo_trade.core.risk.regime_detection import (
    avg_corr,
    detect_regime
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_returns():
    """Create sample return data."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=200, freq='D')
    data = pd.DataFrame({
        'AAPL': np.random.randn(200) * 0.02,
        'MSFT': np.random.randn(200) * 0.015,
        'GOOGL': np.random.randn(200) * 0.018,
        'TSLA': np.random.randn(200) * 0.03,
    }, index=dates)
    return data


@pytest.fixture
def sample_equity_curve():
    """Create sample equity curve."""
    np.random.seed(42)
    returns = np.random.randn(100) * 0.02
    equity = (1 + pd.Series(returns)).cumprod()
    return equity


@pytest.fixture
def risk_config():
    """Standard risk configuration."""
    return {
        'SIGMA_DAILY': 0.01,
        'REGIME_WIN': 60,
        'EWMA_HALFLIFE': 30,
        'LW_SHRINKAGE': 0.5,
    }


# ============================================================================
# Tests for Covariance Module
# ============================================================================

@pytest.mark.unit
class TestCovariance:
    """Tests for covariance estimation."""

    def test_ewma_cov_basic(self, sample_returns):
        """Test basic EWMA covariance calculation."""
        result = _ewma_cov(sample_returns, halflife=30)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (4, 4)
        assert result.index.equals(sample_returns.columns)
        assert result.columns.equals(sample_returns.columns)

    def test_ewma_cov_is_symmetric(self, sample_returns):
        """EWMA covariance should be symmetric."""
        result = _ewma_cov(sample_returns, halflife=30)

        assert np.allclose(result.values, result.values.T, atol=1e-10)

    def test_ewma_cov_empty_input(self):
        """Test EWMA with empty DataFrame."""
        df = pd.DataFrame()
        result = _ewma_cov(df, halflife=30)

        assert result.empty

    def test_ewma_cov_single_asset(self):
        """Test EWMA with single asset."""
        df = pd.DataFrame({'A': np.random.randn(100)})
        result = _ewma_cov(df, halflife=30)

        assert result.shape == (1, 1)
        assert result.iloc[0, 0] >= 0  # Variance should be non-negative

    def test_lw_cov_basic(self, sample_returns):
        """Test Ledoit-Wolf covariance."""
        result = _lw_cov(sample_returns)

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (4, 4)

    def test_lw_cov_is_symmetric(self, sample_returns):
        """Ledoit-Wolf covariance should be symmetric."""
        result = _lw_cov(sample_returns)

        assert np.allclose(result.values, result.values.T, atol=1e-10)

    def test_lw_cov_is_psd(self, sample_returns):
        """Ledoit-Wolf covariance should be PSD."""
        result = _lw_cov(sample_returns)

        eigenvalues = np.linalg.eigvalsh(result.values)
        assert (eigenvalues >= -1e-8).all()

    def test_fix_psd_basic(self):
        """Test PSD correction."""
        # Create non-PSD matrix
        M = pd.DataFrame([
            [1.0, 2.0],
            [2.0, 1.0]
        ], index=['A', 'B'], columns=['A', 'B'])

        result = _fix_psd(M)

        eigenvalues = np.linalg.eigvalsh(result.values)
        assert (eigenvalues >= -1e-8).all()

    def test_fix_psd_already_psd(self):
        """Test PSD correction on already PSD matrix."""
        M = pd.DataFrame(np.eye(3), index=['A', 'B', 'C'], columns=['A', 'B', 'C'])

        result = _fix_psd(M)

        # Should remain unchanged (or very close)
        assert np.allclose(result.values, M.values, atol=1e-8)

    def test_fix_psd_empty(self):
        """Test PSD correction with empty matrix."""
        M = pd.DataFrame()
        result = _fix_psd(M)

        assert result.empty

    def test_adaptive_cov_calm_regime(self, sample_returns, risk_config):
        """Test adaptive covariance in Calm regime."""
        result = adaptive_cov(
            returns=sample_returns,
            regime='Calm',
            T_N_ratio=50.0,  # High T/N
            config=risk_config
        )

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (4, 4)

        # Should be PSD
        eigenvalues = np.linalg.eigvalsh(result.values)
        assert (eigenvalues >= -1e-8).all()

    def test_adaptive_cov_storm_regime(self, sample_returns, risk_config):
        """Test adaptive covariance in Storm regime."""
        result = adaptive_cov(
            returns=sample_returns,
            regime='Storm',
            T_N_ratio=10.0,  # Low T/N
            config=risk_config
        )

        assert isinstance(result, pd.DataFrame)
        assert result.shape == (4, 4)

    def test_adaptive_cov_insufficient_data(self, risk_config):
        """Test adaptive covariance with insufficient data."""
        returns = pd.DataFrame({
            'A': [0.01, 0.02],
            'B': [0.015, 0.018]
        })

        result = adaptive_cov(
            returns=returns,
            regime='Normal',
            T_N_ratio=1.0,
            config=risk_config
        )

        # Should return identity-like matrix
        assert isinstance(result, pd.DataFrame)


# ============================================================================
# Tests for Drawdown Module
# ============================================================================

@pytest.mark.unit
class TestDrawdown:
    """Tests for drawdown calculations."""

    def test_calculate_drawdown_basic(self, sample_equity_curve):
        """Test basic drawdown calculation."""
        result = calculate_drawdown(sample_equity_curve)

        assert isinstance(result, pd.DataFrame)
        assert 'equity' in result.columns
        assert 'peak' in result.columns
        assert 'drawdown' in result.columns
        assert len(result) == len(sample_equity_curve)

    def test_calculate_drawdown_properties(self, sample_equity_curve):
        """Test drawdown properties."""
        result = calculate_drawdown(sample_equity_curve)

        # Peak should always be >= equity
        assert (result['peak'] >= result['equity'] - 1e-10).all()

        # Drawdown should be non-negative
        assert (result['drawdown'] >= -1e-10).all()

        # Drawdown should be <= 1
        assert (result['drawdown'] <= 1.0 + 1e-10).all()

    def test_calculate_drawdown_monotonic_increase(self):
        """Test drawdown with always-increasing equity."""
        equity = pd.Series([100, 110, 120, 130, 140])
        result = calculate_drawdown(equity)

        # No drawdown if always increasing
        assert (result['drawdown'] == 0).all()

    def test_calculate_drawdown_single_drop(self):
        """Test drawdown with single drop."""
        equity = pd.Series([100, 110, 90, 100, 110])
        result = calculate_drawdown(equity)

        # Should have drawdown at index 2
        assert result['drawdown'].iloc[2] > 0
        # Max drawdown should be around 18.18% (90/110 - 1)
        max_dd = result['drawdown'].max()
        assert 0.18 < max_dd < 0.19

    def test_calculate_drawdown_empty(self):
        """Test drawdown with empty equity curve."""
        equity = pd.Series([])
        result = calculate_drawdown(equity)

        assert result.empty

    def test_max_drawdown_basic(self):
        """Test maximum drawdown calculation."""
        pnl_hist = [0.01, 0.02, -0.05, -0.03, 0.04, 0.02]
        result = max_drawdown(pnl_hist)

        assert isinstance(result, float)
        assert 0 <= result <= 1

    def test_max_drawdown_no_losses(self):
        """Test max drawdown with no losses."""
        pnl_hist = [0.01, 0.02, 0.03, 0.01, 0.02]
        result = max_drawdown(pnl_hist)

        assert result == 0.0

    def test_max_drawdown_all_losses(self):
        """Test max drawdown with all losses."""
        pnl_hist = [-0.01, -0.02, -0.03]
        result = max_drawdown(pnl_hist)

        # Should have significant drawdown
        assert result > 0.05

    def test_max_drawdown_empty(self):
        """Test max drawdown with empty history."""
        result = max_drawdown([])
        assert result == 0.0

    def test_analyze_drawdowns_basic(self):
        """Test drawdown analysis."""
        pnl_hist = [0.01, 0.02, -0.05, -0.03, 0.04, 0.02, -0.02, 0.03]
        result = analyze_drawdowns(pnl_hist)

        assert isinstance(result, dict)
        assert 'max_drawdown' in result
        assert 'average_drawdown' in result
        assert 'longest_recovery_period' in result
        assert 'average_recovery_period' in result
        assert 'num_drawdowns' in result

    def test_analyze_drawdowns_empty(self):
        """Test drawdown analysis with empty history."""
        result = analyze_drawdowns([])

        assert result['max_drawdown'] == 0.0
        assert result['num_drawdowns'] == 0


# ============================================================================
# Tests for Regime Detection Module
# ============================================================================

@pytest.mark.unit
class TestRegimeDetection:
    """Tests for market regime detection."""

    def test_avg_corr_basic(self, sample_returns):
        """Test average correlation calculation."""
        result = avg_corr(sample_returns)

        assert isinstance(result, float)
        assert -1 <= result <= 1

    def test_avg_corr_single_asset(self):
        """Test avg_corr with single asset."""
        df = pd.DataFrame({'A': np.random.randn(100)})
        result = avg_corr(df)

        assert result == 0.0

    def test_avg_corr_perfect_correlation(self):
        """Test avg_corr with perfectly correlated assets."""
        x = np.random.randn(100)
        df = pd.DataFrame({
            'A': x,
            'B': x,
            'C': x
        })
        result = avg_corr(df)

        # Should be close to 1
        assert result > 0.99

    def test_avg_corr_uncorrelated(self):
        """Test avg_corr with uncorrelated assets."""
        np.random.seed(42)
        df = pd.DataFrame({
            'A': np.random.randn(1000),
            'B': np.random.randn(1000),
            'C': np.random.randn(1000)
        })
        result = avg_corr(df)

        # Should be close to 0 for large sample
        assert -0.1 < result < 0.1

    def test_detect_regime_basic(self, sample_returns, risk_config):
        """Test basic regime detection."""
        regime, metrics = detect_regime(sample_returns, risk_config)

        assert isinstance(regime, str)
        assert regime in ['Calm', 'Normal', 'Storm']

        assert isinstance(metrics, dict)
        assert 'avg_vol' in metrics
        assert 'avg_rho' in metrics
        assert 'tail_corr' in metrics

    def test_detect_regime_insufficient_data(self, risk_config):
        """Test regime detection with insufficient data."""
        returns = pd.DataFrame({
            'A': np.random.randn(50),
            'B': np.random.randn(50)
        })

        regime, metrics = detect_regime(returns, risk_config)

        assert regime == 'Normal'  # Default regime

    def test_detect_regime_high_volatility(self, risk_config):
        """Test regime detection with high volatility."""
        # Create high volatility data
        returns = pd.DataFrame({
            'A': np.random.randn(200) * 0.1,  # 10% daily vol
            'B': np.random.randn(200) * 0.1
        })

        regime, metrics = detect_regime(returns, risk_config)

        # Should detect some turbulence
        assert metrics['avg_vol'] > 0


# ============================================================================
# Property-Based Tests
# ============================================================================

@pytest.mark.property
class TestRiskProperties:
    """Property-based tests for risk module."""

    @given(
        data=st.lists(
            st.floats(min_value=-0.1, max_value=0.1),
            min_size=10,
            max_size=100
        )
    )
    @settings(max_examples=20, deadline=None)
    def test_max_drawdown_bounds(self, data):
        """Max drawdown should always be in [0, 1]."""
        result = max_drawdown(data)

        assert 0 <= result <= 1

    @given(
        n_assets=st.integers(min_value=2, max_value=5),
        n_obs=st.integers(min_value=50, max_value=100)
    )
    @settings(max_examples=10, deadline=None)
    def test_covariance_psd(self, n_assets, n_obs):
        """Adaptive covariance should always be PSD."""
        np.random.seed(42)
        returns = pd.DataFrame(
            np.random.randn(n_obs, n_assets) * 0.02,
            columns=[f'A{i}' for i in range(n_assets)]
        )
        config = {'SIGMA_DAILY': 0.01, 'EWMA_HALFLIFE': 20}

        result = adaptive_cov(returns, 'Normal', float(n_obs / n_assets), config)

        eigenvalues = np.linalg.eigvalsh(result.values)
        assert (eigenvalues >= -1e-6).all()


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestRiskIntegration:
    """Integration tests for risk module."""

    def test_risk_workflow(self, sample_returns, risk_config):
        """Test full risk assessment workflow."""
        # 1. Detect regime
        regime, metrics = detect_regime(sample_returns, risk_config)

        # 2. Calculate adaptive covariance
        T_N_ratio = len(sample_returns) / sample_returns.shape[1]
        cov = adaptive_cov(sample_returns, regime, T_N_ratio, risk_config)

        # 3. Simulate equity curve
        weights = np.ones(sample_returns.shape[1]) / sample_returns.shape[1]
        portfolio_returns = (sample_returns * weights).sum(axis=1)
        equity = (1 + portfolio_returns).cumprod()

        # 4. Calculate drawdown
        dd_df = calculate_drawdown(equity)
        max_dd = dd_df['drawdown'].max()

        # All metrics should be valid
        assert regime in ['Calm', 'Normal', 'Storm']
        assert cov.shape == (4, 4)
        assert 0 <= max_dd <= 1
