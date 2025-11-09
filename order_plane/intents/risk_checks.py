# -*- coding: utf-8 -*-
"""
order_plane/intents/risk_checks.py
בדיקות סיכון לפני ביצוע הזמנות (Pre-Trade Risk Checks)

אחריות:
- בדיקת גבולות פוזיציה (box limits)
- בדיקת חשיפה ברוטו/נטו (gross/net exposure)
- אכיפת kill-switches (PnL, drawdown, PSR)
- בדיקת תקינות הזמנה (quantity, price)
- מניעת הזמנות חריגות
"""

import logging
import time
from typing import Dict, Optional, Tuple
from collections import defaultdict
from contracts.validators import OrderIntent

logger = logging.getLogger(__name__)


class PreTradeRisk:
    """
    מנגנון בדיקות סיכון לפני ביצוע הזמנות.

    אחריות:
    1. בדיקות ברמת הזמנה בודדת (Box Limits)
    2. בדיקות ברמת תיק (Gross/Net Exposure)
    3. Kill-Switches (עצירת מסחר אוטומטית)
    4. בדיקות תקינות בסיסיות

    דוגמה:
        >>> risk = PreTradeRisk()
        >>> limits = {
        ...     "box_lim": 0.25,
        ...     "gross_lim": {"Normal": 2.0},
        ...     "net_lim": {"Normal": 0.8},
        ...     "kill_pnl": -0.05,
        ...     "max_dd_kill_switch": 0.15,
        ...     "psr_kill_switch": 0.20
        ... }
        >>> if risk.validate(intent, limits):
        ...     await place_order(intent)
        ... else:
        ...     logger.warning("Order rejected by risk checks")
    """

    def __init__(self):
        """
        אתחול מנגנון בדיקות סיכון.
        """
        # Position tracking (per conid)
        self.current_positions: Dict[int, float] = defaultdict(float)
        self.position_values: Dict[int, float] = defaultdict(float)

        # Portfolio metrics
        self.gross_exposure = 0.0
        self.net_exposure = 0.0
        self.total_nav = 1_000_000.0  # Default NAV (should be updated from account)

        # Kill-switch state
        self.kill_switch_active = False
        self.kill_switch_reason = None
        self.kill_switch_time = None

        # Performance tracking for PSR kill-switch
        self.session_pnl = 0.0
        self.session_start_nav = self.total_nav
        self.peak_nav = self.total_nav
        self.returns_history = []

        # Rejected orders counter
        self.rejected_count = defaultdict(int)

        logger.info("PreTradeRisk initialized")

    def validate(self, intent: OrderIntent, limits: Dict) -> bool:
        """
        בדיקת תקינות הזמנה מול כל גבולות הסיכון.

        תהליך:
        1. בדיקת kill-switch פעיל
        2. בדיקת תקינות בסיסית
        3. בדיקת box limits (הזמנה בודדת)
        4. בדיקת gross/net exposure (תיק)
        5. בדיקת kill-switches (PnL, Drawdown, PSR)

        Args:
            intent: OrderIntent המכיל פרטי ההזמנה
            limits: מילון גבולות הכולל:
                - box_lim: גבול פוזיציה מקסימלי (% מ-NAV)
                - gross_lim: חשיפה ברוטו מקסימלית
                - net_lim: חשיפה נטו מקסימלית
                - kill_pnl: סף הפסד להפעלת kill-switch (%)
                - max_dd_kill_switch: drawdown מקסימלי (%)
                - psr_kill_switch: PSR מינימלי

        Returns:
            True אם ההזמנה עוברת את כל הבדיקות, False אחרת
        """
        # 1. Check if kill-switch is active
        if self.kill_switch_active:
            logger.error(
                f"❌ KILL-SWITCH ACTIVE: {self.kill_switch_reason}. "
                f"Order rejected for conid={intent.conid}"
            )
            self.rejected_count[intent.conid] += 1
            return False

        # 2. Basic sanity checks
        if not self._basic_sanity_check(intent):
            self.rejected_count[intent.conid] += 1
            return False

        # 3. Box limits (single position)
        if not self._within_box(intent, limits):
            logger.warning(
                f"⚠️  Box limit exceeded for conid={intent.conid}. Order rejected."
            )
            self.rejected_count[intent.conid] += 1
            return False

        # 4. Gross/Net exposure limits (portfolio level)
        if not self._within_gross_net(intent, limits):
            logger.warning(
                f"⚠️  Gross/Net exposure limit exceeded. Order rejected."
            )
            self.rejected_count[intent.conid] += 1
            return False

        # 5. Check kill-switches (PnL, Drawdown, PSR)
        if self._should_activate_kill_switch(limits):
            logger.error(
                f"❌ Kill-switch activated: {self.kill_switch_reason}. "
                f"Halting all trading."
            )
            self.rejected_count[intent.conid] += 1
            return False

        # All checks passed
        logger.debug(f"✅ Risk checks passed for conid={intent.conid}")
        return True

    def _basic_sanity_check(self, intent: OrderIntent) -> bool:
        """
        בדיקות תקינות בסיסיות.

        בודק:
        - כמות חיובית
        - conid תקין
        - side תקין
        - TIF תקין
        - מחיר סביר (אם limit order)

        Args:
            intent: OrderIntent

        Returns:
            True אם עובר בדיקות בסיסיות
        """
        # Quantity must be positive
        if intent.qty <= 0:
            logger.error(
                f"❌ Invalid quantity: {intent.qty} (must be positive)"
            )
            return False

        # Quantity must be reasonable (< 1M shares for single order)
        if intent.qty > 1_000_000:
            logger.error(
                f"❌ Quantity too large: {intent.qty:,.0f} (max: 1M shares)"
            )
            return False

        # conid must be valid
        if intent.conid <= 0:
            logger.error(f"❌ Invalid conid: {intent.conid}")
            return False

        # Side must be BUY or SELL
        if intent.side not in ['BUY', 'SELL']:
            logger.error(f"❌ Invalid side: {intent.side}")
            return False

        # TIF must be valid
        if intent.tif not in ['DAY', 'IOC', 'GTC']:
            logger.error(f"❌ Invalid TIF: {intent.tif}")
            return False

        # If limit order, price must be positive and reasonable
        if intent.price is not None:
            if intent.price <= 0:
                logger.error(f"❌ Invalid price: {intent.price} (must be positive)")
                return False

            # Price should be reasonable (e.g., $0.01 - $10,000)
            if intent.price < 0.01 or intent.price > 10_000:
                logger.warning(
                    f"⚠️  Unusual price: {intent.price} "
                    f"(outside typical range $0.01-$10,000)"
                )

        return True

    def _within_box(self, intent: OrderIntent, limits: Dict) -> bool:
        """
        בדיקת גבול פוזיציה בודדת (Box Limit).

        Box Limit מגדיר את גודל הפוזיציה המקסימלי לנייר ערך בודד
        כאחוז מ-NAV.

        דוגמה: אם box_lim=0.25 ו-NAV=$1M, פוזיציה מקסימלית = $250k

        Args:
            intent: OrderIntent
            limits: מילון גבולות

        Returns:
            True אם הפוזיציה החדשה לא תחרוג מגבול הbox
        """
        box_lim = limits.get('box_lim', 0.25)  # Default: 25% of NAV

        # Get current position for this asset
        current_qty = self.current_positions.get(intent.conid, 0.0)

        # Calculate new position after this order
        if intent.side == 'BUY':
            new_qty = current_qty + intent.qty
        else:  # SELL
            new_qty = current_qty - intent.qty

        # Estimate position value (need price)
        # If we don't have price, use a conservative estimate
        price = intent.price if intent.price else 100.0  # Default estimate
        new_position_value = abs(new_qty * price)

        # Calculate as percentage of NAV
        position_pct = new_position_value / self.total_nav

        if position_pct > box_lim:
            logger.warning(
                f"⚠️  Box limit exceeded for conid={intent.conid}: "
                f"{position_pct:.2%} > {box_lim:.2%} "
                f"(position_value=${new_position_value:,.0f}, NAV=${self.total_nav:,.0f})"
            )
            return False

        logger.debug(
            f"Box check passed for conid={intent.conid}: "
            f"{position_pct:.2%} <= {box_lim:.2%}"
        )
        return True

    def _within_gross_net(self, intent: OrderIntent, limits: Dict) -> bool:
        """
        בדיקת גבולות חשיפה ברוטו ונטו (Gross/Net Exposure).

        - Gross Exposure: סכום ערך מוחלט של כל הפוזיציות
        - Net Exposure: סכום ערך נטו (long - short)

        Args:
            intent: OrderIntent
            limits: מילון גבולות המכיל:
                - gross_lim: מילון {regime: max_gross}
                - net_lim: מילון {regime: max_net}
                - regime: regime נוכחי (default: "Normal")

        Returns:
            True אם החשיפה החדשה לא תחרוג מגבולות
        """
        # Get regime (default to "Normal")
        regime = limits.get('regime', 'Normal')

        # Get gross/net limits for current regime
        gross_lim_map = limits.get('gross_lim', {"Normal": 2.0})
        net_lim_map = limits.get('net_lim', {"Normal": 0.8})

        max_gross = gross_lim_map.get(regime, 2.0)
        max_net = net_lim_map.get(regime, 0.8)

        # Estimate new exposure after this order
        price = intent.price if intent.price else 100.0
        order_value = intent.qty * price

        current_qty = self.current_positions.get(intent.conid, 0.0)

        if intent.side == 'BUY':
            new_qty = current_qty + intent.qty
        else:
            new_qty = current_qty - intent.qty

        new_position_value = new_qty * price
        old_position_value = current_qty * price

        # Update gross/net exposure estimates
        # (Simplified: assumes we only track this one position change)
        gross_delta = abs(new_position_value) - abs(old_position_value)
        net_delta = new_position_value - old_position_value

        new_gross = self.gross_exposure + gross_delta
        new_net = self.net_exposure + net_delta

        # Check gross limit
        gross_ratio = new_gross / self.total_nav
        if gross_ratio > max_gross:
            logger.warning(
                f"⚠️  Gross exposure exceeded: {gross_ratio:.2f}x > {max_gross:.2f}x "
                f"(regime={regime})"
            )
            return False

        # Check net limit
        net_ratio = abs(new_net) / self.total_nav
        if net_ratio > max_net:
            logger.warning(
                f"⚠️  Net exposure exceeded: {net_ratio:.2f}x > {max_net:.2f}x "
                f"(regime={regime})"
            )
            return False

        logger.debug(
            f"Gross/Net check passed: gross={gross_ratio:.2f}x <= {max_gross:.2f}x, "
            f"net={net_ratio:.2f}x <= {max_net:.2f}x"
        )
        return True

    def _should_activate_kill_switch(self, limits: Dict) -> bool:
        """
        בדיקה אם יש להפעיל kill-switch.

        Kill-switches מפסיקים את כל המסחר במקרה של:
        1. הפסד PnL חריג (> kill_pnl)
        2. Drawdown גבוה מדי (> max_dd_kill_switch)
        3. PSR נמוך מדי (< psr_kill_switch)

        Args:
            limits: מילון גבולות

        Returns:
            True אם יש להפעיל kill-switch
        """
        if self.kill_switch_active:
            return True  # Already active

        # 1. PnL Kill-Switch
        kill_pnl_threshold = limits.get('kill_pnl', -0.05)  # Default: -5%
        pnl_pct = self.session_pnl / self.session_start_nav

        if pnl_pct < kill_pnl_threshold:
            self._activate_kill_switch(
                f"PnL Kill-Switch: {pnl_pct:.2%} < {kill_pnl_threshold:.2%}"
            )
            return True

        # 2. Drawdown Kill-Switch
        max_dd_threshold = limits.get('max_dd_kill_switch', 0.15)  # Default: 15%
        current_nav = self.session_start_nav + self.session_pnl
        drawdown = (self.peak_nav - current_nav) / self.peak_nav if self.peak_nav > 0 else 0.0

        if drawdown > max_dd_threshold:
            self._activate_kill_switch(
                f"Drawdown Kill-Switch: {drawdown:.2%} > {max_dd_threshold:.2%}"
            )
            return True

        # 3. PSR Kill-Switch (Probabilistic Sharpe Ratio)
        psr_threshold = limits.get('psr_kill_switch', 0.20)  # Default: 0.20
        psr = self._calculate_psr()

        if psr is not None and psr < psr_threshold:
            self._activate_kill_switch(
                f"PSR Kill-Switch: {psr:.2f} < {psr_threshold:.2f}"
            )
            return True

        return False

    def _activate_kill_switch(self, reason: str):
        """
        הפעלת kill-switch - הפסקת כל המסחר.

        Args:
            reason: סיבה להפעלת kill-switch
        """
        self.kill_switch_active = True
        self.kill_switch_reason = reason
        self.kill_switch_time = time.time()

        logger.critical(
            f"🚨 KILL-SWITCH ACTIVATED: {reason} 🚨\n"
            f"All trading halted. Manual intervention required."
        )

    def _calculate_psr(self) -> Optional[float]:
        """
        חישוב Probabilistic Sharpe Ratio (PSR).

        PSR מעריך את הסיכוי ש-Sharpe Ratio האמיתי חיובי,
        תוך התחשבות בשונות וב-skewness של התשואות.

        Returns:
            PSR (0-1) או None אם אין מספיק נתונים
        """
        if len(self.returns_history) < 10:
            return None  # Not enough data

        import numpy as np
        from scipy import stats

        returns = np.array(self.returns_history)

        if len(returns) == 0:
            return None

        # Calculate Sharpe ratio
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return == 0:
            return 1.0 if mean_return > 0 else 0.0

        sharpe = mean_return / std_return

        # Calculate skewness and kurtosis
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns)

        # PSR formula (Simplified Bailey & Lopez de Prado)
        n = len(returns)
        psr_stat = (sharpe * np.sqrt(n - 1)) / np.sqrt(1 - skew * sharpe + ((kurt - 1) / 4) * sharpe**2)

        # Convert to probability using normal CDF
        psr = stats.norm.cdf(psr_stat)

        return psr

    def update_position(self, conid: int, qty: float, price: float):
        """
        עדכון פוזיציה אחרי ביצוע הזמנה.

        Args:
            conid: Contract ID
            qty: כמות (חיובי=long, שלילי=short)
            price: מחיר ביצוע
        """
        old_qty = self.current_positions.get(conid, 0.0)
        new_qty = old_qty + qty

        self.current_positions[conid] = new_qty
        self.position_values[conid] = new_qty * price

        # Recalculate gross/net exposure
        self._recalculate_exposure()

        logger.debug(
            f"Position updated: conid={conid}, "
            f"{old_qty:,.0f} → {new_qty:,.0f} @ ${price:.2f}"
        )

    def update_pnl(self, pnl_delta: float):
        """
        עדכון PnL והוספת תשואה להיסטוריה.

        Args:
            pnl_delta: שינוי ב-PnL
        """
        self.session_pnl += pnl_delta

        current_nav = self.session_start_nav + self.session_pnl

        # Update peak for drawdown calculation
        if current_nav > self.peak_nav:
            self.peak_nav = current_nav

        # Calculate return for this period
        period_return = pnl_delta / current_nav if current_nav > 0 else 0.0
        self.returns_history.append(period_return)

        # Keep only recent returns (e.g., last 100)
        if len(self.returns_history) > 100:
            self.returns_history.pop(0)

    def _recalculate_exposure(self):
        """
        חישוב מחדש של חשיפה ברוטו ונטו.
        """
        self.gross_exposure = sum(abs(v) for v in self.position_values.values())
        self.net_exposure = sum(self.position_values.values())

    def reset_kill_switch(self):
        """
        איפוס kill-switch (דורש התערבות ידנית).
        """
        if self.kill_switch_active:
            logger.warning(
                f"⚠️  Kill-switch reset. Reason was: {self.kill_switch_reason}"
            )

        self.kill_switch_active = False
        self.kill_switch_reason = None
        self.kill_switch_time = None

    def get_risk_status(self) -> Dict:
        """
        קבלת סטטוס מלא של מנגנון הסיכון.

        Returns:
            dict עם מצב נוכחי:
                - kill_switch_active: האם kill-switch פעיל
                - gross_exposure: חשיפה ברוטו
                - net_exposure: חשיפה נטו
                - session_pnl: PnL של המושב
                - drawdown: drawdown נוכחי
                - psr: PSR נוכחי
                - rejected_orders: מספר הזמנות שנדחו
        """
        current_nav = self.session_start_nav + self.session_pnl
        drawdown = (self.peak_nav - current_nav) / self.peak_nav if self.peak_nav > 0 else 0.0
        psr = self._calculate_psr()

        return {
            "kill_switch_active": self.kill_switch_active,
            "kill_switch_reason": self.kill_switch_reason,
            "kill_switch_time": self.kill_switch_time,
            "gross_exposure": self.gross_exposure,
            "gross_exposure_ratio": self.gross_exposure / self.total_nav,
            "net_exposure": self.net_exposure,
            "net_exposure_ratio": self.net_exposure / self.total_nav,
            "session_pnl": self.session_pnl,
            "session_pnl_pct": self.session_pnl / self.session_start_nav,
            "peak_nav": self.peak_nav,
            "current_nav": current_nav,
            "drawdown": drawdown,
            "psr": psr,
            "total_positions": len(self.current_positions),
            "total_rejected": sum(self.rejected_count.values()),
        }

    def set_nav(self, nav: float):
        """
        עדכון NAV (מ-account probe).

        Args:
            nav: Net Asset Value
        """
        old_nav = self.total_nav
        self.total_nav = nav

        if self.session_start_nav == old_nav:
            self.session_start_nav = nav
            self.peak_nav = nav

        logger.info(f"NAV updated: ${old_nav:,.0f} → ${nav:,.0f}")
