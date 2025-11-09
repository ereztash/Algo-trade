"""
IBKR Market Data Client - לקוח נתוני שוק מ-IBKR
מטרה: חיבור ל-IBKR API למשיכת נתוני real-time והיסטוריים
"""

import logging
import asyncio
from typing import Dict, Any, Optional, AsyncIterator, List
from datetime import datetime, timedelta
from ib_insync import IB, Contract, Stock, util
from ib_insync.objects import BarData, TickData
import traceback

logger = logging.getLogger(__name__)


class IBKRMarketClient:
    """
    לקוח נתוני שוק מ-IBKR (Interactive Brokers).

    תכונות:
    - חיבור אסינכרוני ל-TWS/Gateway
    - Real-time market data subscriptions
    - Historical data requests
    - Automatic reconnection
    - Error handling מול IBKR error codes
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        אתחול IBKR Market Client.

        Args:
            cfg: Config dictionary עם:
                - host: IBKR host (default: '127.0.0.1')
                - port: IBKR port (4002=paper, 4001=live, 7497=TWS paper, 7496=TWS live)
                - client_id: Client ID (1-32)
                - timeout: Connection timeout (seconds)
                - readonly: Read-only mode (True for Stage 6)
        """
        self.cfg = cfg
        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 4002)  # Default: Paper Gateway
        self.client_id = cfg.get('client_id', 1)
        self.timeout = cfg.get('timeout', 10)
        self.readonly = cfg.get('readonly', True)

        # IB instance
        self.ib = IB()

        # Connection state
        self.connected = False
        self.connection_time: Optional[datetime] = None
        self.last_disconnect: Optional[datetime] = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3

        # Subscriptions tracking
        self.active_subscriptions: Dict[int, Contract] = {}  # reqId -> Contract
        self.subscription_counter = 0

        # Statistics
        self.total_ticks = 0
        self.total_bars = 0
        self.error_count = 0
        self.last_tick_time: Optional[datetime] = None
        self.last_bar_time: Optional[datetime] = None

        # Error handlers
        self._setup_error_handlers()

        logger.info(
            f"IBKRMarketClient initialized: host={self.host}, port={self.port}, "
            f"client_id={self.client_id}, readonly={self.readonly}"
        )

    def _setup_error_handlers(self):
        """
        הגדרת error handlers עבור IBKR events.
        """
        def on_error(reqId, errorCode, errorString, contract):
            """
            Error handler עבור IBKR errors.
            """
            self.error_count += 1

            # Log according to severity
            if errorCode in [2104, 2106, 2158]:  # Info messages
                logger.info(f"IBKR Info [{errorCode}]: {errorString}")
            elif errorCode in [1100, 504]:  # Connection errors
                logger.error(f"IBKR Connection Error [{errorCode}]: {errorString}")
                self.connected = False
            elif errorCode in [100, 103]:  # Pacing violations
                logger.warning(f"IBKR Pacing Violation [{errorCode}]: {errorString}")
            elif errorCode in [201, 321, 399, 434]:  # Permanent errors
                logger.error(f"IBKR Permanent Error [{errorCode}]: {errorString}")
            else:
                logger.warning(f"IBKR Error [{errorCode}]: {errorString} (reqId={reqId})")

        self.ib.errorEvent += on_error

    async def connect(self):
        """
        חיבור ל-IBKR TWS/Gateway (async).

        Returns:
            bool: True אם הצליח, False אחרת
        """
        try:
            logger.info(f"Connecting to IBKR: {self.host}:{self.port} (client_id={self.client_id})")

            await self.ib.connectAsync(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.timeout,
                readonly=self.readonly
            )

            self.connected = True
            self.connection_time = datetime.utcnow()
            self.reconnect_attempts = 0

            logger.info(
                f"Successfully connected to IBKR: {self.host}:{self.port}. "
                f"Server version: {self.ib.client.serverVersion()}"
            )

            return True

        except ConnectionRefusedError:
            logger.error(
                f"Connection refused to IBKR at {self.host}:{self.port}. "
                f"Make sure TWS/Gateway is running."
            )
            self.connected = False
            return False

        except asyncio.TimeoutError:
            logger.error(f"Connection timeout to IBKR at {self.host}:{self.port}")
            self.connected = False
            return False

        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            logger.error(traceback.format_exc())
            self.connected = False
            return False

    async def disconnect(self):
        """
        ניתוק מ-IBKR.
        """
        try:
            if self.ib.isConnected():
                self.ib.disconnect()
                self.connected = False
                self.last_disconnect = datetime.utcnow()
                logger.info("Disconnected from IBKR")
        except Exception as e:
            logger.error(f"Error disconnecting from IBKR: {e}")

    async def subscribe_rt(self, contract: Contract, whatToShow: str = 'TRADES') -> int:
        """
        Subscribe ל-real-time market data.

        Args:
            contract: IBKR Contract object (e.g., Stock('AAPL', 'SMART', 'USD'))
            whatToShow: סוג נתונים - 'TRADES', 'MIDPOINT', 'BID', 'ASK', 'BID_ASK'

        Returns:
            int: Request ID (לביטול subscription)
        """
        if not self.connected:
            logger.error("Not connected to IBKR, cannot subscribe")
            return -1

        try:
            # Qualify contract (get full details)
            qualified = await self.ib.qualifyContractsAsync(contract)
            if not qualified:
                logger.error(f"Could not qualify contract: {contract}")
                return -1

            contract = qualified[0]

            # Request market data
            ticker = self.ib.reqMktData(contract, genericTickList='', snapshot=False)

            # Generate subscription ID
            self.subscription_counter += 1
            req_id = self.subscription_counter
            self.active_subscriptions[req_id] = contract

            logger.info(
                f"Subscribed to real-time data: {contract.symbol} "
                f"(reqId={req_id}, whatToShow={whatToShow})"
            )

            return req_id

        except Exception as e:
            logger.error(f"Error subscribing to market data for {contract}: {e}")
            logger.error(traceback.format_exc())
            return -1

    async def unsubscribe_rt(self, req_id: int):
        """
        ביטול subscription ל-real-time data.

        Args:
            req_id: Request ID מה-subscription
        """
        if req_id not in self.active_subscriptions:
            logger.warning(f"Subscription not found: reqId={req_id}")
            return

        try:
            contract = self.active_subscriptions[req_id]
            self.ib.cancelMktData(contract)
            del self.active_subscriptions[req_id]

            logger.info(f"Unsubscribed from real-time data: reqId={req_id}")

        except Exception as e:
            logger.error(f"Error unsubscribing from market data (reqId={req_id}): {e}")

    async def rt_stream(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream של real-time ticks (async generator).

        Yields:
            Dict: tick data עם fields:
                - symbol, bid, ask, last, volume, timestamp, etc.
        """
        if not self.connected:
            logger.error("Not connected to IBKR, cannot stream")
            return

        logger.info("Starting real-time tick stream")

        try:
            while self.connected:
                # Wait for pending ticks
                await asyncio.sleep(0.01)  # 10ms polling

                # Get pending ticks from IB
                for ticker in self.ib.tickers():
                    if ticker.time is None:
                        continue

                    # Convert to dict
                    tick_data = {
                        'symbol': ticker.contract.symbol,
                        'conid': ticker.contract.conId,
                        'timestamp': ticker.time.timestamp() if ticker.time else None,
                        'bid': ticker.bid if ticker.bid != -1 else None,
                        'ask': ticker.ask if ticker.ask != -1 else None,
                        'last': ticker.last if ticker.last != -1 else None,
                        'bid_size': ticker.bidSize if ticker.bidSize else None,
                        'ask_size': ticker.askSize if ticker.askSize else None,
                        'last_size': ticker.lastSize if ticker.lastSize else None,
                        'volume': ticker.volume if ticker.volume else None,
                        'high': ticker.high if ticker.high != -1 else None,
                        'low': ticker.low if ticker.low != -1 else None,
                        'close': ticker.close if ticker.close != -1 else None
                    }

                    self.total_ticks += 1
                    self.last_tick_time = datetime.utcnow()

                    yield tick_data

        except Exception as e:
            logger.error(f"Error in real-time stream: {e}")
            logger.error(traceback.format_exc())

    async def request_hist(
        self,
        contract: Contract,
        duration: str = '1 D',
        barSize: str = '1 min',
        whatToShow: str = 'TRADES',
        useRTH: bool = True
    ) -> List[Dict[str, Any]]:
        """
        בקשת historical data bars.

        Args:
            contract: IBKR Contract
            duration: Duration string (e.g., '1 D', '1 W', '1 M')
            barSize: Bar size (e.g., '1 min', '5 mins', '1 hour', '1 day')
            whatToShow: 'TRADES', 'MIDPOINT', 'BID', 'ASK'
            useRTH: Use regular trading hours only

        Returns:
            List[Dict]: רשימת bars עם OHLCV data
        """
        if not self.connected:
            logger.error("Not connected to IBKR, cannot request historical data")
            return []

        try:
            # Qualify contract
            qualified = await self.ib.qualifyContractsAsync(contract)
            if not qualified:
                logger.error(f"Could not qualify contract: {contract}")
                return []

            contract = qualified[0]

            # Request historical bars
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',  # Now
                durationStr=duration,
                barSizeSetting=barSize,
                whatToShow=whatToShow,
                useRTH=useRTH,
                formatDate=1  # UTC timestamps
            )

            # Convert to list of dicts
            result = []
            for bar in bars:
                bar_data = {
                    'symbol': contract.symbol,
                    'conid': contract.conId,
                    'timestamp': bar.date.timestamp() if hasattr(bar.date, 'timestamp') else bar.date,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'bar_count': bar.barCount if hasattr(bar, 'barCount') else None,
                    'average': bar.average if hasattr(bar, 'average') else None
                }
                result.append(bar_data)

            self.total_bars += len(result)
            self.last_bar_time = datetime.utcnow()

            logger.info(
                f"Retrieved {len(result)} historical bars for {contract.symbol} "
                f"({duration}, {barSize})"
            )

            return result

        except Exception as e:
            logger.error(f"Error requesting historical data for {contract}: {e}")
            logger.error(traceback.format_exc())
            return []

    def health(self) -> Dict[str, Any]:
        """
        בדיקת health של IBKR connection.

        Returns:
            Dict עם health status
        """
        return {
            'connected': self.connected,
            'session': 'market' if self.connected else 'disconnected',
            'connection_time': self.connection_time.isoformat() if self.connection_time else None,
            'last_disconnect': self.last_disconnect.isoformat() if self.last_disconnect else None,
            'reconnect_attempts': self.reconnect_attempts,
            'active_subscriptions': len(self.active_subscriptions),
            'subscribed_symbols': [c.symbol for c in self.active_subscriptions.values()],
            'total_ticks': self.total_ticks,
            'total_bars': self.total_bars,
            'error_count': self.error_count,
            'last_tick_time': self.last_tick_time.isoformat() if self.last_tick_time else None,
            'last_bar_time': self.last_bar_time.isoformat() if self.last_bar_time else None,
            'server_version': self.ib.client.serverVersion() if self.connected else None
        }

    async def reconnect(self) -> bool:
        """
        ניסיון התחברות מחדש.

        Returns:
            bool: True אם הצליח
        """
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"Max reconnection attempts ({self.max_reconnect_attempts}) reached. "
                f"Giving up."
            )
            return False

        self.reconnect_attempts += 1
        logger.info(f"Attempting to reconnect (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")

        # Disconnect first
        await self.disconnect()

        # Wait with exponential backoff
        wait_time = 2 ** self.reconnect_attempts  # 2, 4, 8 seconds
        await asyncio.sleep(wait_time)

        # Try to connect
        return await self.connect()

    def __del__(self):
        """
        Destructor - disconnect on cleanup.
        """
        if self.ib.isConnected():
            self.ib.disconnect()
