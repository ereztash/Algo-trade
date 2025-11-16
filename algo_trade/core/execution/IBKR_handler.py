"""
Comprehensive Interactive Brokers (IBKR) Handler

This module provides a robust interface to Interactive Brokers TWS/Gateway for:
- Account information retrieval
- Position management
- Order placement and monitoring
- Market data subscriptions
- Automatic reconnection and error handling

Supports both paper trading and live trading environments.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Union, Callable
from datetime import datetime
from enum import Enum

try:
    from ib_insync import IB, Stock, Contract, Order, MarketOrder, LimitOrder, util
    from ib_insync.objects import Position, AccountValue, PortfolioItem, Trade
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    # Fallback for when ib_insync is not installed
    class IB:
        pass
    class Stock:
        pass
    class Contract:
        pass
    class Order:
        pass


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """IBKR connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class IBKRHandler:
    """
    Comprehensive IBKR connection handler with robust error handling and reconnection.

    Features:
    - Automatic reconnection with exponential backoff
    - Account information retrieval
    - Position and portfolio management
    - Order placement and tracking
    - Market data subscriptions
    - Event-driven callbacks
    - Health monitoring

    Args:
        host (str): TWS/Gateway host address (default: '127.0.0.1')
        port (int): TWS/Gateway port (default: 7497 for paper, 7496 for live)
        client_id (int): Unique client ID (default: 1)
        account (str): Account number (optional, auto-detected if not provided)
        readonly (bool): Read-only mode (no order placement)
        auto_reconnect (bool): Enable automatic reconnection
        max_reconnect_attempts (int): Maximum reconnection attempts
    """

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 7497,
        client_id: int = 1,
        account: Optional[str] = None,
        readonly: bool = False,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 5
    ):
        if not IB_INSYNC_AVAILABLE:
            raise ImportError(
                "ib_insync is not installed. Install with: pip install ib_insync"
            )

        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.account = account
        self.readonly = readonly
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts

        # State tracking
        self.state = ConnectionState.DISCONNECTED
        self.reconnect_attempts = 0
        self.last_error = None

        # Caches
        self._account_summary_cache = {}
        self._positions_cache = []
        self._portfolio_cache = []
        self._orders_cache = {}

        # Event callbacks
        self._on_connected_callbacks = []
        self._on_disconnected_callbacks = []
        self._on_error_callbacks = []
        self._on_order_status_callbacks = []

        # Setup event handlers
        self._setup_event_handlers()

        logger.info(
            f"IBKR Handler initialized (host={host}, port={port}, "
            f"client_id={client_id}, readonly={readonly})"
        )

    def _setup_event_handlers(self):
        """Setup IB event handlers."""
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected
        self.ib.errorEvent += self._on_error

    def _on_connected(self):
        """Handle connection event."""
        self.state = ConnectionState.CONNECTED
        self.reconnect_attempts = 0
        logger.info("✅ Successfully connected to IBKR")

        # Auto-detect account if not specified
        if not self.account:
            accounts = self.ib.managedAccounts()
            if accounts:
                self.account = accounts[0]
                logger.info(f"Auto-detected account: {self.account}")

        # Execute callbacks
        for callback in self._on_connected_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in connected callback: {e}")

    def _on_disconnected(self):
        """Handle disconnection event."""
        if self.state != ConnectionState.DISCONNECTED:
            logger.warning("Disconnected from IBKR")
            self.state = ConnectionState.DISCONNECTED

            # Execute callbacks
            for callback in self._on_disconnected_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Error in disconnected callback: {e}")

            # Attempt reconnection
            if self.auto_reconnect:
                self._attempt_reconnect()

    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle error event."""
        self.last_error = {
            "reqId": reqId,
            "code": errorCode,
            "message": errorString,
            "contract": contract,
            "timestamp": datetime.now()
        }

        # Log error with appropriate level
        if errorCode in [2104, 2106, 2158]:  # Info messages
            logger.info(f"IBKR Info [{errorCode}]: {errorString}")
        elif errorCode in [200, 201, 202, 203]:  # Warning messages
            logger.warning(f"IBKR Warning [{errorCode}]: {errorString}")
        else:
            logger.error(f"IBKR Error [{errorCode}]: {errorString} (reqId={reqId})")

        # Execute callbacks
        for callback in self._on_error_callbacks:
            try:
                callback(reqId, errorCode, errorString, contract)
            except Exception as e:
                logger.error(f"Error in error callback: {e}")

    def connect(self, timeout: int = 10) -> bool:
        """
        Establish connection to TWS or IB Gateway.

        Args:
            timeout (int): Connection timeout in seconds

        Returns:
            bool: True if connected successfully
        """
        if self.is_connected():
            logger.info("Already connected to IBKR")
            return True

        self.state = ConnectionState.CONNECTING

        try:
            self.ib.connect(
                self.host,
                self.port,
                self.client_id,
                timeout=timeout,
                readonly=self.readonly
            )
            return True
        except Exception as e:
            self.state = ConnectionState.FAILED
            logger.error(f"❌ Connection failed: {e}")
            self.last_error = {"message": str(e), "timestamp": datetime.now()}
            return False

    def disconnect(self):
        """Disconnect from TWS or IB Gateway."""
        if self.is_connected():
            self.ib.disconnect()
            self.state = ConnectionState.DISCONNECTED
            logger.info("Disconnected from IBKR")

    def is_connected(self) -> bool:
        """Check if currently connected."""
        return self.ib.isConnected()

    def _attempt_reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"Max reconnection attempts ({self.max_reconnect_attempts}) reached. "
                "Giving up."
            )
            self.state = ConnectionState.FAILED
            return

        self.reconnect_attempts += 1
        self.state = ConnectionState.RECONNECTING

        # Exponential backoff: 2^n seconds (2, 4, 8, 16, 32)
        wait_time = 2 ** self.reconnect_attempts

        logger.info(
            f"Attempting reconnection {self.reconnect_attempts}/"
            f"{self.max_reconnect_attempts} in {wait_time}s..."
        )

        # Schedule reconnection
        asyncio.get_event_loop().call_later(wait_time, self.connect)

    # ========================================================================
    # Account Information
    # ========================================================================

    def get_account_summary(self, refresh: bool = False) -> Dict:
        """
        Get comprehensive account summary.

        Args:
            refresh (bool): Force refresh from server (ignore cache)

        Returns:
            dict: Account summary with keys:
                - net_liquidation: Total account value
                - cash: Available cash
                - buying_power: Buying power
                - gross_position_value: Gross value of positions
                - pnl: Unrealized P&L
                - realized_pnl: Realized P&L
                - maintenance_margin: Maintenance margin requirement
                - full_account_values: Complete AccountValue list
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return {}

        if not refresh and self._account_summary_cache:
            return self._account_summary_cache

        try:
            # Request account summary
            account_values = self.ib.accountValues(self.account)

            # Parse key metrics
            summary = {
                "account": self.account,
                "timestamp": datetime.now(),
                "net_liquidation": 0.0,
                "cash": 0.0,
                "buying_power": 0.0,
                "gross_position_value": 0.0,
                "pnl": 0.0,
                "realized_pnl": 0.0,
                "maintenance_margin": 0.0,
                "full_account_values": account_values
            }

            # Extract key values
            for av in account_values:
                if av.tag == "NetLiquidation":
                    summary["net_liquidation"] = float(av.value)
                elif av.tag == "TotalCashValue":
                    summary["cash"] = float(av.value)
                elif av.tag == "BuyingPower":
                    summary["buying_power"] = float(av.value)
                elif av.tag == "GrossPositionValue":
                    summary["gross_position_value"] = float(av.value)
                elif av.tag == "UnrealizedPnL":
                    summary["pnl"] = float(av.value)
                elif av.tag == "RealizedPnL":
                    summary["realized_pnl"] = float(av.value)
                elif av.tag == "MaintMarginReq":
                    summary["maintenance_margin"] = float(av.value)

            self._account_summary_cache = summary
            logger.debug(f"Account summary: NAV=${summary['net_liquidation']:,.2f}")

            return summary

        except Exception as e:
            logger.error(f"Error getting account summary: {e}")
            return {}

    def get_positions(self, refresh: bool = False) -> List[Dict]:
        """
        Get all current positions.

        Args:
            refresh (bool): Force refresh from server

        Returns:
            list: List of position dictionaries with keys:
                - symbol: Stock symbol
                - position: Position size (positive=long, negative=short)
                - avg_cost: Average cost basis
                - market_value: Current market value
                - pnl: Unrealized P&L
                - contract: Full IB contract object
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return []

        if not refresh and self._positions_cache:
            return self._positions_cache

        try:
            positions = self.ib.positions(self.account)

            positions_list = []
            for pos in positions:
                positions_list.append({
                    "symbol": pos.contract.symbol,
                    "position": pos.position,
                    "avg_cost": pos.avgCost,
                    "market_value": pos.marketValue,
                    "pnl": pos.unrealizedPNL,
                    "account": pos.account,
                    "contract": pos.contract
                })

            self._positions_cache = positions_list
            logger.debug(f"Retrieved {len(positions_list)} positions")

            return positions_list

        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []

    def get_orders(self, refresh: bool = False) -> List[Dict]:
        """
        Get all orders (open, filled, cancelled).

        Args:
            refresh (bool): Force refresh from server

        Returns:
            list: List of order dictionaries with keys:
                - order_id: Order ID
                - symbol: Stock symbol
                - action: BUY or SELL
                - quantity: Order quantity
                - order_type: Market, Limit, etc.
                - status: Order status
                - filled: Filled quantity
                - remaining: Remaining quantity
                - avg_fill_price: Average fill price
                - trade: Full IB Trade object
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return []

        if not refresh and self._orders_cache:
            return list(self._orders_cache.values())

        try:
            trades = self.ib.trades()

            orders_list = []
            self._orders_cache = {}

            for trade in trades:
                order_dict = {
                    "order_id": trade.order.orderId,
                    "symbol": trade.contract.symbol,
                    "action": trade.order.action,
                    "quantity": trade.order.totalQuantity,
                    "order_type": trade.order.orderType,
                    "status": trade.orderStatus.status,
                    "filled": trade.orderStatus.filled,
                    "remaining": trade.orderStatus.remaining,
                    "avg_fill_price": trade.orderStatus.avgFillPrice,
                    "last_update": trade.log[-1].time if trade.log else None,
                    "trade": trade
                }

                orders_list.append(order_dict)
                self._orders_cache[trade.order.orderId] = order_dict

            logger.debug(f"Retrieved {len(orders_list)} orders")

            return orders_list

        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []

    def get_portfolio(self, refresh: bool = False) -> List[Dict]:
        """
        Get portfolio items (similar to positions but with more detail).

        Args:
            refresh (bool): Force refresh from server

        Returns:
            list: List of portfolio item dictionaries
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return []

        if not refresh and self._portfolio_cache:
            return self._portfolio_cache

        try:
            portfolio = self.ib.portfolio(self.account)

            portfolio_list = []
            for item in portfolio:
                portfolio_list.append({
                    "symbol": item.contract.symbol,
                    "position": item.position,
                    "market_price": item.marketPrice,
                    "market_value": item.marketValue,
                    "avg_cost": item.averageCost,
                    "unrealized_pnl": item.unrealizedPNL,
                    "realized_pnl": item.realizedPNL,
                    "contract": item.contract
                })

            self._portfolio_cache = portfolio_list
            logger.debug(f"Retrieved portfolio with {len(portfolio_list)} items")

            return portfolio_list

        except Exception as e:
            logger.error(f"Error getting portfolio: {e}")
            return []

    # ========================================================================
    # Order Placement
    # ========================================================================

    def place_order(
        self,
        symbol: str,
        quantity: int,
        action: str = "BUY",
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        **kwargs
    ) -> Optional[Trade]:
        """
        Place an order.

        Args:
            symbol (str): Stock symbol
            quantity (int): Order quantity (positive)
            action (str): "BUY" or "SELL"
            order_type (str): "MARKET", "LIMIT", etc.
            limit_price (float): Limit price (required for LIMIT orders)
            **kwargs: Additional order parameters

        Returns:
            Trade: IB Trade object if successful, None otherwise
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return None

        if self.readonly:
            logger.warning("Cannot place order in read-only mode")
            return None

        try:
            # Create contract
            contract = Stock(symbol, 'SMART', 'USD')

            # Create order
            if order_type.upper() == "MARKET":
                order = MarketOrder(action, quantity)
            elif order_type.upper() == "LIMIT":
                if limit_price is None:
                    raise ValueError("limit_price required for LIMIT orders")
                order = LimitOrder(action, quantity, limit_price)
            else:
                raise ValueError(f"Unsupported order type: {order_type}")

            # Apply additional parameters
            for key, value in kwargs.items():
                setattr(order, key, value)

            # Place order
            trade = self.ib.placeOrder(contract, order)

            logger.info(
                f"Placed {action} order: {symbol} x{quantity} @ "
                f"{order_type} (OrderID: {trade.order.orderId})"
            )

            return trade

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an order.

        Args:
            order_id (int): Order ID to cancel

        Returns:
            bool: True if cancellation request sent successfully
        """
        if not self.is_connected():
            logger.error("Not connected to IBKR")
            return False

        try:
            # Find trade
            trades = [t for t in self.ib.trades() if t.order.orderId == order_id]

            if not trades:
                logger.warning(f"Order {order_id} not found")
                return False

            trade = trades[0]
            self.ib.cancelOrder(trade.order)

            logger.info(f"Cancelled order {order_id}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    # ========================================================================
    # Utilities and Callbacks
    # ========================================================================

    def on_connected(self, callback: Callable):
        """Register callback for connection events."""
        self._on_connected_callbacks.append(callback)

    def on_disconnected(self, callback: Callable):
        """Register callback for disconnection events."""
        self._on_disconnected_callbacks.append(callback)

    def on_error(self, callback: Callable):
        """Register callback for error events."""
        self._on_error_callbacks.append(callback)

    def health_check(self) -> Dict:
        """
        Get health status.

        Returns:
            dict: Health status information
        """
        return {
            "connected": self.is_connected(),
            "state": self.state.value,
            "host": self.host,
            "port": self.port,
            "account": self.account,
            "readonly": self.readonly,
            "reconnect_attempts": self.reconnect_attempts,
            "last_error": self.last_error
        }

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def __repr__(self):
        return (
            f"IBKRHandler(host={self.host}, port={self.port}, "
            f"client_id={self.client_id}, state={self.state.value})"
        )


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Create handler for paper trading (port 7497)
    with IBKRHandler(port=7497, readonly=True) as handler:
        # Get account summary
        summary = handler.get_account_summary()
        print(f"\nAccount Summary:")
        print(f"  Net Liquidation: ${summary.get('net_liquidation', 0):,.2f}")
        print(f"  Cash: ${summary.get('cash', 0):,.2f}")
        print(f"  Buying Power: ${summary.get('buying_power', 0):,.2f}")

        # Get positions
        positions = handler.get_positions()
        print(f"\nPositions ({len(positions)}):")
        for pos in positions:
            print(f"  {pos['symbol']}: {pos['position']} @ ${pos['avg_cost']:.2f}")

        # Get orders
        orders = handler.get_orders()
        print(f"\nOrders ({len(orders)}):")
        for order in orders:
            print(f"  #{order['order_id']}: {order['action']} {order['symbol']} "
                  f"x{order['quantity']} ({order['status']})")
