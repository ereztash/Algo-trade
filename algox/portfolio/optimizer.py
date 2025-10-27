"""
Portfolio Optimizer
===================

Quadratic Programming (QP) optimization for portfolio construction.
Adapted from Algo-trade with enhancements for AlgoX MVP.

Features:
---------
1. Mean-variance optimization with transaction costs
2. Regime-based constraints
3. Ricci curvature exposure adjustment
4. Box constraints (position limits)
5. Gross/Net exposure limits

Objective Function:
------------------
minimize: 0.5 * w^T * Σ * w - μ^T * w + γ * ||w - w_prev||_1 + η * ||w||_2^2

where:
  - Σ: Covariance matrix (annualized)
  - μ: Expected returns (signal strengths)
  - w: Portfolio weights
  - w_prev: Previous weights (for turnover penalty)
  - γ: Turnover penalty
  - η: Ridge penalty (regularization)

Constraints:
-----------
1. Box: 0 ≤ w_i ≤ BOX_LIM (e.g., 15% per position)
2. Gross: Σ|w_i| ≤ GROSS_LIM (e.g., 50% total exposure)
3. Net: Σw_i ≤ NET_LIM (e.g., 50% long bias)
4. Long-only: w_i ≥ 0

Example:
--------
    from algox.portfolio.optimizer import PortfolioOptimizer

    optimizer = PortfolioOptimizer(config)
    weights = optimizer.optimize(
        signals={"REMX": 0.5, "URNM": 0.7, "QTUM": 0.3},
        covariance=cov_matrix,
        current_weights=current_weights,
        regime="Normal",
        ricci_adjustment=1.0
    )
"""

import pandas as pd
import numpy as np
import cvxpy as cp
from typing import Dict, Optional
import logging
from scipy.linalg import sqrtm

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    Portfolio optimizer using Quadratic Programming.

    Attributes:
        config: Configuration dictionary
        vol_target: Target portfolio volatility (annualized)
        turnover_penalty: Penalty for portfolio turnover
        ridge_penalty: Ridge regularization penalty
        long_only: Whether to enforce long-only constraint
    """

    def __init__(self, config: Dict):
        """Initialize portfolio optimizer."""
        opt_config = config.get("OPTIMIZATION", {})
        risk_config = config.get("RISK", {})

        self.vol_target = risk_config.get("VOL_TARGET", 0.12)
        self.turnover_penalty = opt_config.get("TURNOVER_PENALTY", 0.001)
        self.ridge_penalty = opt_config.get("RIDGE_PENALTY", 0.0001)
        self.long_only = opt_config.get("LONG_ONLY", True)

        # Risk limits
        self.max_position_size = risk_config.get("MAX_POSITION_SIZE", 0.15)
        self.max_gross_exposure = risk_config.get("MAX_GROSS_EXPOSURE", 0.50)
        self.max_net_exposure = risk_config.get("MAX_GROSS_EXPOSURE", 0.50)

        # Regime-based adjustments
        self.regime_adjustments = config.get("REGIME", {}).get("ADJUSTMENTS", {})

        # Covariance estimation
        self.cov_method = opt_config.get("COV_METHOD", "ledoit_wolf")
        self.cov_lookback = opt_config.get("COV_LOOKBACK", 252)

    def _adjust_limits_for_regime(self, regime: str) -> Dict[str, float]:
        """
        Adjust position limits based on market regime.

        Args:
            regime: Market regime ("Calm", "Normal", "Storm")

        Returns:
            Dictionary with adjusted limits
        """
        adjustments = self.regime_adjustments.get(regime, {})

        return {
            "gross_limit": adjustments.get("GROSS_LIMIT", self.max_gross_exposure),
            "position_size": adjustments.get("POSITION_SIZE", self.max_position_size)
        }

    def _prepare_covariance(
        self,
        covariance: pd.DataFrame,
        symbols: list
    ) -> pd.DataFrame:
        """
        Prepare covariance matrix for optimization.

        Args:
            covariance: Covariance matrix
            symbols: List of symbols to include

        Returns:
            Aligned covariance matrix
        """
        # Ensure covariance has all symbols
        missing_symbols = set(symbols) - set(covariance.index)

        if missing_symbols:
            logger.warning(f"Missing covariance for symbols: {missing_symbols}")

            # Add missing symbols with default variance
            for symbol in missing_symbols:
                covariance.loc[symbol, symbol] = 0.02 ** 2 * 252  # 2% daily vol annualized

        # Reindex to match symbols
        cov_aligned = covariance.reindex(index=symbols, columns=symbols, fill_value=0.0)

        # Ensure PSD (positive semi-definite)
        cov_aligned = self._ensure_psd(cov_aligned)

        return cov_aligned

    def _ensure_psd(self, cov: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure covariance matrix is positive semi-definite.

        Args:
            cov: Covariance matrix

        Returns:
            PSD covariance matrix
        """
        try:
            # Eigenvalue decomposition
            eigenvalues, eigenvectors = np.linalg.eigh(cov.values)

            # Clip negative eigenvalues
            eigenvalues = np.maximum(eigenvalues, 1e-8)

            # Reconstruct
            cov_psd = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T

            return pd.DataFrame(cov_psd, index=cov.index, columns=cov.columns)

        except np.linalg.LinAlgError as e:
            logger.error(f"Error ensuring PSD: {e}")
            return cov + np.eye(len(cov)) * 1e-6

    def optimize(
        self,
        signals: Dict[str, float],
        covariance: pd.DataFrame,
        current_weights: Optional[Dict[str, float]] = None,
        regime: str = "Normal",
        ricci_adjustment: float = 1.0
    ) -> pd.Series:
        """
        Optimize portfolio weights.

        Args:
            signals: Dictionary of {symbol: signal_strength} in [-1, 1]
            covariance: Covariance matrix (annualized)
            current_weights: Current portfolio weights (for turnover penalty)
            regime: Market regime ("Calm", "Normal", "Storm")
            ricci_adjustment: Ricci curvature adjustment factor (0.5, 1.0, or 1.2)

        Returns:
            Optimized weights as pd.Series
        """
        # Filter out zero signals
        signals = {k: v for k, v in signals.items() if abs(v) > 1e-6}

        if not signals:
            logger.warning("No non-zero signals provided")
            return pd.Series(dtype=float)

        symbols = list(signals.keys())
        n = len(symbols)

        # Prepare inputs
        mu = pd.Series(signals)
        cov = self._prepare_covariance(covariance, symbols)

        if current_weights is None:
            w_prev = pd.Series(0.0, index=symbols)
        else:
            w_prev = pd.Series(current_weights).reindex(symbols, fill_value=0.0)

        # Adjust limits for regime
        limits = self._adjust_limits_for_regime(regime)
        gross_limit = limits["gross_limit"] * ricci_adjustment
        box_limit = limits["position_size"] * ricci_adjustment

        logger.info(f"Optimizing portfolio: regime={regime}, ricci_adj={ricci_adjustment:.2f}, "
                   f"gross_limit={gross_limit:.2%}, box_limit={box_limit:.2%}")

        # Define optimization variables
        w = cp.Variable(n)

        # Objective function
        # minimize: 0.5 * w^T * Σ * w - μ^T * w + γ * ||w - w_prev||_1 + η * ||w||_2^2
        risk_term = 0.5 * cp.quad_form(w, cov.values)
        return_term = -mu.values @ w
        turnover_term = self.turnover_penalty * cp.norm1(w - w_prev.values)
        regularization_term = self.ridge_penalty * cp.sum_squares(w)

        objective = cp.Minimize(
            risk_term + return_term + turnover_term + regularization_term
        )

        # Constraints
        constraints = [
            cp.sum(cp.abs(w)) <= gross_limit,  # Gross exposure
            cp.sum(w) <= self.max_net_exposure,  # Net exposure
            w >= 0,  # Long-only
            w <= box_limit  # Position size limit
        ]

        # Solve
        problem = cp.Problem(objective, constraints)

        try:
            problem.solve(solver=cp.OSQP, warm_start=True, verbose=False)

            if problem.status not in ["optimal", "optimal_inaccurate"]:
                logger.warning(f"Optimization failed with status: {problem.status}")
                return pd.Series(0.0, index=symbols)

            # Extract weights
            weights = pd.Series(w.value, index=symbols)

            # Volatility scaling
            weights = self._scale_to_vol_target(weights, cov)

            # Final clipping
            weights = weights.clip(0, box_limit)

            # Log results
            portfolio_vol = np.sqrt(weights.values @ cov.values @ weights.values)
            gross_exposure = weights.abs().sum()

            logger.info(f"Optimization successful: vol={portfolio_vol:.2%}, "
                       f"gross={gross_exposure:.2%}, positions={len(weights[weights > 0.001])}")

            return weights

        except Exception as e:
            logger.error(f"Optimization error: {e}")
            return pd.Series(0.0, index=symbols)

    def _scale_to_vol_target(
        self,
        weights: pd.Series,
        covariance: pd.DataFrame
    ) -> pd.Series:
        """
        Scale portfolio weights to achieve target volatility.

        Args:
            weights: Portfolio weights
            covariance: Covariance matrix

        Returns:
            Scaled weights
        """
        # Calculate current portfolio volatility
        portfolio_var = weights.values @ covariance.values @ weights.values
        portfolio_vol = np.sqrt(max(portfolio_var, 0))

        if portfolio_vol < 1e-9:
            return weights

        # Scale to target
        scale = self.vol_target / portfolio_vol

        # Don't over-leverage
        scale = min(scale, 2.0)

        return weights * scale

    def estimate_covariance(
        self,
        returns: pd.DataFrame,
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Estimate covariance matrix from returns.

        Args:
            returns: Returns DataFrame
            method: Estimation method ("sample", "ledoit_wolf", "ewma")

        Returns:
            Covariance matrix (annualized)
        """
        if method is None:
            method = self.cov_method

        if len(returns) < 30:
            logger.warning("Insufficient data for covariance estimation")
            return returns.cov() * 252

        if method == "sample":
            cov = returns.cov() * 252

        elif method == "ledoit_wolf":
            from sklearn.covariance import LedoitWolf

            lw = LedoitWolf()
            cov_array = lw.fit(returns.fillna(0)).covariance_
            cov = pd.DataFrame(cov_array, index=returns.columns, columns=returns.columns) * 252

        elif method == "ewma":
            cov = self._ewma_covariance(returns, halflife=60) * 252

        else:
            raise ValueError(f"Unknown covariance method: {method}")

        # Ensure PSD
        cov = self._ensure_psd(cov)

        return cov

    def _ewma_covariance(self, returns: pd.DataFrame, halflife: int = 60) -> pd.DataFrame:
        """
        Calculate EWMA covariance.

        Args:
            returns: Returns DataFrame
            halflife: EWMA halflife in days

        Returns:
            EWMA covariance matrix (daily)
        """
        # Demean
        X = returns.values - returns.mean().values

        # EWMA parameters
        lam = np.exp(-np.log(2) / halflife)
        n_assets = X.shape[1]

        # Initialize
        S = np.zeros((n_assets, n_assets))
        w = 0.0

        # Iterate
        for t in range(X.shape[0]):
            x_t = X[t:t+1, :].T  # Column vector

            S = lam * S + (1 - lam) * (x_t @ x_t.T)
            w = lam * w + (1 - lam)

        # Normalize
        S = S / max(w, 1e-12)

        return pd.DataFrame(S, index=returns.columns, columns=returns.columns)

    def backtest_optimizer(
        self,
        price_data: Dict[str, pd.DataFrame],
        signals_history: pd.DataFrame,
        rebalance_freq: int = 5
    ) -> pd.DataFrame:
        """
        Backtest the optimizer.

        Args:
            price_data: Historical price data
            signals_history: Historical signals DataFrame
            rebalance_freq: Rebalance frequency (days)

        Returns:
            DataFrame with portfolio weights over time
        """
        results = []
        current_weights = {}

        # Get date range from first symbol
        first_symbol = list(price_data.keys())[0]
        dates = price_data[first_symbol].index

        for i in range(self.cov_lookback, len(dates), rebalance_freq):
            current_date = dates[i]

            # Get signals for current date
            if current_date not in signals_history.index:
                continue

            signals = signals_history.loc[current_date].to_dict()

            # Calculate returns for covariance
            returns_window = {}
            for symbol, df in price_data.items():
                if symbol in signals:
                    returns_window[symbol] = df.loc[:current_date, 'close'].pct_change().iloc[-self.cov_lookback:]

            returns_df = pd.DataFrame(returns_window).dropna()

            # Estimate covariance
            cov = self.estimate_covariance(returns_df)

            # Optimize
            weights = self.optimize(
                signals=signals,
                covariance=cov,
                current_weights=current_weights
            )

            # Store results
            result = {"date": current_date}
            result.update(weights.to_dict())
            results.append(result)

            # Update current weights
            current_weights = weights.to_dict()

        return pd.DataFrame(results)
