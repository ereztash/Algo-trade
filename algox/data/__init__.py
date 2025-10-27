"""
Data Layer
==========

Data sources for AlgoX MVP:
- IBKR API (market data + execution)
- FDA calendar (biotech events)
- Market data utilities
"""

from .ibkr_client import IBKRClient, create_ibkr_client

__all__ = ["IBKRClient", "create_ibkr_client"]
