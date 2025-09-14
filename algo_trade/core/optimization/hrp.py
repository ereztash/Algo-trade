import numpy as np
import pandas as pd
from typing import List, Tuple
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, leaves_list

def hrp_portfolio(returns: pd.DataFrame) -> pd.Series:
    """
    מיישם את אלגוריתם Hierarchical Risk Parity (HRP)
    כדי לבנות תיק השקעות יציב על בסיס נתונים היסטוריים.

    HRP הוא אלגוריתם שאינו מתבסס על מטריצה הפכית ולכן הוא יציב יותר
    ממודלי אופטימיזציה מסורתיים.

    Parameters:
    returns (pd.DataFrame): DataFrame של תשואות יומיות.

    Returns:
    pd.Series: סדרה של משקלי התיק עבור כל נכס.
    """
    if returns.empty or returns.shape[1] < 2:
        return pd.Series(1.0 / returns.shape[1], index=returns.columns)

    try:
        # שלב 1: יצירת מטריצת קורלציה ומרחק
        corr = returns.corr().clip(-0.9999, 0.9999).fillna(0)
        dist = np.sqrt(0.5 * (1.0 - corr))
        condensed = squareform(dist.values, checks=False)

        # שלב 2: יצירת אשכולות (אשכולות נכסים)
        Z = linkage(condensed, method='single')

        # שלב 3: סידור הנכסים לפי סדר האשכולות
        order = leaves_list(Z)
        cols = corr.columns[order]

        # שלב 4: חישוב הקצאת HRP
        cov = returns.cov().fillna(0)
        w = _hrp_recursive_allocation(cov, list(cols))

        # נורמליזציה וסידור מחדש של המשקלים
        w = w.reindex(returns.columns).fillna(0.0)
        w_sum = w.sum()
        w = w / w_sum if w_sum > 0 else pd.Series(1.0 / len(w), index=w.index)
        return w.sort_index()

    except Exception as e:
        print(f"❌ שגיאה בחישוב HRP: {e}")
        return pd.Series(1.0 / returns.shape[1], index=returns.columns)

def _get_inverse_variance_weights(cov: pd.DataFrame) -> pd.Series:
    """
    מחשב משקלים לפי וריאציה הפוכה בתוך אשכול נכסים.
    """
    if cov.empty:
        return pd.Series([], dtype=float)
    iv = 1.0 / np.diag(cov.values)
    iv[np.isinf(iv)] = 0.0
    w = iv / iv.sum() if iv.sum() > 0 else np.ones_like(iv) / len(iv)
    return pd.Series(w, index=cov.index)

def _hrp_recursive_allocation(cov: pd.DataFrame, items: List[str]) -> pd.Series:
    """
    פונקציית רקורסיה לחישוב משקלי HRP.
    """
    if len(items) == 1:
        return pd.Series(1.0, index=items)
    
    # פיצול האשכול לשניים
    split = len(items) // 2
    left, right = items[:split], items[split:]
    
    # חישוב וריאציה של כל תת-אשכול
    cov_left = cov.loc[left, left]
    cov_right = cov.loc[right, right]

    var_left = float(_get_inverse_variance_weights(cov_left).values @ cov_left.values @ _get_inverse_variance_weights(cov_left).values)
    var_right = float(_get_inverse_variance_weights(cov_right).values @ cov_right.values @ _get_inverse_variance_weights(cov_right).values)
    
    # הקצאת משקל פנימית לכל תת-אשכול
    alpha = 1.0 - var_left / (var_left + var_right + 1e-12)
    
    # חלוקה רקורסיבית
    w_left = _hrp_recursive_allocation(cov, left) * alpha
    w_right = _hrp_recursive_allocation(cov, right) * (1.0 - alpha)

    return pd.concat([w_left, w_right])
