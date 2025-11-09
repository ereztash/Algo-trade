"""
OFI Calculator - חישוב Order Flow Imbalance מ-quotes
מטרה: חישוב OFI (מדד לחץ קנייה/מכירה) מנתוני bid/ask
"""

import logging
from typing import Dict, Any, Optional
from collections import deque
from datetime import datetime
import numpy as np
from contracts.validators import OFIEvent

logger = logging.getLogger(__name__)


class OFICalculator:
    """
    מחשב Order Flow Imbalance (OFI) מ-tick data.

    OFI מודד את חוסר האיזון בין לחץ קנייה למכירה:
    - OFI > 0: לחץ קנייה (buying pressure)
    - OFI < 0: לחץ מכירה (selling pressure)
    - OFI ≈ 0: איזון

    נוסחה:
    OFI = Δ(bid_size * I{bid_up}) - Δ(ask_size * I{ask_down})

    כאשר:
    - I{bid_up}: indicator שה-bid עלה
    - I{ask_down}: indicator שה-ask ירד
    - Δ: שינוי מהtick הקודם
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        אתחול OFI Calculator.

        Args:
            cfg: Config dictionary עם:
                - lookback_ticks: מספר ticks לlookback (default: 10)
                - normalize: האם לנרמל OFI ל-z-score (default: True)
                - window_size: גודל window לz-score (default: 100)
        """
        self.cfg = cfg
        self.lookback_ticks = cfg.get('lookback_ticks', 10)
        self.normalize = cfg.get('normalize', True)
        self.window_size = cfg.get('window_size', 100)

        # State per symbol (previous tick)
        self.prev_ticks: Dict[int, Dict[str, Any]] = {}  # conid -> prev_tick

        # OFI history per symbol (for z-score normalization)
        self.ofi_history: Dict[int, deque] = {}  # conid -> deque of OFI values

        # Statistics
        self.total_ticks_processed = 0
        self.ofi_events_generated = 0

        logger.info(
            f"OFICalculator initialized: lookback={self.lookback_ticks}, "
            f"normalize={self.normalize}, window_size={self.window_size}"
        )

    def on_tick(self, tick: Any) -> Optional[OFIEvent]:
        """
        עיבוד tick חדש וחישוב OFI.

        Args:
            tick: TickEvent object (עם bid, ask, bid_sz, ask_sz, ts_utc, conid)

        Returns:
            OFIEvent: event עם OFI z-score, או None אם אין מספיק נתונים
        """
        self.total_ticks_processed += 1

        # חלץ שדות נדרשים
        conid = getattr(tick, 'conid', None)
        if conid is None:
            logger.warning("Tick missing conid, skipping OFI calculation")
            return None

        bid = getattr(tick, 'bid', None)
        ask = getattr(tick, 'ask', None)
        bid_sz = getattr(tick, 'bid_sz', None)
        ask_sz = getattr(tick, 'ask_sz', None)
        ts_utc = getattr(tick, 'ts_utc', None)

        # בדוק שיש כל הנתונים
        if any(x is None for x in [bid, ask, bid_sz, ask_sz]):
            logger.debug(f"Tick missing required fields for OFI calculation: conid={conid}")
            return None

        # קבל tick קודם
        prev_tick = self.prev_ticks.get(conid)

        # אם אין tick קודם - שמור והמשך
        if prev_tick is None:
            self.prev_ticks[conid] = {
                'bid': bid,
                'ask': ask,
                'bid_sz': bid_sz,
                'ask_sz': ask_sz,
                'ts_utc': ts_utc
            }
            logger.debug(f"First tick for conid={conid}, storing and skipping OFI")
            return None

        # חשב OFI
        ofi_raw = self._compute_ofi(
            bid, ask, bid_sz, ask_sz,
            prev_tick['bid'], prev_tick['ask'],
            prev_tick['bid_sz'], prev_tick['ask_sz']
        )

        # עדכן prev tick
        self.prev_ticks[conid] = {
            'bid': bid,
            'ask': ask,
            'bid_sz': bid_sz,
            'ask_sz': ask_sz,
            'ts_utc': ts_utc
        }

        # Normalize OFI (z-score)
        if self.normalize:
            ofi_z = self._normalize_ofi(conid, ofi_raw)
        else:
            ofi_z = ofi_raw

        # צור OFIEvent
        try:
            ofi_event = OFIEvent(
                ts_utc=ts_utc,
                conid=conid,
                ofi_z=ofi_z
            )

            self.ofi_events_generated += 1
            logger.debug(f"OFI calculated: conid={conid}, ofi_z={ofi_z:.3f}")

            return ofi_event

        except Exception as e:
            logger.error(f"Error creating OFIEvent: {e}")
            return None

    def _compute_ofi(
        self,
        bid: float,
        ask: float,
        bid_sz: float,
        ask_sz: float,
        prev_bid: float,
        prev_ask: float,
        prev_bid_sz: float,
        prev_ask_sz: float
    ) -> float:
        """
        חישוב OFI raw.

        Args:
            bid, ask, bid_sz, ask_sz: Current tick
            prev_bid, prev_ask, prev_bid_sz, prev_ask_sz: Previous tick

        Returns:
            float: OFI (raw, לא מנורמל)
        """
        # Check if bid went up
        bid_up = 1 if bid > prev_bid else 0

        # Check if ask went down
        ask_down = 1 if ask < prev_ask else 0

        # Calculate deltas
        delta_bid_sz = bid_sz - prev_bid_sz if bid_up else 0
        delta_ask_sz = ask_sz - prev_ask_sz if ask_down else 0

        # OFI = buying pressure - selling pressure
        ofi = delta_bid_sz - delta_ask_sz

        return float(ofi)

    def _normalize_ofi(self, conid: int, ofi_raw: float) -> float:
        """
        נרמול OFI ל-z-score.

        Args:
            conid: Contract ID
            ofi_raw: OFI raw value

        Returns:
            float: OFI z-score
        """
        # Initialize history for this symbol if needed
        if conid not in self.ofi_history:
            self.ofi_history[conid] = deque(maxlen=self.window_size)

        # Add to history
        self.ofi_history[conid].append(ofi_raw)

        # Need at least 2 points for z-score
        if len(self.ofi_history[conid]) < 2:
            return 0.0

        # Calculate z-score
        history = list(self.ofi_history[conid])
        mean = np.mean(history)
        std = np.std(history)

        if std == 0:
            return 0.0

        z_score = (ofi_raw - mean) / std

        return float(z_score)

    def get_stats(self) -> Dict[str, Any]:
        """
        קבלת סטטיסטיקות.

        Returns:
            Dict עם סטטיסטיקות:
            - total_ticks_processed
            - ofi_events_generated
            - symbols_tracked
        """
        return {
            'total_ticks_processed': self.total_ticks_processed,
            'ofi_events_generated': self.ofi_events_generated,
            'symbols_tracked': len(self.prev_ticks),
            'symbols': list(self.prev_ticks.keys())
        }

    def reset(self):
        """
        איפוס calculator.
        """
        self.prev_ticks.clear()
        self.ofi_history.clear()
        self.total_ticks_processed = 0
        self.ofi_events_generated = 0
        logger.info("OFICalculator reset")
