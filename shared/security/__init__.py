"""
Security utilities for the Algo-Trade platform.

This module provides:
- Secrets encryption/decryption (at rest)
- Secrets rotation management
- Secure key storage
- TLS/SSL configuration helpers
"""

from .secrets_manager import SecretsManager, EncryptionError, DecryptionError
from .rotation import SecretsRotationManager, RotationPolicy
from .tls_config import TLSConfig, create_ssl_context

__all__ = [
    'SecretsManager',
    'EncryptionError',
    'DecryptionError',
    'SecretsRotationManager',
    'RotationPolicy',
    'TLSConfig',
    'create_ssl_context',
]

__version__ = '0.1.0'
