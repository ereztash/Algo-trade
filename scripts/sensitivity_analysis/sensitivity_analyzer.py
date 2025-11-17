"""
Hyperparameter Sensitivity Analysis Framework
==============================================

מסגרת לניתוח רגישות של היפר-פרמטרים במערכת המסחר האלגוריתמית.

מטרה:
- זיהוי פרמטרים בעלי ההשפעה הגדולה ביותר על ביצועים
- הבנת יציבות המודל לשינויים בפרמטרים
- מציאת ערכים אופטימליים
- זיהוי overfitting

Usage:
    # Run full sensitivity analysis
    python scripts/sensitivity_analysis/sensitivity_analyzer.py \
        --strategy OFI \
        --param HALFLIFE \
        --range 30,90 \
        --steps 10

    # Run grid search
    python scripts/sensitivity_analysis/sensitivity_analyzer.py \
        --mode grid \
        --config config/sensitivity_grid.yaml

    # Run Optuna optimization
    python scripts/sensitivity_analysis/sensitivity_analyzer.py \
        --mode optuna \
        --trials 100 \
        --metric sharpe

Requirements:
    pip install optuna>=3.4.0 plotly>=5.17.0 scikit-learn>=1.3.0
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Callable, Any
from dataclasses import dataclass
from pathlib import Path
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ParameterRange:
    """Define parameter range for sensitivity analysis."""

    name: str
    min_value: float
    max_value: float
    steps: int = 10
    scale: str = "linear"  # 'linear' or 'log'

    def get_values(self) -> np.ndarray:
        """Generate parameter values to test."""
        if self.scale == "log":
            return np.logspace(
                np.log10(self.min_value), np.log10(self.max_value), self.steps
            )
        else:
            return np.linspace(self.min_value, self.max_value, self.steps)


@dataclass
class SensitivityResult:
    """Store results of sensitivity analysis."""

    parameter: str
    values: List[float]
    sharpe_ratios: List[float]
    max_drawdowns: List[float]
    total_returns: List[float]
    num_trades: List[int]
    win_rates: List[float]
    metadata: Dict[str, Any]


class SensitivityAnalyzer:
    """
    Analyze sensitivity of trading strategy to hyperparameters.

    This class runs multiple backtests with different parameter values
    and analyzes the impact on performance metrics.
    """

    def __init__(
        self,
        backtest_func: Callable,
        base_config: Dict[str, Any],
        output_dir: str = "results/sensitivity",
    ):
        """
        Initialize sensitivity analyzer.

        Args:
            backtest_func: Function to run backtest (returns metrics dict)
            base_config: Base configuration dictionary
            output_dir: Directory to save results
        """
        self.backtest_func = backtest_func
        self.base_config = base_config.copy()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: Dict[str, SensitivityResult] = {}

    def analyze_single_parameter(
        self, param_range: ParameterRange, metric: str = "sharpe_ratio"
    ) -> SensitivityResult:
        """
        Analyze sensitivity to a single parameter.

        Args:
            param_range: Parameter range to test
            metric: Primary metric to optimize ('sharpe_ratio', 'max_drawdown', etc.)

        Returns:
            SensitivityResult with analysis results
        """
        logger.info(f"Analyzing sensitivity to {param_range.name}...")
        logger.info(f"  Range: [{param_range.min_value}, {param_range.max_value}]")
        logger.info(f"  Steps: {param_range.steps}")

        values = param_range.get_values()

        sharpe_ratios = []
        max_drawdowns = []
        total_returns = []
        num_trades = []
        win_rates = []

        for i, value in enumerate(values):
            logger.info(f"  [{i+1}/{len(values)}] Testing {param_range.name}={value:.4f}")

            # Update config with new parameter value
            config = self.base_config.copy()
            config[param_range.name] = value

            # Run backtest
            try:
                metrics = self.backtest_func(config)

                sharpe_ratios.append(metrics.get("sharpe_ratio", 0.0))
                max_drawdowns.append(metrics.get("max_drawdown", 0.0))
                total_returns.append(metrics.get("total_return", 0.0))
                num_trades.append(metrics.get("num_trades", 0))
                win_rates.append(metrics.get("win_rate", 0.0))

            except Exception as e:
                logger.error(f"Error testing {param_range.name}={value}: {e}")
                sharpe_ratios.append(0.0)
                max_drawdowns.append(1.0)
                total_returns.append(-1.0)
                num_trades.append(0)
                win_rates.append(0.0)

        # Create result
        result = SensitivityResult(
            parameter=param_range.name,
            values=values.tolist(),
            sharpe_ratios=sharpe_ratios,
            max_drawdowns=max_drawdowns,
            total_returns=total_returns,
            num_trades=num_trades,
            win_rates=win_rates,
            metadata={
                "base_config": self.base_config,
                "timestamp": datetime.now().isoformat(),
                "primary_metric": metric,
            },
        )

        # Store result
        self.results[param_range.name] = result

        # Log summary
        best_idx = np.argmax(sharpe_ratios)
        logger.info(f"✅ Analysis complete for {param_range.name}")
        logger.info(f"  Best value: {values[best_idx]:.4f}")
        logger.info(f"  Best Sharpe: {sharpe_ratios[best_idx]:.4f}")
        logger.info(f"  Sharpe range: [{min(sharpe_ratios):.4f}, {max(sharpe_ratios):.4f}]")

        return result

    def analyze_multiple_parameters(
        self, param_ranges: List[ParameterRange], metric: str = "sharpe_ratio"
    ) -> Dict[str, SensitivityResult]:
        """
        Analyze sensitivity to multiple parameters (one at a time).

        Args:
            param_ranges: List of parameter ranges to test
            metric: Primary metric to optimize

        Returns:
            Dictionary of parameter_name -> SensitivityResult
        """
        results = {}
        for param_range in param_ranges:
            result = self.analyze_single_parameter(param_range, metric)
            results[param_range.name] = result

        return results

    def grid_search_2d(
        self, param1: ParameterRange, param2: ParameterRange, metric: str = "sharpe_ratio"
    ) -> pd.DataFrame:
        """
        Perform 2D grid search on two parameters.

        Args:
            param1: First parameter range
            param2: Second parameter range
            metric: Metric to record in grid

        Returns:
            DataFrame with grid of metric values
        """
        logger.info(f"Running 2D grid search: {param1.name} x {param2.name}")

        values1 = param1.get_values()
        values2 = param2.get_values()

        grid = np.zeros((len(values1), len(values2)))

        total_iterations = len(values1) * len(values2)
        iteration = 0

        for i, val1 in enumerate(values1):
            for j, val2 in enumerate(values2):
                iteration += 1
                logger.info(
                    f"  [{iteration}/{total_iterations}] "
                    f"{param1.name}={val1:.4f}, {param2.name}={val2:.4f}"
                )

                config = self.base_config.copy()
                config[param1.name] = val1
                config[param2.name] = val2

                try:
                    metrics = self.backtest_func(config)
                    grid[i, j] = metrics.get(metric, 0.0)
                except Exception as e:
                    logger.error(f"Error: {e}")
                    grid[i, j] = 0.0

        # Create DataFrame
        df = pd.DataFrame(grid, index=values1, columns=values2)
        df.index.name = param1.name
        df.columns.name = param2.name

        # Save grid
        output_file = self.output_dir / f"grid_2d_{param1.name}_{param2.name}.csv"
        df.to_csv(output_file)
        logger.info(f"Saved 2D grid to {output_file}")

        return df

    def calculate_importance(self) -> pd.DataFrame:
        """
        Calculate parameter importance based on variance in metrics.

        Returns:
            DataFrame with importance scores
        """
        importance_data = []

        for param_name, result in self.results.items():
            sharpe_var = np.var(result.sharpe_ratios)
            sharpe_range = max(result.sharpe_ratios) - min(result.sharpe_ratios)
            sharpe_mean = np.mean(result.sharpe_ratios)

            importance_data.append(
                {
                    "parameter": param_name,
                    "sharpe_variance": sharpe_var,
                    "sharpe_range": sharpe_range,
                    "sharpe_mean": sharpe_mean,
                    "importance_score": sharpe_var * sharpe_range,  # Combined metric
                }
            )

        df = pd.DataFrame(importance_data)
        df = df.sort_values("importance_score", ascending=False)

        return df

    def save_results(self, filename: str = "sensitivity_results.json"):
        """Save all results to JSON file."""
        output_file = self.output_dir / filename

        # Convert results to dict
        results_dict = {}
        for param_name, result in self.results.items():
            results_dict[param_name] = {
                "parameter": result.parameter,
                "values": result.values,
                "sharpe_ratios": result.sharpe_ratios,
                "max_drawdowns": result.max_drawdowns,
                "total_returns": result.total_returns,
                "num_trades": result.num_trades,
                "win_rates": result.win_rates,
                "metadata": result.metadata,
            }

        with open(output_file, "w") as f:
            json.dump(results_dict, f, indent=2)

        logger.info(f"Results saved to {output_file}")

    def load_results(self, filename: str = "sensitivity_results.json"):
        """Load results from JSON file."""
        input_file = self.output_dir / filename

        with open(input_file, "r") as f:
            results_dict = json.load(f)

        # Convert dict to SensitivityResult objects
        for param_name, data in results_dict.items():
            self.results[param_name] = SensitivityResult(
                parameter=data["parameter"],
                values=data["values"],
                sharpe_ratios=data["sharpe_ratios"],
                max_drawdowns=data["max_drawdowns"],
                total_returns=data["total_returns"],
                num_trades=data["num_trades"],
                win_rates=data["win_rates"],
                metadata=data["metadata"],
            )

        logger.info(f"Results loaded from {input_file}")

    def plot_sensitivity(self, param_name: str, metrics: List[str] = None):
        """
        Plot sensitivity for a single parameter.

        Args:
            param_name: Parameter name
            metrics: List of metrics to plot (default: ['sharpe_ratio', 'max_drawdown'])
        """
        if param_name not in self.results:
            raise ValueError(f"Parameter {param_name} not found in results")

        result = self.results[param_name]

        if metrics is None:
            metrics = ["sharpe_ratio", "max_drawdown"]

        fig, axes = plt.subplots(len(metrics), 1, figsize=(12, 4 * len(metrics)))

        if len(metrics) == 1:
            axes = [axes]

        for ax, metric in zip(axes, metrics):
            if metric == "sharpe_ratio":
                values = result.sharpe_ratios
                ylabel = "Sharpe Ratio"
            elif metric == "max_drawdown":
                values = result.max_drawdowns
                ylabel = "Max Drawdown"
            elif metric == "total_return":
                values = result.total_returns
                ylabel = "Total Return"
            elif metric == "win_rate":
                values = result.win_rates
                ylabel = "Win Rate"
            else:
                continue

            ax.plot(result.values, values, marker="o", linewidth=2, markersize=6)
            ax.set_xlabel(param_name)
            ax.set_ylabel(ylabel)
            ax.set_title(f"{ylabel} vs {param_name}")
            ax.grid(True, alpha=0.3)

            # Mark best value
            if metric == "max_drawdown":
                best_idx = np.argmin(values)
            else:
                best_idx = np.argmax(values)

            ax.axvline(
                result.values[best_idx], color="red", linestyle="--", alpha=0.5, label="Best"
            )
            ax.legend()

        plt.tight_layout()
        output_file = self.output_dir / f"sensitivity_{param_name}.png"
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        logger.info(f"Plot saved to {output_file}")
        plt.close()

    def plot_heatmap_2d(self, df: pd.DataFrame, title: str = "2D Grid Search"):
        """
        Plot heatmap for 2D grid search results.

        Args:
            df: DataFrame from grid_search_2d()
            title: Plot title
        """
        plt.figure(figsize=(12, 10))

        sns.heatmap(
            df,
            annot=True,
            fmt=".3f",
            cmap="RdYlGn",
            center=0,
            cbar_kws={"label": "Sharpe Ratio"},
        )

        plt.title(title)
        plt.tight_layout()

        param1 = df.index.name
        param2 = df.columns.name
        output_file = self.output_dir / f"heatmap_2d_{param1}_{param2}.png"
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        logger.info(f"Heatmap saved to {output_file}")
        plt.close()

    def plot_importance(self, importance_df: pd.DataFrame):
        """
        Plot parameter importance.

        Args:
            importance_df: DataFrame from calculate_importance()
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        importance_df.plot(
            x="parameter", y="importance_score", kind="barh", ax=ax, color="steelblue"
        )

        ax.set_xlabel("Importance Score")
        ax.set_ylabel("Parameter")
        ax.set_title("Parameter Importance (Variance × Range)")
        ax.grid(True, alpha=0.3, axis="x")

        plt.tight_layout()
        output_file = self.output_dir / "parameter_importance.png"
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        logger.info(f"Importance plot saved to {output_file}")
        plt.close()


# Example usage
def example_backtest_function(config: Dict[str, Any]) -> Dict[str, float]:
    """
    Example backtest function for demonstration.

    In real usage, this would call your actual backtest engine.
    """
    # Mock backtest results
    halflife = config.get("HALFLIFE", 60)
    threshold = config.get("THRESHOLD", 0.5)

    # Simulate performance based on parameters
    # (In reality, this would run actual backtest)
    sharpe = 1.5 - 0.01 * abs(halflife - 60) - 0.5 * abs(threshold - 0.5)
    max_dd = 0.1 + 0.001 * abs(halflife - 60)
    total_return = 0.2 + 0.001 * (100 - halflife)

    return {
        "sharpe_ratio": max(0, sharpe + np.random.randn() * 0.1),
        "max_drawdown": max_dd,
        "total_return": total_return,
        "num_trades": int(100 + np.random.randint(-20, 20)),
        "win_rate": 0.55 + np.random.randn() * 0.05,
    }


if __name__ == "__main__":
    # Example: Analyze sensitivity to HALFLIFE parameter
    print("🔍 Running Hyperparameter Sensitivity Analysis Example\n")

    # Base configuration
    base_config = {
        "HALFLIFE": 60,
        "THRESHOLD": 0.5,
        "VOL_TARGET": 0.15,
    }

    # Initialize analyzer
    analyzer = SensitivityAnalyzer(
        backtest_func=example_backtest_function,
        base_config=base_config,
        output_dir="results/sensitivity_example",
    )

    # Define parameter ranges to test
    param_ranges = [
        ParameterRange(name="HALFLIFE", min_value=30, max_value=120, steps=10),
        ParameterRange(name="THRESHOLD", min_value=0.1, max_value=1.0, steps=10),
        ParameterRange(name="VOL_TARGET", min_value=0.10, max_value=0.20, steps=5),
    ]

    # Run sensitivity analysis
    results = analyzer.analyze_multiple_parameters(param_ranges)

    # Calculate importance
    importance = analyzer.calculate_importance()
    print("\n📊 Parameter Importance:")
    print(importance)

    # Plot results
    for param_name in results.keys():
        analyzer.plot_sensitivity(param_name, metrics=["sharpe_ratio", "max_drawdown"])

    # Plot importance
    analyzer.plot_importance(importance)

    # Save results
    analyzer.save_results()

    # 2D grid search example
    print("\n🔍 Running 2D Grid Search: HALFLIFE x THRESHOLD")
    grid_df = analyzer.grid_search_2d(param_ranges[0], param_ranges[1])
    analyzer.plot_heatmap_2d(grid_df, title="Sharpe Ratio: HALFLIFE x THRESHOLD")

    print("\n✅ Sensitivity analysis complete!")
    print(f"Results saved to: {analyzer.output_dir}")
