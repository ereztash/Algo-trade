"""
IBKR Execution Client for Order Plane

Handles order placement, cancellation, and execution monitoring.
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime

from algo_trade.core.execution.IBKR_handler import IBKRHandler

logger = logging.getLogger(__name__)


class IBKRExecClient:
    """
    IBKR execution client for the Order Plane.

    Responsibilities:
    - Place orders based on intents from Strategy Plane
    - Monitor order execution status
    - Report fills and execution details
    - Handle order cancellations
    """

    def __init__(self, cfg: Dict):
        """
        Initialize IBKR execution client.

        Args:
            cfg (dict): Configuration dictionary with:
                - host: IBKR host (default: '127.0.0.1')
                - port: IBKR port (default: 7497 for paper)
                - client_id: Client ID (default: 2 for exec client)
                - account: Account number (optional)
                - readonly: Read-only mode (default: False)
        """
        self.cfg = cfg
        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 7497)
        self.client_id = cfg.get('client_id', 2)
        self.account = cfg.get('account', None)
        self.readonly = cfg.get('readonly', False)

        self.handler = None
        self._active_orders = {}
        self._execution_reports = []

        logger.info(f"IBKR Exec Client initialized (port={self.port}, id={self.client_id})")

    async def connect(self) -> bool:
        """
        Establish connection to IBKR.

        Returns:
            bool: True if connected successfully
        """
        try:
            self.handler = IBKRHandler(
                host=self.host,
                port=self.port,
                client_id=self.client_id,
                account=self.account,
                readonly=self.readonly,
                auto_reconnect=True
            )

            success = self.handler.connect()

            if success:
                logger.info("✅ Order Plane connected to IBKR")
            else:
                logger.error("❌ Order Plane failed to connect to IBKR")

            return success

        except Exception as e:
            logger.error(f"Error connecting to IBKR: {e}")
            return False

    async def disconnect(self):
        """Disconnect from IBKR."""
        if self.handler:
            self.handler.disconnect()
            logger.info("Order Plane disconnected from IBKR")

    async def place(self, intent: Dict) -> Optional[Dict]:
        """
        Place an order based on intent.

        Args:
            intent (dict): Order intent with:
                - symbol: Stock symbol
                - quantity: Order quantity
                - action: "BUY" or "SELL"
                - order_type: "MARKET" or "LIMIT"
                - limit_price: Limit price (for LIMIT orders)
                - time_in_force: Order time in force (optional)

        Returns:
            dict: Execution report with order details, or None if failed
        """
        if not self.handler or not self.handler.is_connected():
            logger.error("Not connected to IBKR")
            return None

        try:
            symbol = intent['symbol']
            quantity = intent['quantity']
            action = intent['action']
            order_type = intent.get('order_type', 'MARKET')
            limit_price = intent.get('limit_price', None)

            # Place order via handler
            trade = self.handler.place_order(
                symbol=symbol,
                quantity=quantity,
                action=action,
                order_type=order_type,
                limit_price=limit_price
            )

            if not trade:
                logger.error(f"Failed to place order for {symbol}")
                return None

            # Track active order
            order_id = trade.order.orderId
            self._active_orders[order_id] = {
                'intent': intent,
                'trade': trade,
                'timestamp': datetime.now()
            }

            # Create execution report
            exec_report = {
                'order_id': order_id,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'order_type': order_type,
                'status': 'submitted',
                'filled': 0,
                'remaining': quantity,
                'avg_fill_price': 0.0,
                'timestamp': datetime.now()
            }

            self._execution_reports.append(exec_report)

            logger.info(f"Order placed: {action} {symbol} x{quantity} (ID: {order_id})")

            return exec_report

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    async def cancel(self, order_id: int) -> bool:
        """
        Cancel an order.

        Args:
            order_id (int): Order ID to cancel

        Returns:
            bool: True if cancellation successful
        """
        if not self.handler or not self.handler.is_connected():
            logger.error("Not connected to IBKR")
            return False

        try:
            success = self.handler.cancel_order(order_id)

            if success:
                # Remove from active orders
                if order_id in self._active_orders:
                    del self._active_orders[order_id]

                logger.info(f"Order {order_id} cancelled")

            return success

        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    async def poll_reports(self) -> List[Dict]:
        """
        Poll for execution reports.

        Returns:
            list: List of new execution reports since last poll
        """
        if not self.handler or not self.handler.is_connected():
            return []

        try:
            # Get current orders from IBKR
            current_orders = self.handler.get_orders(refresh=True)

            new_reports = []

            for order in current_orders:
                order_id = order['order_id']

                # Check if this is a new update
                if order_id in self._active_orders:
                    # Create execution report
                    exec_report = {
                        'order_id': order_id,
                        'symbol': order['symbol'],
                        'action': order['action'],
                        'quantity': order['quantity'],
                        'order_type': order['order_type'],
                        'status': order['status'],
                        'filled': order['filled'],
                        'remaining': order['remaining'],
                        'avg_fill_price': order['avg_fill_price'],
                        'timestamp': datetime.now()
                    }

                    new_reports.append(exec_report)

                    # If fully filled or cancelled, remove from active
                    if order['status'] in ['Filled', 'Cancelled', 'ApiCancelled']:
                        if order_id in self._active_orders:
                            del self._active_orders[order_id]

            return new_reports

        except Exception as e:
            logger.error(f"Error polling execution reports: {e}")
            return []

    def health(self) -> Dict:
        """
        Get health status.

        Returns:
            dict: Health status information
        """
        if not self.handler:
            return {
                "connected": False,
                "session": "exec",
                "active_orders": 0
            }

        handler_health = self.handler.health_check()

        return {
            "connected": handler_health['connected'],
            "session": "exec",
            "state": handler_health['state'],
            "active_orders": len(self._active_orders),
            "total_reports": len(self._execution_reports),
            "account": handler_health.get('account', None)
        }

    async def get_account_info(self) -> Dict:
        """Get account information."""
        if not self.handler or not self.handler.is_connected():
            return {}

        return self.handler.get_account_summary()

    async def get_positions(self) -> List[Dict]:
        """Get current positions."""
        if not self.handler or not self.handler.is_connected():
            return []

        return self.handler.get_positions()

    def __repr__(self):
        return f"IBKRExecClient(port={self.port}, client_id={self.client_id}, connected={self.health()['connected']})"
