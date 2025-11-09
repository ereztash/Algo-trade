"""
Main orchestrator for the 3-plane trading system (Control Plane).

The Orchestrator manages the complete trading lifecycle:
1. START: Initialize system, load config, connect adapters
2. TICK: Process market data events
3. SIGNAL: Generate trading signals from strategy
4. ORDER: Create order intents from signals/allocations
5. RISK: Validate orders against risk rules
6. EXECUTE: Submit orders to broker
7. SHUTDOWN: Clean up resources, log final state

Best Practices:
- Lifecycle separated from business logic (strategies are injected)
- Events emitted at every state transition (complete audit trail)
- Async-ready (uses asyncio patterns for future scalability)
- Mode-aware (dry/prelive/live via config, not hardcoded)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any, Protocol
from dataclasses import dataclass, field

from apps.strategy_loop.events import (
    StartEvent, TickEvent, SignalGeneratedEvent, OrderProposedEvent,
    OrderFilledEvent, RiskBreachEvent, ShutdownEvent
)


logger = logging.getLogger(__name__)


class DataSourceAdapter(Protocol):
    """Data source adapter interface (duck-typed)."""
    async def fetch_bars(self) -> Any: ...


class StrategyAdapter(Protocol):
    """Strategy adapter interface (duck-typed)."""
    async def generate_signal(self, bars: Any) -> Any: ...


class BrokerAdapter(Protocol):
    """Broker adapter interface (duck-typed)."""
    async def execute_order(self, order: Any) -> Any: ...


class RiskAdapter(Protocol):
    """Risk checker adapter interface (duck-typed)."""
    async def check_order(self, order: Any, portfolio: Any) -> tuple[bool, Optional[str]]: ...


@dataclass
class OrchestratorConfig:
    """
    Orchestrator configuration.

    All behavior driven by config (not hardcoded).
    Mode switches: dry|prelive|live.
    """
    mode: str = "dry"  # dry|prelive|live
    symbols: list[str] = field(default_factory=lambda: ["AAPL", "SPY"])
    max_iterations: Optional[int] = None  # None = infinite loop
    event_log_path: str = "reports/events.jsonl"
    enable_risk_checks: bool = True
    sleep_between_ticks: float = 0.0  # seconds (0 = no sleep, for dry-run speed)


class Orchestrator:
    """
    Main orchestrator (Control Plane).

    Coordinates data flow across all 3 planes:
    - Data Plane: Market data ingestion
    - Control Plane: Strategy logic & orchestration (THIS)
    - Execution Plane: Order execution & risk management

    Usage:
        orchestrator = Orchestrator(config)
        orchestrator.set_adapters(
            data_source=csv_source,
            strategy=mean_reversion,
            broker=paper_broker,
            risk_checker=risk_rules
        )
        await orchestrator.run()
    """

    def __init__(self, config: OrchestratorConfig):
        self.config = config
        self.start_time: Optional[datetime] = None
        self.iteration = 0
        self.total_signals = 0
        self.total_orders = 0

        # Adapters (injected, not hardcoded)
        self.data_source: Optional[DataSourceAdapter] = None
        self.strategy: Optional[StrategyAdapter] = None
        self.broker: Optional[BrokerAdapter] = None
        self.risk_checker: Optional[RiskAdapter] = None

        # Event log
        self.event_log: list[dict] = []

    def set_adapters(
        self,
        data_source: Optional[DataSourceAdapter] = None,
        strategy: Optional[StrategyAdapter] = None,
        broker: Optional[BrokerAdapter] = None,
        risk_checker: Optional[RiskAdapter] = None,
    ) -> None:
        """Inject adapters (dependency injection)."""
        if data_source:
            self.data_source = data_source
        if strategy:
            self.strategy = strategy
        if broker:
            self.broker = broker
        if risk_checker:
            self.risk_checker = risk_checker

    def emit_event(self, event: dict) -> None:
        """
        Emit an event to the audit log.

        Events are:
        - Appended to in-memory log
        - Written to disk (JSON-lines format)
        - Logged via structured logging
        """
        self.event_log.append(event)

        # Write to disk (append mode)
        log_path = Path(self.config.event_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(event) + "\n")

        # Log to console
        event_type = event.get("event_type", "UNKNOWN")
        logger.info(f"Event: {event_type}", extra={"event": event})

    async def hook_start(self) -> None:
        """
        Lifecycle hook: START

        Initialize the system:
        - Log startup event
        - Connect to data sources
        - Initialize strategy state
        """
        self.start_time = datetime.now(timezone.utc)

        event: StartEvent = {
            "event_type": "START",
            "timestamp": self.start_time.isoformat(),
            "metadata": {
                "mode": self.config.mode,
                "symbols": self.config.symbols,
                "max_iterations": self.config.max_iterations,
            }
        }
        self.emit_event(event)

        logger.info(f"Orchestrator started in {self.config.mode} mode")

    async def hook_tick(self, bar: Any) -> None:
        """
        Lifecycle hook: TICK

        Process incoming market data.
        Emits TickEvent for each bar.
        """
        event: TickEvent = {
            "event_type": "TICK",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": getattr(bar, "symbol", "UNKNOWN"),
            "metadata": {
                "close": getattr(bar, "close", None),
                "volume": getattr(bar, "volume", None),
            }
        }
        self.emit_event(event)

    async def hook_signal(self, signal: Any) -> None:
        """
        Lifecycle hook: SIGNAL

        Process strategy-generated signal.
        Emits SignalGeneratedEvent.
        """
        self.total_signals += 1

        event: SignalGeneratedEvent = {
            "event_type": "SIGNAL_GENERATED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signal_id": getattr(signal, "strategy_id", f"signal-{self.total_signals}"),
            "symbol": getattr(signal, "symbol", "UNKNOWN"),
            "direction": str(getattr(signal, "direction", "UNKNOWN")),
            "confidence": getattr(signal, "confidence", 0.0),
            "metadata": {
                "rationale": getattr(signal, "rationale", None),
            }
        }
        self.emit_event(event)

    async def hook_order(self, order: Any) -> None:
        """
        Lifecycle hook: ORDER

        Process order intent (before risk checks).
        Emits OrderProposedEvent.
        """
        self.total_orders += 1

        event: OrderProposedEvent = {
            "event_type": "ORDER_PROPOSED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_id": getattr(order, "order_id", f"order-{self.total_orders}"),
            "symbol": getattr(order, "symbol", "UNKNOWN"),
            "side": str(getattr(order, "side", "UNKNOWN")),
            "quantity": getattr(order, "quantity", 0.0),
            "metadata": {
                "order_type": str(getattr(order, "order_type", "UNKNOWN")),
                "limit_price": getattr(order, "limit_price", None),
            }
        }
        self.emit_event(event)

    async def hook_risk_breach(self, breach: Any) -> None:
        """
        Lifecycle hook: RISK_BREACH

        Process risk rule violation.
        Emits RiskBreachEvent.
        """
        event: RiskBreachEvent = {
            "event_type": "RISK_BREACH",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "breach_type": str(getattr(breach, "breach_type", "UNKNOWN")),
            "level": str(getattr(breach, "level", "UNKNOWN")),
            "action_taken": getattr(breach, "action_taken", "UNKNOWN"),
            "metadata": {
                "message": getattr(breach, "message", None),
                "limit_value": getattr(breach, "limit_value", None),
                "observed_value": getattr(breach, "observed_value", None),
            }
        }
        self.emit_event(event)

    async def hook_shutdown(self, reason: str = "NORMAL") -> None:
        """
        Lifecycle hook: SHUTDOWN

        Clean up resources and log final state.
        Emits ShutdownEvent.
        """
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0.0

        event: ShutdownEvent = {
            "event_type": "SHUTDOWN",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "uptime_seconds": uptime,
            "metadata": {
                "total_signals": self.total_signals,
                "total_orders": self.total_orders,
                "total_iterations": self.iteration,
            }
        }
        self.emit_event(event)

        logger.info(f"Orchestrator shutdown: {reason} (uptime: {uptime:.2f}s)")

    async def run(self) -> None:
        """
        Main orchestrator loop.

        Lifecycle:
        1. START
        2. Loop:
           a. Fetch data (TICK)
           b. Generate signals (SIGNAL)
           c. Create orders (ORDER)
           d. Check risk (RISK)
           e. Execute orders (EXECUTE)
        3. SHUTDOWN
        """
        try:
            # START
            await self.hook_start()

            # Main loop (dry-run: fixed iterations, live: infinite)
            max_iter = self.config.max_iterations or 1
            for i in range(max_iter):
                self.iteration = i + 1

                # In Phase 2, we have no adapters yet (pure orchestration test)
                # Adapters will be added in Phase 3
                # For now, just emit START and SHUTDOWN events

                if self.config.sleep_between_ticks > 0:
                    await asyncio.sleep(self.config.sleep_between_ticks)

            # SHUTDOWN
            await self.hook_shutdown(reason="NORMAL")

        except KeyboardInterrupt:
            await self.hook_shutdown(reason="USER_INTERRUPT")
            raise

        except Exception as e:
            logger.exception("Orchestrator error")
            await self.hook_shutdown(reason=f"ERROR: {str(e)}")
            raise
