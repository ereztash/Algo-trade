"""
AlgoX Hybrid MVP
================

A hybrid algorithmic trading system combining the working infrastructure
of Algo-trade with advanced strategies from AlgoX specification.

Strategies:
-----------
1. Structural Arbitrage: Lead-lag relationships (REMX → URNM → QTUM)
2. Event-Driven: FDA approval calendar (biotech)
3. Ricci Curvature: Early warning system for systemic fragility

Architecture:
------------
- Data Layer: IBKR API + FDA scraper
- Signal Layer: 3 core strategies
- Strategy Layer: WFO + LinUCB + Regime detection
- Portfolio Layer: QP optimization + Risk management
- Execution Layer: IBKR order execution
- Monitoring Layer: Performance tracking + Kill-switches

Author: Claude + Erez
Date: 2025-10-27
Version: 0.1.0 (MVP)
"""

__version__ = "0.1.0"
__author__ = "Claude + Erez"

# Package metadata
__all__ = [
    "data",
    "signals",
    "strategy",
    "portfolio",
    "execution",
    "monitoring",
    "utils",
]
