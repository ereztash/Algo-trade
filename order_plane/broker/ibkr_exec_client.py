"""
IBKR Order Execution Client

Handles all order execution operations with Interactive Brokers:
- Order placement (market, limit, stop orders)
- Order status tracking
- Fill confirmations
- Order cancellation
- Position reconciliation

Uses the ibapi (Interactive Brokers API) for communication.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List
from enum import Enum
from dataclasses import dataclass, field
from uuid import uuid4

from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.execution import Execution
from ibapi.commission_report import CommissionReport

logger = logging.getLogger(__name__)


# ==============================================================================
# Order State Tracking
# ==============================================================================

class OrderStatus(Enum):
    """Order lifecycle states."""
    PENDING_SUBMIT = "PendingSubmit"
    PENDING_CANCEL = "PendingCancel"
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    API_CANCELLED = "ApiCancelled"
    CANCELLED = "Cancelled"
    FILLED = "Filled"
    INACTIVE = "Inactive"
    PARTIAL_FILLED = "PartiallyFilled"


@dataclass
class OrderState:
    """Tracks state of a single order."""
    intent_id: str
    ibkr_order_id: int
    symbol: str
    direction: str  # BUY/SELL
    quantity: float
    order_type: str  # MARKET/LIMIT/STOP
    limit_price: Optional[float] = None

    # State tracking
    status: OrderStatus = OrderStatus.PENDING_SUBMIT
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0

    # Timestamps
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    # Execution details
    executions: List[dict] = field(default_factory=list)
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ==============================================================================
# IBKR Wrapper (Callbacks)
# ==============================================================================

class IBKRExecutionWrapper(EWrapper):
    """
    Handles callbacks from IBKR API.

    Key callbacks:
    - nextValidId: Receives next valid order ID
    - orderStatus: Order status updates
    - execDetails: Fill confirmations
    - commissionReport: Commission information
    - error: Error messages
    """

    def __init__(self):
        super().__init__()
        self.next_order_id = None
        self.order_id_event = asyncio.Event()

        # Track orders by IBKR order ID
        self.orders: Dict[int, OrderState] = {}

        # Track orders by intent ID for lookup
        self.intent_to_order: Dict[str, int] = {}

        # Queue for execution reports
        self.execution_queue = asyncio.Queue()

        self.connected = False
        self.connection_event = asyncio.Event()

    def nextValidId(self, orderId: int):
        """Called when connection established. Provides next valid order ID."""
        logger.info(f"IBKR connection established. Next valid order ID: {orderId}")
        self.next_order_id = orderId
        self.connected = True
        self.connection_event.set()
        self.order_id_event.set()

    def orderStatus(
        self,
        orderId: int,
        status: str,
        filled: float,
        remaining: float,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float
    ):
        """
        Called when order status changes.

        Status values: PendingSubmit, PreSubmitted, Submitted, Filled,
                      Cancelled, Inactive, PartiallyFilled
        """
        logger.info(
            f"Order {orderId} status: {status}, "
            f"filled: {filled}/{filled + remaining}, "
            f"avg price: {avgFillPrice:.2f}"
        )

        if orderId in self.orders:
            order_state = self.orders[orderId]
            order_state.status = OrderStatus(status)
            order_state.filled_quantity = filled
            order_state.avg_fill_price = avgFillPrice
            order_state.last_update = datetime.now(timezone.utc)

            # Mark filled timestamp
            if status == "Filled":
                order_state.filled_at = datetime.now(timezone.utc)

                # Queue execution report
                asyncio.create_task(self._queue_execution_report(order_state))

    def execDetails(self, reqId: int, contract: Contract, execution: Execution):
        """
        Called when order is executed (filled).

        Provides detailed execution information including:
        - Execution time
        - Fill price
        - Fill quantity
        - Exchange
        """
        logger.info(
            f"Execution: Order {execution.orderId}, "
            f"{execution.side} {execution.shares} {contract.symbol} "
            f"@ {execution.price} on {execution.exchange}"
        )

        if execution.orderId in self.orders:
            order_state = self.orders[execution.orderId]

            # Record execution
            exec_detail = {
                'exec_id': execution.execId,
                'time': execution.time,
                'shares': execution.shares,
                'price': execution.price,
                'exchange': execution.exchange,
                'side': execution.side
            }
            order_state.executions.append(exec_detail)

    def commissionReport(self, commissionReport: CommissionReport):
        """
        Called after execution with commission details.
        """
        logger.info(
            f"Commission report for order {commissionReport.execId}: "
            f"${commissionReport.commission:.2f}"
        )

        # Find order by execution ID and update commission
        for order_state in self.orders.values():
            for exec_detail in order_state.executions:
                if exec_detail['exec_id'] == commissionReport.execId:
                    order_state.commission += commissionReport.commission

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """
        Error callback.

        Error codes:
        - 2104-2106, 2158: Informational (data farm connection)
        - 200-203: Order rejected
        - 300+: System errors
        """
        # Filter out informational messages
        if errorCode in [2104, 2105, 2106, 2158]:
            logger.debug(f"IBKR Info [{errorCode}]: {errorString}")
            return

        if errorCode >= 2000:
            logger.warning(f"IBKR Warning [{errorCode}]: {errorString}")
        else:
            logger.error(f"IBKR Error [{errorCode}] for request {reqId}: {errorString}")

            # If this is an order error, update order state
            if reqId in self.orders:
                order_state = self.orders[reqId]
                order_state.status = OrderStatus.CANCELLED

    async def _queue_execution_report(self, order_state: OrderState):
        """Queue execution report for publishing to Kafka."""
        report = {
            'execution_id': str(uuid4()),
            'intent_id': order_state.intent_id,
            'ibkr_order_id': order_state.ibkr_order_id,
            'symbol': order_state.symbol,
            'side': order_state.direction,
            'quantity': order_state.quantity,
            'filled_quantity': order_state.filled_quantity,
            'avg_fill_price': order_state.avg_fill_price,
            'status': order_state.status.value,
            'commission': order_state.commission,
            'submitted_at': order_state.submitted_at.isoformat() if order_state.submitted_at else None,
            'filled_at': order_state.filled_at.isoformat() if order_state.filled_at else None,
            'executions': order_state.executions
        }

        await self.execution_queue.put(report)


# ==============================================================================
# IBKR Execution Client
# ==============================================================================

class IBKRExecClient(EClient):
    """
    IBKR Order Execution Client.

    Combines EClient (outgoing requests) with IBKRExecutionWrapper (incoming callbacks).
    """

    def __init__(self, cfg: dict):
        """
        Initialize IBKR execution client.

        Args:
            cfg: Configuration dict with:
                - host: IBKR Gateway/TWS host
                - port: IBKR Gateway/TWS port
                - client_id: Unique client ID
        """
        self.wrapper = IBKRExecutionWrapper()
        super().__init__(self.wrapper)

        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 4002)  # 4002 = paper, 4001 = live
        self.client_id = cfg.get('client_id', 2)  # Order plane uses client_id=2

        self.reader_thread = None

    async def connect_async(self) -> bool:
        """
        Connect to IBKR Gateway/TWS asynchronously.

        Returns:
            True if connected successfully
        """
        try:
            logger.info(f"Connecting to IBKR at {self.host}:{self.port} (client_id={self.client_id})")

            # Connect to IBKR
            self.connect(self.host, self.port, self.client_id)

            # Start message processing thread
            self.reader_thread = asyncio.create_task(self._run_loop())

            # Wait for connection (timeout after 10 seconds)
            try:
                await asyncio.wait_for(self.wrapper.connection_event.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.error("Connection to IBKR timed out")
                return False

            logger.info("✓ Connected to IBKR successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            return False

    async def _run_loop(self):
        """Run IBKR message processing loop."""
        while self.isConnected():
            self.run()
            await asyncio.sleep(0.1)

    def create_contract(self, symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Contract:
        """
        Create IBKR Contract object.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            sec_type: Security type (STK, FUT, OPT, etc.)
            exchange: Exchange (SMART for smart routing)
            currency: Currency (USD, EUR, etc.)

        Returns:
            Contract object
        """
        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = currency
        return contract

    def create_order(
        self,
        direction: str,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None
    ) -> Order:
        """
        Create IBKR Order object.

        Args:
            direction: "BUY" or "SELL"
            quantity: Order quantity
            order_type: "MARKET", "LIMIT", "STOP", etc.
            limit_price: Limit price (for LIMIT orders)
            stop_price: Stop price (for STOP orders)

        Returns:
            Order object
        """
        order = Order()
        order.action = direction  # "BUY" or "SELL"
        order.totalQuantity = quantity
        order.orderType = order_type  # "MKT", "LMT", "STP", etc.

        if order_type == "LIMIT" and limit_price:
            order.lmtPrice = limit_price

        if order_type in ["STOP", "STP"] and stop_price:
            order.auxPrice = stop_price

        # Order properties
        order.transmit = True  # Transmit immediately
        order.eTradeOnly = False
        order.firmQuoteOnly = False

        return order

    async def place_order(self, intent: dict) -> Optional[int]:
        """
        Place order with IBKR.

        Args:
            intent: OrderIntent dict with:
                - intent_id: Unique intent ID
                - symbol: Stock symbol
                - direction: "BUY" or "SELL"
                - quantity: Order quantity
                - order_type: "MARKET", "LIMIT", etc.
                - limit_price: Optional limit price

        Returns:
            IBKR order ID if successful, None otherwise
        """
        try:
            # Wait for next valid order ID
            if self.wrapper.next_order_id is None:
                await asyncio.wait_for(self.wrapper.order_id_event.wait(), timeout=5.0)

            order_id = self.wrapper.next_order_id
            self.wrapper.next_order_id += 1

            # Create contract
            contract = self.create_contract(intent['symbol'])

            # Create order
            ibkr_order_type = {
                'MARKET': 'MKT',
                'LIMIT': 'LMT',
                'STOP': 'STP',
                'STOP_LIMIT': 'STP LMT'
            }.get(intent['order_type'], 'MKT')

            order = self.create_order(
                direction=intent['direction'],
                quantity=intent['quantity'],
                order_type=ibkr_order_type,
                limit_price=intent.get('limit_price')
            )

            # Track order state
            order_state = OrderState(
                intent_id=intent['intent_id'],
                ibkr_order_id=order_id,
                symbol=intent['symbol'],
                direction=intent['direction'],
                quantity=intent['quantity'],
                order_type=intent['order_type'],
                limit_price=intent.get('limit_price'),
                submitted_at=datetime.now(timezone.utc)
            )

            self.wrapper.orders[order_id] = order_state
            self.wrapper.intent_to_order[intent['intent_id']] = order_id

            # Place order
            logger.info(
                f"Placing order {order_id}: "
                f"{intent['direction']} {intent['quantity']} {intent['symbol']} "
                f"({intent['order_type']})"
            )

            self.placeOrder(order_id, contract, order)

            return order_id

        except Exception as e:
            logger.error(f"Failed to place order: {e}", exc_info=True)
            return None

    async def cancel_order(self, order_id: int):
        """Cancel order by IBKR order ID."""
        try:
            logger.info(f"Cancelling order {order_id}")
            self.cancelOrder(order_id, "")

            if order_id in self.wrapper.orders:
                self.wrapper.orders[order_id].status = OrderStatus.PENDING_CANCEL

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")

    def get_order_state(self, intent_id: str) -> Optional[OrderState]:
        """Get order state by intent ID."""
        order_id = self.wrapper.intent_to_order.get(intent_id)
        if order_id:
            return self.wrapper.orders.get(order_id)
        return None

    async def get_execution_reports(self) -> List[dict]:
        """
        Get pending execution reports.

        Returns:
            List of execution report dicts
        """
        reports = []
        while not self.wrapper.execution_queue.empty():
            try:
                report = await asyncio.wait_for(self.wrapper.execution_queue.get(), timeout=0.1)
                reports.append(report)
            except asyncio.TimeoutError:
                break
        return reports

    def health(self) -> dict:
        """Health check."""
        return {
            'connected': self.wrapper.connected,
            'session': 'execution',
            'orders_tracked': len(self.wrapper.orders),
            'next_order_id': self.wrapper.next_order_id
        }

    async def disconnect_async(self):
        """Disconnect from IBKR."""
        logger.info("Disconnecting from IBKR...")
        self.disconnect()

        if self.reader_thread:
            self.reader_thread.cancel()
