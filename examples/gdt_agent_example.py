# -*- coding: utf-8 -*-
"""
דוגמה לשימוש בסוכן GDT (Geometric Dynamic Trading)

דוגמה זו מראה איך להשתמש בסוכן GDT באופן עצמאי
לזיהוי מצבי שוק וקבלת המלצות מסחר.
"""

import numpy as np
import pandas as pd
import sys
import os

# הוספת נתיב לפרויקט
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from algo_trade.core.agents import GDTAgent, MarketState, GDTThresholds


def simulate_market_prices(n_assets: int = 20, n_days: int = 200, volatility: float = 0.02):
    """
    סימולציה של מחירי שוק.

    Args:
        n_assets: מספר נכסים
        n_days: מספר ימים
        volatility: תנודתיות יומית

    Returns:
        DataFrame של מחירים
    """
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=n_days, freq='D')
    assets = [f'Asset_{i}' for i in range(n_assets)]

    # יצירת תשואות עם קורלציה משתנה (סימולציה של מצבי שוק שונים)
    returns = []
    for t in range(n_days):
        # הגדלת קורלציה ותנודתיות לקראת ימים 100-120 (סימולציה של משבר)
        if 100 <= t <= 120:
            # מצב לחוץ/משבר
            corr_factor = 0.7
            vol_factor = 3.0
        elif 80 <= t < 100:
            # מצב מעבר
            corr_factor = 0.4
            vol_factor = 1.5
        else:
            # מצב רגיל
            corr_factor = 0.2
            vol_factor = 1.0

        # יצירת תשואות מתואמות
        common_shock = np.random.randn() * corr_factor
        idio_shocks = np.random.randn(n_assets) * np.sqrt(1 - corr_factor**2)
        day_returns = (common_shock + idio_shocks) * volatility * vol_factor

        returns.append(day_returns)

    returns = np.array(returns)

    # המרה למחירים
    prices = 100 * np.exp(returns.cumsum(axis=0))
    prices_df = pd.DataFrame(prices, index=dates, columns=assets)

    return prices_df


def run_gdt_simulation():
    """הרצת סימולציה מלאה עם סוכן GDT."""

    print("=" * 80)
    print("דוגמה: סוכן GDT למסחר אלגוריתמי מבוסס גיאומטריה")
    print("=" * 80)

    # 1. סימולציה של מחירי שוק
    print("\n📈 שלב 1: סימולציית מחירי שוק...")
    prices = simulate_market_prices(n_assets=20, n_days=200, volatility=0.015)
    print(f"   נוצרו {len(prices)} ימי מסחר עבור {len(prices.columns)} נכסים")

    # 2. יצירת סוכן GDT
    print("\n🤖 שלב 2: יצירת סוכן GDT...")
    thresholds = GDTThresholds(
        T1=0.4,   # סף תנודתיות עקמומיות
        T2=0.25,  # סף סטייה גיאודזית
        power_law_confidence=0.7
    )
    gdt_agent = GDTAgent(
        thresholds=thresholds,
        k_neighbors=8,
        window=60
    )
    print("   ✅ סוכן GDT נוצר בהצלחה")

    # 3. הרצת הסוכן על נתוני השוק
    print("\n🚀 שלב 3: הרצת הסימולציה...")
    print("-" * 80)

    portfolio = pd.Series(1.0 / len(prices.columns), index=prices.columns)  # פורטפוליו שווה משקל
    portfolio_values = [1.0]  # ערך התיק ההתחלתי

    for day in range(60, len(prices)):
        # חלון נתונים
        window_prices = prices.iloc[:day]

        # הרצת הסוכן
        market_state, recommended_action, indicators = gdt_agent.process_market_data(window_prices)

        # חישוב תשואה יומית
        daily_returns = prices.iloc[day] / prices.iloc[day-1] - 1
        portfolio_return = (portfolio * daily_returns).sum()

        # עדכון משקולות לפי המלצת הסוכן
        portfolio = gdt_agent.generate_portfolio_weights(
            recommended_action,
            portfolio
        )

        # עדכון ערך התיק
        portfolio_value = portfolio_values[-1] * (1 + portfolio_return)
        portfolio_values.append(portfolio_value)

        # הדפסה כל 10 ימים
        if day % 10 == 0:
            print(
                f"יום {day:>3} | מצב: {market_state.name:<15} | "
                f"פעולה: {recommended_action.action_type:<15} | "
                f"חשיפה: {recommended_action.exposure:>5.1%} | "
                f"ערך תיק: ${portfolio_value:>7.2f}"
            )
            print(
                f"        | Curv.Vol={indicators['curvature_volatility']:>6.3f} | "
                f"Geo.Dev={indicators['geodesic_deviation']:>6.3f} | "
                f"Manif.V={indicators['manifold_velocity']:>6.3f} | "
                f"PowLaw={str(indicators['power_law_fit']['is_power_law']):<5}"
            )

    # 4. סיכום סטטיסטיקות
    print("\n" + "=" * 80)
    print("📊 סטטיסטיקות סיכום")
    print("=" * 80)

    stats = gdt_agent.get_state_statistics()
    print(f"\nסך תצפיות: {stats['total_observations']}")
    print("\nהתפלגות מצבים:")
    for state, count in stats['state_counts'].items():
        pct = stats['state_percentages'][state]
        print(f"  {state:<15}: {count:>3} תצפיות ({pct:>5.1f}%)")

    # חישוב ביצועים
    final_value = portfolio_values[-1]
    total_return = (final_value - 1.0) * 100
    returns_series = pd.Series(portfolio_values).pct_change().dropna()
    sharpe = returns_series.mean() / returns_series.std() * np.sqrt(252) if len(returns_series) > 1 else 0

    print(f"\nביצועי התיק:")
    print(f"  ערך סופי: ${final_value:.2f}")
    print(f"  תשואה כוללת: {total_return:>6.2f}%")
    print(f"  יחס שארפ מוערך: {sharpe:>6.2f}")

    print("\n✅ הסימולציה הסתיימה בהצלחה!")


def example_manual_usage():
    """דוגמה לשימוש ידני צעד-אחר-צעד."""

    print("\n" + "=" * 80)
    print("דוגמה: שימוש ידני בסוכן GDT")
    print("=" * 80)

    # יצירת נתוני דמה
    np.random.seed(123)
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    prices = pd.DataFrame(
        100 * np.exp(np.random.randn(100, 10).cumsum(axis=0) * 0.01),
        index=dates,
        columns=[f'Stock_{i}' for i in range(10)]
    )

    # יצירת סוכן
    agent = GDTAgent(window=60)

    # עיבוד נתונים
    print("\n📊 עיבוד נתוני שוק...")
    state, action, indicators = agent.process_market_data(prices)

    print(f"\n🔍 תוצאות:")
    print(f"  מצב שוק: {state.name}")
    print(f"  פעולה מומלצת: {action.action_type}")
    print(f"  חשיפה מומלצת: {action.exposure:.1%}")
    print(f"  תיאור: {action.description}")

    print(f"\n📈 מדדים גיאומטריים:")
    print(f"  עקמומיות ממוצעת: {indicators['mean_curvature']:.4f}")
    print(f"  תנודתיות עקמומיות: {indicators['curvature_volatility']:.4f}")
    print(f"  מהירות יריעה: {indicators['manifold_velocity']:.4f}")
    print(f"  סטייה גיאודזית: {indicators['geodesic_deviation']:.4f}")
    print(f"  התאמה לחוק חזקה: {indicators['power_law_fit']['is_power_law']}")


if __name__ == "__main__":
    # הרצת הסימולציה המלאה
    run_gdt_simulation()

    # הרצת הדוגמה הידנית
    example_manual_usage()
