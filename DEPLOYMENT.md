# Deployment Guide

**Version:** 1.0
**Status:** Production-Ready (P1)
**Last Updated:** 2025-11-16
**Owner:** DevOps / SRE Team

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Local Development Deployment](#local-development-deployment)
4. [Docker Compose Deployment (Staging)](#docker-compose-deployment-staging)
5. [Kubernetes Deployment (Production)](#kubernetes-deployment-production)
6. [AWS ECS Deployment](#aws-ecs-deployment)
7. [AWS EC2 Deployment](#aws-ec2-deployment)
8. [Monitoring & Observability](#monitoring--observability)
9. [Rollback Procedures](#rollback-procedures)
10. [Troubleshooting](#troubleshooting)

---

## Overview

### Deployment Environments

| Environment | Platform | Use Case | High Availability |
|-------------|----------|----------|-------------------|
| **Local** | Docker Compose | Development, testing | ❌ No |
| **Staging** | Docker Compose / K8s | Pre-production validation | ⚠️ Optional |
| **Production** | Kubernetes / AWS ECS | Live trading | ✅ Yes |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer                        │
└───────────────────────┬─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
┌───────▼───────┐ ┌────▼─────┐ ┌───────▼───────┐
│  Data Plane   │ │ Strategy │ │  Order Plane  │
│   (Ingest)    │ │  (Compute│ │   (Execute)   │
└───────┬───────┘ └────┬─────┘ └───────┬───────┘
        │              │               │
        └──────────────┼───────────────┘
                       │
                ┌──────▼──────┐
                │    Kafka    │
                └─────────────┘
```

---

## Prerequisites

### General Requirements

- **Docker** 20.10+ and Docker Compose 2.0+
- **Kubernetes** 1.25+ (for K8s deployment)
- **kubectl** configured with cluster access
- **AWS CLI** v2 (for AWS deployments)
- **Helm** 3.10+ (optional, for K8s package management)

### IBKR Requirements

- **IB Gateway** or **TWS** running and accessible
- **Paper Trading Account** (DU*) for staging
- **Live Trading Account** (U*) for production
- **API Access** enabled in IB account settings

### Secrets Management

- **HashiCorp Vault** or **AWS Secrets Manager** configured
- Credentials stored securely (see [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md))

---

## Local Development Deployment

### Quick Start

```bash
# 1. Setup environment
./scripts/setup_env.sh

# 2. Edit .env file
nano .env  # Configure IBKR_ACCOUNT and other settings

# 3. Start infrastructure only
docker-compose up -d zookeeper kafka vault

# 4. Wait for services
sleep 30

# 5. Run application locally (without Docker)
python -m data_plane.app.main &
python -m apps.strategy_loop.main &
python -m order_plane.app.orchestrator &
```

### Full Docker Compose (Local)

```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f data-plane strategy-plane order-plane

# Check health
docker-compose ps

# Stop
docker-compose down
```

---

## Docker Compose Deployment (Staging)

### Preparation

```bash
# 1. Set environment to staging
export ENVIRONMENT=staging

# 2. Configure .env for staging
cat > .env <<EOF
ENVIRONMENT=staging
LOG_LEVEL=INFO
IBKR_HOST=host.docker.internal
IBKR_PORT=4002  # Paper trading
IBKR_ACCOUNT=DU1234567
IBKR_READ_ONLY=true
DP_USE_VAULT=1
VAULT_ADDR=http://vault:8200
EOF

# 3. Initialize Vault with staging secrets
docker-compose up -d vault
sleep 10

# Store IBKR credentials in Vault
docker exec -it algo-trade-vault vault kv put \
  secret/algo-trade/staging/ibkr \
  account="DU1234567" \
  host="host.docker.internal" \
  port="4002" \
  paper="true"
```

### Deployment

```bash
# Build latest images
docker-compose build

# Start infrastructure
docker-compose up -d zookeeper kafka vault prometheus grafana

# Wait for infrastructure
sleep 60

# Start application planes
docker-compose up -d data-plane strategy-plane order-plane

# Verify deployment
docker-compose ps
docker-compose logs -f

# Access monitoring
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

### Health Checks

```bash
# Check plane health
curl http://localhost:8000/healthz  # Data Plane
curl http://localhost:8001/healthz  # Strategy Plane
curl http://localhost:8002/healthz  # Order Plane

# Check metrics
curl http://localhost:8000/metrics | grep -E "system_health|pnl|orders"
```

---

## Kubernetes Deployment (Production)

### Prerequisites

```bash
# Verify cluster access
kubectl cluster-info
kubectl get nodes

# Create namespace
kubectl apply -f k8s/namespace.yaml
```

### Secrets Setup

**Option 1: Manual (Quick Start)**

```bash
# Create IBKR secrets
kubectl create secret generic algo-trade-ibkr \
  --from-literal=username="YOUR_USERNAME" \
  --from-literal=password="YOUR_PASSWORD" \
  --from-literal=api-key="YOUR_API_KEY" \
  --from-literal=account="U1234567" \
  -n algo-trade

# Create Vault secrets
kubectl create secret generic algo-trade-vault \
  --from-literal=token="YOUR_VAULT_TOKEN" \
  -n algo-trade
```

**Option 2: External Secrets Operator (Recommended)**

```bash
# Install External Secrets Operator
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets \
  external-secrets/external-secrets \
  -n external-secrets-system \
  --create-namespace

# Create SecretStore (connects to Vault/AWS)
kubectl apply -f k8s/external-secrets/secret-store.yaml

# Create ExternalSecret (syncs from Vault)
kubectl apply -f k8s/external-secrets/ibkr-secret.yaml
```

### Deployment Steps

```bash
# 1. Apply ConfigMap
kubectl apply -f k8s/configmap.yaml

# 2. Deploy infrastructure (if not using external Kafka)
# See "Kafka Deployment" section below

# 3. Deploy application planes
kubectl apply -f k8s/data-plane-deployment.yaml
kubectl apply -f k8s/strategy-plane-deployment.yaml
kubectl apply -f k8s/order-plane-deployment.yaml

# 4. Wait for rollout
kubectl rollout status deployment/data-plane -n algo-trade
kubectl rollout status deployment/strategy-plane -n algo-trade
kubectl rollout status deployment/order-plane -n algo-trade

# 5. Verify pods
kubectl get pods -n algo-trade
kubectl logs -f deployment/data-plane -n algo-trade
```

### Kafka Deployment (In-Cluster)

**Using Strimzi Operator:**

```bash
# Install Strimzi
kubectl create namespace kafka
kubectl apply -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka

# Deploy Kafka cluster
cat <<EOF | kubectl apply -f -
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: algo-trade-kafka
  namespace: kafka
spec:
  kafka:
    version: 3.5.0
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
      default.replication.factor: 3
      min.insync.replicas: 2
    storage:
      type: persistent-claim
      size: 100Gi
      deleteClaim: false
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 10Gi
      deleteClaim: false
  entityOperator:
    topicOperator: {}
    userOperator: {}
EOF

# Wait for Kafka to be ready
kubectl wait kafka/algo-trade-kafka --for=condition=Ready --timeout=300s -n kafka
```

### Scaling

```bash
# Scale Data Plane (can have multiple replicas)
kubectl scale deployment/data-plane --replicas=3 -n algo-trade

# Strategy and Order Planes should remain at 1 replica
# (to avoid duplicate signals/orders)

# Horizontal Pod Autoscaling
kubectl autoscale deployment/data-plane \
  --min=2 --max=5 \
  --cpu-percent=70 \
  -n algo-trade
```

### Updates & Rolling Deployments

```bash
# Update image
kubectl set image deployment/data-plane \
  data-plane=algo-trade/data-plane:v1.1.0 \
  -n algo-trade

# Monitor rollout
kubectl rollout status deployment/data-plane -n algo-trade

# Rollback if needed (see ROLLBACK_PROCEDURE.md)
kubectl rollout undo deployment/data-plane -n algo-trade
```

---

## AWS ECS Deployment

### Architecture on AWS

```
                    ┌─────────────────┐
                    │   Application   │
                    │  Load Balancer  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         ┌────▼────┐    ┌────▼────┐   ┌────▼────┐
         │ECS Task │    │ECS Task │   │ECS Task │
         │  Data   │    │Strategy │   │  Order  │
         └────┬────┘    └────┬────┘   └────┬────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                       ┌─────▼─────┐
                       │   MSK     │
                       │  (Kafka)  │
                       └───────────┘
```

### Prerequisites

```bash
# Configure AWS CLI
aws configure

# Install ECS CLI
sudo curl -Lo /usr/local/bin/ecs-cli \
  https://amazon-ecs-cli.s3.amazonaws.com/ecs-cli-linux-amd64-latest
sudo chmod +x /usr/local/bin/ecs-cli
```

### Infrastructure Setup (Terraform)

```hcl
# terraform/main.tf
# See aws/terraform/README.md for complete IaC setup

# Key resources:
# - VPC with public/private subnets
# - ECS Cluster
# - MSK (Managed Kafka)
# - Secrets Manager
# - ECR repositories
# - Application Load Balancer
# - RDS (optional, for persistence)
```

### ECR Repository Setup

```bash
# Create ECR repositories
aws ecr create-repository --repository-name algo-trade/data-plane
aws ecr create-repository --repository-name algo-trade/strategy-plane
aws ecr create-repository --repository-name algo-trade/order-plane

# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# Build and push images
docker build -f docker/Dockerfile.data-plane \
  -t 123456789012.dkr.ecr.us-east-1.amazonaws.com/algo-trade/data-plane:latest .
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/algo-trade/data-plane:latest

# Repeat for strategy and order planes
```

### ECS Task Definitions

```bash
# Register task definition
aws ecs register-task-definition \
  --cli-input-json file://aws/ecs/data-plane-task.json

# See aws/ecs/ directory for complete task definitions
```

### ECS Service Deployment

```bash
# Create ECS cluster
aws ecs create-cluster --cluster-name algo-trade-production

# Create service
aws ecs create-service \
  --cluster algo-trade-production \
  --service-name data-plane \
  --task-definition algo-trade-data-plane:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=data-plane,containerPort=8000"

# Monitor deployment
aws ecs describe-services \
  --cluster algo-trade-production \
  --services data-plane
```

### Secrets in AWS

```bash
# Store IBKR credentials in Secrets Manager
aws secretsmanager create-secret \
  --name algo-trade/production/ibkr \
  --secret-string '{
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD",
    "api_key": "YOUR_API_KEY",
    "account": "U1234567"
  }'

# ECS task definition references secrets via ARN
# See aws/ecs/data-plane-task.json for example
```

### MSK (Managed Kafka) Setup

```bash
# Create MSK cluster (via Console or Terraform)
# Recommended: 3 brokers across 3 AZs
# Instance type: kafka.m5.large or larger
# Storage: 100GB per broker minimum

# Get bootstrap servers
aws kafka get-bootstrap-brokers \
  --cluster-arn arn:aws:kafka:us-east-1:123456789012:cluster/algo-trade/...

# Update ECS task env var with bootstrap servers
```

---

## AWS EC2 Deployment

### EC2 Instance Setup

```bash
# Launch EC2 instance (via Console or Terraform)
# Recommended: t3.xlarge or larger
# AMI: Amazon Linux 2023
# Storage: 100GB SSD
# Security Group: Allow 22 (SSH), 8000-8002 (metrics)

# SSH into instance
ssh -i key.pem ec2-user@<instance-ip>

# Install Docker
sudo yum update -y
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -a -G docker ec2-user

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone repository
git clone https://github.com/your-org/Algo-trade.git
cd Algo-trade

# Setup environment
./scripts/setup_env.sh

# Deploy with Docker Compose
docker-compose up -d
```

### Systemd Service (Auto-start)

```bash
# Create systemd service
sudo cat > /etc/systemd/system/algo-trade.service <<EOF
[Unit]
Description=Algo-Trade System
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ec2-user/Algo-trade
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl enable algo-trade
sudo systemctl start algo-trade
```

---

## Monitoring & Observability

### Metrics Collection

All planes expose Prometheus metrics on `/metrics`:
- **Data Plane**: port 8000
- **Strategy Plane**: port 8001
- **Order Plane**: port 8002

### Key Metrics to Monitor

```promql
# System Health
up{job="algo-trade"}

# PnL Metrics
algo_trade_pnl_total
algo_trade_pnl_daily

# Risk Metrics
algo_trade_drawdown_current
algo_trade_exposure_gross
algo_trade_exposure_net

# Performance
algo_trade_latency_p95
algo_trade_signal_computation_duration

# Orders
algo_trade_orders_total
algo_trade_orders_rejected
algo_trade_fill_rate
```

### Grafana Dashboards

```bash
# Import dashboards (in Grafana UI)
# 1. Algo-Trade Overview: monitoring/grafana/dashboards/overview.json
# 2. Risk Management: monitoring/grafana/dashboards/risk.json
# 3. Performance: monitoring/grafana/dashboards/performance.json
```

### Alerting

Key alerts to configure:
- Kill-switch triggered (PnL, Drawdown, PSR)
- High order rejection rate (>10%)
- IBKR connection loss
- Kafka lag >1000 messages
- High latency (p95 >1s)

---

## Rollback Procedures

See [ROLLBACK_PROCEDURE.md](./ROLLBACK_PROCEDURE.md) for complete rollback procedures.

### Quick Rollback (Kubernetes)

```bash
# Rollback to previous version
kubectl rollout undo deployment/data-plane -n algo-trade

# Rollback to specific revision
kubectl rollout history deployment/data-plane -n algo-trade
kubectl rollout undo deployment/data-plane --to-revision=5 -n algo-trade
```

### Quick Rollback (ECS)

```bash
# Update service to previous task definition
aws ecs update-service \
  --cluster algo-trade-production \
  --service data-plane \
  --task-definition algo-trade-data-plane:10  # Previous version
```

### Emergency Shutdown

```bash
# Kubernetes
kubectl scale deployment/strategy-plane --replicas=0 -n algo-trade
kubectl scale deployment/order-plane --replicas=0 -n algo-trade

# Docker Compose
docker-compose stop strategy-plane order-plane

# ECS
aws ecs update-service \
  --cluster algo-trade-production \
  --service strategy-plane \
  --desired-count 0
```

---

## Troubleshooting

### Common Issues

#### Issue: Pods CrashLoopBackOff

```bash
# Check logs
kubectl logs deployment/data-plane -n algo-trade --tail=100

# Check events
kubectl describe pod <pod-name> -n algo-trade

# Common causes:
# - Missing secrets
# - Kafka not reachable
# - IBKR connection failure
```

#### Issue: IBKR Connection Failed

```bash
# Verify IB Gateway is running
nc -zv <ibkr-host> 4001

# Check credentials
kubectl get secret algo-trade-ibkr -n algo-trade -o yaml

# Check logs for connection errors
kubectl logs deployment/order-plane -n algo-trade | grep -i "ibkr\|connection"
```

#### Issue: High Kafka Lag

```bash
# Check consumer lag
kubectl exec -it kafka-0 -n kafka -- \
  kafka-consumer-groups.sh --bootstrap-server localhost:9092 \
  --describe --group algo_trade_consumer

# Scale data plane
kubectl scale deployment/data-plane --replicas=3 -n algo-trade
```

---

## Production Checklist

Before going live:

- [ ] All secrets stored in Vault/AWS Secrets Manager
- [ ] Kubernetes cluster has HA (3+ nodes)
- [ ] Kafka cluster has 3+ brokers
- [ ] Monitoring and alerting configured
- [ ] Rollback procedure tested
- [ ] Security audit passed (Bandit, safety)
- [ ] IBKR paper trading validated
- [ ] Kill-switches tested
- [ ] Incident response team trained
- [ ] CTO approval obtained

---

## Related Documentation

- [SECRETS_MANAGEMENT.md](./SECRETS_MANAGEMENT.md) - Secrets handling
- [RUNBOOK.md](./RUNBOOK.md) - Operations procedures
- [INCIDENT_PLAYBOOK.md](./INCIDENT_PLAYBOOK.md) - Incident response
- [ROLLBACK_PROCEDURE.md](./ROLLBACK_PROCEDURE.md) - Rollback procedures
- [PRE_LIVE_CHECKLIST.md](./PRE_LIVE_CHECKLIST.md) - Go-live requirements

---

**Document Owner:** DevOps Team
**Reviewers:** SRE, CTO, Security
**Next Review:** After production deployment
**Status:** Production-Ready

---

*This document is confidential and intended for internal use only.*
