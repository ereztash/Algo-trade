# IAM Policy Framework
## Identity & Access Management for Algo-Trade

**Document Version:** 1.0
**Date:** 2025-11-08
**Status:** 🔒 PRODUCTION READY
**Parent Document:** SECURITY_EXECUTION_SUMMARY.md

---

## 🎯 Overview

This document defines the **complete IAM architecture** for the Algo-Trade system, including:
- Role hierarchy and permission matrix
- AWS IAM policy templates (Terraform/JSON)
- Just-In-Time (JIT) access procedures
- Least privilege validation rules
- Governance approval workflows

**Key Principles:**
- **Least Privilege:** Minimum permissions required for each role
- **Role Separation:** Trading, DevOps, QA, Service, Governance roles are distinct
- **JIT Access:** Temporary elevation for emergency scenarios
- **Automated Validation:** CI/CD enforces policy standards
- **Governance Approval:** All permission escalations require CTO + Governance sign-off

---

## 📊 Role Hierarchy

```
┌─────────────────────────────────────────────────┐
│           Governance Officer                    │
│  (Audit, Approve, Compliance)                   │
│  Highest authority, lowest execution privilege  │
└────────────────┬────────────────────────────────┘
                 │
     ┌───────────┴───────────┐
     │                       │
┌────▼──────┐        ┌──────▼─────┐
│ CTO       │        │ Security   │
│ (Approve) │        │ Engineer   │
└────┬──────┘        └──────┬─────┘
     │                      │
     ├──────────┬───────────┼──────────┐
     │          │           │          │
┌────▼────┐ ┌──▼─────┐ ┌───▼────┐ ┌──▼────────┐
│ Trader  │ │ DevOps │ │ QA Eng │ │ Service   │
│         │ │        │ │        │ │ Account   │
└─────────┘ └────────┘ └────────┘ └───────────┘
```

---

## 1. Role Definitions

### 1.1 Trader Role

**Purpose:** Execute trading operations, monitor positions, activate kill-switch

**Permissions:**
```yaml
Allowed:
  - Read: prod/ibkr/api-key (IBKR API credentials)
  - Read: prod/tls/private-key (mTLS to IBKR)
  - Write: Kill-switch activation (SNS:Publish to trading-kill-switch topic)
  - Read: Trading dashboards (Grafana/Datadog)
  - Read: Order execution logs (CloudWatch Logs)

Denied:
  - Write: Cannot rotate secrets (DevOps only)
  - Write: Cannot modify IAM policies (Governance only)
  - Read: Cannot access audit logs directly (Governance only)
  - Write: Cannot deploy code (DevOps only)
```

**AWS IAM Policy (JSON):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadProductionSecrets",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/ibkr/api-key*",
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/tls/private-key*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:RequestedRegion": "us-east-1"
        }
      }
    },
    {
      "Sid": "ActivateKillSwitch",
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:us-east-1:123456789012:trading-kill-switch",
      "Condition": {
        "StringLike": {
          "sns:MessageContent": "*kill-switch*"
        }
      }
    },
    {
      "Sid": "ReadTradingLogs",
      "Effect": "Allow",
      "Action": [
        "logs:FilterLogEvents",
        "logs:GetLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:123456789012:log-group:/algo-trade/prod/orders:*"
    }
  ]
}
```

---

### 1.2 DevOps Engineer Role

**Purpose:** Manage infrastructure, deploy code, rotate secrets

**Permissions:**
```yaml
Allowed:
  - Read: All secrets (prod/*, paper/*, qa/*)
  - Write: Secret rotation (secretsmanager:RotateSecret)
  - Write: ECS service updates (deploy code)
  - Write: ECR image push (Docker images)
  - Read/Write: CloudWatch Logs
  - Read: IAM policies (view only, cannot modify)

Denied:
  - Write: Cannot activate kill-switch (Trader only)
  - Write: Cannot modify Governance policies (Governance only)
  - Write: Cannot modify IAM roles (Governance approval required)
```

**AWS IAM Policy (JSON):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ManageSecrets",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:RotateSecret",
        "secretsmanager:UpdateSecret",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:*"
    },
    {
      "Sid": "DeployToProduction",
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecr:PutImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": [
        "arn:aws:ecs:us-east-1:123456789012:service/algo-trade-prod/*",
        "arn:aws:ecr:us-east-1:123456789012:repository/algo-trade*"
      ]
    },
    {
      "Sid": "ViewIAMPolicies",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:ListRolePolicies",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyIAMModifications",
      "Effect": "Deny",
      "Action": [
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:CreateRole",
        "iam:DeleteRole"
      ],
      "Resource": "*"
    }
  ]
}
```

---

### 1.3 QA Engineer Role

**Purpose:** Run tests, validate in Paper/QA environments

**Permissions:**
```yaml
Allowed:
  - Read: paper/*, qa/* secrets (Paper and QA API keys)
  - Write: Deploy to QA/staging environments
  - Read: Test execution logs
  - Write: Update test fixtures

Denied:
  - Read: Cannot access production secrets
  - Write: Cannot deploy to production
  - Write: Cannot rotate production secrets
```

**AWS IAM Policy (JSON):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadPaperAndQASecrets",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:paper/*",
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:qa/*"
      ]
    },
    {
      "Sid": "DeployToQA",
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices"
      ],
      "Resource": "arn:aws:ecs:us-east-1:123456789012:service/algo-trade-qa/*"
    },
    {
      "Sid": "DenyProductionAccess",
      "Effect": "Deny",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/*"
    }
  ]
}
```

---

### 1.4 Service Account (Application Runtime)

**Purpose:** Application runtime execution with minimal privileges

**Permissions:**
```yaml
Allowed:
  - Read: Only secrets required for runtime (prod/ibkr/api-key, prod/rds/password)
  - Write: CloudWatch Logs (application logs)
  - Read: S3 backups (read-only for recovery)

Denied:
  - Write: Cannot rotate secrets
  - Write: Cannot modify IAM policies
  - Write: Cannot access other secrets
  - No human login capability (STS temporary credentials only)
```

**AWS IAM Policy (JSON):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadRuntimeSecrets",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/ibkr/api-key*",
        "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/rds/password*"
      ]
    },
    {
      "Sid": "WriteLogs",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:123456789012:log-group:/algo-trade/prod/*"
    },
    {
      "Sid": "DenySecretsRotation",
      "Effect": "Deny",
      "Action": [
        "secretsmanager:RotateSecret",
        "secretsmanager:UpdateSecret",
        "secretsmanager:DeleteSecret"
      ],
      "Resource": "*"
    }
  ]
}
```

**Trust Policy (AssumeRole):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "ecs-tasks.amazonaws.com",
          "lambda.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "algo-trade-prod-service"
        }
      }
    }
  ]
}
```

**STS Token TTL:** 3600 seconds (1 hour)

---

### 1.5 Governance Officer Role

**Purpose:** Audit access, approve policy changes, compliance oversight

**Permissions:**
```yaml
Allowed:
  - Read: All audit logs (CloudTrail, CloudWatch Logs)
  - Read: All IAM policies (view only)
  - Write: Approve policy changes (manual workflow)
  - Read: Secret access logs (Secrets Manager audit trail)
  - Write: Compliance reports

Denied:
  - Write: Cannot execute trades
  - Write: Cannot deploy code
  - Write: Cannot directly modify IAM policies (requires PR approval)
```

**AWS IAM Policy (JSON):**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadAllAuditLogs",
      "Effect": "Allow",
      "Action": [
        "cloudtrail:LookupEvents",
        "logs:DescribeLogGroups",
        "logs:FilterLogEvents",
        "logs:GetLogEvents"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ReadIAMPolicies",
      "Effect": "Allow",
      "Action": [
        "iam:GetRole",
        "iam:ListRolePolicies",
        "iam:GetRolePolicy",
        "iam:ListAttachedRolePolicies",
        "iam:ListRoles",
        "iam:GetPolicy",
        "iam:GetPolicyVersion"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ReadSecretAccessLogs",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:DescribeSecret",
        "secretsmanager:ListSecrets"
      ],
      "Resource": "*"
    },
    {
      "Sid": "DenyDirectIAMModification",
      "Effect": "Deny",
      "Action": [
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:CreateRole",
        "iam:DeleteRole"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 2. Permission Matrix

| Resource / Action | Trader | DevOps | QA | Service | Governance |
|-------------------|--------|--------|-----|---------|------------|
| **Secrets Management** |
| Read: prod/ibkr/api-key | ✅ | ❌ | ❌ | ✅ | 📊 Audit |
| Read: paper/ibkr/api-key | ✅ | ✅ | ❌ | ✅ | 📊 Audit |
| Rotate secrets | ❌ | ✅ | ❌ | ❌ | 🔐 Approve |
| Delete secrets | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Infrastructure** |
| Deploy to prod | ❌ | ✅ | ❌ | ❌ | 🔐 Approve |
| Deploy to paper/QA | ❌ | ✅ | ✅ | ❌ | ❌ |
| Modify IAM policies | ❌ | ❌ | ❌ | ❌ | 🔐 Approve |
| **Trading Operations** |
| Activate kill-switch | ✅ | ❌ | ❌ | ❌ | ❌ |
| Place orders (prod) | ✅ | ❌ | ❌ | ✅ | ❌ |
| View dashboards | ✅ | ✅ | ✅ | ❌ | ✅ |
| **Audit & Compliance** |
| Read audit logs | ❌ | ❌ | ❌ | ❌ | ✅ |
| Read IAM policies | ❌ | 👁️ View | ❌ | ❌ | ✅ |
| Generate compliance reports | ❌ | ❌ | ❌ | ❌ | ✅ |

**Legend:**
- ✅ Allowed
- ❌ Denied
- 🔐 Approve (approval required)
- 📊 Audit (read-only for compliance)
- 👁️ View (read-only, no modification)

---

## 3. Just-In-Time (JIT) Access

### 3.1 JIT Access Scenarios

**When to Use JIT:**

#### Scenario 1: Emergency Incident Response
```yaml
Use Case: Production database unreachable; DevOps needs immediate access to prod secrets
Approver: Governance Officer (must respond <15 min)
Duration: 30 minutes (auto-revoked)
Justification: "Production incident #12345 - database connection failure"
Request: jit-request prod/rds/password --duration=30m --reason="Incident #12345"
```

#### Scenario 2: Scheduled Maintenance
```yaml
Use Case: Monthly security audit requires access to all logs
Approver: Governance Officer (scheduled approval, <1 week before)
Duration: 2 hours (single session)
Justification: "SOC 2 monthly audit - November 2025"
Request: jit-request audit/all-logs --duration=2h --reason="SOC 2 audit"
```

#### Scenario 3: Onboarding / Training
```yaml
Use Case: New DevOps engineer needs temporary prod access for training
Approver: CTO
Duration: 1 week (training phase)
Justification: "Onboarding: Alice Smith - DevOps training"
Request: jit-request prod/* --duration=7d --reason="Onboarding training"
```

---

### 3.2 JIT Request Flow

```
┌────────────────────────────────────────────────┐
│ 1. User Requests JIT Access                   │
│    CLI: jit-request prod/ibkr/api-key          │
│         --duration=30m                         │
│         --reason="Incident #123"               │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│ 2. System Validates Request                   │
│    - Is this an emergency incident?            │
│    - Is approver on-call?                      │
│    - Is duration within policy limits?         │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│ 3. Route to Approver                          │
│    - Emergency → Governance Officer (Slack)    │
│    - Scheduled → CTO (Email + Slack)           │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│ 4. Approver Reviews (<15 min)                 │
│    - Review request details                    │
│    - Verify justification                      │
│    - Click: Approve / Deny                     │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│ 5. If Approved: Issue Temporary Credentials   │
│    - Generate STS token with TTL              │
│    - Return credentials to user               │
│    - Log approval (audit trail)               │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│ 6. User Performs Action (within TTL window)   │
│    - Use temporary credentials                 │
│    - All actions logged                        │
└────────────┬───────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────┐
│ 7. Auto-Revoke After Duration Expires         │
│    - STS token expires automatically           │
│    - User cannot extend without new request    │
│    - Audit log updated                         │
└────────────────────────────────────────────────┘
```

---

### 3.3 JIT Access Implementation (AWS Lambda)

**Lambda Function: `jit-access-handler`**

```python
# lambda/jit_access_handler.py
import boto3
import json
from datetime import datetime, timedelta

sts_client = boto3.client('sts')
sns_client = boto3.client('sns')
dynamodb = boto3.resource('dynamodb')
jit_table = dynamodb.Table('jit-access-requests')

def lambda_handler(event, context):
    """
    Handle JIT access requests.
    """
    request_id = event['requestId']
    user_id = event['userId']
    resource = event['resource']
    duration_minutes = event['durationMinutes']
    justification = event['justification']

    # 1. Validate request
    if duration_minutes > 120:  # Max 2 hours
        return {'statusCode': 400, 'body': 'Duration exceeds policy limit'}

    # 2. Determine approver
    approver = get_approver(resource, is_emergency=is_emergency(justification))

    # 3. Send approval request
    approval_id = send_approval_request(
        approver=approver,
        user_id=user_id,
        resource=resource,
        duration_minutes=duration_minutes,
        justification=justification
    )

    # 4. Wait for approval (polling or webhook)
    approved = wait_for_approval(approval_id, timeout_sec=900)  # 15 min timeout

    if not approved:
        return {'statusCode': 403, 'body': 'JIT access denied or timed out'}

    # 5. Issue temporary credentials
    temp_creds = issue_temp_credentials(
        user_id=user_id,
        resource=resource,
        ttl_seconds=duration_minutes * 60
    )

    # 6. Log access grant
    log_jit_access(
        request_id=request_id,
        user_id=user_id,
        resource=resource,
        approver=approver,
        duration_minutes=duration_minutes,
        justification=justification
    )

    return {
        'statusCode': 200,
        'body': json.dumps({
            'accessKeyId': temp_creds['AccessKeyId'],
            'secretAccessKey': temp_creds['SecretAccessKey'],
            'sessionToken': temp_creds['SessionToken'],
            'expiration': temp_creds['Expiration'].isoformat()
        })
    }

def issue_temp_credentials(user_id, resource, ttl_seconds):
    """
    Create temporary IAM credentials using STS AssumeRole.
    """
    role_arn = f"arn:aws:iam::123456789012:role/JIT-{resource.replace('/', '-')}"

    response = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=f"jit-{user_id}-{int(datetime.utcnow().timestamp())}",
        DurationSeconds=ttl_seconds,  # Auto-expire after TTL
    )

    return response['Credentials']

def send_approval_request(approver, user_id, resource, duration_minutes, justification):
    """
    Send approval request to approver via SNS (Slack/Email).
    """
    message = f"""
JIT Access Request

User: {user_id}
Resource: {resource}
Duration: {duration_minutes} minutes
Justification: {justification}

Approve: https://jit.example.com/approve/{approval_id}
Deny: https://jit.example.com/deny/{approval_id}
"""

    response = sns_client.publish(
        TopicArn=f"arn:aws:sns:us-east-1:123456789012:jit-approvals-{approver}",
        Subject="JIT Access Request - Action Required",
        Message=message
    )

    approval_id = response['MessageId']

    # Store request in DynamoDB
    jit_table.put_item(Item={
        'approval_id': approval_id,
        'user_id': user_id,
        'resource': resource,
        'status': 'PENDING',
        'requested_at': datetime.utcnow().isoformat()
    })

    return approval_id

def wait_for_approval(approval_id, timeout_sec=900):
    """
    Poll for approval decision (or use webhook in production).
    """
    start_time = datetime.utcnow()

    while (datetime.utcnow() - start_time).seconds < timeout_sec:
        # Check DynamoDB for approval status
        response = jit_table.get_item(Key={'approval_id': approval_id})
        status = response.get('Item', {}).get('status')

        if status == 'APPROVED':
            return True
        elif status == 'DENIED':
            return False

        # Poll every 10 seconds
        import time
        time.sleep(10)

    # Timeout
    return False
```

---

## 4. Least Privilege Validation

### 4.1 Policy Anti-Patterns

**Violations that FAIL CI/CD:**

```yaml
1. Resource Wildcard
   Pattern: "Resource": "*"
   Severity: CRITICAL
   Action: Fail PR, require specific resource ARNs

2. Action Wildcard
   Pattern: "Action": "*" or "Action": "<service>:*"
   Severity: CRITICAL
   Action: Fail PR, require specific actions

3. Missing Condition Clauses
   Pattern: Broad permissions without IP/MFA/time restrictions
   Severity: HIGH
   Action: Warn in PR, require justification

4. Principal Wildcard
   Pattern: "Principal": "*"
   Severity: CRITICAL
   Action: Fail PR, require specific principals
```

---

### 4.2 Automated Validation Script

**Script: `scripts/validate_iam_policies.py`**

```python
#!/usr/bin/env python3
"""
Validate IAM policies for least privilege compliance.
"""
import json
import sys
import re

def validate_iam_policy(policy_json):
    """
    Validate IAM policy for least privilege compliance.
    """
    violations = []
    policy = json.loads(policy_json)

    for statement in policy.get('Statement', []):
        sid = statement.get('Sid', 'unnamed')

        # Check 1: Resource wildcards
        resources = statement.get('Resource', [])
        if isinstance(resources, str):
            resources = [resources]
        if "*" in resources:
            violations.append(
                f"VIOLATION: Resource contains wildcard '*' in {sid}"
            )

        # Check 2: Action wildcards
        actions = statement.get('Action', [])
        if isinstance(actions, str):
            actions = [actions]
        for action in actions:
            if action == "*" or action.endswith(":*"):
                violations.append(
                    f"VIOLATION: Action is wildcard in {sid}: {action}"
                )

        # Check 3: Missing Condition on broad statements
        conditions = statement.get('Condition')
        if not conditions and len(actions) > 5:
            violations.append(
                f"WARNING: Statement {sid} has {len(actions)} actions with no Condition"
            )

        # Check 4: Principal wildcards
        principal = statement.get('Principal')
        if principal == "*":
            violations.append(
                f"VIOLATION: Principal is wildcard in {sid}"
            )

    return violations

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('policy_file', help='Path to IAM policy JSON file')
    parser.add_argument('--fail-on-violation', action='store_true')
    args = parser.parse_args()

    with open(args.policy_file, 'r') as f:
        policy = f.read()

    violations = validate_iam_policy(policy)

    if violations:
        print("Least Privilege Validation Results:")
        for v in violations:
            print(f"  - {v}")

        if args.fail_on_violation and any("VIOLATION" in v for v in violations):
            print("\n❌ Policy validation FAILED")
            sys.exit(1)
        else:
            print("\n⚠️  Warnings found, but merge allowed")
    else:
        print("✓ Policy passes least privilege checks")
```

---

### 4.3 GitHub Actions Integration

**Workflow: `.github/workflows/iam-policy-validation.yml`**

```yaml
name: IAM Policy Validation

on:
  pull_request:
    paths:
      - 'iam/policies/**/*.json'
      - 'terraform/**/*.tf'

jobs:
  validate-policies:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Validate IAM policies for least privilege
        run: |
          for policy in iam/policies/*.json; do
            echo "Validating $policy..."
            python scripts/validate_iam_policies.py "$policy" --fail-on-violation
          done

      - name: AWS Access Analyzer validation
        if: github.event_name == 'pull_request'
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          for policy in iam/policies/*.json; do
            echo "Running AWS Access Analyzer on $policy..."
            aws accessanalyzer validate-policy \
              --policy-document file://"$policy" \
              --policy-type IDENTITY_POLICY \
              --locale EN || exit 1
          done

      - name: Comment PR with results
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '❌ IAM policy validation failed. Please fix violations and re-submit.'
            })
```

---

## 5. Governance Approval Workflow

### 5.1 Policy Change Types & Approval Requirements

| Change Type | Example | Reviewers | Approvers | Testing | Timeline |
|-------------|---------|-----------|-----------|---------|----------|
| **Permission Escalation** | Grant DevOps write to prod secrets | CTO + Security | Governance Board | Staging required | <24 hours |
| **Permission Reduction** | Remove stale admin access | CTO | Self-service | No testing | <4 hours |
| **New Role Creation** | Create data pipeline service account | CTO + Security | CTO | Policy lint + staging | <24 hours |
| **Routine Maintenance** | Update role description (no perms change) | Auto-lint | Auto-approved | Lint check only | Immediate |

---

### 5.2 GitHub PR Approval Template

**Template: `.github/PULL_REQUEST_TEMPLATE/iam_policy_change.md`**

```markdown
# IAM Policy Change Request

## Summary
Brief description of what permission is being changed and why.

## Type
- [ ] Permission Escalation (requires Governance board approval)
- [ ] Permission Reduction (fast-track approval)
- [ ] New Role Creation
- [ ] Routine Maintenance

## Motivation
Why is this change needed? Provide business justification.

## Changes
**Before:**
```json
{
  "Action": ["s3:GetObject"]
}
```

**After:**
```json
{
  "Action": ["s3:GetObject", "s3:PutObject"]
}
```

## Impact
- **Affected Services:** [List services/users affected]
- **Security Risk:** [Low / Medium / High]
- **Compliance Impact:** [None / SOC2 / MiFID II]

## Least Privilege Assessment
- [ ] This change follows least privilege principle
- [ ] No wildcard resources (`*`)
- [ ] No wildcard actions (`*` or `<service>:*`)
- [ ] Condition clauses added (if broad permissions)

## Testing
- [ ] Tested in staging environment
- [ ] Verified service can assume role
- [ ] Verified permissions work as intended
- [ ] Verified no overpermissioning (cannot access restricted resources)

## Rollback Plan
If this policy causes issues, how will we revert?
- [ ] Keep old policy version in Git history
- [ ] Can revert via `git revert` + re-deploy

## Approval
- [ ] CTO: **Approved** / Requested Changes / Denied
- [ ] Security Engineer: **Approved** / Requested Changes / Denied
- [ ] Governance Officer (if escalation): **Approved** / Denied

**Approval Date:** [YYYY-MM-DD]
**Approved By:** [Name]
```

---

### 5.3 Approval Decision Tree

```
┌──────────────────────────────────────────┐
│ Is this a permission escalation?         │
└────────┬─────────────────────────────────┘
         │
    YES  │  NO
         │
         ▼
┌──────────────────────────────────────────┐
│ Requires Governance Board Approval       │
│ (CTO + Security + Governance Officer)    │
└────────┬─────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ Test in Staging First                    │
│ - Deploy policy to staging               │
│ - Run permission tests                   │
│ - Verify least privilege                 │
└────────┬─────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│ All Approvers Sign Off?                  │
└────────┬─────────────────────────────────┘
         │
    YES  │  NO → Rejected, request changes
         │
         ▼
┌──────────────────────────────────────────┐
│ Deploy to Production                     │
│ - Merge PR                               │
│ - Terraform apply                        │
│ - Log change in audit trail              │
└──────────────────────────────────────────┘
```

---

## 6. Terraform IAM Policy Templates

### 6.1 Trader Role (Terraform)

**File: `terraform/iam/trader_role.tf`**

```hcl
# Trader Role - Trading operations and kill-switch activation

resource "aws_iam_role" "trader_role" {
  name               = "algo-trade-trader-prod"
  description        = "Trading operations role - read secrets, activate kill-switch"
  assume_role_policy = data.aws_iam_policy_document.trader_assume_role_policy.json

  tags = {
    Environment = "production"
    Role        = "Trader"
    ManagedBy   = "Terraform"
  }
}

data "aws_iam_policy_document" "trader_assume_role_policy" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = [
        "arn:aws:iam::123456789012:user/alice",
        "arn:aws:iam::123456789012:user/bob"
      ]
    }

    condition {
      test     = "Bool"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["true"]
    }
  }
}

resource "aws_iam_policy" "trader_policy" {
  name        = "algo-trade-trader-policy"
  description = "Policy for trading operations"
  policy      = data.aws_iam_policy_document.trader_policy.json
}

data "aws_iam_policy_document" "trader_policy" {
  # Read production secrets
  statement {
    sid    = "ReadProductionSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue"
    ]
    resources = [
      "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/ibkr/api-key*",
      "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/tls/private-key*"
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = ["us-east-1"]
    }
  }

  # Activate kill-switch
  statement {
    sid    = "ActivateKillSwitch"
    effect = "Allow"
    actions = [
      "sns:Publish"
    ]
    resources = [
      aws_sns_topic.kill_switch.arn
    ]
  }

  # Read trading logs
  statement {
    sid    = "ReadTradingLogs"
    effect = "Allow"
    actions = [
      "logs:FilterLogEvents",
      "logs:GetLogEvents"
    ]
    resources = [
      "arn:aws:logs:us-east-1:123456789012:log-group:/algo-trade/prod/orders:*"
    ]
  }
}

resource "aws_iam_role_policy_attachment" "trader_policy_attachment" {
  role       = aws_iam_role.trader_role.name
  policy_arn = aws_iam_policy.trader_policy.arn
}

# Kill-switch SNS topic
resource "aws_sns_topic" "kill_switch" {
  name         = "trading-kill-switch"
  display_name = "Trading Algorithm Kill-Switch"

  tags = {
    Environment = "production"
    Purpose     = "Emergency halt"
  }
}
```

---

### 6.2 Service Account Role (Terraform)

**File: `terraform/iam/service_account_role.tf`**

```hcl
# Service Account Role - Application runtime with minimal privileges

resource "aws_iam_role" "service_account_role" {
  name               = "algo-trade-service-prod"
  description        = "Application runtime service account"
  assume_role_policy = data.aws_iam_policy_document.service_assume_role_policy.json

  tags = {
    Environment = "production"
    Role        = "ServiceAccount"
    ManagedBy   = "Terraform"
  }
}

data "aws_iam_policy_document" "service_assume_role_policy" {
  statement {
    effect = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = [
        "ecs-tasks.amazonaws.com",
        "lambda.amazonaws.com"
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "sts:ExternalId"
      values   = ["algo-trade-prod-service"]
    }
  }
}

resource "aws_iam_policy" "service_account_policy" {
  name        = "algo-trade-service-policy"
  description = "Minimal runtime permissions for trading app"
  policy      = data.aws_iam_policy_document.service_account_policy.json
}

data "aws_iam_policy_document" "service_account_policy" {
  # Read runtime secrets
  statement {
    sid    = "ReadRuntimeSecrets"
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue"
    ]
    resources = [
      "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/ibkr/api-key*",
      "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/rds/password*"
    ]
  }

  # Write application logs
  statement {
    sid    = "WriteLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:us-east-1:123456789012:log-group:/algo-trade/prod/*"
    ]
  }

  # Deny secrets rotation (security enforcement)
  statement {
    sid    = "DenySecretsRotation"
    effect = "Deny"
    actions = [
      "secretsmanager:RotateSecret",
      "secretsmanager:UpdateSecret",
      "secretsmanager:DeleteSecret"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy_attachment" "service_policy_attachment" {
  role       = aws_iam_role.service_account_role.name
  policy_arn = aws_iam_policy.service_account_policy.arn
}
```

---

## 7. Compliance & Audit

### 7.1 Monthly IAM Audit Report Template

```markdown
# IAM Policy Compliance Report

**Reporting Period:** 2025-11-01 to 2025-11-30
**Auditor:** [Governance Officer Name]
**Date:** 2025-12-01

---

## Summary

| Metric | Count | Status |
|--------|-------|--------|
| Total IAM Policies | 42 | ✅ |
| Validated Policies | 42 | ✅ 100% |
| Policies Passing Least Privilege | 41 | ✅ 97.6% |
| Violations Found | 1 | ⚠️ |

---

## Policy Changes This Period

### Permission Escalations (Approved)
1. **Grant DevOps write access to prod/rds/password**
   - **Date:** 2025-11-05
   - **Approvers:** CTO (Alice), Security (Bob)
   - **Justification:** Support emergency DB troubleshooting
   - **Condition:** Only during business hours; max 2 hours per request
   - **Status:** ✅ APPROVED

### New Roles Created
1. **Data Pipeline Service Account**
   - **Date:** 2025-11-10
   - **Approvers:** CTO
   - **Permissions:** Read IBKR API, Write RDS
   - **Status:** ✅ APPROVED

### Denied Changes
- None this month

---

## Top Risks Detected

1. **Legacy Policy:** ServiceRole-Legacy (last used 6 months ago)
   - **Recommendation:** Delete unused policy
   - **Action:** ⏳ Scheduled for deletion 2025-12-15

---

## Remediation Actions

- [ ] Delete unused ServiceRole-Legacy policy
- [ ] Update 3 policies to include Condition clauses (IP restrictions)
- [ ] All changes to be deployed by next audit (2025-12-31)

---

## Conclusion

✅ **Compliant with least privilege baseline**

---

**Approvals:**
- **Governance Officer:** [Signature] [Date]
- **CTO:** [Signature] [Date]
```

---

### 7.2 SOC 2 Compliance Mapping

| SOC 2 Control | IAM Requirement | Implementation | Evidence |
|---------------|-----------------|----------------|----------|
| CC6.1 Logical Access | Role-based access control | 5 roles defined | This document |
| CC6.2 Access Authorization | Approval workflow for escalations | GitHub PR approvals | PR audit trail |
| CC6.3 Access Revocation | JIT access auto-revoke | STS token expiration | CloudTrail logs |
| CC6.6 Logical Access Removal | Offboarding procedure | Disable IAM user, revoke roles | HR offboard tickets |
| CC6.7 Encryption | Secrets encrypted at rest | AWS KMS | KMS audit logs |

---

## 8. Quick Reference

### 8.1 CLI Commands

**Request JIT Access:**
```bash
jit-request prod/ibkr/api-key --duration=30m --reason="Incident #123"
```

**Validate IAM Policy:**
```bash
python scripts/validate_iam_policies.py iam/policies/trader_role.json --fail-on-violation
```

**Assume Role (Manual):**
```bash
aws sts assume-role \
  --role-arn arn:aws:iam::123456789012:role/algo-trade-trader-prod \
  --role-session-name trader-session \
  --duration-seconds 3600
```

**Check Who Am I:**
```bash
aws sts get-caller-identity
```

---

### 8.2 Emergency Procedures

**If IAM policy breaks production:**
1. Immediately revert via Git: `git revert <commit-hash>`
2. Re-deploy via Terraform: `terraform apply`
3. Verify role assumptions work: `aws sts assume-role ...`
4. File incident report
5. Update post-mortem

---

## 📝 Document Control

- **Version:** 1.0
- **Created:** 2025-11-08
- **Last Modified:** 2025-11-08
- **Next Review:** 2026-02-08 (Quarterly)
- **Classification:** CONFIDENTIAL
- **Distribution:** Security Team, CTO, Governance Board

---

**Generated by:** Claude Code (AI Assistant)
**Parent Document:** SECURITY_EXECUTION_SUMMARY.md
**Status:** ✅ READY FOR IMPLEMENTATION
