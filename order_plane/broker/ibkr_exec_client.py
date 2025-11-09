# -*- coding: utf-8 -*-
"""
order_plane/broker/ibkr_exec_client.py
לקוח ביצוע אסינכרוני עבור IBKR - ביצוע הזמנות וניהול חיבור
"""

import asyncio
import logging
import time
from typing import Dict, Optional, List
from datetime import datetime
from ib_insync import IB, Contract, Order, Trade, OrderStatus
from contracts.validators import OrderIntent, ExecutionReport

logger = logging.getLogger(__name__)


class IBKRExecClient:
    """
    לקוח ביצוע אסינכרוני עבור Interactive Brokers.

    אחריות:
    - ניהול חיבור אסינכרוני ל-IBKR Gateway/TWS
    - שליחת הזמנות לביצוע
    - ביטול הזמנות
    - איסוף דוחות ביצוע (execution reports)
    - ניהול reconnection ו-error handling
    - אכיפת pacing limits

    דוגמה:
        client = IBKRExecClient(cfg)
        await client.connect()
        order_id = await client.place(intent)
        reports = await client.poll_reports()
        await client.cancel(order_id)
    """

    def __init__(self, cfg: Dict):
        """
        אתחול לקוח IBKR.

        Args:
            cfg: קונפיגורציה המכילה:
                - host: כתובת IBKR Gateway (default: 127.0.0.1)
                - port: פורט (4002=paper, 4001=live)
                - client_id: מזהה לקוח ייחודי (1-32)
                - account: מזהה חשבון (DU* = paper)
                - timeout: timeout לחיבור (שניות)
                - max_retries: מספר ניסיונות חיבור מחדש
                - pacing_rate: מספר בקשות מקסימלי לשנייה (default: 50)
        """
        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 4002)  # Paper trading port
        self.client_id = cfg.get('client_id', 1)
        self.account = cfg.get('account', '')
        self.timeout = cfg.get('timeout', 10)
        self.max_retries = cfg.get('max_retries', 3)
        self.pacing_rate = cfg.get('pacing_rate', 50)  # IBKR limit: 50/sec

        # ib_insync instance
        self.ib = IB()

        # State tracking
        self._connected = False
        self._reconnecting = False
        self._order_counter = 0
        self._pending_orders: Dict[int, Trade] = {}
        self._execution_reports: List[ExecutionReport] = []

        # Pacing control (token bucket)
        self._last_request_time = 0
        self._min_interval = 1.0 / self.pacing_rate  # ~0.02s for 50/sec

        # Safety check: ensure paper account for non-production
        if self.port in [4002, 7497]:  # Paper ports
            if self.account and not self.account.startswith('DU'):
                logger.warning(
                    f"⚠️  Paper port {self.port} but account {self.account} "
                    f"doesn't start with 'DU'. Ensure this is correct."
                )

        logger.info(
            f"IBKRExecClient initialized: {self.host}:{self.port}, "
            f"client_id={self.client_id}, account={self.account}"
        )

    async def connect(self):
        """
        יצירת חיבור אסינכרוני ל-IBKR Gateway/TWS.

        תהליך:
        1. ניסיון חיבור עם retry logic
        2. רישום callbacks לאירועי הזמנה
        3. אימות חיבור מוצלח

        Raises:
            ConnectionError: אם החיבור נכשל אחרי כל הניסיונות
        """
        if self._connected:
            logger.info("Already connected to IBKR")
            return

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Connecting to IBKR (attempt {attempt}/{self.max_retries}): "
                    f"{self.host}:{self.port}"
                )

                # Connect with timeout
                await asyncio.wait_for(
                    self._do_connect(),
                    timeout=self.timeout
                )

                self._connected = True
                logger.info(
                    f"✅ Successfully connected to IBKR: {self.host}:{self.port}"
                )

                # Register callbacks for order events
                self._register_callbacks()

                return

            except asyncio.TimeoutError:
                logger.error(
                    f"❌ Connection timeout (attempt {attempt}/{self.max_retries})"
                )
            except Exception as e:
                logger.error(
                    f"❌ Connection failed (attempt {attempt}/{self.max_retries}): {e}"
                )

            # Exponential backoff between retries
            if attempt < self.max_retries:
                wait_time = 2 ** attempt  # 2, 4, 8 seconds
                logger.info(f"Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)

        # All retries failed
        raise ConnectionError(
            f"Failed to connect to IBKR after {self.max_retries} attempts"
        )

    async def _do_connect(self):
        """ביצוע החיבור בפועל (wraps ib_insync's sync connect)."""
        # ib_insync uses asyncio internally, so we can await it
        await self.ib.connectAsync(
            self.host,
            self.port,
            clientId=self.client_id,
            timeout=self.timeout
        )

    def _register_callbacks(self):
        """
        רישום callbacks לאירועי הזמנה.

        ib_insync מספק אירועים:
        - orderStatusEvent: שינוי סטטוס הזמנה
        - execDetailsEvent: פרטי ביצוע (fill)
        - errorEvent: שגיאות
        """
        self.ib.orderStatusEvent += self._on_order_status
        self.ib.execDetailsEvent += self._on_execution
        self.ib.errorEvent += self._on_error

        logger.info("Registered IBKR event callbacks")

    def _on_order_status(self, trade: Trade):
        """
        Callback לשינוי סטטוס הזמנה.

        Args:
            trade: אובייקט Trade מ-ib_insync
        """
        order_id = trade.order.orderId
        status = trade.orderStatus.status
        filled = trade.orderStatus.filled
        remaining = trade.orderStatus.remaining

        logger.info(
            f"Order status update: id={order_id}, status={status}, "
            f"filled={filled}, remaining={remaining}"
        )

        # Track pending orders
        if order_id in self._pending_orders:
            self._pending_orders[order_id] = trade

    def _on_execution(self, trade: Trade, fill):
        """
        Callback לביצוע הזמנה (fill).

        Args:
            trade: אובייקט Trade
            fill: פרטי הביצוע (Execution object)
        """
        try:
            # Create ExecutionReport
            report = self._create_execution_report(trade, fill)
            self._execution_reports.append(report)

            logger.info(
                f"Execution received: order_id={report.order_id}, "
                f"fill_px={report.fill_px}, fill_qty={report.fill_qty}, "
                f"status={report.status}"
            )
        except Exception as e:
            logger.error(f"Error creating execution report: {e}", exc_info=True)

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract):
        """
        Callback לשגיאות IBKR.

        Args:
            reqId: מזהה בקשה
            errorCode: קוד שגיאה IBKR
            errorString: תיאור השגיאה
            contract: חוזה קשור (אם רלוונטי)
        """
        # Error code classification (from IBKR_INTERFACE_MAP.md)
        if errorCode in [100, 103]:  # Rate limit
            logger.warning(
                f"⚠️  RATE LIMIT ERROR {errorCode}: {errorString} (reqId={reqId})"
            )
        elif errorCode in [201, 321, 399, 434]:  # Permanent errors
            logger.error(
                f"❌ PERMANENT ERROR {errorCode}: {errorString} (reqId={reqId})"
            )
        elif errorCode in [504, 1100]:  # Connection errors
            logger.error(
                f"❌ CONNECTION ERROR {errorCode}: {errorString} (reqId={reqId})"
            )
            # Trigger reconnection
            asyncio.create_task(self._reconnect())
        elif errorCode in [2104, 2106]:  # Informational
            logger.info(f"ℹ️  INFO {errorCode}: {errorString}")
        else:
            logger.warning(
                f"⚠️  ERROR {errorCode}: {errorString} (reqId={reqId})"
            )

    async def _reconnect(self):
        """
        ניסיון חיבור מחדש אוטומטי.

        מופעל כאשר מתגלה ניתוק מהרשת.
        """
        if self._reconnecting:
            return  # Already reconnecting

        self._reconnecting = True
        self._connected = False

        logger.warning("⚠️  Connection lost. Attempting to reconnect...")

        try:
            # Disconnect cleanly first
            if self.ib.isConnected():
                self.ib.disconnect()

            # Wait a bit before reconnecting
            await asyncio.sleep(2)

            # Reconnect
            await self.connect()

            logger.info("✅ Reconnection successful")
        except Exception as e:
            logger.error(f"❌ Reconnection failed: {e}")
        finally:
            self._reconnecting = False

    async def place(self, intent: OrderIntent) -> str:
        """
        שליחת הזמנה לביצוע ב-IBKR.

        Args:
            intent: OrderIntent המכיל פרטי ההזמנה

        Returns:
            order_id: מזהה ההזמנה מ-IBKR (str)

        Raises:
            ConnectionError: אם אין חיבור פעיל
            ValueError: אם פרמטרים לא תקינים
        """
        if not self._connected:
            raise ConnectionError("Not connected to IBKR. Call connect() first.")

        # Enforce pacing (token bucket)
        await self._enforce_pacing()

        # Create IBKR contract
        contract = self._create_contract(intent.conid, intent.meta.get('symbol', ''))

        # Create IBKR order
        order = self._create_order(intent)

        try:
            # Place order
            trade = self.ib.placeOrder(contract, order)

            # Wait for acknowledgment (with timeout)
            await asyncio.wait_for(
                self._wait_for_ack(trade),
                timeout=5.0
            )

            order_id = str(trade.order.orderId)

            # Track pending order
            self._pending_orders[trade.order.orderId] = trade

            logger.info(
                f"✅ Order placed: order_id={order_id}, "
                f"conid={intent.conid}, side={intent.side}, qty={intent.qty}"
            )

            return order_id

        except asyncio.TimeoutError:
            logger.error("❌ Order acknowledgment timeout")
            raise
        except Exception as e:
            logger.error(f"❌ Failed to place order: {e}", exc_info=True)
            raise

    async def _enforce_pacing(self):
        """
        אכיפת pacing limits (50 requests/sec).

        משתמש באלגוריתם token bucket: ממתין אם הבקשה הקודמת
        הייתה לאחרונה מדי (< 20ms).
        """
        now = time.time()
        elapsed = now - self._last_request_time

        if elapsed < self._min_interval:
            sleep_time = self._min_interval - elapsed
            logger.debug(f"Pacing: sleeping {sleep_time:.3f}s")
            await asyncio.sleep(sleep_time)

        self._last_request_time = time.time()

    def _create_contract(self, conid: int, symbol: str) -> Contract:
        """
        יצירת אובייקט Contract עבור IBKR.

        Args:
            conid: Contract ID (IBKR)
            symbol: סימול (ticker)

        Returns:
            Contract object
        """
        contract = Contract()
        contract.conId = conid
        contract.symbol = symbol
        contract.secType = 'STK'  # Stock
        contract.exchange = 'SMART'  # Smart routing
        contract.currency = 'USD'

        return contract

    def _create_order(self, intent: OrderIntent) -> Order:
        """
        יצירת אובייקט Order עבור IBKR.

        Args:
            intent: OrderIntent

        Returns:
            Order object
        """
        order = Order()

        # Side
        order.action = intent.side  # 'BUY' or 'SELL'

        # Quantity
        order.totalQuantity = int(intent.qty)

        # Order type
        if intent.price is not None:
            order.orderType = 'LMT'  # Limit order
            order.lmtPrice = round(intent.price, 2)
        else:
            order.orderType = 'MKT'  # Market order

        # Time-in-force
        order.tif = intent.tif  # 'DAY', 'GTC', 'IOC'

        # Account (if specified)
        if self.account:
            order.account = self.account

        return order

    async def _wait_for_ack(self, trade: Trade):
        """
        ממתין לאישור הזמנה (acknowledgment) מ-IBKR.

        Args:
            trade: Trade object
        """
        # Wait until status is not 'PendingSubmit'
        while trade.orderStatus.status in ['PendingSubmit', '']:
            await asyncio.sleep(0.1)

    async def cancel(self, order_id: str) -> bool:
        """
        ביטול הזמנה פעילה.

        Args:
            order_id: מזהה ההזמנה (str)

        Returns:
            bool: True אם הביטול הצליח

        Raises:
            ValueError: אם ההזמנה לא נמצאה
        """
        if not self._connected:
            raise ConnectionError("Not connected to IBKR")

        # Enforce pacing
        await self._enforce_pacing()

        try:
            order_id_int = int(order_id)

            if order_id_int not in self._pending_orders:
                raise ValueError(f"Order {order_id} not found in pending orders")

            trade = self._pending_orders[order_id_int]

            # Cancel order
            self.ib.cancelOrder(trade.order)

            logger.info(f"✅ Order canceled: order_id={order_id}")

            # Wait for cancel confirmation
            await asyncio.sleep(0.5)

            # Remove from pending
            del self._pending_orders[order_id_int]

            return True

        except Exception as e:
            logger.error(f"❌ Failed to cancel order {order_id}: {e}", exc_info=True)
            raise

    async def poll_reports(self) -> List[ExecutionReport]:
        """
        קבלת כל דוחות הביצוע שהצטברו מאז הפעם האחרונה.

        Returns:
            רשימת ExecutionReport
        """
        # Return and clear accumulated reports
        reports = self._execution_reports.copy()
        self._execution_reports.clear()

        logger.debug(f"Polled {len(reports)} execution reports")

        return reports

    def _create_execution_report(self, trade: Trade, fill) -> ExecutionReport:
        """
        יצירת ExecutionReport מתוך Trade ו-Execution.

        Args:
            trade: Trade object
            fill: Execution object

        Returns:
            ExecutionReport
        """
        # Determine status
        status = self._map_status(trade.orderStatus.status, fill)

        # Calculate slippage (if available)
        slippage = 0.0
        if hasattr(trade.order, 'lmtPrice') and trade.order.lmtPrice:
            if trade.order.action == 'BUY':
                slippage = fill.price - trade.order.lmtPrice
            else:  # SELL
                slippage = trade.order.lmtPrice - fill.price

        return ExecutionReport(
            ts_utc=time.time(),
            order_id=str(trade.order.orderId),
            conid=trade.contract.conId,
            fill_px=fill.price,
            fill_qty=fill.shares,
            status=status,
            slippage=slippage
        )

    def _map_status(self, ibkr_status: str, fill) -> str:
        """
        המרת סטטוס IBKR לסטטוס מערכת.

        Args:
            ibkr_status: סטטוס מ-IBKR
            fill: פרטי ביצוע

        Returns:
            'FILLED' | 'PARTIAL' | 'REJECTED'
        """
        status_map = {
            'Filled': 'FILLED',
            'PartiallyFilled': 'PARTIAL',
            'Cancelled': 'REJECTED',
            'Inactive': 'REJECTED',
            'ApiCancelled': 'REJECTED',
        }

        return status_map.get(ibkr_status, 'PARTIAL')

    def health(self) -> Dict:
        """
        בדיקת תקינות החיבור.

        Returns:
            dict עם סטטוס החיבור ומידע נוסף
        """
        return {
            "connected": self._connected and self.ib.isConnected(),
            "session": 'exec',
            "pending_orders": len(self._pending_orders),
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "reconnecting": self._reconnecting,
        }

    async def disconnect(self):
        """
        ניתוק מ-IBKR באופן מסודר.
        """
        if self.ib.isConnected():
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected from IBKR")

    def __del__(self):
        """Cleanup on deletion."""
        if hasattr(self, 'ib') and self.ib.isConnected():
            self.ib.disconnect()
