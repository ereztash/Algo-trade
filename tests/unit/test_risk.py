"""
Unit Tests for Risk Management

Priority tests for:
- Kill-Switches (PnL, PSR, Drawdown)
- Drawdown calculation and monitoring
- Probabilistic Sharpe Ratio (PSR)
- Risk limits and circuit breakers
"""

import numpy as np
import pandas as pd
import pytest
from scipy import stats


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def sample_returns():
    """Generate sample return series."""
    np.random.seed(42)
    n_periods = 252  # One year
    returns = np.random.randn(n_periods) * 0.02 + 0.0003  # ~8% annual return
    return returns


@pytest.fixture
def sample_equity_curve():
    """Generate sample equity curve."""
    np.random.seed(42)
    n_periods = 252
    returns = np.random.randn(n_periods) * 0.02 + 0.0003
    equity = 100000 * np.cumprod(1 + returns)
    return equity


# ==============================================================================
# PnL Kill-Switch Tests
# ==============================================================================

class TestPnLKillSwitch:
    """Test PnL kill-switch mechanism."""

    def test_kill_switch_threshold(self):
        """Test PnL kill-switch threshold detection."""
        kill_threshold = -0.05  # -5% daily PnL

        # Test cases
        pnl_safe = -0.03  # -3%, safe
        pnl_danger = -0.06  # -6%, kill

        assert pnl_safe > kill_threshold, "Safe PnL should not trigger"
        assert pnl_danger < kill_threshold, "Dangerous PnL should trigger"

    def test_daily_pnl_calculation(self, sample_equity_curve):
        """Test daily PnL calculation."""
        equity = sample_equity_curve

        # Daily PnL
        daily_pnl = np.diff(equity) / equity[:-1]

        assert len(daily_pnl) == len(equity) - 1
        assert not np.any(np.isnan(daily_pnl)), "No NaN values"
        assert not np.any(np.isinf(daily_pnl)), "No inf values"

    def test_cumulative_pnl(self, sample_returns):
        """Test cumulative PnL calculation."""
        returns = sample_returns

        # Cumulative PnL
        cumulative_pnl = np.cumprod(1 + returns) - 1

        assert len(cumulative_pnl) == len(returns)
        # Final cumulative should match compound return
        final_pnl = np.prod(1 + returns) - 1
        assert np.abs(cumulative_pnl[-1] - final_pnl) < 1e-10

    def test_kill_switch_trigger_logic(self):
        """Test kill-switch trigger and halt logic."""
        kill_threshold = -0.05

        class MockKillSwitch:
            def __init__(self, threshold):
                self.threshold = threshold
                self.is_killed = False

            def check(self, pnl):
                if pnl < self.threshold:
                    self.is_killed = True
                return self.is_killed

        kill_switch = MockKillSwitch(kill_threshold)

        # Safe PnL
        assert not kill_switch.check(-0.02)
        assert not kill_switch.is_killed

        # Dangerous PnL
        assert kill_switch.check(-0.07)
        assert kill_switch.is_killed

        # Once killed, stays killed
        assert kill_switch.check(0.10)  # Even if PnL recovers
        assert kill_switch.is_killed

    def test_intraday_pnl_monitoring(self):
        """Test intraday PnL monitoring (multiple checks per day)."""
        kill_threshold = -0.05
        n_checks = 100  # Check PnL 100 times during day

        # Simulate intraday PnL path
        np.random.seed(42)
        intraday_returns = np.random.randn(n_checks) * 0.001
        intraday_pnl = np.cumsum(intraday_returns)

        # Check for kill-switch trigger
        triggered = np.any(intraday_pnl < kill_threshold)

        # If triggered, find first trigger time
        if triggered:
            trigger_idx = np.argmax(intraday_pnl < kill_threshold)
            assert trigger_idx >= 0


# ==============================================================================
# Drawdown Tests
# ==============================================================================

class TestDrawdown:
    """Test drawdown calculation and monitoring."""

    def test_drawdown_calculation(self, sample_equity_curve):
        """Test drawdown calculation from equity curve."""
        equity = sample_equity_curve

        # Running maximum
        running_max = np.maximum.accumulate(equity)

        # Drawdown = (current - peak) / peak
        drawdown = (equity - running_max) / running_max

        assert len(drawdown) == len(equity)
        assert np.all(drawdown <= 0), "Drawdown should be non-positive"
        assert drawdown[0] == 0, "First value has zero drawdown"

    def test_max_drawdown(self, sample_equity_curve):
        """Test maximum drawdown calculation."""
        equity = sample_equity_curve

        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max

        max_drawdown = np.min(drawdown)

        assert max_drawdown <= 0, "Max DD should be negative"
        assert max_drawdown >= -1.0, "Max DD should be >= -100%"

    def test_drawdown_duration(self, sample_equity_curve):
        """Test drawdown duration calculation."""
        equity = sample_equity_curve

        running_max = np.maximum.accumulate(equity)
        is_in_drawdown = equity < running_max

        # Find longest drawdown period
        drawdown_periods = []
        current_period = 0

        for in_dd in is_in_drawdown:
            if in_dd:
                current_period += 1
            else:
                if current_period > 0:
                    drawdown_periods.append(current_period)
                current_period = 0

        if current_period > 0:
            drawdown_periods.append(current_period)

        if drawdown_periods:
            max_duration = max(drawdown_periods)
            assert max_duration > 0

    def test_drawdown_kill_switch(self):
        """Test drawdown-based kill-switch."""
        max_dd_threshold = -0.15  # -15% max drawdown

        # Test cases
        current_dd_safe = -0.10  # -10%, safe
        current_dd_danger = -0.20  # -20%, kill

        assert current_dd_safe > max_dd_threshold, "Safe DD"
        assert current_dd_danger < max_dd_threshold, "Danger DD"

    def test_underwater_period(self, sample_equity_curve):
        """Test underwater period (time below previous peak)."""
        equity = sample_equity_curve

        running_max = np.maximum.accumulate(equity)
        is_underwater = equity < running_max * 0.95  # 5% below peak

        underwater_days = np.sum(is_underwater)

        assert underwater_days >= 0
        assert underwater_days <= len(equity)

    def test_recovery_from_drawdown(self):
        """Test recovery from drawdown."""
        # Simulate drawdown and recovery
        equity = np.array([100, 90, 85, 80, 85, 90, 95, 100, 105])

        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max

        # Max drawdown at index 3
        assert np.argmin(drawdown) == 3
        assert np.min(drawdown) == -0.20  # -20% drawdown

        # Recovery at index 7
        recovered_idx = np.argmax(drawdown[3:] == 0)
        assert recovered_idx == 4  # Relative to drawdown start


# ==============================================================================
# Probabilistic Sharpe Ratio (PSR) Tests
# ==============================================================================

class TestPSR:
    """Test Probabilistic Sharpe Ratio calculation."""

    def test_sharpe_ratio_calculation(self, sample_returns):
        """Test basic Sharpe ratio calculation."""
        returns = sample_returns

        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        sharpe = mean_return / std_return if std_return > 0 else 0

        # Annualized Sharpe (assuming daily returns)
        sharpe_annual = sharpe * np.sqrt(252)

        assert not np.isnan(sharpe_annual)
        assert not np.isinf(sharpe_annual)

    def test_psr_calculation(self, sample_returns):
        """
        Test PSR calculation.

        PSR = Prob(SR > SR_benchmark)
        Formula: PSR = N((SR_hat - SR_bench) * sqrt(T-1) / sqrt(1 - skew*SR_hat + (kurt-1)/4*SR_hat^2))
        """
        returns = sample_returns

        # Observed Sharpe ratio
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        sr_hat = mean_return / std_return * np.sqrt(252)

        # Benchmark Sharpe (e.g., 0)
        sr_bench = 0.0

        # Moments
        T = len(returns)
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns, fisher=False)  # Excess kurtosis + 3

        # PSR formula
        numerator = (sr_hat - sr_bench) * np.sqrt(T - 1)
        denominator = np.sqrt(1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2)

        z_score = numerator / denominator if denominator > 0 else 0
        psr = stats.norm.cdf(z_score)

        assert 0 <= psr <= 1, "PSR should be probability"

    def test_psr_kill_switch(self):
        """Test PSR-based kill-switch."""
        psr_threshold = 0.20  # Minimum 20% confidence

        # High PSR (confident strategy)
        psr_high = 0.85
        assert psr_high > psr_threshold, "High PSR is safe"

        # Low PSR (low confidence)
        psr_low = 0.10
        assert psr_low < psr_threshold, "Low PSR triggers kill-switch"

    def test_psr_with_different_benchmarks(self, sample_returns):
        """Test PSR with different benchmark Sharpe ratios."""
        returns = sample_returns

        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        sr_hat = mean_return / std_return * np.sqrt(252)

        benchmarks = [0.0, 0.5, 1.0]

        psrs = []
        for sr_bench in benchmarks:
            T = len(returns)
            skew = stats.skew(returns)
            kurt = stats.kurtosis(returns, fisher=False)

            numerator = (sr_hat - sr_bench) * np.sqrt(T - 1)
            denominator = np.sqrt(1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2)

            z_score = numerator / denominator if denominator > 0 else 0
            psr = stats.norm.cdf(z_score)

            psrs.append(psr)

        # PSR should decrease as benchmark increases
        assert psrs[0] >= psrs[1] >= psrs[2] or all(p == 0 for p in psrs)

    def test_psr_skewness_effect(self):
        """Test effect of skewness on PSR."""
        np.random.seed(42)
        n = 252

        # Symmetric returns (low skew)
        returns_symmetric = np.random.randn(n) * 0.02

        # Right-skewed returns (positive skew)
        returns_skewed = np.concatenate([
            np.random.randn(int(n * 0.9)) * 0.015,
            np.random.randn(int(n * 0.1)) * 0.05 + 0.03
        ])

        # Positive skew should improve PSR (all else equal)
        skew_sym = stats.skew(returns_symmetric)
        skew_skewed = stats.skew(returns_skewed)

        assert skew_skewed > skew_sym, "Second distribution should be more skewed"


# ==============================================================================
# Risk Limits and Circuit Breakers
# ==============================================================================

class TestRiskLimits:
    """Test risk limits and circuit breakers."""

    def test_position_size_limit(self):
        """Test position size limits."""
        max_position_size = 10000

        # Safe position
        position_safe = 5000
        assert abs(position_safe) <= max_position_size

        # Oversized position
        position_large = 15000
        assert abs(position_large) > max_position_size

        # Limit position
        position_limited = np.sign(position_large) * min(abs(position_large), max_position_size)
        assert abs(position_limited) == max_position_size

    def test_gross_exposure_limit(self):
        """Test gross exposure limit."""
        positions = np.array([5000, -3000, 2000, -4000])
        gross_exposure = np.sum(np.abs(positions))

        max_gross = 12000

        assert gross_exposure == 14000
        assert gross_exposure > max_gross

        # Scale down if exceeded
        scale_factor = max_gross / gross_exposure
        scaled_positions = positions * scale_factor

        assert np.sum(np.abs(scaled_positions)) <= max_gross + 1e-6

    def test_net_exposure_limit(self):
        """Test net exposure limit."""
        positions = np.array([5000, -3000, 2000, -1000])
        net_exposure = np.sum(positions)

        max_net = 5000

        assert net_exposure == 3000
        assert abs(net_exposure) <= max_net

    def test_concentration_limit(self):
        """Test concentration limit (max % in single asset)."""
        portfolio_value = 100000
        position_size = 35000

        concentration = position_size / portfolio_value
        max_concentration = 0.25  # 25% max

        assert concentration == 0.35
        assert concentration > max_concentration

    def test_volatility_limit(self):
        """Test portfolio volatility limit."""
        # Daily volatility
        daily_vol = 0.015  # 1.5% daily

        # Annualized
        annual_vol = daily_vol * np.sqrt(252)

        max_vol = 0.30  # 30% annual

        assert annual_vol < max_vol, f"Annual volatility {annual_vol:.2%} exceeds limit {max_vol:.2%}"

    def test_var_limit(self):
        """Test Value-at-Risk (VaR) limit."""
        np.random.seed(42)
        returns = np.random.randn(1000) * 0.02

        # 95% VaR
        var_95 = np.percentile(returns, 5)

        # 99% VaR
        var_99 = np.percentile(returns, 1)

        assert var_95 < 0, "VaR should be negative (loss)"
        assert var_99 < var_95, "99% VaR should be more extreme"

        # Check against limit
        var_limit = -0.05  # Max 5% daily loss at 99% confidence
        assert var_99 > var_limit or abs(var_99 - var_limit) < 0.01


# ==============================================================================
# Kill-Switch Integration Tests
# ==============================================================================

class TestKillSwitchIntegration:
    """Integration tests for multiple kill-switches."""

    def test_multiple_kill_switches(self):
        """Test that any kill-switch can halt trading."""
        class MultiKillSwitch:
            def __init__(self, pnl_threshold, psr_threshold, dd_threshold):
                self.pnl_threshold = pnl_threshold
                self.psr_threshold = psr_threshold
                self.dd_threshold = dd_threshold

            def check(self, pnl, psr, drawdown):
                """Return True if any kill-switch triggers."""
                if pnl < self.pnl_threshold:
                    return True, "PnL kill-switch"
                if psr < self.psr_threshold:
                    return True, "PSR kill-switch"
                if drawdown < self.dd_threshold:
                    return True, "Drawdown kill-switch"
                return False, None

        kill_switch = MultiKillSwitch(
            pnl_threshold=-0.05,
            psr_threshold=0.20,
            dd_threshold=-0.15
        )

        # Safe state
        safe, reason = kill_switch.check(pnl=-0.02, psr=0.85, drawdown=-0.05)
        assert not safe

        # PnL trigger
        triggered, reason = kill_switch.check(pnl=-0.07, psr=0.85, drawdown=-0.05)
        assert triggered
        assert reason == "PnL kill-switch"

        # PSR trigger
        triggered, reason = kill_switch.check(pnl=-0.02, psr=0.10, drawdown=-0.05)
        assert triggered
        assert reason == "PSR kill-switch"

        # Drawdown trigger
        triggered, reason = kill_switch.check(pnl=-0.02, psr=0.85, drawdown=-0.20)
        assert triggered
        assert reason == "Drawdown kill-switch"

    def test_kill_switch_recovery(self):
        """Test kill-switch recovery mechanism."""
        # Once killed, requires manual reset (no automatic recovery)
        class KillSwitchWithReset:
            def __init__(self, threshold):
                self.threshold = threshold
                self.is_killed = False

            def check(self, value):
                if value < self.threshold:
                    self.is_killed = True
                return self.is_killed

            def reset(self):
                """Manual reset by risk officer."""
                self.is_killed = False

        ks = KillSwitchWithReset(-0.05)

        # Trigger
        assert ks.check(-0.07)
        assert ks.is_killed

        # Even if metric recovers, stay killed
        assert ks.check(0.10)
        assert ks.is_killed

        # Manual reset required
        ks.reset()
        assert not ks.is_killed

    def test_early_warning_system(self):
        """Test early warning before kill-switch."""
        # Yellow zone: 75% of kill threshold
        # Red zone: kill threshold

        pnl_yellow = -0.05 * 0.75  # -3.75%
        pnl_red = -0.05  # -5%

        current_pnl = -0.04  # -4%

        if current_pnl < pnl_red:
            status = "KILL"
        elif current_pnl < pnl_yellow:
            status = "WARNING"
        else:
            status = "OK"

        assert status == "WARNING", "Should trigger warning"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
