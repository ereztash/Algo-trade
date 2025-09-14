import numpy as np
import pandas as pd
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

def calculate_drawdown(equity_curve: pd.Series) -> pd.DataFrame:
    """
    מחשב את סדרת נתוני המשיכה (drawdown) מתוך עקומת שווי התיק (Equity).
    השיא (peak) נמדד כשיא המצטבר עד כל נקודה.

    Parameters:
    equity_curve (pd.Series): עקומת שווי התיק (equity) של אסטרטגיית המסחר.

    Returns:
    pd.DataFrame: DataFrame עם סדרות נתונים של שווי התיק, שיאים (peaks) ומשיכה (drawdown).
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return pd.DataFrame(columns=['equity', 'peak', 'drawdown'])

    peak = equity_curve.cummax()
    drawdown = (peak - equity_curve) / (peak.replace(0, np.nan))
    drawdown.fillna(0, inplace=True)
    
    return pd.DataFrame({
        'equity': equity_curve,
        'peak': peak,
        'drawdown': drawdown
    })

def max_drawdown(pnl_hist: List[float]) -> float:
    """
    מחשב את משיכת היתר המקסימלית (Max Drawdown).
    
    Parameters:
    pnl_hist (List[float]): רשימה של תשואות יומיות.

    Returns:
    float: ערך משיכת היתר המקסימלית.
    """
    if not pnl_hist:
        return 0.0

    equity_curve = (1 + pd.Series(pnl_hist)).cumprod()
    dd_df = calculate_drawdown(equity_curve)
    
    if dd_df.empty:
        return 0.0
    return float(dd_df['drawdown'].max())

def analyze_drawdowns(pnl_hist: List[float]) -> Dict[str, float]:
    """
    מחשב מספר מדדים מתקדמים של משיכות יתר.
    
    Parameters:
    pnl_hist (List[float]): רשימה של תשואות יומיות.

    Returns:
    Dict[str, float]: מילון המכיל מדדים שונים.
    """
    if not pnl_hist:
        return {
            "max_drawdown": 0.0,
            "average_drawdown": 0.0,
            "longest_recovery_period": 0,
            "average_recovery_period": 0.0,
            "num_drawdowns": 0
        }

    equity_curve = (1 + pd.Series(pnl_hist)).cumprod()
    dd_df = calculate_drawdown(equity_curve)
    
    # חישוב מדדים
    max_dd = dd_df['drawdown'].max()
    
    # זיהוי תקופות משיכה
    is_in_drawdown = (dd_df['drawdown'] > 0).astype(int)
    drawdown_starts = (is_in_drawdown.diff() > 0)
    
    drawdown_lengths = []
    recovery_periods = []
    num_drawdowns = 0
    
    # חישוב תקופות התאוששות
    for i in range(len(dd_df)):
        if drawdown_starts.iloc[i]:
            start_index = i
            end_index = dd_df.loc[start_index:].index[
                (dd_df['drawdown'].loc[start_index:] == 0) &
                (dd_df['drawdown'].shift(-1).loc[start_index:] == 0)
            ].min()
            
            if pd.notna(end_index):
                num_drawdowns += 1
                length = end_index - start_index
                drawdown_lengths.append(length)
                
                # חישוב תקופת התאוששות
                if i > 0 and (dd_df.iloc[i-1]['drawdown'] > 0):
                    recovery_start_index = dd_df.iloc[i-1].name
                    recovery_period = i - recovery_start_index
                    recovery_periods.append(recovery_period)
                    
    avg_dd = np.mean(drawdown_lengths) if drawdown_lengths else 0
    longest_rec = np.max(recovery_periods) if recovery_periods else 0
    avg_rec = np.mean(recovery_periods) if recovery_periods else 0
    
    return {
        "max_drawdown": float(max_dd),
        "average_drawdown": float(avg_dd),
        "longest_recovery_period": int(longest_rec),
        "average_recovery_period": float(avg_rec),
        "num_drawdowns": int(num_drawdowns)
    }

def drawdown_kill_switch_graded(pnl_hist: List[float], thresholds: Dict[str, float]) -> str:
    """
    Kill-Switch מדורג המבוסס על משיכת היתר.
    
    Parameters:
    pnl_hist (List[float]): רשימה של תשואות יומיות.
    thresholds (Dict[str, float]): מילון ספים מדורגים.
    
    Returns:
    str: מצב הסוויץ' ('NORMAL', 'REDUCE', 'HALT').
    """
    dd = max_drawdown(pnl_hist)
    
    if dd > thresholds.get("HALT", 0.20):
        return "HALT"
    elif dd > thresholds.get("REDUCE", 0.10):
        return "REDUCE"
    else:
        return "NORMAL"
