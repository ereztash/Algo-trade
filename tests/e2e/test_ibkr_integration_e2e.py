"""
End-to-End tests for IBKR Integration

This module tests the complete IBKR integration flow:
- Data Plane: Market data retrieval
- Strategy Plane: Signal generation (simulated)
- Order Plane: Order execution

Author: Algo-trade Team
Updated: 2025-11-17
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime

from data_plane.connectors.ibkr.client import IBKRMarketClient
from order_plane.broker.ibkr_exec_client import IBKRExecClient
from algo_trade.core.execution.IBKR_handler import IBKRConfig, IBKRConnectionError


@pytest.mark.e2e
class TestIBKRIntegrationE2E:
    """End-to-end tests for IBKR integration."""

    @pytest.fixture
    def market_client_config(self):
        """Configuration for market data client."""
        return {
            'host': '127.0.0.1',
            'port': 7497,
            'client_id': 2,
            'timeout': 30
        }

    @pytest.fixture
    def exec_client_config(self):
        """Configuration for execution client."""
        return {
            'host': '127.0.0.1',
            'port': 7497,
            'client_id': 1,
            'timeout': 30
        }

    @pytest.fixture
    async def market_client(self, market_client_config):
        """Create market data client."""
        client = IBKRMarketClient(market_client_config)
        yield client
        await client.disconnect()

    @pytest.fixture
    async def exec_client(self, exec_client_config):
        """Create execution client."""
        client = IBKRExecClient(exec_client_config)
        yield client
        await client.disconnect()

    @pytest.mark.skip(reason="Requires live IBKR connection")
    @pytest.mark.asyncio
    async def test_market_data_flow(self, market_client):
        """
        Test market data flow:
        1. Connect to IBKR
        2. Subscribe to real-time data
        3. Request historical data
        4. Verify data reception
        """
        # Connect
        await market_client.connect()
        assert market_client.health()['connected']

        # Request historical data
        contract = {'symbol': 'SPY'}
        hist_data = await market_client.request_hist(
            contract,
            duration='1 D',
            barSize='1 min',
            whatToShow='TRADES'
        )

        # Verify historical data
        assert len(hist_data) > 0
        assert hist_data[0]['symbol'] == 'SPY'
        assert 'open' in hist_data[0]
        assert 'close' in hist_data[0]

        # Subscribe to real-time data
        await market_client.subscribe_rt(contract, 'TRADES')

        # Wait for some real-time bars
        await asyncio.sleep(10)

        # Check health
        health = market_client.health()
        assert health['subscriptions'] > 0

    @pytest.mark.skip(reason="Requires live IBKR connection")
    @pytest.mark.asyncio
    async def test_order_execution_flow(self, exec_client):
        """
        Test order execution flow:
        1. Connect to IBKR
        2. Get account summary
        3. Place a test order
        4. Get order status
        5. Cancel order
        """
        # Connect
        await exec_client.connect()
        assert exec_client.health()['connected']

        # Get account summary
        summary = await exec_client.get_account_summary()
        assert 'nav' in summary
        assert summary['nav'] > 0

        # Get initial positions
        positions = await exec_client.get_positions()
        initial_position_count = len(positions)

        # Place a small test order (will not fill immediately)
        intent = {
            'symbol': 'SPY',
            'action': 'BUY',
            'quantity': 1,
            'order_type': 'LMT',
            'limit_price': 1.0,  # Very low price, won't fill
            'intent_id': 'test_001'
        }

        exec_report = await exec_client.place(intent)

        # Verify order placed
        assert 'order_id' in exec_report
        assert exec_report['symbol'] == 'SPY'
        assert exec_report['action'] == 'BUY'

        # Wait a bit
        await asyncio.sleep(2)

        # Poll reports
        reports = await exec_client.poll_reports()
        assert len(reports) > 0

        # Cancel the order
        cancel_result = await exec_client.cancel(exec_report['order_id'])
        assert cancel_result['cancelled']

    @pytest.mark.skip(reason="Requires live IBKR connection")
    @pytest.mark.asyncio
    async def test_full_trading_loop(self, market_client, exec_client):
        """
        Test complete trading loop:
        1. Get market data
        2. Generate signal (mock)
        3. Place order
        4. Monitor execution
        5. Update positions
        """
        # Connect both clients
        await market_client.connect()
        await exec_client.connect()

        # Step 1: Get market data
        contract = {'symbol': 'SPY'}
        hist_data = await market_client.request_hist(
            contract,
            duration='1 D',
            barSize='5 mins'
        )

        assert len(hist_data) > 0
        latest_price = hist_data[-1]['close']

        # Step 2: Generate mock signal
        # (In real system, this would be from strategy_plane)
        signal_strength = 0.5  # Mock signal

        # Step 3: Calculate position size (mock)
        summary = await exec_client.get_account_summary()
        nav = summary['nav']
        position_size = int(nav * 0.01 / latest_price)  # 1% of NAV

        if position_size > 0:
            # Step 4: Place order
            intent = {
                'symbol': 'SPY',
                'action': 'BUY',
                'quantity': position_size,
                'order_type': 'LMT',
                'limit_price': latest_price * 0.99,  # 1% below market
                'intent_id': f'signal_{datetime.utcnow().timestamp()}'
            }

            exec_report = await exec_client.place(intent)
            order_id = exec_report['order_id']

            # Step 5: Monitor for 10 seconds
            for _ in range(5):
                await asyncio.sleep(2)
                reports = await exec_client.poll_reports()

                for report in reports:
                    if report['order_id'] == order_id:
                        print(f"Order status: {report['status']}")

            # Step 6: Cancel if not filled
            await exec_client.cancel(order_id)

    @pytest.mark.asyncio
    async def test_mock_trading_loop(self):
        """
        Test trading loop with mocked IBKR.

        This test doesn't require live IBKR connection.
        """
        with patch('order_plane.broker.ibkr_exec_client.IBKRHandler') as mock_handler_class:
            # Setup mocks
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler
            mock_handler.connect.return_value = True
            mock_handler.is_connected.return_value = True

            # Mock account summary
            mock_handler.get_account_summary.return_value = {
                'nav': 100000.0,
                'cash': 50000.0,
                'buying_power': 200000.0
            }

            # Mock order placement
            mock_handler.place_order.return_value = {
                'order_id': 12345,
                'status': 'Submitted',
                'symbol': 'SPY',
                'action': 'BUY',
                'quantity': 10
            }

            # Create client
            exec_client = IBKRExecClient({
                'host': '127.0.0.1',
                'port': 7497,
                'client_id': 1
            })

            # Connect
            await exec_client.connect()

            # Get account
            summary = await exec_client.get_account_summary()
            assert summary['nav'] == 100000.0

            # Place order
            intent = {
                'symbol': 'SPY',
                'action': 'BUY',
                'quantity': 10,
                'order_type': 'MKT'
            }

            report = await exec_client.place(intent)
            assert report['order_id'] == 12345
            assert report['status'] == 'Submitted'

    @pytest.mark.asyncio
    async def test_error_handling_connection_lost(self):
        """Test error handling when connection is lost."""
        with patch('order_plane.broker.ibkr_exec_client.IBKRHandler') as mock_handler_class:
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler

            # Simulate connection loss
            mock_handler.connect.return_value = True
            mock_handler.is_connected.return_value = False
            mock_handler.get_account_summary.side_effect = IBKRConnectionError("Not connected")

            exec_client = IBKRExecClient({
                'host': '127.0.0.1',
                'port': 7497,
                'client_id': 1
            })

            await exec_client.connect()

            # Should raise error when trying to get account
            with pytest.raises(IBKRConnectionError):
                await exec_client.get_account_summary()

    @pytest.mark.asyncio
    async def test_concurrent_clients(self):
        """Test running market data and execution clients concurrently."""
        with patch('data_plane.connectors.ibkr.client.IB') as mock_ib_market, \
             patch('order_plane.broker.ibkr_exec_client.IBKRHandler') as mock_handler_exec:

            # Setup market client mock
            mock_ib_instance = Mock()
            mock_ib_market.return_value = mock_ib_instance
            mock_ib_instance.isConnected.return_value = True

            # Setup exec client mock
            mock_handler = Mock()
            mock_handler_exec.return_value = mock_handler
            mock_handler.connect.return_value = True

            # Create clients
            market_client = IBKRMarketClient({
                'host': '127.0.0.1',
                'port': 7497,
                'client_id': 2
            })

            exec_client = IBKRExecClient({
                'host': '127.0.0.1',
                'port': 7497,
                'client_id': 1
            })

            # Connect both concurrently
            await asyncio.gather(
                market_client.connect(),
                exec_client.connect()
            )

            # Verify both connected
            assert market_client.health()['connected']
            assert exec_client.health()['connected']


@pytest.mark.e2e
class TestIBKRReconnection:
    """Test reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnection_after_disconnect(self):
        """Test automatic reconnection after disconnect."""
        with patch('algo_trade.core.execution.IBKR_handler.IB') as mock_ib_class:
            mock_ib = Mock()
            mock_ib_class.return_value = mock_ib

            # First connect succeeds
            mock_ib.isConnected.side_effect = [False, True, True]
            mock_ib.connect.return_value = None

            from algo_trade.core.execution.IBKR_handler import IBKRHandler, IBKRConfig

            handler = IBKRHandler(IBKRConfig())

            # Connect
            result = handler.connect()
            assert result is True

            # Simulate disconnect
            mock_ib.isConnected.return_value = False
            handler._on_disconnected()

            # Reconnect
            mock_ib.isConnected.side_effect = [False, True]
            result = handler.connect()
            assert result is True


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-m', 'e2e'])
