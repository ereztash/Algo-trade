"""
Optuna-based Hyperparameter Optimization
=========================================

אופטימיזציה אוטומטית של היפר-פרמטרים באמצעות Optuna.

מה זה Optuna?
- Framework לאופטימיזציית היפר-פרמטרים
- משתמש ב-Bayesian Optimization (TPE - Tree-structured Parzen Estimator)
- חכם יותר מ-Grid Search - לומד מניסויים קודמים
- תומך ב-pruning - עוצר trials שלא מבטיחים במוקדם

Usage:
    # Run optimization
    python scripts/sensitivity_analysis/optuna_optimizer.py \
        --strategy OFI \
        --trials 100 \
        --metric sharpe_ratio

    # Resume previous study
    python scripts/sensitivity_analysis/optuna_optimizer.py \
        --study-name my_study \
        --resume

    # Visualize results
    python scripts/sensitivity_analysis/optuna_optimizer.py \
        --study-name my_study \
        --visualize

Requirements:
    pip install optuna>=3.4.0 optuna-dashboard>=0.13.0
"""

import optuna
from optuna.trial import Trial
from optuna.visualization import (
    plot_optimization_history,
    plot_param_importances,
    plot_parallel_coordinate,
    plot_slice,
    plot_contour,
)
import numpy as np
import pandas as pd
from typing import Dict, Any, Callable
import logging
from pathlib import Path
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OptunaOptimizer:
    """
    Hyperparameter optimization using Optuna.

    Features:
    - Bayesian optimization (smarter than grid search)
    - Early stopping (pruning)
    - Parallel trials
    - Study persistence
    - Visualization
    """

    def __init__(
        self,
        objective_func: Callable[[Dict], float],
        study_name: str = "algo_trade_optimization",
        storage: str = None,
        direction: str = "maximize",  # 'maximize' or 'minimize'
    ):
        """
        Initialize Optuna optimizer.

        Args:
            objective_func: Function that takes config dict and returns metric value
            study_name: Name of the study (for persistence)
            storage: Storage URL (e.g., 'sqlite:///optuna.db' or None for in-memory)
            direction: Optimization direction ('maximize' for Sharpe, 'minimize' for DD)
        """
        self.objective_func = objective_func
        self.study_name = study_name
        self.direction = direction

        # Create or load study
        if storage is None:
            storage = f"sqlite:///results/optuna/{study_name}.db"

        Path("results/optuna").mkdir(parents=True, exist_ok=True)

        self.study = optuna.create_study(
            study_name=study_name,
            storage=storage,
            load_if_exists=True,
            direction=direction,
            sampler=optuna.samplers.TPESampler(seed=42),  # Bayesian optimization
            pruner=optuna.pruners.MedianPruner(  # Early stopping
                n_startup_trials=10, n_warmup_steps=5, interval_steps=1
            ),
        )

    def define_search_space(self, trial: Trial, param_config: Dict[str, Dict]) -> Dict:
        """
        Define search space for hyperparameters.

        Args:
            trial: Optuna trial object
            param_config: Dictionary defining parameter ranges
                {
                    'HALFLIFE': {'type': 'int', 'low': 30, 'high': 120},
                    'THRESHOLD': {'type': 'float', 'low': 0.1, 'high': 1.0},
                    'VOL_TARGET': {'type': 'float', 'low': 0.1, 'high': 0.3, 'log': True},
                }

        Returns:
            Dictionary with suggested parameter values
        """
        config = {}

        for param_name, param_spec in param_config.items():
            param_type = param_spec["type"]

            if param_type == "int":
                config[param_name] = trial.suggest_int(
                    param_name, param_spec["low"], param_spec["high"]
                )

            elif param_type == "float":
                if param_spec.get("log", False):
                    # Log scale for parameters that vary over orders of magnitude
                    config[param_name] = trial.suggest_float(
                        param_name, param_spec["low"], param_spec["high"], log=True
                    )
                else:
                    config[param_name] = trial.suggest_float(
                        param_name, param_spec["low"], param_spec["high"]
                    )

            elif param_type == "categorical":
                config[param_name] = trial.suggest_categorical(
                    param_name, param_spec["choices"]
                )

        return config

    def objective(self, trial: Trial, param_config: Dict[str, Dict]) -> float:
        """
        Objective function for Optuna.

        Args:
            trial: Optuna trial
            param_config: Parameter configuration

        Returns:
            Metric value to optimize
        """
        # Suggest parameters
        config = self.define_search_space(trial, param_config)

        # Log trial
        logger.info(f"Trial {trial.number}: {config}")

        try:
            # Run backtest with these parameters
            metric_value = self.objective_func(config)

            # Report intermediate value for pruning
            # (In real usage, report after each period/epoch)
            trial.report(metric_value, step=0)

            # Check if should prune
            if trial.should_prune():
                raise optuna.TrialPruned()

            return metric_value

        except Exception as e:
            logger.error(f"Trial {trial.number} failed: {e}")
            # Return worst possible value
            return -np.inf if self.direction == "maximize" else np.inf

    def optimize(
        self,
        param_config: Dict[str, Dict],
        n_trials: int = 100,
        timeout: int = None,
        n_jobs: int = 1,
    ) -> optuna.Study:
        """
        Run optimization.

        Args:
            param_config: Parameter configuration
            n_trials: Number of trials to run
            timeout: Timeout in seconds (optional)
            n_jobs: Number of parallel jobs (1 = sequential)

        Returns:
            Completed study object
        """
        logger.info(f"🚀 Starting optimization: {self.study_name}")
        logger.info(f"  Trials: {n_trials}")
        logger.info(f"  Direction: {self.direction}")
        logger.info(f"  Parallel jobs: {n_jobs}")

        self.study.optimize(
            lambda trial: self.objective(trial, param_config),
            n_trials=n_trials,
            timeout=timeout,
            n_jobs=n_jobs,
            show_progress_bar=True,
        )

        logger.info(f"\n✅ Optimization complete!")
        logger.info(f"  Best trial: {self.study.best_trial.number}")
        logger.info(f"  Best value: {self.study.best_value:.4f}")
        logger.info(f"  Best params: {self.study.best_params}")

        return self.study

    def get_best_params(self) -> Dict[str, Any]:
        """Get best parameters found."""
        return self.study.best_params

    def get_best_value(self) -> float:
        """Get best value found."""
        return self.study.best_value

    def get_results_dataframe(self) -> pd.DataFrame:
        """Get all trials as DataFrame."""
        return self.study.trials_dataframe()

    def visualize(self, save_dir: str = "results/optuna/plots"):
        """
        Create and save all visualization plots.

        Args:
            save_dir: Directory to save plots
        """
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        logger.info(f"📊 Creating visualizations...")

        # 1. Optimization History
        try:
            fig = plot_optimization_history(self.study)
            fig.write_html(f"{save_dir}/optimization_history.html")
            logger.info(f"  ✅ Optimization history saved")
        except Exception as e:
            logger.error(f"  ❌ Failed to create optimization history: {e}")

        # 2. Parameter Importances
        try:
            fig = plot_param_importances(self.study)
            fig.write_html(f"{save_dir}/param_importances.html")
            logger.info(f"  ✅ Parameter importances saved")
        except Exception as e:
            logger.error(f"  ❌ Failed to create parameter importances: {e}")

        # 3. Parallel Coordinate Plot
        try:
            fig = plot_parallel_coordinate(self.study)
            fig.write_html(f"{save_dir}/parallel_coordinate.html")
            logger.info(f"  ✅ Parallel coordinate plot saved")
        except Exception as e:
            logger.error(f"  ❌ Failed to create parallel coordinate: {e}")

        # 4. Slice Plot
        try:
            fig = plot_slice(self.study)
            fig.write_html(f"{save_dir}/slice_plot.html")
            logger.info(f"  ✅ Slice plot saved")
        except Exception as e:
            logger.error(f"  ❌ Failed to create slice plot: {e}")

        # 5. Contour Plot (for 2D)
        try:
            params = list(self.study.best_params.keys())
            if len(params) >= 2:
                fig = plot_contour(self.study, params=[params[0], params[1]])
                fig.write_html(f"{save_dir}/contour_plot.html")
                logger.info(f"  ✅ Contour plot saved")
        except Exception as e:
            logger.error(f"  ❌ Failed to create contour plot: {e}")

        logger.info(f"\n✅ All visualizations saved to: {save_dir}")

    def save_best_config(self, filename: str = "best_config.json"):
        """
        Save best configuration to JSON file.

        Args:
            filename: Output filename
        """
        output = {
            "study_name": self.study_name,
            "best_trial": self.study.best_trial.number,
            "best_value": self.study.best_value,
            "best_params": self.study.best_params,
            "direction": self.direction,
            "n_trials": len(self.study.trials),
            "timestamp": datetime.now().isoformat(),
        }

        output_file = Path("results/optuna") / filename
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"Best config saved to: {output_file}")

    def print_summary(self):
        """Print optimization summary."""
        print("\n" + "=" * 60)
        print(f"Optuna Optimization Summary: {self.study_name}")
        print("=" * 60)

        print(f"\n📊 Study Statistics:")
        print(f"  Total trials: {len(self.study.trials)}")
        print(f"  Complete trials: {len(self.study.get_trials(states=[optuna.trial.TrialState.COMPLETE]))}")
        print(f"  Pruned trials: {len(self.study.get_trials(states=[optuna.trial.TrialState.PRUNED]))}")
        print(f"  Failed trials: {len(self.study.get_trials(states=[optuna.trial.TrialState.FAIL]))}")

        print(f"\n🏆 Best Trial:")
        print(f"  Trial number: {self.study.best_trial.number}")
        print(f"  Value: {self.study.best_value:.4f}")
        print(f"  Parameters:")
        for param, value in self.study.best_params.items():
            print(f"    {param}: {value}")

        # Parameter importance (if available)
        try:
            importances = optuna.importance.get_param_importances(self.study)
            print(f"\n📈 Parameter Importance:")
            for param, importance in sorted(
                importances.items(), key=lambda x: x[1], reverse=True
            ):
                print(f"    {param}: {importance:.4f}")
        except:
            pass

        print("\n" + "=" * 60)


# Example usage
def example_objective(config: Dict[str, Any]) -> float:
    """
    Example objective function.

    In real usage, this would run a backtest and return Sharpe ratio.
    """
    halflife = config.get("HALFLIFE", 60)
    threshold = config.get("THRESHOLD", 0.5)
    vol_target = config.get("VOL_TARGET", 0.15)

    # Simulate performance (replace with actual backtest)
    sharpe = (
        1.5
        - 0.01 * abs(halflife - 60)
        - 0.5 * abs(threshold - 0.5)
        - 2.0 * abs(vol_target - 0.15)
    )

    return max(0, sharpe + np.random.randn() * 0.1)


if __name__ == "__main__":
    print("🔍 Running Optuna Optimization Example\n")

    # Initialize optimizer
    optimizer = OptunaOptimizer(
        objective_func=example_objective,
        study_name="example_optimization",
        direction="maximize",  # Maximize Sharpe ratio
    )

    # Define parameter search space
    param_config = {
        "HALFLIFE": {"type": "int", "low": 30, "high": 120},
        "THRESHOLD": {"type": "float", "low": 0.1, "high": 1.0},
        "VOL_TARGET": {"type": "float", "low": 0.10, "high": 0.20},
    }

    # Run optimization
    study = optimizer.optimize(param_config, n_trials=50, n_jobs=1)

    # Print summary
    optimizer.print_summary()

    # Save best config
    optimizer.save_best_config()

    # Create visualizations
    optimizer.visualize()

    # Get results DataFrame
    df = optimizer.get_results_dataframe()
    print("\n📄 All Trials:")
    print(df[["number", "value", "params_HALFLIFE", "params_THRESHOLD", "params_VOL_TARGET"]].head(10))

    print("\n✅ Example complete!")
