"""
Metamorphic Testing: MR2 - Time-Shift Invariance

Metamorphic Relation:
    If data is shifted in time by k periods: P'(t) = P(t + k)
    Then statistical patterns and signals should remain consistent

Rationale:
    Trading strategies should recognize patterns regardless of when they occur.
    A momentum signal computed on days 1-100 should be similar to the same
    signal computed on days 101-200 (assuming similar market conditions).
"""

import numpy as np
import pytest
from scipy import stats


@pytest.mark.metamorphic
def test_signal_time_shift_consistency():
    """
    MR2: Signals computed on time-shifted windows should be consistent.

    Test: Compute signal on original window vs shifted window, verify similarity.
    """
    np.random.seed(2007)  # Seed for MR2 tests

    # Generate long price series
    n_periods = 300
    base_price = 100.0
    returns = np.random.randn(n_periods) * 0.02  # 2% daily volatility
    prices = base_price * np.exp(np.cumsum(returns))

    # Define signal computation function
    def compute_momentum_signal(price_series, lookback=20):
        """Compute momentum signal over lookback period."""
        if len(price_series) < lookback:
            return 0.0
        returns_local = np.diff(np.log(price_series))
        signal = np.mean(returns_local[-lookback:])
        return signal

    # Test windows of same length at different times
    window_size = 100
    time_shifts = [0, 50, 100, 150]

    signals = []
    for shift in time_shifts:
        if shift + window_size <= len(prices):
            window_prices = prices[shift:shift + window_size]
            signal = compute_momentum_signal(window_prices)
            signals.append(signal)

    # Signals should have similar statistical properties
    # (variance should be consistent)
    signal_array = np.array(signals)
    signal_std = np.std(signal_array)

    # The standard deviation of signals across time shifts should be small
    # relative to typical signal magnitude
    mean_abs_signal = np.mean(np.abs(signal_array))

    if mean_abs_signal > 1e-6:
        relative_std = signal_std / mean_abs_signal
        # Signals can vary, but not wildly
        assert relative_std < 2.0, f"Signals too inconsistent across time: std={signal_std:.6f}, mean_abs={mean_abs_signal:.6f}, relative_std={relative_std:.2f}"


@pytest.mark.metamorphic
def test_correlation_structure_time_invariance():
    """
    MR2b: Cross-asset correlation structure should be time-invariant.

    Test: Correlation matrix computed on different time windows should be similar.
    """
    np.random.seed(2008)
    n_assets = 4
    n_periods = 400

    # Generate correlated asset returns
    true_corr = np.array([
        [1.0, 0.6, 0.3, 0.1],
        [0.6, 1.0, 0.5, 0.2],
        [0.3, 0.5, 1.0, 0.4],
        [0.1, 0.2, 0.4, 1.0]
    ])

    # Cholesky decomposition for correlation
    L = np.linalg.cholesky(true_corr)
    raw_returns = np.random.randn(n_periods, n_assets) * 0.02
    returns = raw_returns @ L.T

    # Compute correlation on different time windows
    window_size = 100
    time_shifts = [0, 100, 200]

    corr_matrices = []
    for shift in time_shifts:
        if shift + window_size <= len(returns):
            window_returns = returns[shift:shift + window_size, :]
            corr_mat = np.corrcoef(window_returns.T)
            corr_matrices.append(corr_mat)

    # Compare correlation matrices
    # Use Frobenius norm to measure difference
    for i in range(len(corr_matrices) - 1):
        diff = np.linalg.norm(corr_matrices[i] - corr_matrices[i + 1], 'fro')

        # Correlation matrices should be similar (allowing for estimation error)
        # Frobenius norm should be small
        assert diff < 1.5, f"Correlation structure changed too much between windows {i} and {i+1}: Frobenius_norm={diff:.4f}"


@pytest.mark.metamorphic
def test_volatility_estimate_time_consistency():
    """
    MR2c: Volatility estimates should be consistent across time shifts.

    Test: Realized volatility computed on different windows should be similar
    (assuming stationary volatility process).
    """
    np.random.seed(2009)

    # Generate returns with constant volatility
    n_periods = 500
    true_vol = 0.20  # 20% annual volatility
    daily_vol = true_vol / np.sqrt(252)
    returns = np.random.randn(n_periods) * daily_vol

    # Compute realized volatility on different windows
    window_size = 100
    time_shifts = [0, 100, 200, 300]

    realized_vols = []
    for shift in time_shifts:
        if shift + window_size <= len(returns):
            window_returns = returns[shift:shift + window_size]
            # Annualized volatility
            vol = np.std(window_returns, ddof=1) * np.sqrt(252)
            realized_vols.append(vol)

    # Volatility estimates should cluster around true volatility
    mean_vol = np.mean(realized_vols)
    std_vol = np.std(realized_vols, ddof=1)

    # Mean should be close to true volatility
    assert abs(mean_vol - true_vol) < 0.05, f"Mean volatility estimate off: mean={mean_vol:.4f}, true={true_vol:.4f}"

    # Standard deviation of estimates should be small
    # (reflects estimation error, not time-dependence)
    cv = std_vol / mean_vol  # Coefficient of variation
    assert cv < 0.3, f"Volatility estimates too inconsistent across time: CV={cv:.4f}"


@pytest.mark.metamorphic
def test_sharpe_ratio_time_stability():
    """
    MR2d: Sharpe ratio should be stable across time-shifted windows.

    Test: SR computed on different time windows should be similar for
    strategies with consistent performance.
    """
    np.random.seed(2010)

    # Generate strategy returns with consistent Sharpe ratio
    n_periods = 600
    true_sharpe = 1.5  # Annualized Sharpe ratio
    daily_sharpe = true_sharpe / np.sqrt(252)

    # Generate returns: mean + noise
    mu = 0.10 / 252  # 10% annual return, daily
    sigma = mu / daily_sharpe
    returns = np.random.randn(n_periods) * sigma + mu

    # Compute Sharpe ratio on different windows
    window_size = 252  # 1 year
    time_shifts = [0, 126, 252]  # 0, 6mo, 1yr shifts

    sharpe_ratios = []
    for shift in time_shifts:
        if shift + window_size <= len(returns):
            window_returns = returns[shift:shift + window_size]
            mean_ret = np.mean(window_returns)
            std_ret = np.std(window_returns, ddof=1)

            if std_ret > 1e-8:
                sharpe = mean_ret / std_ret * np.sqrt(252)
                sharpe_ratios.append(sharpe)

    # Sharpe ratios should be similar across windows
    if len(sharpe_ratios) >= 2:
        sharpe_array = np.array(sharpe_ratios)
        mean_sharpe = np.mean(sharpe_array)
        std_sharpe = np.std(sharpe_array, ddof=1)

        # Coefficient of variation should be reasonable
        if abs(mean_sharpe) > 0.1:
            cv = std_sharpe / abs(mean_sharpe)
            # Allow some variation due to estimation error
            assert cv < 0.5, f"Sharpe ratio too inconsistent across time: mean={mean_sharpe:.2f}, std={std_sharpe:.2f}, CV={cv:.2f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "metamorphic"])
