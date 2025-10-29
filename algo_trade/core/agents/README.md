# סוכן GDT (Geometric Dynamic Trading)

סוכן מסחר אלגוריתמי מבוסס גיאומטריה שמשתמש במדדים גיאומטריים של שוק המניות כדי לזהות מצבי שוק ולקבל החלטות מסחר.

## תיאור

הסוכן מייצג את שוק המניות כיריעה רימנית (Riemannian manifold) בעלת גיאומטריה דינמית. באמצעות מדדים גיאומטריים כמו עקמומיות, מהירות יריעה וסטייה גיאודזית, הסוכן יכול לזהות מצבי שוק שונים ולהתאים את האסטרטגיה בהתאם.

## מצבי שוק

הסוכן מזהה 3 מצבי שוק עיקריים:

### 1. STABLE (יציב/גיאודזי)
- **תיאור**: השוק עוקב אחר מסלול יציב ואינרציאלי
- **מאפיינים**:
  - עקמומיות נמוכה
  - תנודתיות עקמומיות נמוכה
  - סטייה גיאודזית נמוכה
- **פעולת מסחר**: שמירה על חשיפה מלאה (100% long)

### 2. STRESSED (לחוץ/קדם-מעבר)
- **תיאור**: הגיאומטריה של השוק הופכת לבלתי יציבה
- **מאפיינים**:
  - עלייה משמעותית בתנודתיות העקמומיות
  - עלייה בסטייה הגיאודזית
- **פעולת מסחר**: הקטנת חשיפה ל-50%

### 3. BIFURCATION (ביפורקציה קרובה/משבר)
- **תיאור**: השוק מתקרב לנקודת קריסה
- **מאפיינים**:
  - מהירות היריעה מתאימה לחוק חזקה עם β ≈ 1/2
  - סימן להתבדרות קרובה
- **פעולת מסחר**: סגירת long, פתיחת short (50%)

## מדדים גיאומטריים

### 1. Mean Curvature (עקמומיות ממוצעת)
מדד לעקמומיות הממוצעת של יריעת השוק. מחושב באמצעות Forman's Ricci Curvature על גרף k-NN של השוק.

### 2. Curvature Volatility (תנודתיות עקמומיות)
סטיית התקן של העקמומיות. מדד לאי-יציבות הגיאומטרית של השוק.

### 3. Manifold Velocity (מהירות יריעה)
שיעור השינוי בגיאומטריה של השוק. מחושב כנורמת Frobenius של ההפרש בין מטריצות שכנויות עוקבות.

### 4. Geodesic Deviation (סטייה גיאודזית)
מידת הסטייה של מסלולים בפועל מהמסלולים הגיאודזיים האופטימליים.

### 5. Power Law Fit (התאמה לחוק חזקה)
בדיקה האם מהירות היריעה מתאימה לחוק חזקה: v_g(t) ~ (t_c - t)^(-β)
כאשר β ≈ 1/2 מצביע על התקרבות לביפורקציה.

## שימוש

### דוגמה בסיסית

```python
from algo_trade.core.agents import GDTAgent, GDTThresholds
import pandas as pd

# טעינת נתוני מחירים
prices = pd.read_csv('market_prices.csv')

# יצירת סוכן
agent = GDTAgent(
    thresholds=GDTThresholds(T1=0.4, T2=0.25),
    k_neighbors=10,
    window=60
)

# עיבוד נתונים וקבלת המלצה
market_state, action, indicators = agent.process_market_data(prices)

print(f"מצב שוק: {market_state.name}")
print(f"פעולה מומלצת: {action.action_type}")
print(f"חשיפה: {action.exposure:.1%}")
```

### שילוב במערכת מסחר קיימת

```python
from algo_trade.core.agents import GDTAgent

# יצירת סוכן
gdt_agent = GDTAgent(k_neighbors=10, window=60)

# בלולאת המסחר היומית
for day in trading_days:
    # עיבוד נתוני שוק
    state, action, indicators = gdt_agent.process_market_data(prices[:day])

    # התאמת משקולות הפורטפוליו
    new_weights = gdt_agent.generate_portfolio_weights(
        action,
        current_weights
    )

    # ביצוע המסחר
    execute_trades(new_weights)
```

## פרמטרים

### GDTThresholds
- `T1` (float): סף תנודתיות עקמומיות (ברירת מחדל: 0.5)
- `T2` (float): סף סטייה גיאודזית (ברירת מחדל: 0.3)
- `T3` (float): סף מהירות יריעה (ברירת מחדל: 1.0)
- `power_law_confidence` (float): סף ביטחון להתאמת חוק חזקה (ברירת מחדל: 0.7)

### GDTAgent
- `thresholds` (GDTThresholds): ספי ההחלטה
- `k_neighbors` (int): מספר שכנים קרובים לגרף k-NN (ברירת מחדל: 10)
- `window` (int): חלון זמן בימים לחישוב מדדים (ברירת מחדל: 60)

## ביצועים

הסוכן מותאם לעבודה עם:
- מאות נכסים בו-זמנית
- חישובים בזמן אמת (< 1 שנייה לעדכון)
- היסטוריה של מאות ימי מסחר

לביצועים אופטימליים, מומלץ:
- שימוש במטמון לחישובים כבדים
- הרצה במקביל על ליבות מרובות
- שימוש בספריות מספריות מהירות (NumPy, SciPy)

## התאמה אישית

### הגדרת ספים מותאמים אישית

```python
from algo_trade.core.agents import GDTThresholds

# ספים אגרסיביים (רגישים יותר)
aggressive = GDTThresholds(
    T1=0.3,
    T2=0.2,
    power_law_confidence=0.6
)

# ספים שמרניים (רגישים פחות)
conservative = GDTThresholds(
    T1=0.6,
    T2=0.4,
    power_law_confidence=0.8
)
```

### שינוי כללי המסחר

ניתן להרחיב את מטריצת הכללים על ידי ירושה:

```python
from algo_trade.core.agents import GDTAgent, MarketState, TradingAction

class CustomGDTAgent(GDTAgent):
    def _build_rule_matrix(self):
        # הגדרת כללים מותאמים אישית
        return {
            MarketState.STABLE: TradingAction(
                action_type='hold',
                exposure=1.2,  # מינוף של 1.2x
                position='long',
                description='אגרסיבי יותר במצב יציב'
            ),
            # ... שאר הכללים
        }
```

## דוגמאות

ראה `examples/gdt_agent_example.py` לדוגמאות שלמות של שימוש בסוכן.

## התייחסות תיאורטית

הסוכן מבוסס על:
1. תורת הגיאומטריה הדיפרנציאלית של יריעות רימניות
2. Forman's Ricci Curvature לגרפים דיסקרטיים
3. תיאוריה של ביפורקציות ונקודות קריטיות במערכות דינמיות
4. ניתוח חוק חזקה (Power Law) להתרעה מוקדמת על משברים

## רישיון

חלק מפרויקט Algo-trade.
