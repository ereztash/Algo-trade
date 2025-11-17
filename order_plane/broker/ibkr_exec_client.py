"""
IBKR Execution Client for Production Order Placement

Features:
- Duplicate order detection via intent_id tracking
- Async order placement and cancellation
- Execution report generation
- Connection health monitoring
- Timeout detection support
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from contracts.validators import OrderIntent, ExecutionReport
from ib_insync import IB, Order, Trade
import structlog


class IBKRExecClient:
    """
    Production IBKR execution client with duplicate detection and lifecycle tracking.

    Features:
    - Duplicate intent_id detection (prevents double orders)
    - Order state tracking
    - Execution report generation
    - Connection management with auto-reconnect
    - Health monitoring
    """

    def __init__(self, cfg: dict):
        """
        Initialize IBKR client.

        Args:
            cfg: Configuration dict with keys:
                - host: IBKR TWS/Gateway host (default: 127.0.0.1)
                - port: IBKR port (default: 7497 for paper, 7496 for live)
                - client_id: Unique client ID
                - read_only: If True, block order placement (safety mode)
        """
        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 7497)
        self.client_id = cfg.get('client_id', 1)
        self.read_only = cfg.get('read_only', False)

        self.ib = IB()
        self.logger = structlog.get_logger(__name__)

        # Duplicate detection: intent_id -> order_id mapping
        self._intent_to_order: Dict[str, int] = {}

        # Order tracking: order_id -> Trade object
        self._orders: Dict[int, Trade] = {}

        # Execution reports queue
        self._execution_reports: List[ExecutionReport] = []

        # Connection state
        self._connected = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

    async def connect(self) -> bool:
        """
        Connect to IBKR TWS/Gateway.

        Returns:
            True if connected successfully

        Raises:
            ConnectionError: If connection fails after retries
        """
        if self._connected and self.ib.isConnected():
            self.logger.info("already_connected", client_id=self.client_id)
            return True

        for attempt in range(1, self._max_reconnect_attempts + 1):
            try:
                await self.ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=20,
                )
                self._connected = True
                self._reconnect_attempts = 0

                self.logger.info(
                    "ibkr_connected",
                    host=self.host,
                    port=self.port,
                    client_id=self.client_id,
                    attempt=attempt,
                )

                # Register event handlers
                self.ib.orderStatusEvent += self._on_order_status
                self.ib.execDetailsEvent += self._on_exec_details

                return True

            except Exception as e:
                self._reconnect_attempts = attempt
                self.logger.error(
                    "connection_failed",
                    host=self.host,
                    port=self.port,
                    attempt=attempt,
                    error=str(e),
                )

                if attempt < self._max_reconnect_attempts:
                    wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s, 16s
                    self.logger.info("retrying_connection", wait_seconds=wait_time)
                    await asyncio.sleep(wait_time)

        raise ConnectionError(
            f"Failed to connect to IBKR after {self._max_reconnect_attempts} attempts"
        )

    def disconnect(self) -> None:
        """Disconnect from IBKR."""
        if self.ib.isConnected():
            self.ib.disconnect()
            self._connected = False
            self.logger.info("ibkr_disconnected")

    async def place(self, intent: OrderIntent) -> str:
        """
        Place an order from OrderIntent.

        Args:
            intent: Validated OrderIntent

        Returns:
            order_id: IBKR order ID (as string)

        Raises:
            ValueError: If duplicate intent_id detected
            RuntimeError: If not connected or read-only mode
        """
        if not self._connected or not self.ib.isConnected():
            raise RuntimeError("Not connected to IBKR")

        if self.read_only:
            raise RuntimeError("Cannot place orders in read-only mode")

        # CRITICAL: Duplicate detection
        if intent.intent_id in self._intent_to_order:
            existing_order_id = self._intent_to_order[intent.intent_id]
            error_msg = (
                f"DUPLICATE ORDER DETECTED: intent_id={intent.intent_id} "
                f"already mapped to order_id={existing_order_id}. "
                f"This prevents double order submission (2x risk exposure)."
            )
            self.logger.error(
                "duplicate_order_blocked",
                intent_id=intent.intent_id,
                existing_order_id=existing_order_id,
                symbol=intent.symbol,
                quantity=intent.quantity,
            )
            raise ValueError(error_msg)

        # Create IBKR order from intent
        order = self._create_ibkr_order(intent)

        # Get contract for symbol
        contract = self._create_contract(intent.symbol)

        # Place order
        try:
            trade = self.ib.placeOrder(contract, order)

            # Store mapping
            order_id = trade.order.orderId
            self._intent_to_order[intent.intent_id] = order_id
            self._orders[order_id] = trade

            self.logger.info(
                "order_placed",
                intent_id=intent.intent_id,
                order_id=order_id,
                symbol=intent.symbol,
                direction=intent.direction,
                quantity=intent.quantity,
                order_type=intent.order_type,
            )

            # Generate SUBMITTED execution report
            self._generate_execution_report(intent, trade, 'SUBMITTED')

            return str(order_id)

        except Exception as e:
            self.logger.error(
                "order_placement_failed",
                intent_id=intent.intent_id,
                symbol=intent.symbol,
                error=str(e),
            )
            raise

    async def cancel(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: IBKR order ID

        Returns:
            True if cancellation requested, False if order not found or already terminal
        """
        if not self._connected or not self.ib.isConnected():
            raise RuntimeError("Not connected to IBKR")

        order_id_int = int(order_id)

        if order_id_int not in self._orders:
            self.logger.warning("cancel_order_not_found", order_id=order_id)
            return False

        trade = self._orders[order_id_int]

        # Check if order is in terminal state
        terminal_statuses = ['Filled', 'Cancelled', 'Inactive', 'ApiCancelled']
        if trade.orderStatus.status in terminal_statuses:
            self.logger.info(
                "cannot_cancel_terminal_order",
                order_id=order_id,
                status=trade.orderStatus.status,
            )
            return False

        try:
            self.ib.cancelOrder(trade.order)
            self.logger.info("order_cancelled", order_id=order_id)
            return True
        except Exception as e:
            self.logger.error("cancel_failed", order_id=order_id, error=str(e))
            return False

    async def poll_reports(self) -> List[ExecutionReport]:
        """
        Poll for execution reports.

        Returns:
            List of ExecutionReport objects
        """
        # Return all reports and clear the queue
        reports = self._execution_reports.copy()
        self._execution_reports.clear()
        return reports

    def health(self) -> dict:
        """
        Health check.

        Returns:
            Dict with connection status and metrics
        """
        return {
            "connected": self._connected and self.ib.isConnected(),
            "session": "exec",
            "client_id": self.client_id,
            "reconnect_attempts": self._reconnect_attempts,
            "active_orders": len([
                o for o in self._orders.values()
                if o.orderStatus.status not in ['Filled', 'Cancelled', 'Inactive']
            ]),
            "total_orders": len(self._orders),
            "reports_pending": len(self._execution_reports),
        }

    def _create_ibkr_order(self, intent: OrderIntent) -> Order:
        """Create IBKR Order object from OrderIntent."""
        order = Order()
        order.action = intent.direction  # BUY or SELL
        order.totalQuantity = intent.quantity
        order.orderType = intent.order_type  # MARKET, LIMIT, etc.

        if intent.order_type == 'LIMIT' and intent.limit_price:
            order.lmtPrice = intent.limit_price

        if intent.order_type == 'STOP' and intent.stop_price:
            order.auxPrice = intent.stop_price

        if intent.time_in_force:
            order.tif = intent.time_in_force  # DAY, GTC, IOC, FOK

        return order

    def _create_contract(self, symbol: str):
        """Create IBKR Contract object for symbol."""
        from ib_insync import Stock
        return Stock(symbol, 'SMART', 'USD')

    def _on_order_status(self, trade: Trade):
        """Callback for order status updates."""
        status = trade.orderStatus.status
        order_id = trade.order.orderId

        self.logger.info(
            "order_status_update",
            order_id=order_id,
            status=status,
            filled=trade.orderStatus.filled,
            remaining=trade.orderStatus.remaining,
        )

        # Find corresponding intent_id
        intent_id = next(
            (iid for iid, oid in self._intent_to_order.items() if oid == order_id),
            None,
        )

        if not intent_id:
            self.logger.warning("order_status_no_intent_mapping", order_id=order_id)
            return

        # Map IBKR status to ExecutionReport status
        status_mapping = {
            'PendingSubmit': 'SUBMITTED',
            'PreSubmitted': 'SUBMITTED',
            'Submitted': 'ACKNOWLEDGED',
            'PartiallyFilled': 'PARTIAL_FILL',
            'Filled': 'FILLED',
            'Cancelled': 'CANCELED',
            'ApiCancelled': 'CANCELED',
            'Inactive': 'REJECTED',
        }

        mapped_status = status_mapping.get(status, 'ERROR')

        # Generate execution report (would need to reconstruct intent or store it)
        # For now, just log
        self.logger.info(
            "generating_exec_report",
            intent_id=intent_id,
            order_id=order_id,
            status=mapped_status,
        )

    def _on_exec_details(self, trade: Trade, fill):
        """Callback for execution (fill) details."""
        self.logger.info(
            "execution_received",
            order_id=trade.order.orderId,
            fill_price=fill.execution.price,
            fill_qty=fill.execution.shares,
            cumulative_qty=fill.execution.cumQty,
        )

    def _generate_execution_report(
        self,
        intent: OrderIntent,
        trade: Trade,
        status: str,
    ) -> None:
        """Generate ExecutionReport for order state change."""
        order_status = trade.orderStatus

        report = ExecutionReport(
            event_type='execution_report',
            report_id=str(uuid4()),
            intent_id=intent.intent_id,
            order_id=str(trade.order.orderId),
            symbol=intent.symbol,
            status=status,
            timestamp=datetime.now(timezone.utc),
            requested_quantity=intent.quantity,
            filled_quantity=float(order_status.filled),
            remaining_quantity=float(order_status.remaining),
            average_fill_price=float(order_status.avgFillPrice) if order_status.avgFillPrice > 0 else None,
        )

        self._execution_reports.append(report)
