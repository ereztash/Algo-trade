"""
Structured logging system for Algo-trade.
מערכת לוגים מובנית עבור Algo-trade.
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredLogger:
    """
    Structured logger that outputs JSON-formatted logs.
    לוגר מובנה שמוציא לוגים בפורמט JSON.
    """

    def __init__(self, name: str, level: str = "INFO", stream=None):
        """
        Initialize structured logger.

        Args:
            name: Logger name (usually module name)
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            stream: Output stream (default: sys.stdout)
        """
        self.name = name
        self.level = getattr(logging, level.upper())
        self.stream = stream or sys.stdout

        # Configure Python logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.level)
        self.logger.propagate = False

        # Remove existing handlers
        self.logger.handlers.clear()

        # Add custom handler
        handler = logging.StreamHandler(self.stream)
        handler.setLevel(self.level)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)

    def _log(self, level: str, message: str, **kwargs):
        """
        Internal log method.

        Args:
            level: Log level
            message: Log message
            **kwargs: Additional structured fields
        """
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": self.name,
            "message": message,
        }

        # Add extra fields
        if kwargs:
            log_record["extra"] = kwargs

        # Convert to JSON and log
        log_line = json.dumps(log_record, default=str)
        getattr(self.logger, level.lower())(log_line)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log("DEBUG", message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log("INFO", message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log("WARNING", message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log("ERROR", message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log("CRITICAL", message, **kwargs)

    def exception(self, message: str, exc_info=True, **kwargs):
        """
        Log exception with traceback.

        Args:
            message: Error message
            exc_info: Include exception info
            **kwargs: Additional fields
        """
        self._log("ERROR", message, **kwargs)
        if exc_info:
            import traceback
            self.error("Exception traceback", traceback=traceback.format_exc())


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured logging.
    פורמטר מותאם אישית ללוגים מובנים.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record.

        Args:
            record: Log record

        Returns:
            Formatted log string
        """
        # If message is already JSON, return as-is
        try:
            json.loads(record.getMessage())
            return record.getMessage()
        except (json.JSONDecodeError, ValueError):
            pass

        # Otherwise, create structured log
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def init_structured_logger(name: str = "algo_trade",
                           level: str = "INFO",
                           stream=None) -> StructuredLogger:
    """
    Initialize and return a structured logger.
    אתחול והחזרת לוגר מובנה.

    Args:
        name: Logger name
        level: Log level
        stream: Output stream

    Returns:
        Configured StructuredLogger instance
    """
    return StructuredLogger(name=name, level=level, stream=stream)


class TradingLogger(StructuredLogger):
    """
    Specialized logger for trading events.
    לוגר מיוחד לאירועי טריידינג.
    """

    def trade(self, symbol: str, side: str, qty: float, price: float, **kwargs):
        """Log trade execution."""
        self.info(
            "Trade executed",
            symbol=symbol,
            side=side,
            quantity=qty,
            price=price,
            **kwargs
        )

    def order(self, order_id: str, symbol: str, side: str, qty: float,
              status: str, **kwargs):
        """Log order event."""
        self.info(
            "Order event",
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=qty,
            status=status,
            **kwargs
        )

    def signal(self, symbol: str, signal_name: str, value: float, **kwargs):
        """Log signal generation."""
        self.debug(
            "Signal generated",
            symbol=symbol,
            signal=signal_name,
            value=value,
            **kwargs
        )

    def portfolio(self, gross_exposure: float, net_exposure: float,
                  num_positions: int, **kwargs):
        """Log portfolio state."""
        self.info(
            "Portfolio state",
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            num_positions=num_positions,
            **kwargs
        )

    def risk_event(self, event_type: str, severity: str, message: str, **kwargs):
        """Log risk event."""
        level_map = {
            "LOW": self.info,
            "MEDIUM": self.warning,
            "HIGH": self.error,
            "CRITICAL": self.critical,
        }
        log_func = level_map.get(severity.upper(), self.warning)
        log_func(
            f"Risk event: {event_type}",
            event_type=event_type,
            severity=severity,
            details=message,
            **kwargs
        )

    def performance(self, sharpe: float, max_dd: float, total_return: float,
                   **kwargs):
        """Log performance metrics."""
        self.info(
            "Performance metrics",
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            total_return=total_return,
            **kwargs
        )


def init_trading_logger(name: str = "trading",
                       level: str = "INFO",
                       stream=None) -> TradingLogger:
    """
    Initialize and return a trading logger.
    אתחול והחזרת לוגר טריידינג.

    Args:
        name: Logger name
        level: Log level
        stream: Output stream

    Returns:
        Configured TradingLogger instance
    """
    logger = TradingLogger(name=name, level=level, stream=stream)
    return logger


# Convenience function for backward compatibility
def get_logger(name: str = "algo_trade", level: str = "INFO") -> StructuredLogger:
    """
    Get or create a logger instance.
    קבלת או יצירת instance של לוגר.

    Args:
        name: Logger name
        level: Log level

    Returns:
        Logger instance
    """
    return init_structured_logger(name=name, level=level)


# Example usage
if __name__ == "__main__":
    # Basic structured logger
    logger = init_structured_logger("test", "DEBUG")
    logger.info("System started", version="1.0.0", environment="production")
    logger.debug("Debug information", data={"key": "value"})
    logger.warning("Warning message", threshold_exceeded=True)
    logger.error("Error occurred", error_code=500)

    print("\n--- Trading Logger Example ---\n")

    # Trading logger
    trade_logger = init_trading_logger("trading_test", "DEBUG")
    trade_logger.trade("AAPL", "BUY", 100, 150.50, exchange="NASDAQ")
    trade_logger.signal("TSLA", "momentum", 0.75, zscore=2.3)
    trade_logger.portfolio(1.5, 0.3, 25, total_value=1000000)
    trade_logger.risk_event("DRAWDOWN", "HIGH", "Max drawdown exceeded",
                           current_dd=-0.18, limit=-0.15)
    trade_logger.performance(1.85, -0.12, 0.28, num_trades=150)
