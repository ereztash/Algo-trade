#!/bin/bash
# ==============================================================================
# Algo-Trade Docker Stack Startup Script
# ==============================================================================
# Starts the complete algo-trading system with proper health checks
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  Algo-Trade System - Docker Stack Startup${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo

# ==============================================================================
# Pre-flight Checks
# ==============================================================================

echo -e "${YELLOW}[1/6] Running pre-flight checks...${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Docker is not running!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker is running${NC}"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null 2>&1; then
    echo -e "${RED}ERROR: docker-compose not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✓ docker-compose is available${NC}"

# Check if .env file exists
if [ ! -f "$PROJECT_ROOT/.env" ]; then
    echo -e "${YELLOW}WARNING: .env file not found${NC}"
    echo -e "${YELLOW}Copying .env.docker to .env...${NC}"
    cp "$PROJECT_ROOT/.env.docker" "$PROJECT_ROOT/.env"
    echo -e "${YELLOW}Please edit .env with your IBKR credentials before running again.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ .env file exists${NC}"

# ==============================================================================
# Build Images
# ==============================================================================

echo
echo -e "${YELLOW}[2/6] Building Docker images...${NC}"

cd "$PROJECT_ROOT"

# Build all service images
docker-compose build --parallel

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Images built successfully${NC}"
else
    echo -e "${RED}ERROR: Failed to build images${NC}"
    exit 1
fi

# ==============================================================================
# Start Infrastructure Services
# ==============================================================================

echo
echo -e "${YELLOW}[3/6] Starting infrastructure services...${NC}"

# Start Zookeeper first
echo -e "${BLUE}Starting Zookeeper...${NC}"
docker-compose up -d zookeeper

# Wait for Zookeeper
sleep 5

# Start Kafka
echo -e "${BLUE}Starting Kafka...${NC}"
docker-compose up -d kafka

# Wait for Kafka to be healthy
echo -e "${BLUE}Waiting for Kafka to be healthy...${NC}"
KAFKA_READY=0
for i in {1..30}; do
    if docker-compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
        KAFKA_READY=1
        break
    fi
    echo -n "."
    sleep 2
done
echo

if [ $KAFKA_READY -eq 0 ]; then
    echo -e "${RED}ERROR: Kafka failed to start${NC}"
    docker-compose logs kafka
    exit 1
fi
echo -e "${GREEN}✓ Kafka is healthy${NC}"

# Start Vault
echo -e "${BLUE}Starting Vault...${NC}"
docker-compose up -d vault
sleep 3
echo -e "${GREEN}✓ Vault started${NC}"

# ==============================================================================
# Start Monitoring Stack
# ==============================================================================

echo
echo -e "${YELLOW}[4/6] Starting monitoring stack...${NC}"

docker-compose up -d prometheus grafana alertmanager

sleep 5
echo -e "${GREEN}✓ Monitoring stack started${NC}"

# ==============================================================================
# Start Application Services
# ==============================================================================

echo
echo -e "${YELLOW}[5/6] Starting application services...${NC}"

# Start Data Plane
echo -e "${BLUE}Starting Data Plane...${NC}"
docker-compose up -d data-plane
sleep 5

# Start Strategy Plane
echo -e "${BLUE}Starting Strategy Plane...${NC}"
docker-compose up -d strategy-plane
sleep 5

# Start Order Plane
echo -e "${BLUE}Starting Order Plane...${NC}"
docker-compose up -d order-plane
sleep 5

echo -e "${GREEN}✓ Application services started${NC}"

# ==============================================================================
# Health Check
# ==============================================================================

echo
echo -e "${YELLOW}[6/6] Running health checks...${NC}"

# Function to check HTTP endpoint
check_endpoint() {
    local name=$1
    local url=$2
    local max_attempts=10

    for i in $(seq 1 $max_attempts); do
        if curl -f -s "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $name is healthy${NC}"
            return 0
        fi
        sleep 2
    done

    echo -e "${RED}✗ $name failed health check${NC}"
    return 1
}

# Check services
check_endpoint "Data Plane" "http://localhost:8000/healthz" || true
check_endpoint "Strategy Plane" "http://localhost:8001/healthz" || true
check_endpoint "Order Plane" "http://localhost:8002/healthz" || true
check_endpoint "Prometheus" "http://localhost:9090/-/healthy" || true
check_endpoint "Grafana" "http://localhost:3000/api/health" || true

# ==============================================================================
# Summary
# ==============================================================================

echo
echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}✓ Algo-Trade system started successfully!${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo
echo -e "${BLUE}Service URLs:${NC}"
echo -e "  Grafana:        ${GREEN}http://localhost:3000${NC} (admin/admin)"
echo -e "  Prometheus:     ${GREEN}http://localhost:9090${NC}"
echo -e "  AlertManager:   ${GREEN}http://localhost:9093${NC}"
echo -e "  Data Plane:     ${GREEN}http://localhost:8000/metrics${NC}"
echo -e "  Strategy Plane: ${GREEN}http://localhost:8001/metrics${NC}"
echo -e "  Order Plane:    ${GREEN}http://localhost:8002/metrics${NC}"
echo
echo -e "${YELLOW}Useful commands:${NC}"
echo -e "  View logs:      ${GREEN}docker-compose logs -f [service-name]${NC}"
echo -e "  Stop system:    ${GREEN}./scripts/docker-stop.sh${NC}"
echo -e "  Restart:        ${GREEN}docker-compose restart [service-name]${NC}"
echo
