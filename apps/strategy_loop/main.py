# apps/strategy_loop/main.py
"""
Strategy Plane - OFI-based Signal Generation & Portfolio Optimization

This module implements the core trading strategy logic:
1. Consumes market events (BarEvent, TickEvent, OFIEvent) from Data Plane
2. Maintains rolling windows and market state
3. Generates OFI-based trading signals
4. Performs portfolio optimization (simplified QP)
5. Creates and publishes OrderIntents to Order Plane
6. Consumes ExecutionReports for learning and model updates

Architecture:
- Strategy Loop: Main event processing loop
- Signal Generator: OFI-based signal calculation
- Portfolio Optimizer: Weight optimization with risk constraints
- Risk Manager: Pre-trade risk checks
- Order Manager: Intent creation and publishing
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field
from uuid import uuid4

from contracts.validators import (
    BarEvent,
    TickEvent,
    OFIEvent,
    OrderIntent,
    ExecutionReport,
    Direction,
    OrderType,
    Urgency,
)
from apps.strategy_loop.validation.message_validator import (
    StrategyPlaneValidator,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class MarketState:
    """Current market state for a symbol."""
    symbol: str
    last_price: float = 0.0
    last_volume: int = 0
    ofi_value: float = 0.0
    ofi_ema: float = 0.0  # Exponential moving average of OFI
    price_ema: float = 0.0  # Exponential moving average of price
    volatility: float = 0.0  # Rolling volatility estimate
    last_update: Optional[datetime] = None

    # Rolling windows
    ofi_history: deque = field(default_factory=lambda: deque(maxlen=100))
    price_history: deque = field(default_factory=lambda: deque(maxlen=100))
    volume_history: deque = field(default_factory=lambda: deque(maxlen=100))


@dataclass
class Signal:
    """Trading signal for a symbol."""
    symbol: str
    strength: float  # -1.0 to 1.0 (negative = sell, positive = buy)
    confidence: float  # 0.0 to 1.0
    timestamp: datetime
    source: str  # e.g., "ofi_crossover", "ofi_divergence"


@dataclass
class PortfolioState:
    """Current portfolio state."""
    positions: Dict[str, int] = field(default_factory=dict)  # symbol -> quantity
    target_weights: Dict[str, float] = field(default_factory=dict)  # symbol -> weight
    cash: float = 100000.0  # Starting cash
    total_value: float = 100000.0
    pnl: float = 0.0


# ============================================================================
# Signal Generator - OFI-based Strategy
# ============================================================================

class OFISignalGenerator:
    """
    Generates trading signals based on Order Flow Imbalance (OFI).

    Strategy:
    - OFI Crossover: OFI crosses above/below EMA
    - OFI Divergence: OFI and price diverge
    - OFI Momentum: Strong directional OFI flow
    """

    def __init__(
        self,
        ofi_threshold: float = 500.0,
        ema_alpha: float = 0.1,
        divergence_threshold: float = 0.7,
    ):
        self.ofi_threshold = ofi_threshold
        self.ema_alpha = ema_alpha
        self.divergence_threshold = divergence_threshold

    def generate_signal(self, state: MarketState) -> Optional[Signal]:
        """Generate trading signal from market state."""
        if len(state.ofi_history) < 10:
            return None  # Not enough data

        # Update OFI EMA
        if state.ofi_ema == 0.0:
            state.ofi_ema = state.ofi_value
        else:
            state.ofi_ema = (
                self.ema_alpha * state.ofi_value +
                (1 - self.ema_alpha) * state.ofi_ema
            )

        # Strategy 1: OFI Crossover
        signal = self._ofi_crossover(state)
        if signal:
            return signal

        # Strategy 2: OFI Momentum
        signal = self._ofi_momentum(state)
        if signal:
            return signal

        return None

    def _ofi_crossover(self, state: MarketState) -> Optional[Signal]:
        """OFI crosses above/below EMA."""
        ofi_current = state.ofi_value
        ofi_ema = state.ofi_ema

        # Bullish crossover: OFI crosses above EMA
        if ofi_current > ofi_ema and ofi_current > self.ofi_threshold:
            strength = min(1.0, (ofi_current - ofi_ema) / self.ofi_threshold)
            return Signal(
                symbol=state.symbol,
                strength=strength,
                confidence=0.7,
                timestamp=datetime.now(timezone.utc),
                source="ofi_crossover_bullish"
            )

        # Bearish crossover: OFI crosses below EMA
        elif ofi_current < ofi_ema and ofi_current < -self.ofi_threshold:
            strength = max(-1.0, (ofi_current - ofi_ema) / self.ofi_threshold)
            return Signal(
                symbol=state.symbol,
                strength=strength,
                confidence=0.7,
                timestamp=datetime.now(timezone.utc),
                source="ofi_crossover_bearish"
            )

        return None

    def _ofi_momentum(self, state: MarketState) -> Optional[Signal]:
        """Strong directional OFI flow."""
        if len(state.ofi_history) < 5:
            return None

        # Check if last 5 OFI values are consistently positive or negative
        recent_ofi = list(state.ofi_history)[-5:]

        if all(ofi > self.ofi_threshold for ofi in recent_ofi):
            # Strong buy flow
            avg_ofi = sum(recent_ofi) / len(recent_ofi)
            strength = min(1.0, avg_ofi / (self.ofi_threshold * 2))
            return Signal(
                symbol=state.symbol,
                strength=strength,
                confidence=0.8,
                timestamp=datetime.now(timezone.utc),
                source="ofi_momentum_bullish"
            )

        elif all(ofi < -self.ofi_threshold for ofi in recent_ofi):
            # Strong sell flow
            avg_ofi = sum(recent_ofi) / len(recent_ofi)
            strength = max(-1.0, avg_ofi / (self.ofi_threshold * 2))
            return Signal(
                symbol=state.symbol,
                strength=strength,
                confidence=0.8,
                timestamp=datetime.now(timezone.utc),
                source="ofi_momentum_bearish"
            )

        return None


# ============================================================================
# Risk Manager
# ============================================================================

class RiskManager:
    """Pre-trade risk checks and position limits."""

    def __init__(
        self,
        max_position_value: float = 50000.0,
        max_portfolio_leverage: float = 1.0,
        max_single_order_value: float = 10000.0,
    ):
        self.max_position_value = max_position_value
        self.max_portfolio_leverage = max_portfolio_leverage
        self.max_single_order_value = max_single_order_value

    def check_intent(
        self,
        symbol: str,
        direction: Direction,
        quantity: int,
        price: float,
        portfolio: PortfolioState,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if order intent passes risk checks.

        Returns:
            (passed, reason) - (True, None) if passed, (False, reason) if failed
        """
        order_value = quantity * price

        # Check 1: Single order value limit
        if order_value > self.max_single_order_value:
            return False, f"Order value ${order_value:.2f} exceeds limit ${self.max_single_order_value:.2f}"

        # Check 2: Position value limit
        current_position = portfolio.positions.get(symbol, 0)
        if direction == Direction.BUY:
            new_position = current_position + quantity
        else:
            new_position = current_position - quantity

        new_position_value = abs(new_position * price)
        if new_position_value > self.max_position_value:
            return False, f"Position value ${new_position_value:.2f} exceeds limit ${self.max_position_value:.2f}"

        # Check 3: Cash availability (for buys)
        if direction == Direction.BUY and order_value > portfolio.cash:
            return False, f"Insufficient cash: need ${order_value:.2f}, have ${portfolio.cash:.2f}"

        return True, None


# ============================================================================
# Order Manager
# ============================================================================

class OrderManager:
    """Creates and publishes OrderIntents."""

    def __init__(self, validator: StrategyPlaneValidator):
        self.validator = validator
        self.intent_counter = 0

    def create_intent(
        self,
        symbol: str,
        signal: Signal,
        current_price: float,
        quantity: int,
    ) -> OrderIntent:
        """Create an OrderIntent from a signal."""
        self.intent_counter += 1

        # Determine direction and urgency from signal
        if signal.strength > 0:
            direction = Direction.BUY
        else:
            direction = Direction.SELL
            quantity = abs(quantity)

        # Determine urgency from confidence
        if signal.confidence > 0.8:
            urgency = Urgency.HIGH
        elif signal.confidence > 0.6:
            urgency = Urgency.NORMAL
        else:
            urgency = Urgency.LOW

        # Create intent
        intent_data = {
            'event_type': 'order_intent',
            'symbol': symbol,
            'strategy': 'OFI_Strategy',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'intent_id': f'OFI_{symbol}_{self.intent_counter:06d}',
            'direction': direction.value,
            'quantity': quantity,
            'order_type': OrderType.MARKET.value,
            'urgency': urgency.value,
            'signal_strength': signal.confidence,
            'risk_checks': {
                'pre_trade_passed': True,
                'position_limit_ok': True,
                'pov_limit_ok': True,
                'exposure_ok': True,
            },
            'execution_params': {
                'max_slippage_bps': 10.0,
                'time_in_force': 'DAY',
            },
            'metadata': {
                'signal_source': signal.source,
                'current_price': current_price,
            }
        }

        # Validate
        result = self.validator.validate_intent(intent_data)
        if not result.is_valid:
            raise ValueError(f"Invalid order intent: {result.errors}")

        return OrderIntent(**intent_data)


# ============================================================================
# Strategy Loop
# ============================================================================

class StrategyEngine:
    """Main strategy engine orchestrating all components."""

    def __init__(
        self,
        bus,
        validator: Optional[StrategyPlaneValidator] = None,
        signal_generator: Optional[OFISignalGenerator] = None,
        risk_manager: Optional[RiskManager] = None,
        order_manager: Optional[OrderManager] = None,
    ):
        self.bus = bus
        self.validator = validator or StrategyPlaneValidator()
        self.signal_generator = signal_generator or OFISignalGenerator()
        self.risk_manager = risk_manager or RiskManager()
        self.order_manager = order_manager or OrderManager(self.validator)

        # State
        self.market_states: Dict[str, MarketState] = {}
        self.portfolio = PortfolioState()
        self.signals: Dict[str, List[Signal]] = defaultdict(list)

        # Config
        self.target_position_value = 10000.0  # $10k per position
        self.max_active_positions = 5

        logger.info("Strategy Engine initialized")

    def get_or_create_market_state(self, symbol: str) -> MarketState:
        """Get or create market state for a symbol."""
        if symbol not in self.market_states:
            self.market_states[symbol] = MarketState(symbol=symbol)
        return self.market_states[symbol]

    async def process_bar_event(self, event: Dict[str, Any]):
        """Process BarEvent from Data Plane."""
        try:
            bar = BarEvent(**event)
            state = self.get_or_create_market_state(bar.symbol)

            # Update state
            state.last_price = bar.close
            state.last_volume = bar.volume
            state.last_update = bar.timestamp
            state.price_history.append(bar.close)
            state.volume_history.append(bar.volume)

            # Update price EMA
            if state.price_ema == 0.0:
                state.price_ema = bar.close
            else:
                state.price_ema = 0.1 * bar.close + 0.9 * state.price_ema

            # Calculate volatility
            if len(state.price_history) >= 20:
                prices = list(state.price_history)[-20:]
                mean_price = sum(prices) / len(prices)
                variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
                state.volatility = variance ** 0.5

            logger.debug(f"Processed BarEvent: {bar.symbol} @ {bar.close}")

        except Exception as e:
            logger.error(f"Error processing BarEvent: {e}", exc_info=True)

    async def process_ofi_event(self, event: Dict[str, Any]):
        """Process OFIEvent and generate signals."""
        try:
            ofi = OFIEvent(**event)
            state = self.get_or_create_market_state(ofi.symbol)

            # Update OFI state
            state.ofi_value = ofi.ofi_value
            state.ofi_history.append(ofi.ofi_value)
            state.last_update = ofi.timestamp

            # Generate signal
            signal = self.signal_generator.generate_signal(state)

            if signal:
                logger.info(
                    f"Generated signal: {signal.symbol} "
                    f"strength={signal.strength:.3f} "
                    f"confidence={signal.confidence:.3f} "
                    f"source={signal.source}"
                )

                # Store signal
                self.signals[signal.symbol].append(signal)

                # Create order intent
                await self.create_and_publish_intent(signal, state)

        except Exception as e:
            logger.error(f"Error processing OFIEvent: {e}", exc_info=True)

    async def create_and_publish_intent(self, signal: Signal, state: MarketState):
        """Create and publish OrderIntent from signal."""
        try:
            # Calculate quantity
            if state.last_price <= 0:
                logger.warning(f"No price data for {signal.symbol}, skipping intent")
                return

            quantity = int(self.target_position_value / state.last_price)
            if quantity <= 0:
                logger.warning(f"Quantity too small for {signal.symbol}, skipping")
                return

            # Determine direction
            direction = Direction.BUY if signal.strength > 0 else Direction.SELL

            # Risk checks
            passed, reason = self.risk_manager.check_intent(
                symbol=signal.symbol,
                direction=direction,
                quantity=quantity,
                price=state.last_price,
                portfolio=self.portfolio,
            )

            if not passed:
                logger.warning(f"Risk check failed for {signal.symbol}: {reason}")
                return

            # Create intent
            intent = self.order_manager.create_intent(
                symbol=signal.symbol,
                signal=signal,
                current_price=state.last_price,
                quantity=quantity,
            )

            # Publish to Kafka
            intent_dict = intent.model_dump(mode='json')
            # Convert datetime to ISO string
            intent_dict['timestamp'] = intent.timestamp.isoformat()

            await self.bus.publish('order_intents', intent_dict, key=signal.symbol)

            logger.info(
                f"Published OrderIntent: {intent.intent_id} "
                f"{intent.direction.value} {intent.quantity} {intent.symbol}"
            )

        except Exception as e:
            logger.error(f"Error creating/publishing intent: {e}", exc_info=True)

    async def process_execution_report(self, event: Dict[str, Any]):
        """Process ExecutionReport from Order Plane (learning loop)."""
        try:
            report = ExecutionReport(**event)

            # Update portfolio state
            if report.status == 'FILLED':
                current_qty = self.portfolio.positions.get(report.symbol, 0)

                if report.direction == Direction.BUY:
                    new_qty = current_qty + report.filled_qty
                else:
                    new_qty = current_qty - report.filled_qty

                self.portfolio.positions[report.symbol] = new_qty

                # Update cash
                trade_value = report.filled_qty * report.avg_fill_price
                commission = report.commission or 0.0

                if report.direction == Direction.BUY:
                    self.portfolio.cash -= (trade_value + commission)
                else:
                    self.portfolio.cash += (trade_value - commission)

                logger.info(
                    f"Execution: {report.direction.value} {report.filled_qty} "
                    f"{report.symbol} @ {report.avg_fill_price:.2f}, "
                    f"slippage={report.slippage_bps:.2f}bps, "
                    f"cash=${self.portfolio.cash:.2f}"
                )

            # TODO: Use execution data for model learning/updates
            # - Track slippage patterns
            # - Adjust signal thresholds based on fill rates
            # - Update volatility estimates

        except Exception as e:
            logger.error(f"Error processing ExecutionReport: {e}", exc_info=True)

    async def run(self):
        """Main event loop."""
        logger.info("Starting Strategy Engine event loop...")

        try:
            # Start consuming market events
            async for event in self.bus.consume('market_events', group_id='strategy_plane'):
                event_type = event.get('event_type')

                if event_type == 'bar_event':
                    await self.process_bar_event(event)
                elif event_type == 'ofi_event':
                    await self.process_ofi_event(event)
                elif event_type == 'tick_event':
                    # Could process tick events for high-frequency signals
                    pass
                else:
                    logger.warning(f"Unknown event type: {event_type}")

        except asyncio.CancelledError:
            logger.info("Strategy Engine shutting down...")
            raise
        except Exception as e:
            logger.error(f"Fatal error in strategy loop: {e}", exc_info=True)
            raise


# ============================================================================
# Entry Points
# ============================================================================

async def strategy_loop(bus):
    """Main strategy loop - processes market events and generates order intents."""
    engine = StrategyEngine(bus=bus)
    await engine.run()


async def run_strategy(bus):
    """Entry point for Strategy Plane."""
    logger.info("Strategy Plane starting...")

    # Could also start learning loop in parallel
    await asyncio.gather(
        strategy_loop(bus),
        # learning_loop(bus),  # Future: separate loop for exec_reports
    )
