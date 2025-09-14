import numpy as np
import pandas as pd
from typing import Dict, List, Optional

class EnsembleManager:
    """
    מנהל אנסמבל של אסטרטגיות שונות.
    משלב תחזיות ממודלים שונים ומבצע שקלול מבוסס ביצועים.
    """
    def __init__(self, strategies: List[str], initial_weights: Optional[Dict[str, float]] = None):
        self.strategies = strategies
        if initial_weights and set(initial_weights.keys()) == set(strategies):
            self.weights = initial_weights
        else:
            self.weights = {s: 1.0 / len(strategies) for s in strategies}
        
        self.performance_history: Dict[str, List[float]] = {s: [] for s in strategies}

    def update_weights(self, strategy_pnl: Dict[str, float]):
        """
        מעדכן את משקלי האנסמבל על בסיס ביצועי היום.
        שקלול מבוסס על ממוצע ביצועים מתגלגל.
        """
        for s, pnl in strategy_pnl.items():
            if s in self.performance_history:
                self.performance_history[s].append(pnl)
        
        for s in self.strategies:
            if len(self.performance_history[s]) > 20: # חלון של 20 יום
                perf = np.mean(self.performance_history[s][-20:])
                self.weights[s] = max(0.01, self.weights[s] * (1 + perf * 0.1)) # קנס/פרס
        
        total_weight = sum(self.weights.values())
        if total_weight > 0:
            self.weights = {s: w / total_weight for s, w in self.weights.items()}

    def get_ensemble_signal(self, signals: Dict[str, pd.Series]) -> pd.Series:
        """
        משלב תחזיות מכל האסטרטגיות לידי סיגנל אנסמבל יחיד.
        """
        signal_names = list(self.weights.keys())
        if not signal_names:
            return pd.Series(0.0, index=signals.values().__iter__().__next__().index)

        combined_signal = pd.Series(0.0, index=signals[signal_names[0]].index)
        
        for s in signal_names:
            if s in signals:
                combined_signal += signals[s] * self.weights[s]
                
        return combined_signal

    def get_weighted_signals(self) -> Dict[str, float]:
        """מחזיר את המשקלים הנוכחיים."""
        return self.weights
