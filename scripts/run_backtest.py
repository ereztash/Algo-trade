"""
Run Backtest
============

Main script to run backtest for AlgoX MVP.

Usage:
------
    # Simple backtest
    python scripts/run_backtest.py --config config/mvp_config.yaml --start 2022-01-01 --end 2024-12-31

    # Walk-Forward Optimization
    python scripts/run_backtest.py --config config/mvp_config.yaml --start 2022-01-01 --end 2024-12-31 --wfo

    # With custom data
    python scripts/run_backtest.py --config config/mvp_config.yaml --data data/historical.pkl --wfo
"""

import argparse
import yaml
import pandas as pd
import numpy as np
from pathlib import Path
import logging
from datetime import datetime
import asyncio
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from algox.strategy.orchestrator import StrategyOrchestrator
from algox.strategy.wfo import WalkForwardOptimizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    logger.info(f"Loaded config from {config_path}")
    return config


def load_data(data_path: str) -> dict:
    """Load historical data."""
    if not Path(data_path).exists():
        raise FileNotFoundError(f"Data file not found: {data_path}")

    data = pd.read_pickle(data_path)

    logger.info(f"Loaded data for {len(data)} symbols from {data_path}")

    return data


def run_simple_backtest(
    price_data: dict,
    config: dict,
    start_date: str,
    end_date: str
) -> dict:
    """
    Run simple backtest without optimization.

    Args:
        price_data: Price data dictionary
        config: Configuration
        start_date: Start date
        end_date: End date

    Returns:
        Backtest results
    """
    logger.info(f"Running simple backtest: {start_date} → {end_date}")

    # Initialize orchestrator
    orchestrator = StrategyOrchestrator(config)

    # Filter data by date range
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)

    filtered_data = {}
    for symbol, df in price_data.items():
        mask = (df.index >= start_dt) & (df.index <= end_dt)
        filtered_df = df.loc[mask]

        if not filtered_df.empty:
            filtered_data[symbol] = filtered_df

    # Get date range
    first_symbol = list(filtered_data.keys())[0]
    dates = filtered_data[first_symbol].index

    # Run backtest
    results = []
    current_portfolio = {}
    capital = config.get("CAPITAL", {}).get("INITIAL", 10000.0)

    for i, date in enumerate(dates[60:]):  # Skip first 60 days for warmup
        if i % 10 == 0:
            logger.info(f"Processing {i}/{len(dates)-60}: {date.strftime('%Y-%m-%d')}")

        try:
            # Slice data up to current date
            data_slice = {}
            for symbol, df in filtered_data.items():
                data_slice[symbol] = df.loc[:date]

            # Run one step
            result = asyncio.run(orchestrator.run_step(
                current_date=date,
                price_data=data_slice,
                current_portfolio=current_portfolio,
                capital=capital
            ))

            results.append(result)

            # Update portfolio
            current_portfolio = result["optimized_weights"]

            # Update capital
            capital *= (1 + result["daily_pnl"])

        except Exception as e:
            logger.error(f"Error on date {date}: {e}")
            continue

    # Calculate performance metrics
    pnl_history = [r["daily_pnl"] for r in results]

    total_return = float(np.prod(1 + np.array(pnl_history)) - 1)

    sharpe = np.mean(pnl_history) / np.std(pnl_history) * np.sqrt(252) if len(pnl_history) > 1 else 0.0

    cum_returns = np.cumprod(1 + np.array(pnl_history))
    running_max = np.maximum.accumulate(cum_returns)
    drawdown = (running_max - cum_returns) / running_max
    max_dd = float(np.max(drawdown))

    win_rate = (np.array(pnl_history) > 0).mean()

    summary = {
        "start_date": start_date,
        "end_date": end_date,
        "total_days": len(results),
        "total_return": total_return,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "win_rate": win_rate,
        "final_capital": capital,
        "num_trades": sum(len(r["trades"]) for r in results)
    }

    logger.info("\n" + "="*60)
    logger.info("Backtest Results")
    logger.info("="*60)
    logger.info(f"Total Return:    {total_return:>10.2%}")
    logger.info(f"Sharpe Ratio:    {sharpe:>10.2f}")
    logger.info(f"Max Drawdown:    {max_dd:>10.2%}")
    logger.info(f"Win Rate:        {win_rate:>10.2%}")
    logger.info(f"Final Capital:   ${capital:>10,.2f}")
    logger.info(f"Num Trades:      {summary['num_trades']:>10d}")
    logger.info("="*60)

    return {
        "summary": summary,
        "results": results,
        "pnl_history": pnl_history
    }


def run_wfo_backtest(
    price_data: dict,
    config: dict,
    start_date: str,
    end_date: str
) -> dict:
    """
    Run Walk-Forward Optimization backtest.

    Args:
        price_data: Price data dictionary
        config: Configuration
        start_date: Start date
        end_date: End date

    Returns:
        WFO results
    """
    logger.info(f"Running Walk-Forward Optimization: {start_date} → {end_date}")

    # Initialize WFO
    wfo = WalkForwardOptimizer(config)

    # Run WFO
    results = wfo.run(price_data, start_date, end_date)

    # Print results
    logger.info("\n" + "="*60)
    logger.info("Walk-Forward Optimization Results")
    logger.info("="*60)
    logger.info(f"WFE (Walk-Forward Efficiency): {results['wfe']:>10.2%}")
    logger.info(f"Avg IS Sharpe:                 {results['avg_sharpe_is']:>10.2f}")
    logger.info(f"Avg OOS Sharpe:                {results['avg_sharpe_oos']:>10.2f}")
    logger.info(f"Overall Sharpe:                {results['overall_sharpe']:>10.2f}")
    logger.info(f"Success:                       {results['is_successful']}")
    logger.info("="*60)
    logger.info(f"Success Criteria:")
    logger.info(f"  - WFE > {results['success_criteria']['min_wfe']:.2%}")
    logger.info(f"  - OOS Sharpe > {results['success_criteria']['min_sharpe_oos']:.2f}")
    logger.info("="*60)

    # Print validation metrics
    if "overall_validation" in results and results["overall_validation"]:
        val = results["overall_validation"]
        logger.info("Overall Validation:")
        logger.info(f"  - PSR:           {val.get('psr', 0):>10.2f}")
        logger.info(f"  - DSR:           {val.get('dsr', 0):>10.2f}")
        logger.info(f"  - Max Drawdown:  {val.get('max_drawdown', 0):>10.2%}")
        logger.info("="*60)

    return results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run backtest for AlgoX MVP")
    parser.add_argument("--config", required=True, help="Config file (YAML)")
    parser.add_argument("--data", help="Data file (pickle). If not provided, will download.")
    parser.add_argument("--start", default="2022-01-01", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default="2024-12-31", help="End date (YYYY-MM-DD)")
    parser.add_argument("--wfo", action="store_true", help="Run Walk-Forward Optimization")
    parser.add_argument("--output", help="Output file for results (pickle)")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Load data
    if args.data:
        price_data = load_data(args.data)
    else:
        logger.info("No data file provided. Please download data first:")
        logger.info(f"  python scripts/download_data.py --start {args.start} --end {args.end} --output data/historical.pkl")
        logger.info(f"  Then run this script with --data data/historical.pkl")
        return

    # Run backtest
    if args.wfo:
        results = run_wfo_backtest(price_data, config, args.start, args.end)
    else:
        results = run_simple_backtest(price_data, config, args.start, args.end)

    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        pd.to_pickle(results, output_path)
        logger.info(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
