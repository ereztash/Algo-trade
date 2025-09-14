import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any
from skopt import gp_minimize
from skopt.space import Real, Integer, Categorical
import logging

from ...main import run_day
from ...utils import calculate_sharpe_ratio
from ...signals.ensemble import merge_signals_by_mis
from ...signals.orthogonalize import orthogonalize_signals
from ...validation.cscv import true_cscv_pbo, purged_k_fold
from ..execution.transaction_costs import OnlineLambdaLearner
from ..portfolio import solve_qp
from ...gates.linucb import LinUCB
from ...data.adaptive_cov import adaptive_cov
from ...utils import max_drawdown
from ...main import exec_and_learn_lambda

# הגדרת הלוגר עבור המודול
logger = logging.getLogger(__name__)

# =============================================================================
# 1) פונקציית המטרה של האופטימיזציה
# =============================================================================

class ObjectiveFunction:
    """
    מחלקה שמייצגת את פונקציית המטרה עבור האופטימיזציה הבייסיאנית.
    היא מבצעת backtest של האסטרטגיה על סט נתונים נתון עם ולידציה פנימית.
    """
    def __init__(self, returns: pd.DataFrame, prices: pd.DataFrame, cfg: Dict):
        """
        אתחול פונקציית המטרה.
        
        Parameters:
        returns (pd.DataFrame): נתוני התשואות לאימון.
        prices (pd.DataFrame): נתוני המחירים לאימון.
        cfg (Dict): מילון תצורה.
        """
        self.returns = returns
        self.prices = prices
        self.cfg = cfg

    def __call__(self, params_list: List[Any]) -> float:
        """
        פונקציה זו מופעלת על ידי האופטימייזר הבייסיאני.
        היא מקבלת רשימת פרמטרים, מריצה backtest ומחזירה את יחס השארפ.
        """
        params_dict = self._parse_params(params_list)
        
        # שימוש ב-Purged K-Fold לולידציה פנימית של הפרמטרים
        splits = purged_k_fold(self.returns, n_splits=5, embargo_len=10)
        
        scores = []
        for train_idx, val_idx in splits:
            if val_idx.empty:
                continue
            
            # ביצוע backtest על נתוני האימון
            train_returns = self.returns.loc[train_idx]
            train_prices = self.prices.loc[train_idx]
            pnl_train = self._run_backtest_on_split(train_returns, train_prices, params_dict)

            # ביצוע backtest על נתוני הוולידציה
            val_returns = self.returns.loc[val_idx]
            val_prices = self.prices.loc[val_idx]
            pnl_val = self._run_backtest_on_split(val_returns, val_prices, params_dict)
            
            # חישוב מדדים על נתוני הוולידציה
            sharpe_val = calculate_sharpe_ratio(np.array(pnl_val))
            max_dd_val = max_drawdown(pnl_val)
            
            # פונקציית המטרה כוללת כעת גם עונש על Drawdown
            score = sharpe_val - (max_dd_val * 2.0)
            scores.append(score)

        if not scores:
            return 0.0

        avg_score = np.mean(scores)
        
        logger.info(f"Tested params: {params_dict} -> Average Score: {avg_score:.2f}")

        # האופטימייזר שואף למזער, לכן נחזיר את הערך השלילי של הציון הממוצע
        return -avg_score

    def _run_backtest_on_split(self, returns_split: pd.DataFrame, prices_split: pd.DataFrame, params: Dict) -> List[float]:
        """מבצע backtest על סט נתונים נתון."""
        history = []
        w_prev = pd.Series(0.0, index=returns_split.columns)
        lam_learner = OnlineLambdaLearner(self.cfg)
        linucb = LinUCB(n_arms=self.cfg["NUM_STRATEGIES"], n_features=4, alpha=self.cfg["LINUCB_ALPHA"])
        C_prev = adaptive_cov(returns_split.iloc[:30], "Normal", 1)

        # הרצת הסימולציה
        for t in range(30, len(returns_split)):
            try:
                # קריאה ל-run_day המלא
                net_ret, w_new, _, C_new, _, _, _ = run_day(
                    t=t,
                    prices=prices_split,
                    returns=returns_split,
                    w_prev=w_prev,
                    lam_prev=lam_learner.get_lambda(),
                    linucb=linucb,
                    C_prev=C_prev,
                    params=params
                )
                
                # עדכון הלמדא בלולאה, תוך שימוש בנתונים אמיתיים יותר מהסימולציה
                # (במקום הערכים הסימולטיביים 1.0)
                # החישוב הפנימי ב-run_day כולל גם את עלות העסקה, אז נשתמש בו.
                lam_learner.lam = exec_and_learn_lambda(
                    w_prev=w_prev,
                    w_tgt=w_new,
                    returns_today=returns_split.iloc[t],
                    adv_today=returns_split.iloc[max(0, t-20):t].abs().mean() + 1e-9,
                    lam_prev=lam_learner.get_lambda()
                )[1]
                
                history.append(net_ret)
                w_prev = w_new
                C_prev = C_new
            except Exception as e:
                logger.debug(f"Error during split backtest for params {params}: {e}")
                # במקרה של כשל, נחזיר ערך שלילי מאוד כדי שהאופטימייזר יתרחק מהפרמטרים האלה
                return [-1000]

        return history

    def _parse_params(self, params_list: List[Any]) -> Dict[str, Any]:
        """ממיר רשימת פרמטרים למילון."""
        return {
            "MOM_H": int(params_list[0]),
            "REV_H": int(params_list[1]),
            "TURNOVER_PEN": float(params_list[2]),
            "RIDGE_PEN": float(params_list[3])
        }

# =============================================================================
# 2) ניהול תהליך האופטימיזציה
# =============================================================================

def run_bayesian_optimization(returns: pd.DataFrame, prices: pd.DataFrame, cfg: Dict) -> Dict:
    """
    מנהל את תהליך האופטימיזציה הבייסיאנית.
    
    Parameters:
    returns (pd.DataFrame): נתוני התשואות לאימון.
    prices (pd.DataFrame): נתוני המחירים לאימון.
    cfg (Dict): מילון תצורה.
    
    Returns:
    Dict: מילון הפרמטרים האופטימליים שנמצאו.
    """
    logger.info("Starting Bayesian optimization process...")
    
    search_space_type = cfg.get("BAYESIAN_OPTIMIZATION", {}).get("SEARCH_SPACE_TYPE", "basic")

    if search_space_type == "basic":
        search_space = [
            Integer(cfg["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]["MOM_H"][0], cfg["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]["MOM_H"][1], name='MOM_H'),
            Integer(cfg["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]["REV_H"][0], cfg["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]["REV_H"][1], name='REV_H'),
            Real(cfg["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]["TURNOVER_PEN"][0], cfg["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]["TURNOVER_PEN"][1], name='TURNOVER_PEN'),
            Real(cfg["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]["RIDGE_PEN"][0], cfg["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]["RIDGE_PEN"][1], name='RIDGE_PEN')
        ]
    elif search_space_type == "advanced":
        search_space = [
            Integer(10, 30, name='MOM_H'),
            Integer(3, 10, name='REV_H'),
            Real(1e-4, 1e-2, name='TURNOVER_PEN'),
            Real(1e-6, 1e-4, name='RIDGE_PEN'),
            Categorical(['OFI', 'ERN', 'VRP', 'POS'], name='PRIMARY_SIGNAL')
        ]
    else:
        raise ValueError(f"Unknown search space type: {search_space_type}")

    objective = ObjectiveFunction(returns, prices, cfg)
    
    # הפעלת האופטימייזר הבייסיאני
    result = gp_minimize(
        func=objective,
        dimensions=search_space,
        n_calls=cfg["BAYESIAN_OPTIMIZATION"]["ITERATIONS"],
        random_state=cfg["SEED"]
    )
    
    best_params_list = result.x
    best_sharpe = -result.fun
    
    best_params_dict = {
        'MOM_H': int(best_params_list[0]),
        'REV_H': int(best_params_list[1]),
        'TURNOVER_PEN': float(best_params_list[2]),
        'RIDGE_PEN': float(best_params_list[3])
    }

    if search_space_type == "advanced":
        best_params_dict['PRIMARY_SIGNAL'] = best_params_list[4]
    
    logger.info(f"Bayesian optimization finished. Best Score: {best_sharpe:.2f}")
    logger.info(f"Optimal parameters found: {best_params_dict}")
    
    return best_params_dict
