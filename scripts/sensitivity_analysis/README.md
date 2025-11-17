# Hyperparameter Sensitivity Analysis
## ניתוח רגישות והופטימיזציה של פרמטרים

**תאריך:** 2025-11-17
**גרסה:** 1.0

---

## 🎯 מטרה

מסגרת מקיפה לניתוח והופטימיזציה של היפר-פרמטרים במערכת המסחר האלגוריתמית.

**מה זה עושה?**
- **זיהוי** פרמטרים בעלי השפעה גבוהה על ביצועים
- **מדידת** רגישות - כמה השינוי בפרמטר משפיע על Sharpe/DD
- **אופטימיזציה** אוטומטית של פרמטרים עם Optuna (Bayesian Optimization)
- **ויזואליזציה** של תוצאות
- **מניעת overfitting** - זיהוי פרמטרים שנותנים תוצאות לא יציבות

---

## 📚 כלים זמינים

### 1. `sensitivity_analyzer.py` - ניתוח רגישות ידני

**מה זה עושה:**
- בודק טווח ערכים לפרמטר (למשל: HALFLIFE מ-30 עד 120)
- מריץ backtest עבור כל ערך
- מודד את ההשפעה על Sharpe, DD, Return, Win Rate
- מחשב "importance score" - איזה פרמטר הכי חשוב
- יוצר גרפים של Sharpe vs. פרמטר

**מתי להשתמש:**
- רוצה להבין את ההשפעה של פרמטר אחד
- רוצה לראות את כל הטווח (לא רק אופטימום)
- רוצה 2D heatmap של 2 פרמטרים

**דוגמה:**
```python
from sensitivity_analyzer import SensitivityAnalyzer, ParameterRange

# Define base config
base_config = {
    'HALFLIFE': 60,
    'THRESHOLD': 0.5,
    'VOL_TARGET': 0.15,
}

# Initialize analyzer
analyzer = SensitivityAnalyzer(
    backtest_func=my_backtest_function,
    base_config=base_config,
    output_dir='results/sensitivity'
)

# Define parameter ranges
param_ranges = [
    ParameterRange(name='HALFLIFE', min_value=30, max_value=120, steps=10),
    ParameterRange(name='THRESHOLD', min_value=0.1, max_value=1.0, steps=10),
]

# Run analysis
results = analyzer.analyze_multiple_parameters(param_ranges)

# Calculate importance
importance = analyzer.calculate_importance()
print(importance)

# Plot results
for param_name in results.keys():
    analyzer.plot_sensitivity(param_name)

analyzer.plot_importance(importance)

# Save results
analyzer.save_results()
```

---

### 2. `optuna_optimizer.py` - אופטימיזציה אוטומטית

**מה זה עושה:**
- משתמש ב-Bayesian Optimization (TPE algorithm)
- לומד מניסויים קודמים - לא בודק ערכים אקראיים
- **חסכון זמן:** מוצא אופטימום ב-~100 trials במקום אלפים
- תומך ב-early stopping (pruning) - עוצר trials גרועים מוקדם
- מתעד הכל ב-database - ניתן לחזור ולהמשיך
- יוצר ויזואליזציות אינטראקטיביות (Plotly)

**מתי להשתמש:**
- רוצה למצוא את הפרמטרים הטובים ביותר במהירות
- יש הרבה פרמטרים (3+)
- Grid search לוקח יותר מדי זמן
- רוצה לחסוך זמן חישוב

**דוגמה:**
```python
from optuna_optimizer import OptunaOptimizer

# Initialize optimizer
optimizer = OptunaOptimizer(
    objective_func=my_backtest_function,
    study_name='OFI_optimization',
    direction='maximize'  # Maximize Sharpe
)

# Define search space
param_config = {
    'HALFLIFE': {'type': 'int', 'low': 30, 'high': 120},
    'THRESHOLD': {'type': 'float', 'low': 0.1, 'high': 1.0},
    'VOL_TARGET': {'type': 'float', 'low': 0.10, 'high': 0.20},
}

# Run optimization (100 trials)
study = optimizer.optimize(param_config, n_trials=100)

# Get best parameters
best_params = optimizer.get_best_params()
print(f"Best parameters: {best_params}")
print(f"Best Sharpe: {optimizer.get_best_value():.4f}")

# Save config
optimizer.save_best_config('best_config_OFI.json')

# Create visualizations
optimizer.visualize()

# Print summary
optimizer.print_summary()
```

---

## 🚀 Quick Start

### Installation

```bash
# Install required packages
pip install optuna>=3.4.0 plotly>=5.17.0 scikit-learn>=1.3.0

# Optional: Optuna dashboard (web UI)
pip install optuna-dashboard>=0.13.0
```

---

### Example 1: Analyze single parameter sensitivity

```bash
# Run sensitivity analysis for HALFLIFE
python scripts/sensitivity_analysis/sensitivity_analyzer.py
```

זה יריץ את הדוגמה המובנית ויצור:
- `results/sensitivity_example/sensitivity_results.json` - תוצאות גולמיות
- `results/sensitivity_example/sensitivity_HALFLIFE.png` - גרף Sharpe vs HALFLIFE
- `results/sensitivity_example/parameter_importance.png` - חשיבות פרמטרים
- `results/sensitivity_example/heatmap_2d_HALFLIFE_THRESHOLD.png` - heatmap 2D

---

### Example 2: Optimize with Optuna

```bash
# Run Optuna optimization
python scripts/sensitivity_analysis/optuna_optimizer.py
```

זה יריץ 50 trials ויצור:
- `results/optuna/example_optimization.db` - Optuna database
- `results/optuna/best_config.json` - פרמטרים מיטביים
- `results/optuna/plots/*.html` - ויזואליזציות אינטראקטיביות

**View results in browser:**
```bash
# Start Optuna dashboard
optuna-dashboard results/optuna/example_optimization.db

# Open browser: http://localhost:8080
```

---

## 📊 Output Formats

### 1. JSON Results

```json
{
  "HALFLIFE": {
    "parameter": "HALFLIFE",
    "values": [30, 40, 50, 60, 70, 80, 90, 100, 110, 120],
    "sharpe_ratios": [1.2, 1.35, 1.48, 1.52, 1.49, 1.41, 1.30, 1.15, 1.0, 0.85],
    "max_drawdowns": [0.12, 0.11, 0.10, 0.095, 0.10, 0.11, 0.13, 0.15, 0.17, 0.19],
    "metadata": {
      "timestamp": "2025-11-17T12:00:00",
      "primary_metric": "sharpe_ratio"
    }
  }
}
```

### 2. Parameter Importance

```
parameter        sharpe_variance  sharpe_range  importance_score
HALFLIFE         0.0523           0.67          0.0350
THRESHOLD        0.0312           0.45          0.0140
VOL_TARGET       0.0089           0.22          0.0020
```

**פירוש:**
- **HALFLIFE** - הפרמטר הכי חשוב (importance_score הגבוה ביותר)
- **THRESHOLD** - חשוב באופן בינוני
- **VOL_TARGET** - השפעה נמוכה

**המלצה:**
- השקע זמן בכוונון HALFLIFE
- THRESHOLD פחות קריטי
- VOL_TARGET - די לבחור ערך סביר

---

### 3. Optuna Best Config

```json
{
  "study_name": "OFI_optimization",
  "best_trial": 47,
  "best_value": 1.623,
  "best_params": {
    "HALFLIFE": 58,
    "THRESHOLD": 0.42,
    "VOL_TARGET": 0.148
  },
  "direction": "maximize",
  "n_trials": 100,
  "timestamp": "2025-11-17T14:30:00"
}
```

---

## 📈 Visualizations

### 1. Sensitivity Plots

**Sharpe vs Parameter:**
![sensitivity](https://via.placeholder.com/800x400?text=Sharpe+vs+HALFLIFE)

**מה רואים:**
- Optimal value (קו אדום מקווקו)
- Sharpe range (עד כמה רגיש הפרמטר)
- Stability (האם יש plateau?)

**Insights:**
- **Flat plateau** = יציב, לא צריך כוונון מדויק
- **Sharp peak** = רגיש מאוד, צריך כוונון קפדני
- **Multiple peaks** = overfitting, בעיה!

---

### 2. 2D Heatmap

**HALFLIFE × THRESHOLD:**
![heatmap](https://via.placeholder.com/800x600?text=2D+Heatmap)

**מה רואים:**
- אזורים ירוקים = ביצועים טובים
- אזורים אדומים = ביצועים גרועים
- אינטראקציות בין פרמטרים

---

### 3. Optuna Visualizations

**A. Optimization History**
- צפייה בשיפור לאורך trials
- האם converge?

**B. Parameter Importance**
- בר צ'ארט של חשיבות
- מבוסס על מודל של Optuna (fANOVA)

**C. Parallel Coordinate Plot**
- רואים כל trial כקו
- זיהוי דפוסים (איזה צירופים עובדים)

**D. Slice Plot**
- Sharpe vs כל פרמטר (לאחר marginalization)
- דומה ל-sensitivity plot אבל מבוסס Bayesian

**E. Contour Plot**
- 2D contours (כמו heatmap אבל smooth)
- רואים איך 2 פרמטרים אינטראקטיבים

---

## 🎓 Best Practices

### 1. Start with Sensitivity Analysis

**למה?**
- מבין אילו פרמטרים חשובים
- רואה את כל הטווח (לא רק אופטימום)
- זיהוי overfitting מוקדם

**איך?**
```python
# Step 1: Test each parameter individually
param_ranges = [
    ParameterRange('HALFLIFE', 30, 120, steps=10),
    ParameterRange('THRESHOLD', 0.1, 1.0, steps=10),
]

results = analyzer.analyze_multiple_parameters(param_ranges)

# Step 2: Check importance
importance = analyzer.calculate_importance()
print(importance)

# Step 3: Focus on important parameters only
# Don't waste time optimizing parameters with low importance!
```

---

### 2. Use Optuna for Final Optimization

**למה?**
- מהיר יותר מ-Grid Search (פי 10-100)
- מוצא אופטימום טוב יותר
- תיעוד אוטומטי

**איך?**
```python
# Use results from sensitivity analysis to define search space

# Example: If HALFLIFE important in range [50, 70]
param_config = {
    'HALFLIFE': {'type': 'int', 'low': 50, 'high': 70},  # Narrow range
    'THRESHOLD': {'type': 'float', 'low': 0.3, 'high': 0.6},
    'VOL_TARGET': {'type': 'float', 'low': 0.14, 'high': 0.16},  # Very narrow - not important
}

# Run ~100 trials
optimizer.optimize(param_config, n_trials=100)
```

---

### 3. Validate with Walk-Forward

**⚠️ חשוב מאוד:**
- פרמטרים אופטימליים על ה-train set עלולים להיות overfitted
- **חובה** לבדוק על out-of-sample data

**תהליך:**
```python
# 1. Split data: Train (2020-2023) / Test (2024)
train_data = data[data.index < '2024-01-01']
test_data = data[data.index >= '2024-01-01']

# 2. Optimize on train data
best_params = optimizer.optimize(param_config, n_trials=100)

# 3. Validate on test data
test_sharpe = backtest(test_data, best_params)

# 4. Compare
print(f"Train Sharpe: {optimizer.best_value:.4f}")
print(f"Test Sharpe: {test_sharpe:.4f}")

# If test_sharpe << train_sharpe → OVERFITTED!
if test_sharpe < 0.7 * optimizer.best_value:
    print("⚠️ WARNING: Possible overfitting!")
```

---

### 4. Multi-Objective Optimization (Advanced)

**למה?**
- לא רק Sharpe - גם DD, Drawdown Duration, Calmar, וכו'
- מציאת Pareto optimal solutions

**איך? (Optuna תומך):**
```python
def multi_objective(trial):
    config = define_search_space(trial, param_config)
    metrics = backtest(config)

    # Return multiple objectives
    return metrics['sharpe_ratio'], -metrics['max_drawdown']  # Maximize both

# Create multi-objective study
study = optuna.create_study(directions=['maximize', 'maximize'])
study.optimize(multi_objective, n_trials=100)

# Get Pareto front
pareto_front = study.best_trials
```

---

## 🔧 Integration with Main System

### Step 1: Replace example backtest function

```python
# In sensitivity_analyzer.py or optuna_optimizer.py

# Replace this:
def example_backtest_function(config):
    # Mock backtest
    ...

# With this:
from algo_trade.core.main import run_backtest

def real_backtest_function(config):
    """Run actual backtest with given config."""
    # Update config
    update_config(config)

    # Run backtest
    results = run_backtest(
        start_date='2020-01-01',
        end_date='2024-01-01',
        initial_capital=100000,
    )

    # Return metrics
    return {
        'sharpe_ratio': results['sharpe'],
        'max_drawdown': results['max_dd'],
        'total_return': results['total_return'],
        'num_trades': results['num_trades'],
        'win_rate': results['win_rate'],
    }
```

---

### Step 2: Define your parameters

```python
# Example for OFI strategy
param_config = {
    # OFI parameters
    'OFI_HALFLIFE': {'type': 'int', 'low': 30, 'high': 120},
    'OFI_THRESHOLD': {'type': 'float', 'low': 0.1, 'high': 1.0},

    # Portfolio optimization
    'VOL_TARGET': {'type': 'float', 'low': 0.10, 'high': 0.20},
    'LAMBDA': {'type': 'float', 'low': 0.5, 'high': 5.0, 'log': True},

    # Risk management
    'BOX_LIM_CALM': {'type': 'float', 'low': 0.15, 'high': 0.30},
    'BOX_LIM_NORMAL': {'type': 'float', 'low': 0.10, 'high': 0.25},
}
```

---

### Step 3: Run optimization

```bash
# Sensitivity analysis
python scripts/sensitivity_analysis/run_sensitivity.py \
    --strategy OFI \
    --start-date 2020-01-01 \
    --end-date 2024-01-01

# Optuna optimization
python scripts/sensitivity_analysis/run_optuna.py \
    --strategy OFI \
    --trials 200 \
    --n-jobs 4  # Parallel trials
```

---

## 📊 Expected Results

### Typical Parameter Importance (based on similar systems):

| Parameter | Importance | Notes |
|-----------|------------|-------|
| **Signal Halflife** | 🔴 HIGH | מאוד משפיע על Sharpe |
| **Signal Threshold** | 🟡 MEDIUM | משפיע על # trades |
| **Vol Target** | 🟢 LOW | Sharpe די יציב |
| **Rebalance Frequency** | 🟡 MEDIUM | Trade-off: Sharpe vs. costs |
| **Risk Limits (BOX_LIM)** | 🔴 HIGH | משפיע על DD |

---

## 🐛 Troubleshooting

### Problem: Optimization takes too long

**Solutions:**
1. Start with fewer trials (50 instead of 200)
2. Use parallel trials: `n_jobs=4`
3. Enable pruning (already enabled by default)
4. Narrow search space based on sensitivity analysis

---

### Problem: Best parameters are at boundary

**Example:** Best HALFLIFE = 120 (upper limit)

**Problem:** אולי האופטימום מחוץ לטווח!

**Solution:**
```python
# Expand search range
param_config = {
    'HALFLIFE': {'type': 'int', 'low': 30, 'high': 180},  # Was 120
}
```

---

### Problem: Test performance << Train performance

**This is overfitting!**

**Solutions:**
1. Regularize - add penalty for complexity
2. Use simpler model / fewer parameters
3. Use cross-validation (CSCV)
4. Don't optimize too many parameters
5. Increase training data size

---

## 📚 References

- [Optuna Documentation](https://optuna.readthedocs.io/)
- [Bayesian Optimization](https://arxiv.org/abs/1807.02811)
- [fANOVA - Parameter Importance](https://automl.github.io/fanova/cite.html)
- [Hyperparameter Tuning in Finance](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3270773)

---

## 🎯 Next Steps

1. **הרץ sensitivity analysis** על הפרמטרים שלך
2. **זהה פרמטרים חשובים** (importance score)
3. **הרץ Optuna optimization** על הפרמטרים החשובים
4. **ולידציה** על out-of-sample data
5. **Deploy** את הפרמטרים המיטביים ל-production

---

**Created by:** Claude Code (AI Assistant)
**Date:** 2025-11-17
**Version:** 1.0

---

**End of Hyperparameter Sensitivity Analysis README v1.0**
