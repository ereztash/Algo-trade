# order_plane/app/orchestrator.py — Orchestrator for the order plane
import asyncio
from order_plane.intents.risk_checks import PreTradeRisk
from order_plane.broker.throttling import exceeds_pov, downscale_qty
from order_plane.learning.lambda_online import update_lambda_online

async def run_order_plane(bus, ib_exec, logger, metrics):
    """
    Orchestrator for the order plane: Risk, Execution, Reports, Learning.
    """
    # In a real scenario, limits would be loaded from a config or a dynamic source
    limits = {"max_gross_exposure": 1_000_000, "max_net_exposure": 500_000}
    risk_checker = PreTradeRisk()

    # Spawn a parallel task to consume execution reports
    asyncio.create_task(consume_execution_reports(bus, logger, metrics))

    async for intent in bus.consume("order_intents"):
        # 1. Pre-trade risk validation
        if not risk_checker.validate(intent, limits):
            logger.warn("risk_reject", intent=intent.dict())
            continue

        # 2. Throttling (e.g., POV/ADV caps)
        if exceeds_pov(intent, limits):
            intent = downscale_qty(intent, limits)
            logger.info("downscaled_qty", intent=intent.dict())

        # 3. Place order
        try:
            order_id = await ib_exec.place(intent)
            logger.info("placed_order", order_id=order_id, intent=intent.dict())
            # Track the mapping of order_id to intent for later analysis
            # track(order_id, intent)
        except Exception as e:
            logger.error("place_order_failed", reason=str(e))


async def consume_execution_reports(bus, logger, metrics):
    """
    Consumes execution reports to feed the learning loop and metrics.
    """
    async for rpt in bus.consume("exec_reports"):
        logger.info("received_exec_report", report=rpt.dict())
        
        # Update online learning models (e.g., transaction cost)
        update_lambda_online(rpt)
        
        # Observe metrics
        # latency = (now() - rpt.intent_ts_utc)
        # metrics.observe("fill_latency_ms", latency)
        metrics.inc(f"fill_status_{rpt.status.lower()}")
