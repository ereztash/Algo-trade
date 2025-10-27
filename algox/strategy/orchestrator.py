"""
Strategy Orchestrator
=====================

Main orchestrator that combines all 3 signal strategies:
1. Structural Arbitrage (REMX → URNM → QTUM)
2. Ricci Curvature (Early Warning System)
3. Event-Driven (FDA approvals)

Features:
---------
- LinUCB for dynamic strategy selection
- Regime detection for adaptive risk management
- Signal aggregation and normalization
- Integration with portfolio optimizer and risk manager

Flow:
-----
1. Detect market regime (Calm/Normal/Storm)
2. Calculate Ricci curvature → exposure adjustment
3. Generate signals from all 3 strategies
4. Use LinUCB to select best strategy mix
5. Aggregate signals
6. Pass to portfolio optimizer
7. Check risk constraints
8. Execute trades

Example:
--------
    from algox.strategy.orchestrator import StrategyOrchestrator

    orchestrator = StrategyOrchestrator(config)

    # Run one step
    result = await orchestrator.run_step(
        current_date=datetime.now(),
        price_data=price_data,
        current_portfolio=portfolio
    )
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging
import asyncio

from algox.signals.structural import StructuralArbitrageSignal
from algox.signals.ricci_curvature import RicciCurvatureEWS
from algox.signals.event_driven import EventDrivenSignal
from algox.portfolio.optimizer import PortfolioOptimizer
from algox.portfolio.risk import RiskManager

logger = logging.getLogger(__name__)


class LinUCB:
    """
    LinUCB (Linear Upper Confidence Bound) for contextual bandit.

    Used to dynamically select which strategy to weight more heavily
    based on context (regime, volatility, etc.) and past performance.

    Attributes:
        n_arms: Number of strategies (arms)
        n_features: Number of context features
        alpha: Exploration parameter
    """

    def __init__(self, n_arms: int, n_features: int, alpha: float = 0.1):
        """Initialize LinUCB."""
        self.n_arms = n_arms
        self.n_features = n_features
        self.alpha = alpha

        # Initialize parameters for each arm
        self.A = [np.identity(n_features) for _ in range(n_arms)]  # Feature covariance
        self.b = [np.zeros(n_features) for _ in range(n_arms)]  # Feature-reward correlation

    def select_arm(self, context: np.ndarray) -> int:
        """
        Select best arm given context using UCB.

        Args:
            context: Context vector (n_features,)

        Returns:
            Selected arm index
        """
        ucb_values = []

        for i in range(self.n_arms):
            # Solve for theta: A_i * theta_i = b_i
            A_inv = np.linalg.inv(self.A[i])
            theta = A_inv @ self.b[i]

            # UCB = expected reward + exploration bonus
            expected_reward = context @ theta
            exploration_bonus = self.alpha * np.sqrt(context @ A_inv @ context)

            ucb = expected_reward + exploration_bonus
            ucb_values.append(ucb)

        # Select arm with highest UCB
        return int(np.argmax(ucb_values))

    def update(self, arm: int, context: np.ndarray, reward: float):
        """
        Update arm parameters after observing reward.

        Args:
            arm: Arm index
            context: Context vector
            reward: Observed reward
        """
        # Update covariance: A_i = A_i + x * x^T
        self.A[arm] += np.outer(context, context)

        # Update correlation: b_i = b_i + reward * x
        self.b[arm] += reward * context


class StrategyOrchestrator:
    """
    Main orchestrator for AlgoX MVP.

    Coordinates all strategies, portfolio optimization, and risk management.

    Attributes:
        config: Configuration dictionary
        structural_signal: Structural arbitrage signal generator
        ricci_ews: Ricci curvature early warning system
        event_signal: Event-driven signal generator
        optimizer: Portfolio optimizer
        risk_manager: Risk manager
        linucb: LinUCB bandit for strategy selection
    """

    def __init__(self, config: Dict):
        """Initialize strategy orchestrator."""
        self.config = config

        # Initialize signal generators
        self.structural_signal = StructuralArbitrageSignal(config)
        self.ricci_ews = RicciCurvatureEWS(config)
        self.event_signal = EventDrivenSignal(config)

        # Initialize portfolio components
        self.optimizer = PortfolioOptimizer(config)
        self.risk_manager = RiskManager(config)

        # Initialize LinUCB (3 arms for 3 strategies)
        bandit_config = config.get("BANDIT", {})
        n_arms = bandit_config.get("N_ARMS", 3)
        n_features = len(bandit_config.get("CONTEXT_FEATURES", ["regime", "volatility", "correlation", "ricci_curvature"]))
        alpha = bandit_config.get("ALPHA", 0.1)

        self.linucb = LinUCB(n_arms=n_arms, n_features=n_features + 1, alpha=alpha)  # +1 for bias

        # Tracking
        self._performance_history = []
        self._portfolio_history = []

    def detect_regime(self, returns: pd.DataFrame, lookback: int = 60) -> str:
        """
        Detect market regime based on volatility and correlation.

        Args:
            returns: Returns DataFrame
            lookback: Lookback window

        Returns:
            Regime: "Calm", "Normal", or "Storm"
        """
        if len(returns) < lookback:
            return "Normal"

        recent_returns = returns.tail(lookback)

        # Calculate annualized volatility
        vol = recent_returns.std().mean() * np.sqrt(252)

        # Calculate average correlation
        corr_matrix = recent_returns.corr()
        n = len(corr_matrix)
        avg_corr = (corr_matrix.sum().sum() - n) / (n * (n - 1))

        # Regime thresholds
        regime_config = self.config.get("REGIME", {}).get("THRESHOLDS", {})
        calm_threshold = regime_config.get("CALM", 0.15)
        storm_threshold = regime_config.get("STORM", 0.35)

        if vol < calm_threshold and avg_corr < 0.20:
            regime = "Calm"
        elif vol > storm_threshold or avg_corr > 0.60:
            regime = "Storm"
        else:
            regime = "Normal"

        logger.info(f"Regime detected: {regime} (vol={vol:.2%}, corr={avg_corr:.2f})")

        return regime

    def build_context_vector(
        self,
        regime: str,
        returns: pd.DataFrame,
        ricci_stats: Dict
    ) -> np.ndarray:
        """
        Build context vector for LinUCB.

        Args:
            regime: Market regime
            returns: Returns DataFrame
            ricci_stats: Ricci curvature statistics

        Returns:
            Context vector [bias, regime_calm, regime_storm, volatility, correlation, ricci_curvature]
        """
        # Bias
        context = [1.0]

        # Regime (one-hot encoding)
        context.append(1.0 if regime == "Calm" else 0.0)
        context.append(1.0 if regime == "Storm" else 0.0)

        # Volatility (normalized)
        if len(returns) >= 20:
            vol = returns.tail(20).std().mean() * np.sqrt(252)
            vol_normalized = min(vol / 0.5, 1.0)  # Normalize to [0, 1]
        else:
            vol_normalized = 0.5

        context.append(vol_normalized)

        # Correlation (normalized)
        if len(returns) >= 20:
            corr_matrix = returns.tail(20).corr()
            n = len(corr_matrix)
            avg_corr = (corr_matrix.sum().sum() - n) / (n * (n - 1)) if n > 1 else 0.0
            corr_normalized = max(min(avg_corr, 1.0), -1.0)
        else:
            corr_normalized = 0.0

        context.append(corr_normalized)

        # Ricci curvature (normalized)
        ricci_mean = ricci_stats.get("mean", 0.0)
        ricci_normalized = max(min(ricci_mean, 1.0), -1.0)

        context.append(ricci_normalized)

        return np.array(context)

    async def generate_all_signals(
        self,
        current_date: datetime,
        price_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Dict[str, float]]:
        """
        Generate signals from all 3 strategies.

        Args:
            current_date: Current date
            price_data: Price data dictionary

        Returns:
            Dictionary of {strategy_name: {symbol: signal_strength}}
        """
        signals = {}

        # 1. Structural Arbitrage
        try:
            structural_signals = self.structural_signal.generate(price_data)
            signals["structural"] = structural_signals
            logger.info(f"Structural signals: {structural_signals}")
        except Exception as e:
            logger.error(f"Error generating structural signals: {e}")
            signals["structural"] = {}

        # 2. Event-Driven (FDA)
        try:
            event_signals_raw = self.event_signal.generate(current_date, price_data)

            # Extract signal values
            event_signals = {symbol: data["signal"] for symbol, data in event_signals_raw.items()}
            signals["event_driven"] = event_signals
            logger.info(f"Event-driven signals: {event_signals}")
        except Exception as e:
            logger.error(f"Error generating event-driven signals: {e}")
            signals["event_driven"] = {}

        # 3. Ricci Curvature (used for exposure adjustment, not direct signals)
        # This is handled separately in aggregate_signals()

        return signals

    def aggregate_signals(
        self,
        signals: Dict[str, Dict[str, float]],
        strategy_weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        Aggregate signals from multiple strategies.

        Args:
            signals: Dictionary of {strategy: {symbol: signal}}
            strategy_weights: Optional weights for each strategy

        Returns:
            Aggregated signals {symbol: signal_strength}
        """
        if strategy_weights is None:
            # Equal weights
            n_strategies = len([s for s in signals.values() if s])
            strategy_weights = {k: 1.0 / n_strategies for k in signals.keys() if signals[k]}

        # Collect all symbols
        all_symbols = set()
        for strategy_signals in signals.values():
            all_symbols.update(strategy_signals.keys())

        # Aggregate
        aggregated = {}

        for symbol in all_symbols:
            weighted_signal = 0.0

            for strategy, weight in strategy_weights.items():
                if strategy in signals and symbol in signals[strategy]:
                    weighted_signal += weight * signals[strategy][symbol]

            aggregated[symbol] = weighted_signal

        # Normalize to [-1, 1]
        max_abs = max(abs(s) for s in aggregated.values()) if aggregated else 1.0

        if max_abs > 1e-6:
            aggregated = {k: v / max_abs for k, v in aggregated.items()}

        return aggregated

    async def run_step(
        self,
        current_date: datetime,
        price_data: Dict[str, pd.DataFrame],
        current_portfolio: Dict[str, float],
        capital: float = 10000.0
    ) -> Dict:
        """
        Run one orchestration step.

        Args:
            current_date: Current date
            price_data: Price data dictionary
            current_portfolio: Current portfolio weights
            capital: Available capital

        Returns:
            Dictionary with results: {
                "date", "regime", "ricci_adjustment",
                "signals", "optimized_weights", "trades",
                "risk_report", "selected_strategy"
            }
        """
        logger.info(f"Running orchestration step for {current_date}")

        # 1. Detect regime
        returns = pd.DataFrame({
            symbol: df['close'].pct_change()
            for symbol, df in price_data.items()
        }).dropna()

        regime = self.detect_regime(returns)

        # 2. Calculate Ricci curvature → exposure adjustment
        ricci_stats, ricci_adjustment = self.ricci_ews.calculate(price_data)

        logger.info(f"Ricci EWS: adjustment={ricci_adjustment:.2f}, mean_curv={ricci_stats.get('mean', 0):.3f}")

        # 3. Generate signals from all strategies
        signals = await self.generate_all_signals(current_date, price_data)

        # 4. Build context for LinUCB
        context = self.build_context_vector(regime, returns, ricci_stats)

        # 5. Select strategy using LinUCB
        strategy_names = ["structural", "event_driven", "combined"]
        selected_arm = self.linucb.select_arm(context)
        selected_strategy = strategy_names[selected_arm]

        # Strategy weights based on selection
        if selected_strategy == "structural":
            strategy_weights = {"structural": 1.0, "event_driven": 0.0}
        elif selected_strategy == "event_driven":
            strategy_weights = {"structural": 0.0, "event_driven": 1.0}
        else:  # combined
            strategy_weights = {"structural": 0.5, "event_driven": 0.5}

        logger.info(f"LinUCB selected: {selected_strategy}")

        # 6. Aggregate signals
        aggregated_signals = self.aggregate_signals(signals, strategy_weights)

        # 7. Estimate covariance
        cov = self.optimizer.estimate_covariance(returns)

        # 8. Optimize portfolio
        optimized_weights = self.optimizer.optimize(
            signals=aggregated_signals,
            covariance=cov,
            current_weights=current_portfolio,
            regime=regime,
            ricci_adjustment=ricci_adjustment
        )

        # 9. Pre-trade risk checks
        trades = {}
        rejected_trades = []

        for symbol, target_weight in optimized_weights.items():
            current_weight = current_portfolio.get(symbol, 0.0)

            if abs(target_weight - current_weight) > 0.001:  # Meaningful change
                # Risk check
                is_valid, reason = self.risk_manager.check_pre_trade(
                    symbol=symbol,
                    proposed_weight=target_weight,
                    current_portfolio=current_portfolio
                )

                if is_valid:
                    trades[symbol] = {
                        "from": current_weight,
                        "to": target_weight,
                        "delta": target_weight - current_weight
                    }
                else:
                    rejected_trades.append((symbol, reason))
                    logger.warning(f"Trade rejected for {symbol}: {reason}")

        # 10. Calculate PnL (if we have previous day's returns)
        if len(returns) > 0:
            daily_return = (returns.iloc[-1] * pd.Series(current_portfolio).reindex(returns.columns, fill_value=0.0)).sum()
        else:
            daily_return = 0.0

        # 11. Update LinUCB with reward
        reward = float(np.clip(daily_return, -0.1, 0.1))  # Clip for stability
        self.linucb.update(selected_arm, context, reward)

        # 12. Check circuit breakers
        self.risk_manager._pnl_history.append(daily_return)
        should_halt, halt_reason = self.risk_manager.check_circuit_breakers(
            self.risk_manager._pnl_history
        )

        # 13. Generate risk report
        risk_report = self.risk_manager.get_risk_report(
            portfolio=dict(optimized_weights),
            returns_history=returns,
            pnl_history=self.risk_manager._pnl_history
        )

        # 14. Compile result
        result = {
            "date": current_date,
            "regime": regime,
            "ricci_adjustment": ricci_adjustment,
            "ricci_stats": ricci_stats,
            "signals": signals,
            "aggregated_signals": aggregated_signals,
            "selected_strategy": selected_strategy,
            "strategy_weights": strategy_weights,
            "optimized_weights": dict(optimized_weights),
            "trades": trades,
            "rejected_trades": rejected_trades,
            "daily_pnl": daily_return,
            "risk_report": risk_report,
            "should_halt": should_halt,
            "halt_reason": halt_reason
        }

        # Track performance
        self._performance_history.append({
            "date": current_date,
            "pnl": daily_return,
            "sharpe": risk_report["performance"]["sharpe_ratio"],
            "drawdown": risk_report["performance"]["max_drawdown"]
        })

        self._portfolio_history.append({
            "date": current_date,
            "portfolio": dict(optimized_weights)
        })

        return result

    def get_performance_summary(self) -> Dict:
        """Get performance summary."""
        if not self._performance_history:
            return {}

        perf_df = pd.DataFrame(self._performance_history)

        return {
            "total_days": len(perf_df),
            "total_return": float(np.prod(1 + perf_df['pnl']) - 1),
            "sharpe_ratio": perf_df['sharpe'].iloc[-1] if len(perf_df) > 0 else 0.0,
            "max_drawdown": perf_df['drawdown'].max(),
            "win_rate": (perf_df['pnl'] > 0).mean(),
            "avg_daily_return": perf_df['pnl'].mean()
        }
