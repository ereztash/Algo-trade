"""
CLI entry point for the 3-plane trading system orchestrator.

Usage:
    # Dry-run mode (no actual trading, uses paper broker)
    python -m apps.strategy_loop.run --mode dry --config shared/config/config.yaml

    # Pre-live mode (paper trading with live data)
    python -m apps.strategy_loop.run --mode prelive --config shared/config/config.yaml

    # Live mode (real trading)
    python -m apps.strategy_loop.run --mode live --config shared/config/config.yaml

Best Practices:
- All configuration via --config file (not hardcoded)
- Mode switches via --mode flag (dry|prelive|live)
- Structured logging to stdout and file
- Graceful shutdown on SIGINT (Ctrl+C)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import yaml

from apps.strategy_loop.orchestrator import Orchestrator, OrchestratorConfig


def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """
    Configure structured logging.

    Logs to:
    - stdout (console)
    - file (if log_file specified)

    Format: [timestamp] [level] [module] message
    """
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))

    handlers = [console_handler]

    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
    )


def load_config(config_path: str) -> dict:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config.yaml

    Returns:
        Dictionary of configuration values

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
    """
    config_file = Path(config_path)

    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    return config or {}


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="3-Plane Trading System Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run mode (fast, no delays)
  python -m apps.strategy_loop.run --mode dry

  # Pre-live mode (paper trading)
  python -m apps.strategy_loop.run --mode prelive --config shared/config/config.yaml

  # Live mode (real trading)
  python -m apps.strategy_loop.run --mode live --config shared/config/config.yaml --log-level INFO
        """
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["dry", "prelive", "live"],
        default="dry",
        help="Execution mode: dry (testing), prelive (paper), live (real trading)"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="shared/config/config.yaml",
        help="Path to configuration file (YAML)"
    )

    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        default=None,
        help="Override symbols from config (e.g., --symbols AAPL SPY TLT)"
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum iterations (None = infinite). For dry-run, defaults to 1."
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path (optional, logs to stdout by default)"
    )

    return parser.parse_args()


async def main_async() -> int:
    """
    Async main entry point.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    # Parse arguments
    args = parse_args()

    # Setup logging
    setup_logging(log_level=args.log_level, log_file=args.log_file)
    logger = logging.getLogger(__name__)

    try:
        # Load config (if file exists, otherwise use defaults)
        config_dict = {}
        config_path = Path(args.config)
        if config_path.exists():
            config_dict = load_config(args.config)
            logger.info(f"Loaded config from {args.config}")
        else:
            logger.warning(f"Config file not found: {args.config}. Using defaults.")

        # Build orchestrator config
        orchestrator_config = OrchestratorConfig(
            mode=args.mode,
            symbols=args.symbols or config_dict.get("symbols", ["AAPL", "SPY"]),
            max_iterations=args.max_iterations or (1 if args.mode == "dry" else None),
            event_log_path=config_dict.get("event_log_path", "reports/events.jsonl"),
            enable_risk_checks=config_dict.get("enable_risk_checks", True),
            sleep_between_ticks=config_dict.get("sleep_between_ticks", 0.0),
        )

        # Create orchestrator
        orchestrator = Orchestrator(orchestrator_config)

        # In Phase 2, we don't have adapters yet (they're added in Phase 3)
        # For now, just test the pure orchestration loop

        # Run orchestrator
        logger.info(f"Starting orchestrator in {args.mode} mode...")
        await orchestrator.run()

        logger.info("Orchestrator completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        return 130  # Standard exit code for SIGINT

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


def main() -> int:
    """
    Synchronous main entry point (for CLI).

    Returns:
        Exit code (0 = success, 1 = error)
    """
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
