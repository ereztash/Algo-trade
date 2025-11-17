"""
Unit tests for IBKR Handler

This module tests the IBKR integration including:
- Connection management
- Account summary retrieval
- Position tracking
- Order management
- Error handling
- Reconnection logic

Author: Algo-trade Team
Updated: 2025-11-17
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime

from algo_trade.core.execution.IBKR_handler import (
    IBKRHandler,
    IBKRConfig,
    IBKRConnectionError
)


class TestIBKRConfig:
    """Test IBKRConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = IBKRConfig()

        assert config.host == '127.0.0.1'
        assert config.port == 7497
        assert config.client_id == 1
        assert config.timeout == 30
        assert config.reconnect_attempts == 5
        assert config.reconnect_backoff == [1, 2, 4, 8, 16]

    def test_custom_config(self):
        """Test custom configuration values."""
        config = IBKRConfig(
            host='192.168.1.100',
            port=7496,
            client_id=5,
            timeout=60
        )

        assert config.host == '192.168.1.100'
        assert config.port == 7496
        assert config.client_id == 5
        assert config.timeout == 60


class TestIBKRHandler:
    """Test IBKRHandler class."""

    @pytest.fixture
    def mock_ib(self):
        """Create a mock IB instance."""
        with patch('algo_trade.core.execution.IBKR_handler.IB') as mock:
            ib_instance = MagicMock()
            mock.return_value = ib_instance
            yield ib_instance

    @pytest.fixture
    def handler(self, mock_ib):
        """Create an IBKRHandler with mocked IB."""
        config = IBKRConfig()
        return IBKRHandler(config)

    def test_init(self, handler):
        """Test handler initialization."""
        assert handler.config is not None
        assert handler.ib is not None
        assert handler._connected is False
        assert handler._connection_time is None
        assert handler._reconnect_count == 0

    def test_connect_success(self, handler, mock_ib):
        """Test successful connection."""
        mock_ib.isConnected.return_value = False

        # Mock successful connection
        def mock_connect(*args, **kwargs):
            mock_ib.isConnected.return_value = True

        mock_ib.connect.side_effect = mock_connect

        result = handler.connect()

        assert result is True
        mock_ib.connect.assert_called_once()

    def test_connect_already_connected(self, handler, mock_ib):
        """Test connection when already connected."""
        mock_ib.isConnected.return_value = True

        result = handler.connect()

        assert result is True
        mock_ib.connect.assert_not_called()

    def test_connect_failure_with_retry(self, handler, mock_ib):
        """Test connection failure with retries."""
        mock_ib.isConnected.return_value = False
        mock_ib.connect.side_effect = Exception("Connection refused")

        with pytest.raises(IBKRConnectionError) as exc_info:
            handler.connect()

        assert "Failed to connect to IBKR" in str(exc_info.value)
        assert mock_ib.connect.call_count == 5  # reconnect_attempts

    @patch('time.sleep')
    def test_connect_retry_backoff(self, mock_sleep, handler, mock_ib):
        """Test exponential backoff during retry."""
        mock_ib.isConnected.return_value = False
        mock_ib.connect.side_effect = Exception("Connection refused")

        with pytest.raises(IBKRConnectionError):
            handler.connect()

        # Verify backoff sleep calls: [1, 2, 4, 8]
        expected_calls = [call(1), call(2), call(4), call(8)]
        mock_sleep.assert_has_calls(expected_calls)

    def test_disconnect(self, handler, mock_ib):
        """Test disconnection."""
        mock_ib.isConnected.return_value = True

        handler.disconnect()

        mock_ib.disconnect.assert_called_once()

    def test_disconnect_not_connected(self, handler, mock_ib):
        """Test disconnect when not connected."""
        mock_ib.isConnected.return_value = False

        handler.disconnect()

        mock_ib.disconnect.assert_not_called()

    def test_get_account_summary(self, handler, mock_ib):
        """Test account summary retrieval."""
        mock_ib.isConnected.return_value = True

        # Mock account values
        mock_values = [
            Mock(tag='NetLiquidation', value='100000.50'),
            Mock(tag='TotalCashValue', value='50000.25'),
            Mock(tag='BuyingPower', value='200000.00'),
            Mock(tag='EquityWithLoanValue', value='95000.00'),
        ]
        mock_ib.accountValues.return_value = mock_values

        summary = handler.get_account_summary()

        assert summary['nav'] == 100000.50
        assert summary['cash'] == 50000.25
        assert summary['buying_power'] == 200000.00
        assert summary['equity_with_loan'] == 95000.00

    def test_get_account_summary_not_connected(self, handler, mock_ib):
        """Test account summary when not connected."""
        mock_ib.isConnected.return_value = False

        with pytest.raises(IBKRConnectionError):
            handler.get_account_summary()

    def test_get_positions(self, handler, mock_ib):
        """Test position retrieval."""
        mock_ib.isConnected.return_value = True

        # Mock positions
        mock_contract = Mock(symbol='SPY')
        mock_positions = [
            Mock(
                contract=mock_contract,
                position=100,
                avgCost=450.50,
                marketValue=45500.00,
                unrealizedPNL=500.00
            )
        ]
        mock_ib.positions.return_value = mock_positions

        positions = handler.get_positions()

        assert len(positions) == 1
        assert positions[0]['symbol'] == 'SPY'
        assert positions[0]['position'] == 100
        assert positions[0]['avg_cost'] == 450.50
        assert positions[0]['market_value'] == 45500.00
        assert positions[0]['unrealized_pnl'] == 500.00

    def test_get_positions_empty(self, handler, mock_ib):
        """Test empty positions."""
        mock_ib.isConnected.return_value = True
        mock_ib.positions.return_value = []

        positions = handler.get_positions()

        assert len(positions) == 0

    def test_get_orders(self, handler, mock_ib):
        """Test order retrieval."""
        mock_ib.isConnected.return_value = True

        # Mock trades
        mock_contract = Mock(symbol='AAPL')
        mock_order = Mock(
            orderId=123,
            action='BUY',
            totalQuantity=50,
            orderType='LMT'
        )
        mock_order_status = Mock(
            status='Submitted',
            filled=0,
            remaining=50
        )
        mock_trade = Mock(
            contract=mock_contract,
            order=mock_order,
            orderStatus=mock_order_status
        )
        mock_ib.openTrades.return_value = [mock_trade]

        orders = handler.get_orders()

        assert len(orders) == 1
        assert orders[0]['order_id'] == 123
        assert orders[0]['symbol'] == 'AAPL'
        assert orders[0]['action'] == 'BUY'
        assert orders[0]['quantity'] == 50
        assert orders[0]['order_type'] == 'LMT'
        assert orders[0]['status'] == 'Submitted'

    @patch('algo_trade.core.execution.IBKR_handler.Stock')
    @patch('algo_trade.core.execution.IBKR_handler.MarketOrder')
    def test_place_market_order(self, mock_market_order, mock_stock, handler, mock_ib):
        """Test placing a market order."""
        mock_ib.isConnected.return_value = True

        # Mock contract and order
        mock_contract = Mock()
        mock_stock.return_value = mock_contract

        mock_order_obj = Mock()
        mock_market_order.return_value = mock_order_obj

        mock_trade = Mock()
        mock_trade.order.orderId = 456
        mock_trade.orderStatus.status = 'Submitted'
        mock_ib.placeOrder.return_value = mock_trade

        result = handler.place_order('TSLA', 'BUY', 10, 'MKT')

        assert result['order_id'] == 456
        assert result['status'] == 'Submitted'
        assert result['symbol'] == 'TSLA'
        assert result['action'] == 'BUY'
        assert result['quantity'] == 10

        mock_stock.assert_called_once_with('TSLA', 'SMART', 'USD')
        mock_market_order.assert_called_once_with('BUY', 10)
        mock_ib.placeOrder.assert_called_once()

    @patch('algo_trade.core.execution.IBKR_handler.Stock')
    @patch('algo_trade.core.execution.IBKR_handler.LimitOrder')
    def test_place_limit_order(self, mock_limit_order, mock_stock, handler, mock_ib):
        """Test placing a limit order."""
        mock_ib.isConnected.return_value = True

        mock_contract = Mock()
        mock_stock.return_value = mock_contract

        mock_order_obj = Mock()
        mock_limit_order.return_value = mock_order_obj

        mock_trade = Mock()
        mock_trade.order.orderId = 789
        mock_trade.orderStatus.status = 'Submitted'
        mock_ib.placeOrder.return_value = mock_trade

        result = handler.place_order('GOOGL', 'SELL', 5, 'LMT', 150.50)

        assert result['order_id'] == 789
        mock_limit_order.assert_called_once_with('SELL', 5, 150.50)

    def test_place_order_invalid_action(self, handler, mock_ib):
        """Test placing order with invalid action."""
        mock_ib.isConnected.return_value = True

        with pytest.raises(ValueError) as exc_info:
            handler.place_order('SPY', 'HOLD', 10)

        assert "Invalid action" in str(exc_info.value)

    def test_place_limit_order_without_price(self, handler, mock_ib):
        """Test placing limit order without price."""
        mock_ib.isConnected.return_value = True

        with pytest.raises(ValueError) as exc_info:
            handler.place_order('SPY', 'BUY', 10, 'LMT')

        assert "limit_price required" in str(exc_info.value)

    def test_cancel_order_success(self, handler, mock_ib):
        """Test successful order cancellation."""
        mock_ib.isConnected.return_value = True

        # Mock open trades
        mock_order = Mock(orderId=123)
        mock_trade = Mock(order=mock_order)
        mock_ib.openTrades.return_value = [mock_trade]

        result = handler.cancel_order(123)

        assert result is True
        mock_ib.cancelOrder.assert_called_once_with(mock_order)

    def test_cancel_order_not_found(self, handler, mock_ib):
        """Test cancelling non-existent order."""
        mock_ib.isConnected.return_value = True
        mock_ib.openTrades.return_value = []

        result = handler.cancel_order(999)

        assert result is False

    def test_is_healthy(self, handler, mock_ib):
        """Test health check."""
        mock_ib.isConnected.return_value = True
        mock_ib.reqCurrentTime.return_value = datetime.now()

        health = handler.is_healthy()

        assert health['connected'] is True
        assert 'latency_ms' in health
        assert health['host'] == '127.0.0.1'
        assert health['port'] == 7497

    def test_is_healthy_not_connected(self, handler, mock_ib):
        """Test health check when not connected."""
        mock_ib.isConnected.return_value = False

        health = handler.is_healthy()

        assert health['connected'] is False

    def test_event_handlers(self, handler):
        """Test event handler callbacks."""
        # Test connected event
        handler._on_connected()
        assert handler._connected is True
        assert handler._connection_time is not None
        assert handler._reconnect_count == 0

        # Test disconnected event
        handler._on_disconnected()
        assert handler._connected is False

        # Test error event (should not raise)
        handler._on_error(1, 502, "Couldn't connect", None)


class TestIBKRConnectionError:
    """Test custom exception."""

    def test_exception_message(self):
        """Test exception message."""
        error = IBKRConnectionError("Test error message")
        assert str(error) == "Test error message"


@pytest.mark.integration
class TestIBKRHandlerIntegration:
    """
    Integration tests for IBKR Handler.

    These tests require a running IBKR TWS/Gateway instance.
    Skip if not available.
    """

    @pytest.fixture
    def live_handler(self):
        """Create handler for live testing."""
        config = IBKRConfig(
            host='127.0.0.1',
            port=7497,  # Paper trading
            client_id=999  # Test client ID
        )
        handler = IBKRHandler(config)
        yield handler
        handler.disconnect()

    @pytest.mark.skip(reason="Requires live IBKR connection")
    def test_live_connection(self, live_handler):
        """Test live connection to IBKR."""
        try:
            result = live_handler.connect()
            assert result is True
            assert live_handler.is_connected()
        except IBKRConnectionError:
            pytest.skip("IBKR not available")

    @pytest.mark.skip(reason="Requires live IBKR connection")
    def test_live_account_summary(self, live_handler):
        """Test live account summary."""
        try:
            live_handler.connect()
            summary = live_handler.get_account_summary()

            assert 'nav' in summary
            assert 'cash' in summary
            assert summary['nav'] > 0
        except IBKRConnectionError:
            pytest.skip("IBKR not available")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
