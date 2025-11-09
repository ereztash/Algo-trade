"""
Allocation models for the 3-plane trading system.

Defines:
- Allocation: Individual symbol allocation (weight + metadata)
- PortfolioTarget: Collection of allocations with constraints

Allocations represent the output of the portfolio construction process
(e.g., quadratic programming solver) and input to order generation.

Key constraints:
- Sum of weights ≤ 1.0 (no over-leverage without explicit margin)
- Individual weights in [-1, 1] (short to long)
"""

from datetime import datetime
from typing import Annotated, List, Optional
from pydantic import Field, field_validator, model_validator

from shared.models.base import BaseModel, TimestampMixin, SymbolMixin


class Allocation(BaseModel, SymbolMixin):
    """
    Individual symbol allocation within a portfolio.

    Represents target weight for a single symbol.
    Weights are normalized portfolio fractions:
    - 1.0 = 100% of portfolio in this symbol (long)
    - -1.0 = 100% of portfolio short this symbol
    - 0.0 = no position

    Validation:
    - weight in [-1, 1]
    """

    weight: Annotated[
        float,
        Field(
            ge=-1.0,
            le=1.0,
            description="Target portfolio weight. -1=max short, 0=flat, 1=max long"
        )
    ]

    conviction: Annotated[
        Optional[float],
        Field(
            default=None,
            ge=0.0,
            le=1.0,
            description="Optional conviction score [0, 1] for this allocation"
        )
    ]

    metadata: Annotated[
        Optional[dict],
        Field(
            default=None,
            description="Optional metadata (e.g., expected return, risk contribution)"
        )
    ]


class PortfolioTarget(BaseModel, TimestampMixin):
    """
    Target portfolio composition (collection of allocations).

    Represents the desired portfolio state after rebalancing.
    Used as input to order generation logic.

    Validation:
    - Sum of |weights| ≤ max_leverage (default 1.0)
    - All symbols unique (no duplicates)
    - At least one allocation (non-empty)

    Example:
        PortfolioTarget(
            timestamp=datetime.now(timezone.utc),
            allocations=[
                Allocation(symbol='AAPL', weight=0.4),
                Allocation(symbol='SPY', weight=0.6),
            ],
            max_leverage=1.0,
            strategy_id='mean_reversion_v1'
        )
    """

    allocations: Annotated[
        List[Allocation],
        Field(
            min_length=1,
            description="List of symbol allocations (must have at least one)"
        )
    ]

    max_leverage: Annotated[
        float,
        Field(
            default=1.0,
            ge=0.0,
            le=3.0,
            description="Maximum allowed leverage. 1.0=no leverage, 2.0=2x leverage"
        )
    ]

    strategy_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=50,
            pattern=r'^[a-zA-Z0-9_\-]+$',
            description="Strategy that generated this portfolio target"
        )
    ]

    rebalance_reason: Annotated[
        Optional[str],
        Field(
            default=None,
            max_length=200,
            description="Optional reason for rebalancing (e.g., 'signal threshold breach')"
        )
    ]

    @field_validator('allocations')
    @classmethod
    def validate_unique_symbols(cls, v: List[Allocation]) -> List[Allocation]:
        """Ensure all symbols are unique (no duplicate allocations)."""
        symbols = [alloc.symbol for alloc in v]
        if len(symbols) != len(set(symbols)):
            duplicates = [s for s in symbols if symbols.count(s) > 1]
            raise ValueError(f"Duplicate symbols in allocations: {duplicates}")
        return v

    @model_validator(mode='after')
    def validate_leverage_constraint(self) -> 'PortfolioTarget':
        """Ensure sum of absolute weights <= max_leverage."""
        total_abs_weight = sum(abs(alloc.weight) for alloc in self.allocations)

        if total_abs_weight > self.max_leverage:
            raise ValueError(
                f"Total absolute weight ({total_abs_weight:.4f}) exceeds "
                f"max_leverage ({self.max_leverage}). "
                "Reduce position sizes or increase max_leverage."
            )

        return self

    @property
    def gross_exposure(self) -> float:
        """Calculate gross exposure (sum of absolute weights)."""
        return sum(abs(alloc.weight) for alloc in self.allocations)

    @property
    def net_exposure(self) -> float:
        """Calculate net exposure (sum of signed weights)."""
        return sum(alloc.weight for alloc in self.allocations)

    @property
    def long_exposure(self) -> float:
        """Calculate long exposure (sum of positive weights)."""
        return sum(max(0, alloc.weight) for alloc in self.allocations)

    @property
    def short_exposure(self) -> float:
        """Calculate short exposure (sum of negative weights, absolute value)."""
        return sum(abs(min(0, alloc.weight)) for alloc in self.allocations)
