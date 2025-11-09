"""
NTP Guard - שומר סינכרון זמן
מטרה: מניעת שימוש בנתונים עם drift זמן גדול מדי (מעבר ל-threshold)
"""

import logging
import ntplib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import time

logger = logging.getLogger(__name__)


class NTPGuard:
    """
    מנטר drift זמן מול NTP server ודוחה events עם סטיית זמן גדולה מדי.

    מטרה:
    - מניעת שימוש בנתונים עם timestamp שגוי
    - וידוא sync עם atomic clock
    - הגנה מפני clock skew במערכת
    """

    def __init__(self, drift_ms: float = 100, ntp_server: str = "pool.ntp.org"):
        """
        אתחול NTP Guard.

        Args:
            drift_ms: threshold מקסימלי של drift במילישניות (default: 100ms)
            ntp_server: שרת NTP לסינכרון (default: pool.ntp.org)
        """
        self.drift_threshold_ms = drift_ms
        self.ntp_server = ntp_server
        self.ntp_client = ntplib.NTPClient()

        # Cache של NTP offset (מתעדכן כל 60 שניות)
        self.last_ntp_check: Optional[datetime] = None
        self.ntp_offset_seconds: float = 0.0
        self.ntp_check_interval_seconds = 60

        # Statistics
        self.total_events = 0
        self.rejected_events = 0
        self.ntp_failures = 0
        self.max_drift_observed_ms = 0.0

        # Initialize NTP offset
        self._update_ntp_offset()

        logger.info(
            f"NTPGuard initialized: drift_threshold={drift_ms}ms, "
            f"ntp_server={ntp_server}, current_offset={self.ntp_offset_seconds*1000:.2f}ms"
        )

    def accept(self, event: Any) -> bool:
        """
        בדיקה האם event מקובל מבחינת סינכרון זמן.

        Args:
            event: Event object או timestamp (float/datetime)

        Returns:
            bool: True אם Event מקובל, False אם יש drift גדול מדי
        """
        self.total_events += 1

        # רענן NTP offset אם צריך
        if self._should_refresh_ntp():
            self._update_ntp_offset()

        # חלץ timestamp מה-event
        event_time = self._extract_timestamp(event)
        if event_time is None:
            logger.warning("Could not extract timestamp from event, rejecting")
            self.rejected_events += 1
            return False

        # חשב system time עם NTP correction
        corrected_now = datetime.utcnow() + timedelta(seconds=self.ntp_offset_seconds)

        # חשב drift
        drift_seconds = abs((corrected_now - event_time).total_seconds())
        drift_ms = drift_seconds * 1000

        # עדכן max drift
        if drift_ms > self.max_drift_observed_ms:
            self.max_drift_observed_ms = drift_ms

        # בדוק threshold
        is_acceptable = drift_ms <= self.drift_threshold_ms

        if not is_acceptable:
            self.rejected_events += 1
            logger.warning(
                f"NTP drift exceeded threshold: {drift_ms:.2f}ms > {self.drift_threshold_ms}ms. "
                f"Event time: {event_time}, Corrected now: {corrected_now}"
            )
        else:
            logger.debug(f"Event accepted with drift: {drift_ms:.2f}ms")

        return is_acceptable

    def _extract_timestamp(self, event: Any) -> Optional[datetime]:
        """
        חילוץ timestamp מ-event.

        Args:
            event: Event object, timestamp, או dict

        Returns:
            datetime או None אם לא הצליח
        """
        # אם זה datetime ישירות
        if isinstance(event, datetime):
            return event

        # אם זה Unix timestamp (float/int)
        if isinstance(event, (int, float)):
            try:
                return datetime.utcfromtimestamp(event)
            except (ValueError, OSError):
                # נסה milliseconds
                try:
                    return datetime.utcfromtimestamp(event / 1000)
                except (ValueError, OSError):
                    pass

        # אם זה object עם timestamp field
        if hasattr(event, 'ts_utc'):
            ts = event.ts_utc
            if isinstance(ts, datetime):
                return ts
            if isinstance(ts, (int, float)):
                try:
                    return datetime.utcfromtimestamp(ts)
                except (ValueError, OSError):
                    pass

        # אם זה dict
        if isinstance(event, dict):
            for key in ['ts_utc', 'timestamp', 'time', 'datetime', 'ts', 'event_time']:
                if key in event:
                    ts = event[key]
                    if isinstance(ts, datetime):
                        return ts
                    if isinstance(ts, (int, float)):
                        try:
                            return datetime.utcfromtimestamp(ts)
                        except (ValueError, OSError):
                            try:
                                return datetime.utcfromtimestamp(ts / 1000)
                            except (ValueError, OSError):
                                pass

        logger.warning(f"Could not extract timestamp from event: {type(event)}")
        return None

    def _should_refresh_ntp(self) -> bool:
        """
        בדיקה האם צריך לרענן NTP offset.
        """
        if self.last_ntp_check is None:
            return True

        elapsed = (datetime.utcnow() - self.last_ntp_check).total_seconds()
        return elapsed >= self.ntp_check_interval_seconds

    def _update_ntp_offset(self):
        """
        עדכון NTP offset מול שרת NTP.
        """
        try:
            response = self.ntp_client.request(self.ntp_server, version=3, timeout=5)
            self.ntp_offset_seconds = response.offset
            self.last_ntp_check = datetime.utcnow()

            logger.debug(
                f"NTP offset updated: {self.ntp_offset_seconds*1000:.2f}ms "
                f"(server: {self.ntp_server})"
            )
        except Exception as e:
            self.ntp_failures += 1
            logger.error(
                f"Failed to query NTP server {self.ntp_server}: {e}. "
                f"Using previous offset: {self.ntp_offset_seconds*1000:.2f}ms"
            )

    def get_stats(self) -> Dict[str, Any]:
        """
        קבלת סטטיסטיקות.

        Returns:
            Dict עם סטטיסטיקות:
            - total_events: סך הכל events
            - rejected_events: events שנדחו
            - rejection_rate: אחוז דחייה
            - ntp_offset_ms: NTP offset נוכחי
            - max_drift_ms: drift מקסימלי שנצפה
            - ntp_failures: כשלונות בחיבור ל-NTP
        """
        rejection_rate = (self.rejected_events / self.total_events * 100) if self.total_events > 0 else 0

        return {
            'total_events': self.total_events,
            'rejected_events': self.rejected_events,
            'rejection_rate': round(rejection_rate, 2),
            'ntp_offset_ms': round(self.ntp_offset_seconds * 1000, 2),
            'max_drift_ms': round(self.max_drift_observed_ms, 2),
            'ntp_failures': self.ntp_failures,
            'drift_threshold_ms': self.drift_threshold_ms,
            'last_ntp_check': self.last_ntp_check.isoformat() if self.last_ntp_check else None
        }

    def reset_stats(self):
        """
        איפוס סטטיסטיקות.
        """
        self.total_events = 0
        self.rejected_events = 0
        self.ntp_failures = 0
        self.max_drift_observed_ms = 0.0
        logger.info("NTPGuard stats reset")

    def get_current_drift(self) -> float:
        """
        קבלת drift נוכחי (מבלי לדחות event).

        Returns:
            float: drift במילישניות
        """
        if self._should_refresh_ntp():
            self._update_ntp_offset()

        return abs(self.ntp_offset_seconds * 1000)

    def is_healthy(self) -> bool:
        """
        בדיקה האם המערכת בריאה (drift < threshold).

        Returns:
            bool: True אם drift נוכחי < threshold
        """
        current_drift = self.get_current_drift()
        return current_drift <= self.drift_threshold_ms
