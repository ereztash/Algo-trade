import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple

# =============================================================================
# 1) Transaction Cost Model
# =============================================================================

class TransactionCostModel:
    """
    מודל כללי לחישוב עלויות עסקה המורכב ממספר רכיבים:
    - Fixed Brokerage Fees (עמלות קבועות)
    - Linear Market Impact (השפעת שוק ליניארית)
    - Non-Linear Market Impact (השפעת שוק לא-ליניארית, Power Law)
    """

    def __init__(self, cfg: Dict):
        """
        אתחול המודל עם הגדרות תצורה.
        
        Parameters:
        cfg (Dict): מילון תצורה המכיל פרמטרים כמו per_share_fee, slippage_beta, וכדומה.
        """
        self.cfg = cfg
        self.per_share_fee = cfg.get("per_share_fee", 0.005)  # עמלה קבועה למניה
        self.linear_factor = cfg.get("linear_factor", 0.0001)  # גורם ליניארי להשפעת שוק
        self.slippage_beta = cfg.get("slippage_beta", 0.7)  # בטא עבור מודל Power Law
        self.pov_cap = cfg.get("pov_cap", 0.10)  # מגבלת POV

    def calculate_cost(self, trade_volumes: pd.Series, adv: pd.Series) -> pd.Series:
        """
        מחשב את העלות הכוללת עבור סדרת עסקאות.
        
        Parameters:
        trade_volumes (pd.Series): נפח המסחר (בכסף) לכל נכס.
        adv (pd.Series): Average Daily Volume של הנכסים.
        
        Returns:
        pd.Series: סדרת העלויות הכוללות עבור כל נכס.
        """
        # חישוב העלות הקבועה (עמלת ברוקר)
        fixed_costs = trade_volumes.apply(lambda x: self.per_share_fee if x > 0 else 0)

        # חישוב עלות השפעת שוק ליניארית (פרופורציונלית לנפח המסחר)
        linear_impact = self.linear_factor * trade_volumes.abs()

        # חישוב עלות השפעת שוק לא-ליניארית (Power Law)
        # POV = Percent of Volume, היחס בין נפח העסקה ל-ADV
        pov = np.minimum(trade_volumes.abs() / (adv + 1e-9), self.pov_cap)
        non_linear_impact = (pov ** self.slippage_beta) * self.cfg.get("lam", 1.0)

        # העלות הכוללת היא סכום כל הרכיבים
        total_cost = fixed_costs + linear_impact + non_linear_impact

        return total_cost

# =============================================================================
# 2) Online Lambda Learning
# =============================================================================

class OnlineLambdaLearner:
    """
    מחלקה ללמידת פרמטר העלות למדא (λ) בזמן אמת, באמצעות ממוצע נע מעריכי (EMA).
    """

    def __init__(self, cfg: Dict):
        """
        אתחול הלומד.
        
        Parameters:
        cfg (Dict): מילון תצורה.
        """
        self.lam = cfg.get("lambda_init", 5e-4)  # ערך התחלתי ללמדא
        self.ema_rho = cfg.get("lambda_ema_rho", 0.1)  # משקל ה-EMA
        self.observations = 0

    def update(self, realized_cost: float, trade_volume: float, adv: float):
        """
        מעדכן את פרמטר הלמדא על בסיס עלות שבוצעה בפועל.
        
        Parameters:
        realized_cost (float): עלות הביצוע בפועל (מחיר מילוי - מחיר ממוצע).
        trade_volume (float): נפח העסקה שבוצעה.
        adv (float): ממוצע הנפח היומי (Average Daily Volume).
        """
        self.observations += 1
        
        if trade_volume < 1e-9 or adv < 1e-9:
            return

        # חישוב POV של העסקה שבוצעה
        pov = np.minimum(trade_volume / adv, self.ema_rho)

        # אומדן הלמדא הנוכחי (lam_hat)
        lam_hat = realized_cost / (pov ** self.ema_rho) if pov > 1e-9 else self.lam

        # עדכון למדא באמצעות EMA
        self.lam = (1 - self.ema_rho) * self.lam + self.ema_rho * lam_hat
        self.lam = max(1e-6, self.lam)  # ודא שהלמדא תמיד חיובי

    def get_lambda(self) -> float:
        """מחזיר את ערך הלמדא הנוכחי."""
        return self.lam

# =============================================================================
# 3) Utility Functions for Cost Calculation
# =============================================================================

def calculate_realized_cost(
    fill_price: float,
    vwap: float,
    trade_size: float,
    per_share_fee: float
) -> Tuple[float, float]:
    """
    מחשב את עלות הביצוע בפועל (במונחי דולר ויחס).
    
    Parameters:
    fill_price (float): מחיר המילוי של הפקודה.
    vwap (float): מחיר ה-VWAP של אותו יום/תקופה.
    trade_size (float): גודל הפקודה (בכמות מניות).
    per_share_fee (float): עמלה קבועה למניה.
    
    Returns:
    Tuple[float, float]: (העלות הכוללת בדולרים, העלות כאחוז מהשווי).
    """
    if trade_size <= 0:
        return 0.0, 0.0

    # עלות ההחלקה (Slippage) כהפרש בין מחיר המילוי ל-VWAP
    slippage_cost = np.abs(fill_price - vwap) * trade_size

    # העלות הכוללת היא סכום עלות ההחלקה והעמלות הקבועות
    total_cost_usd = slippage_cost + (per_share_fee * trade_size)

    # עלות כאחוז מהשווי (כסף שהוחלף)
    trade_value = vwap * trade_size
    cost_pct = (total_cost_usd / trade_value) if trade_value > 1e-9 else 0.0

    return total_cost_usd, cost_pct

def convert_weights_to_volume(
    delta_w: pd.Series,
    portfolio_value: float
) -> pd.Series:
    """
    ממיר שינויי משקל בתיק לנפח מסחר דולרי (מטריצה).
    
    Parameters:
    delta_w (pd.Series): סדרת שינוי המשקלים הרצויים.
    portfolio_value (float): שווי התיק הכולל.
    
    Returns:
    pd.Series: נפחי המסחר הדולריים.
    """
    return delta_w * portfolio_value
