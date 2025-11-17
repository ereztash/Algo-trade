# Secrets Management & Security Guide

## Overview

The Algo-Trade platform implements a comprehensive, layered secrets management system designed to meet enterprise security standards while maintaining flexibility for different deployment environments.

## Table of Contents

1. [Architecture](#architecture)
2. [Configuration Methods](#configuration-methods)
3. [Setup Guide](#setup-guide)
4. [Best Practices](#best-practices)
5. [Audit Logging](#audit-logging)
6. [Security Considerations](#security-considerations)
7. [Troubleshooting](#troubleshooting)

---

## Architecture

### Multi-Layered Security Model

The secrets management system uses a **priority-based layering approach**:

```
Priority (Highest to Lowest):
1. Environment Variables (DP_*)
2. HashiCorp Vault
3. Encrypted Local File (Fernet)
4. YAML Configuration File (not recommended for secrets)
```

Each layer can override values from lower priority layers, allowing flexible configuration for different environments.

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────────────┐
│            Config Loader (utils.py)                          │
│  - Merges configs from all sources                           │
│  - Validates with Pydantic                                   │
│  - Enforces priority order                                   │
└──────────────┬────────────────┬────────────────┬────────────┘
               │                │                │
       ┌───────▼─────┐  ┌──────▼──────┐  ┌─────▼──────┐
       │   Vault     │  │  Encrypted  │  │    Env     │
       │ Integration │  │    Local    │  │  Variables │
       │  (hvac)     │  │   Secrets   │  │            │
       └─────────────┘  └─────────────┘  └────────────┘
               │                │                │
       ┌───────▼────────────────▼────────────────▼────────────┐
       │           Audit Logger (audit_logger.py)             │
       │  - Tracks all secret access                          │
       │  - Masks sensitive values                            │
       │  - JSON-structured logs                              │
       └──────────────────────────────────────────────────────┘
```

---

## Configuration Methods

### Method 1: Environment Variables (Recommended for Quick Setup)

**Best for:** Development, CI/CD, containerized deployments

**Setup:**

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set required values:
   ```bash
   # Broker connection
   DP_BROKER__HOST=127.0.0.1
   DP_BROKER__PORT=7497
   DP_IBKR__CLIENT_ID=1

   # Enable audit logging
   DP_AUDIT_LOGGING_ENABLED=true
   ```

3. Load environment:
   ```bash
   source .env  # Or use direnv, dotenv, etc.
   ```

**Pros:**
- Simple and fast setup
- Works with containers and CI/CD
- No additional dependencies

**Cons:**
- Less secure (visible in process list)
- No encryption at rest
- Manual rotation required

---

### Method 2: Encrypted Local File (Recommended for Development)

**Best for:** Local development, small teams, non-production environments

**Setup:**

1. Install cryptography library:
   ```bash
   pip install cryptography
   ```

2. Generate encryption key:
   ```bash
   python -m data_plane.config.secrets_manager generate-key
   ```

   Output:
   ```
   Generated encryption key:
   gAAAAABhkF7x9z... (base64 string)

   Add this to your .env file:
   DP_SECRETS_ENCRYPTION_KEY=gAAAAABhkF7x9z...
   ```

3. Add key to `.env`:
   ```bash
   echo "DP_SECRETS_ENCRYPTION_KEY=gAAAAABhkF7x9z..." >> .env
   echo "DP_USE_ENCRYPTED_SECRETS=1" >> .env
   ```

4. Add secrets:
   ```bash
   python -m data_plane.config.secrets_manager set broker.host 127.0.0.1
   python -m data_plane.config.secrets_manager set broker.port 7497
   python -m data_plane.config.secrets_manager set broker.password "your-password"
   ```

5. Verify:
   ```bash
   python -m data_plane.config.secrets_manager list
   python -m data_plane.config.secrets_manager validate
   ```

**CLI Commands:**

```bash
# Generate encryption key
python -m data_plane.config.secrets_manager generate-key

# Set a secret
python -m data_plane.config.secrets_manager set <key> <value>

# Get a secret
python -m data_plane.config.secrets_manager get <key>

# List all secrets
python -m data_plane.config.secrets_manager list

# Delete a secret
python -m data_plane.config.secrets_manager delete <key>

# Validate secrets file
python -m data_plane.config.secrets_manager validate

# Rotate encryption key
python -m data_plane.config.secrets_manager rotate-key --new-key <new-key>
```

**Pros:**
- Encrypted at rest (AES-128 CBC + HMAC)
- Simple CLI management
- No external dependencies
- Version control safe (.secrets/ is gitignored)

**Cons:**
- Key must be stored securely
- Not suitable for production at scale
- Manual key rotation
- Single point of failure

---

### Method 3: HashiCorp Vault (Recommended for Production)

**Best for:** Production deployments, enterprise environments, regulated industries

**Setup:**

1. Install Vault and hvac:
   ```bash
   # Install Vault server (see https://www.vaultproject.io/downloads)
   # Install Python client
   pip install hvac
   ```

2. Configure Vault environment:
   ```bash
   export VAULT_ADDR=https://vault.example.com:8200
   export VAULT_TOKEN=s.xxxxxxxxxxxxx
   export DP_USE_VAULT=1
   export DP_VAULT_PATH=secret/data/algo-trade/broker
   ```

3. Store secrets in Vault:
   ```bash
   # Using Vault CLI
   vault kv put secret/algo-trade/broker \
     host=127.0.0.1 \
     port=7497 \
     username=trader \
     password=secure-password

   # Verify
   vault kv get secret/algo-trade/broker
   ```

4. (Optional) Separate password path:
   ```bash
   vault kv put secret/algo-trade/broker-password \
     password=secure-password

   export DP_VAULT_PATH_PASSWORD=secret/data/algo-trade/broker-password
   ```

**Vault KV Version Support:**

The system supports both KV v1 and v2:

```python
# KV v2 (recommended - includes versioning)
DP_VAULT_PATH=secret/data/algo-trade/broker

# KV v1 (legacy)
DP_VAULT_PATH=secret/algo-trade/broker
```

**Pros:**
- Enterprise-grade security
- Automatic encryption
- Audit logging built-in
- Key rotation support
- Fine-grained access control
- Dynamic secrets support
- Centralized management

**Cons:**
- Requires Vault infrastructure
- More complex setup
- Additional operational overhead

---

## Setup Guide

### Quick Start (Development)

For local development with encrypted secrets:

```bash
# 1. Clone and setup
git clone <repo>
cd Algo-trade

# 2. Install dependencies
pip install -r requirements.txt
pip install cryptography  # For encrypted secrets

# 3. Copy environment template
cp .env.example .env

# 4. Generate encryption key
python -m data_plane.config.secrets_manager generate-key

# 5. Add key to .env (use output from step 4)
echo "DP_SECRETS_ENCRYPTION_KEY=<generated-key>" >> .env
echo "DP_USE_ENCRYPTED_SECRETS=1" >> .env
echo "DP_AUDIT_LOGGING_ENABLED=true" >> .env

# 6. Add secrets
python -m data_plane.config.secrets_manager set broker.host 127.0.0.1
python -m data_plane.config.secrets_manager set broker.port 7497
python -m data_plane.config.secrets_manager set broker.password "your-password"

# 7. Verify
python -m data_plane.config.secrets_manager list
python -c "from data_plane.config.utils import get_config; print(get_config())"

# 8. Run application
python -m algo_trade.main
```

### Production Deployment with Vault

```bash
# 1. Setup Vault (one-time)
vault secrets enable -path=secret kv-v2
vault policy write algo-trade-policy - <<EOF
path "secret/data/algo-trade/*" {
  capabilities = ["read", "list"]
}
EOF

# 2. Create app token
vault token create -policy=algo-trade-policy

# 3. Store secrets in Vault
vault kv put secret/algo-trade/broker \
  host=prod-broker.example.com \
  port=4001 \
  username=prod-trader \
  password=<secure-password>

# 4. Configure application
export VAULT_ADDR=https://vault.example.com:8200
export VAULT_TOKEN=<token-from-step-2>
export DP_USE_VAULT=1
export DP_VAULT_PATH=secret/data/algo-trade/broker
export DP_ENVIRONMENT=production
export DP_AUDIT_LOGGING_ENABLED=true
export DP_SECURITY__ENFORCE_HTTPS=true

# 5. Deploy application
python -m algo_trade.main
```

### Docker Deployment

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

# Vault configuration (from environment or secrets)
ENV DP_USE_VAULT=1
ENV DP_AUDIT_LOGGING_ENABLED=true
ENV DP_ENVIRONMENT=production

CMD ["python", "-m", "algo_trade.main"]
```

```bash
# Run with environment variables
docker run -e VAULT_ADDR=https://vault:8200 \
           -e VAULT_TOKEN=$VAULT_TOKEN \
           -e DP_VAULT_PATH=secret/data/algo-trade/broker \
           algo-trade:latest
```

---

## Best Practices

### 1. Never Commit Secrets

**Always ensure these are in `.gitignore`:**
- `.env`
- `.secrets/`
- `secrets.yaml`
- `*.key`
- `*.pem`

**Check before committing:**
```bash
git diff --cached | grep -i "password\|secret\|token"
```

### 2. Use Different Credentials per Environment

```bash
# Development
DP_ENVIRONMENT=development
DP_BROKER__PORT=7497  # Paper trading

# Production
DP_ENVIRONMENT=production
DP_BROKER__PORT=4001  # Live trading
```

### 3. Enable Read-Only Mode for Analytics

For applications that only need to read data:

```bash
DP_IBKR__READONLY=true
DP_EXECUTION__ENABLED=false
```

### 4. Rotate Secrets Regularly

**For Encrypted Local File:**
```bash
# Generate new key
NEW_KEY=$(python -m data_plane.config.secrets_manager generate-key | tail -1)

# Rotate
python -m data_plane.config.secrets_manager rotate-key --new-key "$NEW_KEY"

# Update .env
echo "DP_SECRETS_ENCRYPTION_KEY=$NEW_KEY" >> .env
```

**For Vault:**
```bash
# Vault handles rotation automatically
vault write -force /auth/token/renew-self
```

### 5. Monitor Audit Logs

```bash
# View recent secret access
tail -f logs/security_audit.log | jq .

# Search for failed attempts
grep '"success": false' logs/security_audit.log | jq .

# Count access by source
jq -r '.details.source' logs/security_audit.log | sort | uniq -c
```

### 6. Use Principle of Least Privilege

```bash
# Read-only for monitoring apps
DP_IBKR__READONLY=true

# Limit max position risk
DP_EXECUTION__MAX_POSITION_RISK=0.05  # 5% max
```

### 7. Validate Configuration on Startup

```python
from data_plane.config.utils import smoke_test, health_check

# Run smoke test
success, message = smoke_test()
if not success:
    raise RuntimeError(f"Configuration validation failed: {message}")

# Check dependencies
status = health_check(strict=True)
print(f"Health check: {status}")
```

---

## Audit Logging

### Overview

All secrets access is automatically logged to `logs/security_audit.log` with:
- Timestamp (UTC)
- Event type
- Source (vault, encrypted_file, environment, config)
- Success/failure status
- Masked values (configurable)
- Request context

### Log Format

```json
{
  "timestamp": "2025-01-15T10:30:45.123456Z",
  "event_type": "secret_access",
  "success": true,
  "details": {
    "secret_key": "broker.password",
    "source": "vault",
    "value_masked": "***word",
    "value_hash": "a3d5e8f2b1c4d6e7"
  },
  "process_id": 12345,
  "environment": "production"
}
```

### Event Types

- `secret_access` - Secret read operation
- `secret_write` - Secret write/update
- `secret_delete` - Secret deletion
- `config_read` - Configuration file read
- `config_write` - Configuration file write
- `vault_access` - Vault API call
- `auth_success` - Successful authentication
- `auth_failure` - Failed authentication
- `permission_denied` - Access denied
- `validation_failure` - Validation error

### Configuration

```bash
# Enable audit logging
DP_AUDIT_LOGGING_ENABLED=true

# Set log file location
DP_AUDIT_LOG_FILE=logs/security_audit.log

# Mask sensitive values (recommended)
DP_AUDIT_MASK_SECRETS=true
```

### Querying Logs

```bash
# All failed operations
jq 'select(.success == false)' logs/security_audit.log

# Vault access attempts
jq 'select(.event_type == "vault_access")' logs/security_audit.log

# Recent secret access (last hour)
jq --arg time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S)" \
   'select(.timestamp > $time and .event_type == "secret_access")' \
   logs/security_audit.log

# Group by source
jq -r '.details.source' logs/security_audit.log | sort | uniq -c | sort -rn
```

### SIEM Integration

Audit logs use structured JSON format for easy SIEM integration:

**Splunk:**
```splunk
source="logs/security_audit.log" sourcetype="_json"
| stats count by event_type, details.source
```

**ELK Stack:**
```json
{
  "input": {
    "type": "log",
    "paths": ["/app/logs/security_audit.log"],
    "json.keys_under_root": true
  }
}
```

---

## Security Considerations

### Threat Model

**Protected Against:**
- ✅ Accidental credential exposure in version control
- ✅ Plaintext secrets in configuration files
- ✅ Unauthorized access to secrets (with Vault)
- ✅ Secrets in application logs (masking)
- ✅ Process memory dumps (encrypted at rest)

**Not Protected Against:**
- ❌ Compromised encryption keys
- ❌ Root/admin access to host system
- ❌ Runtime memory inspection (by privileged user)
- ❌ Social engineering attacks
- ❌ Supply chain attacks

### Key Security Features

1. **Encryption at Rest**
   - Fernet encryption (AES-128 CBC + HMAC-SHA256)
   - File permissions set to 0600 (user-only)

2. **Encryption in Transit**
   - HTTPS enforced for Vault communication
   - TLS certificate validation

3. **Access Control**
   - Vault ACLs and policies
   - File system permissions
   - Read-only mode for non-execution tasks

4. **Audit Trail**
   - All secret access logged
   - Tamper-evident JSON logs
   - Separate audit log file

5. **Defense in Depth**
   - Multiple configuration layers
   - Validation at every stage
   - Fail-secure defaults

### Compliance

**PCI DSS:**
- Requirement 3.4: Encryption of cardholder data ✅
- Requirement 8.2: Multi-factor authentication (Vault) ✅
- Requirement 10: Audit logging ✅

**SOC 2:**
- CC6.1: Logical access controls ✅
- CC6.6: Encryption ✅
- CC7.2: System monitoring ✅

**GDPR:**
- Article 32: Security of processing ✅
- Article 32: Encryption ✅
- Article 30: Records of processing (audit logs) ✅

---

## Troubleshooting

### Common Issues

#### 1. "Invalid encryption key or corrupted secrets file"

**Cause:** Wrong encryption key or corrupted file

**Solution:**
```bash
# Check if key is correct
python -m data_plane.config.secrets_manager validate

# If corrupted, regenerate and re-add secrets
mv .secrets/encrypted_secrets.bin .secrets/encrypted_secrets.bin.backup
python -m data_plane.config.secrets_manager set broker.host 127.0.0.1
```

#### 2. "Vault client not authenticated"

**Cause:** Invalid or expired VAULT_TOKEN

**Solution:**
```bash
# Check token
vault token lookup

# Renew token
vault token renew

# Create new token
vault token create -policy=algo-trade-policy
```

#### 3. "cryptography library required"

**Cause:** Missing cryptography package

**Solution:**
```bash
pip install cryptography
```

#### 4. "Config validation error"

**Cause:** Invalid configuration values

**Solution:**
```python
# Run in strict mode to see validation errors
from data_plane.config.utils import get_config
config = get_config(strict=True)
```

#### 5. Secrets not loading

**Debug:**
```python
import os
from data_plane.config.utils import get_config

# Check environment
print("Vault enabled:", os.environ.get("DP_USE_VAULT"))
print("Encrypted enabled:", os.environ.get("DP_USE_ENCRYPTED_SECRETS"))

# Try loading
config = get_config()
print(f"Broker host: {config.broker.host}")
print(f"Broker port: {config.broker.port}")

# Check audit logs
import subprocess
subprocess.run(["tail", "-20", "logs/security_audit.log"])
```

### Testing Configuration

```python
#!/usr/bin/env python3
"""Test secrets configuration."""

import os
from data_plane.config.utils import get_config, smoke_test, health_check

def test_config():
    """Test configuration loading."""
    print("=" * 60)
    print("Configuration Test")
    print("=" * 60)

    # Health check
    print("\n1. Health Check:")
    status = health_check()
    print(f"   Modules: {status['modules']}")
    print(f"   Packages: {status['env']}")

    # Smoke test
    print("\n2. Smoke Test:")
    success, message = smoke_test()
    print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
    print(f"   Message: {message}")

    # Load config
    print("\n3. Configuration:")
    config = get_config()
    print(f"   Broker: {config.broker.name}")
    print(f"   Host: {config.broker.host}")
    print(f"   Port: {config.broker.port}")
    print(f"   Paper: {config.broker.paper}")
    print(f"   Password set: {'Yes' if config.broker.password else 'No'}")

    # Check secrets source
    print("\n4. Secrets Source:")
    if os.environ.get("DP_USE_VAULT") == "1":
        print("   ✓ Using Vault")
        print(f"   Path: {os.environ.get('DP_VAULT_PATH')}")
    elif os.environ.get("DP_USE_ENCRYPTED_SECRETS") == "1":
        print("   ✓ Using Encrypted Local File")
        print(f"   File: {os.environ.get('DP_ENCRYPTED_SECRETS_FILE')}")
    else:
        print("   ✓ Using Environment Variables / YAML")

    print("\n" + "=" * 60)
    print("✅ Configuration test complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_config()
```

---

## Additional Resources

- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [Cryptography Library](https://cryptography.io/)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [12-Factor App: Config](https://12factor.net/config)

---

## Support

For issues or questions:
1. Check audit logs: `logs/security_audit.log`
2. Run smoke test: `python -c "from data_plane.config.utils import smoke_test; print(smoke_test())"`
3. Review this documentation
4. Open an issue on GitHub

---

**Last Updated:** 2025-01-15
**Version:** 1.0.0
