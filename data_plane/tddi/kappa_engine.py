"""
Kappa Engine - מנוע חישוב κ (kappa) לזיהוי volatility/news intensity
מטרה: חישוב מדד אחיד המשלב תנודתיות ואירועי חדשות
"""

import logging
from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


class KappaEngine:
    """
    מנוע חישוב κ (kappa) - מדד משולב של volatility ו-news intensity.

    κ = α * volatility_score + β * news_score

    כאשר:
    - volatility_score: normalized rolling volatility (0-1)
    - news_score: normalized news event intensity (0-1)
    - α, β: משקלים (default: α=0.7, β=0.3)

    κ משמש להחלטה על רמת TDDI (S0/S1/S2).
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        אתחול Kappa Engine.

        Args:
            cfg: Config dictionary עם:
                - alpha: משקל volatility (default: 0.7)
                - beta: משקל news (default: 0.3)
                - lookback_periods: תקופת lookback לvolatility (default: 20)
                - volatility_threshold: threshold עבור volatility גבוה (default: 0.02)
                - news_decay_halflife: halflife לדעיכת news events (minutes, default: 30)
        """
        self.cfg = cfg
        self.alpha = cfg.get('alpha', 0.7)
        self.beta = cfg.get('beta', 0.3)
        self.lookback_periods = cfg.get('lookback_periods', 20)
        self.volatility_threshold = cfg.get('volatility_threshold', 0.02)
        self.news_decay_halflife = cfg.get('news_decay_halflife', 30)  # minutes

        # Validate weights
        if not np.isclose(self.alpha + self.beta, 1.0):
            logger.warning(
                f"alpha + beta != 1.0 (α={self.alpha}, β={self.beta}). "
                f"Normalizing..."
            )
            total = self.alpha + self.beta
            self.alpha /= total
            self.beta /= total

        # State
        self.last_kappa: Optional[float] = None
        self.kappa_history: list = []
        self.max_history_size = 1000

        logger.info(
            f"KappaEngine initialized: α={self.alpha}, β={self.beta}, "
            f"lookback={self.lookback_periods}, vol_threshold={self.volatility_threshold}"
        )

    def compute(
        self,
        panel_returns: pd.DataFrame,
        news_counters: Dict[str, int]
    ) -> float:
        """
        חישוב κ (kappa) מתוך panel של returns ו-news counters.

        Args:
            panel_returns: DataFrame עם returns (index=time, columns=symbols)
            news_counters: Dict מספר news events per symbol ב-window אחרון
                          Example: {'AAPL': 5, 'MSFT': 2}

        Returns:
            float: κ (0-1)
        """
        try:
            # חשב volatility score
            vol_score = self._compute_volatility_score(panel_returns)

            # חשב news score
            news_score = self._compute_news_score(news_counters, panel_returns.columns)

            # חשב κ משוקלל
            kappa = self.alpha * vol_score + self.beta * news_score

            # Clamp to [0, 1]
            kappa = np.clip(kappa, 0.0, 1.0)

            # שמור בהיסטוריה
            self.last_kappa = kappa
            self.kappa_history.append({
                'timestamp': datetime.utcnow(),
                'kappa': kappa,
                'vol_score': vol_score,
                'news_score': news_score
            })

            # Trim history
            if len(self.kappa_history) > self.max_history_size:
                self.kappa_history = self.kappa_history[-self.max_history_size:]

            logger.debug(
                f"κ computed: {kappa:.3f} "
                f"(vol={vol_score:.3f}, news={news_score:.3f})"
            )

            return kappa

        except Exception as e:
            logger.error(f"Error computing kappa: {e}")
            # Return last known kappa or default
            return self.last_kappa if self.last_kappa is not None else 0.5

    def _compute_volatility_score(self, panel_returns: pd.DataFrame) -> float:
        """
        חישוב volatility score מנורמל (0-1).

        Args:
            panel_returns: DataFrame של returns

        Returns:
            float: volatility score (0-1)
        """
        if panel_returns is None or panel_returns.empty:
            logger.debug("Empty panel_returns, returning default vol_score=0.5")
            return 0.5

        try:
            # חשב rolling std per symbol
            rolling_stds = panel_returns.rolling(
                window=self.lookback_periods,
                min_periods=max(1, self.lookback_periods // 2)
            ).std()

            # קח את הממוצע על פני כל הסימבולים
            current_vol = rolling_stds.iloc[-1].mean()

            if pd.isna(current_vol):
                logger.debug("Current volatility is NaN, returning default=0.5")
                return 0.5

            # Normalize ביחס ל-threshold
            # vol_score = min(current_vol / threshold, 1.0)
            vol_score = min(current_vol / self.volatility_threshold, 1.0)

            return float(vol_score)

        except Exception as e:
            logger.error(f"Error computing volatility score: {e}")
            return 0.5

    def _compute_news_score(
        self,
        news_counters: Dict[str, int],
        symbols: pd.Index
    ) -> float:
        """
        חישוב news score מנורמל (0-1).

        Args:
            news_counters: Dict של news counts per symbol
            symbols: רשימת symbols בפאנל

        Returns:
            float: news score (0-1)
        """
        if not news_counters:
            return 0.0

        try:
            # חשב total news events
            total_news = sum(news_counters.values())

            # Normalize לפי מספר symbols
            num_symbols = len(symbols)
            if num_symbols == 0:
                return 0.0

            # News events per symbol (ממוצע)
            news_per_symbol = total_news / num_symbols

            # Normalize: נניח שמעל 10 news/symbol/window = 1.0
            max_news_threshold = 10
            news_score = min(news_per_symbol / max_news_threshold, 1.0)

            return float(news_score)

        except Exception as e:
            logger.error(f"Error computing news score: {e}")
            return 0.0

    def get_current_kappa(self) -> Optional[float]:
        """
        קבלת κ הנוכחי.

        Returns:
            float: κ (או None אם עדיין לא חושב)
        """
        return self.last_kappa

    def get_stats(self) -> Dict[str, Any]:
        """
        קבלת סטטיסטיקות.

        Returns:
            Dict עם סטטיסטיקות:
            - current_kappa
            - mean_kappa
            - std_kappa
            - min_kappa
            - max_kappa
        """
        if not self.kappa_history:
            return {
                'current_kappa': None,
                'mean_kappa': None,
                'std_kappa': None,
                'min_kappa': None,
                'max_kappa': None,
                'history_count': 0
            }

        kappas = [h['kappa'] for h in self.kappa_history]

        return {
            'current_kappa': round(self.last_kappa, 3) if self.last_kappa else None,
            'mean_kappa': round(np.mean(kappas), 3),
            'std_kappa': round(np.std(kappas), 3),
            'min_kappa': round(np.min(kappas), 3),
            'max_kappa': round(np.max(kappas), 3),
            'history_count': len(self.kappa_history),
            'alpha': self.alpha,
            'beta': self.beta
        }

    def reset(self):
        """
        איפוס engine.
        """
        self.last_kappa = None
        self.kappa_history.clear()
        logger.info("KappaEngine reset")
