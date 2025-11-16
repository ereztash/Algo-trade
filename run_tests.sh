#!/bin/bash
# AlgoTrader Test Runner
# Convenient script to run different test suites

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${GREEN}========================================"
    echo -e "$1"
    echo -e "========================================${NC}"
}

# Help function
show_help() {
    echo "AlgoTrader Test Runner"
    echo ""
    echo "Usage: ./run_tests.sh [command]"
    echo ""
    echo "Commands:"
    echo "  all            Run all tests with coverage"
    echo "  unit           Run unit tests only"
    echo "  integration    Run integration tests (requires Kafka)"
    echo "  property       Run property-based tests"
    echo "  coverage       Run tests and generate coverage report"
    echo "  fast           Run tests without slow markers"
    echo "  watch          Run tests in watch mode (requires pytest-watch)"
    echo "  clean          Clean test cache and coverage files"
    echo "  help           Show this help message"
    echo ""
}

# Run all tests with coverage
run_all() {
    print_header "Running All Tests with Coverage"
    pytest tests/ \
        --cov=algo_trade \
        --cov=data_plane \
        --cov=order_plane \
        --cov-report=term \
        --cov-report=html \
        --cov-report=xml \
        -v
}

# Run unit tests only
run_unit() {
    print_header "Running Unit Tests"
    pytest tests/ -m "unit" -v
}

# Run integration tests
run_integration() {
    print_header "Running Integration Tests"
    echo -e "${YELLOW}Note: Integration tests require Kafka to be running${NC}"
    echo -e "${YELLOW}Start Kafka with: ./docker/docker-helper.sh start${NC}"
    echo ""
    pytest tests/ -m "integration and not requires_ibkr" -v
}

# Run property-based tests
run_property() {
    print_header "Running Property-Based Tests"
    HYPOTHESIS_PROFILE=ci pytest tests/ -m "property" -v
}

# Run with coverage report
run_coverage() {
    print_header "Generating Coverage Report"
    pytest tests/ \
        -m "unit" \
        --cov=algo_trade \
        --cov=data_plane \
        --cov=order_plane \
        --cov-report=term-missing \
        --cov-report=html \
        -v
    echo ""
    echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"
}

# Run fast tests (exclude slow markers)
run_fast() {
    print_header "Running Fast Tests"
    pytest tests/ -m "not slow" -v
}

# Watch mode
run_watch() {
    print_header "Running Tests in Watch Mode"
    if command -v ptw &> /dev/null; then
        ptw -- tests/ -m "unit" -v
    else
        echo -e "${RED}pytest-watch not installed${NC}"
        echo -e "Install with: pip install pytest-watch"
        exit 1
    fi
}

# Clean test artifacts
clean() {
    print_header "Cleaning Test Artifacts"
    rm -rf .pytest_cache/
    rm -rf htmlcov/
    rm -rf .coverage
    rm -rf coverage.xml
    rm -rf test-results*.xml
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}Clean complete${NC}"
}

# Main command router
case "${1:-all}" in
    all)
        run_all
        ;;
    unit)
        run_unit
        ;;
    integration)
        run_integration
        ;;
    property)
        run_property
        ;;
    coverage)
        run_coverage
        ;;
    fast)
        run_fast
        ;;
    watch)
        run_watch
        ;;
    clean)
        clean
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: ${1}${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
