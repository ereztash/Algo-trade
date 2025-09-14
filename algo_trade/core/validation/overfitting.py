# -*- coding: utf-8 -*-
"""
overfitting.py - מודול ולידציה ואנטי-אוברפיטינג

מודול זה מרכז את כל הכלים והפונקציות הנדרשים לביצוע ולידציה קפדנית
של אסטרטגיות מסחר, במטרה למנוע התאמת יתר (Overfitting) לנתוני העבר.
הוא מכיל יישומים של טכניקות מתקדמות מתוך הספרות הפיננסית הכמותית,
כולל ולידציה צולבת, מבחנים סטטיסטיים, ומדדי ביצוע מותאמים לסיכון.

הכלים במודול זה נועדו לענות על שאלות קריטיות כגון:
- האם ביצועי האסטרטגיה ב-Backtest הם תוצאה של מיומנות או מזל?
- מהי ההסתברות שהאסטרטגיה תיכשל בנתוני אמת?
- כמה היסטוריית מסחר נדרשת כדי לסמוך על התוצאות?
- כיצד לבחור פרמטרים רובסטיים שאינם מותאמים יתר על המידה?

המודול מתוכנן להיות עצמאי וניתן לשילוב בכל מערכת מסחר.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Tuple, Dict
from itertools import combinations
from math import erf, sqrt, log
from scipy.stats import norm

# =============================================================================
# 1) ולידציה צולבת (Cross-Validation) לסדרות-זמן
# =============================================================================

def purged_k_fold(
    df: pd.DataFrame,
    n_splits: int = 5,
    embargo_len: int = 10
) -> List[Tuple[pd.Index, pd.Index]]:
    """
    מבצע ולידציה צולבת מסוג Purged K-Fold, המתאימה לסדרות זמן פיננסיות.
    השיטה מונעת דליפת מידע בין קבוצות האימון והבדיקה על ידי יצירת "אמברגו"
    (מרווח ביטחון) סביב דגימות המבחן.

    Args:
        df (pd.DataFrame): DataFrame המכיל את הנתונים (האינדקס הוא החשוב).
        n_splits (int): מספר ה-folds לחלוקה.
        embargo_len (int): גודל האמברגו (מספר דגימות) להסרה מסביב לנתוני המבחן.

    Returns:
        List[Tuple[pd.Index, pd.Index]]: רשימה של צמדים, כאשר כל צמד מכיל
                                         את אינדקסי האימון ואינדקסי המבחן.
    """
    idx = df.index
    n_obs = len(idx)
    fold_sizes = np.full(n_splits, n_obs // n_splits, dtype=int)
    fold_sizes[:n_obs % n_splits] += 1
    bounds = np.cumsum(fold_sizes)
    starts = np.concatenate(([0], bounds[:-1]))

    splits = []
    for i in range(n_splits):
        val_start, val_end = starts[i], bounds[i]

        # --- Purging ---
        # הסרת דגימות מהאימון שחופפות לתקופת המבחן
        train_left_end = val_start
        train_right_start = val_end

        # --- Embargo ---
        # הסרת דגימות נוספות מהאימון מיד לאחר תקופת המבחן
        train_right_start += embargo_len

        train_idx_left = idx[:train_left_end]
        train_idx_right = idx[train_right_start:]
        train_indices = train_idx_left.union(train_idx_right)

        val_indices = idx[val_start:val_end]
        splits.append((train_indices, val_indices))

    return splits

# =============================================================================
# 2) מדדים סטטיסטיים להערכת סיכון אוברפיטינג
# =============================================================================

def probabilistic_sharpe_ratio(
    sr_hat: float,
    T: int,
    skew: float = 0.0,
    kurt: float = 3.0,
    sr_bench: float = 0.0
) -> float:
    """
    חישוב Probabilistic Sharpe Ratio (PSR).
    מעריך את ההסתברות שיחס השארפ האמיתי (לא הנצפה) גבוה מיחס שארפ ייחוס (sr_bench).
    המדד לוקח בחשבון את אורך סדרת התשואות ואת המומנטים הגבוהים (צידוד וגבנוניות).

    Args:
        sr_hat (float): יחס השארפ הנצפה (בדרך כלל שנתי).
        T (int): מספר תצפיות (ימי מסחר) בסדרה.
        skew (float): הצידוד של סדרת התשואות.
        kurt (float): הגבנוניות של סדרת התשואות.
        sr_bench (float): יחס השארפ של הבנצ'מרק להשוואה.

    Returns:
        float: ההסתברות (בין 0 ל-1) שהשארפ האמיתי עולה על הבנצ'מרק.
    """
    if T < 10: return 0.0
    try:
        term1 = 1 - skew * sr_hat
        term2 = (kurt - 1) / 4 * sr_hat**2
        std_sr = sqrt((term1 + term2) / (T - 1))

        if std_sr == 0: return 1.0 if sr_hat > sr_bench else 0.0

        z = (sr_hat - sr_bench) / std_sr
        return norm.cdf(z)
    except (ValueError, ZeroDivisionError):
        return 0.0

def deflated_sharpe_ratio(
    sr_hat: float,
    T: int,
    n_trials: int,
    skew: float = 0.0,
    kurt: float = 3.0
) -> float:
    """
    חישוב Deflated Sharpe Ratio (DSR).
    "מעניש" את יחס השארפ הנצפה על סמך כמות הניסויים (אסטרטגיות, פרמטרים)
    שנבחנו כדי להגיע לתוצאה. זהו מדד קריטי למניעת "זיהום נתונים" (Data Snooping).

    ה-DSR עונה על השאלה: "מהו יחס השארפ הצפוי מהאסטרטגיה הטובה ביותר מתוך N ניסויים,
    בהנחה שכל האסטרטגיות היו חסרות יכולת חיזוי אמיתית?"

    Args:
        sr_hat (float): יחס השארפ הנצפה (שנתי).
        T (int): מספר תצפיות.
        n_trials (int): מספר הניסויים (אסטרטגיות, פרמטרים) שנבחנו.
        skew (float): צידוד התשואות.
        kurt (float): גבנוניות התשואות.

    Returns:
        float: ההסתברות שהשארפ הנצפה אינו תוצאה של data snooping.
    """
    if T < 10 or n_trials < 1: return 0.0

    term1 = 1 - skew * sr_hat
    term2 = (kurt - 1) / 4 * sr_hat**2
    var_sr = (term1 + term2) / (T - 1)

    if var_sr <= 0: return 1.0 if sr_hat > 0 else 0.0

    # Euler's constant
    EM_CONST = 0.5772156649

    # חישוב יחס השארפ המקסימלי הצפוי במקרה
    sr_max_exp = sqrt(var_sr) * ((1 - EM_CONST) * norm.ppf(1 - 1/n_trials) + EM_CONST * norm.ppf(1 - 1/(n_trials * np.e)))

    # אם השארפ המקסימלי הצפוי הוא 0, כל שארפ חיובי הוא מובהק
    if sr_max_exp == 0:
        return 1.0 if sr_hat > 0 else 0.0

    dsr_prob = norm.cdf(sr_hat, loc=sr_max_exp, scale=sqrt(var_sr))
    return dsr_prob

def min_track_record_length(sr_hat: float, sr_target: float, n_trials: int = 1, significance_level: float = 0.95) -> int:
    """
    חישוב Minimum Track Record Length (MinTRL).
    מעריך את אורך סדרת התשואות המינימלי הנדרש כדי לקבוע, ברמת מובהקות נתונה,
    שיחס השארפ האמיתי של האסטרטגיה גבוה מיחס שארפ מטרה.

    Args:
        sr_hat (float): יחס השארפ הנצפה (שנתי).
        sr_target (float): יחס השארפ המטרה שרוצים לעבור.
        n_trials (int): מספר הניסויים שנבחנו (לא חובה).
        significance_level (float): רמת המובהקות הסטטיסטית (למשל, 0.95 עבור 95%).

    Returns:
        int: מספר שנות המסחר המינימלי הנדרש.
    """
    if sr_hat <= sr_target:
        return float('inf')

    z = norm.ppf(significance_level)
    alpha = (1 / (n_trials**0.5)) if n_trials > 1 else 1.0

    min_trl_val = 1 + (z / (sr_hat - sr_target))**2 * alpha
    return int(np.ceil(min_trl_val))

def true_cscv_pbo(scores: np.ndarray, M: int) -> float:
    """
    חישוב Probability of Backtest Overfitting (PBO) באמצעות
    Combinatorially Symmetric Cross-Validation (CSCV).
    זוהי שיטה רובסטית להערכת הסיכוי שהפרמטרים שנבחרו כ"אופטימליים" על
    נתוני האימון יפגינו ביצועים נחותים על נתוני המבחן.

    Args:
        scores (np.ndarray): מערך של מדדי ביצוע (למשל, Sharpe) עבור כל קונפיגורציית פרמטרים.
        M (int): מספר הבלוקים לחלוקת הנתונים. חייב להיות זוגי.

    Returns:
        float: ההסתברות לאוברפיטינג (PBO). ערך קרוב ל-0.5 מצביע על אוברפיטינג.
               ערך קרוב ל-0 מצביע על אסטרטגיה רובסטית.
    """
    n = len(scores)
    if n < M or M % 2 != 0:
        print(f"❌ אורך נתונים ({n}) קטן ממספר הבלוקים ({M}) או ש-M אינו זוגי.")
        return 0.5

    blocks = np.array_split(np.arange(n), M)
    neg_count = 0
    total_combinations = 0

    # איטרציה על כל הקומבינציות של בחירת M/2 בלוקים לאימון
    for train_blocks_indices in combinations(range(M), M // 2):
        val_blocks_indices = [i for i in range(M) if i not in train_blocks_indices]

        train_idx = np.concatenate([blocks[i] for i in train_blocks_indices])
        val_idx = np.concatenate([blocks[i] for i in val_blocks_indices])

        if len(train_idx) == 0 or len(val_idx) == 0:
            continue

        train_scores = scores[train_idx]
        val_scores = scores[val_idx]

        # מציאת הביצוע האופטימלי על קבוצת האימון
        best_train_performance = np.max(train_scores)

        # חישוב הביצוע הממוצע על קבוצת המבחן
        avg_val_performance = np.mean(val_scores)

        # בדיקה אם הביצוע על המבחן נמוך מהביצוע האופטימלי על האימון (אינדיקציה לאוברפיטינג)
        if avg_val_performance < best_train_performance:
            neg_count += 1
        total_combinations += 1

    return neg_count / total_combinations if total_combinations > 0 else 0.5


# =============================================================================
# 3) מדדי ביצוע וניהול סיכונים
# =============================================================================

def max_drawdown(pnl_history: List[float]) -> float:
    """
    מחשב את ה-Max Drawdown (הירידה המקסימלית מהשיא) של סדרת תשואות.

    Args:
        pnl_history (List[float]): רשימת התשואות היומיות/תקופתיות.

    Returns:
        float: ה-Max Drawdown כאחוז (למשל, 0.15 עבור 15%).
    """
    if not pnl_history: return 0.0
    cum_returns = np.cumprod(1 + np.array(pnl_history))
    if not cum_returns.any(): return 0.0

    peak = np.maximum.accumulate(cum_returns)
    # הוספת 1 לשיא במקרה שהשיא הוא 0 בתחילת הדרך למניעת חלוקה באפס
    peak[peak == 0] = 1.0

    drawdown = (cum_returns - peak) / peak
    return float(np.min(drawdown)) # החזרת הערך השלילי המקסימלי

def evaluate_strategy_performance(pnl_history: pd.Series, n_trials: int = 1) -> Dict[str, float]:
    """
    מחשב סט מקיף של מדדי ביצוע וסיכון עבור סדרת תשואות.

    Args:
        pnl_history (pd.Series): סדרת PnL.
        n_trials (int): מספר הניסויים שנבחנו.

    Returns:
        Dict[str, float]: מילון של מדדי ביצוע.
    """
    if pnl_history.empty or pnl_history.std() == 0:
        return {
            "Total Return": 0.0, "Annualized Sharpe": 0.0, "Max Drawdown": 0.0,
            "Calmar Ratio": 0.0, "PSR": 0.0, "DSR Probability": 0.0, "MinTRL (years)": float('inf')
        }

    T = len(pnl_history)

    # מדדי ביצוע סטנדרטיים
    total_ret = (1 + pnl_history).prod() - 1
    ann_ret = (1 + total_ret)**(252 / T) - 1 if T > 0 else 0
    ann_vol = pnl_history.std() * sqrt(252)
    sr = ann_ret / ann_vol if ann_vol > 0 else 0.0
    mdd = abs(max_drawdown(pnl_history.tolist()))
    calmar = ann_ret / mdd if mdd > 0 else 0.0

    # מדדי אוברפיטינג
    skewness = pnl_history.skew()
    kurtosis = pnl_history.kurt() + 3 # pandas.kurt is excess kurtosis

    psr = probabilistic_sharpe_ratio(sr, T, skewness, kurtosis)
    dsr = deflated_sharpe_ratio(sr, T, n_trials, skewness, kurtosis)
    min_trl_days = min_track_record_length(sr, sr_target=0.5, n_trials=n_trials)
    min_trl_years = min_trl_days / 252

    return {
        "Total Return": total_ret,
        "Annualized Return": ann_ret,
        "Annualized Volatility": ann_vol,
        "Annualized Sharpe": sr,
        "Max Drawdown": mdd,
        "Calmar Ratio": calmar,
        "Skewness": skewness,
        "Kurtosis": kurtosis,
        "PSR": psr,
        "DSR Probability": dsr,
        "MinTRL (years)": min_trl_years,
    }
