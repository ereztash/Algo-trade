"""
Download Historical Data
========================

Script to download historical price data for backtesting.

Uses yfinance as fallback for MVP. In production, use IBKR API.

Usage:
------
    python scripts/download_data.py --start 2022-01-01 --end 2024-12-31 --output data/historical.pkl
"""

import argparse
import pandas as pd
import logging
from datetime import datetime
from pathlib import Path

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("Warning: yfinance not available. Install with: pip install yfinance")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_symbol(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Download historical data for a symbol.

    Args:
        symbol: Stock symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        DataFrame with OHLCV data
    """
    if not YFINANCE_AVAILABLE:
        raise RuntimeError("yfinance is not available")

    logger.info(f"Downloading {symbol}...")

    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)

    if df.empty:
        logger.warning(f"No data found for {symbol}")
        return pd.DataFrame()

    # Rename columns to match our format
    df = df.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })

    # Keep only relevant columns
    df = df[["open", "high", "low", "close", "volume"]]

    logger.info(f"Downloaded {len(df)} bars for {symbol}")

    return df


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Download historical data")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", default="data/historical.pkl", help="Output file")
    parser.add_argument("--symbols", nargs="+", help="Symbols to download (optional)")

    args = parser.parse_args()

    # Default symbols
    if args.symbols:
        symbols = args.symbols
    else:
        symbols = [
            # Structural Arbitrage
            "REMX",  # VanEck Rare Earth/Strategic Metals ETF
            "URNM",  # Sprott Uranium Miners ETF
            "QTUM",  # Defiance Quantum ETF

            # Ricci Curvature (market indices)
            "SPY",   # S&P 500
            "QQQ",   # Nasdaq 100
            "IWM",   # Russell 2000
            "DIA",   # Dow Jones

            # Optional: Add specific biotech for event-driven
            # "ABCD", # Add manually after identifying FDA calendar events
        ]

    # Download data
    data = {}

    for symbol in symbols:
        try:
            df = download_symbol(symbol, args.start, args.end)

            if not df.empty:
                data[symbol] = df

        except Exception as e:
            logger.error(f"Error downloading {symbol}: {e}")

    # Save to file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pd.to_pickle(data, output_path)

    logger.info(f"Saved {len(data)} symbols to {output_path}")

    # Print summary
    print("\n" + "="*60)
    print("Download Summary")
    print("="*60)

    for symbol, df in data.items():
        start = df.index[0].strftime("%Y-%m-%d")
        end = df.index[-1].strftime("%Y-%m-%d")
        print(f"{symbol:6s}: {len(df):4d} bars  ({start} to {end})")

    print("="*60)


if __name__ == "__main__":
    main()
