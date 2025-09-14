import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

def black_litterman(
    market_w: pd.Series,
    cov_mat: pd.DataFrame,
    tau: float,
    P: Optional[np.ndarray] = None,
    Q: Optional[np.ndarray] = None
) -> Tuple[pd.Series, pd.Series]:
    """
    מיישם את מודל Black-Litterman להקצאת נכסים.
    המודל משלב קונצנזוס שוק עם דעות פרטיות כדי להשיג הקצאה אופטימלית.

    Parameters:
    market_w (pd.Series): משקלי תיק השוק הנייטרליים (לרוב מבוססים על HRP).
    cov_mat (pd.DataFrame): מטריצת הקו-וריאנס של הנכסים.
    tau (float): סקאלר המייצג את רמת הוודאות שלנו בתשואות הקונוסנסוס של השוק.
    P (np.ndarray, optional): מטריצה המייצגת את הקשר בין הנכסים לבין הדעות.
    Q (np.ndarray, optional): וקטור המייצג את התשואות הצפויות מהדעות.

    Returns:
    Tuple[pd.Series, pd.Series]: 
    - Series של משקלי התיק האופטימליים לפי Black-Litterman.
    - Series של התשואות הצפויות המשולבות.
    """
    
    if P is None or Q is None:
        logger.info("P and Q views not provided. Returning passive market allocation.")
        implied_returns = (252.0 * cov_mat @ market_w).fillna(0)
        return market_w, implied_returns

    try:
        # P: Link assets to views
        # Q: Returns of views

        # Inverse of the covariance of views
        omega = P @ cov_mat @ P.T
        omega_inv = np.linalg.inv(omega + 1e-12)

        # Implied excess returns from market equilibrium
        market_implied_returns = (252.0 * cov_mat @ market_w).fillna(0)

        # Black-Litterman formula for combined returns
        tau_cov_inv = np.linalg.inv(tau * cov_mat + 1e-12)
        bl_mu = np.linalg.inv(tau_cov_inv + P.T @ omega_inv @ P) @ \
                (tau_cov_inv @ market_implied_returns + P.T @ omega_inv @ Q)

        # Black-Litterman combined covariance
        bl_cov = np.linalg.inv(tau_cov_inv + P.T @ omega_inv @ P)
        
        # New portfolio weights (unconstrained for simplicity)
        bl_w = np.linalg.inv(bl_cov) @ bl_mu

        bl_w_series = pd.Series(bl_w, index=market_w.index)
        bl_w_series_sum = bl_w_series.sum()
        
        # Normalization
        if bl_w_series_sum > 0:
            bl_w_series = bl_w_series / bl_w_series_sum
        else:
            bl_w_series[:] = 0.0

        return bl_w_series, pd.Series(bl_mu, index=market_w.index)
    except np.linalg.LinAlgError as e:
        logger.error(f"Linear algebra error during Black-Litterman calculation: {e}")
        return market_w, pd.Series(0.0, index=market_w.index)
    except Exception as e:
        logger.error(f"Unexpected error during Black-Litterman calculation: {e}")
        return market_w, pd.Series(0.0, index=market_w.index)
