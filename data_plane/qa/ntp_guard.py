"""
NTP Guard for time synchronization validation.
שומר NTP לוולידציה של סנכרון זמן.
"""

from typing import Any, Dict
from datetime import datetime, timezone
import time


class NTPGuard:
    """
    NTP Guard to reject events with clock drift.
    שומר NTP לדחיית אירועים עם סטיית שעון.

    Ensures market data timestamps are within acceptable bounds
    to prevent stale or future-dated data from entering the system.
    """

    def __init__(self, drift_ms: float = 5000.0):
        """
        Initialize NTP Guard.

        Args:
            drift_ms: Maximum acceptable drift in milliseconds (default: 5000ms = 5 seconds)
        """
        self.drift_ms = drift_ms
        self.drift_sec = drift_ms / 1000.0
        self.rejected_count = 0
        self.accepted_count = 0

    def accept(self, event: Any) -> bool:
        """
        Check if event timestamp is within acceptable drift.
        בדיקה אם חותמת הזמן של האירוע בטווח הסטייה המקובל.

        Args:
            event: Event object or dictionary with 'ts_utc' field

        Returns:
            True if event is acceptable, False if rejected
        """
        # Extract timestamp from event
        if isinstance(event, dict):
            ts_utc = event.get('ts_utc', None)
        elif hasattr(event, 'ts_utc'):
            ts_utc = event.ts_utc
        else:
            # No timestamp found - reject for safety
            self.rejected_count += 1
            return False

        if ts_utc is None:
            self.rejected_count += 1
            return False

        # Current system time (UTC)
        now = datetime.now(timezone.utc).timestamp()

        # Calculate drift
        drift = abs(now - ts_utc)

        # Check if within bounds
        if drift <= self.drift_sec:
            self.accepted_count += 1
            return True
        else:
            self.rejected_count += 1
            return False

    def check_drift(self, event: Any) -> float:
        """
        Calculate time drift for an event.
        חישוב סטיית זמן עבור אירוע.

        Args:
            event: Event object or dictionary

        Returns:
            Drift in seconds (positive or negative)
        """
        # Extract timestamp
        if isinstance(event, dict):
            ts_utc = event.get('ts_utc', None)
        elif hasattr(event, 'ts_utc'):
            ts_utc = event.ts_utc
        else:
            return float('inf')

        if ts_utc is None:
            return float('inf')

        # Current system time
        now = datetime.now(timezone.utc).timestamp()

        # Return signed drift (positive = event in future, negative = event in past)
        return ts_utc - now

    def stats(self) -> Dict[str, Any]:
        """
        Get statistics on accepted/rejected events.
        קבלת סטטיסטיקה על אירועים שהתקבלו/נדחו.

        Returns:
            Statistics dictionary
        """
        total = self.accepted_count + self.rejected_count
        reject_rate = (self.rejected_count / total * 100) if total > 0 else 0.0

        return {
            'drift_threshold_ms': self.drift_ms,
            'accepted': self.accepted_count,
            'rejected': self.rejected_count,
            'total': total,
            'reject_rate_pct': round(reject_rate, 2),
        }

    def reset(self):
        """Reset counters."""
        self.accepted_count = 0
        self.rejected_count = 0


# Example usage
if __name__ == "__main__":
    guard = NTPGuard(drift_ms=2000)  # 2 second tolerance

    # Test events
    now = datetime.now(timezone.utc).timestamp()

    # Valid event (current time)
    event1 = {'ts_utc': now, 'symbol': 'AAPL'}
    print(f"Event1 (current): {guard.accept(event1)}")  # True

    # Valid event (1 second ago)
    event2 = {'ts_utc': now - 1.0, 'symbol': 'TSLA'}
    print(f"Event2 (1s ago): {guard.accept(event2)}")  # True

    # Invalid event (10 seconds in future)
    event3 = {'ts_utc': now + 10.0, 'symbol': 'MSFT'}
    print(f"Event3 (10s future): {guard.accept(event3)}")  # False

    # Invalid event (5 seconds in past, exceeds 2s threshold)
    event4 = {'ts_utc': now - 5.0, 'symbol': 'GOOGL'}
    print(f"Event4 (5s ago): {guard.accept(event4)}")  # False

    # Check drift
    print(f"Event3 drift: {guard.check_drift(event3):.2f}s")

    # Stats
    print(f"Stats: {guard.stats()}")
