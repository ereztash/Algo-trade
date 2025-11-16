"""
Unit tests for message schema validation.

Tests the Pydantic validators and JSON schema validation for all message types.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from contracts.validators import (
    BarEvent,
    TickEvent,
    OFIEvent,
    OrderIntent,
    ExecutionReport,
    DataQuality,
    EventMetadata,
    RiskChecks,
    ExecutionParams,
)
from contracts.schema_validator import (
    MessageValidator,
    ValidationMode,
    ValidationResult,
    validate,
    validate_bar_event,
    validate_order_intent,
    validate_execution_report,
)
from pydantic import ValidationError


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def valid_bar_event():
    """Valid BarEvent data."""
    return {
        'event_type': 'bar_event',
        'symbol': 'SPY',
        'timestamp': '2025-11-07T16:00:00Z',
        'open': 450.25,
        'high': 452.80,
        'low': 449.50,
        'close': 451.75,
        'volume': 85234567,
        'bar_duration': '1d',
        'asset_class': 'equity',
        'exchange': 'NYSE',
        'currency': 'USD',
    }


@pytest.fixture
def valid_tick_event():
    """Valid TickEvent data."""
    return {
        'event_type': 'tick_event',
        'symbol': 'SPY',
        'timestamp': '2025-11-07T14:30:05.123Z',
        'bid': 451.50,
        'ask': 451.52,
        'bid_size': 500,
        'ask_size': 300,
        'last': 451.51,
        'last_size': 100,
    }


@pytest.fixture
def valid_ofi_event():
    """Valid OFIEvent data."""
    return {
        'event_type': 'ofi_event',
        'symbol': 'SPY',
        'timestamp': '2025-11-07T14:30:05.123Z',
        'ofi_z': 2.35,
        'ofi_raw': 1500.0,
        'ofi_ma': 100.0,
        'ofi_std': 595.7,
    }


@pytest.fixture
def valid_order_intent():
    """Valid OrderIntent data."""
    return {
        'event_type': 'order_intent',
        'intent_id': '550e8400-e29b-41d4-a716-446655440000',
        'symbol': 'TSLA',
        'direction': 'BUY',
        'quantity': 100,
        'order_type': 'LIMIT',
        'limit_price': 245.50,
        'timestamp': '2025-11-07T14:30:00Z',
        'strategy_id': 'COMPOSITE',
        'time_in_force': 'DAY',
        'urgency': 'NORMAL',
    }


@pytest.fixture
def valid_execution_report():
    """Valid ExecutionReport data."""
    return {
        'event_type': 'execution_report',
        'report_id': '660e8400-e29b-41d4-a716-446655440001',
        'intent_id': '550e8400-e29b-41d4-a716-446655440000',
        'order_id': 'IBKR_12345678',
        'symbol': 'TSLA',
        'status': 'FILLED',
        'direction': 'BUY',
        'timestamp': '2025-11-07T14:30:05.500Z',
        'requested_quantity': 100,
        'filled_quantity': 100,
        'average_fill_price': 245.52,
        'commission': 1.50,
    }


# ============================================================================
# BarEvent Tests
# ============================================================================

class TestBarEvent:
    """Tests for BarEvent validation."""

    def test_valid_bar_event(self, valid_bar_event):
        """Test that a valid BarEvent passes validation."""
        bar = BarEvent(**valid_bar_event)
        assert bar.symbol == 'SPY'
        assert bar.open == 450.25
        assert bar.high == 452.80
        assert bar.low == 449.50
        assert bar.close == 451.75
        assert bar.volume == 85234567

    def test_bar_event_ohlc_consistency_valid(self):
        """Test OHLC consistency validation - valid case."""
        bar_data = {
            'event_type': 'bar_event',
            'symbol': 'SPY',
            'timestamp': '2025-11-07T16:00:00Z',
            'open': 100.0,
            'high': 105.0,  # high >= open, close
            'low': 95.0,    # low <= open, close
            'close': 102.0,
            'volume': 1000,
        }
        bar = BarEvent(**bar_data)
        assert bar.high >= bar.open
        assert bar.high >= bar.close
        assert bar.low <= bar.open
        assert bar.low <= bar.close

    def test_bar_event_ohlc_consistency_invalid_high(self):
        """Test OHLC consistency validation - high too low."""
        bar_data = {
            'event_type': 'bar_event',
            'symbol': 'SPY',
            'timestamp': '2025-11-07T16:00:00Z',
            'open': 100.0,
            'high': 98.0,   # Invalid: high < open
            'low': 95.0,
            'close': 99.0,
            'volume': 1000,
        }
        with pytest.raises(ValidationError, match="High price.*must be"):
            BarEvent(**bar_data)

    def test_bar_event_ohlc_consistency_invalid_low(self):
        """Test OHLC consistency validation - low too high."""
        bar_data = {
            'event_type': 'bar_event',
            'symbol': 'SPY',
            'timestamp': '2025-11-07T16:00:00Z',
            'open': 100.0,
            'high': 105.0,
            'low': 101.0,   # Invalid: low > open
            'close': 102.0,
            'volume': 1000,
        }
        with pytest.raises(ValidationError, match="Low price.*must be"):
            BarEvent(**bar_data)

    def test_bar_event_negative_price(self):
        """Test that negative prices are rejected."""
        bar_data = {
            'event_type': 'bar_event',
            'symbol': 'SPY',
            'timestamp': '2025-11-07T16:00:00Z',
            'open': -100.0,  # Invalid: negative price
            'high': 105.0,
            'low': 95.0,
            'close': 102.0,
            'volume': 1000,
        }
        with pytest.raises(ValidationError):
            BarEvent(**bar_data)

    def test_bar_event_with_data_quality(self, valid_bar_event):
        """Test BarEvent with data quality metadata."""
        valid_bar_event['data_quality'] = {
            'completeness_score': 1.0,
            'freshness_ms': 150,
            'source': 'ibkr_realtime',
        }
        bar = BarEvent(**valid_bar_event)
        assert bar.data_quality.completeness_score == 1.0
        assert bar.data_quality.freshness_ms == 150
        assert bar.data_quality.source == 'ibkr_realtime'


# ============================================================================
# TickEvent Tests
# ============================================================================

class TestTickEvent:
    """Tests for TickEvent validation."""

    def test_valid_tick_event(self, valid_tick_event):
        """Test that a valid TickEvent passes validation."""
        tick = TickEvent(**valid_tick_event)
        assert tick.symbol == 'SPY'
        assert tick.bid == 451.50
        assert tick.ask == 451.52
        assert tick.bid_size == 500
        assert tick.ask_size == 300

    def test_tick_event_bid_ask_spread(self):
        """Test bid-ask spread validation - ask must be >= bid."""
        tick_data = {
            'event_type': 'tick_event',
            'symbol': 'SPY',
            'timestamp': '2025-11-07T14:30:05.123Z',
            'bid': 451.50,
            'ask': 451.40,  # Invalid: ask < bid
            'bid_size': 500,
            'ask_size': 300,
        }
        with pytest.raises(ValidationError, match="Ask.*must be >= bid"):
            TickEvent(**tick_data)

    def test_tick_event_negative_size(self):
        """Test that negative sizes are rejected."""
        tick_data = {
            'event_type': 'tick_event',
            'symbol': 'SPY',
            'timestamp': '2025-11-07T14:30:05.123Z',
            'bid': 451.50,
            'ask': 451.52,
            'bid_size': -500,  # Invalid: negative size
            'ask_size': 300,
        }
        with pytest.raises(ValidationError):
            TickEvent(**tick_data)


# ============================================================================
# OrderIntent Tests
# ============================================================================

class TestOrderIntent:
    """Tests for OrderIntent validation."""

    def test_valid_order_intent(self, valid_order_intent):
        """Test that a valid OrderIntent passes validation."""
        intent = OrderIntent(**valid_order_intent)
        assert intent.symbol == 'TSLA'
        assert intent.direction == 'BUY'
        assert intent.quantity == 100
        assert intent.order_type == 'LIMIT'
        assert intent.limit_price == 245.50

    def test_order_intent_limit_requires_price(self):
        """Test that LIMIT orders require limit_price."""
        intent_data = {
            'event_type': 'order_intent',
            'intent_id': str(uuid4()),
            'symbol': 'TSLA',
            'direction': 'BUY',
            'quantity': 100,
            'order_type': 'LIMIT',
            # Missing limit_price
            'timestamp': '2025-11-07T14:30:00Z',
            'strategy_id': 'COMPOSITE',
        }
        with pytest.raises(ValidationError, match="LIMIT orders must specify limit_price"):
            OrderIntent(**intent_data)

    def test_order_intent_market_no_price(self):
        """Test that MARKET orders don't require limit_price."""
        intent_data = {
            'event_type': 'order_intent',
            'intent_id': str(uuid4()),
            'symbol': 'TSLA',
            'direction': 'BUY',
            'quantity': 100,
            'order_type': 'MARKET',
            'timestamp': '2025-11-07T14:30:00Z',
            'strategy_id': 'COMPOSITE',
        }
        intent = OrderIntent(**intent_data)
        assert intent.order_type == 'MARKET'
        assert intent.limit_price is None

    def test_order_intent_with_risk_checks(self, valid_order_intent):
        """Test OrderIntent with risk checks."""
        valid_order_intent['risk_checks'] = {
            'within_box_limit': True,
            'within_gross_limit': True,
            'within_net_limit': True,
            'pnl_kill_switch': True,
            'drawdown_kill_switch': True,
        }
        intent = OrderIntent(**valid_order_intent)
        assert intent.risk_checks.within_box_limit is True

    def test_order_intent_invalid_uuid(self):
        """Test that invalid UUIDs are rejected."""
        intent_data = {
            'event_type': 'order_intent',
            'intent_id': 'not-a-valid-uuid',  # Invalid UUID format
            'symbol': 'TSLA',
            'direction': 'BUY',
            'quantity': 100,
            'order_type': 'MARKET',
            'timestamp': '2025-11-07T14:30:00Z',
            'strategy_id': 'COMPOSITE',
        }
        with pytest.raises(ValidationError):
            OrderIntent(**intent_data)


# ============================================================================
# ExecutionReport Tests
# ============================================================================

class TestExecutionReport:
    """Tests for ExecutionReport validation."""

    def test_valid_execution_report(self, valid_execution_report):
        """Test that a valid ExecutionReport passes validation."""
        report = ExecutionReport(**valid_execution_report)
        assert report.symbol == 'TSLA'
        assert report.status == 'FILLED'
        assert report.filled_quantity == 100
        assert report.average_fill_price == 245.52

    def test_execution_report_filled_exceeds_requested(self):
        """Test that filled_quantity cannot exceed requested_quantity."""
        report_data = {
            'event_type': 'execution_report',
            'report_id': str(uuid4()),
            'intent_id': str(uuid4()),
            'order_id': 'IBKR_12345678',
            'symbol': 'TSLA',
            'status': 'FILLED',
            'timestamp': '2025-11-07T14:30:05.500Z',
            'requested_quantity': 100,
            'filled_quantity': 150,  # Invalid: filled > requested
        }
        with pytest.raises(ValidationError, match="Filled quantity.*cannot exceed"):
            ExecutionReport(**report_data)

    def test_execution_report_partial_fill(self):
        """Test ExecutionReport with partial fill."""
        report_data = {
            'event_type': 'execution_report',
            'report_id': str(uuid4()),
            'intent_id': str(uuid4()),
            'order_id': 'IBKR_12345678',
            'symbol': 'TSLA',
            'status': 'PARTIAL_FILL',
            'timestamp': '2025-11-07T14:30:05.500Z',
            'requested_quantity': 100,
            'filled_quantity': 50,
            'remaining_quantity': 50,
        }
        report = ExecutionReport(**report_data)
        assert report.status == 'PARTIAL_FILL'
        assert report.filled_quantity == 50
        assert report.remaining_quantity == 50


# ============================================================================
# MessageValidator Tests
# ============================================================================

class TestMessageValidator:
    """Tests for MessageValidator."""

    def test_validate_bar_event_pydantic(self, valid_bar_event):
        """Test validation with Pydantic only."""
        validator = MessageValidator(mode=ValidationMode.PYDANTIC_ONLY)
        result = validator.validate_message(valid_bar_event, 'bar_event')
        assert result.is_valid
        assert len(result.errors) == 0
        assert result.validated_data is not None

    def test_validate_bar_event_both(self, valid_bar_event):
        """Test validation with both Pydantic and JSON Schema."""
        validator = MessageValidator(mode=ValidationMode.BOTH)
        result = validator.validate_message(valid_bar_event, 'bar_event')
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_invalid_bar_event(self):
        """Test validation of invalid BarEvent."""
        invalid_bar = {
            'event_type': 'bar_event',
            'symbol': 'SPY',
            'timestamp': '2025-11-07T16:00:00Z',
            'open': 100.0,
            'high': 98.0,   # Invalid: high < open
            'low': 95.0,
            'close': 99.0,
            'volume': 1000,
        }
        validator = MessageValidator()
        result = validator.validate_message(invalid_bar, 'bar_event')
        assert not result.is_valid
        assert len(result.errors) > 0

    def test_validate_order_intent(self, valid_order_intent):
        """Test OrderIntent validation."""
        result = validate_order_intent(valid_order_intent)
        assert result.is_valid
        assert result.validated_data is not None

    def test_validate_execution_report(self, valid_execution_report):
        """Test ExecutionReport validation."""
        result = validate_execution_report(valid_execution_report)
        assert result.is_valid
        assert result.validated_data is not None

    def test_validate_batch(self, valid_bar_event, valid_tick_event):
        """Test batch validation."""
        validator = MessageValidator()
        messages = [valid_bar_event, valid_tick_event]
        results = validator.validate_batch(messages)
        assert len(results) == 2
        assert all(r.is_valid for r in results)

    def test_validate_json_string(self, valid_bar_event):
        """Test validation with JSON string input."""
        import json
        json_str = json.dumps(valid_bar_event)
        result = validate_bar_event(json_str)
        assert result.is_valid

    def test_validate_invalid_json(self):
        """Test validation with invalid JSON."""
        result = validate_bar_event('{"invalid": json}')
        assert not result.is_valid
        assert 'Invalid JSON' in result.errors[0]

    def test_infer_event_type(self, valid_bar_event):
        """Test event type inference from data."""
        validator = MessageValidator()
        result = validator.validate_message(valid_bar_event)  # No event_type specified
        assert result.is_valid
        assert result.event_type == 'bar_event'


# ============================================================================
# Integration Tests
# ============================================================================

class TestValidationIntegration:
    """Integration tests for validation across planes."""

    def test_data_plane_to_strategy_plane_flow(self, valid_bar_event):
        """Test message flow from Data Plane to Strategy Plane."""
        # Data Plane validates and publishes
        from data_plane.validation.message_validator import DataPlaneValidator
        data_validator = DataPlaneValidator(strict_mode=False)

        result = data_validator.validate_bar_event(valid_bar_event, raise_on_error=False)
        assert result.is_valid

        # Strategy Plane receives and validates
        from apps.strategy_loop.validation.message_validator import StrategyPlaneValidator
        strategy_validator = StrategyPlaneValidator(strict_mode=False)

        result = strategy_validator.validate_bar_event(valid_bar_event, raise_on_error=False)
        assert result.is_valid

        metrics = data_validator.get_metrics()
        assert metrics['validation_count'] == 1
        assert metrics['validation_errors'] == 0

    def test_strategy_plane_to_order_plane_flow(self, valid_order_intent):
        """Test message flow from Strategy Plane to Order Plane."""
        # Strategy Plane validates and publishes
        from apps.strategy_loop.validation.message_validator import StrategyPlaneValidator
        strategy_validator = StrategyPlaneValidator(strict_mode=False)

        result = strategy_validator.validate_order_intent(valid_order_intent, raise_on_error=False)
        assert result.is_valid

        # Order Plane receives and validates
        from order_plane.validation.message_validator import OrderPlaneValidator
        order_validator = OrderPlaneValidator(strict_mode=False)

        result = order_validator.validate_order_intent(valid_order_intent, raise_on_error=False)
        assert result.is_valid

        metrics = order_validator.get_metrics()
        assert metrics['intent_validation_count'] == 1
        assert metrics['intent_validation_errors'] == 0

    def test_order_plane_to_strategy_plane_flow(self, valid_execution_report):
        """Test message flow from Order Plane to Strategy Plane."""
        # Order Plane validates and publishes
        from order_plane.validation.message_validator import OrderPlaneValidator
        order_validator = OrderPlaneValidator(strict_mode=False)

        result = order_validator.validate_execution_report(valid_execution_report, raise_on_error=False)
        assert result.is_valid

        # Strategy Plane receives and validates
        from apps.strategy_loop.validation.message_validator import StrategyPlaneValidator
        strategy_validator = StrategyPlaneValidator(strict_mode=False)

        result = strategy_validator.validate_execution_report(valid_execution_report, raise_on_error=False)
        assert result.is_valid

        metrics = strategy_validator.get_metrics()
        assert metrics['report_validation_count'] == 1
        assert metrics['report_validation_errors'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
