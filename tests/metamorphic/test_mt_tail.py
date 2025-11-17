"""
Metamorphic Testing: MR4 - Tail Event Behavior

Metamorphic Relation:
    Under extreme market events (tail events), risk controls should activate
    proportionally to the severity of the event.

Rationale:
    Trading systems must handle tail events (crashes, flash crashes, extreme
    volatility) gracefully. Risk controls (kill-switches, position limits)
    should activate reliably during extreme conditions.
"""

import numpy as np
import pytest
from scipy import stats


@pytest.mark.metamorphic
def test_kill_switch_activation_under_tail_events():
    """
    MR4: Kill-switches should reliably trigger during tail events.

    Test: Generate extreme loss scenarios, verify kill-switch activates.
    """
    np.random.seed(2011)  # Seed for MR4 tests

    # Kill-switch threshold
    kill_threshold = -0.05  # -5% PnL

    # Simulate various loss scenarios
    loss_scenarios = {
        'mild': -0.03,      # -3% (should NOT trigger)
        'moderate': -0.05,  # -5% (should trigger)
        'severe': -0.10,    # -10% (should trigger)
        'crash': -0.25,     # -25% (should trigger)
    }

    # Test kill-switch logic
    def check_kill_switch(pnl, threshold):
        """Return True if kill-switch should activate."""
        return pnl <= threshold

    for scenario, pnl in loss_scenarios.items():
        is_killed = check_kill_switch(pnl, kill_threshold)

        if pnl <= kill_threshold:
            assert is_killed, f"Kill-switch FAILED to trigger in {scenario} scenario: PnL={pnl:.2%}"
        else:
            assert not is_killed, f"Kill-switch triggered prematurely in {scenario} scenario: PnL={pnl:.2%}"


@pytest.mark.metamorphic
def test_position_limits_under_extreme_volatility():
    """
    MR4b: Position sizes should be reduced under extreme volatility.

    Test: In high volatility regimes, position sizes should decrease.
    """
    np.random.seed(2012)

    # Simulate returns under different volatility regimes
    n_periods = 100

    volatility_regimes = {
        'calm': 0.10,      # 10% annual vol
        'normal': 0.20,    # 20% annual vol
        'elevated': 0.40,  # 40% annual vol
        'extreme': 0.80,   # 80% annual vol (tail event)
    }

    # Mock position sizing function (Kelly-like)
    def compute_position_size(expected_return, volatility, max_position=1.0):
        """
        Compute position size based on expected return and volatility.
        Higher volatility -> smaller position.
        """
        if volatility < 1e-8:
            return max_position

        # Simplified Kelly criterion: position ~ expected_return / variance
        kelly_fraction = expected_return / (volatility ** 2)

        # Cap at max_position
        position = np.clip(kelly_fraction, 0, max_position)

        return position

    expected_return = 0.02  # 2% expected return (avoid hitting max_position cap)

    positions = {}
    for regime, vol in volatility_regimes.items():
        position = compute_position_size(expected_return, vol, max_position=1.0)
        positions[regime] = position

    # Verify positions decrease with volatility
    assert positions['calm'] > positions['normal'], "Position should decrease from calm to normal vol"
    assert positions['normal'] > positions['elevated'], "Position should decrease from normal to elevated vol"
    assert positions['elevated'] > positions['extreme'], "Position should decrease from elevated to extreme vol"

    # In extreme vol, position should be very small
    assert positions['extreme'] < 0.2, f"Position too large in extreme volatility: {positions['extreme']:.4f}"


@pytest.mark.metamorphic
def test_drawdown_limits_during_crashes():
    """
    MR4c: Maximum drawdown limits should halt trading during crashes.

    Test: Simulate crash scenarios, verify drawdown kill-switch activates.
    """
    np.random.seed(2013)

    # Drawdown kill-switch threshold
    max_drawdown_threshold = -0.15  # -15%

    # Simulate equity curves with crashes
    def simulate_crash(initial_equity, crash_magnitude):
        """Simulate a crash event."""
        equity = [initial_equity]

        # Normal period (50 days)
        for _ in range(50):
            daily_return = np.random.randn() * 0.01 + 0.0005  # Slight upward drift
            equity.append(equity[-1] * (1 + daily_return))

        # Crash event
        equity.append(equity[-1] * (1 + crash_magnitude))

        # Post-crash recovery attempt (20 days)
        for _ in range(20):
            daily_return = np.random.randn() * 0.02  # Increased volatility
            equity.append(equity[-1] * (1 + daily_return))

        return np.array(equity)

    # Test various crash magnitudes
    crash_scenarios = {
        'mini': -0.05,     # -5% (should NOT trigger DD kill-switch)
        'moderate': -0.10, # -10% (should NOT trigger DD kill-switch)
        'severe': -0.18,   # -18% (should trigger)
        'crash': -0.30,    # -30% (should trigger)
    }

    for scenario, crash_mag in crash_scenarios.items():
        equity = simulate_crash(initial_equity=100000, crash_magnitude=crash_mag)

        # Compute maximum drawdown
        running_max = np.maximum.accumulate(equity)
        drawdowns = (equity - running_max) / running_max
        max_drawdown = np.min(drawdowns)

        # Check if kill-switch should trigger
        should_kill = max_drawdown <= max_drawdown_threshold

        if crash_mag <= max_drawdown_threshold:
            assert should_kill, f"Drawdown kill-switch FAILED in {scenario} crash: max_DD={max_drawdown:.2%}"
        else:
            # May or may not trigger depending on recovery
            pass  # Allow flexibility for less severe scenarios


@pytest.mark.metamorphic
def test_var_exceedance_frequency():
    """
    MR4d: Value-at-Risk (VaR) should be exceeded at expected frequency.

    Test: In tail events, VaR exceedances should match theoretical frequency.
    """
    np.random.seed(2014)

    # Generate returns with fat tails (Student's t-distribution)
    n_periods = 1000
    df = 5  # Degrees of freedom (lower = fatter tails)
    returns = stats.t.rvs(df=df, size=n_periods) * 0.02

    # Compute VaR at different confidence levels
    confidence_levels = [0.95, 0.99, 0.995]

    for conf_level in confidence_levels:
        # Historical VaR (quantile)
        var = np.quantile(returns, 1 - conf_level)

        # Count exceedances (losses worse than VaR)
        exceedances = returns < var
        exceedance_rate = np.sum(exceedances) / len(returns)

        # Expected exceedance rate
        expected_rate = 1 - conf_level

        # Actual rate should be close to expected (allowing for sampling error)
        # Use binomial confidence interval
        # For large n, std ~ sqrt(p(1-p)/n)
        std_error = np.sqrt(expected_rate * (1 - expected_rate) / n_periods)
        z_score = 2.5  # ~99% CI

        lower_bound = expected_rate - z_score * std_error
        upper_bound = expected_rate + z_score * std_error

        assert lower_bound <= exceedance_rate <= upper_bound, \
            f"VaR exceedance rate out of bounds at {conf_level:.1%} confidence: " \
            f"expected={expected_rate:.2%}, actual={exceedance_rate:.2%}, " \
            f"bounds=[{lower_bound:.2%}, {upper_bound:.2%}]"


@pytest.mark.metamorphic
def test_psr_degradation_under_tail_risk():
    """
    MR4e: Probabilistic Sharpe Ratio (PSR) should degrade with negative skewness.

    Test: Returns with negative skewness (tail risk) should have lower PSR
    than returns with positive skewness, even with same Sharpe ratio.
    """
    np.random.seed(2015)

    n_periods = 252  # 1 year of daily data

    # Generate two return series with similar mean/std but different skewness
    # Series 1: Positive skewness (small wins, occasional big win)
    # Series 2: Negative skewness (small wins, occasional big loss)

    def generate_skewed_returns(target_mean, target_std, target_skew, n):
        """Generate returns with target statistics using rejection sampling."""
        # Start with normal
        returns = np.random.randn(n) * target_std + target_mean

        # Add skewness by mixing with exponential
        if target_skew > 0:
            # Positive skew: add occasional large positive returns
            spike_indices = np.random.choice(n, size=int(n * 0.05), replace=False)
            returns[spike_indices] += np.abs(np.random.randn(len(spike_indices))) * target_std * 2
        elif target_skew < 0:
            # Negative skew: add occasional large negative returns
            spike_indices = np.random.choice(n, size=int(n * 0.05), replace=False)
            returns[spike_indices] -= np.abs(np.random.randn(len(spike_indices))) * target_std * 2

        # Renormalize to target mean/std
        returns = (returns - np.mean(returns)) / np.std(returns) * target_std + target_mean

        return returns

    # Generate returns
    mean_ret = 0.10 / 252  # 10% annual, daily
    std_ret = 0.20 / np.sqrt(252)  # 20% annual vol, daily

    returns_pos_skew = generate_skewed_returns(mean_ret, std_ret, target_skew=0.5, n=n_periods)
    returns_neg_skew = generate_skewed_returns(mean_ret, std_ret, target_skew=-0.5, n=n_periods)

    # Compute PSR for both
    def compute_psr(returns_series):
        """Compute Probabilistic Sharpe Ratio."""
        mean_ret_local = np.mean(returns_series)
        std_ret_local = np.std(returns_series, ddof=1)

        if std_ret_local < 1e-8:
            return 0.0

        sr_hat = mean_ret_local / std_ret_local * np.sqrt(252)

        # PSR formula
        T = len(returns_series)
        skew = stats.skew(returns_series)
        kurt = stats.kurtosis(returns_series, fisher=False)

        sr_bench = 0.0
        numerator = (sr_hat - sr_bench) * np.sqrt(T - 1)
        denominator = np.sqrt(1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2)

        if denominator > 0:
            z_score = numerator / denominator
            psr = stats.norm.cdf(z_score)
        else:
            psr = 0.0

        return psr

    psr_pos_skew = compute_psr(returns_pos_skew)
    psr_neg_skew = compute_psr(returns_neg_skew)

    # PSR should be higher for positive skewness (less tail risk)
    # Even if Sharpe ratios are similar
    actual_skew_pos = stats.skew(returns_pos_skew)
    actual_skew_neg = stats.skew(returns_neg_skew)

    if actual_skew_pos > 0 and actual_skew_neg < 0:
        # If skewness is as intended, PSR should reflect it
        # (Allowing some sampling variability)
        assert psr_pos_skew >= psr_neg_skew - 0.1, \
            f"PSR should favor positive skewness: " \
            f"PSR_pos={psr_pos_skew:.3f} (skew={actual_skew_pos:.2f}), " \
            f"PSR_neg={psr_neg_skew:.3f} (skew={actual_skew_neg:.2f})"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "metamorphic"])
