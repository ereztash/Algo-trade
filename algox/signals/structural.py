"""
Structural Arbitrage Signal
============================

Exploits lead-lag relationships between correlated ETFs based on causal chains:
REMX (Rare Earth Metals) → URNM (Uranium Miners) → QTUM (Quantum Computing)

Rationale:
----------
- REMX contains rare earth elements (REE) needed for magnets
- URNM depends on nuclear energy (high REE consumption)
- QTUM depends on quantum hardware (REE + energy intensive)

Signal Logic:
------------
1. Granger Causality Test: Confirm REMX → URNM → QTUM relationships
2. Lead-Lag Detection: Identify time lag (typically 1-3 days)
3. Breakout Detection: When REMX moves significantly, predict URNM/QTUM
4. Position: Long URNM/QTUM when REMX shows strong move

Example:
--------
    from algox.signals.structural import StructuralArbitrageSignal

    signal = StructuralArbitrageSignal(config)
    signals = signal.generate(price_data)  # Returns {symbol: signal_strength}
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.stats import pearsonr
from statsmodels.tsa.stattools import grangercausalitytests
import logging

logger = logging.getLogger(__name__)


class StructuralArbitrageSignal:
    """
    Generates signals based on structural arbitrage (lead-lag relationships).

    Attributes:
        symbols: List of symbols in causal chain (default: ["REMX", "URNM", "QTUM"])
        granger_lag: Maximum lag for Granger causality test
        granger_pvalue: P-value threshold for significance
        lookback: Days for correlation analysis
        threshold: Minimum move in leader to trigger signal
        hold_days: Holding period options
    """

    def __init__(self, config: Dict):
        """Initialize structural arbitrage signal generator."""
        struct_config = config.get("STRUCTURAL", {})

        self.symbols = config.get("STRATEGIES", {}).get("STRUCTURAL_ARBITRAGE", {}).get("SYMBOLS", ["REMX", "URNM", "QTUM"])
        self.granger_lag = struct_config.get("GRANGER_LAG", 5)
        self.granger_pvalue = struct_config.get("GRANGER_PVALUE", 0.05)
        self.lookback = struct_config.get("LOOKBACK", 252)
        self.threshold = struct_config.get("THRESHOLD", 0.02)  # 2% move
        self.hold_days = struct_config.get("HOLD_DAYS", [1, 2, 3])

        # Cache for Granger test results
        self._granger_cache = {}
        self._last_test_date = None

    def test_granger_causality(
        self,
        leader: pd.Series,
        follower: pd.Series,
        max_lag: int = 5
    ) -> Tuple[bool, int, float]:
        """
        Test Granger causality from leader to follower.

        Args:
            leader: Time series of leader (e.g., REMX)
            follower: Time series of follower (e.g., URNM)
            max_lag: Maximum lag to test

        Returns:
            (is_significant, optimal_lag, min_pvalue)
        """
        try:
            # Align series
            df = pd.DataFrame({"leader": leader, "follower": follower}).dropna()

            if len(df) < 30:
                logger.warning("Insufficient data for Granger causality test")
                return False, 0, 1.0

            # Run Granger causality test
            result = grangercausalitytests(df[["follower", "leader"]], maxlag=max_lag, verbose=False)

            # Find optimal lag (lowest p-value)
            min_pvalue = 1.0
            optimal_lag = 0

            for lag in range(1, max_lag + 1):
                # Extract p-value from F-test
                pvalue = result[lag][0]['ssr_ftest'][1]

                if pvalue < min_pvalue:
                    min_pvalue = pvalue
                    optimal_lag = lag

            is_significant = min_pvalue < self.granger_pvalue

            logger.info(f"Granger test: lag={optimal_lag}, p-value={min_pvalue:.4f}, significant={is_significant}")

            return is_significant, optimal_lag, min_pvalue

        except Exception as e:
            logger.error(f"Error in Granger causality test: {e}")
            return False, 0, 1.0

    def detect_breakout(self, returns: pd.Series, threshold: float = 0.02) -> Tuple[bool, float]:
        """
        Detect significant breakout in leader returns.

        Args:
            returns: Return series
            threshold: Minimum absolute return to consider breakout

        Returns:
            (is_breakout, return_magnitude)
        """
        if len(returns) < 1:
            return False, 0.0

        latest_return = returns.iloc[-1]
        is_breakout = abs(latest_return) >= threshold

        return is_breakout, latest_return

    def calculate_lead_lag_correlation(
        self,
        leader: pd.Series,
        follower: pd.Series,
        max_lag: int = 5
    ) -> Dict[int, float]:
        """
        Calculate correlation at different lags.

        Args:
            leader: Leader series
            follower: Follower series
            max_lag: Maximum lag to test

        Returns:
            Dictionary of {lag: correlation}
        """
        correlations = {}

        for lag in range(0, max_lag + 1):
            if lag == 0:
                corr, _ = pearsonr(leader.dropna(), follower.dropna())
            else:
                # Shift leader forward by lag
                leader_shifted = leader.shift(lag)
                aligned = pd.DataFrame({"leader": leader_shifted, "follower": follower}).dropna()

                if len(aligned) < 10:
                    corr = 0.0
                else:
                    corr, _ = pearsonr(aligned["leader"], aligned["follower"])

            correlations[lag] = corr

        return correlations

    def generate(self, price_data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        """
        Generate structural arbitrage signals.

        Args:
            price_data: Dictionary of {symbol: DataFrame with 'close' column}

        Returns:
            Dictionary of {symbol: signal_strength} where signal_strength in [-1, 1]
        """
        signals = {symbol: 0.0 for symbol in self.symbols}

        # Extract returns
        returns = {}
        for symbol in self.symbols:
            if symbol not in price_data or price_data[symbol].empty:
                logger.warning(f"No price data for {symbol}")
                return signals

            df = price_data[symbol]
            if 'close' not in df.columns:
                logger.error(f"'close' column missing for {symbol}")
                return signals

            returns[symbol] = df['close'].pct_change().iloc[-self.lookback:]

        # Verify we have enough data
        min_length = min(len(r) for r in returns.values())
        if min_length < 30:
            logger.warning("Insufficient data for structural arbitrage signal")
            return signals

        # Test causal relationships
        # REMX → URNM
        if len(self.symbols) >= 2:
            remx_returns = returns[self.symbols[0]]
            urnm_returns = returns[self.symbols[1]]

            is_causal, lag_remx_urnm, pvalue = self.test_granger_causality(
                remx_returns, urnm_returns, self.granger_lag
            )

            # Detect breakout in REMX
            is_breakout, remx_move = self.detect_breakout(remx_returns, self.threshold)

            if is_causal and is_breakout:
                # Calculate correlation to determine signal strength
                correlations = self.calculate_lead_lag_correlation(
                    remx_returns, urnm_returns, self.granger_lag
                )

                optimal_corr = max(correlations.values())

                # Signal strength proportional to:
                # 1. Magnitude of REMX move
                # 2. Correlation strength
                # 3. Inverse of p-value (stronger causality = stronger signal)

                signal_strength = np.sign(remx_move) * min(
                    abs(remx_move) / self.threshold,  # Normalized move
                    1.0
                ) * abs(optimal_corr) * (1 - pvalue)

                signals[self.symbols[1]] = float(np.clip(signal_strength, -1, 1))

                logger.info(f"REMX → URNM: move={remx_move:.2%}, corr={optimal_corr:.2f}, signal={signals[self.symbols[1]]:.2f}")

        # URNM → QTUM (if we have 3 symbols)
        if len(self.symbols) >= 3:
            urnm_returns = returns[self.symbols[1]]
            qtum_returns = returns[self.symbols[2]]

            is_causal, lag_urnm_qtum, pvalue = self.test_granger_causality(
                urnm_returns, qtum_returns, self.granger_lag
            )

            is_breakout, urnm_move = self.detect_breakout(urnm_returns, self.threshold)

            if is_causal and is_breakout:
                correlations = self.calculate_lead_lag_correlation(
                    urnm_returns, qtum_returns, self.granger_lag
                )

                optimal_corr = max(correlations.values())

                signal_strength = np.sign(urnm_move) * min(
                    abs(urnm_move) / self.threshold,
                    1.0
                ) * abs(optimal_corr) * (1 - pvalue)

                signals[self.symbols[2]] = float(np.clip(signal_strength, -1, 1))

                logger.info(f"URNM → QTUM: move={urnm_move:.2%}, corr={optimal_corr:.2f}, signal={signals[self.symbols[2]]:.2f}")

        # REMX → QTUM (direct, for robustness)
        if len(self.symbols) >= 3:
            remx_returns = returns[self.symbols[0]]
            qtum_returns = returns[self.symbols[2]]

            is_causal, lag_remx_qtum, pvalue = self.test_granger_causality(
                remx_returns, qtum_returns, self.granger_lag
            )

            is_breakout, remx_move = self.detect_breakout(remx_returns, self.threshold)

            if is_causal and is_breakout:
                correlations = self.calculate_lead_lag_correlation(
                    remx_returns, qtum_returns, self.granger_lag
                )

                optimal_corr = max(correlations.values())

                signal_strength = np.sign(remx_move) * min(
                    abs(remx_move) / self.threshold,
                    1.0
                ) * abs(optimal_corr) * (1 - pvalue)

                # Average with existing signal (if any)
                if signals[self.symbols[2]] != 0:
                    signals[self.symbols[2]] = (signals[self.symbols[2]] + signal_strength) / 2.0
                else:
                    signals[self.symbols[2]] = signal_strength

                signals[self.symbols[2]] = float(np.clip(signals[self.symbols[2]], -1, 1))

                logger.info(f"REMX → QTUM (direct): move={remx_move:.2%}, corr={optimal_corr:.2f}, signal={signals[self.symbols[2]]:.2f}")

        return signals

    def backtest_lag_performance(
        self,
        price_data: Dict[str, pd.DataFrame],
        leader_symbol: str,
        follower_symbol: str,
        test_lags: List[int] = [1, 2, 3]
    ) -> Dict[int, float]:
        """
        Backtest different lag periods to find optimal holding period.

        Args:
            price_data: Price data
            leader_symbol: Leader symbol
            follower_symbol: Follower symbol
            test_lags: List of lags to test

        Returns:
            Dictionary of {lag: sharpe_ratio}
        """
        if leader_symbol not in price_data or follower_symbol not in price_data:
            return {}

        leader_returns = price_data[leader_symbol]['close'].pct_change()
        follower_returns = price_data[follower_symbol]['close'].pct_change()

        results = {}

        for lag in test_lags:
            # Generate signals: when leader moves > threshold, go long follower
            signals = (leader_returns.abs() > self.threshold).astype(int) * np.sign(leader_returns)

            # Shift signals forward by lag
            signals_shifted = signals.shift(lag)

            # Calculate strategy returns
            strategy_returns = signals_shifted * follower_returns

            # Calculate Sharpe ratio
            if strategy_returns.std() > 0:
                sharpe = strategy_returns.mean() / strategy_returns.std() * np.sqrt(252)
            else:
                sharpe = 0.0

            results[lag] = sharpe

            logger.info(f"Lag {lag}: Sharpe = {sharpe:.2f}")

        return results
