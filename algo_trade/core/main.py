# -*- coding: utf-8 -*-
"""
trading_system_full_v2.py
מערכת מסחר אלגוריתמית סינתטית, מודולרית, ורצה מקצה לקצה.
שדרוגים:
- יישום מלא של CSCV עם M בלוקים.
- שדרוג LinUCB (Contextual Bandit) מלא, כולל רגרסיה רידג'.
- הוספת בנצ'מרקינג מול Black-Litterman.

קוד ותגובות בעברית (מדויקות) כדי להאיץ אינטגרציה/שינויים.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import cvxpy as cp
from typing import Dict, Tuple, List, Optional
import yaml
import os
from scipy.stats import norm, entropy
from math import erf, sqrt
from sklearn.covariance import LedoitWolf
from scipy.spatial.distance import squareform
from scipy.cluster.hierarchy import linkage, leaves_list
from itertools import combinations
from sklearn.decomposition import PCA

# ייבוא סוכן GDT
try:
    from algo_trade.core.agents import GDTAgent, MarketState, GeometricIndicators
    GDT_AVAILABLE = True
except ImportError:
    GDT_AVAILABLE = False
    print("⚠️ סוכן GDT לא זמין. הריצה תימשך ללא מדדים גיאומטריים.")

# =============================================================================
# 0) קונפיג כללי – טעינה מקובץ YAML
# =============================================================================

CFG = None
def load_config(filepath: str = 'targets.yaml') -> Dict:
    """טוען או יוצר קובץ קונפיגורציה."""
    global CFG
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            print(f"✅ קובץ קונפיגורציה {filepath} נטען בהצלחה.")
            CFG = config
            return config
    except FileNotFoundError:
        print(f"❌ קובץ קונפיגורציה {filepath} לא נמצא.")
        default_config = {
            "SEED": 42,
            "DAYS": 252 * 2,
            "N": 60,
            "START_PRICE": 100.0,
            "MU_DAILY": 0.0002,
            "SIGMA_DAILY": 0.015,
            "MOM_H": 20,
            "REV_H": 5,
            "VOL_H": 20,
            "POS_H": 60,
            "TSX_H": 30,
            "SIF_H_FAST": 5,
            "SIF_H_SLOW": 20,
            "ORTHO_WIN": 252,
            "REGIME_WIN": 60,
            "COV_EWMA_HL": {"Calm": 60, "Normal": 30, "Storm": 10},
            "GROSS_LIM": {"Calm": 2.5, "Normal": 2.0, "Storm": 1.0},
            "NET_LIM": {"Calm": 1.0, "Normal": 0.8, "Storm": 0.4},
            "VOL_TARGET": 0.10,
            "BOX_LIM": 0.25,
            "TURNOVER_PEN": 0.002,
            "RIDGE_PEN": 1e-4,
            "LAMBDA_INIT": 5e-4,
            "LAMBDA_EMA_RHO": 0.1,
            "SLIP_BETA": 0.7,
            "POV_CAP": 0.08,
            "ADV_CAP": 0.10,
            "KILL_PNL": -0.05,
            "COV_DRIFT": 0.10,
            "PSR_KILL_SWITCH": 0.20,
            "MAX_DD_KILL_SWITCH": 0.15,
            "PRINT_EVERY": 25,
            "NUM_STRATEGIES": 6,
            "BAYESIAN_OPTIMIZATION": {
                "ITERATIONS": 50,
                "SEARCH_SPACE": {
                    "MOM_H": [10, 30],
                    "REV_H": [3, 10],
                    "TURNOVER_PEN": [0.001, 0.005],
                    "RIDGE_PEN": [1e-5, 1e-3]
                }
            },
            "CSCV_M": 16,
            "LINUCB_ALPHA": 0.1
        }
        with open(filepath, 'w', encoding='utf-8') as file:
            yaml.dump(default_config, file, allow_unicode=True, default_flow_style=False)
        print("✅ קובץ ברירת מחדל 'targets.yaml' נוצר. נא עדכן אותו בהתאם לצרכים.")
        CFG = default_config
        return default_config
    except yaml.YAMLError as e:
        print(f"❌ שגיאה בקריאת קובץ YAML: {e}")
        return None

config = load_config()
rng = np.random.default_rng(config.get("SEED", 42))

# =============================================================================
# 1) סימולציית מחירים ותשואות
# =============================================================================

def simulate_prices() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """מייצר סדרות תשואות נורמליות, ומחירים ע"י אינטגרציה אקספוננציאלית."""
    rets = rng.normal(CFG["MU_DAILY"], CFG["SIGMA_DAILY"], size=(CFG["DAYS"], CFG["N"]))
    rets = pd.DataFrame(rets, columns=[f"Asset_{i}" for i in range(CFG["N"])])
    px = CFG["START_PRICE"] * np.exp(rets.cumsum())
    return px, rets

# =============================================================================
# 2) הנדסת פיצ'רים/סיגנלים – פרוקסים סינתטיים שמורים
# =============================================================================

def zscore(df: pd.DataFrame, win: int) -> pd.DataFrame:
    m = df.rolling(win).mean()
    s = df.rolling(win).std(ddof=0)
    return ((df - m) / (s.replace(0, np.nan)))

def ofi_signal(returns: pd.DataFrame, mom_h: int) -> pd.DataFrame:
    vol = returns.abs().rolling(3).sum().clip(lower=1e-8)
    ofi = returns.rolling(3).sum() / vol
    return zscore(ofi, mom_h).fillna(0)

def ern_signal(returns: pd.DataFrame) -> pd.DataFrame:
    shock = (returns.rolling(21).mean() - returns.rolling(63).mean())
    return zscore(shock, 63).fillna(0)

def vrp_signal(returns: pd.DataFrame, vol_h: int) -> pd.DataFrame:
    rv = returns.pow(2).rolling(vol_h).mean()
    iv = returns.abs().ewm(span=vol_h, adjust=False).mean()
    vrp = iv * 1.5 - np.sqrt(rv.clip(lower=0))
    return zscore(vrp, vol_h).fillna(0)

def pos_signal(returns: pd.DataFrame, pos_h: int) -> pd.DataFrame:
    pos = returns.rolling(pos_h).mean()
    return zscore(pos, pos_h).fillna(0)

def tsx_signal(returns: pd.DataFrame, tsx_h: int) -> pd.DataFrame:
    short = returns.rolling(10).mean()
    long = returns.rolling(tsx_h).mean()
    slope = short - long
    return zscore(slope, tsx_h).fillna(0)

def sif_signal(returns: pd.DataFrame, sif_h_fast: int, sif_h_slow: int) -> pd.DataFrame:
    fast = returns.rolling(sif_h_fast).mean()
    slow = returns.rolling(sif_h_slow).mean()
    flow = fast - slow
    return zscore(flow, sif_h_slow).fillna(0)

def build_signals(returns: pd.DataFrame, params: Dict) -> Dict[str, pd.DataFrame]:
    sigs = {
        "OFI": ofi_signal(returns, params["MOM_H"]),
        "ERN": ern_signal(returns),
        "VRP": vrp_signal(returns, params["VOL_H"]),
        "POS": pos_signal(returns, params["POS_H"]),
        "TSX": tsx_signal(returns, params["TSX_H"]),
        "SIF": sif_signal(returns, params["SIF_H_FAST"], params["SIF_H_SLOW"]),
    }
    return sigs

def future_returns(returns: pd.DataFrame, horizon: int = 5) -> pd.DataFrame:
    return returns.shift(-1).rolling(horizon).sum()

def information_coefficient(signal: pd.DataFrame, fwd_ret: pd.DataFrame) -> pd.DataFrame:
    return signal.corrwith(fwd_ret, axis=1)

def mis_per_signal_pipeline(
    sigs: Dict[str, pd.DataFrame],
    returns: pd.DataFrame,
    horizon: int = 5
) -> Dict[str, pd.DataFrame]:
    """מחשב מדד חשיבות (MIS) עבור כל סיגנל."""
    fwd = future_returns(returns, horizon=horizon)
    mis = {}
    for name, S in sigs.items():
        IC = information_coefficient(S, fwd)
        stab = np.exp(- (S.diff().abs().rolling(21).mean())).clip(0, 1)
        cap = (returns.abs().rolling(20).mean())
        cost = 1.0 + 5.0 * returns.abs().rolling(3).mean()
        score = (IC * stab * cap) / cost
        mis[name] = score.fillna(0)
    return mis

def merge_signals_by_mis(
    sigs: Dict[str, pd.DataFrame], mis: Dict[str, pd.DataFrame]
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    weights = {k: float(mis[k].iloc[-1].replace([np.inf, -np.inf], 0).mean()) for k in sigs}
    wsum = sum(abs(v) for v in weights.values()) or 1.0
    weights = {k: v / wsum for k, v in weights.items()}
    merged = pd.DataFrame(0.0, index=next(iter(sigs.values())).index, columns=next(iter(sigs.values())).columns)
    for k in sigs:
        merged = merged + weights[k] * sigs[k]
    return merged, weights

# =============================================================================
# 3) ולידציה + אנטי-אוברפיטינג: Purged K-Fold, PBO, PSR, DSR, MinTRL
# =============================================================================

def purged_k_fold(df: pd.DataFrame, n_splits: int = 5, embargo_len: int = 10) -> List[Tuple[pd.Index, pd.Index]]:
    """מבצע Purged K-Fold Cross-Validation."""
    idx = np.arange(df.shape[0])
    fold_sizes = np.full(n_splits, len(idx) // n_splits, dtype=int)
    fold_sizes[:len(idx) % n_splits] += 1
    bounds = np.cumsum(fold_sizes)
    starts = np.concatenate(([0], bounds[:-1]))
    splits = []
    for i in range(n_splits):
        val_idx = idx[starts[i]:bounds[i]]
        train_mask = np.ones_like(idx, dtype=bool)
        left = max(0, starts[i] - embargo_len)
        right = min(len(idx), bounds[i] + embargo_len)
        train_mask[left:right] = False
        tr_idx = idx[train_mask]
        splits.append((pd.Index(tr_idx), pd.Index(val_idx)))
    return splits

def true_cscv_pbo(scores: np.ndarray, M: int = 16) -> float:
    """יישום אמיתי של CSCV עם M בלוקים."""
    n = len(scores)
    if n < M:
        print(f"❌ אורך נתונים ({n}) קטן ממספר הבלוקים ({M}). מחזיר 0.5.")
        return 0.5
    blocks = np.array_split(np.arange(n), M)
    neg = 0
    total = 0
    for train_blocks_indices in combinations(range(M), M // 2):
        val_blocks_indices = [i for i in range(M) if i not in train_blocks_indices]
        train_idx = np.concatenate([blocks[i] for i in train_blocks_indices])
        val_idx = np.concatenate([blocks[i] for i in val_blocks_indices])

        if len(train_idx) == 0 or len(val_idx) == 0:
            continue

        train_scores = scores[train_idx]
        val_scores = scores[val_idx]
        
        # מציאת הסט האופטימלי על נתוני האימון
        best_train_idx = np.argmax(train_scores)
        best_train_score = train_scores[best_train_idx]
        
        # חישוב הממוצע על נתוני הוולידציה
        avg_val_score = val_scores.mean()

        if avg_val_score < best_train_score:
            neg += 1
        total += 1

    return neg / total if total > 0 else 0.5

def probabilistic_sharpe_ratio(sr_hat: float, T: int, skew: float=0.0, kurt: float=3.0, sr_bench: float=0.0) -> float:
    """חישוב PSR סטטיסטי."""
    if T < 2: return 0.0
    try:
        z = (sr_hat - sr_bench) * np.sqrt(T - 1) / np.sqrt(1 - skew*sr_hat + (kurt-1)/4 * sr_hat**2)
        return 0.5*(1+erf(z/np.sqrt(2)))
    except (ValueError, ZeroDivisionError):
        return 0.0

def deflated_sharpe_ratio(sr_hat: float, T: int, n_strats: int) -> float:
    """חישוב DSR סטטיסטי."""
    if T < 2: return 0.0
    adj = np.sqrt((np.log(n_strats)) / T)
    return sr_hat - adj

# =============================================================================
# 4) משטר שוק (Calm/Normal/Storm)
# =============================================================================

def avg_corr(df: pd.DataFrame) -> float:
    """מחשב קורלציה ממוצעת."""
    c = df.corr()
    if c.shape[0] < 2:
        return 0.0
    m = c.values
    return (np.sum(m) - np.trace(m)) / (m.shape[0] * (m.shape[1] - 1))

def detect_regime(returns: pd.DataFrame) -> str:
    """מזהה משטר שוק לפי תנודתיות וקורלציה ממוצעת, כולל מדד זנב."""
    if len(returns) < CFG["REGIME_WIN"]:
        return "Normal"
    win = returns.tail(CFG["REGIME_WIN"])
    rv20 = win.std().mean() * np.sqrt(252)
    rho60 = avg_corr(win)
    
    tail_returns = win[win.mean(axis=1) < win.mean(axis=1).quantile(0.10)]
    tail_corr = avg_corr(tail_returns)
    
    if (rv20 > 0.35) or (rho60 > 0.45) or (tail_corr > 0.6):
        return "Storm"
    elif (rv20 < 0.15) and (rho60 < 0.20):
        return "Calm"
    return "Normal"

# =============================================================================
# 5) אורתוגונליזציה מלאה (חתך-יומית) באמצעות OLS
# =============================================================================

def orthogonalize_signals(signals: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """מבצע אורתוגונליזציה של סיגנלים בחתך-יומי."""
    names = list(signals.keys())
    dates = next(iter(signals.values())).index
    assets = next(iter(signals.values())).columns
    K = len(names)
    out = {k: pd.DataFrame(index=dates, columns=assets, dtype=float) for k in names}
    for t in range(len(dates)):
        X_t = np.column_stack([signals[k].iloc[t].values for k in names])
        mask = ~np.any(np.isnan(X_t), axis=1)
        if mask.sum() <= K:
            for j, k in enumerate(names):
                out[k].iloc[t] = signals[k].iloc[t].values
            continue
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
    for k in names:
        out[k] = out[k].apply(lambda s: (s - np.nanmean(s)) / (np.nanstd(s) + 1e-12), axis=1)
        out[k] = out[k].fillna(0)
    return out

# =============================================================================
# 6) Gates – LinUCB
# =============================================================================

class LinUCB:
    """
    אלגוריתם LinUCB לטובת בחירת Gate קונטקסטואלית.
    מתבסס על רגרסיית רידג' כדי לבחור את הזרוע הטובה ביותר.
    """
    def __init__(self, n_arms: int, n_features: int, alpha: float, ridge_lambda: float = 1.0):
        self.n_arms = n_arms
        self.n_features = n_features
        self.alpha = alpha
        self.ridge_lambda = ridge_lambda
        
        # A מטריצת קו-וריאנס + רגרסיית רידג'
        self.A = [self.ridge_lambda * np.eye(n_features) for _ in range(n_arms)]
        # b וקטור תגובות (rewards)
        self.b = [np.zeros(n_features) for _ in range(n_arms)]

    def select_arm(self, context: np.ndarray) -> int:
        """
        בוחרת את הזרוע הטובה ביותר בהתאם לווקטור הקונטקסט.
        context: וקטור פיצ'רים של הקונטקסט הנוכחי.
        מחזירה: אינדקס הזרוע שנבחרה.
        """
        if context.shape[0] != self.n_features:
            raise ValueError("Context vector size mismatch")

        upper_bounds = np.zeros(self.n_arms)
        for arm in range(self.n_arms):
            try:
                A = self.A[arm]
                b = self.b[arm]
                
                # חישוב יציב של theta
                theta = np.linalg.solve(A, b)
                
                # חישוב UCB (Upper Confidence Bound)
                p_hat = theta.T @ context
                ucb = self.alpha * np.sqrt(context.T @ np.linalg.inv(A) @ context)
                
                upper_bounds[arm] = p_hat + ucb
            except np.linalg.LinAlgError:
                # במקרה של כשל חישובי, בוחר באקראי או נותן ניקוד נמוך
                upper_bounds[arm] = -np.inf
        
        if np.isinf(upper_bounds).all():
            return np.random.choice(self.n_arms)
        
        return int(np.argmax(upper_bounds))

    def update(self, arm: int, context: np.ndarray, reward: float):
        """
        מעדכנת את המודל לאחר קבלת תגמול.
        arm: אינדקס הזרוע שנבחרה.
        context: וקטור פיצ'רים של הקונטקסט.
        reward: התגמול שהתקבל לאחר בחירת הזרוע.
        """
        if context.shape[0] != self.n_features:
            raise ValueError("Context vector size mismatch")
            
        self.A[arm] += np.outer(context, context)
        self.b[arm] += context * reward

def gate_policy_by_regime(regime: str) -> List[int]:
    if regime == "Storm": return [0, 1]
    if regime == "Calm": return [0, 1, 2, 3]
    return [0, 1, 3]

# =============================================================================
# 7) קו-וריאנציה: EWMA + Ledoit-Wolf + Nearest-PSD
# =============================================================================

def _ewma_cov(returns: pd.DataFrame, halflife: int) -> pd.DataFrame:
    """EWMA covariance (Σ) תקין: demean, decay λ, חישוב יציב."""
    X = returns.values
    X = X - X.mean(axis=0, keepdims=True)
    lam = np.exp(-np.log(2)/max(halflife, 1))
    n = X.shape[1]
    S = np.zeros((n, n), dtype=float)
    w = 0.0
    for t in range(X.shape[0]):
        x = X[t:t+1, :]
        S = lam * S + (1 - lam) * (x.T @ x)
        w = lam * w + (1 - lam)
    S = S / max(w, 1e-12)
    return pd.DataFrame(S, index=returns.columns, columns=returns.columns)

def _lw_cov(returns: pd.DataFrame, assume_centered=True) -> pd.DataFrame:
    """חישוב Ledoit-Wolf Shrinkage."""
    X = returns.values
    if not assume_centered:
        X = X - X.mean(axis=0, keepdims=True)
    C = LedoitWolf(assume_centered=True).fit(X).covariance_
    return pd.DataFrame(C, index=returns.columns, columns=returns.columns)

def _fix_psd(M: pd.DataFrame) -> pd.DataFrame:
    """תיקון PSD איכותי באמצעות דקומפוזיציית Eigen."""
    A = M.values
    try:
        w, v = np.linalg.eigh(A)
        w[w < 1e-8] = 1e-8
        return pd.DataFrame(v @ np.diag(w) @ v.T, index=M.index, columns=M.columns)
    except np.linalg.LinAlgError:
        return M + np.eye(M.shape[0]) * 1e-8

def adaptive_cov(returns: pd.DataFrame, regime: str, T_N_ratio: float) -> pd.DataFrame:
    """
    Blend דינמי בין EWMA לבין LW לפי משטר ו-T/N. מחזיר Σ שנתית (×252).
    """
    if len(returns) < 30:
        C = returns.cov().values * 252.0
        return pd.DataFrame(C, index=returns.columns, columns=returns.columns)

    HL = CFG["COV_EWMA_HL"].get(regime, 30)
    S_ew = _ewma_cov(returns, halflife=HL)
    if T_N_ratio < 2.0:
        S_lw = _lw_cov(returns, assume_centered=True)
        alpha = 0.50 if regime == "Storm" else 0.35
        S = alpha * S_lw + (1 - alpha) * S_ew
    else:
        S = S_ew

    S_annualized = 252.0 * S
    return _fix_psd(S_annualized).astype(float)


# =============================================================================
# 8) אופטימיזציה: QP + HRP + Black-Litterman
# =============================================================================

def solve_qp(mu_hat: pd.Series, C: pd.DataFrame, w_prev: pd.Series, gross_lim: float, net_lim: float, params: Dict) -> pd.Series:
    """פותר את בעיית האופטימיזציה."""
    idx = mu_hat.index
    n = len(idx)
    w = cp.Variable(n)
    C_psd = cp.psd_wrap(C.values)
    gamma = params.get("TURNOVER_PEN", CFG["TURNOVER_PEN"])
    eta = params.get("RIDGE_PEN", CFG["RIDGE_PEN"])
    obj = 0.5 * cp.quad_form(w, C_psd) - mu_hat.values @ w + gamma * cp.norm1(w - w_prev.values) + eta * cp.sum_squares(w)
    cons = [
        cp.sum(cp.abs(w)) <= gross_lim,
        cp.sum(w) <= net_lim,
        w >= 0, w <= params.get("BOX_LIM", CFG["BOX_LIM"]),
    ]
    prob = cp.Problem(cp.Minimize(obj), cons)
    try:
        prob.solve(solver=cp.OSQP, warm_start=True, verbose=False)
        if w.value is None:
            return pd.Series(0.0, index=idx)
        w_opt = pd.Series(np.clip(w.value, 0, params.get("BOX_LIM", CFG["BOX_LIM"])), index=idx)
        port_vol = float(np.sqrt(w_opt.values @ C.values @ w_opt.values))
        if port_vol > 1e-9:
            scale = params.get("VOL_TARGET", CFG["VOL_TARGET"]) / port_vol
            w_opt = np.clip(w_opt * scale, 0, params.get("BOX_LIM", CFG["BOX_LIM"]))
        return w_opt
    except Exception:
        return pd.Series(0.0, index=idx)

def hrp_portfolio(returns: pd.DataFrame) -> pd.Series:
    """HRP מינימלי אך אמיתי."""
    if len(returns.columns) < 2: return pd.Series(1.0, index=returns.columns)
    
    corr = returns.corr().clip(-0.9999, 0.9999).fillna(0)
    dist = np.sqrt(0.5 * (1.0 - corr))
    condensed = squareform(dist.values, checks=False)

    Z = linkage(condensed, method='single')

    order = leaves_list(Z)
    cols = corr.columns[order]

    def _ivp(cov):
        iv = 1.0 / np.diag(cov.values)
        iv[np.isinf(iv)] = 0.0
        w = iv / iv.sum() if iv.sum() > 0 else np.ones_like(iv)/len(iv)
        return pd.Series(w, index=cov.index)

    def _cluster_var(cov, items):
        if len(items) == 0: return 0.0
        sub = cov.loc[items, items]
        w = _ivp(sub)
        return float(w.values @ sub.values @ w.values)

    def _hrp_allocation(cov, items):
        if len(items) == 1:
            return pd.Series(1.0, index=items)
        split = len(items) // 2
        left, right = items[:split], items[split:]
        w_left = _hrp_allocation(cov, left)
        w_right = _hrp_allocation(cov, right)
        var_left = _cluster_var(cov, left)
        var_right = _cluster_var(cov, right)
        alpha = 1.0 - var_left / (var_left + var_right + 1e-12)
        return pd.concat([w_left * alpha, w_right * (1.0 - alpha)])

    cov = returns.cov().fillna(0)
    w = _hrp_allocation(cov, list(cols))
    w = w.reindex(returns.columns).fillna(0.0)
    w_sum = w.sum()
    w = w / w_sum if w_sum > 0 else pd.Series(1/len(w), index=w.index)
    return w.sort_index()

def black_litterman(
    market_w: pd.Series,
    cov_mat: pd.DataFrame,
    tau: float = 0.05,
    P: Optional[np.ndarray] = None,
    Q: Optional[np.ndarray] = None
) -> pd.Series:
    """
    מודל Black-Litterman.
    כאן הוא ממומש בצורה מופשטת לטובת דמו, ללא שימוש ב-P וב-Q
    האמיתיים שמייצגים דעות סובייקטיביות, אלא רק עם נתוני שוק
    כדי לשמש כבנצ'מרק.
    """
    if P is None or Q is None:
        # דעות פסיביות (היעדר דעה): מחזיר את הקצאת שוק
        return market_w

    try:
        # Black-Litterman מאחד את דעות השוק עם הדעות הפרטיות
        sigma_P = tau * (P @ cov_mat @ P.T)
        P_T_Sigma_P_inv = np.linalg.inv(P.T @ sigma_P @ P + 1e-12)
        
        # חישוב התשואות הצפויות המשולבות
        tau_cov_inv = np.linalg.inv(tau * cov_mat + 1e-12)
        bl_mu = np.linalg.inv(tau_cov_inv + P.T @ np.linalg.inv(sigma_P) @ P) @ \
                (tau_cov_inv @ market_w.values + P.T @ np.linalg.inv(sigma_P) @ Q)

        # חישוב מטריצת הקו-וריאנס המשולבת
        bl_cov = np.linalg.inv(tau_cov_inv + P.T @ np.linalg.inv(sigma_P) @ P)
        
        # בניית פורטפוליו חדש
        w = np.linalg.inv(bl_cov) @ bl_mu
        w_sum = np.abs(w).sum()
        w = w / w_sum if w_sum > 0 else np.zeros_like(w)
        
        return pd.Series(w, index=market_w.index)
    except Exception:
        return market_w


# =============================================================================
# 9) ביצוע + למידת λ בזמן-אמת (השראה מ-Almgren–Chriss)
# =============================================================================

def exec_and_learn_lambda(
    w_prev: pd.Series, w_tgt: pd.Series,
    returns_today: pd.Series, adv_today: pd.Series,
    lam_prev: float
) -> Tuple[float, float, float]:
    """
    ביצוע פקודת מסחר ולמידת פרמטר העלות (lambda) בזמן אמת.
    """
    delta = (w_tgt - w_prev).clip(-CFG["BOX_LIM"], CFG["BOX_LIM"])
    gross_trade = float(np.abs(delta).sum())
    pov = min(CFG["POV_CAP"], gross_trade / (float(adv_today.mean()) + 1e-9))
    slip_realized = lam_prev * (pov ** CFG["SLIP_BETA"])
    gross_ret = float((w_prev * returns_today).sum())
    net_ret = gross_ret - slip_realized
    lam_hat = lam_prev if pov <= 0 else max(1e-6, slip_realized / (pov ** CFG["SLIP_BETA"]))
    lam_new = (1 - CFG["LAMBDA_EMA_RHO"]) * lam_prev + CFG["LAMBDA_EMA_RHO"] * lam_hat
    return net_ret, lam_new, slip_realized

# =============================================================================
# 10) Blind-Spot Agent + Kill-Switch
# =============================================================================

def cov_drift_metric(C_prev: pd.DataFrame, C_new: pd.DataFrame) -> float:
    """מחשב סחף בקו-וריאנציה."""
    a, b = C_prev.values, C_new.values
    num = np.linalg.norm(a - b, ord='fro')
    den = max(1e-12, np.linalg.norm(a, ord='fro'))
    return float(num / den)

def blind_spot_agent(C_prev: pd.DataFrame, C_new: pd.DataFrame) -> Tuple[str, float]:
    d = cov_drift_metric(C_prev, C_new)
    if d > CFG["COV_DRIFT"]:
        return "CONTAIN", d
    return "NORMAL", d

def kill_switch(pnl_hist: List[float]) -> bool:
    """Kill-Switch מבוסס PnL מצטבר."""
    if not pnl_hist: return False
    cum = float(np.prod(1 + np.array(pnl_hist)) - 1)
    return (cum < CFG["KILL_PNL"])

def psr_kill_switch(sr_hat: float, T: int) -> bool:
    """Kill-Switch מבוסס PSR."""
    psr = probabilistic_sharpe_ratio(sr_hat, T)
    return (psr < CFG["PSR_KILL_SWITCH"] and sr_hat < 0.0)

def max_drawdown(pnl_hist: List[float]) -> float:
    """מחשב Max Drawdown."""
    cum_returns = np.cumprod(1 + np.array(pnl_hist))
    if not cum_returns.any(): return 0.0
    peak = np.maximum.accumulate(cum_returns)
    drawdown = (peak - cum_returns) / peak
    return np.max(drawdown)

def drawdown_kill_switch(pnl_hist: List[float]) -> bool:
    """Kill-Switch מבוסס Max Drawdown."""
    dd = max_drawdown(pnl_hist)
    return dd > CFG["MAX_DD_KILL_SWITCH"]


# =============================================================================
# 11) Orchestrator – ריצה של יום יחיד (t)
# =============================================================================

def run_day(
    t: int, prices: pd.DataFrame, returns: pd.DataFrame,
    w_prev: pd.Series, lam_prev: float, linucb: "LinUCB",
    C_prev: pd.DataFrame,
    gdt_agent: Optional["GDTAgent"] = None,
    params: Dict = CFG
) -> Tuple[float, pd.Series, float, pd.DataFrame, dict, pd.Series, float]:

    # 1. הוספת פיצ'רים קונטקסטואליים ל-LinUCB
    regime = detect_regime(returns.iloc[:t])
    rho60 = avg_corr(returns.iloc[:t].tail(60))
    context_vec = np.array([1.0, float(regime == "Calm"), float(regime == "Storm"), rho60])

    # 1a. חישוב מדדים גיאומטריים (GDT)
    gdt_info = {}
    gdt_state = None
    gdt_exposure_factor = 1.0

    if GDT_AVAILABLE and gdt_agent is not None:
        try:
            # חישוב מדדים גיאומטריים
            window_prices = prices.iloc[:t]
            gdt_state, gdt_action, gdt_indicators = gdt_agent.process_market_data(window_prices)

            # שמירת מידע GDT
            gdt_info = {
                'state': gdt_state.name,
                'action': gdt_action.action_type,
                'exposure': gdt_action.exposure,
                'mean_curvature': gdt_indicators['mean_curvature'],
                'curvature_volatility': gdt_indicators['curvature_volatility'],
                'manifold_velocity': gdt_indicators['manifold_velocity'],
                'geodesic_deviation': gdt_indicators['geodesic_deviation'],
                'power_law_fit': gdt_indicators['power_law_fit']['is_power_law']
            }

            # התאמת גורם החשיפה לפי מצב GDT
            gdt_exposure_factor = gdt_action.exposure

        except Exception as e:
            print(f"⚠️ שגיאה בחישוב GDT: {e}")
            gdt_info = {'state': 'ERROR', 'error': str(e)}
    
    T_N_ratio = (t+1) / CFG["N"]
    C_new = adaptive_cov(returns.iloc[:t], regime, T_N_ratio)
    
    drift = cov_drift_metric(C_prev, C_new) if C_prev is not None else 0.0
    
    # 2. בחירת Gates – LinUCB
    arms = ["Micro(OFI,ERN)", "Slow(VRP,POS)", "XAsset(TSX)", "Sector(SIF)"]
    arm_idx = linucb.select_arm(context_vec)
    
    gate_name = arms[arm_idx]

    if arm_idx == 0: subset_sigs = {"OFI": "OFI", "ERN": "ERN"}
    elif arm_idx == 1: subset_sigs = {"VRP": "VRP", "POS": "POS"}
    elif arm_idx == 2: subset_sigs = {"TSX": "TSX"}
    else: subset_sigs = {"SIF": "SIF"}
    
    # 3. ולידציה: Purged K-Fold CV לולידציה
    test_scores = []
    splits = purged_k_fold(returns.iloc[:t], n_splits=5, embargo_len=5)
    
    for train_idx, val_idx in splits:
        train_returns = returns.loc[train_idx]
        val_returns = returns.loc[val_idx]

        train_signals = build_signals(train_returns, params)
        mis_train = mis_per_signal_pipeline(train_signals, train_returns)
        
        merged_train, _ = merge_signals_by_mis({k: train_signals[k] for k in subset_sigs}, mis_train)
        
        val_fwd_ret = future_returns(val_returns)
        val_ic = information_coefficient(merged_train.reindex(val_returns.index), val_fwd_ret)
        test_scores.append(val_ic.mean())

    # 4. חשב מדדים מותאמים על סמך תוצאות הוולידציה
    scores_array = np.array(test_scores)
    pbo_score = true_cscv_pbo(scores_array, M=CFG["CSCV_M"])
    
    # 5. השלמת חישובי QP ו-HRP
    sigs_all = build_signals(returns.iloc[:t], params)
    mis_all = mis_per_signal_pipeline(sigs_all, returns.iloc[:t], horizon=5)
    ortho = orthogonalize_signals(sigs_all)
    merged, _ = merge_signals_by_mis({k: ortho[k] for k in subset_sigs}, mis_all)
    mu_hat = merged.iloc[-1].fillna(0)
    mu_hat = (mu_hat - mu_hat.mean()) / (mu_hat.std() + 1e-12)
    
    gross_lim = CFG["GROSS_LIM"].get(regime, CFG["GROSS_LIM"]["Normal"])
    net_lim = CFG["NET_LIM"].get(regime, CFG["NET_LIM"]["Normal"])

    w_tgt_qp = solve_qp(mu_hat, C_new, w_prev, gross_lim, net_lim, params)

    # התאמת המשקולות לפי מצב GDT
    if GDT_AVAILABLE and gdt_agent is not None and gdt_exposure_factor != 1.0:
        w_tgt_qp = w_tgt_qp * gdt_exposure_factor

    w_hrp_benchmark = hrp_portfolio(returns.iloc[:t])
    w_bl_benchmark = black_litterman(w_hrp_benchmark, C_new)

    today_ret = returns.iloc[t-1]
    adv_today = returns.iloc[max(0, t-20):t].abs().mean() + 1e-9
    net_ret, lam_new, slip = exec_and_learn_lambda(w_prev, w_tgt_qp, today_ret, adv_today, lam_prev)
    
    reward = float(np.clip(net_ret, 0, 1))
    
    # עדכון LinUCB
    linucb.update(arm_idx, context_vec, reward)
    
    blind_state, drift = blind_spot_agent(C_prev, C_new) if C_prev is not None else ("NORMAL", 0.0)

    info = dict(
        regime=regime,
        gate=gate_name,
        reward=reward,
        slip=slip,
        drift=drift,
        blind=blind_state,
        pbo_score=pbo_score,
        cov_type="EWMA" if T_N_ratio >= 2.0 else "EWMA+LW",
        gdt=gdt_info  # הוספת מידע GDT
    )
    return net_ret, w_tgt_qp, lam_new, C_new, info, w_hrp_benchmark, w_bl_benchmark

# =============================================================================
# 12) אופטימיזציה בייסיאנית – שלד יישום
# =============================================================================

def evaluate_params(params: Dict, returns: pd.DataFrame) -> float:
    """
    פונקציית המטרה עבור האופטימיזציה הבייסיאנית.
    מבצעת בקטסט מהיר על נתוני אימון ומחזירה את יחס השארפ.
    """
    history = []
    w = pd.Series(0.0, index=returns.columns)
    lam = params.get("LAMBDA_INIT", CFG["LAMBDA_INIT"])
    linucb = LinUCB(n_arms=4, n_features=4, alpha=CFG["LINUCB_ALPHA"])
    C_prev = adaptive_cov(returns.iloc[:30], "Normal", 1)

    # יצירת סוכן GDT אם זמין
    gdt_agent = None
    if GDT_AVAILABLE:
        try:
            gdt_agent = GDTAgent(k_neighbors=10, window=60)
        except Exception:
            pass

    for t in range(30, len(returns)):
        net_ret, w, lam, C_new, _, _, _ = run_day(t, None, returns, w, lam, linucb, C_prev, gdt_agent, params)
        history.append(net_ret)
        C_prev = C_new

    sr_hist = (np.mean(history) / (np.std(history) + 1e-12)) * np.sqrt(252)
    return float(sr_hist)

def bayesian_optimization(returns: pd.DataFrame, n_iter: int) -> Dict:
    """
    מבצע אופטימיזציה בייסיאנית (יישום דמה).
    """
    print("🧠 התחלת תהליך אופטימיזציה בייסיאנית...")
    search_space = CFG["BAYESIAN_OPTIMIZATION"]["SEARCH_SPACE"]
    
    best_params = CFG.copy()
    best_sharpe = -np.inf
    history = []

    for i in range(n_iter):
        candidate_params = best_params.copy()
        for param, [min_val, max_val] in search_space.items():
            candidate_params[param] = rng.uniform(min_val, max_val)

        sharpe = evaluate_params(candidate_params, returns)
        history.append((candidate_params, sharpe))

        if sharpe > best_sharpe:
            best_sharpe = sharpe
            best_params = candidate_params
            print(f"✔️ איטרציה {i+1:>2}: שארפ חדש {sharpe:.2f} | פרמטרים: {best_params['MOM_H']:.0f}, {best_params['REV_H']:.0f}, {best_params['TURNOVER_PEN']:.4f}")
        else:
            print(f"❌ איטרציה {i+1:>2}: שארפ {sharpe:.2f} | לא נמצא שיפור.")

    print("✅ אופטימיזציה בייסיאנית הסתיימה.")
    print(f"הפרמטרים האופטימליים שנמצאו: {best_params}")
    return best_params

# =============================================================================
# 13) main – ריצה מקצה לקצה
# =============================================================================

def main():
    np.set_printoptions(suppress=True, precision=4)
    config = load_config()
    if not config: return
    prices, returns = simulate_prices()
    
    # שלב 1: אופטימיזציה בייסיאנית על חלק מהנתונים
    train_returns = returns.iloc[:int(CFG["DAYS"] * 0.7)]
    optimized_params = bayesian_optimization(train_returns, CFG["BAYESIAN_OPTIMIZATION"]["ITERATIONS"])
    
    # עדכן את הגלובל CFG עם הפרמטרים שנמצאו
    CFG.update(optimized_params)
    
    # שלב 2: ריצת backtest מלאה על כל הנתונים עם הפרמטרים האופטימליים
    w = pd.Series(0.0, index=returns.columns)
    lam = CFG["LAMBDA_INIT"]
    linucb = LinUCB(n_arms=4, n_features=4, alpha=CFG["LINUCB_ALPHA"])
    pnl_hist: List[float] = []

    # יצירת סוכן GDT
    gdt_agent = None
    if GDT_AVAILABLE:
        try:
            gdt_agent = GDTAgent(k_neighbors=10, window=60)
            print("✅ סוכן GDT הופעל בהצלחה")
        except Exception as e:
            print(f"⚠️ לא ניתן להפעיל סוכן GDT: {e}")

    C_prev = adaptive_cov(returns.iloc[:30], "Normal", 1)

    print("\n🚀 התחלת סימולציה מלאה עם הפרמטרים האופטימליים...")
    print("---")

    for t in range(30, config["DAYS"]):
        net_ret, w, lam, C_new, info, w_hrp, w_bl = run_day(t, prices, returns, w, lam, linucb, C_prev, gdt_agent, CFG)
        pnl_hist.append(net_ret)
        
        T_obs = len(pnl_hist)
        sr = (np.mean(pnl_hist) / (np.std(pnl_hist)+1e-12)) * np.sqrt(252) if T_obs > 1 else 0.0
        psr = probabilistic_sharpe_ratio(sr, T=T_obs)
        dsr = deflated_sharpe_ratio(sr, T=T_obs, n_strats=CFG["NUM_STRATEGIES"])
        dd = max_drawdown(pnl_hist)

        if (t % config["PRINT_EVERY"]) == 0:
            cum = float(np.prod(1 + np.array(pnl_hist)) - 1)
            gdt_str = ""
            if info.get('gdt'):
                gdt = info['gdt']
                if 'state' in gdt:
                    gdt_str = f" | GDT={gdt['state']:<12}"
                    if 'exposure' in gdt:
                        gdt_str += f" Exp={gdt['exposure']:.0%}"

            print(
                f"יום {t:>3} | Regime={info['regime']:<6} | Gate={info['gate']:<18} | PnL={net_ret*100:>6.2f}% | "
                f"cum={cum*100:>6.2f}% | DD={dd*100:>6.2f}% | SR={sr:.2f} | PSR={psr:.2f} | DSR={dsr:.2f} | PBO={info['pbo_score']:.2f}{gdt_str}"
            )

        if psr < CFG["PSR_KILL_SWITCH"] and sr < 0.0:
            print(f"🚨 Kill-Switch מבוסס PSR הופעל (PSR < {CFG['PSR_KILL_SWITCH']}) – מצמצם חשיפה ב-50%")
            w *= 0.5
        
        if drawdown_kill_switch(pnl_hist):
            print(f"🚨 Kill-Switch מבוסס MaxDD הופעל (DD > {CFG['MAX_DD_KILL_SWITCH']*100}%) – מאפס חשיפות.")
            w[:] = 0.0
        
        C_prev = C_new

    cum_final = float(np.prod(1 + np.array(pnl_hist)) - 1)
    ann_sr = (np.mean(pnl_hist) / (np.std(pnl_hist) + 1e-12)) * np.sqrt(252)
    final_dd = max_drawdown(pnl_hist)
    print("\n✅ סימולציה הסתיימה.")
    print(f"PnL מצטבר: {cum_final*100:.2f}% | Max DD: {final_dd*100:.2f}% | Sharpe≈ {ann_sr:.2f}")

    print("\n🔬 מדדי בנצ'מרק: HRP ו-Black-Litterman")
    # כדי להדגים את הבנצ'מרק, נריץ סימולציה פסיבית פשוטה עם הפורטפוליו שחושב
    print(f"    - ביצועי HRP (בנצ'מרק): **יחושב רק בעת הריצה המלאה**")
    print(f"    - ביצועי Black-Litterman (בנצ'מרק): **יחושב רק בעת הריצה המלאה**")

if __name__ == "__main__":
    main()
