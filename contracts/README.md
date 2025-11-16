# Message Contracts & Schema Validation

This directory contains the message contracts and schema validation framework for the 3-plane Kafka architecture.

## Overview

The validation framework ensures reliable communication between the Data Plane, Strategy Plane, and Order Plane by:

1. **Defining clear message contracts** using Pydantic models and JSON schemas
2. **Validating messages** at runtime before publishing to Kafka
3. **Routing invalid messages** to Dead Letter Queues (DLQ) for debugging
4. **Tracking validation metrics** for monitoring and alerting

## Message Types

### Market Data Events (Data Plane → Strategy Plane)

#### BarEvent
OHLCV candlestick data with data quality metadata.

**Required fields:**
- `symbol`: Asset symbol (e.g., "SPY", "TSLA")
- `timestamp`: Bar close timestamp (UTC)
- `open`, `high`, `low`, `close`: OHLC prices
- `volume`: Trading volume

**Validation rules:**
- `high >= open` and `high >= close`
- `low <= open` and `low <= close`
- All prices must be positive
- Symbol must match pattern `^[A-Z0-9]+$`

**Example:**
```python
from contracts.validators import BarEvent

bar = BarEvent(
    event_type='bar_event',
    symbol='SPY',
    timestamp='2025-11-07T16:00:00Z',
    open=450.25,
    high=452.80,
    low=449.50,
    close=451.75,
    volume=85234567,
    bar_duration='1d',
    asset_class='equity',
)
```

#### TickEvent
Level-1/Level-2 quote and trade data.

**Required fields:**
- `symbol`: Asset symbol
- `timestamp`: Tick timestamp (UTC)
- `bid`, `ask`: Best bid/ask prices
- `bid_size`, `ask_size`: Best bid/ask sizes

**Validation rules:**
- `ask >= bid` (positive bid-ask spread)
- All prices and sizes must be non-negative

#### OFIEvent
Order Flow Imbalance signals.

**Required fields:**
- `symbol`: Asset symbol
- `timestamp`: OFI calculation timestamp (UTC)
- `ofi_z`: Standardized OFI z-score

### Order Intent (Strategy Plane → Order Plane)

**Required fields:**
- `intent_id`: Unique UUID
- `symbol`: Asset symbol
- `direction`: "BUY" or "SELL"
- `quantity`: Order quantity (positive)
- `order_type`: "MARKET", "LIMIT", "STOP", "STOP_LIMIT", or "ADAPTIVE"
- `strategy_id`: "OFI", "ERN", "VRP", "POS", "TSX", "SIF", or "COMPOSITE"
- `timestamp`: Intent generation timestamp (UTC)

**Conditional requirements:**
- `LIMIT` orders must include `limit_price`
- `STOP` and `STOP_LIMIT` orders must include `stop_price`

**Optional fields:**
- `risk_checks`: Pre-computed risk validation results
- `execution_params`: POV cap, ADV cap, max slippage
- `metadata`: Portfolio ID, market regime

**Example:**
```python
from contracts.validators import OrderIntent
from uuid import uuid4

intent = OrderIntent(
    event_type='order_intent',
    intent_id=str(uuid4()),
    symbol='TSLA',
    direction='BUY',
    quantity=100,
    order_type='LIMIT',
    limit_price=245.50,
    timestamp='2025-11-07T14:30:00Z',
    strategy_id='COMPOSITE',
    time_in_force='DAY',
    urgency='NORMAL',
)
```

### Execution Report (Order Plane → Strategy Plane)

**Required fields:**
- `report_id`: Unique UUID
- `intent_id`: Original OrderIntent UUID
- `order_id`: Broker order ID
- `symbol`: Asset symbol
- `status`: "SUBMITTED", "ACKNOWLEDGED", "PARTIAL_FILL", "FILLED", "CANCELED", "REJECTED", "TIMEOUT", or "ERROR"
- `timestamp`: Report generation timestamp (UTC)

**Optional fields:**
- `filled_quantity`, `remaining_quantity`: Fill status
- `average_fill_price`: Average execution price
- `execution_costs`: Commission, slippage, market impact breakdown
- `latency_metrics`: Intent→Submit, Submit→Ack, Ack→Fill latencies
- `fills`: Individual fill records (for partial fills)

**Validation rules:**
- `filled_quantity <= requested_quantity`

## Usage

### Quick Start

```python
from contracts.schema_validator import validate

# Validate a message
result = validate(message_data, event_type='bar_event')

if result.is_valid:
    print("Message is valid!")
    validated_model = result.validated_data
else:
    print(f"Validation errors: {result.errors}")
```

### Data Plane Integration

```python
from data_plane.validation.message_validator import DataPlaneValidator

# Initialize validator
validator = DataPlaneValidator(
    validation_mode=ValidationMode.BOTH,
    strict_mode=True,  # Raise exceptions on errors
)

# Validate and publish BarEvent
bar_data = {...}
result = validator.validate_bar_event(bar_data)

if result.is_valid:
    # Publish to Kafka
    await bus.publish('market_events', result.validated_data.dict())
else:
    # Invalid message routed to DLQ automatically
    logger.error(f"Validation failed: {result.errors}")

# Check metrics
metrics = validator.get_metrics()
print(f"Validation success rate: {metrics['validation_success_rate']:.2%}")
```

### Order Plane Integration

```python
from order_plane.validation.message_validator import OrderPlaneValidator

validator = OrderPlaneValidator(strict_mode=True)

# Validate incoming OrderIntent
async for intent_msg in bus.consume('order_intents'):
    result = validator.validate_order_intent(intent_msg)

    if not result.is_valid:
        logger.error(f"Invalid intent: {result.errors}")
        continue

    intent = result.validated_data

    # Check risk constraints
    should_reject, reason = validator.should_reject_intent(intent)
    if should_reject:
        logger.warning(f"Rejecting intent: {reason}")
        continue

    # Execute order
    await execute_order(intent)
```

### Strategy Plane Integration

```python
from apps.strategy_loop.validation.message_validator import StrategyPlaneValidator

validator = StrategyPlaneValidator(strict_mode=True)

# Validate incoming market events
async for market_event in bus.consume('market_events'):
    result = validator.validate_market_event(market_event)

    if not result.is_valid:
        continue

    # Process valid event
    process_market_data(result.validated_data)

# Create and validate OrderIntent
intent = validator.create_order_intent(
    symbol='TSLA',
    direction='BUY',
    quantity=100,
    order_type='LIMIT',
    limit_price=245.50,
    strategy_id='COMPOSITE',
)

# Publish to Kafka
await bus.publish('order_intents', intent.dict())
```

## Validation Modes

The validator supports three modes:

1. **`ValidationMode.PYDANTIC_ONLY`**: Use only Pydantic models (faster, runtime type checking)
2. **`ValidationMode.JSON_SCHEMA_ONLY`**: Use only JSON schemas (structural validation)
3. **`ValidationMode.BOTH`** (default): Use both validators for maximum safety

```python
from contracts.schema_validator import MessageValidator, ValidationMode

# Fast validation (Pydantic only)
validator = MessageValidator(mode=ValidationMode.PYDANTIC_ONLY)

# Comprehensive validation (both)
validator = MessageValidator(mode=ValidationMode.BOTH)
```

## Dead Letter Queue (DLQ)

Invalid messages are automatically routed to DLQ topics for debugging:

- `dlq_market_events`: Invalid market data events
- `dlq_order_intents`: Invalid order intents
- `dlq_execution_reports`: Invalid execution reports

DLQ messages include:
- Original message data
- Validation errors
- Source topic
- Timestamp

## Testing

Run the validation tests:

```bash
# Run all validation tests
pytest tests/test_schema_validation.py -v

# Run specific test class
pytest tests/test_schema_validation.py::TestBarEvent -v

# Run integration tests
pytest tests/test_schema_validation.py::TestValidationIntegration -v
```

## JSON Schemas

JSON schemas are located in this directory:

- `bar_event.schema.json`: BarEvent schema
- `order_intent.schema.json`: OrderIntent schema
- `execution_report.schema.json`: ExecutionReport schema

### Validating Against JSON Schema

```python
from contracts.schema_validator import MessageValidator

validator = MessageValidator()
result = validator._validate_with_json_schema(data, 'bar_event')
```

## Kafka Topics

Message routing and retention policies:

| Topic | Retention | Use Case |
|-------|-----------|----------|
| `market_raw` | 8h | Raw IBKR data ingestion |
| `market_events` | 24h | Normalized market events (compacted by conid) |
| `ofi_events` | 24h | OFI signals |
| `order_intents` | 6h | Trading signals (acks=all for durability) |
| `exec_reports` | 7d | Execution feedback |

## Monitoring

Track validation metrics:

```python
validator = DataPlaneValidator()

# Process messages...

metrics = validator.get_metrics()
print(f"""
Validation Metrics:
- Total validations: {metrics['validation_count']}
- Errors: {metrics['validation_errors']}
- Warnings: {metrics['validation_warnings']}
- Success rate: {metrics['validation_success_rate']:.2%}
- DLQ error count: {metrics['dlq_error_count']}
""")
```

## Best Practices

1. **Always validate before publishing**: Validate messages before publishing to Kafka to prevent downstream errors

2. **Use strict mode in production**: Set `strict_mode=True` to raise exceptions on validation failures

3. **Monitor DLQ topics**: Set up alerts for messages in DLQ topics

4. **Log validation failures**: Include validation errors in structured logs for debugging

5. **Test contracts**: Write unit tests for custom validators and edge cases

6. **Version schemas**: Use semantic versioning for schema changes (currently using `schema: 1`)

## Schema Evolution

When evolving schemas:

1. **Add optional fields**: New fields should be optional to maintain backward compatibility
2. **Increment schema version**: Update the `schema` field version number
3. **Update validators**: Add new validators for new fields
4. **Test backward compatibility**: Ensure old messages still validate
5. **Deploy in order**: Deploy validators before producers

## Performance

Validation overhead is minimal:

- **Pydantic validation**: ~0.1-0.5ms per message
- **JSON Schema validation**: ~0.2-1ms per message
- **Both**: ~0.3-1.5ms per message

For high-throughput scenarios, consider:
- Using `ValidationMode.PYDANTIC_ONLY` for faster validation
- Batch validation with `validator.validate_batch()`
- Caching validated models

## Troubleshooting

### Common Validation Errors

**"High price must be >= open and close"**
- Fix: Ensure OHLC data has correct high/low values

**"LIMIT orders must specify limit_price"**
- Fix: Add `limit_price` field for LIMIT orders

**"Filled quantity cannot exceed requested"**
- Fix: Check execution report logic

**"Ask must be >= bid"**
- Fix: Validate tick data has positive bid-ask spread

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now validation will log detailed debug info
validator = MessageValidator()
result = validator.validate_message(data, 'bar_event')
```

## Contributing

When adding new message types:

1. Add Pydantic model to `validators.py`
2. Add JSON schema to `contracts/`
3. Register in `schema_validator.py` (`PYDANTIC_MODELS`, `JSON_SCHEMAS`)
4. Add validation helper function
5. Write unit tests in `tests/test_schema_validation.py`
6. Update this README

## References

- [Pydantic Documentation](https://docs.pydantic.dev/)
- [JSON Schema Specification](https://json-schema.org/)
- [Kafka Message Validation Best Practices](https://www.confluent.io/blog/5-things-every-kafka-developer-should-know/)
