"""
Strategy Layer
==============

Strategy orchestration and optimization:
- StrategyOrchestrator: Combines all signals with LinUCB
- Walk-Forward Optimization: 8-step protocol
- Regime detection
"""

from .orchestrator import StrategyOrchestrator, LinUCB
from .wfo import WalkForwardOptimizer

__all__ = ["StrategyOrchestrator", "LinUCB", "WalkForwardOptimizer"]
