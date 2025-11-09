"""
Data Normalization - נרמול נתונים raw ל-contract events
מטרה: המרת נתונים raw מ-IBKR ל-BarEvent/TickEvent תקניים
"""

import logging
from typing import Any, Optional, Union
from datetime import datetime
from uuid import UUID
from contracts.validators import BarEvent, TickEvent

logger = logging.getLogger(__name__)


def normalize(raw: Any, ingest_id: UUID) -> Optional[Union[BarEvent, TickEvent]]:
    """
    נרמול נתונים raw ל-BarEvent או TickEvent בהתאם ל-contract.

    Args:
        raw: Raw data object מ-IBKR (dict או object)
        ingest_id: Unique ID של ingestion

    Returns:
        BarEvent או TickEvent, או None אם הנתונים לא תקינים
    """
    try:
        # Determine type (bar vs tick)
        event_type = _detect_event_type(raw)

        if event_type == 'bar':
            return _normalize_bar(raw, ingest_id)
        elif event_type == 'tick':
            return _normalize_tick(raw, ingest_id)
        else:
            logger.warning(f"Unknown event type: {raw}")
            return None

    except Exception as e:
        logger.error(f"Error normalizing event: {e}")
        logger.debug(f"Raw data: {raw}")
        return None


def _detect_event_type(raw: Any) -> Optional[str]:
    """
    זיהוי סוג event (bar או tick).

    Args:
        raw: Raw data

    Returns:
        'bar', 'tick', או None
    """
    # Check for explicit type field
    if hasattr(raw, 'type'):
        return raw.type

    if isinstance(raw, dict) and 'type' in raw:
        return raw['type']

    # Detect based on fields
    # Bar has: open, high, low, close, volume
    # Tick has: bid, ask, last

    if hasattr(raw, 'open') and hasattr(raw, 'high') and hasattr(raw, 'close'):
        return 'bar'

    if isinstance(raw, dict):
        if all(k in raw for k in ['open', 'high', 'low', 'close']):
            return 'bar'
        if any(k in raw for k in ['bid', 'ask', 'last']):
            return 'tick'

    # Check object attributes
    if hasattr(raw, 'bid') or hasattr(raw, 'ask') or hasattr(raw, 'last'):
        return 'tick'

    logger.warning(f"Could not detect event type from raw data: {type(raw)}")
    return None


def _normalize_bar(raw: Any, ingest_id: UUID) -> Optional[BarEvent]:
    """
    נרמול bar event.

    Args:
        raw: Raw bar data
        ingest_id: Ingestion ID

    Returns:
        BarEvent או None
    """
    try:
        # Extract fields (support both dict and object)
        def get_field(obj, field, default=None):
            if isinstance(obj, dict):
                return obj.get(field, default)
            return getattr(obj, field, default)

        # Required fields
        timestamp = get_field(raw, 'timestamp') or get_field(raw, 'ts_utc') or get_field(raw, 'time')
        symbol = get_field(raw, 'symbol')
        conid = get_field(raw, 'conid')
        open_price = get_field(raw, 'open')
        high = get_field(raw, 'high')
        low = get_field(raw, 'low')
        close = get_field(raw, 'close')
        volume = get_field(raw, 'volume', 0)

        # Validate required fields
        if any(x is None for x in [timestamp, symbol, conid, open_price, high, low, close]):
            logger.warning(f"Bar missing required fields: {raw}")
            return None

        # Convert timestamp to float (Unix timestamp)
        if isinstance(timestamp, datetime):
            ts_utc = timestamp.timestamp()
        elif isinstance(timestamp, str):
            ts_utc = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
        else:
            ts_utc = float(timestamp)

        # Optional fields
        primary_exchange = get_field(raw, 'primary_exchange', 'SMART')
        rth_flag = get_field(raw, 'rth_flag', True)
        src = get_field(raw, 'src', 'ibkr_hist')

        # Create BarEvent
        bar_event = BarEvent(
            schema=1,
            ts_utc=ts_utc,
            tz='UTC',
            conid=int(conid),
            symbol=str(symbol),
            primary_exchange=primary_exchange,
            rth_flag=rth_flag,
            bar={
                'o': float(open_price),
                'h': float(high),
                'l': float(low),
                'c': float(close),
                'v': int(volume)
            },
            src=src,
            adj_flags={'split': False, 'dividend': False},
            ingest_id=ingest_id
        )

        logger.debug(f"Normalized BarEvent: {symbol} @ {ts_utc}")
        return bar_event

    except Exception as e:
        logger.error(f"Error normalizing bar: {e}")
        logger.debug(f"Raw bar data: {raw}")
        return None


def _normalize_tick(raw: Any, ingest_id: UUID) -> Optional[TickEvent]:
    """
    נרמול tick event.

    Args:
        raw: Raw tick data
        ingest_id: Ingestion ID

    Returns:
        TickEvent או None
    """
    try:
        # Extract fields
        def get_field(obj, field, default=None):
            if isinstance(obj, dict):
                return obj.get(field, default)
            return getattr(obj, field, default)

        # Required fields
        timestamp = get_field(raw, 'timestamp') or get_field(raw, 'ts_utc') or get_field(raw, 'time')
        conid = get_field(raw, 'conid')
        bid = get_field(raw, 'bid')
        ask = get_field(raw, 'ask')
        last = get_field(raw, 'last')

        # Validate required fields
        if any(x is None for x in [timestamp, conid]):
            logger.warning(f"Tick missing required fields: {raw}")
            return None

        # Convert timestamp
        if isinstance(timestamp, datetime):
            ts_utc = timestamp.timestamp()
        elif isinstance(timestamp, str):
            ts_utc = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
        else:
            ts_utc = float(timestamp)

        # Optional fields (with defaults)
        bid_sz = get_field(raw, 'bid_sz') or get_field(raw, 'bid_size', 0.0)
        ask_sz = get_field(raw, 'ask_sz') or get_field(raw, 'ask_size', 0.0)
        last_sz = get_field(raw, 'last_sz') or get_field(raw, 'last_size', 0.0)
        level2 = get_field(raw, 'level2')
        src = get_field(raw, 'src', 'ibkr_rt')

        # Create TickEvent
        tick_event = TickEvent(
            schema=1,
            ts_utc=ts_utc,
            conid=int(conid),
            bid=float(bid) if bid is not None else 0.0,
            ask=float(ask) if ask is not None else 0.0,
            bid_sz=float(bid_sz),
            ask_sz=float(ask_sz),
            last=float(last) if last is not None else 0.0,
            last_sz=float(last_sz),
            level2=level2,
            src=src,
            ingest_id=ingest_id
        )

        logger.debug(f"Normalized TickEvent: conid={conid} @ {ts_utc}")
        return tick_event

    except Exception as e:
        logger.error(f"Error normalizing tick: {e}")
        logger.debug(f"Raw tick data: {raw}")
        return None


def is_bar(event: Any) -> bool:
    """
    בדיקה האם event הוא BarEvent.

    Args:
        event: Event object

    Returns:
        bool: True אם BarEvent
    """
    return isinstance(event, BarEvent)


def is_tick(event: Any) -> bool:
    """
    בדיקה האם event הוא TickEvent.

    Args:
        event: Event object

    Returns:
        bool: True אם TickEvent
    """
    return isinstance(event, TickEvent)
