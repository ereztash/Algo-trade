# -*- coding: utf-8 -*-
"""
secrets_manager.py
מנהל הצפנה ופענוח של סודות (secrets) במנוחה (at-rest encryption)

מאפיינים:
- Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256)
- Key derivation from master password using PBKDF2
- Support for multiple encryption keys (key rotation)
- Thread-safe operations
- Audit logging
"""

import os
import json
import base64
import logging
import threading
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from datetime import datetime, timedelta

try:
    from cryptography.fernet import Fernet, InvalidToken, MultiFernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
    from cryptography.hazmat.backends import default_backend
except ImportError as e:
    raise ImportError(
        "cryptography library required. Install with: pip install cryptography"
    ) from e

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """Raised when encryption fails"""
    pass


class DecryptionError(Exception):
    """Raised when decryption fails"""
    pass


class SecretsManager:
    """
    Manages encryption/decryption of secrets at rest.

    Uses Fernet (symmetric encryption) with support for key rotation.
    All secrets are encrypted with AES-128 and authenticated with HMAC-SHA256.

    Example:
        >>> manager = SecretsManager()
        >>> encrypted = manager.encrypt("my-api-key-12345")
        >>> decrypted = manager.decrypt(encrypted)
        >>> assert decrypted == "my-api-key-12345"

    Example with file:
        >>> manager = SecretsManager()
        >>> secrets = {"IBKR_PASSWORD": "super-secret", "API_KEY": "xyz"}
        >>> manager.encrypt_secrets_file(secrets, "secrets.enc")
        >>> loaded = manager.decrypt_secrets_file("secrets.enc")
        >>> assert loaded == secrets
    """

    def __init__(
        self,
        master_key: Optional[str] = None,
        key_rotation_enabled: bool = True,
        key_file: Optional[str] = None,
    ):
        """
        Initialize the secrets manager.

        Args:
            master_key: Master encryption key (Fernet key). If None, loads from env
                       MASTER_ENCRYPTION_KEY or generates a new one.
            key_rotation_enabled: Enable support for key rotation (MultiFernet)
            key_file: Path to file containing encryption keys (one per line)
        """
        self._lock = threading.Lock()
        self._key_rotation_enabled = key_rotation_enabled
        self._key_file = Path(key_file) if key_file else None

        # Load or generate keys
        self._keys: List[bytes] = self._load_keys(master_key)

        # Create Fernet instances
        if key_rotation_enabled and len(self._keys) > 1:
            # MultiFernet for key rotation support
            fernets = [Fernet(key) for key in self._keys]
            self._fernet = MultiFernet(fernets)
            logger.info(f"Initialized MultiFernet with {len(self._keys)} keys")
        elif self._keys:
            # Single Fernet
            self._fernet = Fernet(self._keys[0])
            logger.info("Initialized Fernet with single key")
        else:
            raise EncryptionError("No encryption keys available")

    def _load_keys(self, master_key: Optional[str] = None) -> List[bytes]:
        """Load encryption keys from various sources."""
        keys: List[bytes] = []

        # 1. Try provided master key
        if master_key:
            try:
                key_bytes = master_key.encode() if isinstance(master_key, str) else master_key
                # Validate it's a valid Fernet key
                Fernet(key_bytes)
                keys.append(key_bytes)
                logger.debug("Loaded master key from parameter")
            except Exception as e:
                logger.warning(f"Invalid master key provided: {e}")

        # 2. Try environment variable
        env_key = os.environ.get("MASTER_ENCRYPTION_KEY")
        if env_key and env_key not in [k.decode() for k in keys]:
            try:
                key_bytes = env_key.encode()
                Fernet(key_bytes)
                keys.append(key_bytes)
                logger.debug("Loaded master key from MASTER_ENCRYPTION_KEY env var")
            except Exception as e:
                logger.warning(f"Invalid MASTER_ENCRYPTION_KEY in environment: {e}")

        # 3. Try key file (for rotation)
        if self._key_file and self._key_file.exists():
            try:
                with open(self._key_file, 'r') as f:
                    for line in f:
                        key_str = line.strip()
                        if key_str and key_str not in [k.decode() for k in keys]:
                            try:
                                key_bytes = key_str.encode()
                                Fernet(key_bytes)
                                keys.append(key_bytes)
                            except Exception:
                                continue
                logger.info(f"Loaded {len(keys)} keys from {self._key_file}")
            except Exception as e:
                logger.warning(f"Failed to load keys from {self._key_file}: {e}")

        # 4. Generate new key if none found (dev mode only!)
        if not keys:
            if os.environ.get("ENVIRONMENT", "development") == "development":
                logger.warning(
                    "No encryption key found! Generating new key. "
                    "IMPORTANT: This is OK for development but NOT for production!"
                )
                new_key = Fernet.generate_key()
                keys.append(new_key)
                logger.warning(f"Generated key: {new_key.decode()}")
                logger.warning("Save this key to MASTER_ENCRYPTION_KEY environment variable!")
            else:
                raise EncryptionError(
                    "No encryption key found and not in development mode. "
                    "Set MASTER_ENCRYPTION_KEY environment variable."
                )

        return keys

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded Fernet key as string

        Example:
            >>> key = SecretsManager.generate_key()
            >>> print(f"Save this key: {key}")
        """
        return Fernet.generate_key().decode()

    @staticmethod
    def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> tuple[str, str]:
        """
        Derive a Fernet key from a password using PBKDF2.

        Args:
            password: Password to derive key from
            salt: Salt for key derivation (generated if None)

        Returns:
            Tuple of (fernet_key, salt_base64)

        Example:
            >>> key, salt = SecretsManager.derive_key_from_password("my-secure-password")
            >>> # Store salt somewhere safe, you'll need it to recreate the key
        """
        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        salt_b64 = base64.b64encode(salt).decode()

        return key.decode(), salt_b64

    def encrypt(self, plaintext: Union[str, bytes]) -> str:
        """
        Encrypt a string or bytes.

        Args:
            plaintext: Data to encrypt

        Returns:
            Base64-encoded encrypted data (URL-safe)

        Raises:
            EncryptionError: If encryption fails
        """
        with self._lock:
            try:
                if isinstance(plaintext, str):
                    plaintext = plaintext.encode('utf-8')

                encrypted = self._fernet.encrypt(plaintext)
                return encrypted.decode('utf-8')
            except Exception as e:
                logger.error(f"Encryption failed: {e}")
                raise EncryptionError(f"Failed to encrypt data: {e}") from e

    def decrypt(self, ciphertext: Union[str, bytes]) -> str:
        """
        Decrypt encrypted data.

        Args:
            ciphertext: Encrypted data (base64-encoded)

        Returns:
            Decrypted plaintext as string

        Raises:
            DecryptionError: If decryption fails (wrong key, corrupted data, etc.)
        """
        with self._lock:
            try:
                if isinstance(ciphertext, str):
                    ciphertext = ciphertext.encode('utf-8')

                decrypted = self._fernet.decrypt(ciphertext)
                return decrypted.decode('utf-8')
            except InvalidToken:
                logger.error("Decryption failed: Invalid token (wrong key or corrupted data)")
                raise DecryptionError("Invalid encryption token - wrong key or corrupted data")
            except Exception as e:
                logger.error(f"Decryption failed: {e}")
                raise DecryptionError(f"Failed to decrypt data: {e}") from e

    def encrypt_dict(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Encrypt all values in a dictionary.

        Args:
            data: Dictionary with plaintext values

        Returns:
            Dictionary with encrypted values
        """
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, (str, bytes)):
                encrypted[key] = self.encrypt(value)
            else:
                # Convert to JSON first
                encrypted[key] = self.encrypt(json.dumps(value))
        return encrypted

    def decrypt_dict(self, data: Dict[str, str], parse_json: bool = False) -> Dict[str, Any]:
        """
        Decrypt all values in a dictionary.

        Args:
            data: Dictionary with encrypted values
            parse_json: Try to parse values as JSON after decryption

        Returns:
            Dictionary with decrypted values
        """
        decrypted = {}
        for key, value in data.items():
            plaintext = self.decrypt(value)
            if parse_json:
                try:
                    decrypted[key] = json.loads(plaintext)
                except json.JSONDecodeError:
                    decrypted[key] = plaintext
            else:
                decrypted[key] = plaintext
        return decrypted

    def encrypt_secrets_file(
        self,
        secrets: Dict[str, Any],
        output_file: Union[str, Path],
        include_metadata: bool = True
    ) -> None:
        """
        Encrypt secrets and save to file.

        Args:
            secrets: Dictionary of secrets to encrypt
            output_file: Path to output encrypted file
            include_metadata: Include metadata (timestamp, version, etc.)

        Example:
            >>> secrets = {"API_KEY": "xyz", "PASSWORD": "abc"}
            >>> manager.encrypt_secrets_file(secrets, "secrets.enc")
        """
        output_path = Path(output_file)

        # Prepare data
        data = {
            "secrets": self.encrypt_dict(secrets)
        }

        if include_metadata:
            data["metadata"] = {
                "encrypted_at": datetime.utcnow().isoformat(),
                "version": "1.0",
                "key_count": len(self._keys),
            }

        # Write to file
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Set restrictive permissions (owner read/write only)
            os.chmod(output_path, 0o600)

            logger.info(f"Encrypted {len(secrets)} secrets to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write encrypted file: {e}")
            raise EncryptionError(f"Failed to write encrypted file: {e}") from e

    def decrypt_secrets_file(self, input_file: Union[str, Path]) -> Dict[str, Any]:
        """
        Load and decrypt secrets from file.

        Args:
            input_file: Path to encrypted secrets file

        Returns:
            Dictionary of decrypted secrets

        Raises:
            DecryptionError: If file cannot be decrypted
        """
        input_path = Path(input_file)

        if not input_path.exists():
            raise DecryptionError(f"Encrypted file not found: {input_path}")

        try:
            with open(input_path, 'r') as f:
                data = json.load(f)

            if "secrets" not in data:
                raise DecryptionError("Invalid encrypted file format - missing 'secrets' key")

            secrets = self.decrypt_dict(data["secrets"], parse_json=True)

            logger.info(f"Decrypted {len(secrets)} secrets from {input_path}")
            return secrets
        except json.JSONDecodeError as e:
            raise DecryptionError(f"Invalid JSON in encrypted file: {e}") from e
        except Exception as e:
            logger.error(f"Failed to decrypt file: {e}")
            raise DecryptionError(f"Failed to decrypt file: {e}") from e

    def rotate_key(self, new_key: Optional[str] = None) -> str:
        """
        Add a new encryption key for rotation.

        Args:
            new_key: New Fernet key (generated if None)

        Returns:
            The new key (for backup)

        Note:
            - Old keys are retained for decryption
            - New encryptions use the new key
            - Call re-encrypt_secrets() to update existing encrypted data
        """
        if new_key is None:
            new_key = self.generate_key()

        new_key_bytes = new_key.encode()

        # Validate the new key
        try:
            Fernet(new_key_bytes)
        except Exception as e:
            raise EncryptionError(f"Invalid new key: {e}") from e

        with self._lock:
            # Add new key to the front (highest priority)
            self._keys.insert(0, new_key_bytes)

            # Recreate MultiFernet with new keys
            if self._key_rotation_enabled:
                fernets = [Fernet(key) for key in self._keys]
                self._fernet = MultiFernet(fernets)
            else:
                self._fernet = Fernet(self._keys[0])

            # Save to key file if configured
            if self._key_file:
                try:
                    with open(self._key_file, 'w') as f:
                        for key in self._keys:
                            f.write(key.decode() + '\n')
                    os.chmod(self._key_file, 0o600)
                    logger.info(f"Saved {len(self._keys)} keys to {self._key_file}")
                except Exception as e:
                    logger.error(f"Failed to save keys: {e}")

            logger.info(f"Key rotation complete. Total keys: {len(self._keys)}")
            return new_key


# =============================================================================
# Convenience Functions
# =============================================================================

def get_secrets_manager(**kwargs) -> SecretsManager:
    """
    Get a singleton instance of SecretsManager.

    Returns:
        Shared SecretsManager instance
    """
    global _secrets_manager_instance
    if '_secrets_manager_instance' not in globals():
        _secrets_manager_instance = SecretsManager(**kwargs)
    return _secrets_manager_instance


# =============================================================================
# CLI Tool for Key Management
# =============================================================================

if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Secrets encryption utility")
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Generate key command
    gen_parser = subparsers.add_parser('generate-key', help='Generate a new Fernet key')

    # Encrypt command
    enc_parser = subparsers.add_parser('encrypt', help='Encrypt a value')
    enc_parser.add_argument('value', help='Value to encrypt')
    enc_parser.add_argument('--key', help='Encryption key (uses MASTER_ENCRYPTION_KEY if not provided)')

    # Decrypt command
    dec_parser = subparsers.add_parser('decrypt', help='Decrypt a value')
    dec_parser.add_argument('value', help='Encrypted value to decrypt')
    dec_parser.add_argument('--key', help='Decryption key (uses MASTER_ENCRYPTION_KEY if not provided)')

    # Encrypt file command
    enc_file_parser = subparsers.add_parser('encrypt-file', help='Encrypt a secrets file')
    enc_file_parser.add_argument('input', help='Input JSON file with secrets')
    enc_file_parser.add_argument('output', help='Output encrypted file')
    enc_file_parser.add_argument('--key', help='Encryption key')

    # Decrypt file command
    dec_file_parser = subparsers.add_parser('decrypt-file', help='Decrypt a secrets file')
    dec_file_parser.add_argument('input', help='Input encrypted file')
    dec_file_parser.add_argument('--key', help='Decryption key')

    args = parser.parse_args()

    if args.command == 'generate-key':
        key = SecretsManager.generate_key()
        print(f"Generated Fernet key:")
        print(key)
        print("\nSave this key securely! Set as MASTER_ENCRYPTION_KEY environment variable.")

    elif args.command == 'encrypt':
        manager = SecretsManager(master_key=args.key)
        encrypted = manager.encrypt(args.value)
        print(f"Encrypted value:")
        print(encrypted)

    elif args.command == 'decrypt':
        manager = SecretsManager(master_key=args.key)
        decrypted = manager.decrypt(args.value)
        print(f"Decrypted value:")
        print(decrypted)

    elif args.command == 'encrypt-file':
        with open(args.input, 'r') as f:
            secrets = json.load(f)
        manager = SecretsManager(master_key=args.key)
        manager.encrypt_secrets_file(secrets, args.output)
        print(f"Encrypted {len(secrets)} secrets to {args.output}")

    elif args.command == 'decrypt-file':
        manager = SecretsManager(master_key=args.key)
        secrets = manager.decrypt_secrets_file(args.input)
        print(f"Decrypted secrets:")
        print(json.dumps(secrets, indent=2))

    else:
        parser.print_help()
