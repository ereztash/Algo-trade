"""
Completeness Gate - שער שלמות נתונים
מטרה: וידוא שכל הנתונים הנדרשים מתקבלים ללא gaps או missing values
"""

import logging
from typing import List, Dict, Any, Set, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class CompletenessGate:
    """
    בודק שלמות נתונים:
    1. Missing symbols - סימבולים שלא התקבלו
    2. Missing values - ערכים חסרים (NaN/None)
    3. Gaps in coverage - פערים בכיסוי
    """

    def __init__(self, threshold: float = 0.95):
        """
        אתחול Completeness Gate.

        Args:
            threshold: אחוז מינימלי של completeness (0.95 = 95%)
        """
        self.threshold = threshold
        self.total_checks = 0
        self.passed_checks = 0
        self.failed_checks = 0

        logger.info(f"CompletenessGate initialized with threshold: {threshold*100}%")

    def enforce(self, panel_df: pd.DataFrame) -> Dict[str, Any]:
        """
        בדיקת שלמות של DataFrame (panel) עם נתוני שוק.

        Args:
            panel_df: DataFrame עם index=timestamp, columns=symbols, values=prices

        Returns:
            Dict עם תוצאות הבדיקה:
            - is_complete: האם עובר את threshold
            - completeness_rate: אחוז שלמות בפועל
            - missing_count: מספר ערכים חסרים
            - total_count: סך הכל ערכים
            - symbols_with_issues: סימבולים עם בעיות
        """
        self.total_checks += 1

        if panel_df is None or panel_df.empty:
            logger.warning("Empty panel_df received")
            self.failed_checks += 1
            return {
                'is_complete': False,
                'completeness_rate': 0.0,
                'missing_count': 0,
                'total_count': 0,
                'symbols_with_issues': [],
                'passed': False
            }

        # ספור ערכים חסרים
        total_values = panel_df.size
        missing_values = panel_df.isna().sum().sum()
        present_values = total_values - missing_values

        # חשב completeness rate
        completeness_rate = present_values / total_values if total_values > 0 else 0.0

        # זהה סימבולים עם בעיות (>10% missing)
        symbols_with_issues = []
        for col in panel_df.columns:
            col_missing = panel_df[col].isna().sum()
            col_total = len(panel_df[col])
            col_rate = 1 - (col_missing / col_total) if col_total > 0 else 0

            if col_rate < 0.9:  # פחות מ-90% complete
                symbols_with_issues.append({
                    'symbol': col,
                    'missing': int(col_missing),
                    'total': int(col_total),
                    'completeness': round(col_rate, 4)
                })

        # בדוק אם עובר threshold
        passed = completeness_rate >= self.threshold

        if passed:
            self.passed_checks += 1
            logger.debug(
                f"Completeness check PASSED: {completeness_rate*100:.2f}% "
                f"(threshold: {self.threshold*100}%)"
            )
        else:
            self.failed_checks += 1
            logger.error(
                f"Completeness check FAILED: {completeness_rate*100:.2f}% "
                f"(threshold: {self.threshold*100}%). "
                f"Missing: {missing_values}/{total_values}"
            )

        result = {
            'is_complete': passed,
            'completeness_rate': round(completeness_rate, 4),
            'missing_count': int(missing_values),
            'total_count': int(total_values),
            'symbols_with_issues': symbols_with_issues,
            'passed': passed,
            'threshold': self.threshold
        }

        return result

    def check_symbol_coverage(self, panel_df: pd.DataFrame,
                             expected_symbols: List[str]) -> Dict[str, Any]:
        """
        בדיקה שכל הסימבולים הצפויים נמצאים ב-DataFrame.

        Args:
            panel_df: DataFrame עם columns=symbols
            expected_symbols: רשימת סימבולים צפויה

        Returns:
            Dict עם coverage info
        """
        if panel_df is None or panel_df.empty:
            return {
                'coverage_rate': 0.0,
                'missing_symbols': expected_symbols,
                'extra_symbols': [],
                'passed': False
            }

        actual_symbols = set(panel_df.columns)
        expected_set = set(expected_symbols)

        missing_symbols = list(expected_set - actual_symbols)
        extra_symbols = list(actual_symbols - expected_set)

        coverage_rate = len(actual_symbols & expected_set) / len(expected_set) if expected_set else 1.0

        passed = coverage_rate >= self.threshold

        if missing_symbols:
            logger.warning(f"Missing symbols: {missing_symbols}")

        if extra_symbols:
            logger.info(f"Extra symbols (not expected): {extra_symbols}")

        return {
            'coverage_rate': round(coverage_rate, 4),
            'missing_symbols': missing_symbols,
            'extra_symbols': extra_symbols,
            'passed': passed,
            'actual_symbols': list(actual_symbols),
            'expected_symbols': expected_symbols
        }

    def check_time_coverage(self, panel_df: pd.DataFrame,
                           expected_interval_minutes: float = 1.0) -> Dict[str, Any]:
        """
        בדיקת gaps בזמן (time series gaps).

        Args:
            panel_df: DataFrame עם DateTimeIndex
            expected_interval_minutes: interval צפוי בדקות

        Returns:
            Dict עם gap info
        """
        if panel_df is None or panel_df.empty or len(panel_df) < 2:
            return {
                'gaps_found': 0,
                'max_gap_minutes': 0,
                'has_gaps': False
            }

        # בדוק שה-index הוא datetime
        if not isinstance(panel_df.index, pd.DatetimeIndex):
            logger.warning("Index is not DateTimeIndex, cannot check time coverage")
            return {'error': 'Invalid index type'}

        # חשב הפרשי זמן
        time_diffs = panel_df.index.to_series().diff()[1:]  # התעלם מהראשון (NaT)
        time_diffs_minutes = time_diffs.dt.total_seconds() / 60

        # זהה gaps (>1.5x expected interval)
        threshold = expected_interval_minutes * 1.5
        gaps = time_diffs_minutes[time_diffs_minutes > threshold]

        gaps_found = len(gaps)
        max_gap_minutes = float(time_diffs_minutes.max()) if not time_diffs_minutes.empty else 0

        has_gaps = gaps_found > 0

        if has_gaps:
            logger.warning(
                f"Time coverage gaps found: {gaps_found} gaps, "
                f"max gap: {max_gap_minutes:.1f} minutes"
            )

        return {
            'gaps_found': int(gaps_found),
            'max_gap_minutes': round(max_gap_minutes, 2),
            'has_gaps': has_gaps,
            'expected_interval_minutes': expected_interval_minutes,
            'mean_interval_minutes': round(float(time_diffs_minutes.mean()), 2) if not time_diffs_minutes.empty else 0
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        קבלת סטטיסטיקות כוללות.
        """
        pass_rate = (self.passed_checks / self.total_checks * 100) if self.total_checks > 0 else 0

        return {
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'failed_checks': self.failed_checks,
            'pass_rate': round(pass_rate, 2),
            'threshold': self.threshold
        }

    def reset(self):
        """
        איפוס counters.
        """
        self.total_checks = 0
        self.passed_checks = 0
        self.failed_checks = 0
        logger.info("CompletenessGate reset")
