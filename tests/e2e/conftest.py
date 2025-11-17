"""
Shared fixtures and configuration for E2E tests.

Provides common test fixtures for:
- Message event creation
- Mock Kafka producers/consumers
- System state management
- Test data generation
"""

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from contracts.validators import (
    BarEvent, OFIEvent, OrderIntent, ExecutionReport,
    DataQuality, EventMetadata
)


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "e2e: mark test as end-to-end integration test"
    )


# =============================================================================
# Event Loop Fixture
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Common Test Data Fixtures
# =============================================================================

@pytest.fixture
def test_symbols():
    """Common symbols for testing."""
    return ['SPY', 'QQQ', 'IWM', 'TLT', 'GLD']


@pytest.fixture
def test_timestamp():
    """Generate test timestamp."""
    return datetime.now(timezone.utc)


# =============================================================================
# Event Creation Helpers
# =============================================================================

@pytest.fixture
def create_bar_event():
    """Factory for creating BarEvent instances."""

    def _create(symbol='SPY', close=450.0, **kwargs):
        defaults = {
            'event_type': 'bar_event',
            'symbol': symbol,
            'timestamp': datetime.now(timezone.utc),
            'open': close - 1.0,
            'high': close + 2.0,
            'low': close - 2.0,
            'close': close,
            'volume': 1000000,
            'bar_duration': '1d',
            'asset_class': 'equity',
            'data_quality': DataQuality(
                completeness_score=1.0,
                freshness_ms=100,
                source='ibkr_realtime'
            )
        }
        defaults.update(kwargs)
        return BarEvent(**defaults)

    return _create


@pytest.fixture
def create_order_intent():
    """Factory for creating OrderIntent instances."""

    def _create(symbol='SPY', quantity=100, **kwargs):
        defaults = {
            'intent_id': str(uuid4()),
            'symbol': symbol,
            'side': 'buy',
            'quantity': quantity,
            'order_type': 'market',
            'timestamp': datetime.now(timezone.utc),
            'strategy_id': 'test_strategy',
            'signal_strength': 0.5,
            'risk_limit_checks_passed': True
        }
        defaults.update(kwargs)
        return OrderIntent(**defaults)

    return _create


@pytest.fixture
def create_execution_report():
    """Factory for creating ExecutionReport instances."""

    def _create(intent_id=None, symbol='SPY', **kwargs):
        if intent_id is None:
            intent_id = str(uuid4())

        defaults = {
            'execution_id': str(uuid4()),
            'intent_id': intent_id,
            'symbol': symbol,
            'side': 'buy',
            'quantity': 100,
            'filled_quantity': 100,
            'avg_fill_price': 450.0,
            'status': 'filled',
            'timestamp': datetime.now(timezone.utc),
            'broker_order_id': f'IB-{str(uuid4())[:8]}',
            'commission': 1.00
        }
        defaults.update(kwargs)
        return ExecutionReport(**defaults)

    return _create
