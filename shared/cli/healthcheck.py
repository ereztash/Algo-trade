"""Health check utility."""

import sys
from pathlib import Path
import yaml

def healthcheck() -> int:
    """
    Health check for the 3-plane trading system.

    Verifies:
    - Config file exists and is valid YAML
    - Required directories exist
    - Models can be imported

    Returns:
        0 if healthy, 1 if unhealthy
    """
    checks_passed = 0
    checks_failed = 0

    print("=" * 60)
    print("HEALTHCHECK - 3-Plane Trading System")
    print("=" * 60)
    print()

    # Check 1: Config file
    config_path = Path("shared/config/config.yaml")
    if config_path.exists():
        try:
            with open(config_path) as f:
                yaml.safe_load(f)
            print("✓ Config file valid")
            checks_passed += 1
        except Exception as e:
            print(f"✗ Config file invalid: {e}")
            checks_failed += 1
    else:
        print("✗ Config file not found")
        checks_failed += 1

    # Check 2: Models import
    try:
        from shared.models import Bar, Signal, OrderIntent
        print("✓ Models importable")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Models import failed: {e}")
        checks_failed += 1

    # Check 3: Orchestrator import
    try:
        from apps.strategy_loop.orchestrator import Orchestrator
        print("✓ Orchestrator importable")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Orchestrator import failed: {e}")
        checks_failed += 1

    # Check 4: Required directories
    required_dirs = ["reports", "fixtures", "shared/config"]
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"✓ Directory exists: {dir_path}")
            checks_passed += 1
        else:
            print(f"✗ Directory missing: {dir_path}")
            checks_failed += 1

    print()
    print("=" * 60)
    print(f"RESULTS: {checks_passed}/{checks_passed + checks_failed} checks passed")
    print("=" * 60)

    if checks_failed == 0:
        print("✅ System healthy")
        return 0
    else:
        print(f"❌ System unhealthy ({checks_failed} failures)")
        return 1


if __name__ == "__main__":
    sys.exit(healthcheck())
