# -*- coding: utf-8 -*-
"""
data_plane.config.secrets_manager — Encrypted local secrets management.

Provides secure encrypted file-based secrets storage using Fernet (symmetric encryption).
This is an alternative to Vault for local/development environments or when Vault is not available.

Key Features:
- Fernet symmetric encryption (AES-128 CBC with HMAC for authentication)
- JSON-based secret storage with nested key support
- Automatic key generation and validation
- Secure file permissions (0600)
- Integration with existing config system
- CLI utility for secrets management

Security Considerations:
- Encryption key must be stored securely (environment variable, not in code)
- File permissions are set to user-read-only (chmod 600)
- Key rotation requires re-encryption of all secrets
- Not suitable for high-security production use (use Vault instead)
"""
from __future__ import annotations

import os
import json
import stat
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import cryptography
try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAS_CRYPTOGRAPHY = True
except ImportError:
    _HAS_CRYPTOGRAPHY = False
    logger.warning("cryptography not available - encrypted secrets disabled. Install with: pip install cryptography")


class SecretsManager:
    """
    Manages encrypted secrets stored in a local file.

    Usage:
        # Initialize with encryption key from environment
        manager = SecretsManager()

        # Store a secret
        manager.set_secret("broker.password", "my-secret-password")

        # Retrieve a secret
        password = manager.get_secret("broker.password")

        # Get all secrets (for config merging)
        all_secrets = manager.get_all_secrets()
    """

    def __init__(
        self,
        secrets_file: Optional[str] = None,
        encryption_key: Optional[str] = None,
    ):
        """
        Initialize secrets manager.

        Args:
            secrets_file: Path to encrypted secrets file (default from DP_ENCRYPTED_SECRETS_FILE env)
            encryption_key: Base64-encoded Fernet key (default from DP_SECRETS_ENCRYPTION_KEY env)
        """
        if not _HAS_CRYPTOGRAPHY:
            raise ImportError(
                "cryptography library required for encrypted secrets. "
                "Install with: pip install cryptography"
            )

        # Get secrets file path
        default_file = os.environ.get("DP_ENCRYPTED_SECRETS_FILE", ".secrets/encrypted_secrets.bin")
        self.secrets_file = Path(secrets_file or default_file)

        # Get encryption key
        key_str = encryption_key or os.environ.get("DP_SECRETS_ENCRYPTION_KEY")
        if not key_str:
            raise ValueError(
                "Encryption key required. Set DP_SECRETS_ENCRYPTION_KEY environment variable or pass encryption_key parameter. "
                "Generate a key with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )

        # Initialize Fernet cipher
        try:
            self.cipher = Fernet(key_str.encode() if isinstance(key_str, str) else key_str)
        except Exception as e:
            raise ValueError(f"Invalid encryption key format: {e}. Must be a valid base64-encoded Fernet key.")

        # Ensure secrets directory exists with secure permissions
        self.secrets_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        logger.debug("SecretsManager initialized with file: %s", self.secrets_file)

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded encryption key as string
        """
        if not _HAS_CRYPTOGRAPHY:
            raise ImportError("cryptography library required")
        return Fernet.generate_key().decode()

    def _read_encrypted_file(self) -> Dict[str, Any]:
        """Read and decrypt secrets file."""
        if not self.secrets_file.exists():
            logger.debug("Secrets file does not exist: %s", self.secrets_file)
            return {}

        try:
            # Read encrypted data
            encrypted_data = self.secrets_file.read_bytes()

            # Decrypt
            decrypted_data = self.cipher.decrypt(encrypted_data)

            # Parse JSON
            secrets = json.loads(decrypted_data.decode('utf-8'))

            if not isinstance(secrets, dict):
                logger.error("Secrets file contains invalid data (not a dict)")
                return {}

            logger.debug("Successfully read %d secrets from file", len(secrets))
            return secrets

        except InvalidToken:
            logger.error("Failed to decrypt secrets file - invalid key or corrupted file")
            raise ValueError("Invalid encryption key or corrupted secrets file")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse secrets file JSON: %s", e)
            raise ValueError(f"Corrupted secrets file - invalid JSON: {e}")
        except Exception as e:
            logger.error("Failed to read secrets file: %s", e)
            raise

    def _write_encrypted_file(self, secrets: Dict[str, Any]) -> None:
        """Encrypt and write secrets to file."""
        try:
            # Convert to JSON
            json_data = json.dumps(secrets, indent=2, sort_keys=True)

            # Encrypt
            encrypted_data = self.cipher.encrypt(json_data.encode('utf-8'))

            # Write to file
            self.secrets_file.write_bytes(encrypted_data)

            # Set secure file permissions (user read/write only)
            self.secrets_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0600

            logger.debug("Successfully wrote %d secrets to file", len(secrets))

        except Exception as e:
            logger.error("Failed to write secrets file: %s", e)
            raise

    def get_secret(self, key: str, default: Any = None) -> Any:
        """
        Get a secret value by key.

        Supports nested keys with dot notation (e.g., "broker.password").

        Args:
            key: Secret key (supports dot notation for nested keys)
            default: Default value if key not found

        Returns:
            Secret value or default
        """
        try:
            secrets = self._read_encrypted_file()

            # Handle nested keys
            parts = key.split('.')
            value = secrets
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    logger.debug("Secret key not found: %s", key)
                    return default

            logger.debug("Retrieved secret: %s", key)
            return value

        except Exception as e:
            logger.error("Failed to get secret %s: %s", key, e)
            return default

    def set_secret(self, key: str, value: Any) -> None:
        """
        Set a secret value.

        Supports nested keys with dot notation (e.g., "broker.password").

        Args:
            key: Secret key (supports dot notation for nested keys)
            value: Secret value (must be JSON-serializable)
        """
        try:
            # Read existing secrets
            secrets = self._read_encrypted_file()

            # Handle nested keys
            parts = key.split('.')
            current = secrets
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    raise ValueError(f"Cannot set nested key - {part} is not a dict")
                current = current[part]

            # Set the value
            current[parts[-1]] = value

            # Write back
            self._write_encrypted_file(secrets)

            logger.info("Secret set successfully: %s", key)

        except Exception as e:
            logger.error("Failed to set secret %s: %s", key, e)
            raise

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret.

        Args:
            key: Secret key to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            secrets = self._read_encrypted_file()

            # Handle nested keys
            parts = key.split('.')
            current = secrets
            for part in parts[:-1]:
                if not isinstance(current, dict) or part not in current:
                    logger.debug("Secret key not found: %s", key)
                    return False
                current = current[part]

            # Delete the key
            if isinstance(current, dict) and parts[-1] in current:
                del current[parts[-1]]
                self._write_encrypted_file(secrets)
                logger.info("Secret deleted successfully: %s", key)
                return True
            else:
                logger.debug("Secret key not found: %s", key)
                return False

        except Exception as e:
            logger.error("Failed to delete secret %s: %s", key, e)
            raise

    def get_all_secrets(self) -> Dict[str, Any]:
        """
        Get all secrets as a dictionary.

        Returns:
            Dictionary of all secrets
        """
        try:
            return self._read_encrypted_file()
        except Exception as e:
            logger.error("Failed to get all secrets: %s", e)
            return {}

    def list_keys(self) -> list[str]:
        """
        List all secret keys.

        Returns:
            List of secret keys (dot notation for nested keys)
        """
        def _flatten_keys(d: Dict[str, Any], prefix: str = "") -> list[str]:
            keys = []
            for k, v in d.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys.extend(_flatten_keys(v, full_key))
                else:
                    keys.append(full_key)
            return keys

        try:
            secrets = self._read_encrypted_file()
            return _flatten_keys(secrets)
        except Exception as e:
            logger.error("Failed to list keys: %s", e)
            return []

    def rotate_key(self, new_key: str) -> None:
        """
        Rotate encryption key by re-encrypting all secrets with new key.

        Args:
            new_key: New base64-encoded Fernet key
        """
        try:
            # Read secrets with old key
            secrets = self._read_encrypted_file()

            # Create new cipher with new key
            new_cipher = Fernet(new_key.encode() if isinstance(new_key, str) else new_key)

            # Update cipher
            old_cipher = self.cipher
            self.cipher = new_cipher

            try:
                # Write secrets with new key
                self._write_encrypted_file(secrets)
                logger.info("Successfully rotated encryption key")
            except Exception as e:
                # Rollback on failure
                self.cipher = old_cipher
                raise RuntimeError(f"Failed to rotate key: {e}")

        except Exception as e:
            logger.error("Key rotation failed: %s", e)
            raise

    def validate(self) -> bool:
        """
        Validate that secrets file can be read and decrypted.

        Returns:
            True if valid, False otherwise
        """
        try:
            if not self.secrets_file.exists():
                logger.debug("Secrets file does not exist (valid for empty state)")
                return True

            self._read_encrypted_file()
            logger.debug("Secrets file validation passed")
            return True

        except Exception as e:
            logger.error("Secrets file validation failed: %s", e)
            return False


def get_secrets_manager(
    secrets_file: Optional[str] = None,
    encryption_key: Optional[str] = None,
) -> Optional[SecretsManager]:
    """
    Get a SecretsManager instance if encrypted secrets are enabled.

    Returns:
        SecretsManager instance or None if disabled/unavailable
    """
    # Check if encrypted secrets are enabled
    if os.environ.get("DP_USE_ENCRYPTED_SECRETS", "0") != "1":
        logger.debug("Encrypted secrets disabled (DP_USE_ENCRYPTED_SECRETS != 1)")
        return None

    if not _HAS_CRYPTOGRAPHY:
        logger.warning("Encrypted secrets enabled but cryptography not available")
        return None

    try:
        return SecretsManager(secrets_file=secrets_file, encryption_key=encryption_key)
    except Exception as e:
        logger.error("Failed to initialize SecretsManager: %s", e)
        return None


# CLI utility
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Manage encrypted secrets")
    parser.add_argument("action", choices=["generate-key", "set", "get", "delete", "list", "validate", "rotate-key"],
                       help="Action to perform")
    parser.add_argument("key", nargs="?", help="Secret key (for set/get/delete)")
    parser.add_argument("value", nargs="?", help="Secret value (for set)")
    parser.add_argument("--new-key", help="New encryption key (for rotate-key)")
    parser.add_argument("--secrets-file", help="Path to secrets file")
    parser.add_argument("--encryption-key", help="Encryption key (or set DP_SECRETS_ENCRYPTION_KEY)")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    try:
        if args.action == "generate-key":
            if not _HAS_CRYPTOGRAPHY:
                print("ERROR: cryptography library not installed", file=sys.stderr)
                sys.exit(1)
            key = SecretsManager.generate_key()
            print(f"Generated encryption key:")
            print(key)
            print("\nAdd this to your .env file:")
            print(f"DP_SECRETS_ENCRYPTION_KEY={key}")
            sys.exit(0)

        # All other actions require a manager instance
        manager = SecretsManager(
            secrets_file=args.secrets_file,
            encryption_key=args.encryption_key
        )

        if args.action == "set":
            if not args.key or args.value is None:
                print("ERROR: set requires key and value arguments", file=sys.stderr)
                sys.exit(1)
            manager.set_secret(args.key, args.value)
            print(f"✓ Secret '{args.key}' set successfully")

        elif args.action == "get":
            if not args.key:
                print("ERROR: get requires key argument", file=sys.stderr)
                sys.exit(1)
            value = manager.get_secret(args.key)
            if value is None:
                print(f"Secret '{args.key}' not found", file=sys.stderr)
                sys.exit(1)
            print(value)

        elif args.action == "delete":
            if not args.key:
                print("ERROR: delete requires key argument", file=sys.stderr)
                sys.exit(1)
            if manager.delete_secret(args.key):
                print(f"✓ Secret '{args.key}' deleted successfully")
            else:
                print(f"Secret '{args.key}' not found", file=sys.stderr)
                sys.exit(1)

        elif args.action == "list":
            keys = manager.list_keys()
            if keys:
                print("Stored secrets:")
                for key in sorted(keys):
                    print(f"  - {key}")
            else:
                print("No secrets stored")

        elif args.action == "validate":
            if manager.validate():
                print("✓ Secrets file is valid")
            else:
                print("✗ Secrets file validation failed", file=sys.stderr)
                sys.exit(1)

        elif args.action == "rotate-key":
            if not args.new_key:
                print("ERROR: rotate-key requires --new-key argument", file=sys.stderr)
                sys.exit(1)
            manager.rotate_key(args.new_key)
            print("✓ Encryption key rotated successfully")
            print("\nUpdate your .env file with the new key:")
            print(f"DP_SECRETS_ENCRYPTION_KEY={args.new_key}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
