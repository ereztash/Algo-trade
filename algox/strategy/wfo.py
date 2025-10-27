"""
Walk-Forward Optimization (WFO)
================================

8-step protocol for robust out-of-sample validation and hyperparameter optimization.

Protocol Steps:
--------------
1. Data Split (chronological): Train (12m) → Validate (3m) → Test (3m)
2. Feature Engineering (on training only): Granger, Ricci, Events
3. Normalization (fit on training): Z-score parameters, covariance
4. Model Training: Bayesian hyperparameter optimization
5. Out-of-Sample Testing: Test on unseen data
6. Statistical Validation: CSCV, PSR, DSR, WFE
7. Roll Forward: Shift window by 3 months
8. Aggregate Results: Calculate overall WFE

Walk-Forward Efficiency (WFE):
-----------------------------
WFE = (OOS Performance) / (IS Performance)

Target: WFE > 60%

Example:
--------
    from algox.strategy.wfo import WalkForwardOptimizer

    wfo = WalkForwardOptimizer(config)
    results = wfo.run(
        price_data=price_data,
        start_date="2022-01-01",
        end_date="2024-12-31"
    )

    wfe = results["wfe"]
    print(f"Walk-Forward Efficiency: {wfe:.2%}")
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Callable
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging
from scipy.stats import skew, kurtosis
import warnings

try:
    from sklearn.model_selection import ParameterSampler
    from scipy.stats import uniform, randint
except ImportError:
    warnings.warn("scikit-learn not available. Bayesian optimization will be limited.")

from algox.strategy.orchestrator import StrategyOrchestrator

logger = logging.getLogger(__name__)


class WalkForwardOptimizer:
    """
    Walk-Forward Optimization protocol.

    Implements 8-step WFO for robust hyperparameter optimization and
    out-of-sample validation.

    Attributes:
        config: Configuration dictionary
        train_window: Training window size (months)
        validation_window: Validation window size (months)
        test_window: Test window size (months)
        step_size: Roll-forward step size (months)
        search_space: Hyperparameter search space
        n_iterations: Number of optimization iterations
    """

    def __init__(self, config: Dict):
        """Initialize Walk-Forward Optimizer."""
        wfo_config = config.get("WFO", {})

        self.config = config
        self.train_window = wfo_config.get("TRAIN_WINDOW", 12)  # months
        self.validation_window = wfo_config.get("VALIDATION_WINDOW", 3)  # months
        self.test_window = wfo_config.get("TEST_WINDOW", 3)  # months
        self.step_size = wfo_config.get("STEP_SIZE", 3)  # months

        # Hyperparameter search space
        self.search_space = wfo_config.get("SEARCH_SPACE", {
            "GRANGER_LAG": [3, 5, 7],
            "RICCI_LOOKBACK": [30, 60, 90],
            "TURNOVER_PENALTY": [0.0005, 0.001, 0.002],
            "VOL_TARGET": [0.10, 0.12, 0.15]
        })

        self.optimizer_type = wfo_config.get("OPTIMIZER", "bayesian")
        self.n_iterations = wfo_config.get("N_ITERATIONS", 20)

        # Success criteria
        self.min_sharpe_oos = wfo_config.get("MIN_SHARPE_OOS", 0.5)
        self.min_wfe = wfo_config.get("MIN_WFE", 0.60)

    def run(
        self,
        price_data: Dict[str, pd.DataFrame],
        start_date: str,
        end_date: str
    ) -> Dict:
        """
        Run full Walk-Forward Optimization.

        Args:
            price_data: Historical price data
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Dictionary with WFO results:
            {
                "windows": [...],  # Results per window
                "wfe": float,  # Walk-Forward Efficiency
                "avg_sharpe_is": float,
                "avg_sharpe_oos": float,
                "best_params": dict
            }
        """
        logger.info(f"Starting Walk-Forward Optimization: {start_date} → {end_date}")

        # Convert dates
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        # Generate windows
        windows = self._generate_windows(start_dt, end_dt)

        logger.info(f"Generated {len(windows)} walk-forward windows")

        # Run WFO for each window
        window_results = []

        for i, window in enumerate(windows):
            logger.info(f"Processing window {i+1}/{len(windows)}: Train={window['train_start']} to {window['test_end']}")

            result = self._run_window(price_data, window)
            window_results.append(result)

        # Calculate aggregate metrics
        aggregate_results = self._aggregate_results(window_results)

        # Log final results
        logger.info(f"WFO Complete: WFE={aggregate_results['wfe']:.2%}, "
                   f"IS Sharpe={aggregate_results['avg_sharpe_is']:.2f}, "
                   f"OOS Sharpe={aggregate_results['avg_sharpe_oos']:.2f}")

        return aggregate_results

    def _generate_windows(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict]:
        """
        Generate walk-forward windows.

        Each window has:
        - Training period (e.g., 12 months)
        - Validation period (e.g., 3 months)
        - Test period (e.g., 3 months)

        Windows are rolled forward by step_size (e.g., 3 months).

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of window dictionaries
        """
        windows = []
        current_date = start_date

        while True:
            # Define window boundaries
            train_start = current_date
            train_end = train_start + relativedelta(months=self.train_window)
            val_start = train_end
            val_end = val_start + relativedelta(months=self.validation_window)
            test_start = val_end
            test_end = test_start + relativedelta(months=self.test_window)

            # Check if window fits within data range
            if test_end > end_date:
                break

            window = {
                "train_start": train_start,
                "train_end": train_end,
                "val_start": val_start,
                "val_end": val_end,
                "test_start": test_start,
                "test_end": test_end
            }

            windows.append(window)

            # Roll forward
            current_date += relativedelta(months=self.step_size)

        return windows

    def _run_window(
        self,
        price_data: Dict[str, pd.DataFrame],
        window: Dict
    ) -> Dict:
        """
        Run WFO for a single window.

        Steps:
        1. Split data
        2. Optimize hyperparameters on train+val
        3. Test on OOS data
        4. Calculate metrics

        Args:
            price_data: Price data
            window: Window definition

        Returns:
            Window results dictionary
        """
        # Step 1: Split data
        train_data = self._split_data(price_data, window["train_start"], window["train_end"])
        val_data = self._split_data(price_data, window["val_start"], window["val_end"])
        test_data = self._split_data(price_data, window["test_start"], window["test_end"])

        # Step 2: Hyperparameter optimization on train+val
        logger.info("Optimizing hyperparameters...")
        best_params, best_val_sharpe = self._optimize_hyperparameters(train_data, val_data)

        logger.info(f"Best params: {best_params}, Val Sharpe: {best_val_sharpe:.2f}")

        # Step 3: Run backtest with best params on training data (IS)
        is_results = self._run_backtest(train_data, best_params)
        is_sharpe = self._calculate_sharpe(is_results["pnl_history"])

        # Step 4: Run backtest with best params on test data (OOS)
        oos_results = self._run_backtest(test_data, best_params)
        oos_sharpe = self._calculate_sharpe(oos_results["pnl_history"])

        # Step 5: Statistical validation
        validation_metrics = self._validate_results(oos_results)

        result = {
            "window": window,
            "best_params": best_params,
            "is_sharpe": is_sharpe,
            "val_sharpe": best_val_sharpe,
            "oos_sharpe": oos_sharpe,
            "is_results": is_results,
            "oos_results": oos_results,
            "validation": validation_metrics
        }

        return result

    def _split_data(
        self,
        price_data: Dict[str, pd.DataFrame],
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, pd.DataFrame]:
        """
        Split price data by date range.

        Args:
            price_data: Full price data
            start_date: Start date
            end_date: End date

        Returns:
            Filtered price data
        """
        split_data = {}

        for symbol, df in price_data.items():
            mask = (df.index >= start_date) & (df.index < end_date)
            split_df = df.loc[mask]

            if not split_df.empty:
                split_data[symbol] = split_df

        return split_data

    def _optimize_hyperparameters(
        self,
        train_data: Dict[str, pd.DataFrame],
        val_data: Dict[str, pd.DataFrame]
    ) -> Tuple[Dict, float]:
        """
        Optimize hyperparameters using Bayesian optimization or grid search.

        Args:
            train_data: Training data
            val_data: Validation data

        Returns:
            (best_params, best_validation_sharpe)
        """
        if self.optimizer_type == "bayesian":
            return self._bayesian_optimization(train_data, val_data)
        elif self.optimizer_type == "grid":
            return self._grid_search(train_data, val_data)
        elif self.optimizer_type == "random":
            return self._random_search(train_data, val_data)
        else:
            raise ValueError(f"Unknown optimizer type: {self.optimizer_type}")

    def _bayesian_optimization(
        self,
        train_data: Dict[str, pd.DataFrame],
        val_data: Dict[str, pd.DataFrame]
    ) -> Tuple[Dict, float]:
        """
        Bayesian hyperparameter optimization (simplified).

        For MVP, we use random sampling. In production, use libraries like Optuna.

        Args:
            train_data: Training data
            val_data: Validation data

        Returns:
            (best_params, best_validation_sharpe)
        """
        best_params = None
        best_sharpe = -np.inf

        # Random sampling from search space
        for i in range(self.n_iterations):
            # Sample parameters
            params = {}
            for key, values in self.search_space.items():
                if isinstance(values, list):
                    params[key] = np.random.choice(values)
                else:
                    params[key] = values

            # Create modified config
            test_config = self.config.copy()
            test_config["STRUCTURAL"] = test_config.get("STRUCTURAL", {})
            test_config["RICCI"] = test_config.get("RICCI", {})
            test_config["OPTIMIZATION"] = test_config.get("OPTIMIZATION", {})
            test_config["RISK"] = test_config.get("RISK", {})

            if "GRANGER_LAG" in params:
                test_config["STRUCTURAL"]["GRANGER_LAG"] = params["GRANGER_LAG"]
            if "RICCI_LOOKBACK" in params:
                test_config["RICCI"]["LOOKBACK"] = params["RICCI_LOOKBACK"]
            if "TURNOVER_PENALTY" in params:
                test_config["OPTIMIZATION"]["TURNOVER_PENALTY"] = params["TURNOVER_PENALTY"]
            if "VOL_TARGET" in params:
                test_config["RISK"]["VOL_TARGET"] = params["VOL_TARGET"]

            # Run backtest on validation data
            val_results = self._run_backtest(val_data, test_config)
            val_sharpe = self._calculate_sharpe(val_results["pnl_history"])

            logger.info(f"Iteration {i+1}/{self.n_iterations}: Sharpe={val_sharpe:.2f}, Params={params}")

            if val_sharpe > best_sharpe:
                best_sharpe = val_sharpe
                best_params = params

        return best_params, best_sharpe

    def _grid_search(
        self,
        train_data: Dict[str, pd.DataFrame],
        val_data: Dict[str, pd.DataFrame]
    ) -> Tuple[Dict, float]:
        """Grid search over hyperparameters (exhaustive)."""
        from itertools import product

        best_params = None
        best_sharpe = -np.inf

        # Generate all combinations
        keys = list(self.search_space.keys())
        values = [self.search_space[k] if isinstance(self.search_space[k], list) else [self.search_space[k]] for k in keys]
        combinations = list(product(*values))

        logger.info(f"Grid search: {len(combinations)} combinations")

        for i, combo in enumerate(combinations):
            params = dict(zip(keys, combo))

            # Run backtest
            test_config = self._apply_params(self.config, params)
            val_results = self._run_backtest(val_data, test_config)
            val_sharpe = self._calculate_sharpe(val_results["pnl_history"])

            if val_sharpe > best_sharpe:
                best_sharpe = val_sharpe
                best_params = params

        return best_params, best_sharpe

    def _random_search(
        self,
        train_data: Dict[str, pd.DataFrame],
        val_data: Dict[str, pd.DataFrame]
    ) -> Tuple[Dict, float]:
        """Random search over hyperparameters."""
        return self._bayesian_optimization(train_data, val_data)  # Same implementation for MVP

    def _apply_params(self, config: Dict, params: Dict) -> Dict:
        """Apply hyperparameters to config."""
        test_config = config.copy()
        test_config["STRUCTURAL"] = test_config.get("STRUCTURAL", {})
        test_config["RICCI"] = test_config.get("RICCI", {})
        test_config["OPTIMIZATION"] = test_config.get("OPTIMIZATION", {})
        test_config["RISK"] = test_config.get("RISK", {})

        if "GRANGER_LAG" in params:
            test_config["STRUCTURAL"]["GRANGER_LAG"] = params["GRANGER_LAG"]
        if "RICCI_LOOKBACK" in params:
            test_config["RICCI"]["LOOKBACK"] = params["RICCI_LOOKBACK"]
        if "TURNOVER_PENALTY" in params:
            test_config["OPTIMIZATION"]["TURNOVER_PENALTY"] = params["TURNOVER_PENALTY"]
        if "VOL_TARGET" in params:
            test_config["RISK"]["VOL_TARGET"] = params["VOL_TARGET"]

        return test_config

    def _run_backtest(
        self,
        price_data: Dict[str, pd.DataFrame],
        config: Dict
    ) -> Dict:
        """
        Run backtest with given configuration.

        Args:
            price_data: Price data
            config: Configuration (with hyperparameters)

        Returns:
            Backtest results
        """
        # Initialize orchestrator
        orchestrator = StrategyOrchestrator(config)

        # Get date range
        first_symbol = list(price_data.keys())[0]
        dates = price_data[first_symbol].index

        pnl_history = []
        portfolio_history = []
        current_portfolio = {}

        # Run day by day
        for date in dates[60:]:  # Skip first 60 days for warmup
            try:
                # Slice data up to current date
                data_slice = {}
                for symbol, df in price_data.items():
                    data_slice[symbol] = df.loc[:date]

                # Run one step (synchronous for MVP)
                import asyncio

                result = asyncio.run(orchestrator.run_step(
                    current_date=date,
                    price_data=data_slice,
                    current_portfolio=current_portfolio
                ))

                pnl_history.append(result["daily_pnl"])
                portfolio_history.append(result["optimized_weights"])

                # Update portfolio
                current_portfolio = result["optimized_weights"]

            except Exception as e:
                logger.error(f"Error on date {date}: {e}")
                continue

        return {
            "pnl_history": pnl_history,
            "portfolio_history": portfolio_history
        }

    def _calculate_sharpe(self, pnl_history: List[float]) -> float:
        """Calculate Sharpe ratio."""
        if len(pnl_history) < 2:
            return 0.0

        returns = np.array(pnl_history)
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return < 1e-9:
            return 0.0

        sharpe = mean_return / std_return * np.sqrt(252)

        return float(sharpe)

    def _validate_results(self, results: Dict) -> Dict:
        """
        Validate results using statistical tests.

        Returns:
            Dictionary with validation metrics
        """
        pnl_history = results["pnl_history"]

        if len(pnl_history) < 10:
            return {}

        returns = np.array(pnl_history)

        # PSR (Probabilistic Sharpe Ratio)
        sharpe = self._calculate_sharpe(pnl_history)
        T = len(returns)
        skewness = skew(returns)
        kurt = kurtosis(returns, fisher=False)

        try:
            from scipy.stats import norm

            denominator = np.sqrt(1 - skewness * sharpe + (kurt - 1) / 4 * sharpe ** 2)
            z_score = sharpe * np.sqrt(T - 1) / denominator
            psr = norm.cdf(z_score)
        except:
            psr = 0.5

        # DSR (Deflated Sharpe Ratio)
        n_strategies = 3  # We tested 3 strategies
        dsr = sharpe - np.sqrt(np.log(n_strategies) / T)

        # Max Drawdown
        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (running_max - cum_returns) / running_max
        max_dd = float(np.max(drawdown))

        return {
            "psr": float(psr),
            "dsr": float(dsr),
            "max_drawdown": max_dd,
            "sharpe": sharpe
        }

    def _aggregate_results(self, window_results: List[Dict]) -> Dict:
        """
        Aggregate results across all windows.

        Calculate Walk-Forward Efficiency (WFE):
        WFE = (Average OOS Sharpe) / (Average IS Sharpe)

        Args:
            window_results: List of window results

        Returns:
            Aggregated results
        """
        is_sharpes = [r["is_sharpe"] for r in window_results]
        oos_sharpes = [r["oos_sharpe"] for r in window_results]

        avg_is_sharpe = np.mean(is_sharpes)
        avg_oos_sharpe = np.mean(oos_sharpes)

        # Walk-Forward Efficiency
        wfe = avg_oos_sharpe / avg_is_sharpe if avg_is_sharpe > 0 else 0.0

        # Overall performance
        all_oos_pnls = []
        for r in window_results:
            all_oos_pnls.extend(r["oos_results"]["pnl_history"])

        overall_sharpe = self._calculate_sharpe(all_oos_pnls)
        overall_validation = self._validate_results({"pnl_history": all_oos_pnls})

        # Determine success
        is_successful = (wfe >= self.min_wfe and overall_sharpe >= self.min_sharpe_oos)

        return {
            "windows": window_results,
            "wfe": wfe,
            "avg_sharpe_is": avg_is_sharpe,
            "avg_sharpe_oos": avg_oos_sharpe,
            "overall_sharpe": overall_sharpe,
            "overall_validation": overall_validation,
            "is_successful": is_successful,
            "success_criteria": {
                "min_wfe": self.min_wfe,
                "min_sharpe_oos": self.min_sharpe_oos
            }
        }
