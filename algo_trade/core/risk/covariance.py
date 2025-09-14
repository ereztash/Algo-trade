import numpy as np
import pandas as pd
from typing import Dict, Tuple, List
from sklearn.covariance import LedoitWolf
import logging

logger = logging.getLogger(__name__)

def _ewma_cov(returns: pd.DataFrame, halflife: int) -> pd.DataFrame:
    """
    חישוב מטריצת קו-וריאנס EWMA (Exponentially Weighted Moving Average).
    שיטה זו נותנת משקל גבוה יותר לנתונים עדכניים.
    
    Parameters:
    returns (pd.DataFrame): DataFrame של תשואות.
    halflife (int): אורך החיים של חלון הדעיכה.

    Returns:
    pd.DataFrame: מטריצת הקו-וריאנס.
    """
    if returns.empty:
        return pd.DataFrame(index=returns.columns, columns=returns.columns)
        
    X = returns.values
    X = X - X.mean(axis=0, keepdims=True)
    lam = np.exp(-np.log(2) / max(halflife, 1))
    
    # חישוב אופטימלי של מטריצת הקו-וריאנס
    S = np.zeros((X.shape[1], X.shape[1]), dtype=float)
    alpha = 1 - lam
    for t in range(X.shape[0]):
        S = lam * S + alpha * np.outer(X[t], X[t])
    S = S / (1 - lam**X.shape[0])
    
    return pd.DataFrame(S, index=returns.columns, columns=returns.columns)


def _lw_cov(returns: pd.DataFrame) -> pd.DataFrame:
    """
    חישוב מטריצת קו-וריאנס בשיטת Ledoit-Wolf Shrinkage.
    שיטה זו מכווצת את מטריצת הקו-וריאנס לכיוון מטריצת יחידה,
    ובכך משפרת את יציבותה במקרים של רעש בנתונים.

    Parameters:
    returns (pd.DataFrame): DataFrame של תשואות.

    Returns:
    pd.DataFrame: מטריצת הקו-וריאנס.
    """
    if returns.empty:
        return pd.DataFrame(index=returns.columns, columns=returns.columns)
        
    try:
        C = LedoitWolf(assume_centered=True).fit(returns.values).covariance_
        return pd.DataFrame(C, index=returns.columns, columns=returns.columns)
    except Exception as e:
        logger.error(f"Error in Ledoit-Wolf covariance calculation: {e}. Returning fallback.")
        return returns.cov()


def _fix_psd(M: pd.DataFrame) -> pd.DataFrame:
    """
    תיקון מטריצה כדי לוודא שהיא חיובית לחלוטין (Positive Semi-Definite - PSD).
    תנאי הכרחי לפתרון בעיות אופטימיזציה כמו QP.
    
    Parameters:
    M (pd.DataFrame): המטריצה לתיקון.

    Returns:
    pd.DataFrame: המטריצה המתוקנת.
    """
    if M.empty:
        return M
        
    A = M.values
    try:
        w, v = np.linalg.eigh(A)
        w[w < 1e-8] = 1e-8
        return pd.DataFrame(v @ np.diag(w) @ v.T, index=M.index, columns=M.columns)
    except np.linalg.LinAlgError:
        logger.warning("LinAlgError in PSD fix. Adding noise.")
        return M + np.eye(M.shape[0]) * 1e-8


def adaptive_cov(returns: pd.DataFrame, regime: str, T_N_ratio: float, config: Dict) -> pd.DataFrame:
    """
    Blend דינמי בין EWMA לבין LW לפי משטר ו-T/N. מחזיר Σ שנתית.
    
    Parameters:
    returns (pd.DataFrame): DataFrame של תשואות יומיות.
    regime (str): משטר השוק הנוכחי ('Calm', 'Normal', 'Storm').
    T_N_ratio (float): היחס בין מספר ימי הדאטה למספר הנכסים.
    config (Dict): קובץ הקונפיגורציה.

    Returns:
    pd.DataFrame: מטריצת הקו-וריאנס השנתית.
    """
    if returns.empty or len(returns) < 30:
        return pd.DataFrame(np.eye(returns.shape[1]), index=returns.columns, columns=returns.columns) * (config['SIGMA_DAILY']**2 * 252)

    HL = config["COV_EWMA_HL"].get(regime, 30)
    S_ew = _ewma_cov(returns, halflife=HL)
    
    if T_N_ratio < 2.0 or regime == "Storm":
        S_lw = _lw_cov(returns)
        alpha = config["COV_BLEND_ALPHA"].get(regime, 0.35)
        S = alpha * S_lw + (1 - alpha) * S_ew
    else:
        S = S_ew

    S_annualized = 252.0 * S
    return _fix_psd(S_annualized).astype(float)
