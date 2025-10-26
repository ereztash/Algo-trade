"""
Utility functions for algorithmic trading system.
äÕàçæÙÕê âÖè ÜŞâèÛê ÔØèÙÙÓÙàÒ ÔĞÜÒÕèÙêŞÙ.
"""

import numpy as np
import pandas as pd
from typing import Union, Optional


def z_score(x: Union[np.ndarray, pd.Series],
            window: Optional[int] = None,
            min_periods: int = 2) -> Union[np.ndarray, pd.Series]:
    """
    Calculate z-score (standardized values).
    ×ÙéÕÑ z-score (âèÛÙİ ŞêÕçààÙİ).

    Args:
        x: Input array or series
        window: Rolling window size (None for full sample)
        min_periods: Minimum periods for calculation

    Returns:
        Z-scored values
    """
    if window is None:
        mean = np.mean(x)
        std = np.std(x)
        return (x - mean) / (std + 1e-8)

    if isinstance(x, pd.Series):
        mean = x.rolling(window, min_periods=min_periods).mean()
        std = x.rolling(window, min_periods=min_periods).std()
        return (x - mean) / (std + 1e-8)
    else:
        # NumPy array - convert to pandas for rolling
        s = pd.Series(x)
        result = z_score(s, window, min_periods)
        return result.values


def robust_z_score(x: Union[np.ndarray, pd.Series],
                   window: Optional[int] = None) -> Union[np.ndarray, pd.Series]:
    """
    Calculate robust z-score using median and MAD.
    ×ÙéÕÑ z-score ×Öç ÑĞŞæâÕê median Õ-MAD.

    Args:
        x: Input array or series
        window: Rolling window size (None for full sample)

    Returns:
        Robust z-scored values
    """
    if window is None:
        median = np.median(x)
        mad = np.median(np.abs(x - median))
        return (x - median) / (mad * 1.4826 + 1e-8)

    if isinstance(x, pd.Series):
        median = x.rolling(window).median()
        mad = (x - median).abs().rolling(window).median()
        return (x - median) / (mad * 1.4826 + 1e-8)
    else:
        s = pd.Series(x)
        result = robust_z_score(s, window)
        return result.values


def ema(x: Union[np.ndarray, pd.Series],
        span: int,
        min_periods: int = 1) -> Union[np.ndarray, pd.Series]:
    """
    Calculate exponential moving average.
    ×ÙéÕÑ ŞŞÕæâ àâ ĞçáäÕààæÙĞÜÙ.

    Args:
        x: Input array or series
        span: EMA span (half-life)
        min_periods: Minimum periods

    Returns:
        EMA values
    """
    if isinstance(x, pd.Series):
        return x.ewm(span=span, min_periods=min_periods).mean()
    else:
        s = pd.Series(x)
        result = s.ewm(span=span, min_periods=min_periods).mean()
        return result.values


def log_returns(prices: Union[np.ndarray, pd.Series]) -> Union[np.ndarray, pd.Series]:
    """
    Calculate log returns from prices.
    ×ÙéÕÑ êéÕĞÕê ÜÕÒèÙêŞÙÕê ŞŞ×ÙèÙİ.

    Args:
        prices: Price series

    Returns:
        Log returns
    """
    if isinstance(prices, pd.Series):
        return np.log(prices / prices.shift(1))
    else:
        return np.log(prices[1:] / prices[:-1])


def simple_returns(prices: Union[np.ndarray, pd.Series]) -> Union[np.ndarray, pd.Series]:
    """
    Calculate simple returns from prices.
    ×ÙéÕÑ êéÕĞÕê äéÕØÕê ŞŞ×ÙèÙİ.

    Args:
        prices: Price series

    Returns:
        Simple returns
    """
    if isinstance(prices, pd.Series):
        return prices.pct_change()
    else:
        return np.diff(prices) / prices[:-1]


def normalize_weights(weights: np.ndarray,
                      target_gross: float = 1.0) -> np.ndarray:
    """
    Normalize weights to target gross exposure.
    àèŞÕÜ ŞéçÜÙİ Ü×éÙäÔ ÑèÕØÕ ŞØèÔ.

    Args:
        weights: Portfolio weights
        target_gross: Target gross exposure (sum of absolute weights)

    Returns:
        Normalized weights
    """
    gross = np.sum(np.abs(weights))
    if gross < 1e-8:
        return weights
    return weights * (target_gross / gross)


def clip_weights(weights: np.ndarray,
                 min_weight: float = -0.1,
                 max_weight: float = 0.1) -> np.ndarray:
    """
    Clip individual weights to specified range.
    ×ÙêÕÚ ŞéçÜÙİ ÑÕÓÓÙİ ÜØÕÕ× ŞÕÒÓè.

    Args:
        weights: Portfolio weights
        min_weight: Minimum weight per asset
        max_weight: Maximum weight per asset

    Returns:
        Clipped weights
    """
    return np.clip(weights, min_weight, max_weight)


def rolling_std(x: Union[np.ndarray, pd.Series],
                window: int,
                annualize: bool = False,
                periods_per_year: int = 252) -> Union[np.ndarray, pd.Series]:
    """
    Calculate rolling standard deviation.
    ×ÙéÕÑ áØÙÙê êçß ŞêÒÜÒÜê.

    Args:
        x: Input array or series
        window: Rolling window size
        annualize: Whether to annualize volatility
        periods_per_year: Trading periods per year

    Returns:
        Rolling standard deviation
    """
    if isinstance(x, pd.Series):
        result = x.rolling(window).std()
    else:
        s = pd.Series(x)
        result = s.rolling(window).std()

    if annualize:
        result = result * np.sqrt(periods_per_year)

    return result if isinstance(x, pd.Series) else result.values


def sharpe_ratio(returns: Union[np.ndarray, pd.Series],
                 risk_free: float = 0.0,
                 periods_per_year: int = 252) -> float:
    """
    Calculate annualized Sharpe ratio.
    ×ÙéÕÑ Ù×á éĞèä éàêÙ.

    Args:
        returns: Return series
        risk_free: Risk-free rate (annualized)
        periods_per_year: Trading periods per year

    Returns:
        Sharpe ratio
    """
    mean_ret = np.mean(returns) * periods_per_year
    std_ret = np.std(returns) * np.sqrt(periods_per_year)

    if std_ret < 1e-8:
        return 0.0

    return (mean_ret - risk_free) / std_ret


def max_drawdown(equity_curve: Union[np.ndarray, pd.Series]) -> float:
    """
    Calculate maximum drawdown.
    ×ÙéÕÑ ÙèÙÓÔ ŞçáÙŞÜÙê.

    Args:
        equity_curve: Equity curve (cumulative)

    Returns:
        Maximum drawdown (negative value)
    """
    if isinstance(equity_curve, pd.Series):
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max
    else:
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max

    return np.min(drawdown)


def winsorize(x: Union[np.ndarray, pd.Series],
              lower: float = 0.01,
              upper: float = 0.99) -> Union[np.ndarray, pd.Series]:
    """
    Winsorize data by clipping extreme values to percentiles.
    ×ÙêÕÚ âèÛÙİ çÙæÕàÙÙİ ÜäèæàØÙÜÙİ.

    Args:
        x: Input array or series
        lower: Lower percentile (0-1)
        upper: Upper percentile (0-1)

    Returns:
        Winsorized values
    """
    lower_bound = np.percentile(x, lower * 100)
    upper_bound = np.percentile(x, upper * 100)
    return np.clip(x, lower_bound, upper_bound)


def correlation_matrix(returns: pd.DataFrame,
                       method: str = 'pearson',
                       min_periods: int = 30) -> pd.DataFrame:
    """
    Calculate correlation matrix from returns.
    ×ÙéÕÑ ŞØèÙæê ŞêĞŞÙİ ŞêéÕĞÕê.

    Args:
        returns: DataFrame of returns (assets in columns)
        method: Correlation method ('pearson', 'spearman', 'kendall')
        min_periods: Minimum periods for calculation

    Returns:
        Correlation matrix
    """
    return returns.corr(method=method, min_periods=min_periods)


def cross_sectional_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate cross-sectional z-score (normalize across assets at each time).
    ×ÙéÕÑ z-score ×êÛÙ (àèŞÕÜ âÜ äàÙ àÛáÙİ ÑÛÜ ÖŞß).

    Args:
        df: DataFrame with assets in columns, time in rows

    Returns:
        Cross-sectionally normalized DataFrame
    """
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1) + 1e-8, axis=0)


def ensure_psd(matrix: np.ndarray, min_eigenvalue: float = 1e-8) -> np.ndarray:
    """
    Ensure matrix is positive semi-definite by clipping eigenvalues.
    ÔÑØ×ê ŞØèÙæÔ ×ÙÕÑÙê ÜŞ×æÔ âÜ ÙÓÙ ×ÙêÕÚ âèÛÙİ âæŞÙÙİ.

    Args:
        matrix: Input matrix (should be symmetric)
        min_eigenvalue: Minimum eigenvalue threshold

    Returns:
        PSD matrix
    """
    # Symmetrize
    matrix = (matrix + matrix.T) / 2

    # Eigendecomposition
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)

    # Clip negative eigenvalues
    eigenvalues = np.maximum(eigenvalues, min_eigenvalue)

    # Reconstruct
    return eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T


def rank_signals(signals: pd.DataFrame) -> pd.DataFrame:
    """
    Rank signals cross-sectionally (percentile rank).
    ÓÙèÕÒ ĞÕêÕê ×êÛÙê (ÓÙèÕÒ äèæàØÙÜÙ).

    Args:
        signals: DataFrame with signals (assets in columns, time in rows)

    Returns:
        Ranked signals (0-1)
    """
    return signals.rank(axis=1, pct=True)


def demean(x: Union[np.ndarray, pd.Series, pd.DataFrame],
           axis: Optional[int] = None) -> Union[np.ndarray, pd.Series, pd.DataFrame]:
    """
    Remove mean from data.
    Ôáèê ŞŞÕæâ ŞÔàêÕàÙİ.

    Args:
        x: Input data
        axis: Axis for demeaning (None for scalar mean)

    Returns:
        Demeaned data
    """
    if isinstance(x, pd.DataFrame):
        return x - x.mean(axis=axis)
    elif isinstance(x, pd.Series):
        return x - x.mean()
    else:
        return x - np.mean(x, axis=axis, keepdims=True if axis is not None else False)


def exponential_decay_weights(length: int, half_life: int) -> np.ndarray:
    """
    Generate exponential decay weights for weighted averaging.
    ÙæÙèê ŞéçÜÙ ÓâÙÛÔ ĞçáäÕààæÙĞÜÙê ÜŞŞÕæâ ŞéÕçÜÜ.

    Args:
        length: Number of weights
        half_life: Half-life for decay

    Returns:
        Normalized weights (sum to 1)
    """
    decay = np.exp(-np.log(2) / half_life)
    weights = decay ** np.arange(length)[::-1]
    return weights / weights.sum()
