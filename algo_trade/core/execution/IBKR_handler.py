"""
IBKR Handler - Advanced Integration with Interactive Brokers

This module provides a comprehensive interface to Interactive Brokers TWS/Gateway,
including:
- Connection management with automatic reconnection
- Account summary and positions retrieval
- Order management (place, cancel, query)
- Error handling with exponential backoff
- Health checks and monitoring

Author: Algo-trade Team
Updated: 2025-11-17
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from ib_insync import IB, util, Stock, Contract, MarketOrder, LimitOrder, Order
from ib_insync.objects import Position, AccountValue, Trade

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class IBKRConfig:
    """Configuration for IBKR connection."""
    host: str = '127.0.0.1'
    port: int = 7497  # Paper: 7497, Live: 7496
    client_id: int = 1
    timeout: int = 30
    reconnect_attempts: int = 5
    reconnect_backoff: List[int] = None

    def __post_init__(self):
        if self.reconnect_backoff is None:
            self.reconnect_backoff = [1, 2, 4, 8, 16]


class IBKRConnectionError(Exception):
    """Raised when IBKR connection fails."""
    pass


class IBKRHandler:
    """
    Advanced IBKR Handler with full account management and error handling.

    Features:
    - Automatic reconnection with exponential backoff
    - Account summary (NAV, cash, buying power)
    - Position tracking
    - Order management
    - Health checks
    """

    def __init__(self, config: Optional[IBKRConfig] = None):
        """
        Initialize IBKR Handler.

        Args:
            config: IBKRConfig instance. If None, uses defaults.
        """
        self.config = config or IBKRConfig()
        self.ib = IB()
        self._connected = False
        self._connection_time = None
        self._reconnect_count = 0

        # Set up event handlers
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        self.ib.errorEvent += self._on_error

        logger.info(f"IBKR Handler initialized (host={self.config.host}, port={self.config.port})")

    def _on_connected(self):
        """Callback when connection is established."""
        self._connected = True
        self._connection_time = datetime.now()
        self._reconnect_count = 0
        logger.info("✅ Connected to IBKR")

    def _on_disconnected(self):
        """Callback when connection is lost."""
        self._connected = False
        logger.warning("⚠️ Disconnected from IBKR")

    def _on_error(self, reqId, errorCode, errorString, contract):
        """Callback for IBKR errors."""
        logger.error(f"IBKR Error [{errorCode}] reqId={reqId}: {errorString}")

    def connect(self) -> bool:
        """
        Establishes connection to TWS or IB Gateway.

        Returns:
            bool: True if connected successfully, False otherwise.

        Raises:
            IBKRConnectionError: If connection fails after all retry attempts.
        """
        if self.ib.isConnected():
            logger.info("Already connected to IBKR")
            return True

        for attempt in range(self.config.reconnect_attempts):
            try:
                logger.info(f"Connecting to IBKR (attempt {attempt + 1}/{self.config.reconnect_attempts})...")
                self.ib.connect(
                    self.config.host,
                    self.config.port,
                    clientId=self.config.client_id,
                    timeout=self.config.timeout
                )

                if self.ib.isConnected():
                    logger.info("✅ Successfully connected to IBKR")
                    return True

            except Exception as e:
                logger.error(f"❌ Connection attempt {attempt + 1} failed: {e}")

                if attempt < self.config.reconnect_attempts - 1:
                    backoff = self.config.reconnect_backoff[min(attempt, len(self.config.reconnect_backoff) - 1)]
                    logger.info(f"Retrying in {backoff} seconds...")
                    time.sleep(backoff)
                    self._reconnect_count += 1

        raise IBKRConnectionError(
            f"Failed to connect to IBKR after {self.config.reconnect_attempts} attempts"
        )

    def disconnect(self):
        """Disconnects from TWS or IB Gateway."""
        if self.ib.isConnected():
            self.ib.disconnect()
            logger.info("Disconnected from IBKR")

    def is_connected(self) -> bool:
        """Check if connected to IBKR."""
        return self.ib.isConnected()

    def get_account_summary(self) -> Dict[str, Any]:
        """
        Get account summary including NAV, cash, and buying power.

        Returns:
            Dict with account information:
            - nav: Net Asset Value
            - cash: Available cash
            - buying_power: Buying power (for margin accounts)
            - equity_with_loan: Equity with loan value

        Raises:
            IBKRConnectionError: If not connected.
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IBKR")

        try:
            # Request account summary
            account_values = self.ib.accountValues()

            summary = {}
            for av in account_values:
                if av.tag == 'NetLiquidation':
                    summary['nav'] = float(av.value)
                elif av.tag == 'TotalCashValue':
                    summary['cash'] = float(av.value)
                elif av.tag == 'BuyingPower':
                    summary['buying_power'] = float(av.value)
                elif av.tag == 'EquityWithLoanValue':
                    summary['equity_with_loan'] = float(av.value)

            logger.info(f"Account Summary: NAV={summary.get('nav', 0):.2f}")
            return summary

        except Exception as e:
            logger.error(f"Failed to get account summary: {e}")
            raise

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions.

        Returns:
            List of position dictionaries with:
            - symbol: Ticker symbol
            - position: Number of shares (negative for short)
            - avg_cost: Average cost per share
            - market_value: Current market value
            - unrealized_pnl: Unrealized P&L

        Raises:
            IBKRConnectionError: If not connected.
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IBKR")

        try:
            positions = self.ib.positions()

            result = []
            for pos in positions:
                result.append({
                    'symbol': pos.contract.symbol,
                    'position': pos.position,
                    'avg_cost': pos.avgCost,
                    'market_value': pos.marketValue,
                    'unrealized_pnl': pos.unrealizedPNL,
                    'contract': pos.contract
                })

            logger.info(f"Retrieved {len(result)} positions")
            return result

        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    def get_orders(self) -> List[Dict[str, Any]]:
        """
        Get all open orders.

        Returns:
            List of order dictionaries with:
            - order_id: Order ID
            - symbol: Ticker symbol
            - action: BUY or SELL
            - quantity: Number of shares
            - order_type: Market, Limit, etc.
            - status: Order status
            - filled: Filled quantity

        Raises:
            IBKRConnectionError: If not connected.
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IBKR")

        try:
            trades = self.ib.openTrades()

            result = []
            for trade in trades:
                result.append({
                    'order_id': trade.order.orderId,
                    'symbol': trade.contract.symbol,
                    'action': trade.order.action,
                    'quantity': trade.order.totalQuantity,
                    'order_type': trade.order.orderType,
                    'status': trade.orderStatus.status,
                    'filled': trade.orderStatus.filled,
                    'remaining': trade.orderStatus.remaining,
                })

            logger.info(f"Retrieved {len(result)} open orders")
            return result

        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            raise

    def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str = 'MKT',
        limit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Place an order.

        Args:
            symbol: Stock symbol
            action: 'BUY' or 'SELL'
            quantity: Number of shares
            order_type: 'MKT' (market) or 'LMT' (limit)
            limit_price: Limit price (required if order_type='LMT')

        Returns:
            Dict with order information:
            - order_id: Order ID
            - status: Order status

        Raises:
            IBKRConnectionError: If not connected.
            ValueError: If invalid parameters.
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IBKR")

        if action not in ['BUY', 'SELL']:
            raise ValueError(f"Invalid action: {action}. Must be 'BUY' or 'SELL'")

        if order_type == 'LMT' and limit_price is None:
            raise ValueError("limit_price required for limit orders")

        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')

            # Create order
            if order_type == 'MKT':
                order = MarketOrder(action, quantity)
            elif order_type == 'LMT':
                order = LimitOrder(action, quantity, limit_price)
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            # Place order
            trade = self.ib.placeOrder(contract, order)

            # Wait for order to be acknowledged
            self.ib.sleep(1)

            logger.info(
                f"Order placed: {action} {quantity} {symbol} @ "
                f"{order_type} {f'${limit_price}' if limit_price else ''}"
            )

            return {
                'order_id': trade.order.orderId,
                'status': trade.orderStatus.status,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
            }

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if cancellation was successful

        Raises:
            IBKRConnectionError: If not connected.
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IBKR")

        try:
            # Find the trade with this order ID
            for trade in self.ib.openTrades():
                if trade.order.orderId == order_id:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"Cancelled order {order_id}")
                    return True

            logger.warning(f"Order {order_id} not found")
            return False

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    def is_healthy(self) -> Dict[str, Any]:
        """
        Check health status of IBKR connection.

        Returns:
            Dict with health information:
            - connected: Connection status
            - connection_time: Time when connected
            - reconnect_count: Number of reconnection attempts
            - latency_ms: Connection latency (if available)
        """
        health = {
            'connected': self.is_connected(),
            'connection_time': self._connection_time.isoformat() if self._connection_time else None,
            'reconnect_count': self._reconnect_count,
            'host': self.config.host,
            'port': self.config.port,
        }

        # Try to measure latency with a simple request
        if self.is_connected():
            try:
                start = time.time()
                _ = self.ib.reqCurrentTime()
                latency = (time.time() - start) * 1000
                health['latency_ms'] = round(latency, 2)
            except:
                health['latency_ms'] = None

        return health


# דוגמת שימוש (Example usage)
if __name__ == '__main__':
    # Initialize with default config (Paper Trading)
    config = IBKRConfig(
        host='127.0.0.1',
        port=7497,  # Paper trading port
        client_id=1
    )

    handler = IBKRHandler(config)

    try:
        # Connect
        handler.connect()

        # Get account summary
        summary = handler.get_account_summary()
        print(f"\nAccount Summary:")
        print(f"  NAV: ${summary.get('nav', 0):,.2f}")
        print(f"  Cash: ${summary.get('cash', 0):,.2f}")
        print(f"  Buying Power: ${summary.get('buying_power', 0):,.2f}")

        # Get positions
        positions = handler.get_positions()
        print(f"\nPositions ({len(positions)}):")
        for pos in positions:
            print(f"  {pos['symbol']}: {pos['position']} shares @ ${pos['avg_cost']:.2f}")

        # Get orders
        orders = handler.get_orders()
        print(f"\nOpen Orders ({len(orders)}):")
        for order in orders:
            print(f"  {order['action']} {order['quantity']} {order['symbol']} - {order['status']}")

        # Health check
        health = handler.is_healthy()
        print(f"\nHealth Status:")
        print(f"  Connected: {health['connected']}")
        print(f"  Latency: {health.get('latency_ms')} ms")

    except Exception as e:
        logger.error(f"Error: {e}")

    finally:
        # Disconnect
        handler.disconnect()
