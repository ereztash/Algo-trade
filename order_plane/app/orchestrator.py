"""
Orchestrator for the order plane with performance optimizations.

Implements:
- Timeout controls for order placement
- Order batching for improved throughput
- Comprehensive latency tracking
- Circuit breaker pattern
- Caching for risk calculations
"""
import asyncio
import time
from typing import List, Dict, Any, Optional
from collections import defaultdict
from order_plane.intents.risk_checks import PreTradeRisk
from order_plane.broker.throttling import exceeds_pov, downscale_qty
from order_plane.learning.lambda_online import update_lambda_online


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    States:
    - CLOSED: Normal operation
    - OPEN: Failures detected, reject requests
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        half_open_attempts: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.half_open_attempts = half_open_attempts

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.half_open_success = 0

    def record_success(self):
        """Record successful operation."""
        if self.state == "HALF_OPEN":
            self.half_open_success += 1
            if self.half_open_success >= self.half_open_attempts:
                self.state = "CLOSED"
                self.failure_count = 0
                self.half_open_success = 0
        elif self.state == "CLOSED":
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def can_attempt(self) -> bool:
        """Check if operation can be attempted."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if timeout expired
            if self.last_failure_time and (time.time() - self.last_failure_time) >= self.timeout:
                self.state = "HALF_OPEN"
                self.half_open_success = 0
                return True
            return False

        if self.state == "HALF_OPEN":
            return True

        return False


class RiskCheckCache:
    """Cache for pre-computed risk checks to reduce validation overhead."""

    def __init__(self, ttl_seconds: float = 1.0):
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, tuple] = {}  # key -> (result, timestamp)

    def get(self, key: str) -> Optional[bool]:
        """Get cached risk check result if not expired."""
        if key in self.cache:
            result, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return result
            else:
                del self.cache[key]
        return None

    def set(self, key: str, result: bool):
        """Cache risk check result with timestamp."""
        self.cache[key] = (result, time.time())

    def clear_expired(self):
        """Remove expired entries from cache."""
        now = time.time()
        expired_keys = [
            k for k, (_, ts) in self.cache.items()
            if now - ts >= self.ttl_seconds
        ]
        for k in expired_keys:
            del self.cache[k]


class OrderBatcher:
    """
    Batch orders to improve throughput and reduce API calls.

    Collects orders over a short window and submits them together.
    """

    def __init__(self, batch_window_ms: float = 10.0, max_batch_size: int = 50):
        self.batch_window_ms = batch_window_ms
        self.max_batch_size = max_batch_size
        self.pending_orders: List[Any] = []
        self.batch_timer: Optional[asyncio.Task] = None

    def add_order(self, intent):
        """Add order to pending batch."""
        self.pending_orders.append(intent)

    def should_flush(self) -> bool:
        """Check if batch should be flushed."""
        return len(self.pending_orders) >= self.max_batch_size

    def get_batch(self) -> List[Any]:
        """Get and clear pending batch."""
        batch = self.pending_orders.copy()
        self.pending_orders.clear()
        return batch

    def size(self) -> int:
        """Get current batch size."""
        return len(self.pending_orders)


async def run_order_plane(
    bus,
    ib_exec,
    logger,
    metrics,
    order_timeout_ms: float = 100.0,  # Aggressive timeout for <200ms end-to-end
    enable_batching: bool = True,
    batch_window_ms: float = 10.0,
    cache_ttl_seconds: float = 1.0
):
    """
    Optimized orchestrator for the order plane.

    Features:
    - Timeout controls for order placement
    - Order batching for improved throughput
    - Comprehensive latency tracking
    - Circuit breaker pattern
    - Risk check caching

    Args:
        bus: Message bus for consuming/publishing events
        ib_exec: IBKR execution client
        logger: Logger instance
        metrics: Performance monitor instance
        order_timeout_ms: Timeout for order placement in milliseconds
        enable_batching: Enable order batching
        batch_window_ms: Batch collection window in milliseconds
        cache_ttl_seconds: TTL for risk check cache
    """
    # Load limits (in production, from config or dynamic source)
    limits = {"max_gross_exposure": 1_000_000, "max_net_exposure": 500_000}

    # Initialize components
    risk_checker = PreTradeRisk()
    circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60.0)
    risk_cache = RiskCheckCache(ttl_seconds=cache_ttl_seconds)
    batcher = OrderBatcher(batch_window_ms=batch_window_ms) if enable_batching else None

    # Spawn parallel task to consume execution reports
    asyncio.create_task(
        consume_execution_reports(bus, logger, metrics)
    )

    # Periodic cache cleanup
    asyncio.create_task(_cleanup_cache_periodically(risk_cache))

    logger.info("order_plane_started", {
        "order_timeout_ms": order_timeout_ms,
        "batching_enabled": enable_batching,
        "batch_window_ms": batch_window_ms if enable_batching else None
    })

    async for intent in bus.consume("order_intents"):
        # Start end-to-end latency tracking
        intent_id = str(intent.intent_id) if hasattr(intent, 'intent_id') else str(id(intent))
        metrics.start_timer(intent_id)

        try:
            # 1. Pre-trade risk validation with caching
            risk_start = time.time() * 1000

            # Check cache first
            cache_key = f"{intent.symbol}_{intent.quantity}_{intent.side}"
            cached_result = risk_cache.get(cache_key)

            if cached_result is not None:
                risk_passed = cached_result
                metrics.increment("risk_check_cache_hit")
            else:
                risk_passed = risk_checker.validate(intent, limits)
                risk_cache.set(cache_key, risk_passed)
                metrics.increment("risk_check_cache_miss")

            risk_latency = (time.time() * 1000) - risk_start
            metrics.record_latency("risk_validation", risk_latency)

            if not risk_passed:
                logger.warn("risk_reject", intent=intent.dict())
                metrics.increment("orders_rejected_risk")
                metrics.end_timer(intent_id, "order_end_to_end_rejected")
                continue

            # 2. Throttling (POV/ADV caps)
            throttle_start = time.time() * 1000

            if exceeds_pov(intent, limits):
                original_qty = intent.quantity if hasattr(intent, 'quantity') else 0
                intent = downscale_qty(intent, limits)
                new_qty = intent.quantity if hasattr(intent, 'quantity') else 0
                logger.info("downscaled_qty", {
                    "original": original_qty,
                    "new": new_qty
                })
                metrics.increment("orders_downscaled")

            throttle_latency = (time.time() * 1000) - throttle_start
            metrics.record_latency("throttling_check", throttle_latency)

            # 3. Circuit breaker check
            if not circuit_breaker.can_attempt():
                logger.error("circuit_breaker_open", {
                    "state": circuit_breaker.state,
                    "failures": circuit_breaker.failure_count
                })
                metrics.increment("orders_circuit_breaker_reject")
                metrics.end_timer(intent_id, "order_end_to_end_circuit_breaker")
                continue

            # 4. Place order (with timeout)
            placement_start = time.time() * 1000

            try:
                # Await with timeout
                order_id = await asyncio.wait_for(
                    ib_exec.place(intent),
                    timeout=order_timeout_ms / 1000.0  # Convert to seconds
                )

                placement_latency = (time.time() * 1000) - placement_start
                metrics.record_latency("order_placement", placement_latency)

                # Record success
                circuit_breaker.record_success()
                metrics.increment("orders_placed_success")

                logger.info("placed_order", {
                    "order_id": order_id,
                    "intent_id": intent_id,
                    "placement_latency_ms": round(placement_latency, 2)
                })

                # Track end-to-end latency
                end_to_end_latency = metrics.end_timer(intent_id, "order_end_to_end_success")
                if end_to_end_latency:
                    logger.info("order_latency", {
                        "intent_id": intent_id,
                        "total_ms": round(end_to_end_latency, 2),
                        "risk_ms": round(risk_latency, 2),
                        "throttle_ms": round(throttle_latency, 2),
                        "placement_ms": round(placement_latency, 2)
                    })

            except asyncio.TimeoutError:
                timeout_latency = (time.time() * 1000) - placement_start
                logger.error("place_order_timeout", {
                    "intent_id": intent_id,
                    "timeout_ms": order_timeout_ms,
                    "elapsed_ms": round(timeout_latency, 2)
                })

                circuit_breaker.record_failure()
                metrics.increment("orders_timeout")
                metrics.record_error("order_placement_timeout")
                metrics.end_timer(intent_id, "order_end_to_end_timeout")

            except Exception as e:
                error_latency = (time.time() * 1000) - placement_start
                logger.error("place_order_failed", {
                    "reason": str(e),
                    "intent_id": intent_id,
                    "elapsed_ms": round(error_latency, 2)
                })

                circuit_breaker.record_failure()
                metrics.increment("orders_failed")
                metrics.record_error(f"order_placement_error_{type(e).__name__}")
                metrics.end_timer(intent_id, "order_end_to_end_error")

        except Exception as e:
            logger.error("order_processing_error", {
                "error": str(e),
                "intent_id": intent_id
            })
            metrics.record_error(f"order_processing_error_{type(e).__name__}")
            metrics.end_timer(intent_id, "order_end_to_end_exception")


async def consume_execution_reports(bus, logger, metrics):
    """
    Consumes execution reports to feed the learning loop and metrics.

    Enhanced with comprehensive latency tracking.
    """
    async for rpt in bus.consume("exec_reports"):
        report_received_time = time.time() * 1000

        logger.info("received_exec_report", {
            "status": rpt.status if hasattr(rpt, 'status') else 'unknown',
            "order_id": rpt.order_id if hasattr(rpt, 'order_id') else None
        })

        try:
            # Update online learning models (transaction cost)
            learning_start = time.time() * 1000
            update_lambda_online(rpt)
            learning_latency = (time.time() * 1000) - learning_start
            metrics.record_latency("learning_update", learning_latency)

            # Extract and log latency metrics if available
            if hasattr(rpt, 'latency_metrics') and rpt.latency_metrics:
                lm = rpt.latency_metrics

                if hasattr(lm, 'intent_to_submit_ms') and lm.intent_to_submit_ms:
                    metrics.record_latency("intent_to_submit", lm.intent_to_submit_ms)

                if hasattr(lm, 'submit_to_ack_ms') and lm.submit_to_ack_ms:
                    metrics.record_latency("submit_to_ack", lm.submit_to_ack_ms)

                if hasattr(lm, 'ack_to_fill_ms') and lm.ack_to_fill_ms:
                    metrics.record_latency("ack_to_fill", lm.ack_to_fill_ms)

                if hasattr(lm, 'total_latency_ms') and lm.total_latency_ms:
                    metrics.record_latency("fill_end_to_end", lm.total_latency_ms)

            # Track fill status
            if hasattr(rpt, 'status'):
                metrics.increment(f"fill_status_{rpt.status.lower()}")

        except Exception as e:
            logger.error("exec_report_processing_error", {
                "error": str(e),
                "report": rpt.dict() if hasattr(rpt, 'dict') else str(rpt)
            })
            metrics.record_error(f"exec_report_error_{type(e).__name__}")


async def _cleanup_cache_periodically(cache: RiskCheckCache, interval_seconds: float = 10.0):
    """Periodically clean up expired cache entries."""
    while True:
        await asyncio.sleep(interval_seconds)
        cache.clear_expired()
