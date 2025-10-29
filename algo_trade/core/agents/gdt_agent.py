# -*- coding: utf-8 -*-
"""
gdt_agent.py
סוכן GDT (Geometric Dynamic Trading) - סוכן מסחר אלגוריתמי מבוסס גיאומטריה

הסוכן משתמש במדדים גיאומטריים של שוק המניות כדי לזהות מצבי שוק
ולקבל החלטות מסחר על בסיס מכונת מצבים סופית.

מצבי שוק:
- STABLE (יציב/גיאודזי): עקמומיות נמוכה, תנודתיות נמוכה
- STRESSED (לחוץ/קדם-מעבר): עלייה בתנודתיות העקמומיות
- BIFURCATION (ביפורקציה/משבר): התאמה לחוק חזקה, קריסה קרובה
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional
from enum import Enum
from dataclasses import dataclass

from .geometric_indicators import GeometricIndicators


class MarketState(Enum):
    """מצבי שוק אפשריים."""
    STABLE = 0          # יציב/גיאודזי
    STRESSED = 1        # לחוץ/קדם-מעבר
    BIFURCATION = 2     # ביפורקציה קרובה/משבר


@dataclass
class GDTThresholds:
    """
    ספי המדדים להחלטה על מצב השוק.

    Attributes:
        T1: סף תנודתיות עקמומיות
        T2: סף סטייה גיאודזית
        T3: סף מהירות יריעה
        power_law_confidence: סף ביטחון להתאמת חוק חזקה
    """
    T1: float = 0.5      # סף תנודתיות עקמומיות
    T2: float = 0.3      # סף סטייה גיאודזית
    T3: float = 1.0      # סף מהירות יריעה
    power_law_confidence: float = 0.7  # סף ביטחון לחוק חזקה


@dataclass
class TradingAction:
    """
    פעולת מסחר מומלצת.

    Attributes:
        action_type: סוג הפעולה ('hold', 'reduce', 'hedge', 'exit')
        exposure: רמת חשיפה מומלצת (0-1)
        position: סוג פוזיציה ('long', 'short', 'neutral')
        description: תיאור הפעולה
    """
    action_type: str
    exposure: float
    position: str
    description: str


class GDTAgent:
    """
    סוכן GDT למסחר אלגוריתמי מבוסס גיאומטריה.

    הסוכן משלב מדדים גיאומטריים עם מכונת מצבים סופית כדי
    לזהות מצבי שוק ולבצע פעולות מסחר בהתאם.
    """

    def __init__(self,
                 thresholds: Optional[GDTThresholds] = None,
                 k_neighbors: int = 10,
                 window: int = 60):
        """
        אתחול סוכן GDT.

        Args:
            thresholds: ספי ההחלטה (אם None, משתמש בברירות מחדל)
            k_neighbors: מספר שכנים קרובים לגרף k-NN
            window: חלון זמן בימים לחישוב מדדים
        """
        self.thresholds = thresholds or GDTThresholds()
        self.geometric_calc = GeometricIndicators(k_neighbors, window)

        # מצב נוכחי
        self.current_state = MarketState.STABLE

        # היסטוריה
        self.state_history: List[MarketState] = []
        self.indicators_history: List[Dict] = []

        # מטריצת שכנויות קודמת (לחישוב מהירות יריעה)
        self.adjacency_prev: Optional[np.ndarray] = None

        # מטריצת כללים: מצב → פעולה
        self.rule_matrix = self._build_rule_matrix()

    def _build_rule_matrix(self) -> Dict[MarketState, TradingAction]:
        """
        בניית מטריצת הכללים: מיפוי מצבים לפעולות מסחר.

        Returns:
            מילון המקשר מצב שוק לפעולת מסחר
        """
        return {
            MarketState.STABLE: TradingAction(
                action_type='hold',
                exposure=1.0,
                position='long',
                description='שמור על חשיפה מלאה (100% long) - השוק יציב'
            ),
            MarketState.STRESSED: TradingAction(
                action_type='reduce',
                exposure=0.5,
                position='long',
                description='הקטן חשיפה ל-50% - השוק לחוץ'
            ),
            MarketState.BIFURCATION: TradingAction(
                action_type='exit_and_short',
                exposure=0.5,
                position='short',
                description='סגור long, פתח short 50% - ביפורקציה קרובה'
            )
        }

    def determine_market_state(self, indicators: Dict) -> MarketState:
        """
        קביעת מצב השוק על בסיס המדדים הגיאומטריים.

        לוגיקת מעברי מצבים (על בסיס טבלה 3 בתיאוריה):
        - אם curvature_volatility >= T1 → מעבר ל-STRESSED
        - אם geodesic_deviation >= T2 → מעבר ל-STRESSED
        - אם power_law_fit מצביע על חוק חזקה עם β≈0.5 → מעבר ל-BIFURCATION
        - אם חזרה מתחת לספים → חזרה ל-STABLE

        Args:
            indicators: מדדים גיאומטריים

        Returns:
            מצב השוק הנוכחי
        """
        curv_vol = indicators['curvature_volatility']
        geo_dev = indicators['geodesic_deviation']
        power_law = indicators['power_law_fit']

        # בדיקת מעבר ל-BIFURCATION (בעדיפות הגבוהה ביותר)
        if power_law['is_power_law'] and power_law['confidence'] >= self.thresholds.power_law_confidence:
            return MarketState.BIFURCATION

        # בדיקת מעבר ל-STRESSED
        if curv_vol >= self.thresholds.T1 or geo_dev >= self.thresholds.T2:
            return MarketState.STRESSED

        # אם המדדים נמוכים, השוק יציב
        if curv_vol < self.thresholds.T1 and geo_dev < self.thresholds.T2:
            return MarketState.STABLE

        # אחרת, שמור על המצב הנוכחי
        return self.current_state

    def get_recommended_action(self, state: MarketState) -> TradingAction:
        """
        קבלת הפעולה המומלצת עבור מצב שוק נתון.

        Args:
            state: מצב השוק

        Returns:
            פעולת מסחר מומלצת
        """
        return self.rule_matrix[state]

    def process_market_data(self, prices: pd.DataFrame) -> Tuple[MarketState, TradingAction, Dict]:
        """
        עיבוד נתוני שוק וקבלת המלצת מסחר.

        זהו צינור העיבוד המלא:
        1. חישוב מדדים גיאומטריים
        2. קביעת מצב שוק
        3. קבלת פעולה מומלצת

        Args:
            prices: מחירי נכסים (DataFrame)

        Returns:
            tuple של (מצב שוק, פעולה מומלצת, מדדים)
        """
        # שלב 1: חישוב מדדים גיאומטריים
        indicators = self.geometric_calc.compute_all_indicators(
            prices,
            adjacency_prev=self.adjacency_prev
        )

        # עדכון מטריצת שכנויות קודמת
        self.adjacency_prev = indicators['adjacency_matrix']

        # שלב 2: קביעת מצב שוק
        new_state = self.determine_market_state(indicators)

        # זיהוי מעברי מצבים
        if new_state != self.current_state:
            print(f"🔄 מעבר מצב: {self.current_state.name} → {new_state.name}")

        self.current_state = new_state

        # שלב 3: קבלת פעולה מומלצת
        recommended_action = self.get_recommended_action(new_state)

        # עדכון היסטוריה
        self.state_history.append(new_state)
        self.indicators_history.append(indicators)

        return new_state, recommended_action, indicators

    def generate_portfolio_weights(self,
                                   action: TradingAction,
                                   current_weights: pd.Series,
                                   market_index: str = 'SPY') -> pd.Series:
        """
        יצירת משקולות פורטפוליו על בסיס הפעולה המומלצת.

        Args:
            action: פעולת המסחר המומלצת
            current_weights: משקולות נוכחיות
            market_index: שם המדד (לפוזיציות short)

        Returns:
            משקולות פורטפוליו חדשות
        """
        n_assets = len(current_weights)
        new_weights = current_weights.copy()

        if action.action_type == 'hold':
            # שמירה על החשיפה הנוכחית
            pass

        elif action.action_type == 'reduce':
            # הקטנת חשיפה לפי exposure
            new_weights = current_weights * action.exposure

        elif action.action_type == 'exit_and_short':
            # סגירת long, פתיחת short
            # במציאות, זה ידרוש לוגיקה מורכבת יותר
            # כאן נייצר וקטור short פשוט
            if market_index in current_weights.index:
                new_weights[:] = 0.0
                new_weights[market_index] = -action.exposure
            else:
                # אם אין מדד, חלק שווה בין כל הנכסים
                new_weights[:] = -action.exposure / n_assets

        # נירמול לחשיפה מוגדרת
        weight_sum = abs(new_weights).sum()
        if weight_sum > 0:
            new_weights = new_weights * action.exposure / weight_sum

        return new_weights

    def get_state_statistics(self) -> Dict:
        """
        חישוב סטטיסטיקות על היסטוריית המצבים.

        Returns:
            מילון עם סטטיסטיקות
        """
        if not self.state_history:
            return {}

        state_counts = {}
        for state in MarketState:
            state_counts[state.name] = self.state_history.count(state)

        total = len(self.state_history)

        return {
            'total_observations': total,
            'state_counts': state_counts,
            'state_percentages': {k: v / total * 100 for k, v in state_counts.items()},
            'current_state': self.current_state.name
        }

    def reset(self):
        """איפוס הסוכן למצב התחלתי."""
        self.current_state = MarketState.STABLE
        self.state_history = []
        self.indicators_history = []
        self.adjacency_prev = None
        self.geometric_calc.reset_history()


# =============================================================================
# פונקציה ראשית: לולאת סוכן GDT (פסאודו-קוד מתורגם)
# =============================================================================

def GDT_Agent_Main_Loop(current_portfolio: pd.Series,
                       market_data_feed: pd.DataFrame,
                       gdt_agent: Optional[GDTAgent] = None) -> Tuple[pd.Series, Dict]:
    """
    לולאת הביצוע הראשית של סוכן GDT.

    זהו תרגום ישיר של הפסאודו-קוד מהתיאוריה.

    Args:
        current_portfolio: משקולות הפורטפוליו הנוכחיות
        market_data_feed: נתוני שוק (מחירים)
        gdt_agent: אובייקט הסוכן (אם None, יצירת סוכן חדש)

    Returns:
        tuple של (פקודות מסחר, מידע נוסף)
    """
    # שלב 1: קליטת נתונים
    latest_prices = market_data_feed

    # אם אין סוכן, צור אחד חדש
    if gdt_agent is None:
        gdt_agent = GDTAgent()

    # שלב 2-4: עיבוד נתוני השוק וחישוב מדדים
    # (זה מתבצע ב-process_market_data)
    market_state, recommended_action, indicators = gdt_agent.process_market_data(latest_prices)

    # שלב 5: ביצוע לוגיקת מסחר
    # יצירת פקודות מסחר על בסיס הפעולה והפורטפוליו הנוכחי
    trade_orders = gdt_agent.generate_portfolio_weights(
        recommended_action,
        current_portfolio
    )

    # מידע נוסף להחזרה
    info = {
        'market_state': market_state.name,
        'action': recommended_action.action_type,
        'exposure': recommended_action.exposure,
        'position': recommended_action.position,
        'description': recommended_action.description,
        'indicators': {
            'mean_curvature': indicators['mean_curvature'],
            'curvature_volatility': indicators['curvature_volatility'],
            'manifold_velocity': indicators['manifold_velocity'],
            'geodesic_deviation': indicators['geodesic_deviation'],
            'power_law_fit': indicators['power_law_fit']
        }
    }

    return trade_orders, info


# =============================================================================
# דוגמה לשימוש
# =============================================================================

def example_usage():
    """
    דוגמה לשימוש בסוכן GDT.
    """
    # יצירת נתוני דמה
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=100, freq='D')
    assets = [f'Asset_{i}' for i in range(20)]

    # סימולציה של מחירים
    prices = pd.DataFrame(
        100 * np.exp(np.random.randn(100, 20).cumsum(axis=0) * 0.01),
        index=dates,
        columns=assets
    )

    # יצירת סוכן
    gdt_agent = GDTAgent(
        thresholds=GDTThresholds(T1=0.4, T2=0.25),
        k_neighbors=8,
        window=60
    )

    # פורטפוליו התחלתי
    current_portfolio = pd.Series(0.05, index=assets)  # 5% לכל נכס

    # הרצת לולאה
    print("🚀 התחלת סימולציה של סוכן GDT\n")

    for i in range(60, len(prices)):
        # חלון נתונים
        window_prices = prices.iloc[:i]

        # הרצת הסוכן
        trade_orders, info = GDT_Agent_Main_Loop(
            current_portfolio,
            window_prices,
            gdt_agent
        )

        # עדכון הפורטפוליו
        current_portfolio = trade_orders

        # הדפסת מידע
        if i % 10 == 0:
            print(f"יום {i:>3} | מצב: {info['market_state']:<15} | "
                  f"פעולה: {info['action']:<15} | חשיפה: {info['exposure']:.1%}")
            print(f"        | Curv Vol: {info['indicators']['curvature_volatility']:.4f} | "
                  f"Geo Dev: {info['indicators']['geodesic_deviation']:.4f} | "
                  f"Manifold V: {info['indicators']['manifold_velocity']:.4f}")
            print()

    # סטטיסטיקות סיכום
    stats = gdt_agent.get_state_statistics()
    print("\n📊 סטטיסטיקות סיכום:")
    print(f"סך תצפיות: {stats['total_observations']}")
    print("התפלגות מצבים:")
    for state, pct in stats['state_percentages'].items():
        print(f"  {state}: {pct:.1f}%")


if __name__ == "__main__":
    example_usage()
