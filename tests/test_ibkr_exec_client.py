"""
Integration tests for IBKRExecClient.

Tests the complete order execution flow from OrderIntent to ExecutionReport
using a mock IBKR connection.
"""

import pytest
import asyncio
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from order_plane.broker.ibkr_exec_client import IBKRExecClient, TrackedOrder
from contracts.validators import OrderIntent, ExecutionReport


# Test fixtures
@pytest.fixture
def config():
    """IBKR client configuration."""
    return {
        'host': '127.0.0.1',
        'port': 7497,
        'client_id': 1,
        'account': 'DU12345',
        'timeout': 10,
    }


@pytest.fixture
def market_order_intent():
    """Sample MARKET order intent."""
    return OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100,
        order_type='MARKET',
        timestamp=datetime.utcnow(),
        strategy_id='COMPOSITE',
        time_in_force='DAY',
        urgency='NORMAL',
    )


@pytest.fixture
def limit_order_intent():
    """Sample LIMIT order intent."""
    return OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='TSLA',
        direction='SELL',
        quantity=50,
        order_type='LIMIT',
        limit_price=245.50,
        timestamp=datetime.utcnow(),
        strategy_id='OFI',
        time_in_force='GTC',
        urgency='HIGH',
    )


@pytest.fixture
def stop_limit_order_intent():
    """Sample STOP_LIMIT order intent."""
    return OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='SPY',
        direction='BUY',
        quantity=200,
        order_type='STOP_LIMIT',
        stop_price=450.00,
        limit_price=451.00,
        timestamp=datetime.utcnow(),
        strategy_id='VRP',
        time_in_force='DAY',
    )


class TestIBKRExecClientInit:
    """Test IBKRExecClient initialization."""

    def test_init_with_config(self, config):
        """Test initialization with config."""
        client = IBKRExecClient(config)

        assert client.host == '127.0.0.1'
        assert client.port == 7497
        assert client.client_id == 1
        assert client.account == 'DU12345'
        assert client.timeout == 10
        assert not client.is_connected()

    def test_init_with_defaults(self):
        """Test initialization with default config."""
        client = IBKRExecClient({})

        assert client.host == '127.0.0.1'
        assert client.port == 7497  # Default paper trading port
        assert client.client_id == 1
        assert client.account is None
        assert client.timeout == 10

    def test_health_disconnected(self, config):
        """Test health status when disconnected."""
        client = IBKRExecClient(config)
        health = client.health()

        assert health['connected'] is False
        assert health['session'] == 'exec'
        assert health['tracked_orders'] == 0
        assert health['host'] == '127.0.0.1'
        assert health['port'] == 7497


class TestIBKRExecClientOrderCreation:
    """Test IBKR order creation from OrderIntent."""

    def test_create_market_order(self, config, market_order_intent):
        """Test creating MARKET order from OrderIntent."""
        client = IBKRExecClient(config)
        ib_order = client._create_ibkr_order(market_order_intent)

        assert ib_order.action == 'BUY'
        assert ib_order.totalQuantity == 100
        assert ib_order.orderType == 'MKT'
        assert ib_order.tif == 'DAY'
        assert ib_order.account == 'DU12345'

    def test_create_limit_order(self, config, limit_order_intent):
        """Test creating LIMIT order from OrderIntent."""
        client = IBKRExecClient(config)
        ib_order = client._create_ibkr_order(limit_order_intent)

        assert ib_order.action == 'SELL'
        assert ib_order.totalQuantity == 50
        assert ib_order.orderType == 'LMT'
        assert ib_order.lmtPrice == 245.50
        assert ib_order.tif == 'GTC'

    def test_create_stop_limit_order(self, config, stop_limit_order_intent):
        """Test creating STOP_LIMIT order from OrderIntent."""
        client = IBKRExecClient(config)
        ib_order = client._create_ibkr_order(stop_limit_order_intent)

        assert ib_order.action == 'BUY'
        assert ib_order.totalQuantity == 200
        assert ib_order.orderType == 'STP LMT'
        assert ib_order.auxPrice == 450.00  # Stop price
        assert ib_order.lmtPrice == 451.00  # Limit price
        assert ib_order.tif == 'DAY'

    def test_order_type_mapping(self, config):
        """Test order type mapping from OrderIntent to IBKR."""
        client = IBKRExecClient(config)

        test_cases = [
            ('MARKET', 'MKT'),
            ('LIMIT', 'LMT'),
            ('STOP', 'STP'),
            ('STOP_LIMIT', 'STP LMT'),
            ('ADAPTIVE', 'MIDPRICE'),
        ]

        for intent_type, expected_ibkr_type in test_cases:
            intent = OrderIntent(
                event_type='order_intent',
                intent_id=str(uuid4()),
                symbol='TEST',
                direction='BUY',
                quantity=1,
                order_type=intent_type,
                timestamp=datetime.utcnow(),
                strategy_id='TEST',
                limit_price=100.0 if intent_type in ['LIMIT', 'STOP_LIMIT'] else None,
                stop_price=99.0 if intent_type in ['STOP', 'STOP_LIMIT'] else None,
            )

            ib_order = client._create_ibkr_order(intent)
            assert ib_order.orderType == expected_ibkr_type


class TestIBKRExecClientStatusMapping:
    """Test IBKR status mapping to ExecutionReport status."""

    def test_status_mapping(self, config):
        """Test mapping IBKR statuses to ExecutionReport statuses."""
        client = IBKRExecClient(config)

        status_mappings = {
            'PendingSubmit': 'SUBMITTED',
            'PreSubmitted': 'SUBMITTED',
            'Submitted': 'ACKNOWLEDGED',
            'Filled': 'FILLED',
            'Cancelled': 'CANCELED',
            'ApiCancelled': 'CANCELED',
            'PendingCancel': 'CANCELED',
            'Inactive': 'ERROR',
        }

        for ibkr_status, expected_status in status_mappings.items():
            assert client._map_ibkr_status(ibkr_status) == expected_status

    def test_unknown_status(self, config):
        """Test mapping unknown IBKR status defaults to ERROR."""
        client = IBKRExecClient(config)
        assert client._map_ibkr_status('UnknownStatus') == 'ERROR'


class TestIBKRExecClientExecutionReport:
    """Test ExecutionReport generation from TrackedOrder."""

    def test_create_execution_report_filled(self, config):
        """Test creating ExecutionReport for filled order."""
        client = IBKRExecClient(config)

        intent_time = datetime.utcnow()
        submitted_time = datetime.utcnow()
        ack_time = datetime.utcnow()
        filled_time = datetime.utcnow()

        tracked_order = TrackedOrder(
            intent_id=str(uuid4()),
            order_id='12345',
            symbol='AAPL',
            direction='BUY',
            quantity=100,
            order_type='MARKET',
            intent_timestamp=intent_time,
            submitted_timestamp=submitted_time,
            acknowledged_timestamp=ack_time,
            filled_timestamp=filled_time,
            status='FILLED',
            filled_quantity=100,
            average_fill_price=150.25,
            commission=1.50,
        )

        report = client._create_execution_report(tracked_order, datetime.utcnow())

        assert report.event_type == 'execution_report'
        assert report.intent_id == tracked_order.intent_id
        assert report.order_id == '12345'
        assert report.symbol == 'AAPL'
        assert report.status == 'FILLED'
        assert report.direction == 'BUY'
        assert report.requested_quantity == 100
        assert report.filled_quantity == 100
        assert report.remaining_quantity == 0
        assert report.average_fill_price == 150.25
        assert report.commission == 1.50

        # Check latency metrics
        assert report.latency_metrics is not None
        assert report.latency_metrics.intent_to_submit_ms is not None
        assert report.latency_metrics.submit_to_ack_ms is not None
        assert report.latency_metrics.ack_to_fill_ms is not None
        assert report.latency_metrics.total_latency_ms is not None

    def test_create_execution_report_partial_fill(self, config):
        """Test creating ExecutionReport for partial fill."""
        client = IBKRExecClient(config)

        tracked_order = TrackedOrder(
            intent_id=str(uuid4()),
            order_id='12346',
            symbol='TSLA',
            direction='SELL',
            quantity=100,
            order_type='LIMIT',
            intent_timestamp=datetime.utcnow(),
            submitted_timestamp=datetime.utcnow(),
            acknowledged_timestamp=datetime.utcnow(),
            status='ACKNOWLEDGED',
            filled_quantity=50,  # Partial fill
            average_fill_price=245.00,
            commission=0.75,
            limit_price=245.50,
        )

        report = client._create_execution_report(tracked_order, datetime.utcnow())

        assert report.status == 'PARTIAL_FILL'  # Should detect partial fill
        assert report.filled_quantity == 50
        assert report.remaining_quantity == 50
        assert report.limit_price == 245.50

    def test_create_execution_report_rejected(self, config):
        """Test creating ExecutionReport for rejected order."""
        client = IBKRExecClient(config)

        tracked_order = TrackedOrder(
            intent_id=str(uuid4()),
            order_id='12347',
            symbol='SPY',
            direction='BUY',
            quantity=1000,
            order_type='MARKET',
            intent_timestamp=datetime.utcnow(),
            submitted_timestamp=datetime.utcnow(),
            status='REJECTED',
            reject_reason='Insufficient buying power',
        )

        report = client._create_execution_report(tracked_order, datetime.utcnow())

        assert report.status == 'REJECTED'
        assert report.reject_reason == 'Insufficient buying power'
        assert report.filled_quantity == 0


@pytest.mark.asyncio
class TestIBKRExecClientAsyncOperations:
    """Test async operations of IBKRExecClient."""

    async def test_place_order_not_connected(self, config, market_order_intent):
        """Test placing order when not connected raises error."""
        client = IBKRExecClient(config)

        with pytest.raises(ConnectionError, match="Not connected to IBKR"):
            await client.place(market_order_intent)

    async def test_cancel_order_not_connected(self, config):
        """Test canceling order when not connected raises error."""
        client = IBKRExecClient(config)

        with pytest.raises(ConnectionError, match="Not connected to IBKR"):
            await client.cancel('12345')

    @patch('order_plane.broker.ibkr_exec_client.IB')
    async def test_connect_success(self, mock_ib_class, config):
        """Test successful connection to IBKR."""
        # Mock IB instance
        mock_ib = AsyncMock()
        mock_ib.connectAsync = AsyncMock()
        mock_ib.isConnected = Mock(return_value=True)
        mock_ib_class.return_value = mock_ib

        client = IBKRExecClient(config)
        client.ib = mock_ib

        await client.connect()

        assert client._connected is True
        mock_ib.connectAsync.assert_called_once_with(
            host='127.0.0.1',
            port=7497,
            clientId=1,
            timeout=10
        )

    @patch('order_plane.broker.ibkr_exec_client.IB')
    async def test_connect_failure(self, mock_ib_class, config):
        """Test connection failure to IBKR."""
        mock_ib = AsyncMock()
        mock_ib.connectAsync = AsyncMock(side_effect=Exception("Connection refused"))
        mock_ib_class.return_value = mock_ib

        client = IBKRExecClient(config)
        client.ib = mock_ib

        with pytest.raises(ConnectionError, match="IBKR connection failed"):
            await client.connect()

        assert client._connected is False

    @patch('order_plane.broker.ibkr_exec_client.IB')
    async def test_disconnect(self, mock_ib_class, config):
        """Test disconnecting from IBKR."""
        mock_ib = Mock()
        mock_ib.disconnect = Mock()
        mock_ib_class.return_value = mock_ib

        client = IBKRExecClient(config)
        client.ib = mock_ib
        client._connected = True

        await client.disconnect()

        assert client._connected is False
        mock_ib.disconnect.assert_called_once()

    async def test_poll_reports_not_connected(self, config):
        """Test polling reports when not connected returns empty list."""
        client = IBKRExecClient(config)

        reports = await client.poll_reports()

        assert reports == []


class TestIBKRExecClientOrderTracking:
    """Test order tracking functionality."""

    def test_get_tracked_order(self, config):
        """Test retrieving tracked order by order_id."""
        client = IBKRExecClient(config)

        # Add a tracked order
        tracked_order = TrackedOrder(
            intent_id='intent-123',
            order_id='order-456',
            symbol='AAPL',
            direction='BUY',
            quantity=100,
            order_type='MARKET',
            intent_timestamp=datetime.utcnow(),
        )

        client._tracked_orders['order-456'] = tracked_order

        # Retrieve
        result = client.get_tracked_order('order-456')
        assert result is not None
        assert result.order_id == 'order-456'
        assert result.symbol == 'AAPL'

    def test_get_tracked_order_not_found(self, config):
        """Test retrieving non-existent order returns None."""
        client = IBKRExecClient(config)

        result = client.get_tracked_order('non-existent')
        assert result is None

    def test_get_order_by_intent(self, config):
        """Test retrieving order by intent_id."""
        client = IBKRExecClient(config)

        # Add a tracked order
        tracked_order = TrackedOrder(
            intent_id='intent-789',
            order_id='order-101',
            symbol='TSLA',
            direction='SELL',
            quantity=50,
            order_type='LIMIT',
            intent_timestamp=datetime.utcnow(),
        )

        client._tracked_orders['order-101'] = tracked_order
        client._intent_to_order['intent-789'] = 'order-101'

        # Retrieve by intent
        result = client.get_order_by_intent('intent-789')
        assert result is not None
        assert result.intent_id == 'intent-789'
        assert result.order_id == 'order-101'

    def test_get_order_by_intent_not_found(self, config):
        """Test retrieving by non-existent intent_id returns None."""
        client = IBKRExecClient(config)

        result = client.get_order_by_intent('non-existent')
        assert result is None


class TestIBKRExecClientIntegration:
    """Integration tests for complete order flow."""

    def test_order_lifecycle_tracking(self, config, market_order_intent):
        """Test tracking order through its lifecycle."""
        client = IBKRExecClient(config)

        # Simulate order submission
        order_id = '12345'
        tracked_order = TrackedOrder(
            intent_id=market_order_intent.intent_id,
            order_id=order_id,
            symbol=market_order_intent.symbol,
            direction=market_order_intent.direction,
            quantity=market_order_intent.quantity,
            order_type=market_order_intent.order_type,
            intent_timestamp=market_order_intent.timestamp,
            submitted_timestamp=datetime.utcnow(),
            status='SUBMITTED',
        )

        client._tracked_orders[order_id] = tracked_order
        client._intent_to_order[market_order_intent.intent_id] = order_id

        # Verify tracking
        assert client.get_tracked_order(order_id) is not None
        assert client.get_order_by_intent(market_order_intent.intent_id) is not None

        # Update status to acknowledged
        tracked_order.status = 'ACKNOWLEDGED'
        tracked_order.acknowledged_timestamp = datetime.utcnow()

        # Update status to filled
        tracked_order.status = 'FILLED'
        tracked_order.filled_timestamp = datetime.utcnow()
        tracked_order.filled_quantity = 100
        tracked_order.average_fill_price = 150.00
        tracked_order.commission = 1.00

        # Generate execution report
        report = client._create_execution_report(tracked_order, datetime.utcnow())

        assert report.status == 'FILLED'
        assert report.filled_quantity == 100
        assert report.average_fill_price == 150.00
        assert report.commission == 1.00


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
