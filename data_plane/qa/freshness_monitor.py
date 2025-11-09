"""
Freshness Monitor - ניטור רעננות נתונים
מטרה: זיהוי עיכובים בזרם נתונים real-time ומניעת שימוש בנתונים מיושנים
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class FreshnessMonitor:
    """
    מנטר את רעננות נתוני השוק.
    מזהה אם נתונים מגיעים באיחור (stale data) ומעלה אזהרות.
    """

    def __init__(self, p95_ms: float = 250):
        """
        אתחול Freshness Monitor.

        Args:
            p95_ms: Threshold של p95 latency במילישניות (default: 250ms מתוך SLA)
        """
        self.p95_threshold_ms = p95_ms
        self.latencies = []
        self.max_samples = 1000  # שמור עד 1000 מדידות אחרונות
        self.stale_count = 0
        self.total_count = 0
        self.alerts_triggered = 0
        logger.info(f"FreshnessMonitor initialized with p95 threshold: {p95_ms}ms")

    def measure(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        מדידת latency של events ובדיקה מול threshold.

        Args:
            events: רשימת events עם timestamp field

        Returns:
            Dict עם סטטיסטיקות:
            - p50_ms: median latency
            - p95_ms: 95th percentile latency
            - p99_ms: 99th percentile latency
            - stale_count: מספר events מיושנים
            - total_count: סך הכל events
            - is_healthy: האם הזרם בריא (p95 < threshold)
        """
        if not events:
            return {
                'p50_ms': 0,
                'p95_ms': 0,
                'p99_ms': 0,
                'stale_count': 0,
                'total_count': 0,
                'is_healthy': True
            }

        now = datetime.utcnow()
        current_latencies = []

        for event in events:
            try:
                # חלץ timestamp מה-event
                event_time = self._extract_timestamp(event)
                if event_time is None:
                    continue

                # חשב latency במילישניות
                latency_ms = (now - event_time).total_seconds() * 1000
                current_latencies.append(latency_ms)

                # בדוק אם Event מיושן
                if latency_ms > self.p95_threshold_ms:
                    self.stale_count += 1
                    logger.warning(
                        f"Stale event detected: {event.get('symbol', 'unknown')} "
                        f"latency={latency_ms:.1f}ms (threshold={self.p95_threshold_ms}ms)"
                    )

                self.total_count += 1

            except Exception as e:
                logger.error(f"Error measuring event freshness: {e}")
                continue

        # עדכן latencies buffer
        self.latencies.extend(current_latencies)
        if len(self.latencies) > self.max_samples:
            self.latencies = self.latencies[-self.max_samples:]

        # חשב percentiles
        stats = self._calculate_stats()

        # בדוק health
        is_healthy = stats['p95_ms'] < self.p95_threshold_ms
        if not is_healthy:
            self.alerts_triggered += 1
            logger.error(
                f"FRESHNESS ALERT: p95 latency {stats['p95_ms']:.1f}ms "
                f"exceeds threshold {self.p95_threshold_ms}ms"
            )

        return stats

    def _extract_timestamp(self, event: Dict[str, Any]) -> Optional[datetime]:
        """
        חילוץ timestamp מ-event.
        תומך במספר פורמטים.
        """
        # נסה למצוא timestamp field
        for field in ['timestamp', 'time', 'datetime', 'ts', 'event_time']:
            if field in event:
                ts = event[field]

                # אם זה כבר datetime object
                if isinstance(ts, datetime):
                    return ts

                # אם זה Unix timestamp (seconds)
                if isinstance(ts, (int, float)):
                    try:
                        return datetime.fromtimestamp(ts)
                    except:
                        # נסה milliseconds
                        try:
                            return datetime.fromtimestamp(ts / 1000)
                        except:
                            pass

                # אם זה string - נסה לparse
                if isinstance(ts, str):
                    try:
                        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    except:
                        pass

        logger.warning(f"Could not extract timestamp from event: {event}")
        return None

    def _calculate_stats(self) -> Dict[str, Any]:
        """
        חישוב סטטיסטיקות latency.
        """
        if not self.latencies:
            return {
                'p50_ms': 0,
                'p95_ms': 0,
                'p99_ms': 0,
                'max_ms': 0,
                'mean_ms': 0,
                'stale_count': self.stale_count,
                'total_count': self.total_count,
                'stale_rate': 0,
                'is_healthy': True,
                'alerts_triggered': self.alerts_triggered
            }

        arr = np.array(self.latencies)
        p50 = np.percentile(arr, 50)
        p95 = np.percentile(arr, 95)
        p99 = np.percentile(arr, 99)
        max_latency = np.max(arr)
        mean_latency = np.mean(arr)

        stale_rate = (self.stale_count / self.total_count * 100) if self.total_count > 0 else 0

        return {
            'p50_ms': round(p50, 2),
            'p95_ms': round(p95, 2),
            'p99_ms': round(p99, 2),
            'max_ms': round(max_latency, 2),
            'mean_ms': round(mean_latency, 2),
            'stale_count': self.stale_count,
            'total_count': self.total_count,
            'stale_rate': round(stale_rate, 2),
            'is_healthy': p95 < self.p95_threshold_ms,
            'alerts_triggered': self.alerts_triggered
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        קבלת סטטיסטיקות נוכחיות ללא מדידה חדשה.
        """
        return self._calculate_stats()

    def reset(self):
        """
        איפוס counters וסטטיסטיקות.
        """
        self.latencies.clear()
        self.stale_count = 0
        self.total_count = 0
        self.alerts_triggered = 0
        logger.info("FreshnessMonitor reset")

    def is_healthy(self) -> bool:
        """
        בדיקה מהירה אם הזרם בריא.
        """
        stats = self._calculate_stats()
        return stats['is_healthy']
