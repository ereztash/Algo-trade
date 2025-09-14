import pandas as pd
import numpy as np
from typing import Dict

def zscore_dynamic(df: pd.DataFrame, win_vol: int, win_mean: int) -> pd.DataFrame:
    """
    Calculates the rolling Z-score with dynamic windowing based on volatility.
    
    Parameters:
    df (pd.DataFrame): Input DataFrame.
    win_vol (int): The window size for rolling standard deviation.
    win_mean (int): The window size for rolling mean.
    
    Returns:
    pd.DataFrame: DataFrame with Z-scores.
    """
    m = df.rolling(win_mean).mean()
    s = df.rolling(win_vol).std(ddof=0)
    return ((df - m) / (s.replace(0, np.nan))).fillna(0)

def ofi_signal(prices: pd.DataFrame, horizons: Dict[str, int]) -> pd.DataFrame:
    """
    Calculates a multi-horizon Order Flow Imbalance (OFI) signal based on price action.
    This version combines momentum with a price change-to-volume-change ratio.
    
    Parameters:
    prices (pd.DataFrame): DataFrame of asset prices.
    horizons (Dict): Dictionary with short and long horizons.
    
    Returns:
    pd.DataFrame: The OFI signal.
    """
    # Calculate price and volume changes
    d_prices = prices.diff().fillna(0)
    d_volumes = prices['volume'].diff().fillna(0) # Assuming a volume column
    
    # Calculate an approximate order flow imbalance
    flow_imbalance = d_prices / (d_volumes.replace(0, 1e-9))
    
    # Combine with a short-term momentum
    mom_short = prices.pct_change().rolling(horizons["short_h"]).mean()
    
    # Blend the two components
    ofi = flow_imbalance + mom_short
    return zscore_dynamic(ofi, horizons["medium_h"], horizons["long_h"]).fillna(0)

def ern_signal(returns: pd.DataFrame, horizons: Dict[str, int]) -> pd.DataFrame:
    """
    Calculates a multi-horizon Earnings Momentum (ERN) signal.
    This version is based on the concept of 'Information Asymmetry'.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of asset returns.
    horizons (Dict): Dictionary with short and long horizons.
    
    Returns:
    pd.DataFrame: The ERN signal.
    """
    short_ma = returns.rolling(horizons["short_h"]).mean()
    long_ma = returns.rolling(horizons["long_h"]).mean()
    
    # Information Asymmetry is proxied by the deviation of short-term momentum from long-term
    asymmetry = short_ma - long_ma
    return zscore_dynamic(asymmetry, horizons["long_h"], horizons["long_h"]).fillna(0)

def vrp_signal(returns: pd.DataFrame, horizons: Dict[str, int]) -> pd.DataFrame:
    """
    Calculates the Volatility Risk Premium (VRP) signal across horizons.
    This version adds a component for a volatility "smile" effect.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of asset returns.
    horizons (Dict): Dictionary with short and long horizons.
    
    Returns:
    pd.DataFrame: The VRP signal.
    """
    rv_short = returns.pow(2).rolling(horizons["short_h"]).mean()
    rv_long = returns.pow(2).rolling(horizons["long_h"]).mean()
    
    # VRP is the difference between long and short term realized volatility
    vrp = np.sqrt(rv_long.clip(lower=0)) - np.sqrt(rv_short.clip(lower=0))
    return zscore_dynamic(vrp, horizons["long_h"], horizons["long_h"]).fillna(0)

def pos_signal(returns: pd.DataFrame, horizons: Dict[str, int]) -> pd.DataFrame:
    """
    Calculates a multi-horizon Position Sizing (POS) signal.
    Based on a dynamic mean-reversion factor.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of asset returns.
    horizons (Dict): Dictionary with short and long horizons.
    
    Returns:
    pd.DataFrame: The POS signal.
    """
    long_ma = returns.rolling(horizons["long_h"]).mean()
    # Mean-reversion is the deviation from the long-term trend
    pos = long_ma - returns
    return zscore_dynamic(pos, horizons["long_h"], horizons["long_h"]).fillna(0)

def tsx_signal(returns: pd.DataFrame, horizons: Dict[str, int]) -> pd.DataFrame:
    """
    Calculates a multi-horizon Trend-Following (TSX) signal.
    Captures trends based on a blend of short and long-term momentum.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of asset returns.
    horizons (Dict): Dictionary with short and long horizons.
    
    Returns:
    pd.DataFrame: The TSX signal.
    """
    short_ma = returns.rolling(horizons["short_h"]).mean()
    long_ma = returns.rolling(horizons["long_h"]).mean()
    
    # Trend is the difference between short and long moving averages
    slope = short_ma - long_ma
    return zscore_dynamic(slope, horizons["long_h"], horizons["long_h"]).fillna(0)

def sif_signal(returns: pd.DataFrame, horizons: Dict[str, int]) -> pd.DataFrame:
    """
    Calculates a multi-horizon Signal Flow (SIF) signal.
    A mean-reversion factor based on the difference between fast and slow moving averages.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of asset returns.
    horizons (Dict): Dictionary with fast and slow horizons.
    
    Returns:
    pd.DataFrame: The SIF signal.
    """
    fast = returns.rolling(horizons["fast_h"]).mean()
    slow = returns.rolling(horizons["slow_h"]).mean()
    flow = fast - slow
    return zscore_dynamic(flow, horizons["slow_h"], horizons["slow_h"]).fillna(0)

def build_signals(returns: pd.DataFrame, prices: pd.DataFrame, params: Dict) -> Dict[str, pd.DataFrame]:
    """
    Builds a dictionary of all alpha signals, including a multi-horizon approach.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of asset returns.
    prices (pd.DataFrame): DataFrame of asset prices.
    params (Dict): Dictionary of parameters from the configuration file.
    
    Returns:
    Dict[str, pd.DataFrame]: A dictionary with each signal as a DataFrame.
    """
    # Create horizon dictionaries based on config parameters
    ofi_h = {"short_h": params["OFI_H_SHORT"], "medium_h": params["OFI_H_MEDIUM"], "long_h": params["OFI_H_LONG"]}
    ern_h = {"short_h": params["ERN_H_SHORT"], "long_h": params["ERN_H_LONG"]}
    vrp_h = {"short_h": params["VRP_H_SHORT"], "long_h": params["VRP_H_LONG"]}
    pos_h = {"short_h": params["POS_H_SHORT"], "long_h": params["POS_H_LONG"]}
    tsx_h = {"short_h": params["TSX_H_SHORT"], "long_h": params["TSX_H_LONG"]}
    sif_h = {"fast_h": params["SIF_H_FAST"], "slow_h": params["SIF_H_SLOW"]}

    sigs = {
        "OFI": ofi_signal(prices, ofi_h),
        "ERN": ern_signal(returns, ern_h),
        "VRP": vrp_signal(returns, vrp_h),
        "POS": pos_signal(returns, pos_h),
        "TSX": tsx_signal(returns, tsx_h),
        "SIF": sif_signal(returns, sif_h),
    }
    return sigs
