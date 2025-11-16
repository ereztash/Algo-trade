"""
Strategy Plane message validation integration.

This module integrates schema validation into the Strategy Plane.
Validates:
- Incoming market data events (BarEvent, TickEvent, OFIEvent)
- Outgoing order intents to Order Plane
- Incoming execution reports from Order Plane
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import uuid4

from contracts.schema_validator import (
    MessageValidator,
    ValidationResult,
    ValidationMode,
    DLQHandler,
)
from contracts.validators import (
    BarEvent,
    TickEvent,
    OFIEvent,
    OrderIntent,
    ExecutionReport,
)


logger = logging.getLogger(__name__)


class StrategyPlaneValidator:
    """
    Validator for Strategy Plane messages.

    Validates:
    - Incoming market data events (BarEvent, TickEvent, OFIEvent)
    - Outgoing OrderIntents
    - Incoming ExecutionReports for learning loop
    """

    def __init__(
        self,
        validation_mode: ValidationMode = ValidationMode.BOTH,
        dlq_topic_market: str = "dlq_strategy_market_events",
        dlq_topic_intents: str = "dlq_strategy_order_intents",
        dlq_topic_reports: str = "dlq_strategy_exec_reports",
        strict_mode: bool = True,
    ):
        """
        Initialize Strategy Plane validator.

        Args:
            validation_mode: Validation mode (pydantic_only, json_schema_only, or both)
            dlq_topic_market: DLQ topic for invalid market events
            dlq_topic_intents: DLQ topic for invalid order intents
            dlq_topic_reports: DLQ topic for invalid execution reports
            strict_mode: If True, raise exceptions on validation errors
        """
        self.validator = MessageValidator(mode=validation_mode)
        self.dlq_handler_market = DLQHandler(dlq_topic=dlq_topic_market)
        self.dlq_handler_intents = DLQHandler(dlq_topic=dlq_topic_intents)
        self.dlq_handler_reports = DLQHandler(dlq_topic=dlq_topic_reports)
        self.strict_mode = strict_mode

        # Metrics
        self.market_validation_count = 0
        self.market_validation_errors = 0
        self.intent_validation_count = 0
        self.intent_validation_errors = 0
        self.report_validation_count = 0
        self.report_validation_errors = 0
        self.validation_warnings = 0

    # ========================================================================
    # Incoming Market Data Validation
    # ========================================================================

    def validate_market_event(
        self,
        event_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate an incoming market event (auto-detects type).

        Args:
            event_data: Market event data dictionary
            raise_on_error: Override strict_mode for this call

        Returns:
            ValidationResult

        Raises:
            ValueError: If validation fails and strict_mode/raise_on_error is True
        """
        self.market_validation_count += 1
        event_type = event_data.get('event_type')

        # Auto-detect event type if not specified
        if event_type is None:
            # Try to infer from data structure
            if 'ofi_z' in event_data:
                event_type = 'ofi_event'
            elif 'bid' in event_data and 'ask' in event_data:
                event_type = 'tick_event'
            elif 'open' in event_data and 'high' in event_data:
                event_type = 'bar_event'
            else:
                logger.error(f"Cannot infer event type from data: {event_data.keys()}")
                event_type = 'unknown'

        result = self.validator.validate_message(event_data, event_type)

        if not result.is_valid:
            self.market_validation_errors += 1
            self.dlq_handler_market.handle_invalid_message(
                event_data, result, source_topic='market_events'
            )

            should_raise = raise_on_error if raise_on_error is not None else self.strict_mode
            if should_raise:
                raise ValueError(f"Market event validation failed: {result.errors}")

            logger.error(f"Market event validation failed: {result.errors}")
        else:
            logger.debug(f"Market event validation passed: {event_type}")

        if result.warnings:
            self.validation_warnings += len(result.warnings)
            logger.warning(f"Market event validation warnings: {result.warnings}")

        return result

    def validate_bar_event(
        self,
        bar_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """Validate a BarEvent."""
        return self.validate_market_event(bar_data, raise_on_error)

    def validate_tick_event(
        self,
        tick_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """Validate a TickEvent."""
        return self.validate_market_event(tick_data, raise_on_error)

    def validate_ofi_event(
        self,
        ofi_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """Validate an OFIEvent."""
        return self.validate_market_event(ofi_data, raise_on_error)

    # ========================================================================
    # Outgoing Order Intent Validation
    # ========================================================================

    def validate_order_intent(
        self,
        intent_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate an outgoing OrderIntent before publishing.

        Args:
            intent_data: Order intent data dictionary
            raise_on_error: Override strict_mode for this call

        Returns:
            ValidationResult

        Raises:
            ValueError: If validation fails and strict_mode/raise_on_error is True
        """
        self.intent_validation_count += 1
        result = self.validator.validate_message(intent_data, 'order_intent')

        if not result.is_valid:
            self.intent_validation_errors += 1
            self.dlq_handler_intents.handle_invalid_message(
                intent_data, result, source_topic='order_intents'
            )

            should_raise = raise_on_error if raise_on_error is not None else self.strict_mode
            if should_raise:
                raise ValueError(f"OrderIntent validation failed: {result.errors}")

            logger.error(f"OrderIntent validation failed: {result.errors}")
        else:
            logger.debug(f"OrderIntent validation passed: {intent_data.get('intent_id')}")

        if result.warnings:
            self.validation_warnings += len(result.warnings)
            logger.warning(f"OrderIntent validation warnings: {result.warnings}")

        return result

    def create_order_intent(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        order_type: str,
        strategy_id: str,
        **kwargs
    ) -> OrderIntent:
        """
        Create and validate an OrderIntent.

        Args:
            symbol: Asset symbol
            direction: BUY or SELL
            quantity: Order quantity
            order_type: MARKET, LIMIT, STOP, STOP_LIMIT, or ADAPTIVE
            strategy_id: Strategy identifier
            **kwargs: Additional OrderIntent fields

        Returns:
            Validated OrderIntent instance

        Raises:
            ValueError: If validation fails
        """
        from datetime import datetime

        intent_data = {
            'event_type': 'order_intent',
            'intent_id': str(uuid4()),
            'symbol': symbol,
            'direction': direction,
            'quantity': quantity,
            'order_type': order_type,
            'strategy_id': strategy_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            **kwargs
        }

        result = self.validate_order_intent(intent_data, raise_on_error=True)
        return result.validated_data

    # ========================================================================
    # Incoming Execution Report Validation
    # ========================================================================

    def validate_execution_report(
        self,
        report_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate an incoming ExecutionReport for learning loop.

        Args:
            report_data: Execution report data dictionary
            raise_on_error: Override strict_mode for this call

        Returns:
            ValidationResult

        Raises:
            ValueError: If validation fails and strict_mode/raise_on_error is True
        """
        self.report_validation_count += 1
        result = self.validator.validate_message(report_data, 'execution_report')

        if not result.is_valid:
            self.report_validation_errors += 1
            self.dlq_handler_reports.handle_invalid_message(
                report_data, result, source_topic='exec_reports'
            )

            should_raise = raise_on_error if raise_on_error is not None else self.strict_mode
            if should_raise:
                raise ValueError(f"ExecutionReport validation failed: {result.errors}")

            logger.error(f"ExecutionReport validation failed: {result.errors}")
        else:
            logger.debug(f"ExecutionReport validation passed: {report_data.get('report_id')}")

        if result.warnings:
            self.validation_warnings += len(result.warnings)
            logger.warning(f"ExecutionReport validation warnings: {result.warnings}")

        return result

    # ========================================================================
    # Batch Validation
    # ========================================================================

    def validate_market_events_batch(
        self,
        events: List[Dict[str, Any]],
    ) -> List[ValidationResult]:
        """
        Validate a batch of market events.

        Args:
            events: List of market event data dictionaries

        Returns:
            List of ValidationResult objects
        """
        return [self.validate_market_event(event, raise_on_error=False) for event in events]

    # ========================================================================
    # Metrics and Monitoring
    # ========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get validation metrics.

        Returns:
            Dictionary with validation metrics
        """
        total_validations = (
            self.market_validation_count +
            self.intent_validation_count +
            self.report_validation_count
        )
        total_errors = (
            self.market_validation_errors +
            self.intent_validation_errors +
            self.report_validation_errors
        )

        return {
            'market_validation_count': self.market_validation_count,
            'market_validation_errors': self.market_validation_errors,
            'intent_validation_count': self.intent_validation_count,
            'intent_validation_errors': self.intent_validation_errors,
            'report_validation_count': self.report_validation_count,
            'report_validation_errors': self.report_validation_errors,
            'validation_warnings': self.validation_warnings,
            'total_validations': total_validations,
            'total_errors': total_errors,
            'validation_success_rate': (
                (total_validations - total_errors) / total_validations
                if total_validations > 0 else 1.0
            ),
            'market_success_rate': (
                (self.market_validation_count - self.market_validation_errors) / self.market_validation_count
                if self.market_validation_count > 0 else 1.0
            ),
            'intent_success_rate': (
                (self.intent_validation_count - self.intent_validation_errors) / self.intent_validation_count
                if self.intent_validation_count > 0 else 1.0
            ),
            'report_success_rate': (
                (self.report_validation_count - self.report_validation_errors) / self.report_validation_count
                if self.report_validation_count > 0 else 1.0
            ),
        }

    def reset_metrics(self) -> None:
        """Reset validation metrics."""
        self.market_validation_count = 0
        self.market_validation_errors = 0
        self.intent_validation_count = 0
        self.intent_validation_errors = 0
        self.report_validation_count = 0
        self.report_validation_errors = 0
        self.validation_warnings = 0
        self.dlq_handler_market.reset_error_count()
        self.dlq_handler_intents.reset_error_count()
        self.dlq_handler_reports.reset_error_count()
