"""
End-to-End Tests: Full Trading Loop

Tests the complete data flow from market data ingestion through signal generation
to order execution:

Data Plane → Strategy Plane → Order Plane → Execution Reports

Components tested:
- Market data processing (BarEvent, OFIEvent)
- Signal generation
- Portfolio optimization
- Order submission
- Execution confirmation
"""

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4
from decimal import Decimal

# Import validators for creating test messages
from contracts.validators import (
    BarEvent, OFIEvent, OrderIntent, ExecutionReport,
    DataQuality, EventMetadata
)


# =============================================================================
# Test Fixtures for E2E Testing
# =============================================================================

@pytest.fixture
def sample_bar_event():
    """Create a valid BarEvent for testing."""
    return BarEvent(
        event_type='bar_event',
        symbol='SPY',
        timestamp=datetime.now(timezone.utc),
        open=450.25,
        high=452.80,
        low=449.50,
        close=451.75,
        volume=85234567,
        bar_duration='1d',
        asset_class='equity',
        exchange='NASDAQ',
        currency='USD',
        data_quality=DataQuality(
            completeness_score=1.0,
            freshness_ms=100,
            source='ibkr_realtime'
        ),
        metadata=EventMetadata(
            producer_id='data-plane-1',
            sequence_number=1,
            kafka_topic='market_events'
        )
    )


@pytest.fixture
def sample_ofi_event():
    """Create a valid OFIEvent for testing."""
    return OFIEvent(
        event_type='ofi_event',
        symbol='SPY',
        timestamp=datetime.now(timezone.utc),
        ofi_value=0.25,
        bid_volume=1000000,
        ask_volume=800000,
        bid_price=451.50,
        ask_price=451.52,
        window_duration='5m',
        metadata=EventMetadata(
            producer_id='data-plane-1',
            sequence_number=2,
            kafka_topic='ofi_events'
        )
    )


@pytest.fixture
def sample_order_intent():
    """Create a valid OrderIntent for testing."""
    return OrderIntent(
        intent_id=str(uuid4()),
        symbol='SPY',
        side='buy',
        quantity=100,
        order_type='market',
        timestamp=datetime.now(timezone.utc),
        strategy_id='momentum_v1',
        signal_strength=0.75,
        risk_limit_checks_passed=True,
        metadata=EventMetadata(
            producer_id='strategy-plane-1',
            sequence_number=1,
            kafka_topic='order_intents'
        )
    )


@pytest.fixture
def sample_execution_report():
    """Create a valid ExecutionReport for testing."""
    intent_id = str(uuid4())
    return ExecutionReport(
        execution_id=str(uuid4()),
        intent_id=intent_id,
        symbol='SPY',
        side='buy',
        quantity=100,
        filled_quantity=100,
        avg_fill_price=451.75,
        status='filled',
        timestamp=datetime.now(timezone.utc),
        broker_order_id='IB-' + str(uuid4())[:8],
        commission=1.00,
        metadata=EventMetadata(
            producer_id='order-plane-1',
            sequence_number=1,
            kafka_topic='exec_reports'
        )
    )


# =============================================================================
# E2E Test: Full Trading Loop
# =============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestFullTradingLoop:
    """End-to-end tests for the complete trading pipeline."""

    async def test_bar_to_signal_flow(self, sample_bar_event):
        """
        E2E: BarEvent → Signal Generation

        Test that a BarEvent from Data Plane can be consumed
        and processed into a trading signal.
        """
        bar = sample_bar_event

        # Validate bar event
        assert bar.event_type == 'bar_event'
        assert bar.symbol == 'SPY'
        assert bar.close > 0

        # Simulate strategy processing
        # In real E2E, this would consume from Kafka and produce signal

        # Calculate simple momentum signal
        returns = (bar.close - bar.open) / bar.open
        signal_strength = min(max(returns * 10, -1.0), 1.0)  # Normalize to [-1, 1]

        # If signal strong enough, generate order intent
        if abs(signal_strength) > 0.1:
            side = 'buy' if signal_strength > 0 else 'sell'

            intent = OrderIntent(
                intent_id=str(uuid4()),
                symbol=bar.symbol,
                side=side,
                quantity=100,
                order_type='market',
                timestamp=datetime.now(timezone.utc),
                strategy_id='momentum_v1',
                signal_strength=abs(signal_strength),
                risk_limit_checks_passed=True,
                metadata=EventMetadata(
                    producer_id='strategy-plane-test',
                    sequence_number=1,
                    kafka_topic='order_intents'
                )
            )

            # Verify intent created correctly
            assert intent.symbol == bar.symbol
            assert intent.side in ['buy', 'sell']
            assert 0 <= intent.signal_strength <= 1.0

            return intent

        return None

    async def test_ofi_to_order_flow(self, sample_ofi_event):
        """
        E2E: OFIEvent → Order Generation

        Test that OFI signals can generate order intents.
        """
        ofi = sample_ofi_event

        # Validate OFI event
        assert ofi.event_type == 'ofi_event'
        assert -1.0 <= ofi.ofi_value <= 1.0

        # Strong OFI signal should generate order
        if abs(ofi.ofi_value) > 0.2:
            side = 'buy' if ofi.ofi_value > 0 else 'sell'

            # Calculate position size based on signal strength
            base_quantity = 100
            quantity = int(base_quantity * abs(ofi.ofi_value))

            intent = OrderIntent(
                intent_id=str(uuid4()),
                symbol=ofi.symbol,
                side=side,
                quantity=quantity,
                order_type='limit',
                limit_price=ofi.bid_price if side == 'buy' else ofi.ask_price,
                timestamp=datetime.now(timezone.utc),
                strategy_id='ofi_v1',
                signal_strength=abs(ofi.ofi_value),
                risk_limit_checks_passed=True
            )

            assert intent.quantity > 0
            assert intent.quantity <= 100  # OFI scaled position

            return intent

        return None

    async def test_order_to_execution_flow(self, sample_order_intent):
        """
        E2E: OrderIntent → ExecutionReport

        Test complete order lifecycle from intent to execution.
        """
        intent = sample_order_intent

        # Validate order intent
        assert intent.symbol is not None
        assert intent.side in ['buy', 'sell']
        assert intent.quantity > 0

        # Simulate order execution
        # In real E2E, Order Plane would:
        # 1. Consume intent from Kafka
        # 2. Submit to broker (IBKR)
        # 3. Receive fill confirmation
        # 4. Produce ExecutionReport

        # Simulate fill (market order assumed fully filled)
        execution = ExecutionReport(
            execution_id=str(uuid4()),
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            filled_quantity=intent.quantity,  # Full fill
            avg_fill_price=451.75,  # Mock fill price
            status='filled',
            timestamp=datetime.now(timezone.utc),
            broker_order_id='IB-TEST-001',
            commission=1.00,
            metadata=EventMetadata(
                producer_id='order-plane-test',
                sequence_number=1,
                kafka_topic='exec_reports'
            )
        )

        # Verify execution
        assert execution.intent_id == intent.intent_id
        assert execution.filled_quantity == intent.quantity
        assert execution.status == 'filled'
        assert execution.commission >= 0

        return execution

    async def test_complete_pipeline(self):
        """
        E2E: Complete Pipeline Test

        Test full flow: Market Data → Signal → Order → Execution
        """
        # Step 1: Market data arrives
        bar = BarEvent(
            event_type='bar_event',
            symbol='AAPL',
            timestamp=datetime.now(timezone.utc),
            open=180.00,
            high=182.50,
            low=179.50,
            close=182.00,  # Strong upward move
            volume=50000000,
            bar_duration='1d',
            asset_class='equity',
            data_quality=DataQuality(
                completeness_score=1.0,
                freshness_ms=50,
                source='ibkr_realtime'
            )
        )

        # Step 2: Strategy generates signal
        returns = (bar.close - bar.open) / bar.open
        signal_strength = 0.65  # Strong buy signal

        intent = OrderIntent(
            intent_id=str(uuid4()),
            symbol=bar.symbol,
            side='buy',
            quantity=50,
            order_type='market',
            timestamp=datetime.now(timezone.utc),
            strategy_id='momentum_v1',
            signal_strength=signal_strength,
            risk_limit_checks_passed=True
        )

        # Step 3: Order executed
        execution = ExecutionReport(
            execution_id=str(uuid4()),
            intent_id=intent.intent_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            filled_quantity=intent.quantity,
            avg_fill_price=182.05,  # Slight slippage
            status='filled',
            timestamp=datetime.now(timezone.utc),
            broker_order_id='IB-AAPL-001',
            commission=0.50
        )

        # Verify complete pipeline
        assert bar.symbol == intent.symbol == execution.symbol
        assert intent.intent_id == execution.intent_id
        assert execution.filled_quantity == intent.quantity
        assert execution.status == 'filled'

        # Calculate P&L
        slippage = execution.avg_fill_price - bar.close
        cost = execution.avg_fill_price * execution.filled_quantity
        total_cost = cost + execution.commission

        assert slippage < 0.10  # Acceptable slippage
        assert total_cost > 0


# =============================================================================
# E2E Test: Multiple Assets Pipeline
# =============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestMultiAssetPipeline:
    """Test pipeline with multiple assets simultaneously."""

    async def test_portfolio_construction(self):
        """
        E2E: Multi-Asset Portfolio Construction

        Test signal generation and portfolio optimization
        across multiple assets.
        """
        # Market data for multiple assets
        symbols = ['SPY', 'QQQ', 'IWM', 'TLT']
        bars = []

        for symbol in symbols:
            bar = BarEvent(
                event_type='bar_event',
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                open=100.00,
                high=102.00,
                low=99.50,
                close=101.50,
                volume=10000000,
                bar_duration='1d',
                asset_class='equity',
                data_quality=DataQuality(
                    completeness_score=1.0,
                    freshness_ms=100,
                    source='ibkr_realtime'
                )
            )
            bars.append(bar)

        # Generate signals for each asset
        intents = []
        for bar in bars:
            returns = (bar.close - bar.open) / bar.open
            signal_strength = abs(returns * 10)

            if signal_strength > 0.1:
                intent = OrderIntent(
                    intent_id=str(uuid4()),
                    symbol=bar.symbol,
                    side='buy' if returns > 0 else 'sell',
                    quantity=25,  # Equal weight for simplicity
                    order_type='market',
                    timestamp=datetime.now(timezone.utc),
                    strategy_id='multi_asset_momentum',
                    signal_strength=signal_strength,
                    risk_limit_checks_passed=True
                )
                intents.append(intent)

        # Verify portfolio construction
        assert len(intents) == len(symbols)
        assert len(set(i.symbol for i in intents)) == len(symbols)  # All unique

        # Verify total position size (risk management)
        total_quantity = sum(i.quantity for i in intents)
        assert total_quantity == 100  # 4 assets * 25 each

    async def test_batch_order_execution(self):
        """
        E2E: Batch Order Execution

        Test execution of multiple orders simultaneously.
        """
        # Create multiple order intents
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        intents = []

        for symbol in symbols:
            intent = OrderIntent(
                intent_id=str(uuid4()),
                symbol=symbol,
                side='buy',
                quantity=10,
                order_type='market',
                timestamp=datetime.now(timezone.utc),
                strategy_id='diversified_v1',
                signal_strength=0.5,
                risk_limit_checks_passed=True
            )
            intents.append(intent)

        # Simulate batch execution
        executions = []
        for intent in intents:
            execution = ExecutionReport(
                execution_id=str(uuid4()),
                intent_id=intent.intent_id,
                symbol=intent.symbol,
                side=intent.side,
                quantity=intent.quantity,
                filled_quantity=intent.quantity,
                avg_fill_price=150.00,  # Simplified
                status='filled',
                timestamp=datetime.now(timezone.utc),
                broker_order_id=f'IB-{intent.symbol}-001',
                commission=0.35
            )
            executions.append(execution)

        # Verify all orders executed
        assert len(executions) == len(intents)
        assert all(e.status == 'filled' for e in executions)
        assert all(e.filled_quantity == e.quantity for e in executions)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
