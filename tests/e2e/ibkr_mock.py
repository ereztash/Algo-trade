"""
IBKR Mock Client for End-to-End Testing

Simulates Interactive Brokers TWS/Gateway behavior with state machine
for order lifecycle testing without real broker connection.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4


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
