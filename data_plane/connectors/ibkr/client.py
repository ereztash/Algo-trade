"""
IBKR Market Data Client for Data Plane

This module provides async interface for market data from IBKR.
It handles both real-time and historical data requests.

Author: Algo-trade Team
Updated: 2025-11-17
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
from collections import deque

from ib_insync import IB, Stock, Contract, util
from ib_insync.objects import BarData, TickData

from algo_trade.core.execution.IBKR_handler import IBKRConfig, IBKRConnectionError

logger = logging.getLogger(__name__)


class IBKRMarketClient:
    """
    Async market data client for IBKR.

    This client provides:
    - Real-time market data subscriptions
    - Historical data requests
    - Streaming data via async generators
    """

    def __init__(self, cfg: Dict[str, Any]):
        """
        Initialize IBKR Market Data Client.

        Args:
            cfg: Configuration dictionary with keys:
                - host: IBKR host (default: 127.0.0.1)
                - port: IBKR port (default: 7497 for paper)
                - client_id: Client ID (default: 2 for market data)
                - timeout: Connection timeout (default: 30)
        """
        self.cfg = cfg

        # Create IB instance (separate from execution client)
        self.ib = IB()
        self.ib.connectedEvent += self._on_connected
        self.ib.disconnectedEvent += self._on_disconnected

        # Configuration
        self.host = cfg.get('host', '127.0.0.1')
        self.port = cfg.get('port', 7497)
        self.client_id = cfg.get('client_id', 2)  # Different from exec client
        self.timeout = cfg.get('timeout', 30)

        # Real-time data buffer
        self._rt_buffer = deque(maxlen=1000)
        self._subscriptions = {}

        self._connected = False
        logger.info("IBKRMarketClient initialized")

    def _on_connected(self):
        """Callback when connection is established."""
        self._connected = True
        logger.info("✅ IBKRMarketClient connected")

    def _on_disconnected(self):
        """Callback when connection is lost."""
        self._connected = False
        logger.warning("⚠️ IBKRMarketClient disconnected")

    async def connect(self) -> bool:
        """
        Establish connection to IBKR for market data.

        Returns:
            bool: True if connected successfully

        Raises:
            IBKRConnectionError: If connection fails
        """
        if self.ib.isConnected():
            logger.info("IBKRMarketClient already connected")
            return True

        try:
            # Connect with different client ID than execution client
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.ib.connect,
                self.host,
                self.port,
                self.client_id,
                self.timeout
            )

            if self.ib.isConnected():
                logger.info("✅ IBKRMarketClient connected successfully")
                return True
            else:
                raise IBKRConnectionError("Failed to connect to IBKR")

        except Exception as e:
            logger.error(f"IBKRMarketClient connection failed: {e}")
            raise IBKRConnectionError(f"Connection failed: {e}")

    async def subscribe_rt(self, contract: Dict[str, Any], whatToShow: str = 'TRADES'):
        """
        Subscribe to real-time market data.

        Args:
            contract: Contract dictionary with keys:
                - symbol: Stock symbol
                - exchange: Exchange (default: 'SMART')
                - currency: Currency (default: 'USD')
            whatToShow: Data type ('TRADES', 'MIDPOINT', 'BID', 'ASK')

        Raises:
            IBKRConnectionError: If not connected
        """
        if not self.ib.isConnected():
            raise IBKRConnectionError("Not connected to IBKR")

        try:
            # Create IB contract
            ib_contract = Stock(
                contract.get('symbol'),
                contract.get('exchange', 'SMART'),
                contract.get('currency', 'USD')
            )

            # Qualify contract
            loop = asyncio.get_event_loop()
            qualified = await loop.run_in_executor(
                None,
                self.ib.qualifyContracts,
                ib_contract
            )

            if not qualified:
                raise ValueError(f"Could not qualify contract: {contract}")

            ib_contract = qualified[0]

            # Subscribe to real-time bars (5 second bars)
            bars = await loop.run_in_executor(
                None,
                self.ib.reqRealTimeBars,
                ib_contract,
                5,  # 5 second bars
                whatToShow,
                False  # useRTH
            )

            # Set up callback for new bars
            def on_bar_update(bars, hasNewBar):
                if hasNewBar:
                    bar = bars[-1]
                    self._rt_buffer.append({
                        'symbol': contract.get('symbol'),
                        'timestamp': bar.time.isoformat(),
                        'open': bar.open_,
                        'high': bar.high,
                        'low': bar.low,
                        'close': bar.close,
                        'volume': bar.volume,
                        'whatToShow': whatToShow
                    })

            bars.updateEvent += on_bar_update

            # Store subscription
            symbol = contract.get('symbol')
            self._subscriptions[symbol] = {
                'contract': ib_contract,
                'bars': bars,
                'whatToShow': whatToShow
            }

            logger.info(f"Subscribed to real-time data for {symbol}")

        except Exception as e:
            logger.error(f"Failed to subscribe to {contract}: {e}")
            raise

    async def request_hist(
        self,
        contract: Dict[str, Any],
        duration: str = '1 D',
        barSize: str = '1 min',
        whatToShow: str = 'TRADES',
        useRTH: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Request historical market data.

        Args:
            contract: Contract dictionary with keys:
                - symbol: Stock symbol
                - exchange: Exchange (default: 'SMART')
                - currency: Currency (default: 'USD')
            duration: Duration string (e.g., '1 D', '1 W', '1 M')
            barSize: Bar size (e.g., '1 min', '5 mins', '1 hour', '1 day')
            whatToShow: Data type ('TRADES', 'MIDPOINT', 'BID', 'ASK')
            useRTH: Use regular trading hours only

        Returns:
            List of historical bars

        Raises:
            IBKRConnectionError: If not connected
        """
        if not self.ib.isConnected():
            raise IBKRConnectionError("Not connected to IBKR")

        try:
            # Create IB contract
            ib_contract = Stock(
                contract.get('symbol'),
                contract.get('exchange', 'SMART'),
                contract.get('currency', 'USD')
            )

            # Qualify contract
            loop = asyncio.get_event_loop()
            qualified = await loop.run_in_executor(
                None,
                self.ib.qualifyContracts,
                ib_contract
            )

            if not qualified:
                raise ValueError(f"Could not qualify contract: {contract}")

            ib_contract = qualified[0]

            # Request historical data
            bars = await loop.run_in_executor(
                None,
                self.ib.reqHistoricalData,
                ib_contract,
                '',  # endDateTime (empty = now)
                duration,
                barSize,
                whatToShow,
                useRTH,
                1  # formatDate (1 = yyyyMMdd HH:mm:ss)
            )

            # Convert to dict format
            result = []
            for bar in bars:
                result.append({
                    'symbol': contract.get('symbol'),
                    'timestamp': bar.date.isoformat() if hasattr(bar.date, 'isoformat') else str(bar.date),
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                    'average': bar.average,
                    'barCount': bar.barCount
                })

            logger.info(f"Retrieved {len(result)} historical bars for {contract.get('symbol')}")
            return result

        except Exception as e:
            logger.error(f"Failed to request historical data for {contract}: {e}")
            raise

    async def rt_stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Async generator for real-time data stream.

        Yields:
            Dict with real-time bar data

        Example:
            async for bar in client.rt_stream():
                print(bar)
        """
        while True:
            if self._rt_buffer:
                yield self._rt_buffer.popleft()
            else:
                # Wait a bit if buffer is empty
                await asyncio.sleep(0.1)

    def health(self) -> Dict[str, Any]:
        """
        Check health status.

        Returns:
            Dict with health information
        """
        return {
            'connected': self.ib.isConnected(),
            'session': 'market',
            'subscriptions': len(self._subscriptions),
            'buffer_size': len(self._rt_buffer),
            'host': self.host,
            'port': self.port,
            'client_id': self.client_id
        }

    async def disconnect(self):
        """Disconnect from IBKR."""
        try:
            # Cancel all subscriptions
            for symbol, sub in self._subscriptions.items():
                try:
                    self.ib.cancelRealTimeBars(sub['bars'])
                except:
                    pass

            self._subscriptions.clear()
            self._rt_buffer.clear()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.ib.disconnect)
            logger.info("IBKRMarketClient disconnected")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")


# Example usage
async def main():
    """Example usage of IBKRMarketClient."""

    # Configuration
    cfg = {
        'host': '127.0.0.1',
        'port': 7497,
        'client_id': 2
    }

    client = IBKRMarketClient(cfg)

    try:
        # Connect
        await client.connect()

        # Subscribe to real-time data
        contract = {'symbol': 'SPY'}
        await client.subscribe_rt(contract, 'TRADES')

        # Request historical data
        hist_data = await client.request_hist(
            contract,
            duration='1 D',
            barSize='1 min',
            whatToShow='TRADES'
        )

        print(f"Retrieved {len(hist_data)} historical bars")
        print(f"Latest bar: {hist_data[-1]}")

        # Stream real-time data for 30 seconds
        print("\nStreaming real-time data for 30 seconds...")
        timeout = asyncio.create_task(asyncio.sleep(30))
        stream = client.rt_stream()

        while not timeout.done():
            try:
                bar = await asyncio.wait_for(
                    stream.__anext__(),
                    timeout=1.0
                )
                print(f"RT Bar: {bar['symbol']} @ {bar['close']}")
            except asyncio.TimeoutError:
                continue

        # Health check
        health = client.health()
        print(f"\nHealth: {health}")

    except Exception as e:
        logger.error(f"Error: {e}")

    finally:
        await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
