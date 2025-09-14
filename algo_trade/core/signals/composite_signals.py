import pandas as pd
import numpy as np
from typing import Dict, Tuple
from algo_trade.core.signals.base_signals import build_signals
from algo_trade.core.optimization.black_litterman import black_litterman
from algo_trade.core.risk.covariance import _ewma_cov
from sklearn.linear_model import LinearRegression
from sklearn.decomposition import PCA
from scipy.stats import zscore

def orthogonalize_signals(signals: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Performs cross-sectional orthogonalization of signals using OLS.
    This ensures that each signal captures unique information.
    
    Parameters:
    signals (Dict[str, pd.DataFrame]): Dictionary of alpha signals.
    
    Returns:
    Dict[str, pd.DataFrame]: Dictionary of orthogonalized signals.
    """
    names = list(signals.keys())
    dates = next(iter(signals.values())).index
    assets = next(iter(signals.values())).columns
    K = len(names)
    out = {k: pd.DataFrame(index=dates, columns=assets, dtype=float) for k in names}
    
    # Vectorized orthogonalization
    X_full = np.stack([s.values for s in signals.values()], axis=-1)
    
    for t in range(len(dates)):
        X_t = X_full[t, :, :]
        mask = ~np.any(np.isnan(X_t), axis=1)
        
        if mask.sum() > K:
            X = X_t[mask, :]
            R = np.zeros_like(X)
            for j in range(K):
                y = X[:, j]
                Z = np.delete(X, j, axis=1)
                Z = np.column_stack([np.ones(Z.shape[0]), Z])
                
                try:
                    beta, *_ = np.linalg.lstsq(Z, y, rcond=None)
                    resid = y - Z @ beta
                    R[:, j] = resid
                except np.linalg.LinAlgError:
                    R[:, j] = y
            
            R_full = np.full_like(X_t, np.nan)
            R_full[mask, :] = R
            
            for j, k in enumerate(names):
                out[k].iloc[t] = R_full[:, j]
        else:
            for j, k in enumerate(names):
                out[k].iloc[t] = signals[k].iloc[t].values
    
    # Re-normalize the orthogonalized signals
    for k in names:
        out[k] = out[k].apply(lambda s: zscore(s.fillna(0)), axis=1)
        out[k] = out[k].fillna(0)
    
    return out

def combine_signals(
    signals: Dict[str, pd.DataFrame],
    weights: Dict[str, float]
) -> pd.DataFrame:
    """
    Combines a dictionary of signals into a single, weighted DataFrame.
    
    Parameters:
    signals (Dict[str, pd.DataFrame]): Dictionary of signals.
    weights (Dict[str, float]): Dictionary of weights for each signal.
    
    Returns:
    pd.DataFrame: A single DataFrame representing the combined signal.
    """
    merged = pd.DataFrame(0.0, index=next(iter(signals.values())).index, columns=next(iter(signals.values())).columns)
    for k in signals:
        merged = merged + weights[k] * signals[k]
    return merged

def mis_per_signal_pipeline(
    sigs: Dict[str, pd.DataFrame],
    returns: pd.DataFrame,
    horizon: int = 5
) -> Dict[str, pd.DataFrame]:
    """
    Calculates the MIS (Marginal Importance Score) for each signal.
    
    Parameters:
    sigs (Dict[str, pd.DataFrame]): Dictionary of alpha signals.
    returns (pd.DataFrame): DataFrame of asset returns.
    horizon (int): The horizon for future returns.
    
    Returns:
    Dict[str, pd.DataFrame]: Dictionary with the MIS for each signal.
    """
    fwd_returns = returns.shift(-horizon).rolling(horizon).sum()
    mis = {}
    for name, S in sigs.items():
        IC = S.corrwith(fwd_returns, axis=1).fillna(0)
        mis[name] = IC
    return mis

def merge_signals_by_mis(
    sigs: Dict[str, pd.DataFrame], mis: Dict[str, pd.DataFrame]
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    """
    Merges orthogonalized signals into a single alpha signal based on MIS.
    
    Parameters:
    sigs (Dict[str, pd.DataFrame]): Dictionary of orthogonalized signals.
    mis (Dict[str, pd.DataFrame]): Dictionary of MIS scores for each signal.
    
    Returns:
    Tuple[pd.DataFrame, Dict[str, float]]: Merged signal and the weights used.
    """
    weights = {k: float(mis[k].mean()) for k in sigs}
    wsum = sum(np.abs(list(weights.values()))) + 1e-12
    weights = {k: v / wsum for k, v in weights.items()}
    
    merged = combine_signals(sigs, weights)
    
    return merged, weights

def create_composite_signals(
    returns: pd.DataFrame,
    prices: pd.DataFrame,
    params: Dict
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Creates composite signals by building base signals, orthogonalizing them,
    and merging them based on their importance. It also calculates benchmark signals.
    
    Parameters:
    returns (pd.DataFrame): DataFrame of asset returns.
    prices (pd.DataFrame): DataFrame of asset prices.
    params (Dict): Dictionary of parameters from the configuration file.
    
    Returns:
    Tuple[pd.DataFrame, pd.DataFrame, Dict]: Merged alpha signal, HRP benchmark, and BL benchmark.
    """
    base_sigs = build_signals(returns, prices, params)
    
    # Stack signals for PCA
    stacked_sigs = pd.concat(base_sigs.values(), axis=1).dropna()
    
    # Perform PCA and calculate explained variance
    pca = PCA(n_components=stacked_sigs.shape[1])
    pca.fit(stacked_sigs)
    
    # Find number of components to explain 95% of variance
    explained_variance_ratio = np.cumsum(pca.explained_variance_ratio_)
    num_components = np.where(explained_variance_ratio >= 0.95)[0][0] + 1
    
    # Transform signals to principal components
    pca_sigs = pd.DataFrame(pca.transform(stacked_sigs)[:, :num_components],
                            index=stacked_sigs.index,
                            columns=[f"PC_{i}" for i in range(num_components)])
    
    # Use PCA components as the new signals
    ortho_sigs = {f"PC_{i}": pca_sigs[[f"PC_{i}"]] for i in range(num_components)}
    
    mis_scores = mis_per_signal_pipeline(ortho_sigs, returns, horizon=5)
    merged_alpha, _ = merge_signals_by_mis(ortho_sigs, mis_scores)
    
    # Calculate benchmarks
    hrp_benchmark = black_litterman(
        market_w=_ewma_cov(returns, 30).values, # Placeholder for real market weights
        cov_mat=_ewma_cov(returns, 30)
    )
    bl_benchmark = black_litterman(
        market_w=_ewma_cov(returns, 30).values, # Placeholder for real market weights
        cov_mat=_ewma_cov(returns, 30)
    )

    return merged_alpha, hrp_benchmark, bl_benchmark
