# -*- coding: utf-8 -*-
"""
geometric_indicators.py
מודול לחישוב מדדים גיאומטריים עבור סוכן GDT (Geometric Dynamic Trading)

מדדים נתמכים:
- mean_curvature: עקמומיות ממוצעת של יריעת השוק
- curvature_volatility: תנודתיות העקמומיות
- manifold_velocity: מהירות היריעה (v_g)
- geodesic_deviation: סטייה מהמסלול הגיאודזי
- power_law_fit: התאמה לחוק חזקה (β ≈ 1/2 מצביע על ביפורקציה)
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional
from scipy.spatial.distance import pdist, squareform
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path
from scipy.stats import linregress
from sklearn.neighbors import NearestNeighbors


class GeometricIndicators:
    """
    מחלקה לחישוב מדדים גיאומטריים של שוק המניות.

    המדדים מבוססים על ייצוג השוק כיריעה רימנית בעלת גיאומטריה דינמית.
    """

    def __init__(self, k_neighbors: int = 10, window: int = 60):
        """
        אתחול המחשבון הגיאומטרי.

        Args:
            k_neighbors: מספר שכנים קרובים לבניית גרף k-NN
            window: חלון זמן בימים לחישוב קורלציות
        """
        self.k_neighbors = k_neighbors
        self.window = window
        self.history = {
            'mean_curvature': [],
            'curvature_volatility': [],
            'manifold_velocity': [],
            'geodesic_deviation': []
        }

    def calculate_log_returns(self, prices: pd.DataFrame, window: Optional[int] = None) -> pd.DataFrame:
        """
        חישוב תשואות לוגריתמיות.

        Args:
            prices: מחירי נכסים
            window: חלון זמן (אם None, משתמש בערך ברירת המחדל)

        Returns:
            תשואות לוגריתמיות
        """
        if window is None:
            window = self.window

        log_returns = np.log(prices / prices.shift(1)).dropna()
        return log_returns.tail(window)

    def calculate_correlation_matrix(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        חישוב מטריצת קורלציה.

        Args:
            returns: תשואות נכסים

        Returns:
            מטריצת קורלציה
        """
        return returns.corr()

    def correlation_to_distance(self, corr_matrix: pd.DataFrame) -> pd.DataFrame:
        """
        המרת מטריצת קורלציה למטריצת מרחק.

        משתמש בנוסחה: d(i,j) = sqrt(2(1 - ρ_ij))

        Args:
            corr_matrix: מטריצת קורלציה

        Returns:
            מטריצת מרחק
        """
        # חיתוך ערכי קורלציה למניעת בעיות מספריות
        corr_clipped = corr_matrix.clip(-0.9999, 0.9999)
        distance_matrix = np.sqrt(2 * (1 - corr_clipped))
        return pd.DataFrame(distance_matrix,
                           index=corr_matrix.index,
                           columns=corr_matrix.columns)

    def build_knn_graph(self, distance_matrix: pd.DataFrame) -> np.ndarray:
        """
        בניית גרף k-NN מתוך מטריצת מרחק.

        Args:
            distance_matrix: מטריצת מרחקים

        Returns:
            מטריצת שכנויות (adjacency matrix)
        """
        n = distance_matrix.shape[0]

        # אתחול מטריצת שכנויות
        adjacency = np.zeros((n, n))

        # עבור כל צומת, מצא k שכנים הקרובים ביותר
        for i in range(n):
            distances = distance_matrix.iloc[i].values
            # מיון המרחקים ובחירת k+1 הקרובים (כולל הצומת עצמו)
            nearest_indices = np.argsort(distances)[:self.k_neighbors + 1]

            for j in nearest_indices:
                if i != j:
                    adjacency[i, j] = distances[j]

        # הפיכת הגרף לסימטרי
        adjacency = np.minimum(adjacency, adjacency.T)

        return adjacency

    def compute_discrete_curvature_forman(self, adjacency: np.ndarray) -> Tuple[float, np.ndarray]:
        """
        חישוב עקמומיות דיסקרטית לפי Forman's Ricci Curvature.

        זוהי גישה קומבינטורית לחישוב עקמומיות על גרפים.

        Args:
            adjacency: מטריצת שכנויות

        Returns:
            tuple של (עקמומיות ממוצעת, וקטור עקמומיות לכל קשת)
        """
        n = adjacency.shape[0]

        # חישוב דרגות הצמתים
        degrees = np.sum(adjacency > 0, axis=1)

        # חישוב עקמומיות לכל קשת (i,j)
        curvatures = []

        for i in range(n):
            for j in range(i + 1, n):
                if adjacency[i, j] > 0:
                    # Forman's curvature:
                    # R(e_ij) = w_ij * (deg(i) + deg(j) - 2 - |T_ij|)
                    # כאשר T_ij הוא מספר המשולשים שעוברים דרך הקשת

                    # מציאת שכנים משותפים (משולשים)
                    neighbors_i = set(np.where(adjacency[i] > 0)[0])
                    neighbors_j = set(np.where(adjacency[j] > 0)[0])
                    common_neighbors = len(neighbors_i.intersection(neighbors_j))

                    # חישוב עקמומיות
                    curvature = adjacency[i, j] * (
                        degrees[i] + degrees[j] - 2 - common_neighbors
                    )
                    curvatures.append(curvature)

        if len(curvatures) == 0:
            return 0.0, np.array([])

        curvatures_array = np.array(curvatures)
        mean_curvature = float(np.mean(curvatures_array))

        return mean_curvature, curvatures_array

    def compute_curvature_volatility(self, curvatures: np.ndarray) -> float:
        """
        חישוב תנודתיות העקמומיות.

        Args:
            curvatures: וקטור של ערכי עקמומיות

        Returns:
            סטיית תקן של העקמומיות
        """
        if len(curvatures) == 0:
            return 0.0
        return float(np.std(curvatures))

    def compute_manifold_velocity(self,
                                  adjacency_prev: Optional[np.ndarray],
                                  adjacency_curr: np.ndarray) -> float:
        """
        חישוב מהירות היריעה v_g - שיעור השינוי בגיאומטריה.

        Args:
            adjacency_prev: מטריצת שכנויות קודמת (אם None, מחזיר 0)
            adjacency_curr: מטריצת שכנויות נוכחית

        Returns:
            מהירות היריעה (נורמה של ההפרש)
        """
        if adjacency_prev is None or adjacency_prev.shape != adjacency_curr.shape:
            return 0.0

        # חישוב נורמת Frobenius של ההפרש
        diff = adjacency_curr - adjacency_prev
        velocity = float(np.linalg.norm(diff, ord='fro'))

        return velocity

    def compute_geodesic_deviation(self,
                                   adjacency: np.ndarray,
                                   trajectory_length: int = 5) -> float:
        """
        חישוב סטייה גיאודזית - מידת הסטייה מהמסלול הקצר ביותר.

        משווה מסלולים בפועל למסלולים גיאודזיים אופטימליים.

        Args:
            adjacency: מטריצת שכנויות
            trajectory_length: אורך מסלול לבדיקה

        Returns:
            סטייה גיאודזית ממוצעת
        """
        n = adjacency.shape[0]

        if n < 2:
            return 0.0

        # המרה למטריצה דלילה לחישוב יעיל
        graph = csr_matrix(adjacency)

        # חישוב מרחקים גיאודזיים (shortest paths)
        try:
            dist_matrix = shortest_path(csgraph=graph,
                                       directed=False,
                                       return_predecessors=False)
        except Exception:
            return 0.0

        # דגימת זוגות צמתים אקראיים
        num_samples = min(100, n * (n - 1) // 2)
        deviations = []

        for _ in range(num_samples):
            i, j = np.random.choice(n, size=2, replace=False)

            if not np.isinf(dist_matrix[i, j]):
                # המרחק הגיאודזי
                geodesic_dist = dist_matrix[i, j]

                # המרחק האוקלידי (ככה לינארי)
                euclidean_dist = adjacency[i, j] if adjacency[i, j] > 0 else geodesic_dist

                # סטייה יחסית
                if geodesic_dist > 0:
                    deviation = abs(euclidean_dist - geodesic_dist) / geodesic_dist
                    deviations.append(deviation)

        if len(deviations) == 0:
            return 0.0

        return float(np.mean(deviations))

    def check_power_law_divergence(self,
                                   velocity_history: List[float],
                                   beta_target: float = 0.5,
                                   min_points: int = 10) -> Dict:
        """
        בדיקת התאמה לחוק חזקה: v_g(t) ~ (t_c - t)^(-β)

        כאשר β ≈ 1/2, מצביע על התקרבות לנקודת ביפורקציה/משבר.

        Args:
            velocity_history: היסטוריית מהירות היריעה
            beta_target: ערך β מטרה (0.5 למשבר)
            min_points: מספר נקודות מינימלי לרגרסיה

        Returns:
            מילון עם התוצאות: {'is_power_law', 'beta', 'r_squared', 'confidence'}
        """
        if len(velocity_history) < min_points:
            return {
                'is_power_law': False,
                'beta': None,
                'r_squared': None,
                'confidence': 0.0
            }

        # המרה לערכים לוגריתמיים לבדיקת חוק חזקה
        velocities = np.array(velocity_history[-min_points:])

        # סינון ערכים אפסיים או שליליים
        valid_mask = velocities > 1e-9
        if valid_mask.sum() < min_points // 2:
            return {
                'is_power_law': False,
                'beta': None,
                'r_squared': None,
                'confidence': 0.0
            }

        velocities = velocities[valid_mask]
        time_points = np.arange(len(velocities))

        # רגרסיה לוגריתמית: log(v) = α + β*log(t)
        try:
            log_v = np.log(velocities)
            log_t = np.log(time_points + 1)  # +1 למניעת log(0)

            slope, intercept, r_value, p_value, std_err = linregress(log_t, log_v)

            # בדיקה האם β קרוב ל-1/2
            beta_diff = abs(slope - beta_target)
            r_squared = r_value ** 2

            # קריטריון לזיהוי חוק חזקה
            is_power_law = (r_squared > 0.7) and (beta_diff < 0.2)

            # רמת ביטחון (0-1)
            confidence = r_squared * (1 - beta_diff / 0.5)

            return {
                'is_power_law': is_power_law,
                'beta': float(slope),
                'r_squared': float(r_squared),
                'confidence': float(np.clip(confidence, 0, 1))
            }

        except Exception:
            return {
                'is_power_law': False,
                'beta': None,
                'r_squared': None,
                'confidence': 0.0
            }

    def compute_all_indicators(self,
                              prices: pd.DataFrame,
                              adjacency_prev: Optional[np.ndarray] = None) -> Dict:
        """
        חישוב כל המדדים הגיאומטריים בבת אחת.

        זהו צינור עיבוד מלא מקצה לקצה:
        1. תשואות לוגריתמיות
        2. מטריצת קורלציה
        3. מטריצת מרחק
        4. גרף k-NN
        5. מדדים גיאומטריים

        Args:
            prices: מחירי נכסים
            adjacency_prev: מטריצת שכנויות קודמת (אופציונלי)

        Returns:
            מילון עם כל המדדים
        """
        # שלב 1: תשואות
        returns = self.calculate_log_returns(prices)

        # שלב 2: קורלציה
        corr_matrix = self.calculate_correlation_matrix(returns)

        # שלב 3: מרחק
        dist_matrix = self.correlation_to_distance(corr_matrix)

        # שלב 4: גרף k-NN
        adjacency = self.build_knn_graph(dist_matrix)

        # שלב 5: מדדים גיאומטריים
        mean_curvature, curvatures = self.compute_discrete_curvature_forman(adjacency)
        curvature_volatility = self.compute_curvature_volatility(curvatures)
        manifold_velocity = self.compute_manifold_velocity(adjacency_prev, adjacency)
        geodesic_deviation = self.compute_geodesic_deviation(adjacency)

        # עדכון היסטוריה
        self.history['mean_curvature'].append(mean_curvature)
        self.history['curvature_volatility'].append(curvature_volatility)
        self.history['manifold_velocity'].append(manifold_velocity)
        self.history['geodesic_deviation'].append(geodesic_deviation)

        # בדיקת חוק חזקה
        power_law_result = self.check_power_law_divergence(
            self.history['manifold_velocity']
        )

        return {
            'mean_curvature': mean_curvature,
            'curvature_volatility': curvature_volatility,
            'manifold_velocity': manifold_velocity,
            'geodesic_deviation': geodesic_deviation,
            'power_law_fit': power_law_result,
            'adjacency_matrix': adjacency
        }

    def reset_history(self):
        """איפוס ההיסטוריה."""
        for key in self.history:
            self.history[key] = []
