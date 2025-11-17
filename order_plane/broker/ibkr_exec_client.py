"""
IBKR Execution Client for Order Plane.

This module provides the IBKRExecClient class that handles order execution
with Interactive Brokers (IBKR) via ib_insync.

Key Responsibilities:
- Convert OrderIntent messages to IBKR order format
- Submit orders to IBKR TWS/Gateway
- Track order lifecycle and status updates
- Generate ExecutionReport messages from order fills
- Handle order cancellation and error scenarios
- Maintain connection to IBKR

Architecture Flow:
    OrderIntent → place() → IBKR Order → TWS/Gateway
                    ↓
    Track order_id ↔ intent_id mapping
                    ↓
    poll_reports() → Check IBKR status → ExecutionReport
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4
from dataclasses import dataclass, field
import logging

from ib_insync import IB, Stock, Order, Trade, OrderStatus as IBOrderStatus
from contracts.validators import OrderIntent, ExecutionReport, Fill, LatencyMetrics, ExecutionCosts


logger = logging.getLogger(__name__)


@dataclass
class TrackedOrder:
    """Internal order tracking with timestamps and state."""
    intent_id: str
    order_id: str  # IBKR order ID
    symbol: str
    direction: str
    quantity: float
    order_type: str

    # Timestamps for latency tracking
    intent_timestamp: datetime
    submitted_timestamp: Optional[datetime] = None
    acknowledged_timestamp: Optional[datetime] = None
    filled_timestamp: Optional[datetime] = None

    # Order state
    status: str = "PENDING"
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    fills: List[Fill] = field(default_factory=list)
    commission: float = 0.0

    # IBKR Trade object reference
    ib_trade: Optional[Trade] = None

    # Error tracking
    reject_reason: Optional[str] = None
    error_message: Optional[str] = None

    # Pricing
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None


class IBKRExecClient:
    """
    IBKR Execution Client for placing and tracking orders.

    This client converts OrderIntent messages to IBKR orders, submits them,
    tracks their lifecycle, and generates ExecutionReport messages.

    Usage:
        client = IBKRExecClient(config)
        await client.connect()

        # Place order
        order_id = await client.place(order_intent)

        # Poll for execution reports
        reports = await client.poll_reports()

        # Cancel order
        success = await client.cancel(order_id)

        await client.disconnect()
    """

    def __init__(self, cfg: dict):
        """
        Initialize IBKR execution client.

        Args:
            cfg: Configuration dict with:
                - host: IBKR Gateway/TWS host (default: '127.0.0.1')
                - port: IBKR Gateway/TWS port (default: 7497 for paper, 7496 for live)
                - client_id: Unique client ID (default: 1)
                - account: IBKR account number (optional)
                - timeout: Connection timeout in seconds (default: 10)
        """
        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 7497)  # 7497 = paper trading, 7496 = live
        self.client_id = cfg.get('client_id', 1)
        self.account = cfg.get('account', None)
        self.timeout = cfg.get('timeout', 10)

        # ib_insync IB instance
        self.ib = IB()

        # Order tracking: order_id → TrackedOrder
        self._tracked_orders: Dict[str, TrackedOrder] = {}

        # Intent mapping: intent_id → order_id
        self._intent_to_order: Dict[str, str] = {}

        # Connection state
        self._connected = False

        logger.info(
            f"IBKRExecClient initialized: {self.host}:{self.port} "
            f"(client_id={self.client_id}, account={self.account})"
        )

    async def connect(self):
        """
        Connect to IBKR TWS/Gateway.

        Raises:
            ConnectionError: If connection fails
        """
        if self._connected:
            logger.warning("Already connected to IBKR")
            return

        try:
            logger.info(f"Connecting to IBKR at {self.host}:{self.port}...")
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.timeout
            )

            self._connected = True
            logger.info("✅ Successfully connected to IBKR")

            # Register event handlers for order status updates
            self.ib.orderStatusEvent += self._on_order_status
            self.ib.execDetailsEvent += self._on_execution

        except Exception as e:
            logger.error(f"❌ Failed to connect to IBKR: {e}")
            raise ConnectionError(f"IBKR connection failed: {e}")

    async def disconnect(self):
        """Disconnect from IBKR."""
        if not self._connected:
            return

        logger.info("Disconnecting from IBKR...")
        self.ib.disconnect()
        self._connected = False
        logger.info("Disconnected from IBKR")

    def is_connected(self) -> bool:
        """Check if connected to IBKR."""
        return self._connected and self.ib.isConnected()

    async def place(self, intent: OrderIntent) -> str:
        """
        Place an order based on OrderIntent.

        Converts OrderIntent message to IBKR order format, submits to IBKR,
        and tracks the order lifecycle.

        Args:
            intent: OrderIntent message from Strategy Plane

        Returns:
            order_id: IBKR order ID (as string)

        Raises:
            ConnectionError: If not connected to IBKR
            ValueError: If order parameters are invalid
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to IBKR")

        logger.info(f"Placing order for intent {intent.intent_id}: {intent.symbol} {intent.direction} {intent.quantity}")

        # 1. Create IBKR contract (Stock)
        contract = Stock(intent.symbol, 'SMART', 'USD')

        # 2. Create IBKR order
        ib_order = self._create_ibkr_order(intent)

        # 3. Submit order to IBKR
        try:
            trade = self.ib.placeOrder(contract, ib_order)

            # Wait for order to be submitted (with timeout)
            await asyncio.wait_for(
                self._wait_for_submission(trade),
                timeout=5.0
            )

            # Get IBKR order ID
            order_id = str(trade.order.orderId)
            submitted_timestamp = datetime.utcnow()

            logger.info(f"Order submitted to IBKR: order_id={order_id}")

        except asyncio.TimeoutError:
            error_msg = f"Order submission timeout for intent {intent.intent_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        except Exception as e:
            error_msg = f"Order submission failed: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 4. Track the order
        tracked_order = TrackedOrder(
            intent_id=intent.intent_id,
            order_id=order_id,
            symbol=intent.symbol,
            direction=intent.direction,
            quantity=intent.quantity,
            order_type=intent.order_type,
            intent_timestamp=intent.timestamp,
            submitted_timestamp=submitted_timestamp,
            status="SUBMITTED",
            ib_trade=trade,
            limit_price=intent.limit_price,
            stop_price=intent.stop_price,
        )

        self._tracked_orders[order_id] = tracked_order
        self._intent_to_order[intent.intent_id] = order_id

        logger.info(f"Order tracked: {order_id} for intent {intent.intent_id}")

        return order_id

    def _create_ibkr_order(self, intent: OrderIntent) -> Order:
        """
        Convert OrderIntent to IBKR Order object.

        Args:
            intent: OrderIntent message

        Returns:
            IBKR Order object
        """
        # Determine action (BUY/SELL)
        action = intent.direction  # Already 'BUY' or 'SELL'

        # Map order type
        order_type_map = {
            'MARKET': 'MKT',
            'LIMIT': 'LMT',
            'STOP': 'STP',
            'STOP_LIMIT': 'STP LMT',
            'ADAPTIVE': 'MIDPRICE',  # Or use IBKR adaptive algo
        }

        ib_order_type = order_type_map.get(intent.order_type, 'MKT')

        # Create order
        order = Order()
        order.action = action
        order.totalQuantity = intent.quantity
        order.orderType = ib_order_type

        # Set limit price for LIMIT orders
        if intent.order_type == 'LIMIT' and intent.limit_price:
            order.lmtPrice = intent.limit_price

        # Set stop price for STOP orders
        if intent.order_type in ['STOP', 'STOP_LIMIT'] and intent.stop_price:
            order.auxPrice = intent.stop_price  # IBKR uses auxPrice for stop price
            if intent.order_type == 'STOP_LIMIT' and intent.limit_price:
                order.lmtPrice = intent.limit_price

        # Set time in force
        tif_map = {
            'DAY': 'DAY',
            'GTC': 'GTC',
            'IOC': 'IOC',
            'FOK': 'FOK',
        }
        order.tif = tif_map.get(intent.time_in_force, 'DAY')

        # Set account if specified
        if self.account:
            order.account = self.account

        logger.debug(f"Created IBKR order: {order}")

        return order

    async def _wait_for_submission(self, trade: Trade):
        """Wait for order to be submitted to IBKR."""
        while trade.orderStatus.status in ['PendingSubmit', '']:
            await asyncio.sleep(0.1)
            await self.ib.updateEvent

    async def cancel(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: IBKR order ID

        Returns:
            True if cancellation successful, False otherwise
        """
        if not self.is_connected():
            raise ConnectionError("Not connected to IBKR")

        if order_id not in self._tracked_orders:
            logger.warning(f"Order {order_id} not found in tracked orders")
            return False

        tracked_order = self._tracked_orders[order_id]

        # Check if order can be cancelled
        if tracked_order.status in ['FILLED', 'CANCELED', 'REJECTED']:
            logger.warning(f"Cannot cancel order {order_id} with status {tracked_order.status}")
            return False

        try:
            # Cancel via ib_insync
            if tracked_order.ib_trade:
                self.ib.cancelOrder(tracked_order.ib_trade.order)
                logger.info(f"Cancellation request sent for order {order_id}")

                # Update status
                tracked_order.status = "CANCELED"
                return True
            else:
                logger.error(f"No IBKR trade reference for order {order_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def poll_reports(self) -> List[ExecutionReport]:
        """
        Poll for execution reports from IBKR.

        Checks all tracked orders for status updates and generates
        ExecutionReport messages for any changes.

        Returns:
            List of ExecutionReport messages
        """
        if not self.is_connected():
            logger.warning("Not connected to IBKR, cannot poll reports")
            return []

        reports = []
        current_time = datetime.utcnow()

        for order_id, tracked_order in self._tracked_orders.items():
            # Skip if no IBKR trade reference
            if not tracked_order.ib_trade:
                continue

            # Get current order status from IBKR
            ib_status = tracked_order.ib_trade.orderStatus

            # Update tracked order state
            old_status = tracked_order.status
            new_status = self._map_ibkr_status(ib_status.status)

            # Update timestamps
            if new_status == "ACKNOWLEDGED" and not tracked_order.acknowledged_timestamp:
                tracked_order.acknowledged_timestamp = current_time

            if new_status == "FILLED" and not tracked_order.filled_timestamp:
                tracked_order.filled_timestamp = current_time

            # Update fills
            tracked_order.filled_quantity = ib_status.filled
            tracked_order.average_fill_price = ib_status.avgFillPrice if ib_status.avgFillPrice > 0 else 0.0

            # Check if status changed or we have fills
            if new_status != old_status or tracked_order.filled_quantity > 0:
                tracked_order.status = new_status

                # Generate ExecutionReport
                report = self._create_execution_report(tracked_order, current_time)
                reports.append(report)

                logger.info(
                    f"Generated ExecutionReport: order_id={order_id}, "
                    f"status={new_status}, filled={tracked_order.filled_quantity}"
                )

        return reports

    def _map_ibkr_status(self, ibkr_status: str) -> str:
        """
        Map IBKR order status to ExecutionReport status.

        IBKR statuses: PendingSubmit, PendingCancel, PreSubmitted, Submitted,
                      ApiCancelled, Cancelled, Filled, Inactive

        ExecutionReport statuses: SUBMITTED, ACKNOWLEDGED, PARTIAL_FILL, FILLED,
                                  CANCELED, REJECTED, TIMEOUT, ERROR
        """
        status_map = {
            'PendingSubmit': 'SUBMITTED',
            'PreSubmitted': 'SUBMITTED',
            'Submitted': 'ACKNOWLEDGED',
            'Filled': 'FILLED',
            'Cancelled': 'CANCELED',
            'ApiCancelled': 'CANCELED',
            'PendingCancel': 'CANCELED',
            'Inactive': 'ERROR',
        }

        return status_map.get(ibkr_status, 'ERROR')

    def _create_execution_report(self, tracked_order: TrackedOrder, timestamp: datetime) -> ExecutionReport:
        """
        Create ExecutionReport from TrackedOrder.

        Args:
            tracked_order: Internal tracked order
            timestamp: Report generation timestamp

        Returns:
            ExecutionReport message
        """
        # Calculate latency metrics
        latency_metrics = None
        if tracked_order.submitted_timestamp:
            intent_to_submit = int(
                (tracked_order.submitted_timestamp - tracked_order.intent_timestamp).total_seconds() * 1000
            )

            submit_to_ack = None
            if tracked_order.acknowledged_timestamp:
                submit_to_ack = int(
                    (tracked_order.acknowledged_timestamp - tracked_order.submitted_timestamp).total_seconds() * 1000
                )

            ack_to_fill = None
            total_latency = None
            if tracked_order.filled_timestamp:
                if tracked_order.acknowledged_timestamp:
                    ack_to_fill = int(
                        (tracked_order.filled_timestamp - tracked_order.acknowledged_timestamp).total_seconds() * 1000
                    )
                total_latency = int(
                    (tracked_order.filled_timestamp - tracked_order.intent_timestamp).total_seconds() * 1000
                )

            latency_metrics = LatencyMetrics(
                intent_to_submit_ms=intent_to_submit,
                submit_to_ack_ms=submit_to_ack,
                ack_to_fill_ms=ack_to_fill,
                total_latency_ms=total_latency,
            )

        # Calculate remaining quantity
        remaining_qty = tracked_order.quantity - tracked_order.filled_quantity

        # Determine if partial fill
        status = tracked_order.status
        if 0 < tracked_order.filled_quantity < tracked_order.quantity:
            status = "PARTIAL_FILL"

        # Create execution report
        report = ExecutionReport(
            event_type='execution_report',
            report_id=str(uuid4()),
            intent_id=tracked_order.intent_id,
            order_id=tracked_order.order_id,
            symbol=tracked_order.symbol,
            status=status,
            timestamp=timestamp,
            direction=tracked_order.direction,
            submitted_timestamp=tracked_order.submitted_timestamp,
            acknowledged_timestamp=tracked_order.acknowledged_timestamp,
            filled_timestamp=tracked_order.filled_timestamp,
            requested_quantity=tracked_order.quantity,
            filled_quantity=tracked_order.filled_quantity,
            remaining_quantity=remaining_qty,
            average_fill_price=tracked_order.average_fill_price if tracked_order.average_fill_price > 0 else None,
            limit_price=tracked_order.limit_price,
            commission=tracked_order.commission,
            reject_reason=tracked_order.reject_reason,
            error_message=tracked_order.error_message,
            latency_metrics=latency_metrics,
        )

        return report

    def _on_order_status(self, trade: Trade):
        """
        Callback for IBKR order status updates.

        This is called by ib_insync when order status changes.
        """
        order_id = str(trade.order.orderId)

        if order_id in self._tracked_orders:
            logger.debug(f"Order status update: {order_id} → {trade.orderStatus.status}")
        else:
            logger.warning(f"Received status update for untracked order: {order_id}")

    def _on_execution(self, trade: Trade, fill):
        """
        Callback for IBKR execution (fill) events.

        This is called by ib_insync when an order is filled.
        """
        order_id = str(trade.order.orderId)

        if order_id in self._tracked_orders:
            tracked_order = self._tracked_orders[order_id]

            # Create fill record
            fill_record = Fill(
                fill_id=fill.execution.execId,
                quantity=fill.execution.shares,
                price=fill.execution.price,
                timestamp=datetime.utcnow(),
                commission=fill.commissionReport.commission if fill.commissionReport else 0.0,
            )

            tracked_order.fills.append(fill_record)
            tracked_order.commission += fill_record.commission

            logger.info(
                f"Order filled: {order_id}, qty={fill_record.quantity}, "
                f"price={fill_record.price}, commission={fill_record.commission}"
            )
        else:
            logger.warning(f"Received fill for untracked order: {order_id}")

    def health(self) -> dict:
        """
        Return health status of the execution client.

        Returns:
            Dict with connection status and metrics
        """
        return {
            "connected": self.is_connected(),
            "session": "exec",
            "tracked_orders": len(self._tracked_orders),
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
        }

    def get_tracked_order(self, order_id: str) -> Optional[TrackedOrder]:
        """Get tracked order by order_id."""
        return self._tracked_orders.get(order_id)

    def get_order_by_intent(self, intent_id: str) -> Optional[TrackedOrder]:
        """Get tracked order by intent_id."""
        order_id = self._intent_to_order.get(intent_id)
        if order_id:
            return self._tracked_orders.get(order_id)
        return None
