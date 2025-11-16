"""
Centralized schema validation module for Kafka message contracts.

This module provides a unified interface for validating messages using:
1. Pydantic models (runtime type checking and validation)
2. JSON Schema validation (structural validation)

Usage:
    from contracts.schema_validator import MessageValidator, ValidationResult

    validator = MessageValidator()

    # Validate a BarEvent
    result = validator.validate_message(bar_data, 'bar_event')
    if result.is_valid:
        print("Message is valid")
    else:
        print(f"Validation errors: {result.errors}")
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Type
from enum import Enum
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
import jsonschema
from jsonschema import Draft7Validator, validators

from contracts.validators import (
    BarEvent,
    TickEvent,
    OFIEvent,
    OrderIntent,
    ExecutionReport,
)


# ============================================================================
# Configuration and Constants
# ============================================================================

logger = logging.getLogger(__name__)

SCHEMA_DIR = Path(__file__).parent
JSON_SCHEMAS = {
    'bar_event': SCHEMA_DIR / 'bar_event.schema.json',
    'order_intent': SCHEMA_DIR / 'order_intent.schema.json',
    'execution_report': SCHEMA_DIR / 'execution_report.schema.json',
}

PYDANTIC_MODELS: Dict[str, Type[BaseModel]] = {
    'bar_event': BarEvent,
    'tick_event': TickEvent,
    'ofi_event': OFIEvent,
    'order_intent': OrderIntent,
    'execution_report': ExecutionReport,
}


class ValidationMode(str, Enum):
    """Validation modes."""
    PYDANTIC_ONLY = 'pydantic_only'
    JSON_SCHEMA_ONLY = 'json_schema_only'
    BOTH = 'both'  # Default: run both validators


# ============================================================================
# Validation Result
# ============================================================================

@dataclass
class ValidationResult:
    """
    Result of message validation.

    Attributes:
        is_valid: Whether the message passed validation
        errors: List of validation error messages
        warnings: List of validation warnings (non-critical)
        validated_data: The validated data (Pydantic model instance if available)
        event_type: The type of event that was validated
    """
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    validated_data: Optional[BaseModel] = None
    event_type: Optional[str] = None

    def __bool__(self) -> bool:
        """Allow using ValidationResult as a boolean."""
        return self.is_valid

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'event_type': self.event_type,
            'has_validated_data': self.validated_data is not None,
        }


# ============================================================================
# Message Validator
# ============================================================================

class MessageValidator:
    """
    Centralized message validator for Kafka contracts.

    Validates messages using both Pydantic models and JSON schemas.
    Provides caching of JSON schemas for performance.
    """

    def __init__(self, mode: ValidationMode = ValidationMode.BOTH):
        """
        Initialize the validator.

        Args:
            mode: Validation mode (pydantic_only, json_schema_only, or both)
        """
        self.mode = mode
        self._json_schemas: Dict[str, Dict[str, Any]] = {}
        self._json_validators: Dict[str, Draft7Validator] = {}
        self._load_json_schemas()

    def _load_json_schemas(self) -> None:
        """Load and cache JSON schemas."""
        if self.mode == ValidationMode.PYDANTIC_ONLY:
            return

        for event_type, schema_path in JSON_SCHEMAS.items():
            try:
                if not schema_path.exists():
                    logger.warning(f"JSON schema not found: {schema_path}")
                    continue

                with open(schema_path, 'r') as f:
                    schema = json.load(f)
                    self._json_schemas[event_type] = schema

                    # Create validator with default values
                    self._json_validators[event_type] = Draft7Validator(schema)

                logger.debug(f"Loaded JSON schema for {event_type}")
            except Exception as e:
                logger.error(f"Failed to load JSON schema for {event_type}: {e}")

    def validate_message(
        self,
        data: Union[Dict[str, Any], str],
        event_type: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate a message using configured validation mode.

        Args:
            data: Message data (dict or JSON string)
            event_type: Type of event (e.g., 'bar_event', 'order_intent')
                       If not provided, will try to infer from data['event_type']

        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        warnings = []
        validated_data = None

        # Parse JSON string if needed
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as e:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Invalid JSON: {e}"],
                    warnings=[],
                    event_type=event_type,
                )

        # Infer event type if not provided
        if event_type is None:
            event_type = data.get('event_type')
            if event_type is None:
                return ValidationResult(
                    is_valid=False,
                    errors=["Cannot infer event_type from data"],
                    warnings=[],
                )

        # Validate with Pydantic
        if self.mode in [ValidationMode.PYDANTIC_ONLY, ValidationMode.BOTH]:
            pydantic_result = self._validate_with_pydantic(data, event_type)
            if not pydantic_result.is_valid:
                errors.extend(pydantic_result.errors)
            else:
                validated_data = pydantic_result.validated_data
            warnings.extend(pydantic_result.warnings)

        # Validate with JSON Schema
        if self.mode in [ValidationMode.JSON_SCHEMA_ONLY, ValidationMode.BOTH]:
            json_schema_result = self._validate_with_json_schema(data, event_type)
            if not json_schema_result.is_valid:
                errors.extend(json_schema_result.errors)
            warnings.extend(json_schema_result.warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_data=validated_data,
            event_type=event_type,
        )

    def _validate_with_pydantic(
        self,
        data: Dict[str, Any],
        event_type: str,
    ) -> ValidationResult:
        """
        Validate using Pydantic models.

        Args:
            data: Message data
            event_type: Type of event

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []
        validated_data = None

        # Get the Pydantic model
        model_class = PYDANTIC_MODELS.get(event_type)
        if model_class is None:
            warnings.append(f"No Pydantic model found for event type: {event_type}")
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=warnings,
                event_type=event_type,
            )

        # Validate
        try:
            validated_data = model_class(**data)
            logger.debug(f"Pydantic validation passed for {event_type}")
        except ValidationError as e:
            for error in e.errors():
                field_path = ' -> '.join(str(loc) for loc in error['loc'])
                error_msg = f"Pydantic: {field_path}: {error['msg']}"
                errors.append(error_msg)
            logger.debug(f"Pydantic validation failed for {event_type}: {errors}")
        except Exception as e:
            errors.append(f"Pydantic validation error: {str(e)}")
            logger.error(f"Unexpected Pydantic validation error: {e}", exc_info=True)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_data=validated_data,
            event_type=event_type,
        )

    def _validate_with_json_schema(
        self,
        data: Dict[str, Any],
        event_type: str,
    ) -> ValidationResult:
        """
        Validate using JSON Schema.

        Args:
            data: Message data
            event_type: Type of event

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Get the JSON schema validator
        validator = self._json_validators.get(event_type)
        if validator is None:
            warnings.append(f"No JSON schema found for event type: {event_type}")
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=warnings,
                event_type=event_type,
            )

        # Validate
        try:
            validation_errors = list(validator.iter_errors(data))
            for error in validation_errors:
                field_path = ' -> '.join(str(p) for p in error.path) or 'root'
                error_msg = f"JSON Schema: {field_path}: {error.message}"
                errors.append(error_msg)

            if errors:
                logger.debug(f"JSON Schema validation failed for {event_type}: {errors}")
            else:
                logger.debug(f"JSON Schema validation passed for {event_type}")
        except Exception as e:
            errors.append(f"JSON Schema validation error: {str(e)}")
            logger.error(f"Unexpected JSON Schema validation error: {e}", exc_info=True)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            event_type=event_type,
        )

    def validate_batch(
        self,
        messages: List[Dict[str, Any]],
        event_type: Optional[str] = None,
    ) -> List[ValidationResult]:
        """
        Validate a batch of messages.

        Args:
            messages: List of message data dictionaries
            event_type: Optional event type (will be inferred if not provided)

        Returns:
            List of ValidationResult objects
        """
        return [
            self.validate_message(msg, event_type)
            for msg in messages
        ]

    def get_model_for_event(self, event_type: str) -> Optional[Type[BaseModel]]:
        """
        Get the Pydantic model class for an event type.

        Args:
            event_type: Type of event

        Returns:
            Pydantic model class or None
        """
        return PYDANTIC_MODELS.get(event_type)

    def get_supported_event_types(self) -> List[str]:
        """
        Get list of supported event types.

        Returns:
            List of event type strings
        """
        return list(PYDANTIC_MODELS.keys())


# ============================================================================
# Convenience Functions
# ============================================================================

# Global validator instance
_default_validator: Optional[MessageValidator] = None


def get_validator(mode: ValidationMode = ValidationMode.BOTH) -> MessageValidator:
    """
    Get or create the default validator instance.

    Args:
        mode: Validation mode

    Returns:
        MessageValidator instance
    """
    global _default_validator
    if _default_validator is None:
        _default_validator = MessageValidator(mode=mode)
    return _default_validator


def validate(
    data: Union[Dict[str, Any], str],
    event_type: Optional[str] = None,
    mode: ValidationMode = ValidationMode.BOTH,
) -> ValidationResult:
    """
    Convenience function to validate a message.

    Args:
        data: Message data (dict or JSON string)
        event_type: Type of event (optional, will be inferred if not provided)
        mode: Validation mode

    Returns:
        ValidationResult
    """
    validator = get_validator(mode=mode)
    return validator.validate_message(data, event_type)


def validate_bar_event(data: Union[Dict[str, Any], str]) -> ValidationResult:
    """Validate a BarEvent."""
    return validate(data, 'bar_event')


def validate_tick_event(data: Union[Dict[str, Any], str]) -> ValidationResult:
    """Validate a TickEvent."""
    return validate(data, 'tick_event')


def validate_ofi_event(data: Union[Dict[str, Any], str]) -> ValidationResult:
    """Validate an OFIEvent."""
    return validate(data, 'ofi_event')


def validate_order_intent(data: Union[Dict[str, Any], str]) -> ValidationResult:
    """Validate an OrderIntent."""
    return validate(data, 'order_intent')


def validate_execution_report(data: Union[Dict[str, Any], str]) -> ValidationResult:
    """Validate an ExecutionReport."""
    return validate(data, 'execution_report')


# ============================================================================
# Dead Letter Queue (DLQ) Handler
# ============================================================================

class DLQHandler:
    """
    Handler for invalid messages.

    Logs validation errors and routes invalid messages to a dead letter queue.
    """

    def __init__(self, dlq_topic: str = "dlq_invalid_messages"):
        """
        Initialize DLQ handler.

        Args:
            dlq_topic: Kafka topic for dead letter queue
        """
        self.dlq_topic = dlq_topic
        self.error_count = 0
        self.logger = logging.getLogger(f"{__name__}.DLQHandler")

    def handle_invalid_message(
        self,
        message: Dict[str, Any],
        validation_result: ValidationResult,
        source_topic: str,
    ) -> None:
        """
        Handle an invalid message.

        Args:
            message: The invalid message data
            validation_result: Validation result with errors
            source_topic: Original Kafka topic
        """
        self.error_count += 1

        error_payload = {
            'source_topic': source_topic,
            'dlq_topic': self.dlq_topic,
            'event_type': validation_result.event_type,
            'errors': validation_result.errors,
            'warnings': validation_result.warnings,
            'original_message': message,
            'error_count': self.error_count,
        }

        self.logger.error(
            f"Invalid message from {source_topic}: {validation_result.errors}",
            extra={'error_payload': error_payload}
        )

        # In production, would publish to DLQ Kafka topic
        # For now, just log
        self.logger.info(f"Would publish to DLQ: {self.dlq_topic}")

    def get_error_count(self) -> int:
        """Get total error count."""
        return self.error_count

    def reset_error_count(self) -> None:
        """Reset error count."""
        self.error_count = 0
