"""CSV/Parquet data source adapter."""

import pandas as pd
from pathlib import Path
from typing import AsyncIterator, List
from datetime import datetime, timezone

from shared.models import Bar


class CSVSource:
    """
    CSV/Parquet data source adapter.

    Reads historical bar data from CSV or Parquet files.
    Implements async iterator for compatibility with orchestrator.
    """

    def __init__(self, file_path: str, symbol_column: str = "symbol"):
        self.file_path = Path(file_path)
        self.symbol_column = symbol_column
        self.data: pd.DataFrame = None

    async def fetch_bars(self) -> AsyncIterator[Bar]:
        """Fetch bars from file (async generator)."""
        # Load data
        if self.file_path.suffix == '.parquet':
            self.data = pd.read_parquet(self.file_path)
        else:
            self.data = pd.read_csv(self.file_path)

        # Yield bars one by one
        for _, row in self.data.iterrows():
            bar = Bar(
                timestamp=pd.to_datetime(row['timestamp']).tz_localize(timezone.utc) if pd.isna(pd.to_datetime(row['timestamp']).tzinfo) else pd.to_datetime(row['timestamp']),
                symbol=row[self.symbol_column],
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
                interval=row.get('interval', '1D')
            )
            yield bar
