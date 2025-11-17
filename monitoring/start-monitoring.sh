#!/bin/bash
# Algo-Trading Monitoring Stack Startup Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║        Algo-Trading Monitoring Stack - Startup Script         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

echo "✓ Docker is running"
echo ""

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed."
    echo "   Please install docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ docker-compose is available"
echo ""

# Start monitoring stack
echo "Starting monitoring stack..."
echo "  - Prometheus (metrics storage)"
echo "  - Grafana (dashboards)"
echo "  - Alertmanager (alerting)"
echo "  - Node Exporter (system metrics)"
echo "  - Pushgateway (batch jobs)"
echo ""

cd "$PROJECT_ROOT"

docker-compose -f docker-compose.monitoring.yml up -d

echo ""
echo "Waiting for services to be ready..."
sleep 5

# Check service health
echo ""
echo "Checking service health..."

services=("prometheus:9091" "grafana:3000" "alertmanager:9093")
all_healthy=true

for service in "${services[@]}"; do
    service_name="${service%%:*}"
    port="${service##*:}"

    if curl -s "http://localhost:$port" > /dev/null 2>&1 || \
       curl -s "http://localhost:$port/api/health" > /dev/null 2>&1; then
        echo "  ✓ $service_name is healthy"
    else
        echo "  ❌ $service_name is not responding"
        all_healthy=false
    fi
done

echo ""

if [ "$all_healthy" = true ]; then
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║                   ✅ Monitoring Stack Ready!                   ║"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📊 Access your monitoring services:"
    echo ""
    echo "  Grafana:         http://localhost:3000"
    echo "                   Username: admin"
    echo "                   Password: algo-trade-2024"
    echo ""
    echo "  Prometheus:      http://localhost:9091"
    echo "  Alertmanager:    http://localhost:9093"
    echo ""
    echo "📈 Available Dashboards:"
    echo "  - System Health:         /d/algo-trade-system-health"
    echo "  - Data Quality:          /d/algo-trade-data-quality"
    echo "  - Strategy Performance:  /d/algo-trade-strategy-performance"
    echo "  - Risk Monitoring:       /d/algo-trade-risk-monitoring"
    echo ""
    echo "📚 Documentation: docs/MONITORING.md"
    echo ""
    echo "To view logs:  docker-compose -f docker-compose.monitoring.yml logs -f [service]"
    echo "To stop:       docker-compose -f docker-compose.monitoring.yml down"
    echo ""
else
    echo "⚠️  Warning: Some services are not healthy."
    echo "   Check logs: docker-compose -f docker-compose.monitoring.yml logs"
    exit 1
fi
