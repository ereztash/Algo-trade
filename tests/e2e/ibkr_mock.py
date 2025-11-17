"""
IBKR Mock Client for End-to-End Testing

Simulates Interactive Brokers TWS/Gateway behavior with state machine
for order lifecycle testing without real broker connection.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from contracts.validators import OrderIntent, ExecutionReport


class OrderStatus(Enum):
    """Order status states."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass
class Fill:
    """Individual fill record."""

    fill_id: str
    quantity: float
    price: float
    timestamp: datetime
    commission: float = 0.0


@dataclass
class MockOrder:
    """Mock order with state."""

    order_id: str
    symbol: str
    direction: str  # BUY or SELL
    quantity: float
    order_type: str  # MARKET, LIMIT, etc.
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    fills: List[Fill] = field(default_factory=list)
    commission: float = 0.0
    submitted_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    reject_reason: Optional[str] = None


class IBKRMock:
    """
    Mock IBKR client with configurable behavior.

    Features:
    - Order lifecycle simulation
    - Configurable fill delays
    - Partial fill simulation
    - Order rejection scenarios
    - Network timeout simulation
    - Connection state management
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        auto_fill: bool = True,
        fill_delay_ms: float = 100,
        partial_fill_prob: float = 0.1,
        reject_prob: float = 0.0,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.auto_fill = auto_fill
        self.fill_delay_ms = fill_delay_ms
        self.partial_fill_prob = partial_fill_prob
        self.reject_prob = reject_prob

        self._connected = False
        self._orders: Dict[str, MockOrder] = {}
        self._account_info = {
            "nav": 100000.0,
            "cash": 50000.0,
            "buying_power": 200000.0,
        }
        self._positions: Dict[str, float] = {}

    def connect(self) -> bool:
        """Connect to mock broker."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from mock broker."""
        self._connected = False

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    def get_account_info(self) -> dict:
        """Get account information."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        return self._account_info.copy()

    def get_positions(self) -> Dict[str, float]:
        """Get current positions."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")
        return self._positions.copy()

    def place_order(
        self,
        symbol: str,
        quantity: float,
        direction: str,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        **kwargs,
    ) -> dict:
        """
        Place an order.

        Returns:
            Order details including order_id
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        # Generate order ID
        order_id = f"MOCK_ORDER_{uuid4().hex[:8].upper()}"

        # Create order
        order = MockOrder(
            order_id=order_id,
            symbol=symbol,
            direction=direction,
            quantity=quantity,
            order_type=order_type,
            limit_price=limit_price,
            status=OrderStatus.SUBMITTED,
            submitted_at=datetime.utcnow(),
        )

        self._orders[order_id] = order

        # Simulate acknowledgment (immediate in mock)
        order.status = OrderStatus.ACKNOWLEDGED
        order.acknowledged_at = datetime.utcnow()

        # Auto-fill if enabled
        if self.auto_fill:
            self._simulate_fill(order_id)

        return {
            "order_id": order_id,
            "symbol": symbol,
            "quantity": quantity,
            "direction": direction,
            "order_type": order_type,
            "status": order.status.value,
            "submitted_at": order.submitted_at.isoformat(),
        }

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        order = self._orders[order_id]

        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED]:
            return False  # Cannot cancel

        order.status = OrderStatus.CANCELED
        return True

    def get_order_status(self, order_id: str) -> dict:
        """Get order status."""
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        order = self._orders[order_id]

        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "status": order.status.value,
            "filled_quantity": order.filled_quantity,
            "remaining_quantity": order.quantity - order.filled_quantity,
            "average_fill_price": order.average_fill_price,
            "commission": order.commission,
        }

    def _simulate_fill(self, order_id: str) -> None:
        """Simulate order fill (internal)."""
        import random

        order = self._orders[order_id]

        # Determine if rejection (if configured)
        if random.random() < self.reject_prob:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Insufficient buying power"
            return

        # Determine if partial fill
        is_partial = random.random() < self.partial_fill_prob

        if is_partial:
            # Partial fill: 50% of quantity
            fill_quantity = order.quantity * 0.5
            order.status = OrderStatus.PARTIAL_FILL
        else:
            # Full fill
            fill_quantity = order.quantity
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.utcnow()

        # Simulate fill price (for MARKET orders, use mock price)
        if order.order_type == "MARKET":
            # Mock: use a random price around 100
            fill_price = 100.0 + random.uniform(-1.0, 1.0)
        elif order.order_type == "LIMIT" and order.limit_price:
            fill_price = order.limit_price
        else:
            fill_price = 100.0

        # Create fill record
        fill = Fill(
            fill_id=f"FILL_{uuid4().hex[:8].upper()}",
            quantity=fill_quantity,
            price=fill_price,
            timestamp=datetime.utcnow(),
            commission=fill_quantity * 0.01,  # $0.01 per share
        )

        order.fills.append(fill)
        order.filled_quantity += fill_quantity
        order.commission += fill.commission

        # Update average fill price
        total_value = sum(f.quantity * f.price for f in order.fills)
        order.average_fill_price = total_value / order.filled_quantity if order.filled_quantity > 0 else 0.0

        # Update positions
        if order.direction == "BUY":
            self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + fill_quantity
        elif order.direction == "SELL":
            self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) - fill_quantity

    def simulate_disconnect(self) -> None:
        """Simulate network disconnect."""
        self._connected = False

    def simulate_reconnect(self) -> bool:
        """Simulate network reconnect."""
        self._connected = True
        return True

    def get_all_orders(self) -> List[dict]:
        """Get all orders (for testing)."""
        return [
            {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "status": order.status.value,
                "filled_quantity": order.filled_quantity,
            }
            for order in self._orders.values()
        ]

    def reset(self) -> None:
        """Reset mock state (for testing)."""
        self._orders.clear()
        self._positions.clear()
        self._account_info = {
            "nav": 100000.0,
            "cash": 50000.0,
            "buying_power": 200000.0,
        }


class IBKRMockClient:
    """
    Async IBKR Mock Client for comprehensive order lifecycle testing.

    Features:
    - Async order placement and cancellation
    - Duplicate order detection (via intent_id tracking)
    - Configurable fill delays and partial fills
    - State machine with 8 order states
    - Execution report generation
    - Position tracking
    - Commission calculation
    """

    def __init__(
        self,
        auto_fill: bool = True,
        fill_delay_ms: float = 100,
        partial_fill_prob: float = 0.0,
        reject_prob: float = 0.0,
    ):
        self.auto_fill = auto_fill
        self.fill_delay_ms = fill_delay_ms
        self.partial_fill_prob = partial_fill_prob
        self.reject_prob = reject_prob

        self._connected = False
        self._orders: Dict[str, MockOrder] = {}  # order_id -> MockOrder
        self._intent_to_order: Dict[str, str] = {}  # intent_id -> order_id
        self._execution_reports: List[ExecutionReport] = []
        self._fill_tasks: Dict[str, asyncio.Task] = {}  # order_id -> fill task

        # Position tracking
        self.position_buy_qty: float = 0.0
        self.position_sell_qty: float = 0.0
        self._positions: Dict[str, float] = {}  # symbol -> net position

    async def connect(self) -> bool:
        """Connect to mock broker."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Disconnect from mock broker."""
        self._connected = False
        # Cancel all pending fill tasks
        for task in self._fill_tasks.values():
            task.cancel()
        self._fill_tasks.clear()

    def is_connected(self) -> bool:
        """Check connection status."""
        return self._connected

    async def place(self, intent: OrderIntent) -> str:
        """
        Place an order from OrderIntent.

        Args:
            intent: Validated OrderIntent

        Returns:
            order_id: Unique broker order ID

        Raises:
            ValueError: If duplicate intent_id detected
            RuntimeError: If not connected
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        # DUPLICATE DETECTION: Check if intent_id already exists
        if intent.intent_id in self._intent_to_order:
            existing_order_id = self._intent_to_order[intent.intent_id]
            # Option 1: Raise exception (preferred for safety)
            raise ValueError(
                f"Duplicate order intent detected: intent_id={intent.intent_id} "
                f"already mapped to order_id={existing_order_id}"
            )
            # Option 2: Return existing order_id (idempotent behavior)
            # return existing_order_id

        # Generate unique order ID
        order_id = f"MOCK_{intent.symbol}_{uuid4().hex[:8].upper()}"

        # Create mock order
        order = MockOrder(
            order_id=order_id,
            symbol=intent.symbol,
            direction=intent.direction,
            quantity=intent.quantity,
            order_type=intent.order_type,
            limit_price=intent.limit_price,
            status=OrderStatus.SUBMITTED,
            submitted_at=datetime.now(timezone.utc),
        )

        self._orders[order_id] = order
        self._intent_to_order[intent.intent_id] = order_id

        # Generate SUBMITTED execution report
        self._generate_execution_report(intent, order, 'SUBMITTED')

        # Check for immediate rejection (before acknowledgment)
        import random
        if random.random() < self.reject_prob:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "Insufficient buying power (simulated)"
            self._generate_execution_report(intent, order, 'REJECTED')
            return order_id

        # Transition to ACKNOWLEDGED only if auto_fill is enabled
        # When auto_fill=False, order stays in SUBMITTED (for timeout testing)
        if self.auto_fill:
            await asyncio.sleep(0.01)  # Simulate network latency
            order.status = OrderStatus.ACKNOWLEDGED
            order.acknowledged_at = datetime.now(timezone.utc)
            self._generate_execution_report(intent, order, 'ACKNOWLEDGED')

            # Schedule fill
            fill_task = asyncio.create_task(self._simulate_fill_async(intent, order_id))
            self._fill_tasks[order_id] = fill_task

        return order_id

    async def cancel(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Order to cancel

        Returns:
            True if canceled, False if cannot cancel (already filled/terminal)
        """
        if not self._connected:
            raise RuntimeError("Not connected to broker")

        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")

        order = self._orders[order_id]

        # Cannot cancel terminal states
        terminal_states = [
            OrderStatus.FILLED,
            OrderStatus.CANCELED,
            OrderStatus.REJECTED,
            OrderStatus.TIMEOUT,
            OrderStatus.ERROR,
        ]

        if order.status in terminal_states:
            return False

        # Cancel pending fill task
        if order_id in self._fill_tasks:
            self._fill_tasks[order_id].cancel()
            del self._fill_tasks[order_id]

        # Update status
        order.status = OrderStatus.CANCELED

        # Find corresponding intent
        intent_id = next(
            (iid for iid, oid in self._intent_to_order.items() if oid == order_id),
            None,
        )

        # Generate CANCELED report (create minimal intent for report generation)
        if intent_id:
            minimal_intent = self._create_minimal_intent_from_order(order, intent_id)
            self._generate_execution_report(minimal_intent, order, 'CANCELED')

        return True

    def get_order_status(self, order_id: str) -> OrderStatus:
        """Get current order status."""
        if order_id not in self._orders:
            raise ValueError(f"Order not found: {order_id}")
        return self._orders[order_id].status

    async def poll_reports(self) -> List[ExecutionReport]:
        """
        Poll for execution reports.

        Returns:
            List of all execution reports since last poll (or all reports)
        """
        # For simplicity, return all reports
        # In production, would track "consumed" reports
        return self._execution_reports.copy()

    def health(self) -> dict:
        """Health check."""
        return {
            "connected": self._connected,
            "orders_count": len(self._orders),
            "reports_count": len(self._execution_reports),
        }

    async def _simulate_fill_async(self, intent: OrderIntent, order_id: str) -> None:
        """Asynchronously simulate order fill."""
        import random

        order = self._orders[order_id]

        # Wait for fill delay
        await asyncio.sleep(self.fill_delay_ms / 1000.0)

        # Check if order was canceled during delay
        if order.status == OrderStatus.CANCELED:
            return

        # Note: Rejection is now handled in place() before acknowledgment

        # Determine if partial fill
        is_partial = random.random() < self.partial_fill_prob

        if is_partial:
            # First partial fill
            fill_quantity = order.quantity * random.uniform(0.3, 0.7)
            self._apply_fill(intent, order, fill_quantity)

            # Generate PARTIAL_FILL report
            self._generate_execution_report(intent, order, 'PARTIAL_FILL')

            # Wait and fill the rest
            await asyncio.sleep(0.05)

            if order.status != OrderStatus.CANCELED:
                remaining = order.quantity - order.filled_quantity
                self._apply_fill(intent, order, remaining)
                order.status = OrderStatus.FILLED
                order.filled_at = datetime.now(timezone.utc)
                self._generate_execution_report(intent, order, 'FILLED')
        else:
            # Full fill
            self._apply_fill(intent, order, order.quantity)
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(timezone.utc)
            self._generate_execution_report(intent, order, 'FILLED')

        # Cleanup fill task
        if order_id in self._fill_tasks:
            del self._fill_tasks[order_id]

    def _apply_fill(self, intent: OrderIntent, order: MockOrder, fill_quantity: float) -> None:
        """Apply a fill to an order."""
        import random

        # Determine fill price
        if order.order_type == "MARKET":
            # Simulate market price with small random walk
            base_price = 100.0
            fill_price = base_price + random.uniform(-2.0, 2.0)
        elif order.order_type == "LIMIT" and order.limit_price:
            # For LIMIT orders, respect limit constraints
            if intent.direction == "BUY":
                # Buy limit: fill at or below limit
                fill_price = order.limit_price - random.uniform(0, 0.5)
            else:  # SELL
                # Sell limit: fill at or above limit
                fill_price = order.limit_price + random.uniform(0, 0.5)
        else:
            fill_price = 100.0

        # Create fill record
        fill = Fill(
            fill_id=f"FILL_{uuid4().hex[:8].upper()}",
            quantity=fill_quantity,
            price=fill_price,
            timestamp=datetime.now(timezone.utc),
            commission=fill_quantity * 0.005,  # $0.005 per share
        )

        order.fills.append(fill)
        order.filled_quantity += fill_quantity
        order.commission += fill.commission

        # Update average fill price
        total_value = sum(f.quantity * f.price for f in order.fills)
        order.average_fill_price = total_value / order.filled_quantity

        # Update status if partial
        if order.filled_quantity < order.quantity:
            order.status = OrderStatus.PARTIAL_FILL

        # Update positions
        if intent.direction == "BUY":
            self.position_buy_qty += fill_quantity
            self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) + fill_quantity
        elif intent.direction == "SELL":
            self.position_sell_qty += fill_quantity
            self._positions[order.symbol] = self._positions.get(order.symbol, 0.0) - fill_quantity

    def _generate_execution_report(
        self,
        intent: OrderIntent,
        order: MockOrder,
        status: str,
    ) -> None:
        """Generate ExecutionReport for order state change."""
        report = ExecutionReport(
            event_type='execution_report',
            report_id=str(uuid4()),
            intent_id=intent.intent_id,
            order_id=order.order_id,
            symbol=order.symbol,
            status=status,
            timestamp=datetime.now(timezone.utc),
            requested_quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            remaining_quantity=order.quantity - order.filled_quantity,
            average_fill_price=order.average_fill_price if order.filled_quantity > 0 else None,
            commission=order.commission if order.commission > 0 else None,
            fills=[
                {
                    'fill_id': f.fill_id,
                    'quantity': f.quantity,
                    'price': f.price,
                    'timestamp': f.timestamp,
                    'commission': f.commission,
                }
                for f in order.fills
            ] if order.fills else None,
        )

        self._execution_reports.append(report)

    def _create_minimal_intent_from_order(self, order: MockOrder, intent_id: str) -> OrderIntent:
        """Create minimal OrderIntent for report generation (for cancellations)."""
        return OrderIntent(
            event_type='order_intent',
            intent_id=intent_id,
            symbol=order.symbol,
            direction=order.direction,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
            timestamp=datetime.now(timezone.utc),
            strategy_id='OFI',  # Default
        )
