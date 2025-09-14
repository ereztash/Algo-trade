import numpy as np
import pandas as pd
from typing import Dict, Tuple
from scipy.stats import norm
import logging
from hmmlearn import hmm
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

def avg_corr(df: pd.DataFrame) -> float:
    """
    Calculates the average correlation within a cross-section of data.
    
    Parameters:
    df (pd.DataFrame): DataFrame of assets, where columns are assets and rows are dates.
    
    Returns:
    float: The average correlation.
    """
    if df.shape[1] < 2:
        return 0.0
    
    c = df.corr()
    c_no_diag = c.values[~np.eye(c.shape[0], dtype=bool)].reshape(c.shape[0], c.shape[1]-1)
    
    avg_rho = float(np.nanmean(c_no_diag))
    
    return avg_rho

def detect_regime(returns: pd.DataFrame, config: Dict) -> Tuple[str, Dict[str, float]]:
    """
    Detects the current market regime using a combination of statistical indicators
    and a Hidden Markov Model (HMM).
    
    Parameters:
    returns (pd.DataFrame): DataFrame of returns.
    config (Dict): Configuration dictionary.
    
    Returns:
    Tuple[str, Dict[str, float]]: Current market regime and a dictionary of metrics.
    """
    win_size = config.get("REGIME_WIN", 60)
    
    if len(returns) < win_size * 2:
        return "Normal", {"avg_vol": 0.0, "avg_rho": 0.0, "tail_corr": 0.0, "hmm_state": -1}
    
    win = returns.tail(win_size)
    
    # 1. Statistical Indicators (as sanity check and for hybrid models)
    avg_vol = float(win.std().mean() * np.sqrt(252))
    avg_rho = avg_corr(win)
    
    tail_returns = win[win.mean(axis=1) < win.mean(axis=1).quantile(0.10)]
    tail_corr = avg_corr(tail_returns)
    
    # 2. HMM-based Regime Detection
    # Create a feature set for the HMM
    features = pd.DataFrame({
        'vol': returns.rolling(20).std().mean(axis=1).dropna(),
        'corr': returns.rolling(20).apply(avg_corr, raw=False, axis=1).dropna(),
        'mean_ret': returns.mean(axis=1).rolling(20).mean().dropna()
    })
    
    if len(features) < 100:
        return "Normal", {"avg_vol": avg_vol, "avg_rho": avg_rho, "tail_corr": tail_corr, "hmm_state": -1}

    # Use a scaler to normalize the features
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)
    
    # Fit a Gaussian HMM model
    model = hmm.GaussianHMM(n_components=3, covariance_type="full", n_iter=100)
    model.fit(scaled_features)
    
    # Predict the hidden state of the current period
    current_state = model.predict([scaled_features[-1]])[0]
    
    # Map the hidden states to meaningful regimes
    # The mapping is determined by the characteristics of each state
    state_means = model.means_
    state_vols = np.array([np.mean(np.diag(cov)) for cov in model.covars_])
    
    # Simple mapping: sort states by volatility to assign 'Calm', 'Normal', 'Storm'
    vol_sorted_states = state_vols.argsort()
    state_map = {
        vol_sorted_states[0]: "Calm",
        vol_sorted_states[1]: "Normal",
        vol_sorted_states[2]: "Storm"
    }

    hmm_regime = state_map.get(current_state, "Normal")
    
    # Combine the statistical and HMM-based regimes for a robust decision
    # If HMM and stats point to a 'Storm' regime, this adds confidence
    regime = hmm_regime
    if (avg_vol > config.get("VOL_STORM_THRESHOLD", 0.35)) or \
       (avg_rho > config.get("RHO_STORM_THRESHOLD", 0.45)) or \
       (tail_corr > config.get("TAIL_STORM_THRESHOLD", 0.60)):
        regime = "Storm"
    
    metrics = {
        "avg_vol": avg_vol,
        "avg_rho": avg_rho,
        "tail_corr": tail_corr,
        "hmm_state": int(current_state),
        "hmm_regime": hmm_regime
    }
    
    return regime, metrics
