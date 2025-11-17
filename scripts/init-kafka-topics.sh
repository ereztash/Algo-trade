#!/bin/bash
# =============================================================================
# Kafka Topic Initialization Script
# =============================================================================
# Purpose: Create all required Kafka topics for Algo-Trade system
# Reference: /contracts/topics.yaml
# Usage: ./scripts/init-kafka-topics.sh
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
KAFKA_BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP_SERVERS:-localhost:9092}"
REPLICATION_FACTOR="${KAFKA_REPLICATION_FACTOR:-1}"  # Single broker = 1
PARTITIONS="${KAFKA_PARTITIONS:-3}"                   # Default 3 partitions for parallelism

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}Kafka Topic Initialization for Algo-Trade${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo "Bootstrap Server: $KAFKA_BOOTSTRAP_SERVER"
echo "Replication Factor: $REPLICATION_FACTOR"
echo "Default Partitions: $PARTITIONS"
echo ""

# Function to check if Kafka is available
check_kafka() {
    echo -e "${YELLOW}Checking Kafka availability...${NC}"

    # Try to list topics (will fail if Kafka is not ready)
    if kafka-topics.sh --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --list &> /dev/null; then
        echo -e "${GREEN}✓ Kafka is available${NC}"
        return 0
    else
        echo -e "${RED}✗ Kafka is not available${NC}"
        echo -e "${RED}Please ensure Kafka is running: docker-compose up -d kafka${NC}"
        exit 1
    fi
}

# Function to create a topic
create_topic() {
    local topic_name=$1
    local partitions=$2
    local retention_ms=$3
    local cleanup_policy=$4
    local min_insync_replicas=$5
    local acks=$6

    echo -e "${YELLOW}Creating topic: $topic_name${NC}"

    # Check if topic already exists
    if kafka-topics.sh --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --list | grep -q "^${topic_name}$"; then
        echo -e "${GREEN}  ✓ Topic already exists: $topic_name${NC}"
        return 0
    fi

    # Build configuration string
    local config="retention.ms=$retention_ms,cleanup.policy=$cleanup_policy"

    if [ -n "$min_insync_replicas" ]; then
        config="$config,min.insync.replicas=$min_insync_replicas"
    fi

    # Create topic
    kafka-topics.sh --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" \
        --create \
        --topic "$topic_name" \
        --partitions "$partitions" \
        --replication-factor "$REPLICATION_FACTOR" \
        --config "$config" \
        --if-not-exists

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ Created topic: $topic_name${NC}"
    else
        echo -e "${RED}  ✗ Failed to create topic: $topic_name${NC}"
        exit 1
    fi
}

# Check Kafka availability
check_kafka

echo -e "${YELLOW}==============================================================================${NC}"
echo -e "${YELLOW}Creating Market Data Topics${NC}"
echo -e "${YELLOW}==============================================================================${NC}"

# Topic: market_raw
# Purpose: Raw market data from IBKR (before normalization)
# Retention: 8 hours (28800000 ms)
# Cleanup: delete
create_topic "market_raw" 3 28800000 "delete" "" ""

# Topic: market_events
# Purpose: Normalized market data events (BarEvent, TickEvent)
# Retention: 24 hours (86400000 ms)
# Cleanup: compact (log compaction enabled, keyed by conid)
# Note: Log compaction allows replaying latest state per conid
create_topic "market_events" 3 86400000 "compact" "" ""

# Topic: ofi_events
# Purpose: Order Flow Imbalance (OFI) signals from Data Plane
# Retention: 24 hours (86400000 ms)
# Cleanup: delete
create_topic "ofi_events" 3 86400000 "delete" "" ""

echo ""
echo -e "${YELLOW}==============================================================================${NC}"
echo -e "${YELLOW}Creating Trading Topics${NC}"
echo -e "${YELLOW}==============================================================================${NC}"

# Topic: order_intents
# Purpose: Order intents from Strategy Plane to Order Plane
# Retention: 6 hours (21600000 ms)
# Cleanup: delete
# Config: acks=all for durability (min.insync.replicas=1)
create_topic "order_intents" 3 21600000 "delete" 1 "all"

# Topic: exec_reports
# Purpose: Execution reports from Order Plane (order fills, rejections, etc.)
# Retention: 7 days (604800000 ms)
# Cleanup: delete
# Note: Longer retention for reconciliation and learning loop
create_topic "exec_reports" 3 604800000 "delete" "" ""

echo ""
echo -e "${YELLOW}==============================================================================${NC}"
echo -e "${YELLOW}Creating Dead Letter Queue (DLQ) Topics${NC}"
echo -e "${YELLOW}==============================================================================${NC}"

# Topic: dlq_market_events
# Purpose: Invalid BarEvent/TickEvent/OFIEvent messages
# Retention: 7 days (604800000 ms)
# Cleanup: delete
create_topic "dlq_market_events" 1 604800000 "delete" "" ""

# Topic: dlq_order_intents
# Purpose: Invalid OrderIntent messages
# Retention: 7 days (604800000 ms)
# Cleanup: delete
create_topic "dlq_order_intents" 1 604800000 "delete" "" ""

# Topic: dlq_execution_reports
# Purpose: Invalid ExecutionReport messages
# Retention: 7 days (604800000 ms)
# Cleanup: delete
create_topic "dlq_execution_reports" 1 604800000 "delete" "" ""

echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}Topic Creation Complete!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""

# List all topics
echo -e "${YELLOW}Listing all topics:${NC}"
kafka-topics.sh --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --list

echo ""
echo -e "${YELLOW}Topic Details:${NC}"

# Describe key topics
for topic in market_raw market_events ofi_events order_intents exec_reports; do
    echo ""
    echo -e "${YELLOW}Topic: $topic${NC}"
    kafka-topics.sh --bootstrap-server "$KAFKA_BOOTSTRAP_SERVER" --describe --topic "$topic"
done

echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}Kafka topics are ready for use!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Verify topics in Kafka UI: http://localhost:8080"
echo "  2. Start Data Plane to publish market data"
echo "  3. Start Strategy Plane to consume market data and generate signals"
echo "  4. Start Order Plane to execute orders"
echo ""
