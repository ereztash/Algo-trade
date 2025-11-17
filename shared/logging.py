"""
Structured logging with JSON formatting and distributed tracing support.

Provides:
- JSON-formatted logs for easy parsing
- Trace IDs for request correlation
- Context propagation across service boundaries
- Performance-aware logging (latency tracking)
- Security-aware logging (PII redaction)
"""

import logging
import json
import time
import uuid
from typing import Optional, Dict, Any
from contextvars import ContextVar
from datetime import datetime
import traceback
import sys


# Context variable for trace ID propagation
_trace_id: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
_span_id: ContextVar[Optional[str]] = ContextVar('span_id', default=None)
_parent_span_id: ContextVar[Optional[str]] = ContextVar('parent_span_id', default=None)


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def __init__(self, service_name: str, environment: str = "development"):
        """Initialize JSON formatter.

        Args:
            service_name: Name of the service (data_plane, strategy_plane, order_plane)
            environment: Environment name (development, staging, production)
        """
        super().__init__()
        self.service_name = service_name
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "service": self.service_name,
            "environment": self.environment,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "thread": record.thread,
            "thread_name": record.threadName,
        }

        # Add trace/span IDs if available
        trace_id = _trace_id.get()
        if trace_id:
            log_data["trace_id"] = trace_id

        span_id = _span_id.get()
        if span_id:
            log_data["span_id"] = span_id

        parent_span_id = _parent_span_id.get()
        if parent_span_id:
            log_data["parent_span_id"] = parent_span_id

        # Add custom fields from record
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }

        # Add stack info if present
        if record.stack_info:
            log_data["stack_info"] = record.stack_info

        return json.dumps(log_data)


class StructuredLogger:
    """Structured logger with context management and tracing support."""

    def __init__(
        self,
        name: str,
        service_name: str,
        environment: str = "development",
        level: int = logging.INFO,
        json_output: bool = True
    ):
        """Initialize structured logger.

        Args:
            name: Logger name
            service_name: Service name (data_plane, strategy_plane, order_plane)
            environment: Environment (development, staging, production)
            level: Log level (default: INFO)
            json_output: Whether to use JSON formatting (default: True)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.service_name = service_name
        self.environment = environment

        # Remove existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Add console handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        if json_output:
            formatter = JSONFormatter(service_name, environment)
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Prevent propagation to root logger
        self.logger.propagate = False

    def _add_extra_fields(self, extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Add extra fields to log record.

        Args:
            extra: Optional extra fields

        Returns:
            Dictionary with extra fields
        """
        if extra is None:
            extra = {}

        # Create a copy to avoid mutating the original
        extra = extra.copy()
        extra_fields = extra.pop('extra_fields', {})

        # Add trace context if available
        trace_id = _trace_id.get()
        if trace_id:
            extra_fields['trace_id'] = trace_id

        span_id = _span_id.get()
        if span_id:
            extra_fields['span_id'] = span_id

        return {'extra_fields': extra_fields, **extra}

    def debug(self, msg: str, **kwargs):
        """Log debug message.

        Args:
            msg: Log message
            **kwargs: Additional fields to include in log
        """
        extra = self._add_extra_fields({'extra_fields': kwargs})
        self.logger.debug(msg, extra=extra)

    def info(self, msg: str, **kwargs):
        """Log info message.

        Args:
            msg: Log message
            **kwargs: Additional fields to include in log
        """
        extra = self._add_extra_fields({'extra_fields': kwargs})
        self.logger.info(msg, extra=extra)

    def warning(self, msg: str, **kwargs):
        """Log warning message.

        Args:
            msg: Log message
            **kwargs: Additional fields to include in log
        """
        extra = self._add_extra_fields({'extra_fields': kwargs})
        self.logger.warning(msg, extra=extra)

    def error(self, msg: str, **kwargs):
        """Log error message.

        Args:
            msg: Log message
            **kwargs: Additional fields to include in log
        """
        extra = self._add_extra_fields({'extra_fields': kwargs})
        self.logger.error(msg, extra=extra, exc_info=kwargs.get('exc_info', False))

    def critical(self, msg: str, **kwargs):
        """Log critical message.

        Args:
            msg: Log message
            **kwargs: Additional fields to include in log
        """
        extra = self._add_extra_fields({'extra_fields': kwargs})
        self.logger.critical(msg, extra=extra, exc_info=kwargs.get('exc_info', False))

    def exception(self, msg: str, **kwargs):
        """Log exception with traceback.

        Args:
            msg: Log message
            **kwargs: Additional fields to include in log
        """
        extra = self._add_extra_fields({'extra_fields': kwargs})
        self.logger.exception(msg, extra=extra)


class TraceContext:
    """Context manager for trace ID propagation."""

    def __init__(
        self,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        parent_span_id: Optional[str] = None
    ):
        """Initialize trace context.

        Args:
            trace_id: Optional trace ID (generated if not provided)
            span_id: Optional span ID (generated if not provided)
            parent_span_id: Optional parent span ID
        """
        self.trace_id = trace_id or str(uuid.uuid4())
        self.span_id = span_id or str(uuid.uuid4())
        self.parent_span_id = parent_span_id
        self.tokens = []

    def __enter__(self):
        """Enter trace context."""
        self.tokens.append(_trace_id.set(self.trace_id))
        self.tokens.append(_span_id.set(self.span_id))
        if self.parent_span_id:
            self.tokens.append(_parent_span_id.set(self.parent_span_id))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit trace context."""
        for token in reversed(self.tokens):
            if token:
                try:
                    _trace_id.reset(token) if token.var is _trace_id else None
                    _span_id.reset(token) if token.var is _span_id else None
                    _parent_span_id.reset(token) if token.var is _parent_span_id else None
                except (ValueError, LookupError):
                    pass


class PerformanceLogger:
    """Logger for performance metrics with automatic latency tracking."""

    def __init__(self, logger: StructuredLogger, operation: str):
        """Initialize performance logger.

        Args:
            logger: Structured logger instance
            operation: Operation name being tracked
        """
        self.logger = logger
        self.operation = operation
        self.start_time = None

    def __enter__(self):
        """Start performance tracking."""
        self.start_time = time.perf_counter()
        self.logger.debug(f"{self.operation} started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End performance tracking and log duration."""
        duration_ms = (time.perf_counter() - self.start_time) * 1000

        if exc_type:
            self.logger.error(
                f"{self.operation} failed",
                duration_ms=duration_ms,
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                exc_info=True
            )
        else:
            self.logger.info(
                f"{self.operation} completed",
                duration_ms=duration_ms
            )


def redact_pii(data: Dict[str, Any], pii_fields: Optional[list] = None) -> Dict[str, Any]:
    """Redact PII fields from log data.

    Args:
        data: Data dictionary
        pii_fields: List of field names to redact (default: common PII fields)

    Returns:
        Dictionary with PII fields redacted
    """
    if pii_fields is None:
        pii_fields = [
            'password', 'secret', 'api_key', 'token', 'ssn',
            'credit_card', 'account_number', 'routing_number'
        ]

    redacted = data.copy()
    for field in pii_fields:
        if field in redacted:
            redacted[field] = "***REDACTED***"

    return redacted


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context.

    Returns:
        Current trace ID or None
    """
    return _trace_id.get()


def get_span_id() -> Optional[str]:
    """Get current span ID from context.

    Returns:
        Current span ID or None
    """
    return _span_id.get()


def get_parent_span_id() -> Optional[str]:
    """Get current parent span ID from context.

    Returns:
        Current parent span ID or None
    """
    return _parent_span_id.get()


# Global logger instances
_loggers: Dict[str, StructuredLogger] = {}


def init_structured_logger(
    service_name: str,
    environment: str = "development",
    level: int = logging.INFO,
    json_output: bool = True
) -> StructuredLogger:
    """Initialize and return a structured logger.

    Args:
        service_name: Service name (data_plane, strategy_plane, order_plane)
        environment: Environment (development, staging, production)
        level: Log level (default: INFO)
        json_output: Whether to use JSON formatting (default: True)

    Returns:
        StructuredLogger instance
    """
    logger_key = f"{service_name}:{environment}"

    if logger_key not in _loggers:
        _loggers[logger_key] = StructuredLogger(
            name=service_name,
            service_name=service_name,
            environment=environment,
            level=level,
            json_output=json_output
        )
        print(f"✓ Structured logger initialized for {service_name} ({environment})")

    return _loggers[logger_key]


def get_logger(service_name: str) -> Optional[StructuredLogger]:
    """Get logger instance by service name.

    Args:
        service_name: Service name

    Returns:
        StructuredLogger instance or None if not initialized
    """
    for key, logger in _loggers.items():
        if key.startswith(service_name):
            return logger
    return None


# Example usage:
if __name__ == "__main__":
    # Initialize logger
    logger = init_structured_logger("data_plane", environment="development", json_output=True)

    # Simple logging
    logger.info("Service started", port=9090)

    # Logging with trace context
    with TraceContext() as trace:
        logger.info("Processing market data", conid=123456, event_type="BarEvent")

        # Performance logging
        with PerformanceLogger(logger, "data_ingestion"):
            time.sleep(0.1)  # Simulate work

        # Nested span
        with TraceContext(trace_id=trace.trace_id, parent_span_id=trace.span_id) as child_trace:
            logger.info("Normalization started", conid=123456)

    # Error logging
    try:
        raise ValueError("Invalid data format")
    except Exception:
        logger.exception("Data processing failed", conid=123456)

    # Logging with PII redaction
    user_data = {
        "username": "trader01",
        "password": "secret123",
        "api_key": "key_abc123"
    }
    logger.info("User login", **redact_pii(user_data))
