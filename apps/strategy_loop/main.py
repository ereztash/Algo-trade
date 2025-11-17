# apps/strategy_loop/main.py
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def strategy_loop(bus, validator):
    """
    External strategy loop that consumes market data and produces OrderIntents.

    Flow:
    1. Consume validated market events from market_events topic
    2. Validate incoming events
    3. Build signals and context
    4. Generate order intents
    5. Validate and publish order intents to order_intents topic

    This runs independently of the data and order planes.
    """
    logger.info("Strategy Plane started - consuming from 'market_events' topic")
    logger.info("Will produce to 'order_intents' topic")

    # Consume normalized market events
    async for market_event in bus.consume("market_events"):
        try:
            # Validate incoming market event
            result = validator.validate_market_event(market_event, raise_on_error=False)

            if not result.is_valid:
                logger.error(f"Invalid market event received: {result.errors}")
                continue

            validated_event = result.validated_data

            # In a real strategy, this would be a complex process:
            # 1. Update rolling window
            # window.update(validated_event)

            # 2. Build context and signals
            # context = build_context(window)
            # signals = build_signals(window, context)

            # 3. Orthogonalize and merge signals
            # mu_hat = merge_signals(signals)

            # 4. Solve QP for target weights
            # w_tgt = solve_qp(mu_hat, ...)

            # 5. Assemble and publish intents
            # intents = assemble_order_intents(w_prev, w_tgt, ...)
            # for intent_data in intents:
            #     # Validate order intent before publishing
            #     intent_result = validator.validate_order_intent(intent_data, raise_on_error=False)
            #     if intent_result.is_valid:
            #         validated_intent = intent_result.validated_data
            #         await bus.publish(
            #             "order_intents",
            #             validated_intent.dict(),
            #             key=validated_intent.symbol
            #         )
            #     else:
            #         logger.error(f"Invalid order intent: {intent_result.errors}")

            # Placeholder: Log event reception
            logger.debug(f"Strategy received market event: {validated_event.symbol if hasattr(validated_event, 'symbol') else 'unknown'}")

        except Exception as e:
            logger.error(f"Error in strategy loop: {e}", exc_info=True)
            continue


async def run_strategy(bus, validator):
    """
    Run the strategy plane with Kafka message bus and validator.

    Args:
        bus: KafkaAdapter instance
        validator: StrategyPlaneValidator instance
    """
    await strategy_loop(bus, validator)
