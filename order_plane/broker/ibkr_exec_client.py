"""
Interactive Brokers execution client for Algo-trade.
קליינט ביצוע עסקאות של Interactive Brokers עבור Algo-trade.
"""

import asyncio
from typing import Dict, Any, Optional, List, AsyncIterator
from datetime import datetime
from uuid import uuid4
import logging

# Try to import ib_insync
try:
    from ib_insync import IB, Contract, Order, Trade, OrderStatus, Stock, Future, Forex
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    logging.warning("ib_insync not available, IBKRExecClient will use mock mode")


class IBKRExecClient:
    """
    Interactive Brokers execution client.
    קליינט ביצוע עסקאות של Interactive Brokers.

    Features:
    - Place market/limit orders
    - Cancel orders
    - Monitor order status
    - Execution reports
    - Position tracking
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        Initialize IBKR execution client.

        Args:
            cfg: Configuration dictionary with:
                - host: TWS/Gateway host (default: '127.0.0.1')
                - port: TWS/Gateway port (default: 7497)
                - client_id: Client ID (default: 2)
                - account: Account ID (optional)
        """
        self.cfg = cfg
        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 7497)
        self.client_id = cfg.get('client_id', 2)
        self.account = cfg.get('account', '')

        # IB connection
        self.ib: Optional[Any] = None
        self.connected = False
        self.mock_mode = not IB_INSYNC_AVAILABLE

        # Order tracking
        self.orders: Dict[str, Any] = {}  # order_id -> Trade object
        self.next_order_id = 1

        # Execution reports queue
        self.exec_reports: asyncio.Queue = asyncio.Queue()

        # Logger
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        """
        Connect to TWS or IB Gateway.
        התחברות ל-TWS או IB Gateway.
        """
        if self.connected:
            self.logger.info("Already connected to IBKR")
            return

        if self.mock_mode:
            self.logger.warning("Running in MOCK mode (ib_insync not available)")
            self.connected = True
            return

        try:
            self.ib = IB()
            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                account=self.account
            )

            self.connected = True
            self.logger.info(f"Connected to IBKR at {self.host}:{self.port} "
                           f"(client_id={self.client_id})")

            # Set up event handlers
            self.ib.orderStatusEvent += self._on_order_status
            self.ib.execDetailsEvent += self._on_exec_details
            self.ib.disconnectedEvent += self._on_disconnect

        except Exception as e:
            self.logger.error(f"Failed to connect to IBKR: {e}")
            raise

    async def disconnect(self):
        """Disconnect from TWS/Gateway."""
        if not self.connected:
            return

        if self.mock_mode:
            self.connected = False
            return

        try:
            if self.ib:
                self.ib.disconnect()
            self.connected = False
            self.logger.info("Disconnected from IBKR")

        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")
            raise

    def _on_disconnect(self):
        """Handle disconnection event."""
        self.connected = False
        self.logger.warning("Disconnected from IBKR")

    def _on_order_status(self, trade: Any):
        """Handle order status update."""
        order_id = str(trade.order.orderId)
        status = trade.orderStatus.status
        self.logger.info(f"Order {order_id} status: {status}")

    def _on_exec_details(self, trade: Any, fill: Any):
        """Handle execution details."""
        order_id = str(trade.order.orderId)
        self.logger.info(f"Order {order_id} executed: {fill.execution.shares} @ "
                       f"{fill.execution.avgPrice}")

        # Create execution report
        report = {
            'ts_utc': datetime.utcnow().timestamp(),
            'order_id': order_id,
            'conid': fill.contract.conId if hasattr(fill.contract, 'conId') else 0,
            'fill_px': fill.execution.avgPrice,
            'fill_qty': fill.execution.shares,
            'status': 'FILLED' if trade.orderStatus.filled == trade.order.totalQuantity else 'PARTIAL',
            'slippage': 0.0,  # Calculate based on order price vs fill price
        }

        # Put in queue for async consumption
        asyncio.create_task(self.exec_reports.put(report))

    async def place(self, intent: Dict[str, Any]) -> str:
        """
        Place an order.
        ביצוע הזמנה.

        Args:
            intent: Order intent dictionary with:
                - conid: Contract ID
                - symbol: Symbol (if conid not available)
                - secType: Security type ('STK', 'FUT', 'CASH')
                - exchange: Exchange
                - currency: Currency
                - side: 'BUY' or 'SELL'
                - qty: Quantity
                - tif: Time in force ('DAY', 'GTC', 'IOC')
                - price: Limit price (optional, uses market order if None)

        Returns:
            Order ID
        """
        if not self.connected:
            await self.connect()

        # Generate order ID
        order_id = str(uuid4())[:8] if self.mock_mode else str(self.next_order_id)
        self.next_order_id += 1

        if self.mock_mode:
            self.logger.info(f"Mock order placed: {order_id} - {intent['side']} "
                           f"{intent['qty']} {intent.get('symbol', 'N/A')}")
            self.orders[order_id] = {
                'status': 'FILLED',
                'intent': intent,
            }

            # Create mock execution report
            await self.exec_reports.put({
                'ts_utc': datetime.utcnow().timestamp(),
                'order_id': order_id,
                'conid': intent.get('conid', 0),
                'fill_px': intent.get('price', 100.0),
                'fill_qty': intent['qty'],
                'status': 'FILLED',
                'slippage': 0.01,
            })

            return order_id

        try:
            # Create contract
            contract = self._create_contract(intent)

            # Create order
            action = intent['side']  # 'BUY' or 'SELL'
            quantity = abs(intent['qty'])
            order_type = 'LMT' if 'price' in intent and intent['price'] else 'MKT'

            order = Order()
            order.action = action
            order.totalQuantity = quantity
            order.orderType = order_type
            order.tif = intent.get('tif', 'DAY')

            if order_type == 'LMT':
                order.lmtPrice = intent['price']

            # Place order
            trade = self.ib.placeOrder(contract, order)
            self.orders[order_id] = trade

            self.logger.info(f"Order placed: {order_id} - {action} {quantity} "
                           f"{intent.get('symbol', 'N/A')} @ "
                           f"{intent.get('price', 'MKT')}")

            return order_id

        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            raise

    async def cancel(self, order_id: str):
        """
        Cancel an order.
        ביטול הזמנה.

        Args:
            order_id: Order ID to cancel
        """
        if order_id not in self.orders:
            self.logger.warning(f"Order not found: {order_id}")
            return

        if self.mock_mode:
            self.orders[order_id]['status'] = 'CANCELLED'
            self.logger.info(f"Mock order cancelled: {order_id}")
            return

        try:
            trade = self.orders[order_id]
            self.ib.cancelOrder(trade.order)
            self.logger.info(f"Order cancelled: {order_id}")

        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            raise

    async def poll_reports(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Poll for execution reports.
        קבלת דוחות ביצוע.

        Yields:
            Execution report dictionaries
        """
        while self.connected:
            try:
                report = await asyncio.wait_for(self.exec_reports.get(), timeout=1.0)
                self.logger.debug(f"Execution report: {report['order_id']}")
                yield report
            except asyncio.TimeoutError:
                continue

    async def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current positions.
        קבלת פוזיציות נוכחיות.

        Returns:
            List of position dictionaries
        """
        if not self.connected:
            await self.connect()

        if self.mock_mode:
            return [
                {'symbol': 'AAPL', 'position': 100, 'avgCost': 150.0},
                {'symbol': 'TSLA', 'position': -50, 'avgCost': 250.0},
            ]

        try:
            positions = self.ib.positions()
            result = [
                {
                    'account': pos.account,
                    'symbol': pos.contract.symbol,
                    'conid': pos.contract.conId,
                    'position': pos.position,
                    'avgCost': pos.avgCost,
                    'marketValue': pos.marketValue,
                    'unrealizedPNL': pos.unrealizedPNL,
                }
                for pos in positions
            ]
            self.logger.info(f"Retrieved {len(result)} positions")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            raise

    async def get_account_summary(self) -> Dict[str, Any]:
        """
        Get account summary.
        קבלת סיכום חשבון.

        Returns:
            Account summary dictionary
        """
        if not self.connected:
            await self.connect()

        if self.mock_mode:
            return {
                'NetLiquidation': 1000000.0,
                'GrossPositionValue': 500000.0,
                'AvailableFunds': 500000.0,
                'BuyingPower': 1000000.0,
            }

        try:
            summary = self.ib.accountSummary()
            result = {item.tag: float(item.value) if item.value else 0.0
                     for item in summary}
            self.logger.info("Retrieved account summary")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get account summary: {e}")
            raise

    def health(self) -> Dict[str, Any]:
        """
        Get health status.
        קבלת סטטוס בריאות.

        Returns:
            Health status dictionary
        """
        return {
            "connected": self.connected,
            "session": 'exec',
            "mode": "mock" if self.mock_mode else "ibkr",
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "active_orders": len(self.orders),
        }

    # Helper methods

    def _create_contract(self, spec: Dict[str, Any]) -> Any:
        """Create IB contract from specification."""
        if self.mock_mode:
            return None

        sec_type = spec.get('secType', 'STK')

        if sec_type == 'STK':
            return Stock(
                symbol=spec.get('symbol', ''),
                exchange=spec.get('exchange', 'SMART'),
                currency=spec.get('currency', 'USD')
            )
        elif sec_type == 'FUT':
            return Future(
                symbol=spec.get('symbol', ''),
                exchange=spec.get('exchange', 'CME'),
                currency=spec.get('currency', 'USD'),
                lastTradeDateOrContractMonth=spec.get('expiry', '')
            )
        elif sec_type == 'CASH':
            return Forex(
                pair=spec.get('symbol', ''),
                exchange=spec.get('exchange', 'IDEALPRO')
            )
        else:
            # Generic contract
            contract = Contract()
            for key, value in spec.items():
                setattr(contract, key, value)
            return contract


# Example usage
async def example():
    """Example usage of IBKR execution client."""
    config = {
        'host': '127.0.0.1',
        'port': 7497,  # Paper trading
        'client_id': 200,
    }

    client = IBKRExecClient(config)
    await client.connect()

    # Place order
    intent = {
        'symbol': 'AAPL',
        'secType': 'STK',
        'exchange': 'SMART',
        'currency': 'USD',
        'side': 'BUY',
        'qty': 100,
        'price': 150.0,
        'tif': 'DAY',
    }

    order_id = await client.place(intent)
    print(f"Order placed: {order_id}")

    # Poll for execution reports
    async def poll_task():
        count = 0
        async for report in client.poll_reports():
            print(f"Execution report: {report}")
            count += 1
            if count >= 1:
                break

    await poll_task()

    # Get positions
    positions = await client.get_positions()
    print(f"Positions: {positions}")

    # Get account summary
    account = await client.get_account_summary()
    print(f"Account: {account}")

    # Health check
    print("Health:", client.health())

    # Disconnect
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(example())
