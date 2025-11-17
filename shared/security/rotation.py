# -*- coding: utf-8 -*-
"""
rotation.py
ניהול rotation (החלפה תקופתית) של סודות ומפתחות

מאפיינים:
- Automatic secret rotation based on age
- Rotation policies (time-based, usage-based)
- Integration with Vault, AWS Secrets Manager
- Audit trail for rotations
- Notifications for upcoming rotations
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class RotationStatus(Enum):
    """Status of a secret rotation"""
    CURRENT = "current"           # Secret is current and valid
    ROTATING = "rotating"          # Rotation in progress
    PENDING = "pending"            # Rotation scheduled but not started
    EXPIRED = "expired"            # Secret has expired
    FAILED = "failed"              # Rotation failed


@dataclass
class RotationPolicy:
    """
    Policy for secret rotation.

    Attributes:
        max_age_days: Maximum age before rotation required
        rotation_window_days: Days before expiry to start rotation
        auto_rotate: Automatically rotate when conditions met
        notify_before_days: Days before expiry to send notification
    """
    max_age_days: int = 90
    rotation_window_days: int = 7
    auto_rotate: bool = False
    notify_before_days: int = 14

    def __post_init__(self):
        """Validate policy parameters"""
        if self.max_age_days <= 0:
            raise ValueError("max_age_days must be positive")
        if self.rotation_window_days >= self.max_age_days:
            raise ValueError("rotation_window_days must be less than max_age_days")
        if self.notify_before_days > self.max_age_days:
            raise ValueError("notify_before_days must be less than max_age_days")


@dataclass
class SecretMetadata:
    """
    Metadata for a managed secret.

    Attributes:
        name: Secret identifier
        created_at: When secret was created
        rotated_at: Last rotation timestamp
        expires_at: When secret expires
        status: Current rotation status
        rotation_count: Number of times rotated
        policy: Rotation policy for this secret
    """
    name: str
    created_at: datetime
    rotated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    status: RotationStatus = RotationStatus.CURRENT
    rotation_count: int = 0
    policy: Optional[RotationPolicy] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecretMetadata':
        """Create from dictionary (for loading from JSON)"""
        # Convert ISO strings to datetime
        if isinstance(data.get('created_at'), str):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if isinstance(data.get('rotated_at'), str):
            data['rotated_at'] = datetime.fromisoformat(data['rotated_at'])
        if isinstance(data.get('expires_at'), str):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])

        # Convert status string to enum
        if isinstance(data.get('status'), str):
            data['status'] = RotationStatus(data['status'])

        # Convert policy dict to RotationPolicy
        if isinstance(data.get('policy'), dict):
            data['policy'] = RotationPolicy(**data['policy'])

        return cls(**data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (for JSON serialization)"""
        data = asdict(self)
        # Convert datetime to ISO strings
        data['created_at'] = self.created_at.isoformat()
        if self.rotated_at:
            data['rotated_at'] = self.rotated_at.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        # Convert enum to string
        data['status'] = self.status.value
        return data

    def is_expired(self) -> bool:
        """Check if secret has expired"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False

    def needs_rotation(self) -> bool:
        """Check if secret needs rotation based on policy"""
        if not self.policy:
            return False

        if self.is_expired():
            return True

        age = datetime.utcnow() - (self.rotated_at or self.created_at)
        max_age = timedelta(days=self.policy.max_age_days)
        rotation_threshold = max_age - timedelta(days=self.policy.rotation_window_days)

        return age >= rotation_threshold


class SecretsRotationManager:
    """
    Manages rotation of secrets according to policies.

    Example:
        >>> policy = RotationPolicy(max_age_days=90, auto_rotate=True)
        >>> manager = SecretsRotationManager(policy)
        >>> manager.register_secret("IBKR_PASSWORD", current_value)
        >>> secrets_to_rotate = manager.get_secrets_needing_rotation()
        >>> for secret in secrets_to_rotate:
        ...     new_value = generate_new_password()
        ...     manager.rotate_secret(secret, new_value)
    """

    def __init__(
        self,
        default_policy: Optional[RotationPolicy] = None,
        metadata_file: Optional[str] = None,
        rotation_callback: Optional[Callable[[str, str], None]] = None
    ):
        """
        Initialize rotation manager.

        Args:
            default_policy: Default rotation policy for all secrets
            metadata_file: Path to file storing secret metadata
            rotation_callback: Function called when rotation happens (secret_name, new_value)
        """
        self.default_policy = default_policy or RotationPolicy()
        self.metadata_file = Path(metadata_file) if metadata_file else Path(".secrets_metadata.json")
        self.rotation_callback = rotation_callback

        # Load existing metadata
        self.secrets: Dict[str, SecretMetadata] = self._load_metadata()

        logger.info(f"Initialized rotation manager with {len(self.secrets)} secrets")

    def _load_metadata(self) -> Dict[str, SecretMetadata]:
        """Load secret metadata from file"""
        if not self.metadata_file.exists():
            logger.debug(f"No metadata file found at {self.metadata_file}")
            return {}

        try:
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)

            secrets = {}
            for name, meta_dict in data.items():
                secrets[name] = SecretMetadata.from_dict(meta_dict)

            logger.info(f"Loaded metadata for {len(secrets)} secrets")
            return secrets
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return {}

    def _save_metadata(self) -> None:
        """Save secret metadata to file"""
        try:
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

            data = {name: meta.to_dict() for name, meta in self.secrets.items()}

            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Set restrictive permissions
            os.chmod(self.metadata_file, 0o600)

            logger.debug(f"Saved metadata for {len(self.secrets)} secrets")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def register_secret(
        self,
        name: str,
        policy: Optional[RotationPolicy] = None,
        created_at: Optional[datetime] = None
    ) -> SecretMetadata:
        """
        Register a new secret for rotation management.

        Args:
            name: Secret identifier
            policy: Rotation policy (uses default if None)
            created_at: Creation timestamp (uses now if None)

        Returns:
            SecretMetadata for the registered secret
        """
        if name in self.secrets:
            logger.warning(f"Secret {name} already registered, updating policy")
            self.secrets[name].policy = policy or self.default_policy
        else:
            policy = policy or self.default_policy
            created_at = created_at or datetime.utcnow()

            # Calculate expiry
            expires_at = created_at + timedelta(days=policy.max_age_days)

            metadata = SecretMetadata(
                name=name,
                created_at=created_at,
                expires_at=expires_at,
                policy=policy
            )

            self.secrets[name] = metadata
            logger.info(f"Registered secret: {name}, expires: {expires_at.date()}")

        self._save_metadata()
        return self.secrets[name]

    def rotate_secret(
        self,
        name: str,
        new_value: Optional[str] = None,
        update_callback: Optional[Callable[[str], str]] = None
    ) -> bool:
        """
        Rotate a secret to a new value.

        Args:
            name: Secret identifier
            new_value: New secret value (if None, uses update_callback)
            update_callback: Function to generate/update secret (returns new value)

        Returns:
            True if rotation succeeded

        Example:
            >>> def update_ibkr_password(old_password):
            ...     # Call IBKR API to change password
            ...     return new_password
            >>> manager.rotate_secret("IBKR_PASSWORD", update_callback=update_ibkr_password)
        """
        if name not in self.secrets:
            logger.error(f"Secret {name} not registered")
            return False

        metadata = self.secrets[name]

        try:
            metadata.status = RotationStatus.ROTATING
            self._save_metadata()

            # Get new value
            if new_value is None and update_callback:
                new_value = update_callback(name)
            elif new_value is None:
                logger.error("No new value or callback provided for rotation")
                metadata.status = RotationStatus.FAILED
                self._save_metadata()
                return False

            # Call rotation callback (to update external systems)
            if self.rotation_callback:
                self.rotation_callback(name, new_value)

            # Update metadata
            now = datetime.utcnow()
            metadata.rotated_at = now
            metadata.rotation_count += 1
            metadata.status = RotationStatus.CURRENT

            # Update expiry
            if metadata.policy:
                metadata.expires_at = now + timedelta(days=metadata.policy.max_age_days)

            self._save_metadata()

            logger.info(f"Rotated secret: {name} (count: {metadata.rotation_count})")
            return True

        except Exception as e:
            logger.error(f"Failed to rotate secret {name}: {e}")
            metadata.status = RotationStatus.FAILED
            self._save_metadata()
            return False

    def get_secrets_needing_rotation(self) -> List[str]:
        """
        Get list of secrets that need rotation.

        Returns:
            List of secret names that need rotation
        """
        needs_rotation = []

        for name, metadata in self.secrets.items():
            if metadata.needs_rotation():
                needs_rotation.append(name)

        logger.info(f"Found {len(needs_rotation)} secrets needing rotation")
        return needs_rotation

    def get_secrets_expiring_soon(self, days: int = 7) -> List[str]:
        """
        Get secrets expiring within specified days.

        Args:
            days: Number of days to look ahead

        Returns:
            List of secret names expiring soon
        """
        threshold = datetime.utcnow() + timedelta(days=days)
        expiring = []

        for name, metadata in self.secrets.items():
            if metadata.expires_at and metadata.expires_at <= threshold:
                expiring.append(name)

        return expiring

    def auto_rotate_secrets(self) -> Dict[str, bool]:
        """
        Automatically rotate all secrets that need rotation.

        Returns:
            Dict mapping secret names to rotation success (True/False)
        """
        results = {}
        secrets_to_rotate = self.get_secrets_needing_rotation()

        for secret_name in secrets_to_rotate:
            metadata = self.secrets[secret_name]

            if not metadata.policy or not metadata.policy.auto_rotate:
                logger.info(f"Skipping {secret_name} - auto_rotate disabled")
                continue

            logger.info(f"Auto-rotating secret: {secret_name}")
            success = self.rotate_secret(secret_name)
            results[secret_name] = success

        return results

    def get_rotation_report(self) -> Dict[str, Any]:
        """
        Generate a rotation status report.

        Returns:
            Report with rotation statistics and upcoming rotations
        """
        now = datetime.utcnow()

        report = {
            "generated_at": now.isoformat(),
            "total_secrets": len(self.secrets),
            "by_status": {},
            "needs_rotation": [],
            "expiring_soon": [],
            "rotation_history": []
        }

        # Count by status
        for status in RotationStatus:
            count = sum(1 for m in self.secrets.values() if m.status == status)
            report["by_status"][status.value] = count

        # Secrets needing rotation
        report["needs_rotation"] = self.get_secrets_needing_rotation()

        # Expiring soon (next 30 days)
        report["expiring_soon"] = [
            {
                "name": name,
                "expires_at": meta.expires_at.isoformat() if meta.expires_at else None
            }
            for name, meta in self.secrets.items()
            if meta.expires_at and meta.expires_at <= now + timedelta(days=30)
        ]

        # Recent rotations
        recent_rotations = sorted(
            [
                {
                    "name": name,
                    "rotated_at": meta.rotated_at.isoformat(),
                    "rotation_count": meta.rotation_count
                }
                for name, meta in self.secrets.items()
                if meta.rotated_at
            ],
            key=lambda x: x["rotated_at"],
            reverse=True
        )[:10]  # Last 10 rotations

        report["rotation_history"] = recent_rotations

        return report


# =============================================================================
# CLI for Rotation Management
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Secrets rotation management")
    subparsers = parser.add_subparsers(dest='command')

    # Register secret
    reg = subparsers.add_parser('register', help='Register a secret')
    reg.add_argument('name', help='Secret name')
    reg.add_argument('--max-age', type=int, default=90, help='Max age in days')

    # List secrets
    list_parser = subparsers.add_parser('list', help='List managed secrets')

    # Check rotations
    check = subparsers.add_parser('check', help='Check secrets needing rotation')

    # Generate report
    report = subparsers.add_parser('report', help='Generate rotation report')

    args = parser.parse_args()

    if args.command == 'register':
        policy = RotationPolicy(max_age_days=args.max_age)
        manager = SecretsRotationManager(default_policy=policy)
        manager.register_secret(args.name)
        print(f"Registered secret: {args.name}")

    elif args.command == 'list':
        manager = SecretsRotationManager()
        print(f"\nManaged Secrets ({len(manager.secrets)}):")
        for name, meta in manager.secrets.items():
            print(f"  - {name}: {meta.status.value}, rotated {meta.rotation_count} times")

    elif args.command == 'check':
        manager = SecretsRotationManager()
        needs_rotation = manager.get_secrets_needing_rotation()
        if needs_rotation:
            print(f"\n⚠️  Secrets needing rotation ({len(needs_rotation)}):")
            for name in needs_rotation:
                print(f"  - {name}")
        else:
            print("\n✅ All secrets are current")

    elif args.command == 'report':
        manager = SecretsRotationManager()
        report = manager.get_rotation_report()
        print(json.dumps(report, indent=2))

    else:
        parser.print_help()
