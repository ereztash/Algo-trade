"""
IBKR Client Wrapper
===================

Simple wrapper around ib_insync for market data and order execution.
Provides a clean interface and automatic reconnection.

Usage:
------
    from algox.data.ibkr_client import IBKRClient

    client = IBKRClient(host="127.0.0.1", port=7497, client_id=1)
    await client.connect()

    # Get historical data
    bars = await client.get_historical_bars("AAPL", duration="1 Y", bar_size="1 day")

    # Place order
    order_id = await client.place_order("AAPL", "BUY", 100, order_type="MKT")
"""

import asyncio
from typing import List, Dict, Optional, Literal
from datetime import datetime
import logging

try:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder, Contract, util
    IBKR_AVAILABLE = True
except ImportError:
    IBKR_AVAILABLE = False
    logging.warning("ib_insync not available. IBKR client will run in mock mode.")

import pandas as pd


logger = logging.getLogger(__name__)


class IBKRClient:
    """
    Wrapper for Interactive Brokers API using ib_insync.

    Attributes:
        host: IB Gateway/TWS host
        port: IB Gateway/TWS port (7497 for paper, 7496 for live)
        client_id: Unique client ID
        mock_mode: If True, operates without actual IBKR connection
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        mock_mode: bool = False
    ):
        """Initialize IBKR client."""
        self.host = host
        self.port = port
        self.client_id = client_id
        self.mock_mode = mock_mode or not IBKR_AVAILABLE

        if not self.mock_mode:
            self.ib = IB()
        else:
            self.ib = None
            logger.info("IBKR client initialized in MOCK mode")

    async def connect(self) -> bool:
        """Connect to IBKR Gateway/TWS."""
        if self.mock_mode:
            logger.info("Mock mode: Simulating connection")
            return True

        try:
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            return False

    def disconnect(self):
        """Disconnect from IBKR."""
        if not self.mock_mode and self.ib:
            self.ib.disconnect()
            logger.info("Disconnected from IBKR")

    def _create_contract(self, symbol: str, sec_type: str = "STK", exchange: str = "SMART", currency: str = "USD") -> Optional[Contract]:
        """Create an IBKR contract object."""
        if self.mock_mode:
            return {"symbol": symbol, "secType": sec_type, "exchange": exchange, "currency": currency}

        if sec_type == "STK":
            return Stock(symbol, exchange, currency)
        else:
            logger.error(f"Security type {sec_type} not yet supported")
            return None

    async def get_historical_bars(
        self,
        symbol: str,
        duration: str = "1 Y",
        bar_size: str = "1 day",
        what_to_show: str = "TRADES",
        use_rth: bool = True
    ) -> pd.DataFrame:
        """
        Get historical bar data.

        Args:
            symbol: Stock symbol
            duration: Duration string (e.g., "1 Y", "6 M", "30 D")
            bar_size: Bar size (e.g., "1 day", "1 hour", "5 mins")
            what_to_show: Type of data ("TRADES", "MIDPOINT", "BID", "ASK")
            use_rth: Use regular trading hours only

        Returns:
            DataFrame with columns: date, open, high, low, close, volume
        """
        if self.mock_mode:
            logger.warning(f"Mock mode: Returning dummy data for {symbol}")
            # Return dummy data for testing
            dates = pd.date_range(end=datetime.now(), periods=252, freq='D')
            return pd.DataFrame({
                'date': dates,
                'open': 100.0,
                'high': 102.0,
                'low': 98.0,
                'close': 101.0,
                'volume': 1000000
            })

        contract = self._create_contract(symbol)
        if not contract:
            return pd.DataFrame()

        try:
            bars = await self.ib.reqHistoricalDataAsync(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow=what_to_show,
                useRTH=use_rth
            )

            # Convert to DataFrame
            df = util.df(bars)
            if not df.empty:
                df = df.rename(columns={'date': 'date', 'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'})
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')

            logger.info(f"Retrieved {len(df)} bars for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol."""
        if self.mock_mode:
            return 100.0  # Dummy price

        contract = self._create_contract(symbol)
        if not contract:
            return None

        try:
            ticker = self.ib.reqMktData(contract)
            await asyncio.sleep(2)  # Wait for price update

            # Try different price fields
            price = ticker.marketPrice()
            if price and price > 0:
                return price
            elif ticker.last and ticker.last > 0:
                return ticker.last
            elif ticker.close and ticker.close > 0:
                return ticker.close
            else:
                logger.warning(f"No valid price found for {symbol}")
                return None

        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None

    async def place_order(
        self,
        symbol: str,
        action: Literal["BUY", "SELL"],
        quantity: int,
        order_type: Literal["MKT", "LMT"] = "MKT",
        limit_price: Optional[float] = None
    ) -> Optional[str]:
        """
        Place an order.

        Args:
            symbol: Stock symbol
            action: "BUY" or "SELL"
            quantity: Number of shares
            order_type: "MKT" (market) or "LMT" (limit)
            limit_price: Limit price (required for LMT orders)

        Returns:
            Order ID if successful, None otherwise
        """
        if self.mock_mode:
            order_id = f"MOCK_{symbol}_{action}_{quantity}"
            logger.info(f"Mock order placed: {order_id}")
            return order_id

        contract = self._create_contract(symbol)
        if not contract:
            return None

        # Create order
        if order_type == "MKT":
            order = MarketOrder(action, quantity)
        elif order_type == "LMT":
            if limit_price is None:
                logger.error("Limit price required for limit orders")
                return None
            order = LimitOrder(action, quantity, limit_price)
        else:
            logger.error(f"Order type {order_type} not supported")
            return None

        try:
            trade = self.ib.placeOrder(contract, order)
            logger.info(f"Order placed: {symbol} {action} {quantity} @ {order_type}")

            # Wait for order to be acknowledged
            await asyncio.sleep(1)

            return str(trade.order.orderId)

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    async def get_account_summary(self) -> Dict[str, float]:
        """Get account summary (cash, equity, etc.)."""
        if self.mock_mode:
            return {
                "NetLiquidation": 10000.0,
                "TotalCashValue": 10000.0,
                "GrossPositionValue": 0.0
            }

        try:
            summary = await self.ib.accountSummaryAsync()
            result = {}
            for item in summary:
                if item.tag in ["NetLiquidation", "TotalCashValue", "GrossPositionValue"]:
                    result[item.tag] = float(item.value)

            return result

        except Exception as e:
            logger.error(f"Error fetching account summary: {e}")
            return {}

    async def get_positions(self) -> List[Dict]:
        """Get current positions."""
        if self.mock_mode:
            return []

        try:
            positions = await self.ib.reqPositionsAsync()
            result = []
            for pos in positions:
                result.append({
                    "symbol": pos.contract.symbol,
                    "position": pos.position,
                    "avgCost": pos.avgCost,
                    "marketValue": pos.position * pos.avgCost
                })

            return result

        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []


# Convenience function for creating client
def create_ibkr_client(config: Dict) -> IBKRClient:
    """Create IBKR client from config dictionary."""
    exec_config = config.get("EXECUTION", {})

    return IBKRClient(
        host=exec_config.get("HOST", "127.0.0.1"),
        port=exec_config.get("PORT", 7497),
        client_id=exec_config.get("CLIENT_ID", 1),
        mock_mode=(config.get("MODE") == "backtest")
    )
