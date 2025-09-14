import numpy as np
import pandas as pd
import cvxpy as cp
from typing import Dict, Tuple, List, Optional
import logging

logger = logging.getLogger(__name__)

def solve_qp(
    mu_hat: pd.Series,
    C: pd.DataFrame,
    w_prev: pd.Series,
    gross_lim: float,
    net_lim: float,
    params: Dict
) -> pd.Series:
    """
    פותר את בעיית האופטימיזציה של התיק באמצעות תכנות ריבועי (QP).
    מטרה: מזעור סיכון תוך מקסום תשואה, עם אילוצים על חשיפה ותחלופה.

    Parameters:
    mu_hat (pd.Series): וקטור התשואות הצפויות (מנורמל).
    C (pd.DataFrame): מטריצת הקו-וריאנס הצפויה.
    w_prev (pd.Series): משקלי התיק הנוכחיים.
    gross_lim (float): חשיפת ברוטו מקסימלית (סכום הערכים המוחלטים).
    net_lim (float): חשיפת נטו מקסימלית (סכום המשקלים).
    params (Dict): מילון פרמטרים נוספים (עונשים וכו').

    Returns:
    pd.Series: משקלי התיק האופטימליים.
    """
    
    idx = mu_hat.index
    n = len(idx)
    w = cp.Variable(n)
    
    # ודא שמטריצת הקו-וריאנס חיובית לחלוטין (Positive Semi-Definite - PSD)
    try:
        # Check if the matrix is already PSD. If not, add small noise.
        min_eig = np.linalg.eigvalsh(C.values).min()
        C_psd_raw = C.values if min_eig > 1e-8 else C.values + np.eye(n) * (1e-8 - min_eig)
        C_psd = cp.psd_wrap(C_psd_raw)
    except Exception as e:
        logger.error(f"Error handling C matrix as PSD: {e}. Using a fallback.")
        C_psd = cp.psd_wrap(C.values + np.eye(n) * 1e-8)

    gamma = params.get("TURNOVER_PEN", 0.002)
    eta = params.get("RIDGE_PEN", 1e-4)

    # פונקציית המטרה:
    # 1. סיכון: cp.quad_form(w, C_psd) - וריאציית התיק.
    # 2. תשואה: mu_hat.values @ w - התשואה הצפויה.
    # 3. עונש תחלופה: gamma * cp.norm1(w - w_prev.values) - מזער תחלופה.
    # 4. עונש L2: eta * cp.sum_squares(w) - מזער משקלים קיצוניים (Regularization).
    obj = 0.5 * cp.quad_form(w, C_psd) - mu_hat.values @ w + \
          gamma * cp.norm1(w - w_prev.values) + eta * cp.sum_squares(w)

    # אילוצים
    cons = [
        cp.sum(cp.abs(w)) <= gross_lim,  # אילוץ על חשיפת ברוטו
        cp.sum(w) >= -net_lim,            # חשיפה נטו יכולה להיות שלילית
        cp.sum(w) <= net_lim,             # חשיפה נטו יכולה להיות חיובית
        w >= -params.get("BOX_LIM", 0.25), # גבול תחתון
        w <= params.get("BOX_LIM", 0.25),  # גבול עליון
    ]
    
    prob = cp.Problem(cp.Minimize(obj), cons)
    
    try:
        # פתרון הבעיה באמצעות OSQP (פתרון מהיר ויעיל)
        prob.solve(solver=cp.OSQP, warm_start=True, verbose=False)

        # בדיקת סטטוס הפתרון והחזרת משקלים
        if prob.status in ["optimal", "optimal_inaccurate"]:
            w_opt = pd.Series(np.clip(w.value, -1.0, 1.0), index=idx)
            # Volatility Targeting (קביעת גודל התיק לפי יעד תנודתיות)
            port_vol = float(np.sqrt(w_opt.values @ C.values @ w_opt.values))
            if port_vol > 1e-9:
                scale = params.get("VOL_TARGET", 0.10) / port_vol
                w_opt = np.clip(w_opt * scale, -1.0, 1.0)
            
            return w_opt
        else:
            logger.warning(f"QP solution failed with status: {prob.status}. Returning previous weights.")
            return w_prev

    except Exception as e:
        logger.error(f"An unexpected error occurred during QP solving: {e}. Returning previous weights.")
        return w_prev
