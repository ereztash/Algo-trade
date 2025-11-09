# -*- coding: utf-8 -*-
"""
order_plane/broker/throttling.py
מנגנון throttling למניעת חריגה מגבולות POV/ADV ו-rate limiting
"""

import logging
from typing import Dict, Optional
from contracts.validators import OrderIntent

logger = logging.getLogger(__name__)


def exceeds_pov(intent: OrderIntent, limits: Dict) -> bool:
    """
    בודק אם הזמנה חורגת ממגבלת Percentage of Volume (POV).

    POV מגדיר את אחוז הנפח המקסימלי שניתן לסחור בו ביחס לנפח השוק הכולל.
    דוגמה: אם POV_CAP=0.08 (8%), לא ניתן לסחור יותר מ-8% מהנפח היומי.

    Args:
        intent: OrderIntent המכיל את פרטי ההזמנה
        limits: מילון גבולות המכיל:
            - pov_cap: אחוז מקסימלי מהנפח (default: 0.08 = 8%)
            - market_volume_map: מיפוי {conid: current_volume}
            - adv_map: מיפוי {conid: average_daily_volume}

    Returns:
        True אם ההזמנה חורגת ממגבלת POV

    דוגמה:
        >>> limits = {
        ...     "pov_cap": 0.08,
        ...     "market_volume_map": {12345: 1_000_000},
        ...     "adv_map": {12345: 5_000_000}
        ... }
        >>> intent = OrderIntent(
        ...     ts_utc=time.time(),
        ...     conid=12345,
        ...     side='BUY',
        ...     qty=100_000,
        ...     tif='DAY',
        ...     meta={}
        ... )
        >>> exceeds_pov(intent, limits)
        True  # 100k / 1M = 10% > 8%
    """
    pov_cap = limits.get('pov_cap', 0.08)  # Default: 8%

    # Get current market volume for this conid
    market_volume_map = limits.get('market_volume_map', {})
    current_volume = market_volume_map.get(intent.conid, None)

    if current_volume is None or current_volume <= 0:
        # No volume data available - use ADV as fallback
        logger.warning(
            f"No current volume for conid={intent.conid}. "
            f"Using ADV as fallback for POV check."
        )
        adv_map = limits.get('adv_map', {})
        current_volume = adv_map.get(intent.conid, 1_000_000)  # Default: 1M shares

    # Calculate POV percentage
    pov_percentage = intent.qty / current_volume

    if pov_percentage > pov_cap:
        logger.warning(
            f"⚠️  POV exceeded for conid={intent.conid}: "
            f"{pov_percentage:.2%} > {pov_cap:.2%} "
            f"(qty={intent.qty:,.0f}, volume={current_volume:,.0f})"
        )
        return True

    logger.debug(
        f"POV check passed for conid={intent.conid}: "
        f"{pov_percentage:.2%} <= {pov_cap:.2%}"
    )
    return False


def exceeds_adv(intent: OrderIntent, limits: Dict) -> bool:
    """
    בודק אם הזמנה חורגת ממגבלת Average Daily Volume (ADV).

    ADV מגדיר את אחוז הנפח היומי הממוצע המקסימלי שניתן לסחור בו.
    דוגמה: אם ADV_CAP=0.10 (10%), לא ניתן לסחור יותר מ-10% מה-ADV.

    Args:
        intent: OrderIntent
        limits: מילון גבולות המכיל:
            - adv_cap: אחוז מקסימלי מ-ADV (default: 0.10 = 10%)
            - adv_map: מיפוי {conid: average_daily_volume}

    Returns:
        True אם ההזמנה חורגת ממגבלת ADV
    """
    adv_cap = limits.get('adv_cap', 0.10)  # Default: 10%

    # Get ADV for this conid
    adv_map = limits.get('adv_map', {})
    adv = adv_map.get(intent.conid, None)

    if adv is None or adv <= 0:
        logger.warning(
            f"No ADV data for conid={intent.conid}. "
            f"Cannot perform ADV check. Allowing order."
        )
        return False

    # Calculate ADV percentage
    adv_percentage = intent.qty / adv

    if adv_percentage > adv_cap:
        logger.warning(
            f"⚠️  ADV exceeded for conid={intent.conid}: "
            f"{adv_percentage:.2%} > {adv_cap:.2%} "
            f"(qty={intent.qty:,.0f}, ADV={adv:,.0f})"
        )
        return True

    logger.debug(
        f"ADV check passed for conid={intent.conid}: "
        f"{adv_percentage:.2%} <= {adv_cap:.2%}"
    )
    return False


def downscale_qty(intent: OrderIntent, limits: Dict) -> OrderIntent:
    """
    מקטין את כמות ההזמנה כדי לעמוד במגבלות POV/ADV.

    אלגוריתם:
    1. בדיקת POV - אם חורג, הקטנה לפי נפח שוק נוכחי
    2. בדיקת ADV - אם חורג, הקטנה לפי ADV
    3. בחירת הכמות המינימלית מבין שתי הבדיקות
    4. הגבלת כמות מינימלית (min_order_size)

    Args:
        intent: OrderIntent המכיל כמות מקורית
        limits: מילון גבולות

    Returns:
        OrderIntent עם כמות מעודכנת (או מקורית אם לא נדרשה הקטנה)

    דוגמה:
        >>> limits = {
        ...     "pov_cap": 0.08,
        ...     "adv_cap": 0.10,
        ...     "market_volume_map": {12345: 1_000_000},
        ...     "adv_map": {12345: 5_000_000},
        ...     "min_order_size": 100
        ... }
        >>> intent = OrderIntent(
        ...     ts_utc=time.time(),
        ...     conid=12345,
        ...     side='BUY',
        ...     qty=600_000,  # Exceeds both POV and ADV
        ...     tif='DAY',
        ...     meta={}
        ... )
        >>> downscaled = downscale_qty(intent, limits)
        >>> downscaled.qty
        80000.0  # min(0.08 * 1M, 0.10 * 5M) = min(80k, 500k) = 80k
    """
    original_qty = intent.qty

    # Get limits
    pov_cap = limits.get('pov_cap', 0.08)
    adv_cap = limits.get('adv_cap', 0.10)
    min_order_size = limits.get('min_order_size', 100)

    # Get volume data
    market_volume_map = limits.get('market_volume_map', {})
    adv_map = limits.get('adv_map', {})

    current_volume = market_volume_map.get(intent.conid, None)
    adv = adv_map.get(intent.conid, None)

    # Calculate max allowed quantities
    max_qty_candidates = [original_qty]  # Start with original

    # POV constraint
    if current_volume and current_volume > 0:
        max_qty_pov = pov_cap * current_volume
        max_qty_candidates.append(max_qty_pov)
        logger.debug(
            f"POV constraint: max_qty={max_qty_pov:,.0f} "
            f"({pov_cap:.1%} of {current_volume:,.0f})"
        )

    # ADV constraint
    if adv and adv > 0:
        max_qty_adv = adv_cap * adv
        max_qty_candidates.append(max_qty_adv)
        logger.debug(
            f"ADV constraint: max_qty={max_qty_adv:,.0f} "
            f"({adv_cap:.1%} of {adv:,.0f})"
        )

    # Take minimum of all constraints
    new_qty = min(max_qty_candidates)

    # Apply minimum order size
    if new_qty < min_order_size:
        logger.warning(
            f"⚠️  Downscaled qty ({new_qty:,.0f}) below minimum "
            f"({min_order_size:,.0f}). Setting to minimum."
        )
        new_qty = min_order_size

    # Update intent if changed
    if new_qty < original_qty:
        intent.qty = new_qty
        logger.info(
            f"✅ Downscaled order for conid={intent.conid}: "
            f"{original_qty:,.0f} → {new_qty:,.0f} "
            f"({new_qty/original_qty:.1%} of original)"
        )
    else:
        logger.debug(f"No downscaling needed for conid={intent.conid}")

    return intent


def apply_throttling(intent: OrderIntent, limits: Dict) -> Optional[OrderIntent]:
    """
    מנגנון throttling מלא: בדיקה והקטנה אוטומטית.

    תהליך:
    1. בדיקת חריגה מ-POV או ADV
    2. אם חורג - downscaling אוטומטי
    3. אם אחרי downscaling עדיין חורג - דחיית הזמנה
    4. החזרת intent מעודכן או None אם נדחה

    Args:
        intent: OrderIntent
        limits: מילון גבולות

    Returns:
        OrderIntent מעודכן או None אם ההזמנה נדחתה

    דוגמה:
        >>> result = apply_throttling(intent, limits)
        >>> if result is None:
        ...     print("Order rejected")
        ... else:
        ...     await ib_exec.place(result)
    """
    # Check if exceeds POV or ADV
    if exceeds_pov(intent, limits) or exceeds_adv(intent, limits):
        # Try downscaling
        intent = downscale_qty(intent, limits)

        # Re-check after downscaling
        if exceeds_pov(intent, limits) or exceeds_adv(intent, limits):
            logger.error(
                f"❌ Order still exceeds limits after downscaling. "
                f"Rejecting order for conid={intent.conid}"
            )
            return None  # Reject order

    return intent  # Accept order (original or downscaled)


def get_rate_limiter(pacing_rate: int = 50):
    """
    יוצר rate limiter (token bucket) למניעת IBKR pacing violations.

    IBKR מגביל ל-50 בקשות לשנייה. שימוש ב-token bucket מבטיח שלא נחרוג.

    Args:
        pacing_rate: מספר בקשות מקסימלי לשנייה (default: 50)

    Returns:
        RateLimiter instance

    דוגמה:
        >>> limiter = get_rate_limiter(pacing_rate=50)
        >>> async def send_orders():
        ...     for intent in intents:
        ...         await limiter.acquire()  # Wait if necessary
        ...         await ib_exec.place(intent)
    """
    import asyncio
    import time

    class TokenBucketRateLimiter:
        """
        Token bucket rate limiter.

        מאפשר bursts קטנים אבל שומר על ממוצע של pacing_rate לשנייה.
        """

        def __init__(self, rate: int = 50, per: float = 1.0):
            """
            Args:
                rate: מספר tokens (בקשות) לתקופה
                per: תקופה בשניות (default: 1.0)
            """
            self.rate = rate
            self.per = per
            self.tokens = float(rate)
            self.last_refill = time.time()
            self._lock = asyncio.Lock()

        async def acquire(self):
            """
            רכישת token (ממתין אם אין זמין).

            Blocks עד שיש token זמין.
            """
            async with self._lock:
                while self.tokens < 1.0:
                    await self._refill()
                    if self.tokens < 1.0:
                        # Need to wait
                        await asyncio.sleep(0.01)

                # Consume token
                self.tokens -= 1.0

        async def _refill(self):
            """
            מילוי tokens לפי זמן שעבר.
            """
            now = time.time()
            elapsed = now - self.last_refill

            if elapsed > 0:
                # Refill tokens based on elapsed time
                refill_amount = (elapsed / self.per) * self.rate
                self.tokens = min(self.rate, self.tokens + refill_amount)
                self.last_refill = now

    return TokenBucketRateLimiter(rate=pacing_rate, per=1.0)


def estimate_execution_time(intent: OrderIntent, limits: Dict) -> float:
    """
    אומד זמן ביצוע משוער להזמנה (בשניות).

    משתמש במודל פשוט: זמן ביצוע ~ כמות / קצב ממוצע
    קצב ממוצע תלוי ב-POV cap ונפח השוק.

    Args:
        intent: OrderIntent
        limits: מילון גבולות

    Returns:
        זמן ביצוע משוער בשניות

    דוגמה:
        >>> eta = estimate_execution_time(intent, limits)
        >>> print(f"Estimated execution time: {eta:.1f} seconds")
    """
    pov_cap = limits.get('pov_cap', 0.08)

    # Get market volume
    market_volume_map = limits.get('market_volume_map', {})
    current_volume = market_volume_map.get(intent.conid, 1_000_000)

    # Trading session duration (6.5 hours = 23,400 seconds)
    session_duration = 6.5 * 3600

    # Average volume rate (shares/second)
    avg_volume_rate = current_volume / session_duration

    # Our allowed rate (shares/second)
    allowed_rate = pov_cap * avg_volume_rate

    # Execution time estimate
    if allowed_rate > 0:
        execution_time = intent.qty / allowed_rate
    else:
        execution_time = float('inf')  # Unknown

    logger.debug(
        f"Execution time estimate for conid={intent.conid}: "
        f"{execution_time:.1f}s (qty={intent.qty:,.0f}, "
        f"rate={allowed_rate:,.1f} shares/s)"
    )

    return execution_time
