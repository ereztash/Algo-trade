#!/bin/bash
set -e

# AlgoTrader Docker Entrypoint Script
# This script handles initialization for all three planes

echo "========================================"
echo "AlgoTrader Service Starting"
echo "========================================"
echo "Service: ${SERVICE_NAME:-Unknown}"
echo "Environment: ${APP_ENV:-development}"
echo "========================================"

# Wait for Kafka to be ready
wait_for_kafka() {
    echo "Waiting for Kafka to be ready..."
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if nc -z kafka 29092; then
            echo "✓ Kafka is ready"
            return 0
        fi
        attempt=$((attempt + 1))
        echo "Waiting for Kafka... (attempt $attempt/$max_attempts)"
        sleep 2
    done

    echo "✗ Kafka is not available after $max_attempts attempts"
    return 1
}

# Create necessary Kafka topics
create_kafka_topics() {
    echo "Creating Kafka topics..."

    # Check if kafka-topics command is available
    # If not, we'll rely on auto-creation in Kafka
    echo "Note: Topics will be auto-created by Kafka when first accessed"
}

# Verify Python environment
verify_python_env() {
    echo "Verifying Python environment..."
    python --version
    echo "Python path: $(which python)"
    echo "PYTHONPATH: ${PYTHONPATH}"
}

# Create necessary directories
create_directories() {
    echo "Creating necessary directories..."
    mkdir -p /app/data /app/logs /app/config
    echo "✓ Directories created"
}

# Main initialization
main() {
    echo "Starting initialization..."

    create_directories
    verify_python_env
    wait_for_kafka

    echo "========================================"
    echo "Initialization complete!"
    echo "Starting service: $@"
    echo "========================================"

    # Execute the command passed to the script
    exec "$@"
}

# Run main with all arguments
main "$@"
