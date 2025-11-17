#!/bin/bash

# Stop Monitoring Stack for Algo-Trade System

set -e

echo "🛑 Stopping Algo-Trade Monitoring Stack..."
echo ""

# Navigate to project root
cd "$(dirname "$0")/.."

# Stop the monitoring stack
docker-compose -f docker-compose.monitoring.yml down

echo ""
echo "✅ Monitoring stack stopped successfully!"
echo ""
echo "💡 To preserve data, volumes are kept. To remove all data:"
echo "   docker-compose -f docker-compose.monitoring.yml down -v"
echo ""
