"""
Pacing Manager - מנהל קצב שליחת בקשות
מטרה: מניעת pacing violations ב-IBKR API (rate limiting)
"""

import logging
import asyncio
import time
from typing import Dict, Optional, Any, List
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PacingRule:
    """
    חוק pacing עבור endpoint ספציפי.

    Attributes:
        rate: מספר requests מקסימלי
        per_seconds: בתוך כמה שניות
        burst: האם לאפשר burst (קבוצת requests בבת אחת)
    """
    rate: int  # requests
    per_seconds: int  # seconds
    burst: bool = False


class TokenBucket:
    """
    Token Bucket Algorithm למימוש rate limiting.

    אלגוריתם:
    - יש bucket עם tokens
    - כל request צורך token אחד
    - Tokens מתמלאים בקצב קבוע
    - אם אין tokens - צריך לחכות
    """

    def __init__(self, rate: int, per_seconds: int):
        """
        אתחול Token Bucket.

        Args:
            rate: מספר tokens מקסימלי (requests)
            per_seconds: תקופת מילוי מחדש (שניות)
        """
        self.capacity = rate
        self.tokens = float(rate)
        self.fill_rate = rate / per_seconds  # tokens per second
        self.last_update = time.time()

    def _refill(self):
        """
        מילוי tokens בהתאם לזמן שעבר.
        """
        now = time.time()
        elapsed = now - self.last_update
        tokens_to_add = elapsed * self.fill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_update = now

    def consume(self, tokens: int = 1) -> bool:
        """
        ניסיון לצרוך tokens.

        Args:
            tokens: מספר tokens לצריכה

        Returns:
            bool: True אם הצליח, False אם אין מספיק tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    async def acquire(self, tokens: int = 1):
        """
        המתנה עד שיהיו מספיק tokens (async).

        Args:
            tokens: מספר tokens לקבלת
        """
        while not self.consume(tokens):
            # חשב כמה זמן צריך לחכות
            tokens_needed = tokens - self.tokens
            wait_time = tokens_needed / self.fill_rate
            await asyncio.sleep(min(wait_time, 0.1))  # לפחות 100ms

    def get_available_tokens(self) -> float:
        """
        קבלת מספר tokens זמינים.

        Returns:
            float: מספר tokens זמינים
        """
        self._refill()
        return self.tokens


class PacingManager:
    """
    מנהל pacing עבור כל endpoints של IBKR.

    מטרה:
    - מניעת pacing violations (error 100, 103)
    - שמירה על rate limits per endpoint
    - ניהול תור של requests שנדחו
    - מעקב אחר utilization
    """

    def __init__(self, pacing_tbl: Optional[Dict[str, PacingRule]] = None):
        """
        אתחול Pacing Manager.

        Args:
            pacing_tbl: טבלת pacing rules per endpoint
                       אם None - משתמש ב-defaults של IBKR
        """
        # Default IBKR pacing rules (מתוך IBKR_INTERFACE_MAP.md)
        default_rules = {
            'order_messages': PacingRule(rate=50, per_seconds=1),
            'market_data': PacingRule(rate=50, per_seconds=1),
            'historical_data': PacingRule(rate=60, per_seconds=600),  # 60 per 10 minutes
            'account_updates': PacingRule(rate=50, per_seconds=1),
            'rt_marketdata': PacingRule(rate=50, per_seconds=1),
            'default': PacingRule(rate=50, per_seconds=1)
        }

        # מיזוג עם custom rules אם ניתנו
        if pacing_tbl:
            # המרת dict פשוט ל-PacingRule objects אם צריך
            for endpoint, rule in pacing_tbl.items():
                if isinstance(rule, dict):
                    pacing_tbl[endpoint] = PacingRule(**rule)
            self.rules = {**default_rules, **pacing_tbl}
        else:
            self.rules = default_rules

        # יצירת token buckets per endpoint
        self.buckets: Dict[str, TokenBucket] = {}
        for endpoint, rule in self.rules.items():
            self.buckets[endpoint] = TokenBucket(rule.rate, rule.per_seconds)

        # תור של requests שנדחו (per endpoint)
        self.retry_queues: Dict[str, deque] = defaultdict(deque)

        # Statistics
        self.total_requests: Dict[str, int] = defaultdict(int)
        self.allowed_requests: Dict[str, int] = defaultdict(int)
        self.denied_requests: Dict[str, int] = defaultdict(int)
        self.retried_requests: Dict[str, int] = defaultdict(int)

        logger.info(
            f"PacingManager initialized with {len(self.rules)} endpoints. "
            f"Rules: {[(ep, f'{r.rate}/{r.per_seconds}s') for ep, r in self.rules.items()]}"
        )

    def allow(self, endpoint: str, code: Optional[str] = None) -> bool:
        """
        בדיקה האם request מותר (synchronous check).

        Args:
            endpoint: endpoint name (e.g., 'order_messages', 'market_data')
            code: optional error code (לזיהוי סוג request)

        Returns:
            bool: True אם מותר, False אם צריך לחכות
        """
        self.total_requests[endpoint] += 1

        # קבל bucket מתאים
        bucket = self._get_bucket(endpoint)

        # נסה לצרוך token
        allowed = bucket.consume(1)

        if allowed:
            self.allowed_requests[endpoint] += 1
            logger.debug(f"Request allowed: {endpoint} (tokens left: {bucket.get_available_tokens():.1f})")
        else:
            self.denied_requests[endpoint] += 1
            logger.warning(
                f"Request denied (rate limit): {endpoint}. "
                f"Tokens: {bucket.get_available_tokens():.1f}/{bucket.capacity}"
            )

        return allowed

    async def gate(self, endpoint: str, code: Optional[str] = None):
        """
        Gate asynchronous - ממתין עד שיש tokens זמינים.

        Args:
            endpoint: endpoint name
            code: optional error code

        Note:
            פונקציה זו תחסום (block) עד שיהיה token זמין
        """
        self.total_requests[endpoint] += 1

        bucket = self._get_bucket(endpoint)

        # המתן לtoken
        tokens_before = bucket.get_available_tokens()
        if tokens_before < 1:
            logger.debug(f"Waiting for token: {endpoint} (available: {tokens_before:.1f})")

        await bucket.acquire(1)

        self.allowed_requests[endpoint] += 1
        logger.debug(f"Request gated and allowed: {endpoint}")

    def _get_bucket(self, endpoint: str) -> TokenBucket:
        """
        קבלת bucket מתאים ל-endpoint.

        Args:
            endpoint: endpoint name

        Returns:
            TokenBucket
        """
        if endpoint in self.buckets:
            return self.buckets[endpoint]

        # אם אין bucket ספציפי - השתמש ב-default
        logger.debug(f"No specific bucket for {endpoint}, using 'default'")
        return self.buckets['default']

    def enqueue_retry(self, msg: Any):
        """
        הכנסת message לתור retry.

        Args:
            msg: message object (צריך להיות עם .endpoint field)
        """
        endpoint = getattr(msg, 'endpoint', 'default')
        self.retry_queues[endpoint].append(msg)
        self.retried_requests[endpoint] += 1
        logger.debug(f"Message enqueued for retry: {endpoint} (queue size: {len(self.retry_queues[endpoint])})")

    def dequeue_retry(self, endpoint: str, max_items: int = 10) -> List[Any]:
        """
        הוצאת messages מתור retry.

        Args:
            endpoint: endpoint name
            max_items: מספר מקסימלי של items להוציא

        Returns:
            List[Any]: רשימת messages
        """
        items = []
        queue = self.retry_queues[endpoint]

        while queue and len(items) < max_items:
            # בדוק אם יש token זמין
            if self.allow(endpoint):
                items.append(queue.popleft())
            else:
                break

        if items:
            logger.debug(f"Dequeued {len(items)} items from retry queue: {endpoint}")

        return items

    def get_stats(self) -> Dict[str, Any]:
        """
        קבלת סטטיסטיקות.

        Returns:
            Dict עם סטטיסטיקות per endpoint:
            - total_requests
            - allowed_requests
            - denied_requests
            - denial_rate
            - retry_queue_size
            - available_tokens
        """
        stats = {}

        for endpoint in self.buckets.keys():
            total = self.total_requests[endpoint]
            allowed = self.allowed_requests[endpoint]
            denied = self.denied_requests[endpoint]
            denial_rate = (denied / total * 100) if total > 0 else 0

            bucket = self.buckets[endpoint]
            available_tokens = bucket.get_available_tokens()

            stats[endpoint] = {
                'total_requests': total,
                'allowed_requests': allowed,
                'denied_requests': denied,
                'retried_requests': self.retried_requests[endpoint],
                'denial_rate': round(denial_rate, 2),
                'retry_queue_size': len(self.retry_queues[endpoint]),
                'available_tokens': round(available_tokens, 1),
                'capacity': bucket.capacity,
                'utilization': round((1 - available_tokens / bucket.capacity) * 100, 2)
            }

        return stats

    def get_health(self) -> Dict[str, Any]:
        """
        בדיקת health של pacing manager.

        Returns:
            Dict עם health status:
            - is_healthy: האם כל endpoints בריאים
            - violations: מספר pacing violations
            - high_utilization: endpoints עם utilization > 80%
        """
        stats = self.get_stats()
        violations = sum(s['denied_requests'] for s in stats.values())
        high_util = [ep for ep, s in stats.items() if s['utilization'] > 80]

        is_healthy = violations < 10 and len(high_util) < 3

        return {
            'is_healthy': is_healthy,
            'total_violations': violations,
            'high_utilization_endpoints': high_util,
            'endpoints_count': len(self.buckets),
            'total_retry_queue_size': sum(len(q) for q in self.retry_queues.values())
        }

    def reset_stats(self):
        """
        איפוס סטטיסטיקות.
        """
        self.total_requests.clear()
        self.allowed_requests.clear()
        self.denied_requests.clear()
        self.retried_requests.clear()
        logger.info("PacingManager stats reset")
