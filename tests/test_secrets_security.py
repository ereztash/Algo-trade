# -*- coding: utf-8 -*-
"""
Security tests for secrets management system.

Tests cover:
- Encryption functionality
- Secrets manager operations
- Audit logging
- Config integration
- Security best practices validation
"""
import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import modules to test
try:
    from data_plane.config.secrets_manager import SecretsManager, get_secrets_manager
    from data_plane.config.audit_logger import AuditLogger, get_audit_logger
    from data_plane.config.utils import get_config, reload_config
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


@pytest.mark.skipif(not HAS_CRYPTO, reason="cryptography not available")
class TestSecretsManager:
    """Test SecretsManager functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.secrets_file = Path(self.temp_dir) / "test_secrets.bin"
        self.encryption_key = SecretsManager.generate_key()

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_key_generation(self):
        """Test encryption key generation."""
        key1 = SecretsManager.generate_key()
        key2 = SecretsManager.generate_key()

        # Keys should be different
        assert key1 != key2

        # Keys should be valid base64
        import base64
        try:
            base64.urlsafe_b64decode(key1)
            base64.urlsafe_b64decode(key2)
        except Exception as e:
            pytest.fail(f"Invalid base64 key: {e}")

    def test_secrets_manager_init(self):
        """Test SecretsManager initialization."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        assert manager.secrets_file == self.secrets_file
        assert manager.cipher is not None

    def test_set_and_get_secret(self):
        """Test setting and getting secrets."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Set a secret
        manager.set_secret("test.password", "super-secret-123")

        # Get the secret
        value = manager.get_secret("test.password")
        assert value == "super-secret-123"

    def test_nested_keys(self):
        """Test nested key support."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Set nested secrets
        manager.set_secret("broker.host", "localhost")
        manager.set_secret("broker.port", 7497)
        manager.set_secret("broker.credentials.username", "trader")
        manager.set_secret("broker.credentials.password", "secret")

        # Get nested secrets
        assert manager.get_secret("broker.host") == "localhost"
        assert manager.get_secret("broker.port") == 7497
        assert manager.get_secret("broker.credentials.username") == "trader"
        assert manager.get_secret("broker.credentials.password") == "secret"

    def test_get_all_secrets(self):
        """Test getting all secrets."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Set multiple secrets
        manager.set_secret("key1", "value1")
        manager.set_secret("key2", "value2")
        manager.set_secret("nested.key3", "value3")

        # Get all secrets
        all_secrets = manager.get_all_secrets()
        assert "key1" in all_secrets
        assert "key2" in all_secrets
        assert "nested" in all_secrets
        assert all_secrets["key1"] == "value1"
        assert all_secrets["nested"]["key3"] == "value3"

    def test_delete_secret(self):
        """Test deleting secrets."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Set and delete
        manager.set_secret("temp.secret", "delete-me")
        assert manager.get_secret("temp.secret") == "delete-me"

        result = manager.delete_secret("temp.secret")
        assert result is True
        assert manager.get_secret("temp.secret") is None

        # Delete non-existent
        result = manager.delete_secret("nonexistent")
        assert result is False

    def test_list_keys(self):
        """Test listing secret keys."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Set multiple secrets
        manager.set_secret("key1", "value1")
        manager.set_secret("key2", "value2")
        manager.set_secret("nested.key3", "value3")
        manager.set_secret("nested.deep.key4", "value4")

        # List keys
        keys = manager.list_keys()
        assert "key1" in keys
        assert "key2" in keys
        assert "nested.key3" in keys
        assert "nested.deep.key4" in keys

    def test_invalid_encryption_key(self):
        """Test handling of invalid encryption key."""
        with pytest.raises(ValueError, match="Invalid encryption key"):
            SecretsManager(
                secrets_file=str(self.secrets_file),
                encryption_key="invalid-key"
            )

    def test_corrupted_file(self):
        """Test handling of corrupted secrets file."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Write corrupted data
        self.secrets_file.write_bytes(b"corrupted data")

        # Should raise ValueError
        with pytest.raises(ValueError, match="Invalid encryption key or corrupted"):
            manager.get_secret("any.key")

    def test_file_permissions(self):
        """Test that secrets file has secure permissions."""
        import stat

        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Set a secret to create the file
        manager.set_secret("test", "value")

        # Check file permissions
        file_stat = self.secrets_file.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)

        # Should be 0600 (user read/write only)
        expected_mode = stat.S_IRUSR | stat.S_IWUSR
        assert file_mode == expected_mode, f"File mode {oct(file_mode)} != {oct(expected_mode)}"

    def test_key_rotation(self):
        """Test encryption key rotation."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Set secrets
        manager.set_secret("key1", "value1")
        manager.set_secret("key2", "value2")

        # Generate new key
        new_key = SecretsManager.generate_key()

        # Rotate key
        manager.rotate_key(new_key)

        # Should still be able to read secrets
        assert manager.get_secret("key1") == "value1"
        assert manager.get_secret("key2") == "value2"

        # New manager with new key should work
        new_manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=new_key
        )
        assert new_manager.get_secret("key1") == "value1"

        # Old key should not work
        with pytest.raises(ValueError):
            old_manager = SecretsManager(
                secrets_file=str(self.secrets_file),
                encryption_key=self.encryption_key
            )
            old_manager.get_secret("key1")

    def test_validate(self):
        """Test secrets file validation."""
        manager = SecretsManager(
            secrets_file=str(self.secrets_file),
            encryption_key=self.encryption_key
        )

        # Empty file should be valid
        assert manager.validate() is True

        # File with secrets should be valid
        manager.set_secret("test", "value")
        assert manager.validate() is True

        # Corrupted file should be invalid
        self.secrets_file.write_bytes(b"corrupted")
        assert manager.validate() is False


class TestAuditLogger:
    """Test AuditLogger functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "test_audit.log"

    def teardown_method(self):
        """Cleanup test environment."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_audit_logger_init(self):
        """Test AuditLogger initialization."""
        logger = AuditLogger(
            log_file=str(self.log_file),
            enabled=True,
            mask_secrets=True
        )

        assert logger.enabled is True
        assert logger.mask_secrets is True
        assert logger.log_file == self.log_file

    def test_log_secret_access(self):
        """Test logging secret access."""
        logger = AuditLogger(
            log_file=str(self.log_file),
            enabled=True,
            mask_secrets=True
        )

        # Log secret access
        logger.log_secret_access(
            secret_key="broker.password",
            source="vault",
            success=True,
            value="super-secret-password"
        )

        # Read log file
        log_content = self.log_file.read_text()
        log_entry = json.loads(log_content.strip())

        # Verify log entry
        assert log_entry["event_type"] == "secret_access"
        assert log_entry["success"] is True
        assert log_entry["details"]["secret_key"] == "broker.password"
        assert log_entry["details"]["source"] == "vault"
        assert "***" in log_entry["details"]["value_masked"]  # Should be masked
        assert "value_hash" in log_entry["details"]

    def test_secret_masking(self):
        """Test secret value masking."""
        logger = AuditLogger(
            log_file=str(self.log_file),
            enabled=True,
            mask_secrets=True
        )

        test_cases = [
            ("short", "***"),
            ("password123", "***d123"),
            ("super-secret-password", "***word"),
        ]

        for value, expected in test_cases:
            masked = logger._mask_value(value)
            assert masked == expected, f"Expected {expected}, got {masked}"

    def test_disabled_logging(self):
        """Test that disabled logger doesn't create logs."""
        logger = AuditLogger(
            log_file=str(self.log_file),
            enabled=False
        )

        # Log secret access
        logger.log_secret_access("key", "source", True)

        # Log file should not exist
        assert not self.log_file.exists()

    def test_log_format(self):
        """Test audit log JSON format."""
        logger = AuditLogger(
            log_file=str(self.log_file),
            enabled=True
        )

        # Log various events
        logger.log_secret_access("key1", "vault", True)
        logger.log_config_access("/path/to/config", "read", True)
        logger.log_vault_access("secret/path", "read", True)

        # Read all log entries
        log_lines = self.log_file.read_text().strip().split('\n')
        assert len(log_lines) == 3

        # Each line should be valid JSON
        for line in log_lines:
            entry = json.loads(line)
            assert "timestamp" in entry
            assert "event_type" in entry
            assert "success" in entry
            assert "details" in entry
            assert "process_id" in entry

    def test_file_permissions(self):
        """Test that audit log has secure permissions."""
        import stat

        logger = AuditLogger(
            log_file=str(self.log_file),
            enabled=True
        )

        # Log something to create file
        logger.log_secret_access("key", "source", True)

        # Check file permissions
        file_stat = self.log_file.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)

        # Should be 0600 (user read/write only)
        expected_mode = stat.S_IRUSR | stat.S_IWUSR
        assert file_mode == expected_mode


class TestConfigIntegration:
    """Test integration of secrets management with config system."""

    def test_env_var_priority(self):
        """Test that environment variables have highest priority."""
        with patch.dict(os.environ, {
            "DP_BROKER__HOST": "env-host",
            "DP_BROKER__PORT": "9999"
        }):
            reload_config()
            config = get_config()
            assert config.broker.host == "env-host"
            assert config.broker.port == 9999

    def test_sensitive_key_detection(self):
        """Test that sensitive keys are detected in environment variables."""
        sensitive_keys = [
            "DP_BROKER__PASSWORD",
            "DP_BROKER__TOKEN",
            "DP_SECRETS_ENCRYPTION_KEY",
            "VAULT_TOKEN"
        ]

        for key in sensitive_keys:
            # Should match sensitive pattern
            assert any(sk in key.lower() for sk in ["password", "token", "key", "secret"])

    def test_no_hardcoded_secrets(self):
        """Test that no secrets are hard-coded in the codebase."""
        import re

        # Patterns that might indicate hard-coded secrets
        secret_patterns = [
            r'password\s*=\s*["\'](?!None|null|<|{{)[^"\']{8,}["\']',
            r'api_key\s*=\s*["\'][^"\']{16,}["\']',
            r'token\s*=\s*["\'][^"\']{16,}["\']',
            r'secret\s*=\s*["\'][^"\']{16,}["\']',
        ]

        files_to_check = [
            "data_plane/config/utils.py",
            "algo_trade/core/execution/IBKR_handler.py",
        ]

        for file_path in files_to_check:
            full_path = Path(__file__).parent.parent / file_path
            if not full_path.exists():
                continue

            content = full_path.read_text()
            for pattern in secret_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                assert not matches, f"Potential hard-coded secret in {file_path}: {matches}"


class TestSecurityBestPractices:
    """Test compliance with security best practices."""

    def test_gitignore_secrets(self):
        """Test that .gitignore excludes secret files."""
        gitignore_path = Path(__file__).parent.parent / ".gitignore"
        assert gitignore_path.exists(), ".gitignore not found"

        gitignore_content = gitignore_path.read_text()

        # Should exclude these patterns
        required_patterns = [
            ".env",
            "secrets.yaml",
            ".secrets/",
        ]

        for pattern in required_patterns:
            assert pattern in gitignore_content, f"{pattern} not in .gitignore"

    def test_env_example_exists(self):
        """Test that .env.example template exists."""
        env_example = Path(__file__).parent.parent / ".env.example"
        assert env_example.exists(), ".env.example not found"

        content = env_example.read_text()

        # Should contain documentation
        assert "VAULT_ADDR" in content
        assert "DP_SECRETS_ENCRYPTION_KEY" in content
        assert "DP_BROKER__PASSWORD" in content

        # Should NOT contain actual secrets
        assert "your-vault-token-here" in content or "your-" in content

    def test_secure_defaults(self):
        """Test that config has secure defaults."""
        config = get_config()

        # Paper trading should be default
        assert config.broker.paper is True

        # Execution should be disabled by default
        assert config.execution.enabled is False

    def test_documentation_exists(self):
        """Test that security documentation exists."""
        docs_path = Path(__file__).parent.parent / "docs" / "SECRETS_MANAGEMENT.md"
        assert docs_path.exists(), "SECRETS_MANAGEMENT.md not found"

        content = docs_path.read_text()

        # Should cover key topics
        required_topics = [
            "Vault",
            "encryption",
            "audit",
            "best practices",
            "rotation"
        ]

        content_lower = content.lower()
        for topic in required_topics:
            assert topic in content_lower, f"Missing documentation for: {topic}"


@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests."""

    def test_encrypted_secrets_flow(self):
        """Test complete encrypted secrets workflow."""
        if not HAS_CRYPTO:
            pytest.skip("cryptography not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            secrets_file = Path(temp_dir) / "secrets.bin"
            key = SecretsManager.generate_key()

            # Create manager and add secrets
            manager = SecretsManager(
                secrets_file=str(secrets_file),
                encryption_key=key
            )

            manager.set_secret("broker.host", "localhost")
            manager.set_secret("broker.port", 7497)
            manager.set_secret("broker.password", "secret123")

            # Verify persistence
            manager2 = SecretsManager(
                secrets_file=str(secrets_file),
                encryption_key=key
            )

            assert manager2.get_secret("broker.host") == "localhost"
            assert manager2.get_secret("broker.port") == 7497
            assert manager2.get_secret("broker.password") == "secret123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
