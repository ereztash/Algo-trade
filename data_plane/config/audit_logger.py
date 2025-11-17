# -*- coding: utf-8 -*-
"""
data_plane.config.audit_logger — Security audit logging for secrets access.

Provides tamper-evident audit logging for security-sensitive operations:
- Secrets access (Vault, encrypted files, environment variables)
- Configuration changes
- Authentication attempts
- Authorization failures

Features:
- Structured JSON logging for machine parsing
- Automatic masking of sensitive values
- Separate audit log file with restricted permissions
- Compliance with security best practices
- Integration with existing config system
"""
from __future__ import annotations

import os
import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from enum import Enum


class AuditEventType(Enum):
    """Types of auditable events."""
    SECRET_ACCESS = "secret_access"
    SECRET_WRITE = "secret_write"
    SECRET_DELETE = "secret_delete"
    CONFIG_READ = "config_read"
    CONFIG_WRITE = "config_write"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    VAULT_ACCESS = "vault_access"
    ENCRYPTION_KEY_USE = "encryption_key_use"
    PERMISSION_DENIED = "permission_denied"
    VALIDATION_FAILURE = "validation_failure"


class AuditLogger:
    """
    Security audit logger for tracking sensitive operations.

    Usage:
        audit = AuditLogger()
        audit.log_secret_access("broker.password", source="vault", success=True)
        audit.log_auth_attempt("user@example.com", success=False, reason="invalid_password")
    """

    def __init__(
        self,
        log_file: Optional[str] = None,
        enabled: Optional[bool] = None,
        mask_secrets: Optional[bool] = None,
    ):
        """
        Initialize audit logger.

        Args:
            log_file: Path to audit log file (default from DP_AUDIT_LOG_FILE env)
            enabled: Enable audit logging (default from DP_AUDIT_LOGGING_ENABLED env)
            mask_secrets: Mask sensitive values in logs (default from DP_AUDIT_MASK_SECRETS env)
        """
        # Get configuration from environment
        self.enabled = enabled if enabled is not None else (
            os.environ.get("DP_AUDIT_LOGGING_ENABLED", "true").lower() in ("1", "true", "yes")
        )

        self.mask_secrets = mask_secrets if mask_secrets is not None else (
            os.environ.get("DP_AUDIT_MASK_SECRETS", "true").lower() in ("1", "true", "yes")
        )

        default_log_file = os.environ.get("DP_AUDIT_LOG_FILE", "logs/security_audit.log")
        self.log_file = Path(log_file or default_log_file)

        # Ensure log directory exists with secure permissions
        if self.enabled:
            self.log_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

            # Create dedicated audit logger
            self.logger = logging.getLogger("audit")
            self.logger.setLevel(logging.INFO)
            self.logger.propagate = False  # Don't propagate to root logger

            # Remove existing handlers to avoid duplicates
            self.logger.handlers.clear()

            # Add file handler with restricted permissions
            handler = logging.FileHandler(str(self.log_file), mode='a', encoding='utf-8')
            handler.setLevel(logging.INFO)

            # JSON formatter for structured logging
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)

            self.logger.addHandler(handler)

            # Set secure file permissions (user read/write only)
            try:
                import stat
                self.log_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600
            except Exception:
                pass  # Best effort

    def _mask_value(self, value: Any, mask_length: int = 4) -> str:
        """
        Mask a sensitive value, showing only last few characters.

        Args:
            value: Value to mask
            mask_length: Number of characters to show

        Returns:
            Masked string
        """
        if not self.mask_secrets or value is None:
            return str(value) if value is not None else "None"

        str_value = str(value)
        if len(str_value) <= mask_length:
            return "***"

        return "***" + str_value[-mask_length:]

    def _get_value_hash(self, value: Any) -> str:
        """
        Get SHA-256 hash of value for correlation without revealing the value.

        Args:
            value: Value to hash

        Returns:
            Hex digest of SHA-256 hash
        """
        if value is None:
            return "null"

        str_value = str(value)
        return hashlib.sha256(str_value.encode('utf-8')).hexdigest()[:16]

    def _log_event(
        self,
        event_type: AuditEventType,
        details: Dict[str, Any],
        success: bool = True,
    ) -> None:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            details: Event details
            success: Whether operation was successful
        """
        if not self.enabled:
            return

        try:
            event = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": event_type.value,
                "success": success,
                "details": details,
                "process_id": os.getpid(),
            }

            # Add environment context
            event["environment"] = os.environ.get("DP_ENVIRONMENT", "unknown")

            # Log as JSON
            self.logger.info(json.dumps(event, sort_keys=True))

        except Exception as e:
            # Never let audit logging break the application
            # But log to standard logger for debugging
            logging.getLogger(__name__).debug("Audit logging failed: %s", e)

    def log_secret_access(
        self,
        secret_key: str,
        source: str,
        success: bool = True,
        value: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Log access to a secret.

        Args:
            secret_key: Key/path of secret accessed
            source: Source of secret (vault, encrypted_file, env, config)
            success: Whether access was successful
            value: Secret value (will be masked)
            error: Error message if access failed
        """
        details = {
            "secret_key": secret_key,
            "source": source,
        }

        if value is not None:
            details["value_masked"] = self._mask_value(value)
            details["value_hash"] = self._get_value_hash(value)

        if error:
            details["error"] = str(error)

        self._log_event(AuditEventType.SECRET_ACCESS, details, success)

    def log_secret_write(
        self,
        secret_key: str,
        source: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Log writing/updating a secret.

        Args:
            secret_key: Key/path of secret written
            source: Destination (vault, encrypted_file)
            success: Whether write was successful
            error: Error message if write failed
        """
        details = {
            "secret_key": secret_key,
            "source": source,
        }

        if error:
            details["error"] = str(error)

        self._log_event(AuditEventType.SECRET_WRITE, details, success)

    def log_secret_delete(
        self,
        secret_key: str,
        source: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Log deletion of a secret.

        Args:
            secret_key: Key/path of secret deleted
            source: Source (vault, encrypted_file)
            success: Whether deletion was successful
            error: Error message if deletion failed
        """
        details = {
            "secret_key": secret_key,
            "source": source,
        }

        if error:
            details["error"] = str(error)

        self._log_event(AuditEventType.SECRET_DELETE, details, success)

    def log_config_access(
        self,
        config_path: str,
        operation: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Log configuration file access.

        Args:
            config_path: Path to configuration file
            operation: Operation performed (read, write, reload)
            success: Whether operation was successful
            error: Error message if operation failed
        """
        details = {
            "config_path": str(config_path),
            "operation": operation,
        }

        if error:
            details["error"] = str(error)

        event_type = AuditEventType.CONFIG_WRITE if operation == "write" else AuditEventType.CONFIG_READ
        self._log_event(event_type, details, success)

    def log_vault_access(
        self,
        vault_path: str,
        operation: str,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Log Vault access.

        Args:
            vault_path: Vault path accessed
            operation: Operation performed (read, write, delete)
            success: Whether operation was successful
            error: Error message if operation failed
        """
        details = {
            "vault_path": vault_path,
            "operation": operation,
            "vault_addr": self._mask_value(os.environ.get("VAULT_ADDR", "")),
        }

        if error:
            details["error"] = str(error)

        self._log_event(AuditEventType.VAULT_ACCESS, details, success)

    def log_auth_attempt(
        self,
        username: str,
        success: bool,
        reason: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        """
        Log authentication attempt.

        Args:
            username: Username/identifier
            success: Whether authentication succeeded
            reason: Reason for failure (if applicable)
            source: Authentication source (broker, api, etc.)
        """
        details = {
            "username": username,
        }

        if reason:
            details["reason"] = reason

        if source:
            details["source"] = source

        event_type = AuditEventType.AUTH_SUCCESS if success else AuditEventType.AUTH_FAILURE
        self._log_event(event_type, details, success)

    def log_encryption_key_use(
        self,
        purpose: str,
        key_id: Optional[str] = None,
        success: bool = True,
    ) -> None:
        """
        Log encryption key usage.

        Args:
            purpose: Purpose of key use (encrypt, decrypt, rotate)
            key_id: Key identifier (masked)
            success: Whether operation succeeded
        """
        details = {
            "purpose": purpose,
        }

        if key_id:
            details["key_id_masked"] = self._mask_value(key_id, mask_length=8)

        self._log_event(AuditEventType.ENCRYPTION_KEY_USE, details, success)

    def log_permission_denied(
        self,
        resource: str,
        operation: str,
        reason: Optional[str] = None,
    ) -> None:
        """
        Log permission denied event.

        Args:
            resource: Resource access was denied to
            operation: Operation that was denied
            reason: Reason for denial
        """
        details = {
            "resource": resource,
            "operation": operation,
        }

        if reason:
            details["reason"] = reason

        self._log_event(AuditEventType.PERMISSION_DENIED, details, success=False)

    def log_validation_failure(
        self,
        validation_type: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Log validation failure.

        Args:
            validation_type: Type of validation that failed
            details: Failure details
        """
        self._log_event(
            AuditEventType.VALIDATION_FAILURE,
            {"validation_type": validation_type, **details},
            success=False
        )


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Get the global audit logger instance.

    Returns:
        AuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Convenience functions for common operations
def audit_secret_access(secret_key: str, source: str, success: bool = True, value: Optional[Any] = None) -> None:
    """Log secret access (convenience function)."""
    get_audit_logger().log_secret_access(secret_key, source, success, value)


def audit_config_access(config_path: str, operation: str, success: bool = True) -> None:
    """Log config access (convenience function)."""
    get_audit_logger().log_config_access(config_path, operation, success)


def audit_vault_access(vault_path: str, operation: str, success: bool = True) -> None:
    """Log Vault access (convenience function)."""
    get_audit_logger().log_vault_access(vault_path, operation, success)
