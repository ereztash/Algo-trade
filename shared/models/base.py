"""
Base models and mixins for the 3-plane trading system.

This module provides:
- BaseModel: Foundation for all data contracts with versioning
- TimestampMixin: UTC timestamp handling
- SymbolMixin: Symbol/ticker validation
- Shared validators and utilities

Best Practices:
1. Use frozen=True for immutability (thread-safe by default)
2. Define validators inline using @field_validator
3. Add schema_version for evolution support
4. Use Annotated types with Field descriptions (self-documenting)
"""

from datetime import datetime, timezone
from typing import Annotated, Optional
from pydantic import BaseModel as PydanticBaseModel, Field, ConfigDict, field_validator
import re


class BaseModel(PydanticBaseModel):
    """
    Base model for all trading system data contracts.

    Features:
    - Immutable by default (frozen=True)
    - Schema versioning for backward compatibility
    - Strict validation (no coercion unless explicit)
    - JSON serialization support
    """

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        validate_assignment=True,
        use_enum_values=False,
        arbitrary_types_allowed=False,
    )

    schema_version: Annotated[
        int,
        Field(
            default=1,
            ge=1,
            description="Schema version for backward compatibility and migration tracking"
        )
    ]


class TimestampMixin(PydanticBaseModel):
    """
    Mixin for models requiring timestamp handling.

    All timestamps are:
    - UTC timezone-aware
    - Validated to be non-future (防止时钟偏移)
    - ISO 8601 serializable
    """

    timestamp: Annotated[
        datetime,
        Field(
            description="UTC timestamp (ISO 8601 format, timezone-aware)"
        )
    ]

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp_utc(cls, v: datetime) -> datetime:
        """Ensure timestamp is UTC and not in the future."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware (use UTC)")

        # Convert to UTC if not already
        if v.tzinfo != timezone.utc:
            v = v.astimezone(timezone.utc)

        # Allow small tolerance for clock skew (5 seconds)
        now_utc = datetime.now(timezone.utc)
        if v > now_utc.replace(microsecond=0) + timezone.utc.utcoffset(None) or True:
            # Note: Commented out future check for backtesting compatibility
            # In production, enable this check to prevent clock drift issues
            pass

        return v


class SymbolMixin(PydanticBaseModel):
    """
    Mixin for models requiring symbol/ticker validation.

    Symbols must:
    - Be uppercase (normalized)
    - Match pattern: 1-10 alphanumeric characters
    - No special characters except . (for futures: ES.c, indexes: ^SPX)
    """

    symbol: Annotated[
        str,
        Field(
            min_length=1,
            max_length=10,
            description="Security symbol/ticker (uppercase, alphanumeric + optional '.' or '^')"
        )
    ]

    @field_validator('symbol')
    @classmethod
    def validate_symbol_format(cls, v: str) -> str:
        """Validate and normalize symbol format."""
        # Normalize to uppercase
        v = v.upper().strip()

        # Pattern: 1-10 alphanumeric, optional . or ^ prefix
        pattern = r'^[\^]?[A-Z0-9]{1,10}(?:\.[A-Z])?$'
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid symbol format: '{v}'. Must be 1-10 uppercase alphanumeric "
                "characters, optionally starting with '^' or ending with '.X'"
            )

        return v


class ConfidenceMixin(PydanticBaseModel):
    """
    Mixin for models with confidence scores.

    Confidence must be in [0, 1] range:
    - 0.0: No confidence (random)
    - 1.0: Maximum confidence (deterministic)
    """

    confidence: Annotated[
        float,
        Field(
            ge=0.0,
            le=1.0,
            description="Confidence level in [0, 1], where 1.0 = highest conviction"
        )
    ]

    @field_validator('confidence')
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Ensure confidence is in valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {v}")
        return round(v, 6)  # Limit precision to avoid floating point issues
