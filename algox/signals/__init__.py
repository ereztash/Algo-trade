"""
Signal Layer
============

Signal generators for AlgoX MVP:
1. Structural Arbitrage (lead-lag relationships)
2. Ricci Curvature (early warning system)
3. Event-Driven (FDA approvals)
"""

from .structural import StructuralArbitrageSignal
from .ricci_curvature import RicciCurvatureEWS
from .event_driven import EventDrivenSignal

__all__ = [
    "StructuralArbitrageSignal",
    "RicciCurvatureEWS",
    "EventDrivenSignal",
]
