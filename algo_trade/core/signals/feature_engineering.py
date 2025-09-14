import pandas as pd
import numpy as np
from typing import Dict

def robust_zscore(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a robust Z-score using median and MAD (Median Absolute Deviation).
    This is less sensitive to outliers than a standard Z-score.
    
    Parameters:
    df (pd.DataFrame): The DataFrame to normalize.
    
    Returns:
    pd.DataFrame: The normalized DataFrame.
    """
    median = df.median()
    mad = (df - median).abs().median()
    return (df - median) / (1.4826 * mad + 1e-12)

def volatility(returns: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Calculates the rolling volatility of asset returns.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of returns.
    window (int): The lookback window for the calculation.
    
    Returns:
    pd.DataFrame: A DataFrame of rolling volatility.
    """
    return returns.rolling(window).std() * np.sqrt(252)

def returns_over_volatility(returns: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Calculates the risk-adjusted returns (Sharpe-like ratio) over a rolling window.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of returns.
    window (int): The lookback window.
    
    Returns:
    pd.DataFrame: A DataFrame of risk-adjusted returns.
    """
    m = returns.rolling(window).mean()
    s = returns.rolling(window).std()
    return m / (s.replace(0, np.nan))

def moving_average_crossover(prices: pd.DataFrame, fast_window: int, slow_window: int) -> pd.DataFrame:
    """
    Calculates the difference between a fast and slow moving average.
    
    Parameters:
    prices (pd.DataFrame): DataFrame of prices.
    fast_window (int): The window for the fast moving average.
    slow_window (int): The window for the slow moving average.
    
    Returns:
    pd.DataFrame: A DataFrame with the difference.
    """
    fast_ma = prices.rolling(fast_window).mean()
    slow_ma = prices.rolling(slow_window).mean()
    return fast_ma - slow_ma

def exponential_moving_average_ratio(prices: pd.DataFrame, fast_window: int, slow_window: int) -> pd.DataFrame:
    """
    Calculates the ratio of two exponential moving averages.
    
    Parameters:
    prices (pd.DataFrame): DataFrame of prices.
    fast_window (int): The window for the fast EMA.
    slow_window (int): The window for the slow EMA.
    
    Returns:
    pd.DataFrame: A DataFrame with the ratio.
    """
    fast_ema = prices.ewm(span=fast_window, adjust=False).mean()
    slow_ema = prices.ewm(span=slow_window, adjust=False).mean()
    return fast_ema / (slow_ema.replace(0, np.nan))

def relative_strength(returns: pd.DataFrame, benchmark: pd.Series, window: int) -> pd.DataFrame:
    """
    Calculates the rolling relative strength of assets against a benchmark.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of asset returns.
    benchmark (pd.Series): The benchmark series (e.g., S&P 500 returns).
    window (int): The lookback window.
    
    Returns:
    pd.DataFrame: DataFrame of relative strength signals.
    """
    rel_ret = returns.subtract(benchmark, axis=0)
    return rel_ret.rolling(window).sum()

def gap_signal(prices: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the overnight gap between today's open and yesterday's close.
    This is a proxy for market sentiment and overnight news.
    
    Parameters:
    prices (pd.DataFrame): DataFrame of prices with 'open' and 'close' columns.
    
    Returns:
    pd.DataFrame: DataFrame of gap signals.
    """
    return (prices.iloc[:, 0] / prices.iloc[:, 1].shift(1)) - 1

def nonlinear_interaction_term(df1: pd.DataFrame, df2: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates a non-linear interaction term between two features.
    
    Parameters:
    df1 (pd.DataFrame): The first feature.
    df2 (pd.DataFrame): The second feature.
    
    Returns:
    pd.DataFrame: A DataFrame with the interaction term.
    """
    return np.log(df1.abs() + 1e-12) * df2

def create_feature_set(
    prices: pd.DataFrame, returns: pd.DataFrame, params: Dict
) -> Dict[str, pd.DataFrame]:
    """
    Creates a full set of engineered features for the alpha models.
    
    Parameters:
    prices (pd.DataFrame): DataFrame of prices.
    returns (pd.DataFrame): DataFrame of returns.
    params (Dict): Dictionary of parameters.
    
    Returns:
    Dict[str, pd.DataFrame]: A dictionary of engineered features.
    """
    features = {
        "volatility_20d": volatility(returns, 20),
        "returns_vol_5d": returns_over_volatility(returns, 5),
        "ma_crossover_10_30": moving_average_crossover(prices, 10, 30),
        "ema_ratio_5_20": exponential_moving_average_ratio(prices, 5, 20),
        "relative_strength_60d": relative_strength(returns, returns.mean(axis=1), 60),
        "gap_signal": gap_signal(prices[['open', 'close']]),
    }
    
    # Add nonlinear features
    features["vol_interact_ma"] = nonlinear_interaction_term(features["volatility_20d"], features["ma_crossover_10_30"])
    features["returns_vol_sq"] = features["returns_vol_5d"].pow(2)
    
    return features
