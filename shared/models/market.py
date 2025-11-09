"""
Market data models for the 3-plane trading system.

Defines:
- Bar: OHLCV bar data (time-series candles)
- Quote: Bid/ask quotes (Level 1 market data)
- TradeTick: Individual trade executions (time & sales)

All models are:
- Immutable (frozen=True)
- UTC timezone-aware
- Validated for logical consistency (e.g., high >= low)
"""

from datetime import datetime
from typing import Annotated, Optional
from pydantic import Field, field_validator

from shared.models.base import BaseModel, TimestampMixin, SymbolMixin


class Bar(BaseModel, TimestampMixin, SymbolMixin):
    """
    OHLCV bar (candle) for time-series market data.

    Represents aggregated price data over a time interval.
    Used for backtesting, strategy signals, and historical analysis.

    Validation rules:
    - high >= low (always)
    - high >= open, close (always)
    - low <= open, close (always)
    - volume >= 0
    """

    open: Annotated[
        float,
        Field(
            gt=0.0,
            description="Opening price during the bar interval"
        )
    ]

    high: Annotated[
        float,
        Field(
            gt=0.0,
            description="Highest price during the bar interval"
        )
    ]

    low: Annotated[
        float,
        Field(
            gt=0.0,
            description="Lowest price during the bar interval"
        )
    ]

    close: Annotated[
        float,
        Field(
            gt=0.0,
            description="Closing price at the end of the bar interval"
        )
    ]

    volume: Annotated[
        float,
        Field(
            ge=0.0,
            description="Total volume traded during the bar interval"
        )
    ]

    interval: Annotated[
        Optional[str],
        Field(
            default="1D",
            pattern=r"^\d+[smhDWM]$",
            description="Bar interval (e.g., '1m', '5m', '1h', '1D'). s=second, m=minute, h=hour, D=day, W=week, M=month"
        )
    ]

    @field_validator('high')
    @classmethod
    def validate_high_price(cls, v: float, info) -> float:
        """Ensure high is the highest price."""
        if 'low' in info.data and v < info.data['low']:
            raise ValueError(f"High ({v}) must be >= low ({info.data['low']})")
        if 'open' in info.data and v < info.data['open']:
            raise ValueError(f"High ({v}) must be >= open ({info.data['open']})")
        if 'close' in info.data and v < info.data['close']:
            raise ValueError(f"High ({v}) must be >= close ({info.data['close']})")
        return v

    @field_validator('low')
    @classmethod
    def validate_low_price(cls, v: float, info) -> float:
        """Ensure low is the lowest price."""
        if 'open' in info.data and v > info.data['open']:
            raise ValueError(f"Low ({v}) must be <= open ({info.data['open']})")
        if 'close' in info.data and v > info.data['close']:
            raise ValueError(f"Low ({v}) must be <= close ({info.data['close']})")
        return v


class Quote(BaseModel, TimestampMixin, SymbolMixin):
    """
    Bid/ask quote (Level 1 market data).

    Represents the current best bid and ask prices with sizes.
    Used for live trading, spread analysis, and liquidity monitoring.

    Validation rules:
    - ask > bid (no crossed market)
    - bid_size, ask_size > 0
    """

    bid: Annotated[
        float,
        Field(
            gt=0.0,
            description="Best bid price (highest price buyers are willing to pay)"
        )
    ]

    ask: Annotated[
        float,
        Field(
            gt=0.0,
            description="Best ask price (lowest price sellers are willing to accept)"
        )
    ]

    bid_size: Annotated[
        float,
        Field(
            gt=0.0,
            description="Size available at the bid price"
        )
    ]

    ask_size: Annotated[
        float,
        Field(
            gt=0.0,
            description="Size available at the ask price"
        )
    ]

    exchange: Annotated[
        Optional[str],
        Field(
            default=None,
            max_length=10,
            description="Exchange code (e.g., 'NASDAQ', 'NYSE', 'SMART')"
        )
    ]

    @field_validator('ask')
    @classmethod
    def validate_no_crossed_market(cls, v: float, info) -> float:
        """Ensure ask > bid (no crossed market)."""
        if 'bid' in info.data and v <= info.data['bid']:
            raise ValueError(
                f"Ask ({v}) must be > bid ({info.data['bid']}). "
                "Crossed market detected (indicates bad data or halted symbol)."
            )
        return v

    @property
    def mid(self) -> float:
        """Calculate mid-price (average of bid and ask)."""
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread in price units."""
        return self.ask - self.bid

    @property
    def spread_bps(self) -> float:
        """Calculate bid-ask spread in basis points."""
        return (self.spread / self.mid) * 10000.0


class TradeTick(BaseModel, TimestampMixin, SymbolMixin):
    """
    Individual trade tick (time & sales).

    Represents a single trade execution.
    Used for microstructure analysis, volume profiling, and tick data strategies.

    Validation rules:
    - price > 0
    - size > 0
    """

    price: Annotated[
        float,
        Field(
            gt=0.0,
            description="Execution price of the trade"
        )
    ]

    size: Annotated[
        float,
        Field(
            gt=0.0,
            description="Size (quantity) of the trade"
        )
    ]

    side: Annotated[
        Optional[str],
        Field(
            default=None,
            pattern=r"^(BUY|SELL|UNKNOWN)$",
            description="Trade aggressor side: BUY (uptick), SELL (downtick), UNKNOWN"
        )
    ]

    exchange: Annotated[
        Optional[str],
        Field(
            default=None,
            max_length=10,
            description="Exchange where the trade occurred"
        )
    ]

    trade_id: Annotated[
        Optional[str],
        Field(
            default=None,
            max_length=50,
            description="Unique trade identifier (if provided by exchange)"
        )
    ]
