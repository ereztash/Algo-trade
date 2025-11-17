# order_plane/app/orchestrator.py — Orchestrator for the order plane with timeout detection
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from dataclasses import dataclass

from order_plane.intents.risk_checks import PreTradeRisk
from order_plane.broker.throttling import exceeds_pov, downscale_qty
from order_plane.learning.lambda_online import update_lambda_online


@dataclass
class OrderTracking:
    """Track order lifecycle for timeout detection."""
    intent_id: str
    order_id: Optional[str]
    symbol: str
    quantity: float
    submitted_at: datetime
    acknowledged_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    status: str = 'PENDING'  # PENDING, SUBMITTED, ACKNOWLEDGED, FILLED, TIMEOUT, ERROR


class OrderLifecycleMonitor:
    """
    Monitor order lifecycle and detect timeouts.

    Timeout thresholds:
    - Submission timeout: 30s (intent -> order placed)
    - Acknowledgment timeout: 30s (submitted -> broker ack)
    - Fill timeout (MARKET): 60s (ack -> filled)
    - Fill timeout (LIMIT DAY): Until market close
    """

    def __init__(
        self,
        submission_timeout_s: float = 30.0,
        ack_timeout_s: float = 30.0,
        market_fill_timeout_s: float = 60.0,
    ):
        self.submission_timeout_s = submission_timeout_s
        self.ack_timeout_s = ack_timeout_s
        self.market_fill_timeout_s = market_fill_timeout_s

        # Track orders: intent_id -> OrderTracking
        self._tracked_orders: Dict[str, OrderTracking] = {}

    def track_intent(self, intent):
        """Start tracking an order intent."""
        tracking = OrderTracking(
            intent_id=intent.intent_id,
            order_id=None,
            symbol=intent.symbol,
            quantity=intent.quantity,
            submitted_at=datetime.now(timezone.utc),
            status='PENDING',
        )
        self._tracked_orders[intent.intent_id] = tracking

    def mark_submitted(self, intent_id: str, order_id: str):
        """Mark order as submitted to broker."""
        if intent_id in self._tracked_orders:
            tracking = self._tracked_orders[intent_id]
            tracking.order_id = order_id
            tracking.status = 'SUBMITTED'

    def mark_acknowledged(self, intent_id: str):
        """Mark order as acknowledged by broker."""
        if intent_id in self._tracked_orders:
            tracking = self._tracked_orders[intent_id]
            tracking.acknowledged_at = datetime.now(timezone.utc)
            tracking.status = 'ACKNOWLEDGED'

    def mark_filled(self, intent_id: str):
        """Mark order as filled."""
        if intent_id in self._tracked_orders:
            tracking = self._tracked_orders[intent_id]
            tracking.filled_at = datetime.now(timezone.utc)
            tracking.status = 'FILLED'
            # Clean up after fill
            del self._tracked_orders[intent_id]

    def check_timeouts(self, logger, metrics) -> list:
        """
        Check for timed-out orders.

        Returns:
            List of (intent_id, timeout_type) tuples for timed-out orders
        """
        now = datetime.now(timezone.utc)
        timeouts = []

        for intent_id, tracking in list(self._tracked_orders.items()):
            # Check submission timeout
            if tracking.status == 'PENDING':
                elapsed = (now - tracking.submitted_at).total_seconds()
                if elapsed > self.submission_timeout_s:
                    logger.error(
                        "order_submission_timeout",
                        intent_id=intent_id,
                        symbol=tracking.symbol,
                        elapsed_s=elapsed,
                    )
                    metrics.inc("order_timeout_submission")
                    tracking.status = 'TIMEOUT'
                    timeouts.append((intent_id, 'SUBMISSION_TIMEOUT'))

            # Check acknowledgment timeout
            elif tracking.status == 'SUBMITTED':
                elapsed = (now - tracking.submitted_at).total_seconds()
                if elapsed > self.ack_timeout_s:
                    logger.error(
                        "order_acknowledgment_timeout",
                        intent_id=intent_id,
                        order_id=tracking.order_id,
                        symbol=tracking.symbol,
                        elapsed_s=elapsed,
                    )
                    metrics.inc("order_timeout_acknowledgment")
                    tracking.status = 'TIMEOUT'
                    timeouts.append((intent_id, 'ACK_TIMEOUT'))

            # Check fill timeout (for MARKET orders)
            elif tracking.status == 'ACKNOWLEDGED' and tracking.acknowledged_at:
                elapsed = (now - tracking.acknowledged_at).total_seconds()
                if elapsed > self.market_fill_timeout_s:
                    logger.error(
                        "order_fill_timeout",
                        intent_id=intent_id,
                        order_id=tracking.order_id,
                        symbol=tracking.symbol,
                        elapsed_s=elapsed,
                    )
                    metrics.inc("order_timeout_fill")
                    tracking.status = 'TIMEOUT'
                    timeouts.append((intent_id, 'FILL_TIMEOUT'))

        return timeouts


async def run_order_plane(bus, ib_exec, logger, metrics):
    """
    Orchestrator for the order plane: Risk, Execution, Reports, Learning, Timeouts.
    """
    # In a real scenario, limits would be loaded from a config or a dynamic source
    limits = {"max_gross_exposure": 1_000_000, "max_net_exposure": 500_000}
    risk_checker = PreTradeRisk()

    # Initialize lifecycle monitor
    lifecycle_monitor = OrderLifecycleMonitor(
        submission_timeout_s=30.0,
        ack_timeout_s=30.0,
        market_fill_timeout_s=60.0,
    )

    # Spawn parallel tasks
    asyncio.create_task(consume_execution_reports(bus, logger, metrics, lifecycle_monitor))
    asyncio.create_task(timeout_watchdog(lifecycle_monitor, logger, metrics, interval_s=10.0))

    async for intent in bus.consume("order_intents"):
        # Track intent for timeout detection
        lifecycle_monitor.track_intent(intent)

        # 1. Pre-trade risk validation
        if not risk_checker.validate(intent, limits):
            logger.warn("risk_reject", intent=intent.dict())
            metrics.inc("order_risk_rejected")
            continue

        # 2. Throttling (e.g., POV/ADV caps)
        if exceeds_pov(intent, limits):
            intent = downscale_qty(intent, limits)
            logger.info("downscaled_qty", intent=intent.dict())
            metrics.inc("order_downscaled")

        # 3. Place order
        try:
            order_id = await ib_exec.place(intent)
            logger.info("placed_order", order_id=order_id, intent=intent.dict())
            metrics.inc("order_placed")

            # Mark as submitted
            lifecycle_monitor.mark_submitted(intent.intent_id, order_id)

        except ValueError as e:
            # Duplicate order detection
            if "DUPLICATE ORDER" in str(e):
                logger.error("duplicate_order_rejected", intent_id=intent.intent_id, error=str(e))
                metrics.inc("order_duplicate_rejected")
            else:
                logger.error("place_order_validation_failed", intent_id=intent.intent_id, error=str(e))
                metrics.inc("order_validation_failed")

        except Exception as e:
            logger.error("place_order_failed", intent_id=intent.intent_id, reason=str(e))
            metrics.inc("order_placement_failed")


async def consume_execution_reports(bus, logger, metrics, lifecycle_monitor: OrderLifecycleMonitor):
    """
    Consumes execution reports to feed the learning loop and metrics.
    """
    async for rpt in bus.consume("exec_reports"):
        logger.info("received_exec_report", report=rpt.dict())

        # Update lifecycle tracking
        if rpt.status == 'ACKNOWLEDGED':
            lifecycle_monitor.mark_acknowledged(rpt.intent_id)
        elif rpt.status == 'FILLED':
            lifecycle_monitor.mark_filled(rpt.intent_id)

        # Update online learning models (e.g., transaction cost)
        update_lambda_online(rpt)

        # Observe latency metrics
        if hasattr(rpt, 'latency_metrics') and rpt.latency_metrics:
            lm = rpt.latency_metrics
            if lm.intent_to_submit_ms:
                metrics.observe("order_latency_submit_ms", lm.intent_to_submit_ms)
            if lm.submit_to_ack_ms:
                metrics.observe("order_latency_ack_ms", lm.submit_to_ack_ms)
            if lm.ack_to_fill_ms:
                metrics.observe("order_latency_fill_ms", lm.ack_to_fill_ms)

        # Track fill status
        metrics.inc(f"fill_status_{rpt.status.lower()}")

        # Track slippage if available
        if hasattr(rpt, 'slippage_bps') and rpt.slippage_bps:
            metrics.observe("order_slippage_bps", rpt.slippage_bps)


async def timeout_watchdog(
    lifecycle_monitor: OrderLifecycleMonitor,
    logger,
    metrics,
    interval_s: float = 10.0,
):
    """
    Periodic watchdog to check for timed-out orders.

    Args:
        lifecycle_monitor: Order lifecycle monitor
        logger: Structured logger
        metrics: Metrics collector
        interval_s: Check interval in seconds
    """
    logger.info("timeout_watchdog_started", interval_s=interval_s)

    while True:
        await asyncio.sleep(interval_s)

        try:
            timeouts = lifecycle_monitor.check_timeouts(logger, metrics)

            if timeouts:
                logger.warning(
                    "orders_timed_out",
                    count=len(timeouts),
                    timeouts=[{"intent_id": iid, "type": tt} for iid, tt in timeouts],
                )

                # TODO: Take action on timeouts:
                # - Alert operations
                # - Attempt to cancel stuck orders
                # - Generate TIMEOUT execution reports

        except Exception as e:
            logger.error("timeout_watchdog_error", error=str(e))
            metrics.inc("timeout_watchdog_errors")
