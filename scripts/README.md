# Security Validation Scripts

This directory contains security validation scripts for the Algo-Trade system.

## Scripts

### 1. IAM Policy Validator (`validate_iam_policies.py`)

Validates IAM policies for least privilege compliance.

**Usage:**
```bash
# Validate single policy
python scripts/validate_iam_policies.py iam/policies/trader_role.json

# Validate all policies
python scripts/validate_iam_policies.py iam/policies/*.json

# Fail on violations (for CI/CD)
python scripts/validate_iam_policies.py iam/policies/*.json --fail-on-violation

# Strict mode (warnings = errors)
python scripts/validate_iam_policies.py iam/policies/*.json --strict
```

**Checks:**
- ❌ No wildcard resources (`"Resource": "*"`)
- ❌ No wildcard actions (`"Action": "*"` or `"service:*"`)
- ❌ No wildcard principals (`"Principal": "*"`)
- ⚠️  Missing Condition clauses on broad permissions
- ⚠️  Use of NotAction/NotResource (anti-patterns)

---

### 2. Security Log Validator (`validate_security_logs.py`)

Validates security event logs against the schema defined in SECURITY_EXECUTION_SUMMARY.md.

**Usage:**
```bash
# Validate JSON file
python scripts/validate_security_logs.py logs/security_events.json

# Validate JSONL file (one JSON object per line)
python scripts/validate_security_logs.py logs/security_events.jsonl --jsonlines

# Fail on violations (for CI/CD)
python scripts/validate_security_logs.py logs/security_events.json --fail-on-violation

# Strict mode
python scripts/validate_security_logs.py logs/security_events.json --strict
```

**Checks:**
- ✅ All required fields present
- ✅ Timestamp in ISO 8601 UTC format
- ✅ Valid event types
- ✅ Valid actor types, action verbs, result statuses
- ✅ No secrets in logs (sanitization check)
- ⚠️  Missing recommended fields (context, security_context)

**Example Valid Event:**
```json
{
  "timestamp": "2025-11-08T14:30:15.042Z",
  "event_id": "evt-abc123456",
  "event_type": "SECRET_READ",
  "actor": {
    "type": "user",
    "id": "alice@example.com",
    "role": "trader-prod",
    "session_id": "sess-xyz789"
  },
  "action": {
    "verb": "READ",
    "resource": "secret://prod/ibkr/api-key",
    "resource_id": "sec-12345"
  },
  "context": {
    "ip_address": "203.0.113.42",
    "environment": "production"
  },
  "result": {
    "status": "SUCCESS",
    "duration_ms": 42
  }
}
```

---

## CI/CD Integration

These scripts are automatically run in GitHub Actions:

- **IAM Policy Validation:** Runs on PRs that change `iam/policies/**/*.json`
- **Security Log Validation:** Can be added to validate generated logs

See `.github/workflows/security-gates.yml` for configuration.

---

## Pre-commit Hooks

Install pre-commit hooks to run checks locally before committing:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

See `.pre-commit-config.yaml` for hook configuration.

---

## Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `jsonschema` (for schema validation)
- `boto3` (for AWS Access Analyzer integration)
- `pyyaml` (for YAML config validation)

---

## Testing

Test the validators with sample data:

```bash
# Test IAM validator with invalid policy
echo '{"Statement": [{"Action": "*", "Resource": "*"}]}' > test_policy.json
python scripts/validate_iam_policies.py test_policy.json
# Expected: Violations found

# Test log validator with invalid event
echo '{"event_type": "INVALID_TYPE"}' > test_log.json
python scripts/validate_security_logs.py test_log.json
# Expected: Violations found
```

---

## Contributing

When adding new validation scripts:

1. Add script to this directory
2. Update this README
3. Add to `.github/workflows/security-gates.yml` if applicable
4. Add to `.pre-commit-config.yaml` for local validation
5. Write tests

---

**Maintained by:** Security Team
**Last Updated:** 2025-11-08
