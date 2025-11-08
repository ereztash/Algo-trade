#!/usr/bin/env python3
"""
Security Event Log Schema Validator

Validates security event logs against the schema defined in SECURITY_EXECUTION_SUMMARY.md

Schema:
{
  "timestamp": "2025-11-08T14:30:15.042Z",  # ISO 8601 UTC
  "event_id": "evt-abc123456",              # Unique identifier
  "event_type": "SECRET_READ",              # Type
  "actor": {
    "type": "user",                         # user | service_account | system
    "id": "alice@example.com",
    "role": "trader-prod",
    "session_id": "sess-xyz789"
  },
  "action": {
    "verb": "READ",                         # CREATE | READ | UPDATE | DELETE | EXECUTE
    "resource": "secret://prod/ibkr/api-key",
    "resource_id": "sec-12345"
  },
  "context": {
    "ip_address": "203.0.113.42",
    "user_agent": "AWS CLI v2",
    "request_id": "req-abc123",
    "environment": "production"
  },
  "result": {
    "status": "SUCCESS",                    # SUCCESS | FAILURE
    "http_status": 200,
    "error_code": null,
    "error_message": null,
    "duration_ms": 42
  },
  "security_context": {
    "mfa_verified": true,
    "ip_whitelisted": true,
    "anomaly_score": 0.15
  }
}

Usage:
    python scripts/validate_security_logs.py <log_file.json>
    python scripts/validate_security_logs.py <log_file.jsonl> --jsonlines
"""

import json
import sys
import argparse
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
import re


class SecurityLogValidator:
    """Validator for security event logs."""

    # Valid event types
    VALID_EVENT_TYPES = {
        'SECRET_READ', 'SECRET_ROTATE', 'SECRET_REVOKE',
        'LOGIN_SUCCESS', 'LOGIN_FAILED',
        'IAM_ROLE_CREATED', 'IAM_POLICY_CHANGED',
        'PACING_VIOLATION', 'KILL_SWITCH_ACTIVATED',
        'CERTIFICATE_EXPIRY', 'DATA_EXPORT',
        'CODE_CHANGE_DEPLOYED', 'COMPLIANCE_AUDIT',
        'INCIDENT_CREATED'
    }

    # Valid actor types
    VALID_ACTOR_TYPES = {'user', 'service_account', 'system'}

    # Valid action verbs
    VALID_ACTION_VERBS = {'CREATE', 'READ', 'UPDATE', 'DELETE', 'EXECUTE'}

    # Valid result statuses
    VALID_RESULT_STATUSES = {'SUCCESS', 'FAILURE'}

    # Valid environments
    VALID_ENVIRONMENTS = {'qa', 'paper', 'production'}

    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode

    def validate_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single security event.

        Returns:
            Dict with validation results
        """
        violations = []
        warnings = []

        # Validate required fields
        required_fields = ['timestamp', 'event_id', 'event_type', 'actor', 'action', 'result']
        for field in required_fields:
            if field not in event:
                violations.append(f"Missing required field: {field}")

        if violations:
            return {'valid': False, 'violations': violations, 'warnings': warnings}

        # Validate timestamp (ISO 8601 UTC)
        try:
            ts = event['timestamp']
            # Must end with 'Z' for UTC
            if not ts.endswith('Z'):
                violations.append(f"Timestamp must be UTC (end with 'Z'): {ts}")

            # Try to parse
            datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except (ValueError, KeyError) as e:
            violations.append(f"Invalid timestamp format: {e}")

        # Validate event_id (non-empty string)
        event_id = event.get('event_id', '')
        if not event_id or not isinstance(event_id, str):
            violations.append("event_id must be a non-empty string")

        # Validate event_type
        event_type = event.get('event_type', '')
        if event_type not in self.VALID_EVENT_TYPES:
            violations.append(
                f"Invalid event_type '{event_type}'. Must be one of: {self.VALID_EVENT_TYPES}"
            )

        # Validate actor
        actor = event.get('actor', {})
        if not isinstance(actor, dict):
            violations.append("actor must be an object")
        else:
            # actor.type
            actor_type = actor.get('type')
            if actor_type not in self.VALID_ACTOR_TYPES:
                violations.append(
                    f"Invalid actor.type '{actor_type}'. Must be one of: {self.VALID_ACTOR_TYPES}"
                )

            # actor.id (required)
            if not actor.get('id'):
                violations.append("actor.id is required and cannot be empty")

            # actor.role (required)
            if not actor.get('role'):
                warnings.append("actor.role is missing (recommended)")

        # Validate action
        action = event.get('action', {})
        if not isinstance(action, dict):
            violations.append("action must be an object")
        else:
            # action.verb
            verb = action.get('verb')
            if verb not in self.VALID_ACTION_VERBS:
                violations.append(
                    f"Invalid action.verb '{verb}'. Must be one of: {self.VALID_ACTION_VERBS}"
                )

            # action.resource (required)
            resource = action.get('resource', '')
            if not resource:
                violations.append("action.resource is required")

            # Check resource URI scheme
            if not re.match(r'^[a-z]+://', resource):
                warnings.append(
                    f"action.resource should include scheme (e.g., 'secret://', 'iam://'): {resource}"
                )

        # Validate context (optional, but recommended)
        context = event.get('context', {})
        if context:
            # context.environment
            env = context.get('environment')
            if env and env not in self.VALID_ENVIRONMENTS:
                violations.append(
                    f"Invalid context.environment '{env}'. Must be one of: {self.VALID_ENVIRONMENTS}"
                )

            # context.ip_address (validate format if present)
            ip = context.get('ip_address')
            if ip:
                # Basic IPv4/IPv6 validation
                if not re.match(r'^(\d{1,3}\.){3}\d{1,3}$|^([0-9a-fA-F:]+)$', ip):
                    warnings.append(f"context.ip_address format may be invalid: {ip}")

        # Validate result
        result = event.get('result', {})
        if not isinstance(result, dict):
            violations.append("result must be an object")
        else:
            # result.status
            status = result.get('status')
            if status not in self.VALID_RESULT_STATUSES:
                violations.append(
                    f"Invalid result.status '{status}'. Must be one of: {self.VALID_RESULT_STATUSES}"
                )

            # result.duration_ms (must be non-negative)
            duration = result.get('duration_ms')
            if duration is not None:
                if not isinstance(duration, (int, float)) or duration < 0:
                    violations.append(f"result.duration_ms must be a non-negative number: {duration}")

        # Validate security_context (optional)
        sec_ctx = event.get('security_context', {})
        if sec_ctx:
            # anomaly_score (must be 0-1)
            anomaly_score = sec_ctx.get('anomaly_score')
            if anomaly_score is not None:
                if not isinstance(anomaly_score, (int, float)) or not 0 <= anomaly_score <= 1:
                    violations.append(
                        f"security_context.anomaly_score must be between 0 and 1: {anomaly_score}"
                    )

        # Check for secrets in logs (PII sanitization)
        event_str = json.dumps(event)
        if self._contains_secrets(event_str):
            violations.append(
                "CRITICAL: Event contains potential secrets (API keys, passwords). "
                "All secrets must be sanitized before logging."
            )

        return {
            'valid': len(violations) == 0,
            'violations': violations,
            'warnings': warnings,
            'event_id': event.get('event_id', 'unknown')
        }

    def _contains_secrets(self, text: str) -> bool:
        """
        Check if text contains potential secrets.

        Patterns to detect:
        - IBKR API keys
        - AWS keys (AKIA*)
        - Passwords
        - Private keys
        """
        secret_patterns = [
            r'AKIA[A-Z0-9]{16}',  # AWS Access Key
            r'password\s*[:=]\s*["\']?[^"\'\s]+',  # password=xxx
            r'api[_-]?key\s*[:=]\s*["\']?[^"\'\s]+',  # api_key=xxx
            r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY',  # Private key
            r'Bearer\s+[A-Za-z0-9\-._~+/]+=*',  # Bearer token
        ]

        for pattern in secret_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def validate_file(self, log_file: Path, jsonlines: bool = False) -> List[Dict[str, Any]]:
        """
        Validate all events in a log file.

        Args:
            log_file: Path to log file
            jsonlines: True if file is JSONL format (one JSON object per line)

        Returns:
            List of validation results
        """
        results = []

        with open(log_file, 'r') as f:
            if jsonlines:
                # JSONL format
                for line_num, line in enumerate(f, start=1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        event = json.loads(line)
                        result = self.validate_event(event)
                        result['line_number'] = line_num
                        results.append(result)
                    except json.JSONDecodeError as e:
                        results.append({
                            'valid': False,
                            'violations': [f"Invalid JSON on line {line_num}: {e}"],
                            'warnings': [],
                            'line_number': line_num
                        })
            else:
                # Standard JSON array
                try:
                    data = json.load(f)

                    # Support both single event and array of events
                    if isinstance(data, dict):
                        events = [data]
                    elif isinstance(data, list):
                        events = data
                    else:
                        return [{
                            'valid': False,
                            'violations': ['Log file must contain a JSON object or array'],
                            'warnings': []
                        }]

                    for idx, event in enumerate(events):
                        result = self.validate_event(event)
                        result['event_index'] = idx
                        results.append(result)

                except json.JSONDecodeError as e:
                    return [{
                        'valid': False,
                        'violations': [f"Invalid JSON file: {e}"],
                        'warnings': []
                    }]

        return results


def print_results(results: List[Dict[str, Any]], log_file: str) -> bool:
    """
    Print validation results.

    Returns:
        True if all events passed, False otherwise
    """
    total_violations = 0
    total_warnings = 0
    total_events = len(results)

    print("\n" + "=" * 80)
    print(f"Security Log Validation Results: {log_file}")
    print("=" * 80 + "\n")

    for result in results:
        event_id = result.get('event_id', 'unknown')
        line_num = result.get('line_number')
        event_idx = result.get('event_index')

        location = f"Line {line_num}" if line_num else f"Event {event_idx}"

        violations = result.get('violations', [])
        warnings = result.get('warnings', [])

        if violations:
            print(f"❌ {location} (event_id: {event_id})")
            print(f"   Violations ({len(violations)}):")
            for v in violations:
                print(f"     • {v}")
            total_violations += len(violations)

        if warnings:
            print(f"⚠️  {location} (event_id: {event_id})")
            print(f"   Warnings ({len(warnings)}):")
            for w in warnings:
                print(f"     • {w}")
            total_warnings += len(warnings)

        if not violations and not warnings:
            print(f"✅ {location} (event_id: {event_id})")

    # Summary
    print("\n" + "=" * 80)
    print(f"Summary: {total_events} event(s) validated")
    print(f"  • Violations: {total_violations}")
    print(f"  • Warnings: {total_warnings}")

    if total_violations > 0:
        print("\n❌ FAILED: Found schema violations")
        return False
    elif total_warnings > 0:
        print("\n⚠️  PASSED with warnings")
        return True
    else:
        print("\n✅ PASSED: All events comply with schema")
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate security event logs against schema",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'log_file',
        help='Security log file to validate (JSON or JSONL format)'
    )
    parser.add_argument(
        '--jsonlines',
        action='store_true',
        help='Treat file as JSONL format (one JSON object per line)'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Strict mode: treat warnings as errors'
    )
    parser.add_argument(
        '--fail-on-violation',
        action='store_true',
        help='Exit with error code if violations found (for CI/CD)'
    )

    args = parser.parse_args()

    log_file = Path(args.log_file)
    if not log_file.exists():
        print(f"❌ Log file not found: {log_file}")
        sys.exit(1)

    # Validate logs
    validator = SecurityLogValidator(strict_mode=args.strict)
    results = validator.validate_file(log_file, jsonlines=args.jsonlines)

    # Print results
    success = print_results(results, str(log_file))

    # Exit with appropriate code
    if args.fail_on_violation and not success:
        sys.exit(1)
    elif args.strict:
        # In strict mode, warnings also fail
        total_warnings = sum(len(r.get('warnings', [])) for r in results)
        if total_warnings > 0:
            sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
