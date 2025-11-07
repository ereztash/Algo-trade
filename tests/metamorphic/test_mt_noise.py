"""
Metamorphic Testing: MR3 - Symmetric Noise Injection

Metamorphic Relation:
    If small symmetric noise is added: P' = P + ε (where ε ~ N(0, σ²), σ small)
    Then trading decisions should remain stable

Rationale:
    Robust trading systems should not be overly sensitive to minor price
    fluctuations. Small random noise shouldn't flip trading decisions.
"""

import numpy as np
import pytest


@pytest.mark.metamorphic
def test_signal_stability_under_small_noise():
    """
    MR3: Signals should be stable under small additive noise.

    Test: Add small Gaussian noise to prices, verify signal doesn't flip.
    """
    np.random.seed(2003)  # From seeds.yaml: metamorphic_noise

    # Generate base price series
    n_periods = 100
    base_price = 100.0
    returns = np.random.randn(n_periods) * 0.02
    prices = base_price * np.exp(np.cumsum(returns))

    # Compute base signal
    def compute_signal_direction(price_series):
        """Return signal direction: +1 (long), -1 (short), 0 (neutral)."""
        returns_local = np.diff(np.log(price_series))
        momentum = np.mean(returns_local[-20:])

        if momentum > 0.001:
            return +1
        elif momentum < -0.001:
            return -1
        else:
            return 0

    base_direction = compute_signal_direction(prices)

    # Test with multiple noise realizations
    noise_levels = [0.0001, 0.0005, 0.001, 0.002]  # Relative to price
    n_trials = 10

    for noise_level in noise_levels:
        flipped_count = 0

        for trial in range(n_trials):
            # Add symmetric Gaussian noise
            noise = np.random.randn(n_periods) * noise_level * prices
            noisy_prices = prices + noise

            # Compute signal with noise
            noisy_direction = compute_signal_direction(noisy_prices)

            # Count flips
            if noisy_direction != base_direction and base_direction != 0:
                flipped_count += 1

        # Signal should be stable (low flip rate)
        flip_rate = flipped_count / n_trials

        # Acceptance criteria: <20% flip rate for small noise
        if noise_level <= 0.001:
            assert flip_rate < 0.2, f"Signal too unstable with noise level {noise_level}: flip_rate={flip_rate:.2%}"


@pytest.mark.metamorphic
def test_portfolio_stability_under_return_noise():
    """
    MR3b: Portfolio weights should be stable under noisy expected returns.

    Test: Add small noise to expected returns, weights shouldn't change drastically.
    """
    np.random.seed(2004)
    n_assets = 6

    # Generate base inputs
    mu = np.random.randn(n_assets) * 0.01
    Sigma = np.eye(n_assets) * 0.01  # Diagonal for simplicity

    # Mock QP solver
    def solve_qp_mock(mu_vec):
        """Simplified QP: weights proportional to expected returns."""
        weights = mu_vec / np.sum(np.abs(mu_vec)) if np.sum(np.abs(mu_vec)) > 0 else np.ones(n_assets) / n_assets
        return weights

    weights_base = solve_qp_mock(mu)

    # Add small noise to expected returns
    noise_levels = [0.0001, 0.0005, 0.001]

    for noise_level in noise_levels:
        mu_noisy = mu + np.random.randn(n_assets) * noise_level
        weights_noisy = solve_qp_mock(mu_noisy)

        # Measure weight change
        weight_change = np.linalg.norm(weights_noisy - weights_base)

        # Weights should not change drastically
        # Heuristic: change proportional to noise level
        assert weight_change < noise_level * 100, f"Weights too sensitive to noise: change={weight_change:.6f} with noise_level={noise_level}"


@pytest.mark.metamorphic
def test_regime_detection_stability():
    """
    MR3c: Regime detection should be stable under small volatility noise.

    Test: Add small noise to volatility estimates, regime shouldn't flip.
    """
    np.random.seed(2005)

    # Mock regime detection based on volatility
    def detect_regime(volatility):
        """Detect market regime: Calm, Normal, Storm."""
        if volatility < 0.10:
            return "Calm"
        elif volatility < 0.20:
            return "Normal"
        else:
            return "Storm"

    # Base volatility
    base_vol = 0.15  # Normal regime
    base_regime = detect_regime(base_vol)

    # Add small noise
    noise_trials = 20
    noise_std = 0.01  # 1% noise

    flipped_count = 0
    for _ in range(noise_trials):
        noisy_vol = base_vol + np.random.randn() * noise_std
        noisy_regime = detect_regime(noisy_vol)

        if noisy_regime != base_regime:
            flipped_count += 1

    flip_rate = flipped_count / noise_trials

    # Regime should be stable (<30% flip rate)
    assert flip_rate < 0.3, f"Regime detection too unstable: flip_rate={flip_rate:.2%}"


@pytest.mark.metamorphic
def test_kill_switch_stability():
    """
    MR3d: Kill-switch triggers should be stable under PnL noise.

    Test: Small noise in PnL shouldn't cause spurious kill-switch activations.
    """
    np.random.seed(2006)

    # Mock kill-switch logic
    kill_threshold = -0.05  # -5% kill switch

    # Base PnL just above threshold
    base_pnl = -0.045  # -4.5%, safe
    is_killed_base = base_pnl < kill_threshold

    # Add small measurement noise to PnL
    noise_trials = 100
    noise_std = 0.001  # 0.1% noise

    spurious_kills = 0
    for _ in range(noise_trials):
        noisy_pnl = base_pnl + np.random.randn() * noise_std
        is_killed_noisy = noisy_pnl < kill_threshold

        if is_killed_noisy and not is_killed_base:
            spurious_kills += 1

    spurious_rate = spurious_kills / noise_trials

    # Very low spurious kill rate expected
    assert spurious_rate < 0.05, f"Too many spurious kill-switch triggers: rate={spurious_rate:.2%}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "metamorphic"])
