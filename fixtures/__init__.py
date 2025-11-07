"""
Fixture Management Module

Provides utilities for:
- Loading deterministic test fixtures
- Signing fixtures with SHA256 hashes
- Verifying fixture integrity
- Managing random seeds
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import yaml

# Fixture base directory
FIXTURES_DIR = Path(__file__).parent


def load_seeds() -> Dict[str, Any]:
    """Load random seeds from seeds.yaml."""
    seeds_file = FIXTURES_DIR / "seeds.yaml"
    with open(seeds_file) as f:
        return yaml.safe_load(f)


def sign_fixture(data: dict, version: str = "1.0") -> dict:
    """
    Add cryptographic signature to fixture data.

    Args:
        data: Fixture data dictionary
        version: Fixture version

    Returns:
        Signed fixture with metadata
    """
    from datetime import datetime

    # Sort keys for consistent hashing
    data_str = json.dumps(data, sort_keys=True, default=str)
    signature = hashlib.sha256(data_str.encode()).hexdigest()

    return {
        "data": data,
        "metadata": {
            "signature": signature,
            "version": version,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "algorithm": "sha256",
        },
    }


def verify_fixture(fixture_content: dict) -> bool:
    """
    Verify fixture signature.

    Args:
        fixture_content: Loaded fixture dictionary

    Returns:
        True if signature is valid, False otherwise
    """
    if "data" not in fixture_content or "metadata" not in fixture_content:
        raise ValueError("Invalid fixture format: missing data or metadata")

    data = fixture_content["data"]
    expected_sig = fixture_content["metadata"]["signature"]

    # Recompute signature
    data_str = json.dumps(data, sort_keys=True, default=str)
    actual_sig = hashlib.sha256(data_str.encode()).hexdigest()

    return actual_sig == expected_sig


def load_fixture(filename: str, verify: bool = True) -> dict:
    """
    Load and optionally verify a fixture file.

    Args:
        filename: Fixture filename (relative to fixtures/)
        verify: Whether to verify signature

    Returns:
        Fixture data

    Raises:
        ValueError: If signature verification fails
    """
    fixture_path = FIXTURES_DIR / filename

    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path) as f:
        content = json.load(f)

    if verify:
        if not verify_fixture(content):
            raise ValueError(f"Fixture signature verification failed: {filename}")

    return content["data"]


def save_fixture(filename: str, data: dict, version: str = "1.0") -> None:
    """
    Sign and save a fixture file.

    Args:
        filename: Fixture filename (relative to fixtures/)
        data: Fixture data
        version: Fixture version
    """
    fixture_path = FIXTURES_DIR / filename
    fixture_path.parent.mkdir(parents=True, exist_ok=True)

    signed = sign_fixture(data, version)

    with open(fixture_path, "w") as f:
        json.dump(signed, f, indent=2, default=str)


# Expose key functions
__all__ = [
    "load_seeds",
    "sign_fixture",
    "verify_fixture",
    "load_fixture",
    "save_fixture",
    "FIXTURES_DIR",
]
