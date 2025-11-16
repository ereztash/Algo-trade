#!/bin/bash
# ==============================================================================
# Algo-Trade Docker Stack Shutdown Script
# ==============================================================================
# Gracefully stops the complete algo-trading system
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}  Algo-Trade System - Docker Stack Shutdown${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo

cd "$PROJECT_ROOT"

# ==============================================================================
# Stop Application Services First
# ==============================================================================

echo -e "${YELLOW}[1/3] Stopping application services...${NC}"

docker-compose stop order-plane
echo -e "${GREEN}✓ Order Plane stopped${NC}"

docker-compose stop strategy-plane
echo -e "${GREEN}✓ Strategy Plane stopped${NC}"

docker-compose stop data-plane
echo -e "${GREEN}✓ Data Plane stopped${NC}"

# ==============================================================================
# Stop Monitoring Stack
# ==============================================================================

echo
echo -e "${YELLOW}[2/3] Stopping monitoring stack...${NC}"

docker-compose stop alertmanager grafana prometheus
echo -e "${GREEN}✓ Monitoring stack stopped${NC}"

# ==============================================================================
# Stop Infrastructure
# ==============================================================================

echo
echo -e "${YELLOW}[3/3] Stopping infrastructure services...${NC}"

docker-compose stop vault kafka zookeeper
echo -e "${GREEN}✓ Infrastructure stopped${NC}"

# ==============================================================================
# Summary
# ==============================================================================

echo
echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}✓ Algo-Trade system stopped successfully!${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo
echo -e "${YELLOW}To completely remove all containers and volumes:${NC}"
echo -e "  ${RED}docker-compose down -v${NC}"
echo
echo -e "${YELLOW}To restart the system:${NC}"
echo -e "  ${GREEN}./scripts/docker-start.sh${NC}"
echo
