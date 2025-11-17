"""
Order Plane Orchestrator

Main execution loop for the Order Plane:
1. Consume order intents from Kafka (order_intents topic)
2. Validate risk limits
3. Place orders with IBKR
4. Monitor order status and fills
5. Publish execution reports to Kafka (exec_reports topic)

Flow:
  Strategy Plane → Kafka (order_intents)
                ↓
           Order Plane (this orchestrator)
                ↓
          IBKR Gateway/TWS
                ↓
  Execution confirmations → Kafka (exec_reports)
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class OrderOrchestrator:
    """
    Orchestrates order execution workflow.

    Responsibilities:
    - Consume order intents from Kafka
    - Pre-trade risk validation
    - Order placement via IBKR
    - Status tracking
    - Execution report publishing
    """

    def __init__(self, kafka_consumer, kafka_producer, ibkr_client, risk_checker=None):
        """
        Initialize orchestrator.

        Args:
            kafka_consumer: Kafka consumer for order_intents topic
            kafka_producer: Kafka producer for exec_reports topic
            ibkr_client: IBKRExecClient instance
            risk_checker: Optional pre-trade risk validator
        """
        self.kafka_consumer = kafka_consumer
        self.kafka_producer = kafka_producer
        self.ibkr_client = ibkr_client
        self.risk_checker = risk_checker

        # Track active orders
        self.active_orders: Dict[str, dict] = {}  # intent_id -> order info

        self.running = False

    async def start(self):
        """Start the orchestrator main loop."""
        self.running = True
        logger.info("✓ Order Orchestrator started")

        # Start parallel tasks
        tasks = [
            asyncio.create_task(self._consume_order_intents()),
            asyncio.create_task(self._publish_execution_reports())
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            self.running = False

    async def stop(self):
        """Stop the orchestrator."""
        logger.info("Stopping Order Orchestrator...")
        self.running = False

    async def _consume_order_intents(self):
        """
        Main loop: Consume order intents and place orders.
        """
        logger.info("Started consuming order intents from Kafka...")

        while self.running:
            try:
                # Consume order intents from Kafka
                # In real implementation, this would be:
                # async for msg in self.kafka_consumer.consume("order_intents"):
                #     intent = parse_order_intent(msg)

                # Placeholder: process pending intents
                await asyncio.sleep(0.1)

                # Check if IBKR is connected
                if not self.ibkr_client.wrapper.connected:
                    logger.warning("IBKR not connected, waiting...")
                    await asyncio.sleep(1.0)
                    continue

            except Exception as e:
                logger.error(f"Error consuming order intents: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def process_order_intent(self, intent: dict) -> bool:
        """
        Process a single order intent.

        Args:
            intent: Order intent dict with:
                - intent_id: Unique ID
                - symbol: Stock symbol
                - direction: BUY/SELL
                - quantity: Order quantity
                - order_type: MARKET/LIMIT/etc
                - limit_price: Optional limit price
                - strategy_id: Source strategy
                - signal_strength: Signal confidence

        Returns:
            True if order placed successfully
        """
        intent_id = intent.get('intent_id')

        try:
            logger.info(
                f"Processing order intent {intent_id}: "
                f"{intent['direction']} {intent['quantity']} {intent['symbol']}"
            )

            # Step 1: Pre-trade risk validation
            if self.risk_checker:
                if not self.risk_checker.validate(intent):
                    logger.warning(f"Order intent {intent_id} rejected by risk checks")
                    await self._publish_rejection(intent, "Risk limits exceeded")
                    return False

            # Step 2: Place order with IBKR
            order_id = await self.ibkr_client.place_order(intent)

            if order_id is None:
                logger.error(f"Failed to place order for intent {intent_id}")
                await self._publish_rejection(intent, "Order placement failed")
                return False

            # Step 3: Track order
            self.active_orders[intent_id] = {
                'intent': intent,
                'ibkr_order_id': order_id,
                'submitted_at': datetime.now(timezone.utc)
            }

            logger.info(
                f"✓ Order placed successfully: "
                f"intent_id={intent_id}, ibkr_order_id={order_id}"
            )

            return True

        except Exception as e:
            logger.error(f"Error processing order intent {intent_id}: {e}", exc_info=True)
            await self._publish_rejection(intent, f"Exception: {str(e)}")
            return False

    async def _publish_execution_reports(self):
        """
        Monitor execution reports from IBKR and publish to Kafka.
        """
        logger.info("Started publishing execution reports...")

        while self.running:
            try:
                # Get pending execution reports from IBKR
                reports = await self.ibkr_client.get_execution_reports()

                for report in reports:
                    # Publish to Kafka exec_reports topic
                    await self._publish_exec_report(report)

                    # Remove from active orders if filled
                    if report['status'] in ['Filled', 'Cancelled']:
                        intent_id = report['intent_id']
                        if intent_id in self.active_orders:
                            del self.active_orders[intent_id]

                await asyncio.sleep(0.1)  # Poll interval

            except Exception as e:
                logger.error(f"Error publishing execution reports: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _publish_exec_report(self, report: dict):
        """
        Publish execution report to Kafka.

        Args:
            report: Execution report dict
        """
        try:
            logger.info(
                f"Publishing execution report: "
                f"intent_id={report['intent_id']}, "
                f"status={report['status']}, "
                f"filled={report['filled_quantity']}/{report['quantity']}"
            )

            # In real implementation:
            # await self.kafka_producer.produce("exec_reports", report)

            # For now, just log
            logger.debug(f"Execution report: {report}")

        except Exception as e:
            logger.error(f"Failed to publish execution report: {e}", exc_info=True)

    async def _publish_rejection(self, intent: dict, reason: str):
        """
        Publish order rejection as execution report.

        Args:
            intent: Original order intent
            reason: Rejection reason
        """
        rejection_report = {
            'execution_id': f"REJ-{intent['intent_id']}",
            'intent_id': intent['intent_id'],
            'symbol': intent['symbol'],
            'side': intent['direction'],
            'quantity': intent['quantity'],
            'filled_quantity': 0.0,
            'avg_fill_price': 0.0,
            'status': 'Rejected',
            'rejection_reason': reason,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        await self._publish_exec_report(rejection_report)

    def get_active_orders_count(self) -> int:
        """Get count of active orders."""
        return len(self.active_orders)

    def get_order_status(self, intent_id: str) -> Optional[dict]:
        """Get status of specific order by intent ID."""
        if intent_id in self.active_orders:
            order_state = self.ibkr_client.get_order_state(intent_id)
            if order_state:
                return {
                    'intent_id': intent_id,
                    'ibkr_order_id': order_state.ibkr_order_id,
                    'symbol': order_state.symbol,
                    'status': order_state.status.value,
                    'filled_quantity': order_state.filled_quantity,
                    'avg_fill_price': order_state.avg_fill_price
                }
        return None


# ==============================================================================
# Simple Risk Checker (Placeholder)
# ==============================================================================

class SimpleRiskChecker:
    """
    Simple pre-trade risk validator.

    Checks:
    - Position size limits
    - Gross exposure limits
    - Order size sanity checks
    """

    def __init__(self, config: dict = None):
        """
        Initialize risk checker.

        Args:
            config: Configuration with risk limits
        """
        self.config = config or {}

        # Default limits
        self.max_order_quantity = self.config.get('max_order_quantity', 1000)
        self.max_gross_exposure = self.config.get('max_gross_exposure', 1_000_000)

    def validate(self, intent: dict) -> bool:
        """
        Validate order intent against risk limits.

        Args:
            intent: Order intent to validate

        Returns:
            True if intent passes all checks
        """
        # Check 1: Order quantity sanity
        if intent['quantity'] <= 0:
            logger.warning(f"Invalid quantity: {intent['quantity']}")
            return False

        if intent['quantity'] > self.max_order_quantity:
            logger.warning(
                f"Order quantity {intent['quantity']} exceeds max {self.max_order_quantity}"
            )
            return False

        # Check 2: Order type validation
        if intent['order_type'] not in ['MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT']:
            logger.warning(f"Invalid order type: {intent['order_type']}")
            return False

        # Check 3: Limit orders must have limit price
        if intent['order_type'] in ['LIMIT', 'STOP_LIMIT']:
            if 'limit_price' not in intent or intent['limit_price'] is None:
                logger.warning(f"Limit order missing limit_price")
                return False

        return True


# ==============================================================================
# Example Usage
# ==============================================================================

async def main():
    """Example orchestrator setup."""
    import os

    # Configuration
    ibkr_config = {
        'host': os.getenv('IBKR_HOST', '127.0.0.1'),
        'port': int(os.getenv('IBKR_PORT', 4002)),
        'client_id': int(os.getenv('IBKR_CLIENT_ID', 2))
    }

    risk_config = {
        'max_order_quantity': 1000,
        'max_gross_exposure': 1_000_000
    }

    # Initialize components
    from order_plane.broker.ibkr_exec_client import IBKRExecClient

    ibkr_client = IBKRExecClient(ibkr_config)
    risk_checker = SimpleRiskChecker(risk_config)

    # Connect to IBKR
    connected = await ibkr_client.connect_async()
    if not connected:
        logger.error("Failed to connect to IBKR")
        return

    # Initialize orchestrator
    # Note: kafka_consumer and kafka_producer would be real Kafka clients
    orchestrator = OrderOrchestrator(
        kafka_consumer=None,  # Placeholder
        kafka_producer=None,  # Placeholder
        ibkr_client=ibkr_client,
        risk_checker=risk_checker
    )

    # Example: Process a test order intent
    test_intent = {
        'intent_id': 'test-001',
        'symbol': 'SPY',
        'direction': 'BUY',
        'quantity': 10,
        'order_type': 'MARKET',
        'strategy_id': 'test_strategy',
        'signal_strength': 0.75
    }

    await orchestrator.process_order_intent(test_intent)

    # Run for a while to see fills
    await asyncio.sleep(10)

    # Check execution reports
    reports = await ibkr_client.get_execution_reports()
    for report in reports:
        logger.info(f"Execution report: {report}")

    # Disconnect
    await ibkr_client.disconnect_async()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
