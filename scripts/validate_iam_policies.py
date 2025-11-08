#!/usr/bin/env python3
"""
IAM Policy Least Privilege Validator

Validates IAM policies against least privilege principles:
- No wildcard resources ("Resource": "*")
- No wildcard actions ("Action": "*" or "service:*")
- Conditions required for broad permissions
- No wildcard principals

Usage:
    python scripts/validate_iam_policies.py <policy_file> [--fail-on-violation]
    python scripts/validate_iam_policies.py iam/policies/*.json --fail-on-violation
"""

import json
import sys
import argparse
import glob
from typing import List, Dict, Any
from pathlib import Path


class IAMPolicyValidator:
    """Validator for IAM policies following least privilege principles."""

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self.violations = []
        self.warnings = []

    def validate_policy(self, policy_json: str, policy_file: str = "unknown") -> Dict[str, Any]:
        """
        Validate an IAM policy for least privilege compliance.

        Args:
            policy_json: JSON string of IAM policy
            policy_file: File path (for reporting)

        Returns:
            Dict with validation results
        """
        try:
            policy = json.loads(policy_json)
        except json.JSONDecodeError as e:
            return {
                'valid': False,
                'violations': [f"Invalid JSON: {str(e)}"],
                'warnings': []
            }

        violations = []
        warnings = []

        # Validate policy has required fields
        if 'Statement' not in policy:
            violations.append("Missing required 'Statement' field")
            return {'valid': False, 'violations': violations, 'warnings': warnings}

        # Validate each statement
        for idx, statement in enumerate(policy.get('Statement', [])):
            sid = statement.get('Sid', f'Statement-{idx}')

            # Check 1: Resource wildcards
            resources = statement.get('Resource', [])
            if isinstance(resources, str):
                resources = [resources]

            if "*" in resources:
                violations.append(
                    f"[{sid}] VIOLATION: Resource contains wildcard '*' "
                    f"(violates least privilege)"
                )

            # Check partial wildcards (e.g., "arn:aws:s3:::bucket/*")
            partial_wildcards = [r for r in resources if '*' in r and r != '*']
            if partial_wildcards and self.strict_mode:
                warnings.append(
                    f"[{sid}] WARNING: Resource contains partial wildcard: {partial_wildcards}"
                )

            # Check 2: Action wildcards
            actions = statement.get('Action', [])
            if isinstance(actions, str):
                actions = [actions]

            for action in actions:
                if action == "*":
                    violations.append(
                        f"[{sid}] VIOLATION: Action is '*' (grants all permissions)"
                    )
                elif action.endswith(":*"):
                    violations.append(
                        f"[{sid}] VIOLATION: Action is wildcard '{action}' "
                        f"(grants all service permissions)"
                    )

            # Check 3: Missing Condition on broad statements
            conditions = statement.get('Condition')
            if not conditions:
                if len(actions) > 10:
                    warnings.append(
                        f"[{sid}] WARNING: Statement has {len(actions)} actions "
                        f"with no Condition clause (consider adding IP/MFA/time restrictions)"
                    )

                # Check for admin-like actions without conditions
                admin_keywords = ['Admin', 'Full', '*', 'All']
                if any(keyword in str(actions) for keyword in admin_keywords):
                    warnings.append(
                        f"[{sid}] WARNING: Admin-like permissions without Condition clause"
                    )

            # Check 4: Principal wildcards (dangerous for trust policies)
            principal = statement.get('Principal')
            if principal == "*":
                violations.append(
                    f"[{sid}] VIOLATION: Principal is wildcard '*' "
                    f"(allows anyone to assume role)"
                )
            elif isinstance(principal, dict):
                for key, value in principal.items():
                    if value == "*":
                        violations.append(
                            f"[{sid}] VIOLATION: Principal.{key} is wildcard '*'"
                        )

            # Check 5: Effect is Allow (informational)
            effect = statement.get('Effect', 'Deny')
            if effect == 'Allow' and not conditions and len(resources) == 1 and resources[0] == '*':
                violations.append(
                    f"[{sid}] VIOLATION: Allows all actions on all resources without restrictions"
                )

            # Check 6: NotAction / NotResource (anti-patterns)
            if 'NotAction' in statement:
                warnings.append(
                    f"[{sid}] WARNING: Uses 'NotAction' (difficult to maintain, prefer explicit actions)"
                )

            if 'NotResource' in statement:
                warnings.append(
                    f"[{sid}] WARNING: Uses 'NotResource' (difficult to maintain, prefer explicit resources)"
                )

        return {
            'valid': len(violations) == 0,
            'violations': violations,
            'warnings': warnings,
            'policy_file': policy_file
        }

    def validate_file(self, policy_file: Path) -> Dict[str, Any]:
        """Validate a single policy file."""
        with open(policy_file, 'r') as f:
            policy_json = f.read()

        return self.validate_policy(policy_json, str(policy_file))

    def validate_directory(self, directory: Path, pattern: str = "**/*.json") -> List[Dict[str, Any]]:
        """Validate all policy files in a directory."""
        results = []
        policy_files = list(directory.glob(pattern))

        if not policy_files:
            print(f"⚠️  No policy files found matching pattern '{pattern}' in {directory}")
            return results

        for policy_file in policy_files:
            result = self.validate_file(policy_file)
            results.append(result)

        return results


def print_results(results: List[Dict[str, Any]], fail_on_violation: bool = False) -> bool:
    """
    Print validation results and return success status.

    Args:
        results: List of validation results
        fail_on_violation: Whether to fail on any violation

    Returns:
        True if all policies passed, False otherwise
    """
    total_violations = 0
    total_warnings = 0

    print("\n" + "=" * 80)
    print("IAM Policy Least Privilege Validation Results")
    print("=" * 80 + "\n")

    for result in results:
        policy_file = result['policy_file']
        violations = result['violations']
        warnings = result['warnings']

        print(f"📄 {policy_file}")

        if violations:
            print(f"  ❌ Found {len(violations)} violation(s):")
            for v in violations:
                print(f"    • {v}")
            total_violations += len(violations)

        if warnings:
            print(f"  ⚠️  Found {len(warnings)} warning(s):")
            for w in warnings:
                print(f"    • {w}")
            total_warnings += len(warnings)

        if not violations and not warnings:
            print(f"  ✅ Policy passed validation")

        print()

    # Summary
    print("=" * 80)
    print(f"Summary: {len(results)} policy file(s) validated")
    print(f"  • Violations: {total_violations}")
    print(f"  • Warnings: {total_warnings}")

    if total_violations > 0:
        print("\n❌ FAILED: Found critical violations")
        print("   Action required: Fix violations before merging")
        return False
    elif total_warnings > 0:
        print("\n⚠️  PASSED with warnings")
        print("   Consider addressing warnings for best security posture")
        return True
    else:
        print("\n✅ PASSED: All policies comply with least privilege")
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate IAM policies for least privilege compliance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single policy file
  python scripts/validate_iam_policies.py iam/policies/trader_role.json

  # Validate all policies in directory
  python scripts/validate_iam_policies.py iam/policies/*.json

  # Fail on any violation (for CI/CD)
  python scripts/validate_iam_policies.py iam/policies/*.json --fail-on-violation

  # Strict mode (treat warnings as errors)
  python scripts/validate_iam_policies.py iam/policies/*.json --strict
        """
    )

    parser.add_argument(
        'policy_files',
        nargs='+',
        help='IAM policy JSON file(s) to validate'
    )
    parser.add_argument(
        '--fail-on-violation',
        action='store_true',
        help='Exit with error code if violations found (for CI/CD)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Strict mode: treat warnings as errors'
    )
    parser.add_argument(
        '--json-output',
        action='store_true',
        help='Output results as JSON'
    )

    args = parser.parse_args()

    # Expand glob patterns
    policy_files = []
    for pattern in args.policy_files:
        expanded = glob.glob(pattern, recursive=True)
        policy_files.extend(expanded)

    if not policy_files:
        print("❌ No policy files found to validate")
        sys.exit(1)

    # Validate policies
    validator = IAMPolicyValidator(strict_mode=args.strict)
    results = []

    for policy_file in policy_files:
        path = Path(policy_file)
        if not path.exists():
            print(f"⚠️  File not found: {policy_file}")
            continue

        result = validator.validate_file(path)
        results.append(result)

    # Output results
    if args.json_output:
        print(json.dumps(results, indent=2))
        sys.exit(0)

    # Print results
    success = print_results(results, args.fail_on_violation)

    # Exit with appropriate code
    if args.fail_on_violation and not success:
        sys.exit(1)
    elif args.strict:
        # In strict mode, warnings also fail
        total_warnings = sum(len(r['warnings']) for r in results)
        if total_warnings > 0:
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
