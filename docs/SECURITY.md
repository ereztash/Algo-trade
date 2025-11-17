# 🔒 Security Guide - Algo-Trade Platform

**Last Updated:** 2025-11-17
**Security Level:** Production-Ready
**Compliance:** Best Practices for Financial Trading Systems

---

## 📋 Table of Contents

1. [Security Overview](#security-overview)
2. [Secrets Management](#secrets-management)
3. [Secret Scanning & Prevention](#secret-scanning--prevention)
4. [Encryption](#encryption)
5. [Secrets Rotation](#secrets-rotation)
6. [TLS/SSL Configuration](#tlsssl-configuration)
7. [Access Control](#access-control)
8. [Security Best Practices](#security-best-practices)
9. [Incident Response](#incident-response)
10. [Security Checklist](#security-checklist)

---

## 🛡️ Security Overview

The Algo-Trade platform implements **defense-in-depth** security with multiple layers:

### Security Layers

```
┌─────────────────────────────────────────────────────────┐
│                 Layer 1: Prevention                      │
│  • Pre-commit hooks (detect-secrets, GitLeaks)          │
│  • .gitignore protection                                 │
│  • Environment variable templates (.env.example)        │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                 Layer 2: Detection                       │
│  • CI/CD secret scanning (3 tools)                      │
│  • Code security analysis (Bandit)                      │
│  • Dependency vulnerability scanning (Safety)           │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                 Layer 3: Protection                      │
│  • At-rest encryption (Fernet/AES-128)                  │
│  • Vault integration (HashiCorp Vault)                  │
│  • AWS Secrets Manager support                          │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                 Layer 4: Communication                   │
│  • TLS 1.2+ for all network traffic                     │
│  • Kafka SSL/TLS encryption                             │
│  • Certificate-based authentication                      │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│                 Layer 5: Rotation & Audit                │
│  • Automatic secret rotation (90-day policy)            │
│  • Audit logging for all secret access                  │
│  • Rotation alerts and notifications                    │
└─────────────────────────────────────────────────────────┘
```

---

## 🔐 Secrets Management

### What Are Secrets?

Secrets include ANY sensitive information:
- 🔑 API keys (IBKR, Polygon, Alpaca)
- 🔒 Passwords (database, broker, admin)
- 🎟️ Tokens (authentication, webhooks)
- 📜 Certificates and private keys
- 🗝️ Encryption keys

### ⚠️ NEVER Do This

```python
# ❌ WRONG - Hardcoded secret
IBKR_PASSWORD = "MyP@ssw0rd123"  # NEVER!

# ❌ WRONG - Hardcoded API key
API_KEY = "pk_live_51H4F8dE2eSeH123456"  # NEVER!

# ❌ WRONG - Connection string with password
DB_URL = "postgresql://user:password@localhost/db"  # NEVER!
```

### ✅ Always Do This

```python
# ✅ CORRECT - Use environment variables
import os
IBKR_PASSWORD = os.environ.get("IBKR_PASSWORD")
API_KEY = os.environ.get("POLYGON_API_KEY")

# ✅ CORRECT - Use secrets manager
from shared.security import SecretsManager
manager = SecretsManager()
ibkr_password = manager.decrypt(os.environ.get("IBKR_PASSWORD_ENCRYPTED"))

# ✅ CORRECT - Use Vault
from data_plane.config.utils import get_config
config = get_config()  # Automatically loads from Vault if configured
```

---

## 🚫 Secret Scanning & Prevention

### Pre-Commit Hooks (Local Protection)

**Setup (One-time):**
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Test hooks
pre-commit run --all-files
```

**What Gets Scanned:**
- ✅ **detect-secrets** - Comprehensive secret detection
- ✅ **GitLeaks** - Pattern-based scanning
- ✅ **Bandit** - Python security issues
- ✅ **detect-private-key** - SSH/TLS keys
- ✅ **detect-aws-credentials** - AWS keys
- ✅ **Custom checks** - Hardcoded IPs, encryption keys

### CI/CD Scanning (Repository Protection)

Every pull request is automatically scanned with:

1. **GitLeaks** - 15+ secret patterns
2. **detect-secrets** - Entropy-based detection
3. **TruffleHog** - Verified secrets only
4. **Custom regex** - API keys, passwords, tokens

**If secrets are detected:**
- 🚨 PR is automatically BLOCKED
- 🏷️ Labels added: `security-critical`, `secrets-detected`
- 💬 Detailed remediation instructions posted
- ⛔ Cannot merge until resolved

### Handling False Positives

If a secret scanner flags a false positive:

```bash
# Update .secrets.baseline
detect-secrets scan > .secrets.baseline
git add .secrets.baseline
git commit -m "Update secrets baseline"
```

Or add to `.gitleaks.toml`:
```toml
[allowlist]
paths = [
  '''tests/fixtures/dummy_credentials\.json$''',
]
```

---

## 🔐 Encryption

### At-Rest Encryption

All secrets stored locally are encrypted using **Fernet** (AES-128-CBC + HMAC-SHA256).

#### Quick Start

```python
from shared.security import SecretsManager

# Initialize manager (loads key from MASTER_ENCRYPTION_KEY env var)
manager = SecretsManager()

# Encrypt a secret
encrypted = manager.encrypt("my-secret-api-key")
print(encrypted)  # gAAAAABf... (base64-encoded)

# Decrypt
decrypted = manager.decrypt(encrypted)
print(decrypted)  # my-secret-api-key
```

#### Generate Encryption Key

```bash
# Method 1: Use the CLI tool
python shared/security/secrets_manager.py generate-key

# Method 2: Python
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Save to environment
export MASTER_ENCRYPTION_KEY="<generated-key>"
```

#### Encrypt Secrets File

```bash
# Create secrets.json with your secrets
cat > secrets.json <<EOF
{
  "IBKR_PASSWORD": "actual-password",
  "POLYGON_API_KEY": "actual-api-key"
}
EOF

# Encrypt it
python shared/security/secrets_manager.py encrypt-file secrets.json secrets.enc

# Decrypt when needed
python shared/security/secrets_manager.py decrypt-file secrets.enc
```

#### Encrypt/Decrypt in Code

```python
from shared.security import SecretsManager

manager = SecretsManager()

# Encrypt a dictionary
secrets = {
    "IBKR_PASSWORD": "MyP@ssw0rd",
    "API_KEY": "xyz123"
}
manager.encrypt_secrets_file(secrets, "secrets.enc")

# Decrypt back
loaded_secrets = manager.decrypt_secrets_file("secrets.enc")
print(loaded_secrets["IBKR_PASSWORD"])
```

### HashiCorp Vault Integration

**Already implemented!** See `data_plane/config/utils.py:174-313`

#### Setup Vault

```bash
# 1. Install Vault
brew install vault  # macOS
# or download from https://www.vaultproject.io/

# 2. Start Vault dev server (for testing)
vault server -dev

# 3. Set environment variables
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='<dev-token-from-startup>'

# 4. Store secrets
vault kv put secret/algo-trade/broker \
  username="ibkr_user" \
  password="secure_password"

# 5. Enable in application
export DP_USE_VAULT=1
export DP_VAULT_PATH="secret/data/algo-trade/broker"
```

#### Use Vault in Code

```python
# Vault integration is automatic when configured
from data_plane.config.utils import get_config

config = get_config()  # Automatically fetches from Vault
print(config.broker.password)  # Retrieved from Vault
```

### AWS Secrets Manager

```bash
# Install AWS CLI and configure
aws configure

# Create secret
aws secretsmanager create-secret \
    --name algo-trade/production \
    --secret-string '{"IBKR_PASSWORD":"xxx","API_KEY":"yyy"}'

# Enable in application
export USE_AWS_SECRETS_MANAGER=1
export AWS_SECRET_NAME=algo-trade/production
export AWS_REGION=us-east-1
```

---

## 🔄 Secrets Rotation

### Rotation Policy

Default policy: **90-day rotation**

```python
from shared.security import SecretsRotationManager, RotationPolicy

# Create rotation policy
policy = RotationPolicy(
    max_age_days=90,          # Must rotate after 90 days
    rotation_window_days=7,   # Start rotation 7 days before expiry
    auto_rotate=True,         # Automatically rotate
    notify_before_days=14     # Notify 14 days before expiry
)

# Initialize manager
manager = SecretsRotationManager(default_policy=policy)

# Register secrets
manager.register_secret("IBKR_PASSWORD")
manager.register_secret("POLYGON_API_KEY")
manager.register_secret("DATABASE_PASSWORD")
```

### Check Rotation Status

```bash
# CLI tool
python shared/security/rotation.py check

# Example output:
# ⚠️  Secrets needing rotation (2):
#   - IBKR_PASSWORD
#   - POLYGON_API_KEY
```

### Manual Rotation

```python
def update_ibkr_password(secret_name):
    """Generate new password and update IBKR account"""
    new_password = generate_secure_password()

    # Update IBKR account (via API or manually)
    ibkr_client.change_password(new_password)

    return new_password

# Rotate with callback
manager.rotate_secret("IBKR_PASSWORD", update_callback=update_ibkr_password)
```

### Automatic Rotation

```python
# Auto-rotate all secrets that need rotation
results = manager.auto_rotate_secrets()

for secret, success in results.items():
    if success:
        print(f"✅ Rotated: {secret}")
    else:
        print(f"❌ Failed: {secret}")
```

### Rotation Report

```bash
python shared/security/rotation.py report
```

Output:
```json
{
  "generated_at": "2025-11-17T10:00:00Z",
  "total_secrets": 10,
  "by_status": {
    "current": 7,
    "rotating": 1,
    "pending": 2,
    "expired": 0,
    "failed": 0
  },
  "needs_rotation": ["IBKR_PASSWORD", "API_KEY"],
  "expiring_soon": [
    {
      "name": "DATABASE_PASSWORD",
      "expires_at": "2025-12-01T00:00:00Z"
    }
  ]
}
```

---

## 🔐 TLS/SSL Configuration

### Kafka with TLS

```python
from shared.security import TLSConfig, create_kafka_ssl_config

# Configure TLS
tls_config = TLSConfig(
    ca_cert="certs/ca.pem",
    cert_file="certs/client.pem",
    key_file="certs/client-key.pem",
    verify_mode=ssl.CERT_REQUIRED,
    check_hostname=True,
    min_tls_version=ssl.TLSVersion.TLSv1_2
)

# Get Kafka SSL config
kafka_ssl = create_kafka_ssl_config(tls_config)

# Use with Kafka producer
from kafka import KafkaProducer
producer = KafkaProducer(
    bootstrap_servers=['kafka:9093'],
    security_protocol='SSL',
    **kafka_ssl
)
```

### HTTPS Connections

```python
from shared.security import create_ssl_context, TLSConfig
import urllib.request

# Create SSL context
config = TLSConfig(ca_cert="certs/ca.pem")
ctx = create_ssl_context(config)

# Use with urllib
response = urllib.request.urlopen('https://api.example.com', context=ctx)
```

### Environment Variables for TLS

```bash
# .env file
SSL_CA_CERT=certs/ca.pem
SSL_CERT_FILE=certs/client.pem
SSL_KEY_FILE=certs/client-key.pem
SSL_KEY_PASSWORD=optional-password
SSL_VERIFY=REQUIRED
SSL_CHECK_HOSTNAME=true
SSL_MIN_VERSION=1.2
```

### Generate Self-Signed Certificates (Testing)

```bash
# Generate CA
openssl req -x509 -newkey rsa:4096 -keyout ca-key.pem -out ca.pem -days 365 -nodes

# Generate server certificate
openssl req -newkey rsa:4096 -keyout server-key.pem -out server-csr.pem -nodes
openssl x509 -req -in server-csr.pem -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out server.pem -days 365

# Generate client certificate
openssl req -newkey rsa:4096 -keyout client-key.pem -out client-csr.pem -nodes
openssl x509 -req -in client-csr.pem -CA ca.pem -CAkey ca-key.pem -CAcreateserial -out client.pem -days 365
```

---

## 🔑 Access Control

### File Permissions

**Critical files must have restrictive permissions:**

```bash
# Secrets files (owner read/write only)
chmod 600 .env
chmod 600 secrets.enc
chmod 600 *.pem

# Verify permissions
ls -la .env
# Output: -rw------- 1 user group ... .env
```

### Environment Isolation

```bash
# Development
export ENVIRONMENT=development
export ENABLE_LIVE_TRADING=false

# Staging
export ENVIRONMENT=staging
export ENABLE_LIVE_TRADING=false

# Production
export ENVIRONMENT=production
export ENABLE_LIVE_TRADING=true  # Only when ready!
export DP_USE_VAULT=1            # Always use Vault in production
```

---

## 🏆 Security Best Practices

### Development

1. ✅ **Never commit secrets** - Use `.env.example` templates
2. ✅ **Use pre-commit hooks** - Install and run before every commit
3. ✅ **Test with dummy data** - Use fake credentials in tests
4. ✅ **Review dependencies** - Run `safety check` regularly
5. ✅ **Keep secrets encrypted** - Use `SecretsManager` for local storage

### Production

1. 🔒 **Use Vault/AWS Secrets Manager** - NEVER use plaintext .env files
2. 🔄 **Enable secret rotation** - 90-day maximum age
3. 🔐 **Use TLS everywhere** - Kafka, APIs, databases
4. 📝 **Audit all secret access** - Log who accessed what when
5. 🚨 **Monitor for leaks** - Set up alerts for exposed secrets
6. 🔑 **Use IAM roles** - Prefer IAM over static credentials (AWS)
7. 🛡️ **Principle of least privilege** - Grant minimal necessary permissions
8. 📊 **Regular security audits** - Review access logs monthly

### Emergency Procedures

**If a secret is exposed:**

1. **IMMEDIATE:** Revoke/rotate the compromised secret
2. **WITHIN 1 HOUR:** Assess impact (what systems, data exposed?)
3. **WITHIN 24 HOURS:** Update all dependent systems
4. **WITHIN 1 WEEK:** Complete post-incident review

---

## 🚨 Incident Response

### Secret Leak Response Plan

**Severity Levels:**

- **P0 (Critical):** Production API keys, database passwords, broker credentials
- **P1 (High):** Staging credentials, encryption keys
- **P2 (Medium):** Development credentials
- **P3 (Low):** Deprecated/unused credentials

**Response Timeline:**

| Severity | Detection | Revocation | Rotation | Audit | Total |
|----------|-----------|------------|----------|-------|-------|
| P0       | 0 min     | 15 min     | 1 hour   | 1 day | <24h  |
| P1       | 1 hour    | 4 hours    | 8 hours  | 3 days| <5 days|
| P2       | 4 hours   | 1 day      | 2 days   | 1 week| <2 weeks|
| P3       | 1 day     | 3 days     | 1 week   | 2 weeks| <1 month|

**Action Checklist:**

- [ ] Immediately revoke exposed secret
- [ ] Generate and deploy new secret
- [ ] Check logs for unauthorized usage
- [ ] Notify affected parties (if applicable)
- [ ] Update documentation
- [ ] Conduct root cause analysis
- [ ] Implement preventive measures

---

## ✅ Security Checklist

### Pre-Production Checklist

#### Secrets Management
- [ ] `.env.example` exists and is up-to-date
- [ ] No secrets in `.env` committed to git
- [ ] `.gitignore` protects `.env`, `secrets.yaml`, `.secrets/`
- [ ] Vault or AWS Secrets Manager configured
- [ ] `MASTER_ENCRYPTION_KEY` generated and stored securely
- [ ] All production secrets stored in Vault/AWS Secrets Manager

#### Secret Scanning
- [ ] Pre-commit hooks installed (`pre-commit install`)
- [ ] `.secrets.baseline` exists and is current
- [ ] GitLeaks configuration (`.gitleaks.toml`) present
- [ ] CI/CD secret scanning enabled
- [ ] All team members trained on secret handling

#### Encryption
- [ ] Encryption keys generated and stored securely
- [ ] At-rest encryption enabled for all sensitive data
- [ ] TLS 1.2+ enabled for all network traffic
- [ ] Kafka configured with SSL/TLS
- [ ] Database connections use TLS

#### Rotation
- [ ] Rotation policies defined (90-day default)
- [ ] Rotation manager initialized with all secrets
- [ ] Automatic rotation enabled (where applicable)
- [ ] Rotation alerts configured
- [ ] Rotation runbook documented

#### Access Control
- [ ] File permissions set correctly (600 for secrets)
- [ ] Environment isolation configured
- [ ] IAM roles used instead of static credentials (AWS)
- [ ] Principle of least privilege applied
- [ ] Access audit logging enabled

#### Monitoring & Response
- [ ] Secret access logging enabled
- [ ] Alerts configured for secret exposure
- [ ] Incident response plan documented
- [ ] Team trained on incident response
- [ ] Regular security audits scheduled

---

## 📚 Additional Resources

- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [AWS Secrets Manager Guide](https://docs.aws.amazon.com/secretsmanager/)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [NIST Cryptographic Standards](https://csrc.nist.gov/projects/cryptographic-standards-and-guidelines)

---

## 🆘 Support

**Security Issues:** Report immediately to security team
**Questions:** Check this guide first, then ask in #security channel
**Updates:** This document is updated with each security enhancement

---

**Remember: Security is everyone's responsibility!** 🔒

