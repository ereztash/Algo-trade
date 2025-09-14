import numpy as np
import pandas as pd
from typing import List, Dict, Tuple

class LinUCB:
    """
    אלגוריתם LinUCB לטובת בחירת Gate קונטקסטואלית.
    מתבסס על רגרסיית רידג' כדי לבחור את הזרוע הטובה ביותר.
    """
    def __init__(self, n_arms: int, n_features: int, alpha: float, ridge_lambda: float = 1.0):
        """
        אתחול המודל.
        n_arms: מספר האסטרטגיות (זרועות) לבחירה.
        n_features: מספר הפיצ'רים (קונטקסט) לכל זרוע.
        alpha: פרמטר שליטה בחיפוש (exploration).
        ridge_lambda: פרמטר רגרסיית רידג' ליציבות.
        """
        self.n_arms = n_arms
        self.n_features = n_features
        self.alpha = alpha
        self.ridge_lambda = ridge_lambda
        
        # A מטריצת קו-וריאנס + רגרסיית רידג'
        self.A = [self.ridge_lambda * np.eye(n_features) for _ in range(n_arms)]
        # b וקטור תגובות (rewards)
        self.b = [np.zeros(n_features) for _ in range(n_arms)]

    def select_arm(self, context: np.ndarray) -> int:
        """
        בוחרת את הזרוע הטובה ביותר בהתאם לווקטור הקונטקסט.
        context: וקטור פיצ'רים של הקונטקסט הנוכחי.
        מחזירה: אינדקס הזרוע שנבחרה.
        """
        if context.shape[0] != self.n_features:
            raise ValueError("Context vector size mismatch")

        upper_bounds = np.zeros(self.n_arms)
        for arm in range(self.n_arms):
            try:
                A = self.A[arm]
                b = self.b[arm]
                
                # חישוב יציב של theta
                theta = np.linalg.solve(A, b)
                
                # חישוב UCB (Upper Confidence Bound)
                p_hat = theta.T @ context
                ucb = self.alpha * np.sqrt(context.T @ np.linalg.inv(A) @ context)
                
                upper_bounds[arm] = p_hat + ucb
            except np.linalg.LinAlgError:
                # במקרה של כשל חישובי, בוחר באקראי או נותן ניקוד נמוך
                upper_bounds[arm] = -np.inf
        
        if np.isinf(upper_bounds).all():
            return np.random.choice(self.n_arms)
        
        return int(np.argmax(upper_bounds))

    def update(self, arm: int, context: np.ndarray, reward: float):
        """
        מעדכנת את המודל לאחר קבלת תגמול.
        arm: אינדקס הזרוע שנבחרה.
        context: וקטור פיצ'רים של הקונטקסט.
        reward: התגמול שהתקבל לאחר בחירת הזרוע.
        """
        if context.shape[0] != self.n_features:
            raise ValueError("Context vector size mismatch")
            
        self.A[arm] += np.outer(context, context)
        self.b[arm] += context * reward
