# -*- coding: utf-8 -*-
"""
order_plane/learning/lambda_online.py
למידה מקוונת (online learning) של עלויות טרנזקציה (λ - lambda)

מטרה:
עדכון מודל עלויות הטרנזקציה בזמן אמת על סמך ביצועים ממשיים.
השימוש ב-EMA (Exponential Moving Average) מאפשר הסתגלות מהירה לשינויים בשוק.

מודל:
λ_new = (1 - ρ) × λ_prev + ρ × realized_slippage

כאשר:
- λ: עלות טרנזקציה משוערת
- ρ: קצב למידה (learning rate, רק LAMBDA_EMA_RHO מ-config)
- realized_slippage: slippage בפועל מדוח הביצוע
"""

import logging
import time
from typing import Dict, Optional
from collections import defaultdict
from contracts.validators import ExecutionReport

logger = logging.getLogger(__name__)


class LambdaOnlineLearner:
    """
    מנגנון למידה מקוונת לעלויות טרנזקציה (λ).

    שומר מודל נפרד לכל נייר ערך (conid) ומעדכן אותו בזמן אמת
    על סמך דוחות ביצוע אמיתיים.

    Attributes:
        lambda_map: מיפוי {conid: lambda_current}
        lambda_init: ערך התחלתי ל-λ (default: 5e-4)
        rho: קצב למידה EMA (default: 0.1)
        slip_beta: מקדם למידול slippage (default: 0.7)
        update_count: מונה עדכונים לכל conid
        last_update_time: זמן עדכון אחרון לכל conid

    דוגמה:
        >>> learner = LambdaOnlineLearner(lambda_init=5e-4, rho=0.1)
        >>> report = ExecutionReport(...)
        >>> learner.update(report)
        >>> current_lambda = learner.get_lambda(conid=12345)
    """

    def __init__(
        self,
        lambda_init: float = 5e-4,
        rho: float = 0.1,
        slip_beta: float = 0.7,
        min_lambda: float = 1e-5,
        max_lambda: float = 1e-2,
    ):
        """
        אתחול מנגנון למידה.

        Args:
            lambda_init: ערך התחלתי ל-λ (עלות טרנזקציה)
            rho: קצב למידה EMA (0 < rho <= 1)
                 ערך נמוך יותר = למידה איטית, ערך גבוה יותר = למידה מהירה
            slip_beta: מקדם slippage בנוסחה (0 < beta <= 1)
            min_lambda: ערך מינימלי ל-λ (למניעת ערכים שליליים)
            max_lambda: ערך מקסימלי ל-λ (למניעת ערכים קיצוניים)
        """
        self.lambda_init = lambda_init
        self.rho = rho
        self.slip_beta = slip_beta
        self.min_lambda = min_lambda
        self.max_lambda = max_lambda

        # State tracking per conid
        self.lambda_map: Dict[int, float] = defaultdict(lambda: lambda_init)
        self.update_count: Dict[int, int] = defaultdict(int)
        self.last_update_time: Dict[int, float] = defaultdict(float)

        # Statistics
        self.total_updates = 0
        self.total_slippage_observed = 0.0

        logger.info(
            f"LambdaOnlineLearner initialized: "
            f"lambda_init={lambda_init}, rho={rho}, slip_beta={slip_beta}"
        )

    def update(self, report: ExecutionReport) -> float:
        """
        עדכון מודל λ על סמך דוח ביצוע.

        תהליך:
        1. חילוץ slippage בפועל מהדוח
        2. קבלת λ נוכחי לנייר הערך
        3. חישוב λ חדש באמצעות EMA
        4. הגבלת λ לטווח [min_lambda, max_lambda]
        5. שמירת λ מעודכן

        Args:
            report: ExecutionReport המכיל פרטי ביצוע

        Returns:
            lambda_new: ערך λ מעודכן

        נוסחה:
            realized_cost = |slippage| × slip_beta
            λ_new = (1 - ρ) × λ_prev + ρ × realized_cost
        """
        conid = report.conid
        realized_slippage = abs(report.slippage)

        # Get current lambda for this asset
        lambda_prev = self.lambda_map[conid]

        # Calculate realized transaction cost
        # Using slip_beta to model the relationship between slippage and cost
        realized_cost = realized_slippage * self.slip_beta

        # EMA update
        lambda_new = (1 - self.rho) * lambda_prev + self.rho * realized_cost

        # Clamp to valid range
        lambda_new = max(self.min_lambda, min(self.max_lambda, lambda_new))

        # Update state
        self.lambda_map[conid] = lambda_new
        self.update_count[conid] += 1
        self.last_update_time[conid] = time.time()

        # Statistics
        self.total_updates += 1
        self.total_slippage_observed += realized_slippage

        logger.info(
            f"Updated λ for conid={conid}: "
            f"{lambda_prev:.6f} → {lambda_new:.6f} "
            f"(slippage={realized_slippage:.6f}, updates={self.update_count[conid]})"
        )

        return lambda_new

    def get_lambda(self, conid: int) -> float:
        """
        קבלת ערך λ נוכחי לנייר ערך.

        Args:
            conid: Contract ID

        Returns:
            lambda_current: ערך λ נוכחי (או lambda_init אם לא עודכן מעולם)
        """
        return self.lambda_map.get(conid, self.lambda_init)

    def get_lambda_with_confidence(self, conid: int) -> tuple[float, float]:
        """
        קבלת ערך λ עם רמת ביטחון.

        רמת הביטחון תלויה במספר העדכונים:
        - פחות מ-10 עדכונים: ביטחון נמוך
        - 10-100 עדכונים: ביטחון בינוני
        - מעל 100 עדכונים: ביטחון גבוה

        Args:
            conid: Contract ID

        Returns:
            tuple: (lambda, confidence)
                - lambda: ערך λ נוכחי
                - confidence: רמת ביטחון (0.0 - 1.0)
        """
        lambda_val = self.get_lambda(conid)
        updates = self.update_count.get(conid, 0)

        # Confidence based on number of updates
        if updates == 0:
            confidence = 0.0  # No data
        elif updates < 10:
            confidence = 0.3  # Low confidence
        elif updates < 100:
            confidence = 0.7  # Medium confidence
        else:
            confidence = 1.0  # High confidence

        return lambda_val, confidence

    def reset_lambda(self, conid: int):
        """
        איפוס λ לערך התחלתי עבור נייר ערך מסוים.

        שימושי כאשר מתגלה שינוי משמעותי בתנאי השוק.

        Args:
            conid: Contract ID
        """
        if conid in self.lambda_map:
            old_lambda = self.lambda_map[conid]
            self.lambda_map[conid] = self.lambda_init
            self.update_count[conid] = 0

            logger.warning(
                f"Reset λ for conid={conid}: {old_lambda:.6f} → {self.lambda_init:.6f}"
            )

    def get_statistics(self) -> Dict:
        """
        קבלת סטטיסטיקות על תהליך הלמידה.

        Returns:
            dict עם סטטיסטיקות:
                - total_updates: סה"כ עדכונים
                - total_assets: מספר נכסים שנלמדו
                - avg_lambda: ממוצע λ על כל הנכסים
                - avg_updates_per_asset: ממוצע עדכונים לנכס
                - avg_slippage: ממוצע slippage נצפה
        """
        total_assets = len(self.lambda_map)

        if total_assets > 0:
            avg_lambda = sum(self.lambda_map.values()) / total_assets
            avg_updates = sum(self.update_count.values()) / total_assets
        else:
            avg_lambda = self.lambda_init
            avg_updates = 0

        avg_slippage = (
            self.total_slippage_observed / self.total_updates
            if self.total_updates > 0
            else 0.0
        )

        return {
            "total_updates": self.total_updates,
            "total_assets": total_assets,
            "avg_lambda": avg_lambda,
            "avg_updates_per_asset": avg_updates,
            "avg_slippage": avg_slippage,
            "lambda_init": self.lambda_init,
            "rho": self.rho,
        }

    def export_model(self) -> Dict:
        """
        ייצוא מודל λ לשמירה חיצונית.

        Returns:
            dict המכיל את כל המידע על המודל
        """
        return {
            "lambda_map": dict(self.lambda_map),
            "update_count": dict(self.update_count),
            "last_update_time": dict(self.last_update_time),
            "config": {
                "lambda_init": self.lambda_init,
                "rho": self.rho,
                "slip_beta": self.slip_beta,
                "min_lambda": self.min_lambda,
                "max_lambda": self.max_lambda,
            },
            "statistics": self.get_statistics(),
        }

    def import_model(self, model_data: Dict):
        """
        ייבוא מודל λ משמור.

        Args:
            model_data: dict שהוחזר מ-export_model()
        """
        self.lambda_map = defaultdict(
            lambda: self.lambda_init, model_data.get("lambda_map", {})
        )
        self.update_count = defaultdict(int, model_data.get("update_count", {}))
        self.last_update_time = defaultdict(
            float, model_data.get("last_update_time", {})
        )

        logger.info(
            f"Imported λ model: {len(self.lambda_map)} assets, "
            f"{sum(self.update_count.values())} total updates"
        )


# Global learner instance (singleton pattern)
_global_learner: Optional[LambdaOnlineLearner] = None


def get_global_learner(
    lambda_init: float = 5e-4,
    rho: float = 0.1,
    slip_beta: float = 0.7,
) -> LambdaOnlineLearner:
    """
    קבלת instance גלובלי של LambdaOnlineLearner.

    משתמש בדפוס singleton כדי לשתף מצב בין מודולים שונים.

    Args:
        lambda_init: ערך התחלתי (משמש רק בפעם הראשונה)
        rho: קצב למידה (משמש רק בפעם הראשונה)
        slip_beta: מקדם slippage (משמש רק בפעם הראשונה)

    Returns:
        LambdaOnlineLearner instance
    """
    global _global_learner

    if _global_learner is None:
        _global_learner = LambdaOnlineLearner(
            lambda_init=lambda_init,
            rho=rho,
            slip_beta=slip_beta,
        )
        logger.info("Created global λ learner instance")

    return _global_learner


def update_lambda_online(report: ExecutionReport):
    """
    עדכון מודל λ גלובלי על סמך דוח ביצוע.

    זוהי הפונקציה הפשוטה המשמשת ב-orchestrator.

    Args:
        report: ExecutionReport המכיל פרטי ביצוע

    דוגמה:
        >>> async def consume_execution_reports(bus):
        ...     async for report in bus.consume("exec_reports"):
        ...         update_lambda_online(report)
    """
    learner = get_global_learner()
    learner.update(report)


def get_current_lambda(conid: int) -> float:
    """
    קבלת ערך λ נוכחי לנייר ערך מהמודל הגלובלי.

    Args:
        conid: Contract ID

    Returns:
        lambda_current: ערך λ נוכחי
    """
    learner = get_global_learner()
    return learner.get_lambda(conid)


def initialize_from_config(cfg: Dict):
    """
    אתחול מנגנון הלמידה מקובץ קונפיגורציה.

    Args:
        cfg: קונפיגורציה המכילה:
            - LAMBDA_INIT: ערך התחלתי
            - LAMBDA_EMA_RHO: קצב למידה
            - SLIP_BETA: מקדם slippage

    דוגמה:
        >>> from algo_trade.core.config import load_config
        >>> cfg = load_config()
        >>> initialize_from_config(cfg)
    """
    lambda_init = cfg.get('LAMBDA_INIT', 5e-4)
    rho = cfg.get('LAMBDA_EMA_RHO', 0.1)
    slip_beta = cfg.get('SLIP_BETA', 0.7)

    global _global_learner
    _global_learner = LambdaOnlineLearner(
        lambda_init=lambda_init,
        rho=rho,
        slip_beta=slip_beta,
    )

    logger.info(
        f"Initialized λ learner from config: "
        f"lambda_init={lambda_init}, rho={rho}, slip_beta={slip_beta}"
    )


def export_lambda_model(filepath: str):
    """
    שמירת מודל λ לקובץ.

    Args:
        filepath: נתיב לקובץ (JSON)
    """
    import json

    learner = get_global_learner()
    model_data = learner.export_model()

    with open(filepath, 'w') as f:
        json.dump(model_data, f, indent=2)

    logger.info(f"Exported λ model to {filepath}")


def import_lambda_model(filepath: str):
    """
    טעינת מודל λ מקובץ.

    Args:
        filepath: נתיב לקובץ (JSON)
    """
    import json

    with open(filepath, 'r') as f:
        model_data = json.load(f)

    learner = get_global_learner()
    learner.import_model(model_data)

    logger.info(f"Imported λ model from {filepath}")
