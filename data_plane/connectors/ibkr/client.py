"""
Interactive Brokers market data client for Algo-trade.
קליינט נתוני שוק של Interactive Brokers עבור Algo-trade.
"""

import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
import logging

# Try to import ib_insync
try:
    from ib_insync import IB, Contract, Stock, Future, Forex, Index, ContractDetails
    from ib_insync import BarDataList, Ticker, util
    IB_INSYNC_AVAILABLE = True
except ImportError:
    IB_INSYNC_AVAILABLE = False
    logging.warning("ib_insync not available, IBKRMarketClient will use mock mode")


class IBKRMarketClient:
    """
    Interactive Brokers market data client.
    קליינט נתוני שוק של Interactive Brokers.

    Features:
    - Real-time market data (ticks, bars)
    - Historical data requests
    - Contract details lookup
    - Connection management
    - Auto-reconnect on disconnect
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        Initialize IBKR market data client.

        Args:
            cfg: Configuration dictionary with:
                - host: TWS/Gateway host (default: '127.0.0.1')
                - port: TWS/Gateway port (default: 7497 for paper, 7496 for live)
                - client_id: Client ID (default: 1)
                - readonly: Read-only mode (default: True)
                - account: Account ID (optional)
        """
        self.cfg = cfg
        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 7497)
        self.client_id = cfg.get('client_id', 1)
        self.readonly = cfg.get('readonly', True)
        self.account = cfg.get('account', '')

        # IB connection
        self.ib: Optional[Any] = None
        self.connected = False
        self.mock_mode = not IB_INSYNC_AVAILABLE

        # Subscriptions
        self.subscriptions: Dict[str, Ticker] = {}
        self.callbacks: Dict[str, List[Callable]] = {}

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
                readonly=self.readonly,
                account=self.account
            )

            self.connected = True
            self.logger.info(f"Connected to IBKR at {self.host}:{self.port} "
                           f"(client_id={self.client_id})")

            # Set up disconnect handler
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

    async def subscribe_rt(self,
                          contract: Dict[str, Any],
                          whatToShow: str = "TRADES",
                          callback: Optional[Callable] = None) -> str:
        """
        Subscribe to real-time market data.
        הרשמה לנתוני שוק בזמן אמת.

        Args:
            contract: Contract specification dict with fields:
                - symbol: Ticker symbol
                - secType: 'STK', 'FUT', 'CASH', 'IND', etc.
                - exchange: Primary exchange (e.g., 'SMART', 'NASDAQ')
                - currency: Currency (e.g., 'USD')
            whatToShow: Data type ('TRADES', 'MIDPOINT', 'BID', 'ASK')
            callback: Callback function for data updates

        Returns:
            Subscription ID
        """
        if not self.connected:
            await self.connect()

        # Create contract
        ib_contract = self._create_contract(contract)
        sub_id = f"{contract['symbol']}_{contract['secType']}"

        if self.mock_mode:
            self.logger.info(f"Mock subscription: {sub_id}")
            self.subscriptions[sub_id] = None
            if callback:
                if sub_id not in self.callbacks:
                    self.callbacks[sub_id] = []
                self.callbacks[sub_id].append(callback)
            return sub_id

        try:
            # Request market data
            ticker = self.ib.reqMktData(ib_contract, whatToShow, snapshot=False)

            # Store subscription
            self.subscriptions[sub_id] = ticker

            # Register callback
            if callback:
                if sub_id not in self.callbacks:
                    self.callbacks[sub_id] = []
                self.callbacks[sub_id].append(callback)
                ticker.updateEvent += lambda t: callback(self._ticker_to_dict(t))

            self.logger.info(f"Subscribed to real-time data: {sub_id} ({whatToShow})")
            return sub_id

        except Exception as e:
            self.logger.error(f"Failed to subscribe to {sub_id}: {e}")
            raise

    async def unsubscribe_rt(self, sub_id: str):
        """Unsubscribe from real-time data."""
        if sub_id not in self.subscriptions:
            self.logger.warning(f"Subscription not found: {sub_id}")
            return

        if self.mock_mode:
            del self.subscriptions[sub_id]
            if sub_id in self.callbacks:
                del self.callbacks[sub_id]
            return

        try:
            ticker = self.subscriptions[sub_id]
            self.ib.cancelMktData(ticker.contract)
            del self.subscriptions[sub_id]
            if sub_id in self.callbacks:
                del self.callbacks[sub_id]

            self.logger.info(f"Unsubscribed from: {sub_id}")

        except Exception as e:
            self.logger.error(f"Failed to unsubscribe from {sub_id}: {e}")
            raise

    async def request_hist(self,
                          contract: Dict[str, Any],
                          duration: str = "1 D",
                          barSize: str = "1 min",
                          whatToShow: str = "TRADES",
                          useRTH: bool = True) -> List[Dict[str, Any]]:
        """
        Request historical bar data.
        בקשת נתונים היסטוריים.

        Args:
            contract: Contract specification dict
            duration: Duration string (e.g., '1 D', '1 W', '1 M')
            barSize: Bar size (e.g., '1 min', '5 mins', '1 hour', '1 day')
            whatToShow: Data type ('TRADES', 'MIDPOINT', 'BID', 'ASK')
            useRTH: Use regular trading hours only

        Returns:
            List of bar dictionaries
        """
        if not self.connected:
            await self.connect()

        ib_contract = self._create_contract(contract)

        if self.mock_mode:
            self.logger.info(f"Mock historical request: {contract['symbol']}")
            return self._mock_historical_bars(duration, barSize)

        try:
            # Request historical data
            bars: BarDataList = await self.ib.reqHistoricalDataAsync(
                contract=ib_contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=barSize,
                whatToShow=whatToShow,
                useRTH=useRTH,
                formatDate=1  # UTC timestamps
            )

            # Convert to dict list
            result = [self._bar_to_dict(bar) for bar in bars]
            self.logger.info(f"Received {len(result)} historical bars for "
                           f"{contract['symbol']}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to fetch historical data for "
                            f"{contract['symbol']}: {e}")
            raise

    async def get_contract_details(self,
                                   contract: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get contract details.
        קבלת פרטי חוזה.

        Args:
            contract: Contract specification dict

        Returns:
            List of contract detail dictionaries
        """
        if not self.connected:
            await self.connect()

        ib_contract = self._create_contract(contract)

        if self.mock_mode:
            self.logger.info(f"Mock contract details: {contract['symbol']}")
            return [{'conId': 12345, 'symbol': contract['symbol']}]

        try:
            details: List[ContractDetails] = await self.ib.reqContractDetailsAsync(
                ib_contract
            )
            result = [self._contract_details_to_dict(cd) for cd in details]
            self.logger.info(f"Retrieved {len(result)} contract details for "
                           f"{contract['symbol']}")
            return result

        except Exception as e:
            self.logger.error(f"Failed to get contract details for "
                            f"{contract['symbol']}: {e}")
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
            "session": 'market',
            "mode": "mock" if self.mock_mode else "ibkr",
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "subscriptions": list(self.subscriptions.keys()),
            "num_subscriptions": len(self.subscriptions),
        }

    # Helper methods

    def _create_contract(self, spec: Dict[str, Any]) -> Any:
        """Create IB contract from specification."""
        if self.mock_mode:
            return None

        sec_type = spec.get('secType', 'STK')

        if sec_type == 'STK':
            return Stock(
                symbol=spec['symbol'],
                exchange=spec.get('exchange', 'SMART'),
                currency=spec.get('currency', 'USD')
            )
        elif sec_type == 'FUT':
            return Future(
                symbol=spec['symbol'],
                exchange=spec.get('exchange', 'CME'),
                currency=spec.get('currency', 'USD'),
                lastTradeDateOrContractMonth=spec.get('expiry', '')
            )
        elif sec_type == 'CASH':
            return Forex(
                pair=spec['symbol'],
                exchange=spec.get('exchange', 'IDEALPRO')
            )
        elif sec_type == 'IND':
            return Index(
                symbol=spec['symbol'],
                exchange=spec.get('exchange', 'CBOE'),
                currency=spec.get('currency', 'USD')
            )
        else:
            # Generic contract
            contract = Contract()
            for key, value in spec.items():
                setattr(contract, key, value)
            return contract

    @staticmethod
    def _ticker_to_dict(ticker: Any) -> Dict[str, Any]:
        """Convert Ticker to dictionary."""
        return {
            'symbol': ticker.contract.symbol,
            'bid': ticker.bid,
            'ask': ticker.ask,
            'last': ticker.last,
            'bid_size': ticker.bidSize,
            'ask_size': ticker.askSize,
            'last_size': ticker.lastSize,
            'volume': ticker.volume,
            'high': ticker.high,
            'low': ticker.low,
            'close': ticker.close,
            'time': ticker.time,
        }

    @staticmethod
    def _bar_to_dict(bar: Any) -> Dict[str, Any]:
        """Convert Bar to dictionary."""
        return {
            'date': bar.date,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
            'average': bar.average,
            'barCount': bar.barCount,
        }

    @staticmethod
    def _contract_details_to_dict(cd: Any) -> Dict[str, Any]:
        """Convert ContractDetails to dictionary."""
        return {
            'conId': cd.contract.conId,
            'symbol': cd.contract.symbol,
            'secType': cd.contract.secType,
            'exchange': cd.contract.exchange,
            'currency': cd.contract.currency,
            'longName': cd.longName,
            'minTick': cd.minTick,
            'priceMagnifier': cd.priceMagnifier,
            'validExchanges': cd.validExchanges,
        }

    def _mock_historical_bars(self, duration: str, barSize: str) -> List[Dict[str, Any]]:
        """Generate mock historical bars."""
        # Simple mock: 10 bars with random prices
        import random
        base_price = 100.0
        bars = []

        for i in range(10):
            price = base_price + random.uniform(-5, 5)
            bars.append({
                'date': (datetime.utcnow() - timedelta(minutes=10-i)).isoformat(),
                'open': price,
                'high': price + random.uniform(0, 2),
                'low': price - random.uniform(0, 2),
                'close': price + random.uniform(-1, 1),
                'volume': random.randint(1000, 10000),
                'average': price,
                'barCount': random.randint(10, 100),
            })

        return bars


# Example usage
async def example():
    """Example usage of IBKR market client."""
    config = {
        'host': '127.0.0.1',
        'port': 7497,  # Paper trading
        'client_id': 100,
        'readonly': True,
    }

    client = IBKRMarketClient(config)
    await client.connect()

    # Get contract details
    contract = {
        'symbol': 'AAPL',
        'secType': 'STK',
        'exchange': 'SMART',
        'currency': 'USD',
    }

    details = await client.get_contract_details(contract)
    print(f"Contract details: {details}")

    # Request historical data
    hist_bars = await client.request_hist(
        contract,
        duration='1 D',
        barSize='5 mins',
        whatToShow='TRADES'
    )
    print(f"Historical bars: {len(hist_bars)}")

    # Subscribe to real-time data
    def on_update(data):
        print(f"Real-time update: {data}")

    sub_id = await client.subscribe_rt(contract, callback=on_update)
    print(f"Subscribed: {sub_id}")

    # Wait a bit
    await asyncio.sleep(5)

    # Unsubscribe
    await client.unsubscribe_rt(sub_id)

    # Health check
    print("Health:", client.health())

    # Disconnect
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(example())
