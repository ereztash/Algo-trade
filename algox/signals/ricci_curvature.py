"""
Ricci Curvature Early Warning System
====================================

Implements Forman-Ricci Curvature to detect systemic fragility in market networks.

Theory:
-------
- Markets can be modeled as correlation networks (nodes = stocks, edges = correlations)
- Ricci curvature measures the "shape" of the network
- Negative curvature indicates fragility (edges that can break under stress)
- Positive curvature indicates robustness (well-connected clusters)

Application:
-----------
- When avg(Ricci) < -0.2: Market is fragile → Reduce exposure
- When avg(Ricci) > 0.1: Market is robust → Increase exposure
- Used as RISK FILTER, not standalone signal

References:
----------
- Sandhu, R., et al. (2016). "Market fragility, systemic risk, and Ricci curvature"
- Ollivier, Y. (2009). "Ricci curvature of Markov chains on metric spaces"

Example:
--------
    from algox.signals.ricci_curvature import RicciCurvatureEWS

    ews = RicciCurvatureEWS(config)
    curvature, adjustment = ews.calculate(price_data)

    # adjustment is multiplier for exposure: 0.5 (reduce), 1.0 (neutral), 1.2 (increase)
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, List
import networkx as nx
import logging

logger = logging.getLogger(__name__)


class RicciCurvatureEWS:
    """
    Early Warning System based on Forman-Ricci Curvature.

    Attributes:
        universe: List of symbols to analyze (typically market indices)
        correlation_threshold: Minimum correlation to create edge
        lookback: Days for correlation calculation
        curvature_threshold: Thresholds for negative/positive curvature
        exposure_scaling: Scaling factors for exposure adjustment
    """

    def __init__(self, config: Dict):
        """Initialize Ricci Curvature EWS."""
        ricci_config = config.get("RICCI", {})

        self.universe = config.get("STRATEGIES", {}).get("RICCI_CURVATURE", {}).get("UNIVERSE", ["SPY", "QQQ", "IWM", "DIA"])
        self.correlation_threshold = ricci_config.get("CORRELATION_THRESHOLD", 0.3)
        self.lookback = ricci_config.get("LOOKBACK", 60)

        thresholds = ricci_config.get("CURVATURE_THRESHOLD", {})
        self.negative_threshold = thresholds.get("NEGATIVE", -0.2)
        self.positive_threshold = thresholds.get("POSITIVE", 0.1)

        scaling = ricci_config.get("EXPOSURE_SCALING", {})
        self.reduce_factor = scaling.get("REDUCE", 0.5)
        self.increase_factor = scaling.get("INCREASE", 1.2)

    def build_correlation_network(self, returns: pd.DataFrame) -> nx.Graph:
        """
        Build correlation network from returns data.

        Args:
            returns: DataFrame of returns (columns = symbols)

        Returns:
            NetworkX graph with nodes = symbols, edges = correlations > threshold
        """
        # Calculate correlation matrix
        corr_matrix = returns.corr()

        # Create graph
        G = nx.Graph()

        # Add nodes
        G.add_nodes_from(returns.columns)

        # Add edges where correlation exceeds threshold
        for i, symbol1 in enumerate(returns.columns):
            for j, symbol2 in enumerate(returns.columns):
                if i < j:  # Avoid duplicates
                    corr = corr_matrix.loc[symbol1, symbol2]

                    if abs(corr) >= self.correlation_threshold:
                        # Edge weight = correlation
                        G.add_edge(symbol1, symbol2, weight=abs(corr))

        logger.info(f"Built correlation network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        return G

    def forman_ricci_curvature(self, G: nx.Graph, edge: Tuple[str, str]) -> float:
        """
        Calculate Forman-Ricci curvature for a single edge.

        Forman curvature formula for edge (i, j):
        Ric(i,j) = w(i,j) * [deg(i) + deg(j) - 2] - sum of weights of triangles

        Simplified version (ignoring triangle terms for speed):
        Ric(i,j) ≈ w(i,j) * [deg(i) + deg(j) - 2]

        Args:
            G: NetworkX graph
            edge: Tuple of (node1, node2)

        Returns:
            Ricci curvature value
        """
        i, j = edge

        # Get edge weight
        w_ij = G[i][j].get('weight', 1.0)

        # Get degrees
        deg_i = G.degree(i)
        deg_j = G.degree(j)

        # Simplified Forman curvature
        # Positive curvature: well-connected nodes (high degree)
        # Negative curvature: poorly connected nodes (low degree)
        curvature = w_ij * (deg_i + deg_j - 2)

        # Normalize by max possible degree
        max_degree = G.number_of_nodes() - 1
        curvature_normalized = curvature / (2 * max_degree) if max_degree > 0 else 0.0

        return curvature_normalized

    def calculate_network_curvature(self, G: nx.Graph) -> Dict[str, float]:
        """
        Calculate Ricci curvature for all edges in the network.

        Args:
            G: NetworkX graph

        Returns:
            Dictionary of {edge: curvature}
        """
        curvatures = {}

        for edge in G.edges():
            curvature = self.forman_ricci_curvature(G, edge)
            curvatures[edge] = curvature

        return curvatures

    def analyze_curvature_distribution(self, curvatures: Dict[Tuple[str, str], float]) -> Dict[str, float]:
        """
        Analyze the distribution of curvatures.

        Args:
            curvatures: Dictionary of edge curvatures

        Returns:
            Dictionary with statistics: mean, std, min, max, negative_pct
        """
        if not curvatures:
            return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "negative_pct": 0.0}

        values = list(curvatures.values())

        stats = {
            "mean": np.mean(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values),
            "negative_pct": sum(1 for v in values if v < 0) / len(values)
        }

        return stats

    def calculate(self, price_data: Dict[str, pd.DataFrame]) -> Tuple[Dict[str, float], float]:
        """
        Calculate Ricci curvature and determine exposure adjustment.

        Args:
            price_data: Dictionary of {symbol: DataFrame with 'close' column}

        Returns:
            Tuple of (curvature_stats, exposure_adjustment)
            where exposure_adjustment is multiplier: 0.5 (reduce), 1.0 (neutral), 1.2 (increase)
        """
        # Extract returns for universe
        returns = {}
        for symbol in self.universe:
            if symbol not in price_data or price_data[symbol].empty:
                logger.warning(f"No price data for {symbol}")
                continue

            df = price_data[symbol]
            if 'close' not in df.columns:
                logger.error(f"'close' column missing for {symbol}")
                continue

            returns[symbol] = df['close'].pct_change().iloc[-self.lookback:]

        if len(returns) < 2:
            logger.warning("Insufficient symbols for Ricci curvature analysis")
            return {"mean": 0.0}, 1.0

        # Convert to DataFrame
        returns_df = pd.DataFrame(returns).dropna()

        if len(returns_df) < 20:
            logger.warning("Insufficient data for Ricci curvature analysis")
            return {"mean": 0.0}, 1.0

        # Build correlation network
        G = self.build_correlation_network(returns_df)

        if G.number_of_edges() == 0:
            logger.warning("No edges in correlation network (correlations too low)")
            return {"mean": 0.0}, 1.0

        # Calculate curvatures
        curvatures = self.calculate_network_curvature(G)

        # Analyze distribution
        stats = self.analyze_curvature_distribution(curvatures)

        # Determine exposure adjustment based on mean curvature
        mean_curvature = stats["mean"]

        if mean_curvature < self.negative_threshold:
            # Fragile market → Reduce exposure
            adjustment = self.reduce_factor
            signal = "FRAGILE"
            logger.warning(f"Ricci EWS: FRAGILE market detected (mean curvature={mean_curvature:.3f}). Reducing exposure to {adjustment*100:.0f}%")

        elif mean_curvature > self.positive_threshold:
            # Robust market → Increase exposure
            adjustment = self.increase_factor
            signal = "ROBUST"
            logger.info(f"Ricci EWS: ROBUST market detected (mean curvature={mean_curvature:.3f}). Increasing exposure to {adjustment*100:.0f}%")

        else:
            # Neutral market → No adjustment
            adjustment = 1.0
            signal = "NEUTRAL"
            logger.info(f"Ricci EWS: NEUTRAL market (mean curvature={mean_curvature:.3f}). No exposure adjustment")

        # Add signal to stats
        stats["signal"] = signal
        stats["adjustment"] = adjustment

        return stats, adjustment

    def visualize_network(self, G: nx.Graph, curvatures: Dict[Tuple[str, str], float]) -> None:
        """
        Visualize the correlation network with curvature values.

        Args:
            G: NetworkX graph
            curvatures: Edge curvatures

        Note:
            Requires matplotlib. Only for research/debugging.
        """
        try:
            import matplotlib.pyplot as plt

            # Color edges by curvature
            edge_colors = []
            for edge in G.edges():
                curv = curvatures.get(edge, 0.0)
                if curv < 0:
                    edge_colors.append('red')  # Fragile
                else:
                    edge_colors.append('green')  # Robust

            # Draw network
            pos = nx.spring_layout(G, k=0.5, iterations=50)
            nx.draw(G, pos, with_labels=True, node_color='lightblue',
                   edge_color=edge_colors, node_size=500, font_size=8)

            plt.title("Market Correlation Network\n(Red = Negative Curvature, Green = Positive)")
            plt.tight_layout()
            plt.show()

        except ImportError:
            logger.warning("matplotlib not available for visualization")

    def backtest_signal(
        self,
        price_data: Dict[str, pd.DataFrame],
        rebalance_freq: int = 5
    ) -> pd.DataFrame:
        """
        Backtest the Ricci curvature signal.

        Args:
            price_data: Historical price data
            rebalance_freq: Rebalance frequency (days)

        Returns:
            DataFrame with columns: date, mean_curvature, adjustment, signal
        """
        results = []

        # Get date range from first symbol
        first_symbol = list(price_data.keys())[0]
        dates = price_data[first_symbol].index

        for i in range(self.lookback, len(dates), rebalance_freq):
            current_date = dates[i]

            # Slice price data up to current date
            price_slice = {}
            for symbol, df in price_data.items():
                price_slice[symbol] = df.loc[:current_date]

            # Calculate curvature
            stats, adjustment = self.calculate(price_slice)

            results.append({
                "date": current_date,
                "mean_curvature": stats.get("mean", 0.0),
                "std_curvature": stats.get("std", 0.0),
                "negative_pct": stats.get("negative_pct", 0.0),
                "adjustment": adjustment,
                "signal": stats.get("signal", "NEUTRAL")
            })

        return pd.DataFrame(results)
