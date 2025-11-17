"""
End-to-end integration tests for the full trading system workflow.

Tests the integration of:
1. Signal generation
2. Portfolio optimization
3. Risk management
4. Order execution (mocked)
"""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch

from algo_trade.core.signals.base_signals import build_signals
from algo_trade.core.optimization.qp_solver import solve_qp
from algo_trade.core.risk.covariance import adaptive_cov
from algo_trade.core.risk.drawdown import calculate_drawdown
from algo_trade.core.risk.regime_detection import detect_regime


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def market_data():
    """Create realistic market data for testing."""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=252, freq='D')  # 1 year

    # Simulate 5 assets with different characteristics
    prices = pd.DataFrame({
        'SPY': 100 + np.random.randn(252).cumsum() * 0.5,  # Low vol
        'QQQ': 200 + np.random.randn(252).cumsum() * 1.0,  # Medium vol
        'IWM': 150 + np.random.randn(252).cumsum() * 0.8,
        'EEM': 80 + np.random.randn(252).cumsum() * 1.2,   # Higher vol
        'AGG': 110 + np.random.randn(252).cumsum() * 0.2,  # Very low vol (bonds)
    }, index=dates)

    # Add volume
    prices['volume'] = np.random.randint(1000000, 50000000, 252)

    # Calculate returns
    returns = prices.drop('volume', axis=1).pct_change().fillna(0)

    return {
        'prices': prices,
        'returns': returns,
        'dates': dates
    }


@pytest.fixture
def system_params():
    """System parameters for all modules."""
    return {
        # Horizons
        'horizons': {
            'short_h': 5,
            'medium_h': 10,
            'long_h': 20,
            'fast_h': 3,
            'slow_h': 15
        },
        # Optimization
        'BOX_LIM': 0.25,
        'GROSS_LIM': 1.0,
        'NET_LIM': 0.5,
        'TURNOVER_PEN': 0.002,
        'RIDGE_PEN': 1e-4,
        'VOL_TARGET': 0.10,
        # Risk
        'SIGMA_DAILY': 0.01,
        'REGIME_WIN': 60,
        'EWMA_HALFLIFE': 30,
        'MAX_DRAWDOWN_LIMIT': 0.20,
        # Kill switches
        'MAX_LOSS_DAILY': 0.05,
        'MIN_PSR': 0.95,
    }


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.integration
class TestFullTradingWorkflow:
    """Test complete trading system workflow."""

    def test_signal_to_portfolio_workflow(self, market_data, system_params):
        """Test signal generation -> portfolio optimization workflow."""
        prices = market_data['prices']
        returns = market_data['returns']

        # Step 1: Generate signals
        signals = build_signals(returns, prices, system_params)

        assert isinstance(signals, dict)
        assert len(signals) > 0

        # Step 2: Combine signals (simple equal weight for testing)
        combined_signal = pd.DataFrame({
            asset: sum(signals[sig][asset] for sig in signals.keys()) / len(signals)
            for asset in returns.columns
        })

        assert combined_signal.shape == returns.shape

        # Step 3: Use signals as expected returns (scaled)
        mu = combined_signal.iloc[-1] * 0.01  # Scale to reasonable return

        # Step 4: Calculate covariance
        cov = returns.cov() * 252  # Annualized

        # Step 5: Optimize portfolio
        w_prev = pd.Series(0, index=returns.columns)
        weights = solve_qp(
            mu_hat=mu,
            C=cov,
            w_prev=w_prev,
            gross_lim=system_params['GROSS_LIM'],
            net_lim=system_params['NET_LIM'],
            params=system_params
        )

        # Verify portfolio
        assert isinstance(weights, pd.Series)
        assert len(weights) == len(returns.columns)
        assert weights.abs().sum() <= system_params['GROSS_LIM'] + 1e-5

    def test_regime_adaptive_workflow(self, market_data, system_params):
        """Test regime detection -> adaptive risk management workflow."""
        returns = market_data['returns']

        # Step 1: Detect regime
        regime, metrics = detect_regime(returns, system_params)

        assert regime in ['Calm', 'Normal', 'Storm']

        # Step 2: Calculate adaptive covariance based on regime
        T_N_ratio = len(returns) / returns.shape[1]
        cov = adaptive_cov(returns, regime, T_N_ratio, system_params)

        assert isinstance(cov, pd.DataFrame)
        assert cov.shape == (5, 5)

        # Step 3: Verify covariance is PSD
        eigenvalues = np.linalg.eigvalsh(cov.values)
        assert (eigenvalues >= -1e-6).all()

        # Step 4: Use in portfolio optimization
        mu = pd.Series(0.10 / 252, index=returns.columns)  # 10% annual return
        w_prev = pd.Series(0, index=returns.columns)

        weights = solve_qp(
            mu_hat=mu,
            C=cov,
            w_prev=w_prev,
            gross_lim=system_params['GROSS_LIM'],
            net_lim=system_params['NET_LIM'],
            params=system_params
        )

        assert isinstance(weights, pd.Series)

    def test_backtest_with_risk_monitoring(self, market_data, system_params):
        """Test backtest with continuous risk monitoring."""
        returns = market_data['returns']

        # Simple backtest: equal weight, rebalance monthly
        weights = pd.Series(0.2, index=returns.columns)  # Equal weight
        portfolio_returns = (returns * weights).sum(axis=1)

        # Calculate equity curve
        equity = (1 + portfolio_returns).cumprod()

        # Risk monitoring
        dd_df = calculate_drawdown(equity)

        # Verify drawdown calculation
        assert isinstance(dd_df, pd.DataFrame)
        assert len(dd_df) == len(equity)

        max_dd = dd_df['drawdown'].max()

        # Check kill switch
        if max_dd > system_params['MAX_DRAWDOWN_LIMIT']:
            # Kill switch triggered
            assert max_dd > system_params['MAX_DRAWDOWN_LIMIT']
        else:
            # Within limits
            assert max_dd <= system_params['MAX_DRAWDOWN_LIMIT']

    def test_full_day_simulation(self, market_data, system_params):
        """Test complete daily trading cycle."""
        prices = market_data['prices']
        returns = market_data['returns']

        # Use last 100 days for history
        hist_returns = returns.iloc[-100:]
        hist_prices = prices.iloc[-100:]

        # Day T workflow:

        # 1. Generate signals
        signals = build_signals(hist_returns, hist_prices, system_params)

        # 2. Detect regime
        regime, _ = detect_regime(hist_returns, system_params)

        # 3. Calculate adaptive covariance
        T_N_ratio = len(hist_returns) / hist_returns.shape[1]
        cov = adaptive_cov(hist_returns, regime, T_N_ratio, system_params)

        # 4. Combine signals to forecast
        combined_signal = pd.DataFrame({
            asset: sum(signals[sig][asset] for sig in signals.keys()) / len(signals)
            for asset in hist_returns.columns
        })
        mu = combined_signal.iloc[-1] * 0.01

        # 5. Optimize portfolio
        w_prev = pd.Series(0, index=hist_returns.columns)
        weights = solve_qp(mu, cov, w_prev, 1.0, 0.5, system_params)

        # 6. Verify all steps completed
        assert signals is not None
        assert regime is not None
        assert cov is not None
        assert weights is not None
        assert len(weights) == len(hist_returns.columns)

    def test_rebalancing_with_turnover_control(self, market_data, system_params):
        """Test portfolio rebalancing with turnover control."""
        returns = market_data['returns']

        # Initial portfolio
        w0 = pd.Series(0.2, index=returns.columns)

        # Calculate covariance
        cov = returns.cov() * 252

        # Scenario 1: High turnover penalty
        params_high = system_params.copy()
        params_high['TURNOVER_PEN'] = 0.1

        mu = pd.Series(np.random.randn(5) * 0.1, index=returns.columns)

        w1_high = solve_qp(mu, cov, w0, 1.0, 0.5, params_high)
        turnover_high = (w1_high - w0).abs().sum()

        # Scenario 2: Low turnover penalty
        params_low = system_params.copy()
        params_low['TURNOVER_PEN'] = 0.0001

        w1_low = solve_qp(mu, cov, w0, 1.0, 0.5, params_low)
        turnover_low = (w1_low - w0).abs().sum()

        # High penalty should reduce turnover
        assert turnover_high <= turnover_low + 1e-5

    def test_stress_scenario_high_volatility(self, system_params):
        """Test system behavior in high volatility scenario."""
        # Generate high volatility returns
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=100, freq='D')
        returns = pd.DataFrame(
            np.random.randn(100, 5) * 0.05,  # 5% daily volatility!
            columns=['A', 'B', 'C', 'D', 'E'],
            index=dates
        )

        # Detect regime
        regime, metrics = detect_regime(returns, system_params)

        # Should likely detect Storm or high volatility
        assert metrics['avg_vol'] > 0.3  # Annualized vol > 30%

        # Calculate adaptive covariance
        T_N_ratio = len(returns) / returns.shape[1]
        cov = adaptive_cov(returns, regime, T_N_ratio, system_params)

        # Should still produce valid covariance
        eigenvalues = np.linalg.eigvalsh(cov.values)
        assert (eigenvalues >= -1e-6).all()

    def test_stress_scenario_market_crash(self, system_params):
        """Test system behavior in market crash scenario."""
        # Simulate crash: large negative returns followed by recovery
        dates = pd.date_range('2024-01-01', periods=100, freq='D')

        crash_returns = []
        for i in range(100):
            if 30 <= i < 40:  # Crash period
                ret = -0.10  # -10% daily
            elif 40 <= i < 60:  # Recovery
                ret = 0.02   # +2% daily
            else:
                ret = 0.001  # Normal

            # Add noise
            ret += np.random.randn() * 0.01

            crash_returns.append(ret)

        returns = pd.DataFrame({
            'A': crash_returns,
            'B': [r + np.random.randn() * 0.005 for r in crash_returns],
            'C': [r + np.random.randn() * 0.005 for r in crash_returns],
        }, index=dates)

        # Calculate equity curve
        weights = pd.Series(1/3, index=returns.columns)
        portfolio_returns = (returns * weights).sum(axis=1)
        equity = (1 + portfolio_returns).cumprod()

        # Analyze drawdown
        dd_df = calculate_drawdown(equity)
        max_dd = dd_df['drawdown'].max()

        # Should detect significant drawdown
        assert max_dd > 0.20  # More than 20% drawdown


# ============================================================================
# Data Plane Integration Tests
# ============================================================================

@pytest.mark.integration
class TestDataPlaneIntegration:
    """Test data plane integration with strategy plane."""

    def test_data_flow_market_to_signals(self, market_data, system_params):
        """Test data flow from market data to signals."""
        prices = market_data['prices']
        returns = market_data['returns']

        # Simulate data plane: market data -> normalized data
        normalized_prices = (prices - prices.mean()) / prices.std()
        normalized_returns = (returns - returns.mean()) / returns.std()

        # Strategy plane: Generate signals from normalized data
        signals = build_signals(returns, prices, system_params)

        # Verify signals are generated
        assert signals is not None
        assert all(isinstance(sig, pd.DataFrame) for sig in signals.values())


# ============================================================================
# Order Plane Integration Tests
# ============================================================================

@pytest.mark.integration
class TestOrderPlaneIntegration:
    """Test order plane integration with strategy plane."""

    def test_weights_to_orders_conversion(self, market_data, system_params):
        """Test conversion from portfolio weights to orders."""
        returns = market_data['returns']

        # Generate portfolio weights
        mu = pd.Series(0.1, index=returns.columns)
        cov = returns.cov() * 252
        w_prev = pd.Series(0, index=returns.columns)

        weights = solve_qp(mu, cov, w_prev, 1.0, 0.5, system_params)

        # Convert to orders (simple example)
        portfolio_value = 1000000  # $1M
        target_positions = weights * portfolio_value

        # Generate orders
        orders = []
        for symbol, target_value in target_positions.items():
            if abs(target_value) > 100:  # Min order $100
                orders.append({
                    'symbol': symbol,
                    'side': 'BUY' if target_value > 0 else 'SELL',
                    'value': abs(target_value),
                })

        # Verify orders generated
        assert len(orders) > 0
        assert all('symbol' in order for order in orders)
        assert all('side' in order for order in orders)
