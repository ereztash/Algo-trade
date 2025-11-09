"""
Structured Logger - אתחול logger מובנה
מטרה: יצירת structured JSON logging עם traceability ומדדי ביצועים
"""

import logging
import json
import sys
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import uuid


def init_structured_logger(
    name: str = "algo_trade",
    level: int = logging.INFO,
    output_format: str = "json"
) -> Callable:
    """
    אתחול structured logger עם פורמט JSON.

    Args:
        name: שם ה-logger (default: "algo_trade")
        level: רמת logging (default: INFO)
        output_format: "json" או "text" (default: "json")

    Returns:
        פונקציה logger: log(msg, **kwargs) שמקבלת msg וכל kwargs נוספים

    Usage:
        log = init_structured_logger()
        log("order_placed", conid=12345, qty=100, side="BUY")
        # Output: {"timestamp": "2025-11-09T...", "level": "INFO", "msg": "order_placed", "conid": 12345, ...}
    """

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # הסר handlers קיימים כדי למנוע כפילויות
    if logger.handlers:
        logger.handlers.clear()

    # צור handler ל-stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    # Formatter בהתאם לפורמט
    if output_format == "json":
        formatter = StructuredJSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # צור wrapper function ש-logger מחזיר
    def structured_log(msg: str, level: str = "info", **kwargs):
        """
        Log structured message עם fields נוספים.

        Args:
            msg: הודעה ראשית
            level: רמת log ("debug", "info", "warning", "error", "critical")
            **kwargs: שדות נוספים ל-JSON (e.g., conid=12345, qty=100)
        """
        # בנה dict עם כל הנתונים
        log_data = {
            "msg": msg,
            **kwargs
        }

        # המר dict ל-JSON string
        log_message = json.dumps(log_data)

        # קרא ל-logger ברמה המתאימה
        level_lower = level.lower()
        if level_lower == "debug":
            logger.debug(log_message)
        elif level_lower == "info":
            logger.info(log_message)
        elif level_lower == "warning" or level_lower == "warn":
            logger.warning(log_message)
        elif level_lower == "error":
            logger.error(log_message)
        elif level_lower == "critical":
            logger.critical(log_message)
        else:
            logger.info(log_message)

    return structured_log


class StructuredJSONFormatter(logging.Formatter):
    """
    Custom formatter שמפיק JSON structured logs.
    כל log record מומר ל-JSON object עם timestamp, level, msg, ושדות נוספים.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        פורמט log record ל-JSON.

        Args:
            record: LogRecord מ-logging module

        Returns:
            JSON string
        """
        # בסיס: timestamp, level, logger name
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage()
        }

        # אם יש exception info, הוסף traceback
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # אם ה-message הוא JSON, parse אותו והוסף fields
        try:
            parsed_msg = json.loads(record.msg)
            if isinstance(parsed_msg, dict):
                # מיזוג: msg עצמו הופך להיות field בתוך ה-JSON
                actual_msg = parsed_msg.pop("msg", "")
                log_obj["msg"] = actual_msg
                log_obj.update(parsed_msg)
        except (json.JSONDecodeError, ValueError):
            # אם זה לא JSON, השאר את msg כמו שהוא
            pass

        # הוסף trace_id אם קיים (מעקב אחר requests)
        if hasattr(record, "trace_id"):
            log_obj["trace_id"] = record.trace_id

        # המר ל-JSON string
        return json.dumps(log_obj, default=str)


def get_trace_id() -> str:
    """
    יצירת trace ID אחיד לצורכי tracing.
    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def add_trace_id_to_logger(logger: logging.Logger, trace_id: str):
    """
    הוספת trace_id ל-logger כדי שכל logs יכללו אותו.

    Args:
        logger: Logger instance
        trace_id: Trace ID string
    """
    # הוסף filter שמוסיף trace_id לכל record
    class TraceIDFilter(logging.Filter):
        def filter(self, record):
            record.trace_id = trace_id
            return True

    logger.addFilter(TraceIDFilter())


# דוגמה לשימוש
if __name__ == "__main__":
    # אתחול logger
    log = init_structured_logger(level=logging.DEBUG)

    # דוגמאות logging
    log("system_startup", component="algo_trade", version="1.0.0")
    log("order_placed", level="info", conid=12345, qty=100, side="BUY", price=150.25)
    log("order_filled", level="info", order_id="ORD-001", fill_px=150.30, slippage=0.05)
    log("risk_violation", level="error", reason="max_drawdown", dd_pct=15.5)
    log("debug_info", level="debug", state="S1_L1", kappa=0.45)
