"""
Time Service - שירות זמן אחיד
מטרה: מתן timestamp אחיד ומסונכרן (NTP/UTC) לכל המערכת
"""

import logging
from datetime import datetime, timezone
from typing import Callable, Optional
import ntplib
import time

logger = logging.getLogger(__name__)


class TimeService:
    """
    שירות זמן מרכזי המספק timestamps מסונכרנים.

    תכונות:
    - Sync עם NTP server
    - UTC timestamps
    - Offset correction
    - Caching של NTP queries
    """

    def __init__(self, ntp_server: str = "pool.ntp.org", sync_interval_seconds: int = 300):
        """
        אתחול Time Service.

        Args:
            ntp_server: שרת NTP לסינכרון (default: pool.ntp.org)
            sync_interval_seconds: interval לסינכרון מחדש (default: 300 = 5 minutes)
        """
        self.ntp_server = ntp_server
        self.sync_interval_seconds = sync_interval_seconds
        self.ntp_client = ntplib.NTPClient()

        # NTP offset (seconds)
        self.offset_seconds: float = 0.0
        self.last_sync: Optional[datetime] = None
        self.sync_failures = 0

        # Initial sync
        self._sync_with_ntp()

        logger.info(
            f"TimeService initialized: ntp_server={ntp_server}, "
            f"sync_interval={sync_interval_seconds}s, offset={self.offset_seconds*1000:.2f}ms"
        )

    def _sync_with_ntp(self):
        """
        סינכרון עם NTP server.
        """
        try:
            response = self.ntp_client.request(self.ntp_server, version=3, timeout=5)
            self.offset_seconds = response.offset
            self.last_sync = datetime.utcnow()

            logger.info(
                f"NTP sync successful: offset={self.offset_seconds*1000:.2f}ms "
                f"(server: {self.ntp_server})"
            )

        except Exception as e:
            self.sync_failures += 1
            logger.error(
                f"NTP sync failed ({self.sync_failures} failures): {e}. "
                f"Using previous offset: {self.offset_seconds*1000:.2f}ms"
            )

    def _should_resync(self) -> bool:
        """
        בדיקה האם צריך לסנכרן מחדש.

        Returns:
            bool: True אם צריך
        """
        if self.last_sync is None:
            return True

        elapsed = (datetime.utcnow() - self.last_sync).total_seconds()
        return elapsed >= self.sync_interval_seconds

    def now_utc(self) -> float:
        """
        קבלת timestamp נוכחי UTC מתוקן (Unix timestamp).

        Returns:
            float: Unix timestamp (seconds since epoch) מתוקן עם NTP offset
        """
        # Check if we need to resync
        if self._should_resync():
            self._sync_with_ntp()

        # Get current time and apply offset
        now = time.time()
        corrected = now + self.offset_seconds

        return corrected

    def now_datetime(self) -> datetime:
        """
        קבלת datetime object נוכחי UTC מתוקן.

        Returns:
            datetime: datetime object (UTC)
        """
        timestamp = self.now_utc()
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)

    def get_offset_ms(self) -> float:
        """
        קבלת NTP offset במילישניות.

        Returns:
            float: Offset במילישניות
        """
        return self.offset_seconds * 1000

    def get_stats(self) -> dict:
        """
        קבלת סטטיסטיקות.

        Returns:
            dict: סטטיסטיקות time service
        """
        return {
            'ntp_server': self.ntp_server,
            'offset_ms': round(self.offset_seconds * 1000, 2),
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'sync_failures': self.sync_failures,
            'sync_interval_seconds': self.sync_interval_seconds
        }


def init_time_service(
    ntp_server: str = "pool.ntp.org",
    sync_interval_seconds: int = 300
) -> Callable[[], float]:
    """
    אתחול שירות זמן אחיד (NTP/UTC).

    Args:
        ntp_server: שרת NTP לסינכרון (default: pool.ntp.org)
        sync_interval_seconds: interval לסינכרון מחדש (default: 300)

    Returns:
        Callable: פונקציה now() שמחזירה Unix timestamp מתוקן
    """
    time_service = TimeService(ntp_server=ntp_server, sync_interval_seconds=sync_interval_seconds)

    # Return now() function
    def now() -> float:
        """
        קבלת timestamp נוכחי UTC מתוקן.

        Returns:
            float: Unix timestamp (seconds)
        """
        return time_service.now_utc()

    # Attach service for direct access
    now.service = time_service

    logger.info("Time service initialized and ready")
    return now
