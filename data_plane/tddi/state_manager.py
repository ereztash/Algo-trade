"""
TDDI State Manager - ניהול מצב TDDI (Tick-by-Tick Data Intensity)
מטרה: קביעה דינמית של רמת פירוט נתונים (S0/S1/S2) בהתאם ל-κ (kappa)
"""

import logging
from typing import Dict, Any, Optional, Literal
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class TDDIState(str, Enum):
    """
    רמות TDDI (Tick-by-Tick Data Intensity).

    S0: BARS - סרגלים רגילים בלבד (1min/5min)
    S1: L1 - Level-1 quotes (bid/ask)
    S2: L2/TBT - Level-2 orderbook + Tick-by-Tick
    """
    S0_BARS = "S0_BARS"
    S1_L1 = "S1_L1"
    S2_L2_TBT = "S2_L2_TBT"


class StateManager:
    """
    מנהל מצב TDDI עם hysteresis למניעת flapping.

    אלגוריתם:
    - κ (kappa) - מדד volatility/news intensity
    - כאשר κ חוצה threshold - מעבר למצב אחר
    - Hysteresis - דורש חציית threshold + delta כדי לשנות מצב
    - מונע switching מהיר מדי (flapping)

    Thresholds:
    - κ < 0.3: S0 (Bars only)
    - 0.3 ≤ κ < 0.7: S1 (L1 quotes)
    - κ ≥ 0.7: S2 (L2 orderbook + TBT)
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        אתחול State Manager.

        Args:
            cfg: Config dictionary עם:
                - initial_state: מצב התחלתי (default: 'S0_BARS')
                - thresholds: Dict עם thresholds למעברים
                - hysteresis_delta: Delta להיסטרזיס (default: 0.05)
                - min_duration_seconds: זמן מינימלי במצב (default: 60)
        """
        self.cfg = cfg
        self.state = TDDIState(cfg.get('initial_state', 'S0_BARS'))

        # Thresholds for state transitions
        self.thresholds = cfg.get('thresholds', {
            'S0_to_S1': 0.3,
            'S1_to_S2': 0.7,
            'S2_to_S1': 0.5,  # With hysteresis
            'S1_to_S0': 0.2   # With hysteresis
        })

        # Hysteresis delta (מונע flapping)
        self.hysteresis_delta = cfg.get('hysteresis_delta', 0.05)

        # Minimum duration in state (seconds)
        self.min_duration_seconds = cfg.get('min_duration_seconds', 60)

        # State tracking
        self.current_kappa: Optional[float] = None
        self.state_history: list = []
        self.last_state_change: Optional[datetime] = None
        self.state_durations: Dict[TDDIState, float] = {
            TDDIState.S0_BARS: 0,
            TDDIState.S1_L1: 0,
            TDDIState.S2_L2_TBT: 0
        }
        self.transition_count = 0

        logger.info(
            f"StateManager initialized: initial_state={self.state}, "
            f"thresholds={self.thresholds}, hysteresis_delta={self.hysteresis_delta}"
        )

    def update(self, kappa: float) -> Optional[TDDIState]:
        """
        עדכון state בהתאם ל-κ (kappa) הנוכחי.

        Args:
            kappa: ערך κ (0-1, מדד volatility/news intensity)

        Returns:
            TDDIState: המצב החדש (או None אם לא השתנה)
        """
        self.current_kappa = kappa
        previous_state = self.state

        # Check if we can change state (min duration passed)
        if not self._can_change_state():
            logger.debug(
                f"State change blocked: min_duration not passed "
                f"(state={self.state}, kappa={kappa:.3f})"
            )
            return None

        # Determine new state based on kappa and hysteresis
        new_state = self._compute_new_state(kappa)

        # If state changed
        if new_state != previous_state:
            self._transition_to(new_state)
            logger.info(
                f"TDDI state transition: {previous_state} → {new_state} "
                f"(κ={kappa:.3f})"
            )
            return new_state

        return None

    def _compute_new_state(self, kappa: float) -> TDDIState:
        """
        חישוב state חדש בהתאם ל-κ והיסטרזיס.

        Args:
            kappa: ערך κ

        Returns:
            TDDIState: state מומלץ
        """
        current = self.state

        # S0 → S1 (upward transition)
        if current == TDDIState.S0_BARS:
            if kappa >= self.thresholds['S0_to_S1']:
                return TDDIState.S1_L1
            return current

        # S1 → S2 or S1 → S0
        elif current == TDDIState.S1_L1:
            # Upward: S1 → S2
            if kappa >= self.thresholds['S1_to_S2']:
                return TDDIState.S2_L2_TBT
            # Downward: S1 → S0 (with hysteresis)
            elif kappa < (self.thresholds['S1_to_S0'] - self.hysteresis_delta):
                return TDDIState.S0_BARS
            return current

        # S2 → S1 (downward transition with hysteresis)
        elif current == TDDIState.S2_L2_TBT:
            if kappa < (self.thresholds['S2_to_S1'] - self.hysteresis_delta):
                return TDDIState.S1_L1
            return current

        return current

    def _can_change_state(self) -> bool:
        """
        בדיקה האם ניתן לשנות state (min duration עבר).

        Returns:
            bool: True אם ניתן לשנות
        """
        if self.last_state_change is None:
            return True

        elapsed = (datetime.utcnow() - self.last_state_change).total_seconds()
        return elapsed >= self.min_duration_seconds

    def _transition_to(self, new_state: TDDIState):
        """
        ביצוע מעבר ל-state חדש.

        Args:
            new_state: State חדש
        """
        # Update duration of previous state
        if self.last_state_change:
            duration = (datetime.utcnow() - self.last_state_change).total_seconds()
            self.state_durations[self.state] += duration

        # Record transition
        self.state_history.append({
            'timestamp': datetime.utcnow(),
            'from_state': self.state,
            'to_state': new_state,
            'kappa': self.current_kappa
        })

        # Update state
        self.state = new_state
        self.last_state_change = datetime.utcnow()
        self.transition_count += 1

    def get_state(self) -> TDDIState:
        """
        קבלת state נוכחי.

        Returns:
            TDDIState: state נוכחי
        """
        return self.state

    def get_stats(self) -> Dict[str, Any]:
        """
        קבלת סטטיסטיקות.

        Returns:
            Dict עם סטטיסטיקות:
            - current_state
            - current_kappa
            - transition_count
            - state_durations
            - last_state_change
        """
        total_duration = sum(self.state_durations.values())
        state_percentages = {
            state.value: round(duration / total_duration * 100, 2) if total_duration > 0 else 0
            for state, duration in self.state_durations.items()
        }

        return {
            'current_state': self.state.value,
            'current_kappa': round(self.current_kappa, 3) if self.current_kappa else None,
            'transition_count': self.transition_count,
            'state_durations_seconds': {s.value: round(d, 1) for s, d in self.state_durations.items()},
            'state_percentages': state_percentages,
            'last_state_change': self.last_state_change.isoformat() if self.last_state_change else None,
            'state_history_count': len(self.state_history)
        }

    def get_data_requirements(self) -> Dict[str, Any]:
        """
        קבלת דרישות נתונים בהתאם ל-state הנוכחי.

        Returns:
            Dict עם דרישות:
            - data_type: 'BARS', 'L1', 'L2', 'TBT'
            - bar_size: גודל סרגל (אם רלוונטי)
            - include_orderbook: האם לכלול orderbook
            - tick_by_tick: האם לכלול TBT
        """
        requirements = {
            TDDIState.S0_BARS: {
                'data_type': 'BARS',
                'bar_size': '1 min',
                'include_orderbook': False,
                'tick_by_tick': False,
                'whatToShow': 'TRADES'
            },
            TDDIState.S1_L1: {
                'data_type': 'L1',
                'bar_size': None,
                'include_orderbook': False,
                'tick_by_tick': False,
                'whatToShow': 'BID_ASK'
            },
            TDDIState.S2_L2_TBT: {
                'data_type': 'L2_TBT',
                'bar_size': None,
                'include_orderbook': True,
                'tick_by_tick': True,
                'whatToShow': 'BID_ASK'
            }
        }

        return requirements[self.state]

    def reset(self):
        """
        איפוס state manager למצב התחלתי.
        """
        self.state = TDDIState(self.cfg.get('initial_state', 'S0_BARS'))
        self.current_kappa = None
        self.state_history.clear()
        self.last_state_change = None
        self.state_durations = {s: 0 for s in TDDIState}
        self.transition_count = 0
        logger.info("StateManager reset to initial state")
