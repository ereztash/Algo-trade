"""
Order Plane message validation integration.

This module integrates schema validation into the Order Plane orchestrator.
Validates incoming OrderIntents and outgoing ExecutionReports.
"""

import logging
from typing import Dict, Any, Optional

from contracts.schema_validator import (
    MessageValidator,
    ValidationResult,
    ValidationMode,
    DLQHandler,
)
from contracts.validators import OrderIntent, ExecutionReport


logger = logging.getLogger(__name__)


class OrderPlaneValidator:
    """
    Validator for Order Plane messages.

    Validates:
    - Incoming OrderIntents from Strategy Plane
    - Outgoing ExecutionReports to Strategy Plane
    """

    def __init__(
        self,
        validation_mode: ValidationMode = ValidationMode.BOTH,
        dlq_topic_intents: str = "dlq_order_intents",
        dlq_topic_reports: str = "dlq_execution_reports",
        strict_mode: bool = True,
    ):
        """
        Initialize Order Plane validator.

        Args:
            validation_mode: Validation mode (pydantic_only, json_schema_only, or both)
            dlq_topic_intents: DLQ topic for invalid order intents
            dlq_topic_reports: DLQ topic for invalid execution reports
            strict_mode: If True, raise exceptions on validation errors
        """
        self.validator = MessageValidator(mode=validation_mode)
        self.dlq_handler_intents = DLQHandler(dlq_topic=dlq_topic_intents)
        self.dlq_handler_reports = DLQHandler(dlq_topic=dlq_topic_reports)
        self.strict_mode = strict_mode

        # Metrics
        self.intent_validation_count = 0
        self.intent_validation_errors = 0
        self.report_validation_count = 0
        self.report_validation_errors = 0
        self.validation_warnings = 0

    def validate_order_intent(
        self,
        intent_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate an incoming OrderIntent.

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

    def validate_execution_report(
        self,
        report_data: Dict[str, Any],
        raise_on_error: Optional[bool] = None,
    ) -> ValidationResult:
        """
        Validate an outgoing ExecutionReport.

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

    def validate_intent_risk_checks(self, intent: OrderIntent) -> Dict[str, bool]:
        """
        Extract and validate risk checks from an OrderIntent.

        Args:
            intent: Validated OrderIntent instance

        Returns:
            Dictionary of risk check results
        """
        if intent.risk_checks is None:
            logger.warning(f"OrderIntent {intent.intent_id} has no risk_checks")
            return {
                'within_box_limit': True,  # Default to pass if not provided
                'within_gross_limit': True,
                'within_net_limit': True,
                'pnl_kill_switch': True,
                'drawdown_kill_switch': True,
            }

        return {
            'within_box_limit': intent.risk_checks.within_box_limit,
            'within_gross_limit': intent.risk_checks.within_gross_limit,
            'within_net_limit': intent.risk_checks.within_net_limit,
            'pnl_kill_switch': intent.risk_checks.pnl_kill_switch,
            'drawdown_kill_switch': intent.risk_checks.drawdown_kill_switch,
        }

    def should_reject_intent(self, intent: OrderIntent) -> tuple[bool, Optional[str]]:
        """
        Check if an OrderIntent should be rejected based on risk checks.

        Args:
            intent: Validated OrderIntent instance

        Returns:
            Tuple of (should_reject, rejection_reason)
        """
        if intent.risk_checks is None:
            return False, None

        risk_checks = self.validate_intent_risk_checks(intent)

        # Check each risk constraint
        for check_name, passed in risk_checks.items():
            if not passed:
                reason = f"Risk check failed: {check_name}"
                logger.warning(f"Rejecting intent {intent.intent_id}: {reason}")
                return True, reason

        return False, None

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get validation metrics.

        Returns:
            Dictionary with validation metrics
        """
        total_validations = self.intent_validation_count + self.report_validation_count
        total_errors = self.intent_validation_errors + self.report_validation_errors

        return {
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
        self.intent_validation_count = 0
        self.intent_validation_errors = 0
        self.report_validation_count = 0
        self.report_validation_errors = 0
        self.validation_warnings = 0
        self.dlq_handler_intents.reset_error_count()
        self.dlq_handler_reports.reset_error_count()
