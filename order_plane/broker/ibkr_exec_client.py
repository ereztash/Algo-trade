"""
IBKR Execution Client for Order Plane

This module provides async interface for order execution through IBKR.
It bridges the order_plane with the core IBKR_handler.

Author: Algo-trade Team
Updated: 2025-11-17
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from algo_trade.core.execution.IBKR_handler import IBKRHandler, IBKRConfig, IBKRConnectionError

logger = logging.getLogger(__name__)


class IBKRExecClient:
    """
    Async execution client for IBKR orders.

    This client wraps IBKRHandler to provide async interface for the order_plane.
    It handles order placement, cancellation, and execution report polling.
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        Initialize IBKR Execution Client.

        Args:
            cfg: Configuration dictionary with keys:
                - host: IBKR host (default: 127.0.0.1)
                - port: IBKR port (default: 7497 for paper)
                - client_id: Client ID (default: 1)
                - timeout: Connection timeout (default: 30)
        """
        self.cfg = cfg

        # Create IBKRConfig from cfg dict
        ibkr_config = IBKRConfig(
            host=cfg.get('host', '127.0.0.1'),
            port=cfg.get('port', 7497),
            client_id=cfg.get('client_id', 1),
            timeout=cfg.get('timeout', 30),
            reconnect_attempts=cfg.get('reconnect_attempts', 5)
        )

        self.handler = IBKRHandler(ibkr_config)
        self._execution_reports = []
        logger.info("IBKRExecClient initialized")

    async def connect(self) -> bool:
        """
        Establish connection to IBKR.

        Returns:
            bool: True if connected successfully

        Raises:
            IBKRConnectionError: If connection fails
        """
        try:
            # Run sync connect in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.handler.connect)
            logger.info("IBKRExecClient connected")
            return result
        except Exception as e:
            logger.error(f"Failed to connect IBKRExecClient: {e}")
            raise

    async def place(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place an order from OrderIntent.

        Args:
            intent: OrderIntent dictionary with keys:
                - symbol: Stock symbol
                - action: 'BUY' or 'SELL'
                - quantity: Number of shares
                - order_type: 'MKT' or 'LMT'
                - limit_price: (optional) Limit price for LMT orders

        Returns:
            Dict with execution report:
            - order_id: IBKR order ID
            - status: Order status
            - timestamp: Execution timestamp

        Raises:
            ValueError: If intent is invalid
            IBKRConnectionError: If not connected
        """
        try:
            # Validate intent
            required_fields = ['symbol', 'action', 'quantity', 'order_type']
            for field in required_fields:
                if field not in intent:
                    raise ValueError(f"Missing required field: {field}")

            # Run place_order in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.handler.place_order,
                intent['symbol'],
                intent['action'],
                intent['quantity'],
                intent.get('order_type', 'MKT'),
                intent.get('limit_price')
            )

            # Create execution report
            exec_report = {
                **result,
                'timestamp': datetime.utcnow().isoformat(),
                'intent_id': intent.get('intent_id'),
            }

            # Store for polling
            self._execution_reports.append(exec_report)

            logger.info(f"Order placed: {result['order_id']}")
            return exec_report

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            raise

    async def cancel(self, order_id: int) -> Dict[str, Any]:
        """
        Cancel an order.

        Args:
            order_id: IBKR order ID to cancel

        Returns:
            Dict with cancellation result:
            - order_id: Order ID
            - cancelled: True if successful
            - timestamp: Cancellation timestamp

        Raises:
            IBKRConnectionError: If not connected
        """
        try:
            # Run cancel_order in executor
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                self.handler.cancel_order,
                order_id
            )

            result = {
                'order_id': order_id,
                'cancelled': success,
                'timestamp': datetime.utcnow().isoformat(),
            }

            logger.info(f"Order cancelled: {order_id}")
            return result

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    async def poll_reports(self) -> List[Dict[str, Any]]:
        """
        Poll for execution reports.

        This method retrieves all pending execution reports and clears the queue.

        Returns:
            List of execution reports

        Raises:
            IBKRConnectionError: If not connected
        """
        try:
            # Get current orders from IBKR
            loop = asyncio.get_event_loop()
            orders = await loop.run_in_executor(None, self.handler.get_orders)

            # Update execution reports with latest status
            for order in orders:
                # Find matching report
                for report in self._execution_reports:
                    if report.get('order_id') == order['order_id']:
                        report['status'] = order['status']
                        report['filled'] = order['filled']
                        report['remaining'] = order['remaining']

            # Return and clear reports
            reports = self._execution_reports.copy()
            self._execution_reports.clear()

            logger.info(f"Polled {len(reports)} execution reports")
            return reports

        except Exception as e:
            logger.error(f"Failed to poll reports: {e}")
            raise

    async def get_account_summary(self) -> Dict[str, Any]:
        """
        Get account summary.

        Returns:
            Dict with account information

        Raises:
            IBKRConnectionError: If not connected
        """
        try:
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(None, self.handler.get_account_summary)
            return summary
        except Exception as e:
            logger.error(f"Failed to get account summary: {e}")
            raise

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions.

        Returns:
            List of position dictionaries

        Raises:
            IBKRConnectionError: If not connected
        """
        try:
            loop = asyncio.get_event_loop()
            positions = await loop.run_in_executor(None, self.handler.get_positions)
            return positions
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise

    def health(self) -> Dict[str, Any]:
        """
        Check health status.

        Returns:
            Dict with health information
        """
        try:
            health = self.handler.is_healthy()
            health['session'] = 'exec'
            return health
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'connected': False,
                'session': 'exec',
                'error': str(e)
            }

    async def disconnect(self):
        """Disconnect from IBKR."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.handler.disconnect)
            logger.info("IBKRExecClient disconnected")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
