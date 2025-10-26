"""
Data normalization module for Algo-trade.
מודול נרמול נתונים עבור Algo-trade.
"""

from typing import Any, Dict, Optional
from datetime import datetime
from uuid import UUID, uuid4

try:
    from contracts.validators import BarEvent, TickEvent
    VALIDATORS_AVAILABLE = True
except ImportError:
    VALIDATORS_AVAILABLE = False
    BarEvent = dict
    TickEvent = dict


def normalize(raw: Any, ingest_id: Optional[UUID] = None) -> Optional[Any]:
    """
    Normalize raw market data into BarEvent or TickEvent.
    נרמול נתוני שוק גולמיים ל-BarEvent או TickEvent.

    Args:
        raw: Raw data object (could be dict, API response, etc.)
        ingest_id: Unique ingestion ID

    Returns:
        Normalized BarEvent or TickEvent, or None if unable to normalize
    """
    if ingest_id is None:
        ingest_id = uuid4()

    # Handle dict input
    if isinstance(raw, dict):
        return normalize_dict(raw, ingest_id)

    # Handle object with attributes
    if hasattr(raw, '__dict__'):
        return normalize_object(raw, ingest_id)

    # Unable to normalize
    return None


def normalize_dict(data: Dict[str, Any], ingest_id: UUID) -> Optional[Any]:
    """
    Normalize dictionary data.
    נרמול נתונים מסוג dictionary.

    Args:
        data: Raw data dictionary
        ingest_id: Ingestion ID

    Returns:
        BarEvent, TickEvent, or None
    """
    data_type = data.get('type', '').lower()

    if data_type == 'bar' or 'open' in data:
        return normalize_bar(data, ingest_id)
    elif data_type == 'tick' or 'bid' in data:
        return normalize_tick(data, ingest_id)

    return None


def normalize_object(obj: Any, ingest_id: UUID) -> Optional[Any]:
    """
    Normalize object with attributes.
    נרמול אובייקט עם תכונות.

    Args:
        obj: Raw data object
        ingest_id: Ingestion ID

    Returns:
        BarEvent, TickEvent, or None
    """
    # Convert object to dict
    if hasattr(obj, 'dict'):
        data = obj.dict()
    elif hasattr(obj, '__dict__'):
        data = obj.__dict__
    else:
        return None

    return normalize_dict(data, ingest_id)


def normalize_bar(data: Dict[str, Any], ingest_id: UUID) -> Any:
    """
    Normalize bar data to BarEvent.
    נרמול נתוני בר ל-BarEvent.

    Args:
        data: Raw bar data
        ingest_id: Ingestion ID

    Returns:
        BarEvent
    """
    # Extract timestamp
    ts_utc = extract_timestamp(data)

    # Extract OHLCV
    bar_data = {
        'o': data.get('open', data.get('o', 0.0)),
        'h': data.get('high', data.get('h', 0.0)),
        'l': data.get('low', data.get('l', 0.0)),
        'c': data.get('close', data.get('c', 0.0)),
        'v': data.get('volume', data.get('v', 0)),
    }

    # Extract contract info
    symbol = data.get('symbol', data.get('ticker', 'UNKNOWN'))
    conid = data.get('conid', data.get('conId', 0))
    exchange = data.get('exchange', data.get('primary_exchange', 'UNKNOWN'))

    # Determine source
    src = data.get('src', data.get('source', 'ibkr_rt'))

    # Adjustment flags
    adj_flags = data.get('adj_flags', {'split': False, 'dividend': False})

    # Create BarEvent
    bar_event = {
        'schema': 1,
        'ts_utc': ts_utc,
        'tz': 'UTC',
        'conid': conid,
        'symbol': symbol,
        'primary_exchange': exchange,
        'rth_flag': data.get('rth_flag', data.get('useRTH', True)),
        'bar': bar_data,
        'src': src,
        'adj_flags': adj_flags,
        'ingest_id': ingest_id,
    }

    if VALIDATORS_AVAILABLE:
        return BarEvent(**bar_event)
    return bar_event


def normalize_tick(data: Dict[str, Any], ingest_id: UUID) -> Any:
    """
    Normalize tick data to TickEvent.
    נרמול נתוני טיק ל-TickEvent.

    Args:
        data: Raw tick data
        ingest_id: Ingestion ID

    Returns:
        TickEvent
    """
    # Extract timestamp
    ts_utc = extract_timestamp(data)

    # Extract contract info
    conid = data.get('conid', data.get('conId', 0))

    # Extract quote data
    bid = data.get('bid', data.get('bidPrice', 0.0))
    ask = data.get('ask', data.get('askPrice', 0.0))
    bid_sz = data.get('bid_sz', data.get('bidSize', 0.0))
    ask_sz = data.get('ask_sz', data.get('askSize', 0.0))
    last = data.get('last', data.get('lastPrice', 0.0))
    last_sz = data.get('last_sz', data.get('lastSize', 0.0))

    # Level 2 data (optional)
    level2 = data.get('level2', data.get('depth', None))

    # Determine source
    src = data.get('src', data.get('source', 'ibkr_rt'))

    # Create TickEvent
    tick_event = {
        'schema': 1,
        'ts_utc': ts_utc,
        'conid': conid,
        'bid': bid,
        'ask': ask,
        'bid_sz': bid_sz,
        'ask_sz': ask_sz,
        'last': last,
        'last_sz': last_sz,
        'level2': level2,
        'src': src,
        'ingest_id': ingest_id,
    }

    if VALIDATORS_AVAILABLE:
        return TickEvent(**tick_event)
    return tick_event


def extract_timestamp(data: Dict[str, Any]) -> float:
    """
    Extract timestamp from data.
    חילוץ חותמת זמן מנתונים.

    Args:
        data: Raw data

    Returns:
        Unix timestamp (UTC)
    """
    # Try various timestamp fields
    ts = data.get('ts_utc', data.get('timestamp', data.get('time', data.get('date'))))

    if ts is None:
        # Use current time as fallback
        return datetime.utcnow().timestamp()

    # Handle different timestamp formats
    if isinstance(ts, (int, float)):
        # Already a timestamp
        return float(ts)
    elif isinstance(ts, str):
        # Parse ISO format or other common formats
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.timestamp()
        except (ValueError, AttributeError):
            # Fallback to current time
            return datetime.utcnow().timestamp()
    elif isinstance(ts, datetime):
        return ts.timestamp()
    else:
        return datetime.utcnow().timestamp()


# Convenience functions

def normalize_ibkr_bar(bar: Any, contract: Any, ingest_id: Optional[UUID] = None) -> Any:
    """
    Normalize IBKR bar data.
    נרמול נתוני בר של IBKR.

    Args:
        bar: IBKR Bar object
        contract: IBKR Contract object
        ingest_id: Ingestion ID

    Returns:
        BarEvent
    """
    data = {
        'type': 'bar',
        'symbol': getattr(contract, 'symbol', 'UNKNOWN'),
        'conid': getattr(contract, 'conId', 0),
        'exchange': getattr(contract, 'primaryExchange', getattr(contract, 'exchange', 'UNKNOWN')),
        'date': getattr(bar, 'date', None),
        'open': getattr(bar, 'open', 0.0),
        'high': getattr(bar, 'high', 0.0),
        'low': getattr(bar, 'low', 0.0),
        'close': getattr(bar, 'close', 0.0),
        'volume': getattr(bar, 'volume', 0),
        'src': 'ibkr_hist',
    }

    return normalize(data, ingest_id)


def normalize_ibkr_ticker(ticker: Any, ingest_id: Optional[UUID] = None) -> Any:
    """
    Normalize IBKR ticker data.
    נרמול נתוני טיקר של IBKR.

    Args:
        ticker: IBKR Ticker object
        ingest_id: Ingestion ID

    Returns:
        TickEvent
    """
    data = {
        'type': 'tick',
        'conid': getattr(ticker.contract, 'conId', 0),
        'time': getattr(ticker, 'time', None),
        'bid': getattr(ticker, 'bid', 0.0),
        'ask': getattr(ticker, 'ask', 0.0),
        'bid_sz': getattr(ticker, 'bidSize', 0.0),
        'ask_sz': getattr(ticker, 'askSize', 0.0),
        'last': getattr(ticker, 'last', 0.0),
        'last_sz': getattr(ticker, 'lastSize', 0.0),
        'src': 'ibkr_rt',
    }

    return normalize(data, ingest_id)
