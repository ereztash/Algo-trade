"""
Integration tests for IBKR connectivity.

These tests require:
- TWS or IB Gateway running on localhost
- Paper trading account
- API connections enabled in TWS/Gateway settings

Run with: pytest tests/integration/test_ibkr_integration.py -m "requires_ibkr"
"""

import pytest
import logging
from datetime import datetime

from algo_trade.core.execution.IBKR_handler import IBKRHandler
from order_plane.broker.ibkr_exec_client import IBKRExecClient

logger = logging.getLogger(__name__)


# ============================================================================
# IBKR Handler Integration Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.requires_ibkr
class TestIBKRHandlerIntegration:
    """Integration tests for IBKR Handler."""

    @pytest.fixture
    def handler(self):
        """Create IBKR handler for testing."""
        handler = IBKRHandler(
            host='127.0.0.1',
            port=7497,  # Paper trading
            client_id=999,  # Test client ID
            readonly=True  # Read-only for safety
        )
        yield handler
        if handler.is_connected():
            handler.disconnect()

    def test_connection(self, handler):
        """Test basic connection to IBKR."""
        success = handler.connect(timeout=10)
        assert success is True
        assert handler.is_connected() is True
        assert handler.state.value == "connected"

    def test_get_account_summary(self, handler):
        """Test retrieving account summary."""
        handler.connect()

        summary = handler.get_account_summary()

        assert isinstance(summary, dict)
        assert 'account' in summary
        assert 'net_liquidation' in summary
        assert 'cash' in summary
        assert 'buying_power' in summary

        # Paper accounts usually have significant buying power
        assert summary['buying_power'] > 0

        logger.info(f"Account NAV: ${summary['net_liquidation']:,.2f}")

    def test_get_positions(self, handler):
        """Test retrieving positions."""
        handler.connect()

        positions = handler.get_positions()

        assert isinstance(positions, list)
        # May be empty if no positions

        if positions:
            pos = positions[0]
            assert 'symbol' in pos
            assert 'position' in pos
            assert 'avg_cost' in pos
            assert 'market_value' in pos

            logger.info(f"Position: {pos['symbol']} x{pos['position']}")

    def test_get_orders(self, handler):
        """Test retrieving orders."""
        handler.connect()

        orders = handler.get_orders()

        assert isinstance(orders, list)
        # May be empty if no recent orders

        if orders:
            order = orders[0]
            assert 'order_id' in order
            assert 'symbol' in order
            assert 'action' in order
            assert 'quantity' in order
            assert 'status' in order

            logger.info(f"Order: {order['action']} {order['symbol']} x{order['quantity']}")

    def test_health_check(self, handler):
        """Test health check."""
        handler.connect()

        health = handler.health_check()

        assert isinstance(health, dict)
        assert 'connected' in health
        assert 'state' in health
        assert 'host' in health
        assert 'port' in health

        assert health['connected'] is True
        assert health['state'] == 'connected'

    def test_reconnection(self, handler):
        """Test automatic reconnection."""
        handler.connect()
        assert handler.is_connected()

        # Manually disconnect
        handler.disconnect()
        assert not handler.is_connected()

        # Try to reconnect
        success = handler.connect()
        assert success is True


# ============================================================================
# IBKR Exec Client Integration Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.requires_ibkr
class TestIBKRExecClientIntegration:
    """Integration tests for IBKR Execution Client."""

    @pytest.fixture
    async def exec_client(self):
        """Create execution client for testing."""
        cfg = {
            'host': '127.0.0.1',
            'port': 7497,
            'client_id': 998,
            'readonly': True  # Read-only for safety
        }
        client = IBKRExecClient(cfg)
        await client.connect()
        yield client
        await client.disconnect()

    @pytest.mark.asyncio
    async def test_connection(self, exec_client):
        """Test execution client connection."""
        health = exec_client.health()

        assert health['connected'] is True
        assert health['session'] == 'exec'
        assert 'account' in health

    @pytest.mark.asyncio
    async def test_get_account_info(self, exec_client):
        """Test getting account info via exec client."""
        account_info = await exec_client.get_account_info()

        assert isinstance(account_info, dict)
        assert 'net_liquidation' in account_info
        assert 'cash' in account_info

    @pytest.mark.asyncio
    async def test_get_positions(self, exec_client):
        """Test getting positions via exec client."""
        positions = await exec_client.get_positions()

        assert isinstance(positions, list)


# ============================================================================
# End-to-End Integration Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.requires_ibkr
@pytest.mark.slow
class TestE2EIntegration:
    """End-to-end integration tests."""

    @pytest.fixture
    def handler(self):
        """Create handler for E2E testing."""
        handler = IBKRHandler(
            port=7497,
            readonly=True
        )
        handler.connect()
        yield handler
        handler.disconnect()

    def test_full_workflow(self, handler):
        """Test complete workflow: connect, query, monitor."""
        # Step 1: Connect and verify
        assert handler.is_connected()

        # Step 2: Get account summary
        summary = handler.get_account_summary()
        assert summary['net_liquidation'] > 0

        # Step 3: Get positions
        positions = handler.get_positions()
        assert isinstance(positions, list)

        # Step 4: Get orders
        orders = handler.get_orders()
        assert isinstance(orders, list)

        # Step 5: Health check
        health = handler.health_check()
        assert health['connected'] is True

        logger.info("✅ Full workflow test completed successfully")


# ============================================================================
# Performance Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.requires_ibkr
@pytest.mark.performance
class TestIBKRPerformance:
    """Performance tests for IBKR integration."""

    @pytest.fixture
    def handler(self):
        handler = IBKRHandler(port=7497, readonly=True)
        handler.connect()
        yield handler
        handler.disconnect()

    def test_account_summary_performance(self, handler, benchmark):
        """Benchmark account summary retrieval."""
        result = benchmark(handler.get_account_summary, refresh=True)
        assert isinstance(result, dict)

    def test_positions_performance(self, handler, benchmark):
        """Benchmark positions retrieval."""
        result = benchmark(handler.get_positions, refresh=True)
        assert isinstance(result, list)


# ============================================================================
# Utility Functions
# ============================================================================


def check_ibkr_available():
    """Check if IBKR is available for testing."""
    try:
        handler = IBKRHandler(port=7497, readonly=True)
        success = handler.connect(timeout=5)
        if success:
            handler.disconnect()
            return True
        return False
    except Exception:
        return False


if __name__ == "__main__":
    # Quick connectivity check
    logging.basicConfig(level=logging.INFO)

    print("Checking IBKR connectivity...")
    if check_ibkr_available():
        print("✅ IBKR is available")
        print("\nRun integration tests with:")
        print("  pytest tests/integration/test_ibkr_integration.py -m 'requires_ibkr' -v")
    else:
        print("❌ IBKR not available")
        print("\nTo run integration tests:")
        print("  1. Start TWS or IB Gateway (Paper Trading)")
        print("  2. Enable API connections in settings")
        print("  3. Run: pytest tests/integration/test_ibkr_integration.py -m 'requires_ibkr' -v")
