"""
Data Plane message validation integration.

This module integrates schema validation into the Data Plane orchestrator.
Validates outgoing market data events before publishing to Kafka.
"""

import logging
from typing import Dict, Any, Optional

from contracts.schema_validator import (
    MessageValidator,
    ValidationResult,
    ValidationMode,
    DLQHandler,
)
from contracts.validators import BarEvent, TickEvent, OFIEvent


logger = logging.getLogger(__name__)


class DataPlaneValidator:
    """
    Validator for Data Plane messages.

    Validates market data events before publishing to Kafka topics.
    Routes invalid messages to dead letter queue.
    """

    def __init__(
        self,
        validation_mode: ValidationMode = ValidationMode.BOTH,
        dlq_topic: str = "dlq_market_events",
        strict_mode: bool = True,
    ):
        """
        Initialize Data Plane validator.

        Args:
            validation_mode: Validation mode (pydantic_only, json_schema_only, or both)
            dlq_topic: Dead letter queue topic for invalid messages
            strict_mode: If True, raise exceptions on validation errors
        """
        self.validator = MessageValidator(mode=validation_mode)
        self.dlq_handler = DLQHandler(dlq_topic=dlq_topic)
        self.strict_mode = strict_mode

        # Metrics
        self.validation_count = 0
        self.validation_errors = 0
        self.validation_warnings = 0

    def validate_bar_event(
        self,
        bar_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate a BarEvent before publishing.

        Args:
            bar_data: Bar event data dictionary
            raise_on_error: Override strict_mode for this call

        Returns:
            ValidationResult

        Raises:
            ValueError: If validation fails and strict_mode/raise_on_error is True
        """
        self.validation_count += 1
        result = self.validator.validate_message(bar_data, 'bar_event')

        if not result.is_valid:
            self.validation_errors += 1
            self.dlq_handler.handle_invalid_message(
                bar_data, result, source_topic='market_raw'
            )

            should_raise = raise_on_error if raise_on_error is not None else self.strict_mode
            if should_raise:
                raise ValueError(f"BarEvent validation failed: {result.errors}")

        if result.warnings:
            self.validation_warnings += len(result.warnings)
            logger.warning(f"BarEvent validation warnings: {result.warnings}")

        return result

    def validate_tick_event(
        self,
        tick_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate a TickEvent before publishing.

        Args:
            tick_data: Tick event data dictionary
            raise_on_error: Override strict_mode for this call

        Returns:
            ValidationResult

        Raises:
            ValueError: If validation fails and strict_mode/raise_on_error is True
        """
        self.validation_count += 1
        result = self.validator.validate_message(tick_data, 'tick_event')

        if not result.is_valid:
            self.validation_errors += 1
            self.dlq_handler.handle_invalid_message(
                tick_data, result, source_topic='market_raw'
            )

            should_raise = raise_on_error if raise_on_error is not None else self.strict_mode
            if should_raise:
                raise ValueError(f"TickEvent validation failed: {result.errors}")

        if result.warnings:
            self.validation_warnings += len(result.warnings)
            logger.warning(f"TickEvent validation warnings: {result.warnings}")

        return result

    def validate_ofi_event(
        self,
        ofi_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate an OFIEvent before publishing.

        Args:
            ofi_data: OFI event data dictionary
            raise_on_error: Override strict_mode for this call

        Returns:
            ValidationResult

        Raises:
            ValueError: If validation fails and strict_mode/raise_on_error is True
        """
        self.validation_count += 1
        result = self.validator.validate_message(ofi_data, 'ofi_event')

        if not result.is_valid:
            self.validation_errors += 1
            self.dlq_handler.handle_invalid_message(
                ofi_data, result, source_topic='market_events'
            )

            should_raise = raise_on_error if raise_on_error is not None else self.strict_mode
            if should_raise:
                raise ValueError(f"OFIEvent validation failed: {result.errors}")

        if result.warnings:
            self.validation_warnings += len(result.warnings)
            logger.warning(f"OFIEvent validation warnings: {result.warnings}")

        return result

    def get_metrics(self) -> Dict[str, int]:
        """
        Get validation metrics.

        Returns:
            Dictionary with validation metrics
        """
        return {
            'validation_count': self.validation_count,
            'validation_errors': self.validation_errors,
            'validation_warnings': self.validation_warnings,
            'dlq_error_count': self.dlq_handler.get_error_count(),
            'validation_success_rate': (
                (self.validation_count - self.validation_errors) / self.validation_count
                if self.validation_count > 0 else 1.0
            ),
        }

    def reset_metrics(self) -> None:
        """Reset validation metrics."""
        self.validation_count = 0
        self.validation_errors = 0
        self.validation_warnings = 0
        self.dlq_handler.reset_error_count()
