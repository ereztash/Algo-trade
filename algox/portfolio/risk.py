"""
Risk Management Module
======================

Comprehensive risk management for AlgoX MVP including:
1. Pre-trade checks (position limits, exposure limits)
2. Circuit breakers (kill-switches)
3. Real-time risk monitoring
4. Drawdown tracking

Features:
---------
- Position size limits (per symbol, per sector)
- Gross/Net exposure limits
- VaR (Value at Risk) calculation
- Maximum drawdown tracking
- PSR-based kill-switch
- Daily loss limit

Example:
--------
    from algox.portfolio.risk import RiskManager

    risk_mgr = RiskManager(config)

    # Pre-trade check
    is_valid = risk_mgr.check_pre_trade(
        symbol="AAPL",
        proposed_weight=0.12,
        current_portfolio=portfolio,
        current_capital=10000
    )

    # Check circuit breakers
    should_halt = risk_mgr.check_circuit_breakers(
        pnl_history=pnl_hist,
        current_drawdown=0.15
    )
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
from scipy.stats import norm

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Risk management system for portfolio.

    Attributes:
        config: Configuration dictionary
        max_position_size: Maximum weight per position
        max_gross_exposure: Maximum gross exposure
        max_sector_exposure: Maximum exposure per sector
        max_drawdown_threshold: Circuit breaker threshold
        max_daily_loss: Maximum daily loss threshold
        psr_threshold: Minimum PSR threshold
    """

    def __init__(self, config: Dict):
        """Initialize risk manager."""
        risk_config = config.get("RISK", {})
        kill_config = config.get("KILL_SWITCHES", {})

        # Position limits
        self.max_position_size = risk_config.get("MAX_POSITION_SIZE", 0.15)
        self.max_gross_exposure = risk_config.get("MAX_GROSS_EXPOSURE", 0.50)
        self.max_concurrent_positions = risk_config.get("MAX_CONCURRENT_POSITIONS", 5)
        self.max_sector_exposure = risk_config.get("MAX_SECTOR_EXPOSURE", 0.30)

        # Strategy-specific limits
        self.biotech_max = risk_config.get("BIOTECH_MAX", 0.10)
        self.etf_max = risk_config.get("ETF_MAX", 0.15)

        # Circuit breakers
        self.max_drawdown_threshold = kill_config.get("MAX_DRAWDOWN", 0.20)
        self.min_sharpe_ratio = kill_config.get("MIN_SHARPE_RATIO", 0.5)
        self.max_daily_loss = kill_config.get("MAX_DAILY_LOSS", 0.03)
        self.psr_threshold = kill_config.get("PSR_THRESHOLD", 0.2)
        self.min_months_for_sr = kill_config.get("MIN_MONTHS_FOR_SR", 3)

        # Tracking
        self._drawdown_history = []
        self._pnl_history = []
        self._halt_status = False
        self._halt_reason = None

    def check_pre_trade(
        self,
        symbol: str,
        proposed_weight: float,
        current_portfolio: Dict[str, float],
        sector: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Check if proposed trade passes pre-trade risk checks.

        Args:
            symbol: Symbol to trade
            proposed_weight: Proposed weight for symbol
            current_portfolio: Current portfolio weights
            sector: Sector classification (optional)

        Returns:
            (is_valid, reason)
        """
        # Check 1: Position size limit
        if abs(proposed_weight) > self.max_position_size:
            return False, f"Position size {abs(proposed_weight):.2%} exceeds limit {self.max_position_size:.2%}"

        # Check 2: Strategy-specific limits (ETF vs. biotech)
        if symbol in ["REMX", "URNM", "QTUM", "SPY", "QQQ", "IWM", "DIA"]:
            # ETF
            if abs(proposed_weight) > self.etf_max:
                return False, f"ETF position {abs(proposed_weight):.2%} exceeds limit {self.etf_max:.2%}"
        else:
            # Assume biotech
            if abs(proposed_weight) > self.biotech_max:
                return False, f"Biotech position {abs(proposed_weight):.2%} exceeds limit {self.biotech_max:.2%}"

        # Check 3: Gross exposure limit
        new_portfolio = current_portfolio.copy()
        new_portfolio[symbol] = proposed_weight

        gross_exposure = sum(abs(w) for w in new_portfolio.values())

        if gross_exposure > self.max_gross_exposure:
            return False, f"Gross exposure {gross_exposure:.2%} exceeds limit {self.max_gross_exposure:.2%}"

        # Check 4: Number of concurrent positions
        num_positions = sum(1 for w in new_portfolio.values() if abs(w) > 0.001)

        if num_positions > self.max_concurrent_positions:
            return False, f"Number of positions {num_positions} exceeds limit {self.max_concurrent_positions}"

        # Check 5: Sector exposure (if provided)
        if sector is not None:
            sector_exposure = sum(
                abs(w) for s, w in new_portfolio.items()
                if self._get_sector(s) == sector
            )

            if sector_exposure > self.max_sector_exposure:
                return False, f"Sector {sector} exposure {sector_exposure:.2%} exceeds limit {self.max_sector_exposure:.2%}"

        # All checks passed
        return True, "OK"

    def _get_sector(self, symbol: str) -> str:
        """
        Get sector for symbol (simplified for MVP).

        Args:
            symbol: Stock symbol

        Returns:
            Sector name
        """
        # Simplified sector mapping
        etf_map = {
            "REMX": "Materials",
            "URNM": "Energy",
            "QTUM": "Technology",
            "SPY": "Broad Market",
            "QQQ": "Technology",
            "IWM": "Small Cap",
            "DIA": "Large Cap"
        }

        return etf_map.get(symbol, "Biotech")

    def check_circuit_breakers(
        self,
        pnl_history: List[float],
        current_drawdown: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if any circuit breakers should trigger.

        Args:
            pnl_history: List of daily PnL (as fractions)
            current_drawdown: Current drawdown (optional, will calculate if None)

        Returns:
            (should_halt, reason)
        """
        if not pnl_history:
            return False, None

        # Check 1: Maximum drawdown
        if current_drawdown is None:
            current_drawdown = self.calculate_drawdown(pnl_history)

        if current_drawdown > self.max_drawdown_threshold:
            reason = f"Drawdown {current_drawdown:.2%} exceeds threshold {self.max_drawdown_threshold:.2%}"
            logger.critical(f"CIRCUIT BREAKER: {reason}")
            self._halt_status = True
            self._halt_reason = reason
            return True, reason

        # Check 2: Daily loss limit
        if len(pnl_history) > 0:
            daily_loss = pnl_history[-1]

            if daily_loss < -self.max_daily_loss:
                reason = f"Daily loss {daily_loss:.2%} exceeds limit {self.max_daily_loss:.2%}"
                logger.warning(f"CIRCUIT BREAKER (Daily): {reason}")
                # Don't halt permanently, just for today
                return True, reason

        # Check 3: Sharpe ratio (if enough history)
        min_days = self.min_months_for_sr * 21  # ~21 trading days per month

        if len(pnl_history) >= min_days:
            sharpe = self.calculate_sharpe_ratio(pnl_history)

            if sharpe < self.min_sharpe_ratio:
                reason = f"Sharpe ratio {sharpe:.2f} below threshold {self.min_sharpe_ratio:.2f}"
                logger.critical(f"CIRCUIT BREAKER: {reason}")
                self._halt_status = True
                self._halt_reason = reason
                return True, reason

        # Check 4: PSR (if enough history)
        if len(pnl_history) >= min_days:
            psr = self.calculate_psr(pnl_history)

            if psr < self.psr_threshold:
                reason = f"PSR {psr:.2f} below threshold {self.psr_threshold:.2f}"
                logger.critical(f"CIRCUIT BREAKER: {reason}")
                self._halt_status = True
                self._halt_reason = reason
                return True, reason

        return False, None

    def calculate_drawdown(self, pnl_history: List[float]) -> float:
        """
        Calculate maximum drawdown from PnL history.

        Args:
            pnl_history: List of daily PnL (as fractions)

        Returns:
            Maximum drawdown
        """
        if not pnl_history:
            return 0.0

        # Calculate cumulative returns
        cum_returns = np.cumprod(1 + np.array(pnl_history))

        # Calculate running maximum
        running_max = np.maximum.accumulate(cum_returns)

        # Calculate drawdown
        drawdown = (running_max - cum_returns) / running_max

        return float(np.max(drawdown))

    def calculate_sharpe_ratio(
        self,
        pnl_history: List[float],
        risk_free_rate: float = 0.0
    ) -> float:
        """
        Calculate Sharpe ratio.

        Args:
            pnl_history: List of daily PnL (as fractions)
            risk_free_rate: Risk-free rate (annualized)

        Returns:
            Sharpe ratio (annualized)
        """
        if len(pnl_history) < 2:
            return 0.0

        returns = np.array(pnl_history)
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return < 1e-9:
            return 0.0

        # Annualize (assuming 252 trading days)
        sharpe = (mean_return - risk_free_rate / 252) / std_return * np.sqrt(252)

        return float(sharpe)

    def calculate_psr(
        self,
        pnl_history: List[float],
        benchmark_sharpe: float = 0.0
    ) -> float:
        """
        Calculate Probabilistic Sharpe Ratio.

        PSR = Φ((SR - SR_bench) * √(T-1) / √(1 - γ₃·SR + (γ₄-1)/4 · SR²))

        where:
          - Φ: CDF of standard normal
          - SR: Observed Sharpe ratio
          - SR_bench: Benchmark Sharpe ratio
          - T: Number of observations
          - γ₃: Skewness
          - γ₄: Kurtosis

        Args:
            pnl_history: List of daily PnL (as fractions)
            benchmark_sharpe: Benchmark Sharpe ratio

        Returns:
            PSR value in [0, 1]
        """
        if len(pnl_history) < 10:
            return 0.5

        returns = np.array(pnl_history)
        T = len(returns)

        # Calculate Sharpe ratio
        sr = self.calculate_sharpe_ratio(pnl_history)

        # Calculate skewness and kurtosis
        from scipy.stats import skew, kurtosis

        skewness = skew(returns)
        kurt = kurtosis(returns, fisher=False)  # Pearson kurtosis (not excess)

        # PSR formula
        try:
            denominator = np.sqrt(1 - skewness * sr + (kurt - 1) / 4 * sr ** 2)
            z_score = (sr - benchmark_sharpe) * np.sqrt(T - 1) / denominator
            psr = norm.cdf(z_score)
        except (ValueError, ZeroDivisionError):
            psr = 0.5

        return float(np.clip(psr, 0, 1))

    def calculate_var(
        self,
        returns: np.ndarray,
        confidence: float = 0.95,
        method: str = "historical"
    ) -> float:
        """
        Calculate Value at Risk (VaR).

        Args:
            returns: Array of returns
            confidence: Confidence level (e.g., 0.95 for 95%)
            method: Method ("historical", "parametric", "cornish_fisher")

        Returns:
            VaR value (positive = loss)
        """
        if len(returns) < 10:
            return 0.0

        if method == "historical":
            # Historical VaR
            var = -np.percentile(returns, (1 - confidence) * 100)

        elif method == "parametric":
            # Parametric VaR (assumes normal distribution)
            mu = np.mean(returns)
            sigma = np.std(returns, ddof=1)
            z = norm.ppf(1 - confidence)
            var = -(mu + z * sigma)

        elif method == "cornish_fisher":
            # Cornish-Fisher VaR (accounts for skew and kurtosis)
            from scipy.stats import skew, kurtosis

            mu = np.mean(returns)
            sigma = np.std(returns, ddof=1)
            s = skew(returns)
            k = kurtosis(returns, fisher=True)  # Excess kurtosis

            z = norm.ppf(1 - confidence)

            # Cornish-Fisher adjustment
            z_cf = z + (z ** 2 - 1) * s / 6 + (z ** 3 - 3 * z) * k / 24 - (2 * z ** 3 - 5 * z) * s ** 2 / 36

            var = -(mu + z_cf * sigma)

        else:
            raise ValueError(f"Unknown VaR method: {method}")

        return float(max(var, 0))

    def calculate_cvar(
        self,
        returns: np.ndarray,
        confidence: float = 0.95
    ) -> float:
        """
        Calculate Conditional Value at Risk (CVaR / Expected Shortfall).

        CVaR is the expected loss given that VaR is exceeded.

        Args:
            returns: Array of returns
            confidence: Confidence level

        Returns:
            CVaR value (positive = loss)
        """
        if len(returns) < 10:
            return 0.0

        # Calculate VaR threshold
        var_threshold = -np.percentile(returns, (1 - confidence) * 100)

        # CVaR = average of returns worse than VaR
        tail_losses = returns[returns <= -var_threshold]

        if len(tail_losses) == 0:
            return var_threshold

        cvar = -np.mean(tail_losses)

        return float(cvar)

    def get_risk_report(
        self,
        portfolio: Dict[str, float],
        returns_history: pd.DataFrame,
        pnl_history: List[float]
    ) -> Dict:
        """
        Generate comprehensive risk report.

        Args:
            portfolio: Current portfolio weights
            returns_history: Historical returns DataFrame
            pnl_history: PnL history

        Returns:
            Dictionary with risk metrics
        """
        # Portfolio metrics
        gross_exposure = sum(abs(w) for w in portfolio.values())
        net_exposure = sum(portfolio.values())
        num_positions = sum(1 for w in portfolio.values() if abs(w) > 0.001)

        # Performance metrics
        sharpe = self.calculate_sharpe_ratio(pnl_history) if pnl_history else 0.0
        drawdown = self.calculate_drawdown(pnl_history) if pnl_history else 0.0
        psr = self.calculate_psr(pnl_history) if len(pnl_history) >= 10 else 0.5

        # VaR metrics
        if len(pnl_history) >= 10:
            returns_array = np.array(pnl_history)
            var_95 = self.calculate_var(returns_array, 0.95, "historical")
            cvar_95 = self.calculate_cvar(returns_array, 0.95)
        else:
            var_95 = 0.0
            cvar_95 = 0.0

        # Circuit breaker status
        should_halt, halt_reason = self.check_circuit_breakers(pnl_history)

        report = {
            "timestamp": datetime.now().isoformat(),
            "portfolio": {
                "gross_exposure": gross_exposure,
                "net_exposure": net_exposure,
                "num_positions": num_positions,
                "largest_position": max(abs(w) for w in portfolio.values()) if portfolio else 0.0
            },
            "performance": {
                "sharpe_ratio": sharpe,
                "max_drawdown": drawdown,
                "psr": psr,
                "total_return": float(np.prod(1 + np.array(pnl_history)) - 1) if pnl_history else 0.0
            },
            "risk": {
                "var_95": var_95,
                "cvar_95": cvar_95
            },
            "circuit_breakers": {
                "should_halt": should_halt,
                "halt_reason": halt_reason,
                "is_halted": self._halt_status
            }
        }

        return report

    def reset_halt(self):
        """Reset halt status (for manual override)."""
        self._halt_status = False
        self._halt_reason = None
        logger.info("Risk manager halt status reset")

    @property
    def is_halted(self) -> bool:
        """Check if trading is halted."""
        return self._halt_status
