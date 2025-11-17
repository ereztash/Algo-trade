# order_plane/app/orchestrator.py — Orchestrator for the order plane
import asyncio
import logging
from typing import Dict, Any
from order_plane.intents.risk_checks import PreTradeRisk
from order_plane.broker.throttling import exceeds_pov, downscale_qty
from order_plane.learning.lambda_online import update_lambda_online

logger = logging.getLogger(__name__)


async def run_order_plane(bus, ib_exec, logger_legacy, metrics, validator):
    """
    Orchestrator for the order plane: Risk, Execution, Reports, Learning.

    Flow:
    1. Consume order intents from order_intents topic
    2. Validate incoming intents
    3. Check pre-trade risk constraints
    4. Apply throttling (POV/ADV caps)
    5. Execute orders via IBKR
    6. Publish execution reports to exec_reports topic
    """
    logger.info("Order Plane started - consuming from 'order_intents' topic")
    logger.info("Will produce to 'exec_reports' topic")

    # In a real scenario, limits would be loaded from a config or a dynamic source
    limits = {"max_gross_exposure": 1_000_000, "max_net_exposure": 500_000}
    risk_checker = PreTradeRisk()

    # Spawn a parallel task to consume execution reports
    asyncio.create_task(consume_execution_reports(bus, logger_legacy, metrics, validator))

    async for intent_data in bus.consume("order_intents"):
        try:
            # 1. Validate incoming OrderIntent
            result = validator.validate_order_intent(intent_data, raise_on_error=False)

            if not result.is_valid:
                logger.error(f"Invalid order intent received: {result.errors}")
                metrics.inc("invalid_order_intents")
                continue

            intent = result.validated_data

            # 2. Check risk constraints from OrderIntent
            should_reject, reason = validator.should_reject_intent(intent)
            if should_reject:
                logger.warning(f"Rejecting intent {intent.intent_id}: {reason}")
                logger_legacy.warn("risk_reject", intent=intent.dict())
                metrics.inc("risk_rejects")
                continue

            # 3. Pre-trade risk validation
            intent_dict = intent.dict() if hasattr(intent, 'dict') else intent
            if not risk_checker.validate(intent_dict, limits):
                logger_legacy.warn("risk_reject", intent=intent_dict)
                metrics.inc("risk_rejects")
                continue

            # 4. Throttling (e.g., POV/ADV caps)
            if exceeds_pov(intent_dict, limits):
                intent_dict = downscale_qty(intent_dict, limits)
                logger_legacy.info("downscaled_qty", intent=intent_dict)

            # 5. Place order
            try:
                order_id = await ib_exec.place(intent_dict)
                logger.info(f"Placed order: {order_id} for {intent.symbol}")
                logger_legacy.info("placed_order", order_id=order_id, intent=intent_dict)
                metrics.inc("orders_placed")
                # Track the mapping of order_id to intent for later analysis
                # track(order_id, intent)
            except Exception as e:
                logger.error(f"Order placement failed: {e}")
                logger_legacy.error("place_order_failed", reason=str(e))
                metrics.inc("order_placement_errors")

        except Exception as e:
            logger.error(f"Error processing order intent: {e}", exc_info=True)
            metrics.inc("processing_errors")
            continue


async def consume_execution_reports(bus, logger_legacy, metrics, validator):
    """
    Consumes execution reports to feed the learning loop and metrics.

    Flow:
    1. Consume execution reports from exec_reports topic
    2. Validate reports
    3. Update learning models
    4. Track metrics
    """
    logger.info("Execution reports consumer started")

    async for rpt_data in bus.consume("exec_reports"):
        try:
            # Validate execution report
            result = validator.validate_execution_report(rpt_data, raise_on_error=False)

            if not result.is_valid:
                logger.error(f"Invalid execution report: {result.errors}")
                metrics.inc("invalid_exec_reports")
                continue

            rpt = result.validated_data

            logger.info(f"Received execution report: {rpt.report_id} for {rpt.symbol} - {rpt.status}")
            logger_legacy.info("received_exec_report", report=rpt.dict() if hasattr(rpt, 'dict') else rpt)

            # Update online learning models (e.g., transaction cost)
            update_lambda_online(rpt)

            # Observe metrics
            # latency = (now() - rpt.intent_ts_utc)
            # metrics.observe("fill_latency_ms", latency)
            status_key = rpt.status.lower() if hasattr(rpt, 'status') else 'unknown'
            metrics.inc(f"fill_status_{status_key}")

        except Exception as e:
            logger.error(f"Error processing execution report: {e}", exc_info=True)
            metrics.inc("exec_report_errors")
            continue
