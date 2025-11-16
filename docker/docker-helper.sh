#!/bin/bash
# AlgoTrader Docker Helper Script
# Provides convenient commands for managing the AlgoTrader Docker environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${GREEN}========================================"
    echo -e "$1"
    echo -e "========================================${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Copying from .env.example..."
        cp .env.example .env
        print_success "Created .env file. Please review and update it with your settings."
        echo "Key settings to configure:"
        echo "  - IBKR_HOST, IBKR_PORT (for Interactive Brokers connection)"
        echo "  - GRAFANA_ADMIN_PASSWORD"
        echo ""
        read -p "Press Enter to continue after reviewing .env file..."
    fi
}

# Start all services
start() {
    print_header "Starting AlgoTrader Services"
    check_env_file
    docker-compose up -d
    print_success "All services started!"
    echo ""
    print_service_urls
}

# Stop all services
stop() {
    print_header "Stopping AlgoTrader Services"
    docker-compose down
    print_success "All services stopped!"
}

# Restart all services
restart() {
    print_header "Restarting AlgoTrader Services"
    docker-compose restart
    print_success "All services restarted!"
}

# Build images
build() {
    print_header "Building AlgoTrader Images"
    docker-compose build --no-cache
    print_success "Images built successfully!"
}

# Show logs
logs() {
    local service=$1
    if [ -z "$service" ]; then
        docker-compose logs -f
    else
        docker-compose logs -f "$service"
    fi
}

# Show status
status() {
    print_header "AlgoTrader Service Status"
    docker-compose ps
    echo ""
    print_header "Container Health"
    docker ps --filter "name=algotrader" --format "table {{.Names}}\t{{.Status}}"
}

# Clean everything (including volumes)
clean() {
    print_warning "This will remove all containers, volumes, and data. Are you sure? (y/N)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        print_header "Cleaning AlgoTrader Environment"
        docker-compose down -v
        docker system prune -f
        print_success "Environment cleaned!"
    else
        print_warning "Clean cancelled"
    fi
}

# Print service URLs
print_service_urls() {
    print_header "Service URLs"
    echo "Grafana:     http://localhost:3000 (admin/admin)"
    echo "Prometheus:  http://localhost:9090"
    echo "Kafka UI:    http://localhost:8090"
    echo "Data Plane:  http://localhost:8000/metrics"
    echo "Strategy:    http://localhost:8001/metrics"
    echo "Order:       http://localhost:8002/metrics"
    echo ""
}

# Show help
show_help() {
    echo "AlgoTrader Docker Helper"
    echo ""
    echo "Usage: ./docker-helper.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       Start all services"
    echo "  stop        Stop all services"
    echo "  restart     Restart all services"
    echo "  build       Build Docker images"
    echo "  logs [svc]  Show logs (optionally for specific service)"
    echo "  status      Show service status"
    echo "  clean       Remove all containers and volumes"
    echo "  urls        Show service URLs"
    echo "  help        Show this help message"
    echo ""
    echo "Services:"
    echo "  data-plane, strategy-plane, order-plane"
    echo "  kafka, zookeeper, prometheus, grafana"
    echo ""
}

# Main command router
case "${1}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    build)
        build
        ;;
    logs)
        logs "${2}"
        ;;
    status)
        status
        ;;
    clean)
        clean
        ;;
    urls)
        print_service_urls
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: ${1}"
        echo ""
        show_help
        exit 1
        ;;
esac
