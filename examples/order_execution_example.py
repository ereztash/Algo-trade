"""
End-to-End Order Execution Example.

This example demonstrates the complete flow of order execution from
OrderIntent to ExecutionReport using the IBKRExecClient.

Flow:
    1. Create OrderIntent (from Strategy Plane)
    2. Initialize and connect IBKRExecClient
    3. Place order via place()
    4. Poll for execution reports
    5. Handle ExecutionReport (send to Strategy Plane)

Usage:
    # With real IBKR connection:
    python examples/order_execution_example.py --live

    # With mock IBKR (for testing):
    python examples/order_execution_example.py --mock
"""

import asyncio
import logging
from datetime import datetime
from uuid import uuid4

from order_plane.broker.ibkr_exec_client import IBKRExecClient
from contracts.validators import OrderIntent, ExecutionReport


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_market_order():
    """Example: Place a MARKET order and wait for fill."""
    logger.info("=" * 60)
    logger.info("Example 1: MARKET Order Execution")
    logger.info("=" * 60)

    # 1. Create OrderIntent (normally comes from Strategy Plane via Kafka)
    order_intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='AAPL',
        direction='BUY',
        quantity=100,
        order_type='MARKET',
        timestamp=datetime.utcnow(),
        strategy_id='COMPOSITE',
        time_in_force='DAY',
        urgency='NORMAL',
    )

    logger.info(f"Created OrderIntent: {order_intent.intent_id}")
    logger.info(f"  Symbol: {order_intent.symbol}")
    logger.info(f"  Direction: {order_intent.direction}")
    logger.info(f"  Quantity: {order_intent.quantity}")
    logger.info(f"  Order Type: {order_intent.order_type}")

    # 2. Initialize IBKRExecClient
    config = {
        'host': '127.0.0.1',
        'port': 7497,  # 7497 = paper trading, 7496 = live trading
        'client_id': 1,
        'account': None,  # Optional: specify IBKR account
    }

    client = IBKRExecClient(config)

    try:
        # 3. Connect to IBKR
        logger.info("Connecting to IBKR...")
        await client.connect()
        logger.info("✅ Connected to IBKR")

        # 4. Place order
        logger.info("Placing order...")
        order_id = await client.place(order_intent)
        logger.info(f"✅ Order placed: order_id={order_id}")

        # 5. Poll for execution reports
        logger.info("Polling for execution reports...")

        max_polls = 30  # Poll for 30 seconds max
        poll_interval = 1.0  # Poll every second

        for i in range(max_polls):
            await asyncio.sleep(poll_interval)

            reports = await client.poll_reports()

            for report in reports:
                logger.info(f"📊 ExecutionReport received:")
                logger.info(f"  Report ID: {report.report_id}")
                logger.info(f"  Order ID: {report.order_id}")
                logger.info(f"  Status: {report.status}")
                logger.info(f"  Filled Quantity: {report.filled_quantity}/{report.requested_quantity}")
                logger.info(f"  Average Fill Price: ${report.average_fill_price}")
                logger.info(f"  Commission: ${report.commission}")

                if report.latency_metrics:
                    logger.info(f"  Latency Metrics:")
                    logger.info(f"    Intent → Submit: {report.latency_metrics.intent_to_submit_ms}ms")
                    logger.info(f"    Submit → Ack: {report.latency_metrics.submit_to_ack_ms}ms")
                    logger.info(f"    Total: {report.latency_metrics.total_latency_ms}ms")

                # In real system: publish report to Kafka (exec_reports topic)
                # await kafka_producer.send('exec_reports', report.dict())

                if report.status == 'FILLED':
                    logger.info("✅ Order fully filled!")
                    return report

        logger.warning("⚠️ Order not filled within timeout")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise

    finally:
        # 6. Disconnect
        await client.disconnect()
        logger.info("Disconnected from IBKR")


async def example_limit_order():
    """Example: Place a LIMIT order."""
    logger.info("=" * 60)
    logger.info("Example 2: LIMIT Order Execution")
    logger.info("=" * 60)

    # Create LIMIT order intent
    order_intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='TSLA',
        direction='SELL',
        quantity=50,
        order_type='LIMIT',
        limit_price=245.50,  # Required for LIMIT orders
        timestamp=datetime.utcnow(),
        strategy_id='OFI',
        time_in_force='GTC',  # Good 'Til Cancelled
        urgency='HIGH',
    )

    logger.info(f"Created LIMIT OrderIntent: {order_intent.intent_id}")
    logger.info(f"  Symbol: {order_intent.symbol}")
    logger.info(f"  Direction: {order_intent.direction}")
    logger.info(f"  Quantity: {order_intent.quantity}")
    logger.info(f"  Limit Price: ${order_intent.limit_price}")

    config = {
        'host': '127.0.0.1',
        'port': 7497,
        'client_id': 2,  # Different client ID
    }

    client = IBKRExecClient(config)

    try:
        await client.connect()
        logger.info("✅ Connected to IBKR")

        order_id = await client.place(order_intent)
        logger.info(f"✅ LIMIT order placed: order_id={order_id}")

        # Poll for a few seconds to see if acknowledged
        for i in range(5):
            await asyncio.sleep(1.0)
            reports = await client.poll_reports()

            for report in reports:
                logger.info(f"📊 Status: {report.status}")

                if report.status in ['FILLED', 'PARTIAL_FILL']:
                    logger.info(f"✅ Order filled: {report.filled_quantity} shares at ${report.average_fill_price}")

        logger.info("Note: LIMIT orders may take time to fill or may not fill if price not reached")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise

    finally:
        await client.disconnect()


async def example_order_cancellation():
    """Example: Place and cancel an order."""
    logger.info("=" * 60)
    logger.info("Example 3: Order Cancellation")
    logger.info("=" * 60)

    # Create order intent
    order_intent = OrderIntent(
        event_type='order_intent',
        intent_id=str(uuid4()),
        symbol='SPY',
        direction='BUY',
        quantity=100,
        order_type='LIMIT',
        limit_price=450.00,  # Set high price so it won't fill immediately
        timestamp=datetime.utcnow(),
        strategy_id='VRP',
        time_in_force='DAY',
    )

    logger.info(f"Created OrderIntent: {order_intent.intent_id}")

    config = {
        'host': '127.0.0.1',
        'port': 7497,
        'client_id': 3,
    }

    client = IBKRExecClient(config)

    try:
        await client.connect()
        logger.info("✅ Connected to IBKR")

        # Place order
        order_id = await client.place(order_intent)
        logger.info(f"✅ Order placed: order_id={order_id}")

        # Wait a bit
        await asyncio.sleep(2.0)

        # Cancel order
        logger.info(f"Cancelling order {order_id}...")
        success = await client.cancel(order_id)

        if success:
            logger.info("✅ Order cancelled successfully")
        else:
            logger.warning("⚠️ Order cancellation failed")

        # Check status
        await asyncio.sleep(1.0)
        reports = await client.poll_reports()

        for report in reports:
            logger.info(f"📊 Final status: {report.status}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise

    finally:
        await client.disconnect()


async def example_multiple_orders():
    """Example: Place multiple orders concurrently."""
    logger.info("=" * 60)
    logger.info("Example 4: Multiple Concurrent Orders")
    logger.info("=" * 60)

    # Create multiple order intents
    symbols = ['AAPL', 'TSLA', 'SPY', 'QQQ']
    order_intents = []

    for symbol in symbols:
        intent = OrderIntent(
            event_type='order_intent',
            intent_id=str(uuid4()),
            symbol=symbol,
            direction='BUY',
            quantity=10,
            order_type='MARKET',
            timestamp=datetime.utcnow(),
            strategy_id='COMPOSITE',
            time_in_force='DAY',
        )
        order_intents.append(intent)

    logger.info(f"Created {len(order_intents)} OrderIntents")

    config = {
        'host': '127.0.0.1',
        'port': 7497,
        'client_id': 4,
    }

    client = IBKRExecClient(config)

    try:
        await client.connect()
        logger.info("✅ Connected to IBKR")

        # Place all orders
        order_ids = []
        for intent in order_intents:
            order_id = await client.place(intent)
            order_ids.append(order_id)
            logger.info(f"✅ Placed order: {intent.symbol} (order_id={order_id})")

        # Poll for all fills
        filled_count = 0
        max_polls = 30

        for i in range(max_polls):
            await asyncio.sleep(1.0)

            reports = await client.poll_reports()

            for report in reports:
                if report.status == 'FILLED':
                    filled_count += 1
                    logger.info(
                        f"✅ {report.symbol} filled: {report.filled_quantity} @ ${report.average_fill_price}"
                    )

            if filled_count >= len(order_ids):
                logger.info(f"✅ All {filled_count} orders filled!")
                break

        # Health check
        health = client.health()
        logger.info(f"📊 Client health: {health}")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise

    finally:
        await client.disconnect()


async def main():
    """Run all examples."""
    import sys

    if '--mock' in sys.argv:
        logger.warning("=" * 60)
        logger.warning("MOCK MODE - Using mock IBKR (not real connection)")
        logger.warning("In mock mode, orders will be simulated")
        logger.warning("=" * 60)
        # In mock mode, you would use the IBKRMock class instead
        # from tests.e2e.ibkr_mock import IBKRMock

    elif '--live' in sys.argv:
        logger.warning("=" * 60)
        logger.warning("LIVE MODE - Connecting to real IBKR")
        logger.warning("Make sure TWS or IB Gateway is running!")
        logger.warning("=" * 60)

    else:
        logger.info("Usage:")
        logger.info("  python examples/order_execution_example.py --live   (real IBKR)")
        logger.info("  python examples/order_execution_example.py --mock   (mock IBKR)")
        return

    try:
        # Run examples
        await example_market_order()
        await asyncio.sleep(2)

        # Uncomment to run other examples:
        # await example_limit_order()
        # await asyncio.sleep(2)
        #
        # await example_order_cancellation()
        # await asyncio.sleep(2)
        #
        # await example_multiple_orders()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(main())
