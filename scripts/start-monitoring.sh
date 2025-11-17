#!/bin/bash

# Start Monitoring Stack for Algo-Trade System
# This script starts Prometheus, Grafana, Alertmanager, and Node Exporter

set -e

echo "🚀 Starting Algo-Trade Monitoring Stack..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed."
    echo "Please install docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# Navigate to project root
cd "$(dirname "$0")/.."

# Create necessary directories if they don't exist
echo "📁 Creating monitoring directories..."
mkdir -p monitoring/prometheus
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/alertmanager

# Start the monitoring stack
echo ""
echo "🐳 Starting Docker containers..."
docker-compose -f docker-compose.monitoring.yml up -d

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to start..."
sleep 5

# Check service health
echo ""
echo "🏥 Checking service health..."

# Check Prometheus
if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
    echo "✅ Prometheus is healthy (http://localhost:9090)"
else
    echo "⚠️  Prometheus may not be ready yet"
fi

# Check Grafana
if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
    echo "✅ Grafana is healthy (http://localhost:3000)"
    echo "   📝 Default credentials: admin/admin"
else
    echo "⚠️  Grafana may not be ready yet"
fi

# Check Alertmanager
if curl -s http://localhost:9093/-/healthy > /dev/null 2>&1; then
    echo "✅ Alertmanager is healthy (http://localhost:9093)"
else
    echo "⚠️  Alertmanager may not be ready yet"
fi

# Check Node Exporter
if curl -s http://localhost:9100/metrics > /dev/null 2>&1; then
    echo "✅ Node Exporter is healthy (http://localhost:9100)"
else
    echo "⚠️  Node Exporter may not be ready yet"
fi

# Display summary
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✨ Monitoring Stack Started Successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🌐 Access the following services:"
echo ""
echo "   Grafana (Dashboards):     http://localhost:3000"
echo "   Prometheus (Metrics):     http://localhost:9090"
echo "   Alertmanager (Alerts):    http://localhost:9093"
echo "   Node Exporter (System):   http://localhost:9100"
echo ""
echo "📊 Next steps:"
echo ""
echo "   1. Start your application: python -m data_plane.app.main"
echo "   2. Open Grafana at http://localhost:3000"
echo "   3. Login with admin/admin"
echo "   4. Navigate to 'Algo-Trade System Overview' dashboard"
echo ""
echo "📖 For more information, see MONITORING.md"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 Useful commands:"
echo ""
echo "   View logs:     docker-compose -f docker-compose.monitoring.yml logs -f"
echo "   Stop stack:    docker-compose -f docker-compose.monitoring.yml down"
echo "   Restart stack: docker-compose -f docker-compose.monitoring.yml restart"
echo ""
