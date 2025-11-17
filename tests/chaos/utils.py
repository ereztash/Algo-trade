"""
Chaos Engineering Utilities

Provides fault injection, recovery measurement, and state validation utilities
for chaos engineering tests.
"""

import time
import asyncio
from typing import Callable, Optional, Any, Dict, List
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
import threading


class FaultType(Enum):
    """Types of faults that can be injected"""
    NETWORK_DISCONNECT = "network_disconnect"
    NETWORK_LATENCY = "network_latency"
    NETWORK_PACKET_LOSS = "network_packet_loss"
    CONNECTION_TIMEOUT = "connection_timeout"
    RATE_LIMIT = "rate_limit"
    COMPONENT_CRASH = "component_crash"
    SLOW_RESPONSE = "slow_response"


@dataclass
class RecoveryMetrics:
    """Metrics collected during recovery testing"""
    fault_injected_at: float
    fault_detected_at: Optional[float] = None
    recovery_started_at: Optional[float] = None
    recovery_completed_at: Optional[float] = None
    data_loss_count: int = 0
    order_integrity_violations: int = 0
    state_consistency_issues: List[str] = field(default_factory=list)

    @property
    def detection_time_s(self) -> Optional[float]:
        """Time to detect the fault"""
        if self.fault_detected_at:
            return self.fault_detected_at - self.fault_injected_at
        return None

    @property
    def recovery_time_s(self) -> Optional[float]:
        """Total time to recover from fault"""
        if self.recovery_completed_at:
            return self.recovery_completed_at - self.fault_injected_at
        return None

    @property
    def meets_rto(self) -> bool:
        """Check if recovery time meets 30s RTO target"""
        if self.recovery_time_s is not None:
            return self.recovery_time_s <= 30.0
        return False

    def __str__(self) -> str:
        """Human-readable summary"""
        lines = [
            f"Recovery Metrics:",
            f"  Detection Time: {self.detection_time_s:.2f}s" if self.detection_time_s else "  Detection Time: N/A",
            f"  Recovery Time: {self.recovery_time_s:.2f}s" if self.recovery_time_s else "  Recovery Time: N/A",
            f"  Meets RTO (≤30s): {'✓ YES' if self.meets_rto else '✗ NO'}",
            f"  Data Loss: {self.data_loss_count} events",
            f"  Order Violations: {self.order_integrity_violations}",
            f"  State Issues: {len(self.state_consistency_issues)}",
        ]
        if self.state_consistency_issues:
            lines.append("  Issues:")
            for issue in self.state_consistency_issues:
                lines.append(f"    - {issue}")
        return "\n".join(lines)


class RecoveryTimer:
    """
    Context manager for measuring recovery time from faults.

    Usage:
        with RecoveryTimer() as timer:
            inject_fault()
            timer.mark_detected()
            timer.mark_recovery_started()
            # ... wait for recovery ...
            timer.mark_recovery_completed()

        assert timer.metrics.meets_rto
    """

    def __init__(self):
        self.metrics = RecoveryMetrics(fault_injected_at=time.time())
        self._start_time = None

    def __enter__(self):
        self._start_time = time.time()
        self.metrics.fault_injected_at = self._start_time
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Auto-complete if not already marked
        if self.metrics.recovery_completed_at is None:
            self.metrics.recovery_completed_at = time.time()
        return False

    def mark_detected(self):
        """Mark when fault was detected"""
        self.metrics.fault_detected_at = time.time()

    def mark_recovery_started(self):
        """Mark when recovery process started"""
        self.metrics.recovery_started_at = time.time()

    def mark_recovery_completed(self):
        """Mark when recovery completed successfully"""
        self.metrics.recovery_completed_at = time.time()

    def record_data_loss(self, count: int = 1):
        """Record data loss events"""
        self.metrics.data_loss_count += count

    def record_order_violation(self, count: int = 1):
        """Record order integrity violations"""
        self.metrics.order_integrity_violations += count

    def record_state_issue(self, issue: str):
        """Record state consistency issue"""
        self.metrics.state_consistency_issues.append(issue)


class NetworkFaultInjector:
    """
    Simulates network-level faults for chaos testing.

    Can inject:
    - Connection failures (disconnect/reconnect)
    - Latency (constant or variable delays)
    - Packet loss (probabilistic drops)
    - Timeouts (connection/read timeouts)
    """

    def __init__(self):
        self._active_faults: Dict[str, Any] = {}
        self._latency_ms = 0
        self._packet_loss_prob = 0.0
        self._is_disconnected = False
        self._lock = threading.Lock()

    @contextmanager
    def inject_disconnect(self, duration_s: float):
        """
        Context manager to inject network disconnect for specified duration.

        Args:
            duration_s: Duration of disconnect in seconds

        Example:
            with injector.inject_disconnect(5.0):
                # Network is down for 5 seconds
                client.request_data()  # Should fail or timeout
        """
        with self._lock:
            self._is_disconnected = True

        try:
            yield
            time.sleep(duration_s)
        finally:
            with self._lock:
                self._is_disconnected = False

    @contextmanager
    def inject_latency(self, latency_ms: int):
        """
        Context manager to inject network latency.

        Args:
            latency_ms: Latency to add in milliseconds

        Example:
            with injector.inject_latency(500):
                # All network calls delayed by 500ms
                client.request_data()
        """
        with self._lock:
            old_latency = self._latency_ms
            self._latency_ms = latency_ms

        try:
            yield
        finally:
            with self._lock:
                self._latency_ms = old_latency

    @contextmanager
    def inject_packet_loss(self, loss_probability: float):
        """
        Context manager to inject packet loss.

        Args:
            loss_probability: Probability of packet loss (0.0 to 1.0)

        Example:
            with injector.inject_packet_loss(0.20):
                # 20% of packets dropped
                client.stream_data()
        """
        with self._lock:
            old_prob = self._packet_loss_prob
            self._packet_loss_prob = loss_probability

        try:
            yield
        finally:
            with self._lock:
                self._packet_loss_prob = old_prob

    def apply_latency(self):
        """Apply configured latency delay (call in network operations)"""
        with self._lock:
            latency = self._latency_ms

        if latency > 0:
            time.sleep(latency / 1000.0)

    def should_drop_packet(self) -> bool:
        """Check if packet should be dropped (call in network operations)"""
        import random
        with self._lock:
            prob = self._packet_loss_prob

        return random.random() < prob

    def is_disconnected(self) -> bool:
        """Check if network is currently disconnected"""
        with self._lock:
            return self._is_disconnected

    def get_current_latency_ms(self) -> int:
        """Get current latency setting"""
        with self._lock:
            return self._latency_ms


class StateValidator:
    """
    Validates system state consistency after chaos events.

    Checks:
    - Order integrity (no duplicates, all orders accounted for)
    - Position accuracy (matches expected state)
    - Data completeness (no gaps in time series)
    - Message ordering (proper sequencing)
    """

    def __init__(self):
        self.violations: List[str] = []

    def validate_order_integrity(
        self,
        sent_orders: List[Dict],
        received_orders: List[Dict],
    ) -> bool:
        """
        Validate that all sent orders are properly tracked.

        Args:
            sent_orders: Orders that were sent
            received_orders: Orders that were acknowledged

        Returns:
            True if integrity maintained, False otherwise
        """
        sent_ids = {o.get('order_id') for o in sent_orders}
        received_ids = {o.get('order_id') for o in received_orders}

        # Check for missing orders
        missing = sent_ids - received_ids
        if missing:
            self.violations.append(
                f"Missing order acknowledgments: {missing}"
            )
            return False

        # Check for duplicate orders
        if len(received_ids) != len(received_orders):
            duplicates = len(received_orders) - len(received_ids)
            self.violations.append(
                f"Duplicate orders detected: {duplicates} duplicates"
            )
            return False

        return True

    def validate_position_consistency(
        self,
        expected_position: Dict[str, int],
        actual_position: Dict[str, int],
    ) -> bool:
        """
        Validate that position matches expected state.

        Args:
            expected_position: Expected position by symbol
            actual_position: Actual position by symbol

        Returns:
            True if positions match, False otherwise
        """
        all_symbols = set(expected_position.keys()) | set(actual_position.keys())

        for symbol in all_symbols:
            expected = expected_position.get(symbol, 0)
            actual = actual_position.get(symbol, 0)

            if expected != actual:
                self.violations.append(
                    f"Position mismatch for {symbol}: "
                    f"expected {expected}, actual {actual}"
                )
                return False

        return True

    def validate_data_completeness(
        self,
        expected_count: int,
        actual_count: int,
        tolerance: float = 0.05,
    ) -> bool:
        """
        Validate that data is complete within tolerance.

        Args:
            expected_count: Expected number of data points
            actual_count: Actual number of data points
            tolerance: Acceptable loss ratio (default 5%)

        Returns:
            True if completeness meets tolerance, False otherwise
        """
        if expected_count == 0:
            return actual_count == 0

        loss_ratio = (expected_count - actual_count) / expected_count

        if loss_ratio > tolerance:
            self.violations.append(
                f"Data loss exceeds tolerance: "
                f"{loss_ratio:.1%} loss (tolerance: {tolerance:.1%})"
            )
            return False

        return True

    def validate_message_ordering(
        self,
        messages: List[Dict],
        sequence_key: str = 'seq',
    ) -> bool:
        """
        Validate that messages are in proper sequence.

        Args:
            messages: List of messages with sequence numbers
            sequence_key: Key for sequence number in message dict

        Returns:
            True if ordering is correct, False otherwise
        """
        if not messages:
            return True

        sequences = [m.get(sequence_key) for m in messages]

        # Check for missing sequence numbers
        if None in sequences:
            self.violations.append("Messages missing sequence numbers")
            return False

        # Check for gaps or out-of-order
        sorted_seq = sorted(sequences)
        if sequences != sorted_seq:
            self.violations.append(
                "Messages out of sequence order"
            )
            return False

        # Check for gaps in sequence
        expected_range = range(sorted_seq[0], sorted_seq[-1] + 1)
        missing = set(expected_range) - set(sequences)
        if missing:
            self.violations.append(
                f"Sequence gaps detected: {len(missing)} missing sequences"
            )
            return False

        return True

    def get_violations(self) -> List[str]:
        """Get all validation violations"""
        return self.violations.copy()

    def reset(self):
        """Reset validator state"""
        self.violations.clear()


@contextmanager
def chaos_scenario(
    name: str,
    fault_type: FaultType,
    recovery_fn: Optional[Callable] = None,
):
    """
    Context manager for running a complete chaos scenario.

    Args:
        name: Name of the chaos scenario
        fault_type: Type of fault to inject
        recovery_fn: Optional recovery function to call

    Example:
        with chaos_scenario("IBKR Disconnect", FaultType.NETWORK_DISCONNECT):
            timer = RecoveryTimer()
            with timer:
                # Inject fault
                client.disconnect()
                timer.mark_detected()

                # Trigger recovery
                if recovery_fn:
                    recovery_fn()
                timer.mark_recovery_started()

                # Wait for recovery
                wait_for_healthy(client)
                timer.mark_recovery_completed()

            assert timer.metrics.meets_rto
    """
    print(f"\n{'='*60}")
    print(f"CHAOS SCENARIO: {name}")
    print(f"Fault Type: {fault_type.value}")
    print(f"{'='*60}\n")

    start_time = time.time()

    try:
        yield

        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"SCENARIO COMPLETED: {name}")
        print(f"Duration: {elapsed:.2f}s")
        print(f"{'='*60}\n")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"SCENARIO FAILED: {name}")
        print(f"Duration: {elapsed:.2f}s")
        print(f"Error: {e}")
        print(f"{'='*60}\n")
        raise


async def wait_for_condition(
    condition_fn: Callable[[], bool],
    timeout_s: float = 30.0,
    check_interval_s: float = 0.1,
) -> bool:
    """
    Wait for a condition to become true within timeout.

    Args:
        condition_fn: Function that returns True when condition is met
        timeout_s: Maximum time to wait
        check_interval_s: How often to check condition

    Returns:
        True if condition met, False if timeout

    Example:
        success = await wait_for_condition(
            lambda: client.is_connected(),
            timeout_s=30.0
        )
        assert success, "Failed to reconnect within 30s"
    """
    start_time = time.time()

    while time.time() - start_time < timeout_s:
        if condition_fn():
            return True
        await asyncio.sleep(check_interval_s)

    return False


def exponential_backoff(
    attempt: int,
    base_delay_s: float = 1.0,
    max_delay_s: float = 30.0,
) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay_s: Base delay in seconds
        max_delay_s: Maximum delay cap

    Returns:
        Delay in seconds for this attempt

    Example:
        for attempt in range(5):
            delay = exponential_backoff(attempt)
            time.sleep(delay)
            try_connect()
    """
    delay = base_delay_s * (2 ** attempt)
    return min(delay, max_delay_s)
