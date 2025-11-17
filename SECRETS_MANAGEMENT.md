# Secrets Management & Security Guide

**Version:** 1.0
**Status:** Pre-Production (P1 - Required before production)
**Last Updated:** 2025-11-16
**Owner:** Security Team / DevOps

---

## Table of Contents

1. [Overview](#overview)
2. [Local Development Setup](#local-development-setup)
3. [Staging Environment](#staging-environment)
4. [Production Environment](#production-environment)
5. [HashiCorp Vault Setup](#hashicorp-vault-setup)
6. [AWS Secrets Manager Setup](#aws-secrets-manager-setup)
7. [Kubernetes Secrets](#kubernetes-secrets)
8. [Secrets Rotation Policy](#secrets-rotation-policy)
9. [Incident Response](#incident-response)
10. [Compliance & Audit](#compliance--audit)

---

## Overview

### Purpose

This document defines how secrets (credentials, API keys, passwords) are managed across all environments in the Algo-Trade system.

### Security Principles

1. **Never commit secrets to git** - Use environment variables or secret managers
2. **Least privilege** - Grant minimum required permissions
3. **Encryption at rest** - All secrets encrypted when stored
4. **Encryption in transit** - TLS/SSL for all secret transfers
5. **Audit logging** - Track all secret access
6. **Regular rotation** - Rotate credentials quarterly (minimum)
7. **Separation of duties** - Different secrets for dev/staging/prod

### Secrets Maturity Model

| Environment | Method | Encryption | Rotation | Audit | Status |
|-------------|--------|------------|----------|-------|--------|
| **Local Development** | `.env` file | ❌ No | Manual | ❌ No | ✅ Current |
| **Staging** | Vault/AWS Secrets | ✅ Yes | Manual | ✅ Yes | 🟡 Planned |
| **Production** | Vault/AWS Secrets | ✅ Yes | Automated | ✅ Yes | 🟡 Planned |

---

## Local Development Setup

### 1. Initial Setup

```bash
# Clone repository
git clone https://github.com/ereztash/Algo-trade.git
cd Algo-trade

# Copy environment template
cp .env.example .env

# Edit with your local values
nano .env  # or vim, code, etc.
```

### 2. Configure Local Environment

**Edit `.env` file:**

```bash
# Basic configuration for paper trading
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# IBKR Paper Trading (no credentials needed)
IBKR_HOST=127.0.0.1
IBKR_PORT=4002          # TWS Paper port: 7497 | Gateway Paper port: 4002
IBKR_CLIENT_ID=1
IBKR_ACCOUNT=DU1234567  # Your paper trading account
IBKR_READ_ONLY=true     # Stage 6 - read-only mode

# Kafka (local Docker)
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# Disable Vault for local dev
DP_USE_VAULT=0
```

### 3. Verify Setup

```bash
# Check .env is gitignored
git status .env
# Should output: nothing (file is ignored)

# Verify environment loads
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('IBKR_PORT'))"
# Should output: 4002

# Test IBKR connection (with TWS/Gateway running)
python -m data_plane.connectors.ibkr.client
```

### 4. Security Checklist for Local Dev

- [ ] `.env` file is NOT committed to git
- [ ] `.env` file has restrictive permissions: `chmod 600 .env`
- [ ] No secrets in configuration YAML files
- [ ] No secrets in log files
- [ ] Paper trading mode enabled (`IBKR_READ_ONLY=true`)

---

## Staging Environment

### Purpose

Staging environment mirrors production but uses:
- Paper trading accounts
- Separate credentials
- Lower rate limits

### Setup with HashiCorp Vault

**Architecture:**

```
Staging Server
├── Vault Agent (sidecar)
│   ├── Auto-auth with AppRole
│   ├── Fetches secrets from Vault
│   └── Writes to /vault/secrets/
└── Algo-Trade Application
    ├── Reads from /vault/secrets/config.json
    └── Falls back to ENV vars
```

**Configuration:**

```bash
# Enable Vault
export DP_USE_VAULT=1
export VAULT_ADDR=https://vault.yourcompany.com
export VAULT_TOKEN=$(cat /vault/token)  # Auto-injected by Vault agent
export DP_VAULT_PATH=secret/data/algo-trade/staging
```

### Setup with AWS Secrets Manager

```bash
# Enable AWS Secrets Manager
export USE_AWS_SECRETS=true
export AWS_REGION=us-east-1
export AWS_SECRET_NAME=algo-trade/staging

# Use IAM role (recommended)
# No need for AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
```

**Python code integration** (already exists in `data_plane/config/utils.py`):

```python
import boto3
import json

def fetch_secret_from_aws(secret_name: str, region: str = "us-east-1") -> dict:
    """Fetch secret from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name=region)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])
```

---

## Production Environment

### Requirements

Production MUST use:
1. **Secret manager** (Vault or AWS Secrets Manager)
2. **Encrypted storage** (AES-256)
3. **Automated rotation** (quarterly minimum)
4. **Audit logging** (all access logged)
5. **Least privilege** (read-only where possible)
6. **Multi-factor authentication** (for secret access)

### Secrets Inventory

| Secret Type | Location | Rotation | Owner |
|-------------|----------|----------|-------|
| IBKR Live Credentials | Vault: `secret/ibkr/live` | Quarterly | Trading Ops |
| IBKR API Keys | Vault: `secret/ibkr/api` | Quarterly | Trading Ops |
| Kafka SASL Credentials | Vault: `secret/kafka/prod` | Annual | DevOps |
| Database Password | Vault: `secret/db/prod` | Quarterly | DBA |
| Grafana API Key | AWS Secrets | Annual | Monitoring Team |
| PagerDuty API Key | AWS Secrets | Annual | SRE Team |
| Email SMTP Password | AWS Secrets | Annual | SRE Team |

### Infrastructure as Code

**Terraform example** for AWS Secrets Manager:

```hcl
# terraform/secrets.tf
resource "aws_secretsmanager_secret" "ibkr_live" {
  name        = "algo-trade/production/ibkr"
  description = "IBKR Live Trading Credentials"

  rotation_rules {
    automatically_after_days = 90
  }
}

resource "aws_secretsmanager_secret_version" "ibkr_live" {
  secret_id = aws_secretsmanager_secret.ibkr_live.id
  secret_string = jsonencode({
    username = var.ibkr_username
    password = var.ibkr_password
    api_key  = var.ibkr_api_key
  })
}

# IAM policy for application
resource "aws_iam_policy" "secrets_read" {
  name        = "AlgoTradeSecretsRead"
  description = "Read-only access to Algo-Trade secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.ibkr_live.arn
      }
    ]
  })
}
```

---

## HashiCorp Vault Setup

### 1. Vault Server Installation

```bash
# Install Vault (Ubuntu/Debian)
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install vault

# Start Vault server (dev mode for testing)
vault server -dev

# Production mode (separate terminal)
vault server -config=/etc/vault/config.hcl
```

**Production config** (`/etc/vault/config.hcl`):

```hcl
storage "raft" {
  path    = "/opt/vault/data"
  node_id = "vault-1"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_cert_file = "/etc/vault/tls/vault.crt"
  tls_key_file  = "/etc/vault/tls/vault.key"
}

api_addr = "https://vault.yourcompany.com:8200"
cluster_addr = "https://vault.yourcompany.com:8201"
ui = true

# Enable audit logging
audit {
  type = "file"
  path = "/var/log/vault/audit.log"
}
```

### 2. Initialize Vault

```bash
# Initialize (SAVE UNSEAL KEYS SECURELY!)
vault operator init -key-shares=5 -key-threshold=3

# Unseal (3 out of 5 keys required)
vault operator unseal <key1>
vault operator unseal <key2>
vault operator unseal <key3>

# Authenticate
export VAULT_TOKEN=<root-token>
vault login
```

### 3. Create Secrets

```bash
# Enable KV v2 engine
vault secrets enable -path=secret kv-v2

# Store IBKR credentials (production)
vault kv put secret/algo-trade/production/ibkr \
  username="YOUR_IBKR_USERNAME" \
  password="YOUR_IBKR_PASSWORD" \
  api_key="YOUR_API_KEY" \
  account="U1234567" \
  host="127.0.0.1" \
  port="4001"

# Store IBKR credentials (staging - paper)
vault kv put secret/algo-trade/staging/ibkr \
  account="DU1234567" \
  host="127.0.0.1" \
  port="4002" \
  paper="true"

# Verify
vault kv get secret/algo-trade/production/ibkr
```

### 4. Configure AppRole Authentication

```bash
# Enable AppRole
vault auth enable approle

# Create policy
vault policy write algo-trade-prod - <<EOF
path "secret/data/algo-trade/production/*" {
  capabilities = ["read"]
}
EOF

# Create AppRole
vault write auth/approle/role/algo-trade-prod \
  token_policies="algo-trade-prod" \
  token_ttl=1h \
  token_max_ttl=4h

# Get RoleID and SecretID
vault read auth/approle/role/algo-trade-prod/role-id
vault write -f auth/approle/role/algo-trade-prod/secret-id
```

### 5. Application Integration

**Python code** (already exists in `data_plane/config/utils.py`):

```python
import hvac
import os

def _fetch_secret_from_vault_hvac(vault_path: str) -> dict:
    """Fetch secret from Vault using hvac client."""
    client = hvac.Client(url=os.getenv("VAULT_ADDR"))

    # Authenticate with AppRole (production)
    if role_id := os.getenv("VAULT_ROLE_ID"):
        secret_id = os.getenv("VAULT_SECRET_ID")
        client.auth.approle.login(role_id, secret_id)
    # Or use token (development)
    elif token := os.getenv("VAULT_TOKEN"):
        client.token = token

    # Fetch secret (KV v2)
    response = client.secrets.kv.v2.read_secret_version(path=vault_path)
    return response.get("data", {}).get("data", {})

# Usage
if os.getenv("DP_USE_VAULT") == "1":
    secrets = _fetch_secret_from_vault_hvac("algo-trade/production/ibkr")
    ibkr_config = {
        "username": secrets.get("username"),
        "password": secrets.get("password"),
        "api_key": secrets.get("api_key"),
    }
```

---

## AWS Secrets Manager Setup

### 1. Create Secret via AWS CLI

```bash
# Install AWS CLI
pip install awscli

# Configure credentials (or use IAM role)
aws configure

# Create secret
aws secretsmanager create-secret \
  --name algo-trade/production/ibkr \
  --description "IBKR Live Trading Credentials" \
  --secret-string '{
    "username": "YOUR_IBKR_USERNAME",
    "password": "YOUR_IBKR_PASSWORD",
    "api_key": "YOUR_API_KEY",
    "account": "U1234567",
    "host": "127.0.0.1",
    "port": "4001"
  }'

# Enable automatic rotation (optional)
aws secretsmanager rotate-secret \
  --secret-id algo-trade/production/ibkr \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:123456789012:function:SecretsManagerRotation \
  --rotation-rules AutomaticallyAfterDays=90
```

### 2. Python Integration

```python
import boto3
import json

def load_secrets_from_aws(secret_name: str, region: str = "us-east-1") -> dict:
    """Load secrets from AWS Secrets Manager."""
    client = boto3.client('secretsmanager', region_name=region)

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error fetching secret {secret_name}: {e}")
        return {}

# Usage in data_plane/config/utils.py
if os.getenv("USE_AWS_SECRETS") == "true":
    secrets = load_secrets_from_aws(os.getenv("AWS_SECRET_NAME"))
    ibkr_config = {
        "username": secrets.get("username"),
        "password": secrets.get("password"),
        "api_key": secrets.get("api_key"),
    }
```

### 3. IAM Permissions

**EC2 Instance Role** (recommended):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:algo-trade/production/*"
    }
  ]
}
```

---

## Kubernetes Secrets

### 1. Create Kubernetes Secret

```bash
# From literal values
kubectl create secret generic algo-trade-ibkr \
  --from-literal=username=YOUR_IBKR_USERNAME \
  --from-literal=password=YOUR_IBKR_PASSWORD \
  --from-literal=api-key=YOUR_API_KEY \
  -n algo-trade

# From .env file
kubectl create secret generic algo-trade-env \
  --from-env-file=.env \
  -n algo-trade

# Verify
kubectl get secrets -n algo-trade
kubectl describe secret algo-trade-ibkr -n algo-trade
```

### 2. Mount Secret in Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: algo-trade-data-plane
  namespace: algo-trade
spec:
  template:
    spec:
      containers:
      - name: data-plane
        image: algo-trade/data-plane:latest
        env:
        # Load from secret
        - name: IBKR_USERNAME
          valueFrom:
            secretKeyRef:
              name: algo-trade-ibkr
              key: username
        - name: IBKR_PASSWORD
          valueFrom:
            secretKeyRef:
              name: algo-trade-ibkr
              key: password

        # Or mount entire secret as file
        volumeMounts:
        - name: secrets
          mountPath: /secrets
          readOnly: true

      volumes:
      - name: secrets
        secret:
          secretName: algo-trade-ibkr
          defaultMode: 0400  # Read-only for owner
```

### 3. External Secrets Operator (Recommended)

Sync secrets from Vault/AWS to Kubernetes automatically:

```yaml
# k8s/external-secret.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: algo-trade-ibkr
  namespace: algo-trade
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: SecretStore

  target:
    name: algo-trade-ibkr
    creationPolicy: Owner

  data:
  - secretKey: username
    remoteRef:
      key: secret/algo-trade/production/ibkr
      property: username

  - secretKey: password
    remoteRef:
      key: secret/algo-trade/production/ibkr
      property: password
```

---

## Secrets Rotation Policy

### Rotation Schedule

| Secret Type | Frequency | Method | Owner |
|-------------|-----------|--------|-------|
| **IBKR Live Credentials** | Quarterly (90 days) | Manual | Trading Ops |
| **IBKR API Keys** | Quarterly (90 days) | Manual | Trading Ops |
| **Database Passwords** | Quarterly (90 days) | Automated | DBA |
| **Kafka SASL** | Annually | Manual | DevOps |
| **API Keys (3rd party)** | Annually | Manual | Dev Team |
| **SSH Keys** | Annually | Manual | DevOps |
| **TLS/SSL Certificates** | Before expiry (90 days) | Automated (Let's Encrypt) | DevOps |

### Rotation Procedure

**For IBKR Credentials:**

1. **Generate new credentials** in IBKR portal
2. **Update in Vault/AWS:**
   ```bash
   # Vault
   vault kv put secret/algo-trade/production/ibkr \
     username="NEW_USERNAME" \
     password="NEW_PASSWORD" \
     api_key="NEW_API_KEY"

   # AWS Secrets Manager
   aws secretsmanager update-secret \
     --secret-id algo-trade/production/ibkr \
     --secret-string '{"username":"NEW_USERNAME","password":"NEW_PASSWORD","api_key":"NEW_API_KEY"}'
   ```
3. **Test new credentials** in staging
4. **Rolling restart** of production services
5. **Verify** trading continues without disruption
6. **Revoke old credentials** in IBKR portal
7. **Document** in changelog

### Automated Rotation (AWS Lambda)

```python
# lambda/rotate_ibkr_secret.py
import boto3
import json

def lambda_handler(event, context):
    """Rotate IBKR credentials in AWS Secrets Manager."""
    client = boto3.client('secretsmanager')
    secret_id = event['SecretId']

    # Get current secret
    current = client.get_secret_value(SecretId=secret_id)
    current_dict = json.loads(current['SecretString'])

    # Generate new credentials (integrate with IBKR API)
    new_credentials = generate_new_ibkr_credentials(current_dict['username'])

    # Update secret
    client.update_secret(
        SecretId=secret_id,
        SecretString=json.dumps(new_credentials)
    )

    return {'statusCode': 200, 'body': 'Rotation complete'}
```

---

## Incident Response

### Scenario 1: Secret Leaked to Git

**Immediate Actions:**

```bash
# 1. Revoke compromised secret immediately
vault kv delete secret/algo-trade/production/ibkr

# 2. Generate new credentials
# (via IBKR portal or Vault rotation)

# 3. Update secret
vault kv put secret/algo-trade/production/ibkr \
  username="NEW_USERNAME" \
  password="NEW_PASSWORD"

# 4. Restart all services
kubectl rollout restart deployment/algo-trade-data-plane -n algo-trade

# 5. Audit access logs
vault audit log | grep "algo-trade/production/ibkr"

# 6. Remove from git history
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all
```

**Post-Incident:**

- Document in incident log
- Review secret scanning tools (GitGuardian, TruffleHog)
- Update training materials
- Add pre-commit hooks to prevent future leaks

### Scenario 2: Unauthorized Access Detected

**Actions:**

```bash
# 1. Review Vault audit logs
vault audit log | grep "unauthorized"

# 2. Revoke suspicious tokens
vault token revoke <suspicious-token>

# 3. Rotate all affected secrets
vault kv put secret/algo-trade/production/ibkr ...

# 4. Update policies (restrict access)
vault policy write algo-trade-prod restrictive-policy.hcl

# 5. Enable MFA for sensitive operations
vault write sys/mfa/method/totp/algo-trade \
  issuer=AlgoTrade \
  period=30
```

### Scenario 3: Secret Manager Down

**Fallback Strategy:**

```bash
# 1. Use local .env file (encrypted backup)
gpg --decrypt /secure/backup/.env.gpg > /tmp/.env
export $(cat /tmp/.env | xargs)

# 2. Start services with env vars
python -m data_plane.app.main

# 3. Monitor secret manager recovery
watch -n 10 "curl -s https://vault.yourcompany.com/v1/sys/health"

# 4. Restore normal operations when available
# (restart services to use Vault again)
```

---

## Compliance & Audit

### Audit Logging

**Vault audit logs:**

```bash
# Enable file audit
vault audit enable file file_path=/var/log/vault/audit.log

# Query logs
cat /var/log/vault/audit.log | jq 'select(.request.path | contains("ibkr"))'

# Track who accessed IBKR secrets
cat /var/log/vault/audit.log | jq 'select(.request.path == "secret/data/algo-trade/production/ibkr") | {time: .time, user: .auth.display_name, action: .request.operation}'
```

**AWS CloudTrail:**

```bash
# Query Secrets Manager access
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceType,AttributeValue=AWS::SecretsManager::Secret \
  --start-time 2025-01-01 \
  --end-time 2025-12-31

# Export to CSV for compliance review
aws cloudtrail lookup-events ... --output json | jq -r '...'
```

### Compliance Checklist

- [ ] **SOC 2 Type II**: Secrets encrypted at rest and in transit
- [ ] **PCI DSS**: No credentials in logs or console output
- [ ] **GDPR**: Customer data encrypted with rotated keys
- [ ] **ISO 27001**: Access controls documented and audited
- [ ] **FINRA**: Trading credentials secured with MFA

### Regular Security Reviews

**Quarterly:**
- Review access logs for anomalies
- Verify all secrets rotated on schedule
- Test disaster recovery (restore from backup)
- Update documentation

**Annually:**
- Full security audit by external firm
- Penetration testing
- Review and update policies
- Training for all engineers

---

## Best Practices Summary

### DO ✅

- ✅ Use `.env` files for local development
- ✅ Use Vault or AWS Secrets Manager for staging/production
- ✅ Encrypt secrets at rest (AES-256)
- ✅ Use TLS for all secret transfers
- ✅ Rotate credentials quarterly
- ✅ Log all secret access
- ✅ Use least privilege IAM policies
- ✅ Test secret rotation in staging first
- ✅ Have disaster recovery plan
- ✅ Use MFA for production access

### DON'T ❌

- ❌ Commit secrets to git
- ❌ Share secrets via email/Slack
- ❌ Hardcode secrets in application code
- ❌ Log secrets in application logs
- ❌ Use same credentials across environments
- ❌ Give everyone production access
- ❌ Skip secret rotation
- ❌ Ignore audit logs
- ❌ Store secrets in plain text
- ❌ Use weak passwords

---

## Implementation Checklist

### Phase 1: Local Development (Week 1)
- [x] Create `.env.example` template
- [ ] Setup local `.env` file
- [ ] Test environment variable loading
- [ ] Verify `.gitignore` excludes secrets
- [ ] Document setup in README

### Phase 2: Staging (Week 2-3)
- [ ] Setup HashiCorp Vault or AWS Secrets Manager
- [ ] Create staging secrets
- [ ] Configure application to use secret manager
- [ ] Test secret loading in staging
- [ ] Document staging setup

### Phase 3: Production (Week 4-5)
- [ ] Setup production secret manager (with HA)
- [ ] Migrate all secrets from env vars to secret manager
- [ ] Enable audit logging
- [ ] Setup secret rotation automation
- [ ] Configure alerting for secret access anomalies
- [ ] Complete security audit
- [ ] Train team on incident response

### Phase 4: Operations (Ongoing)
- [ ] Monitor audit logs weekly
- [ ] Rotate secrets quarterly
- [ ] Review access policies monthly
- [ ] Test disaster recovery quarterly
- [ ] Update documentation as needed

---

## Related Documentation

- [RUNBOOK.md](./RUNBOOK.md) - Operational procedures
- [INCIDENT_PLAYBOOK.md](./INCIDENT_PLAYBOOK.md) - Incident response
- [RACI.md](./RACI.md) - Responsibility matrix
- [PRE_LIVE_CHECKLIST.md](./PRE_LIVE_CHECKLIST.md) - Go-live requirements
- [IBKR_INTEGRATION_FLOW.md](./IBKR_INTEGRATION_FLOW.md) - IBKR setup

---

**Document Owner:** Security Team
**Reviewers:** DevOps, Trading Ops, CTO
**Next Review:** Quarterly or after incidents
**Status:** Draft → Review → Approved → Live

---

## Support & Contact

- **Security Team:** security@yourcompany.com
- **DevOps On-Call:** +972-XX-XXX-XXXX
- **Vault Support:** https://discuss.hashicorp.com/c/vault
- **AWS Support:** https://console.aws.amazon.com/support

---

*This document is confidential and intended for internal use only. Do not distribute outside the organization.*
