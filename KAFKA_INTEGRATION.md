# Kafka Message Bus Integration

## סקירה כללית

מערכת ה-Algo-trade משתמשת ב-Kafka Message Bus לתקשורת אסינכרונית מבוזרת בין 3 המישורים (Planes):
- **Data Plane**: מייצר אירועי שוק (market events) ואירועי OFI
- **Strategy Plane**: צורך אירועי שוק ומייצר כוונות הזמנה (order intents)
- **Order Plane**: צורך כוונות הזמנה ומייצר דוחות ביצוע (execution reports)

## ארכיטקטורה

```
┌─────────────────┐
│   Data Plane    │
│   (Producer)    │
└────────┬────────┘
         │
         ├──> market_events  ──┐
         └──> ofi_events      │
                              │
                         ┌────▼──────────┐
                         │ Strategy Plane│
                         │   (Consumer   │
                         │   & Producer) │
                         └────┬──────────┘
                              │
                              └──> order_intents ──┐
                                                   │
                                              ┌────▼────────┐
                                              │ Order Plane │
                                              │  (Consumer  │
                                              │ & Producer) │
                                              └────┬────────┘
                                                   │
                                                   └──> exec_reports
```

## Topics

| Topic | Producer | Consumer | Retention | Description |
|-------|----------|----------|-----------|-------------|
| `market_raw` | IBKR Connectors | Data Plane | 8h | נתוני שוק גולמיים מ-IBKR |
| `market_events` | Data Plane | Strategy Plane | 24h | אירועי שוק מנורמלים (BarEvent, TickEvent) |
| `ofi_events` | Data Plane | Strategy Plane | 24h | אותות Order Flow Imbalance |
| `order_intents` | Strategy Plane | Order Plane | 6h | כוונות מסחר |
| `exec_reports` | Order Plane | Strategy Plane | 7d | דוחות ביצוע |

### DLQ Topics

כל topic יש DLQ (Dead Letter Queue) משלו:
- `dlq_market_raw`
- `dlq_market_events`
- `dlq_ofi_events`
- `dlq_order_intents`
- `dlq_exec_reports`

## התקנה והרצה

### 1. התקנת Dependencies

```bash
pip install -r requirements.txt
```

Dependencies נדרשים:
- `aiokafka>=0.8.0` - Async Kafka client
- `pydantic>=2.0.0` - Message validation
- `jsonschema>=4.0.0` - Schema validation

### 2. הרצת Kafka (Development)

הרץ Kafka מקומי עם Docker Compose:

```bash
docker-compose -f docker-compose.kafka.yml up -d
```

זה יתקין:
- Zookeeper (port 2181)
- Kafka Broker (port 9092)
- Kafka UI (port 8080) - ממשק גרפי לניהול

גישה ל-Kafka UI:
```
http://localhost:8080
```

### 3. בדיקת תקינות Kafka

```bash
python scripts/kafka_health_check.py
```

פלט מצופה:
```
============================================================
Kafka Health Check
============================================================

✓ Configuration loaded
  Bootstrap servers: localhost:9092

✓ Kafka adapter initialized

✓ Connected to Kafka cluster

Topics (10):
  - dlq_exec_reports
  - dlq_market_events
  - dlq_market_raw
  - dlq_ofi_events
  - dlq_order_intents
  - exec_reports
  - market_events
  - market_raw
  - ofi_events
  - order_intents

Health Status:
  Connected: True
  Active consumers: 0

✓ Connection closed

============================================================
Health check completed successfully!
============================================================
```

### 4. הרצת המערכת

```bash
python data_plane/app/main.py
```

המערכת תתחיל את 3 המישורים במקביל:
```
🚀 Data Plane: Produces to market_events, ofi_events
🚀 Strategy Plane: Consumes market_events → Produces order_intents
🚀 Order Plane: Consumes order_intents → Produces exec_reports
```

## קונפיגורציה

### Kafka Configuration

קובץ: `data_plane/config/kafka.yaml`

```yaml
kafka:
  bootstrap_servers: "localhost:9092"
  group_id: "algo-trade-consumer-group"
  auto_offset_reset: "earliest"
  enable_auto_commit: true
  max_poll_records: 500

topics:
  market_events:
    retention: "24h"
    partitions: 6
    replication_factor: 1
```

### שינוי Kafka Broker

לשינוי כתובת ה-broker (למשל לייצור):

```yaml
kafka:
  bootstrap_servers: "kafka-prod-1:9092,kafka-prod-2:9092,kafka-prod-3:9092"
```

## שימוש ב-API

### Publishing Messages

```python
from data_plane.bus.kafka_adapter import KafkaAdapter
from data_plane.validation.message_validator import DataPlaneValidator

# Initialize
kafka_cfg = get_kafka_config()
bus = KafkaAdapter(kafka_cfg)
validator = DataPlaneValidator()

# Create and validate message
bar_data = {
    'event_type': 'bar_event',
    'symbol': 'SPY',
    'timestamp': '2025-11-17T14:30:00Z',
    'open': 450.25,
    'high': 452.80,
    'low': 449.50,
    'close': 451.75,
    'volume': 85234567,
}

# Validate
result = validator.validate_bar_event(bar_data)

if result.is_valid:
    # Publish to Kafka
    await bus.publish(
        'market_events',
        result.validated_data.dict(),
        key='SPY'  # Partition by symbol
    )
```

### Consuming Messages

```python
# Consume with validation
async for event in bus.consume('market_events'):
    result = validator.validate_market_event(event)

    if result.is_valid:
        validated_event = result.validated_data
        # Process validated event
        process_market_event(validated_event)
```

### Validation Only

```python
from contracts.schema_validator import validate_bar_event

# Quick validation
result = validate_bar_event(bar_data)

if result.is_valid:
    print("Valid!")
else:
    print(f"Errors: {result.errors}")
```

## Message Contracts

### BarEvent

```python
{
    'event_type': 'bar_event',
    'symbol': 'SPY',
    'timestamp': '2025-11-17T16:00:00Z',
    'open': 450.25,
    'high': 452.80,
    'low': 449.50,
    'close': 451.75,
    'volume': 85234567,
    'bar_duration': '1d',
    'asset_class': 'equity'
}
```

### OrderIntent

```python
{
    'event_type': 'order_intent',
    'intent_id': '550e8400-e29b-41d4-a716-446655440000',
    'symbol': 'TSLA',
    'direction': 'BUY',
    'quantity': 100,
    'order_type': 'LIMIT',
    'limit_price': 245.50,
    'timestamp': '2025-11-17T14:30:00Z',
    'strategy_id': 'COMPOSITE'
}
```

### ExecutionReport

```python
{
    'event_type': 'execution_report',
    'report_id': '660e8400-e29b-41d4-a716-446655440001',
    'intent_id': '550e8400-e29b-41d4-a716-446655440000',
    'order_id': 'IBKR_12345678',
    'symbol': 'TSLA',
    'status': 'FILLED',
    'timestamp': '2025-11-17T14:30:05Z',
    'filled_quantity': 100,
    'average_fill_price': 245.52
}
```

## Monitoring

### Kafka UI

גש ל-http://localhost:8080 לראות:
- Topics ו-partitions
- Consumer groups ו-lag
- Messages בזמן אמת
- Broker health

### Metrics

כל plane מספק metrics:

```python
# Data Plane
metrics = data_validator.get_metrics()
print(f"Validation success rate: {metrics['validation_success_rate']:.2%}")

# Kafka Adapter
kafka_metrics = bus.get_metrics()
print(f"Messages produced: {kafka_metrics['messages_produced']}")
print(f"Messages consumed: {kafka_metrics['messages_consumed']}")
```

### Logs

הפעל logging לדיבאג:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Troubleshooting

### בעיה: "Failed to connect to Kafka"

**פתרון:**
```bash
# וודא ש-Kafka רץ
docker-compose -f docker-compose.kafka.yml ps

# אם לא רץ, התחל
docker-compose -f docker-compose.kafka.yml up -d

# בדוק logs
docker-compose -f docker-compose.kafka.yml logs -f kafka
```

### בעיה: "Topic does not exist"

**פתרון:**
Topics נוצרים אוטומטית בהרצה ראשונה. אם לא:

```bash
python -c "
from data_plane.bus.kafka_adapter import KafkaAdapter
from data_plane.bus.topic_initializer import initialize_kafka_topics, get_kafka_config
import asyncio

async def create():
    cfg = get_kafka_config()
    bus = KafkaAdapter(cfg)
    await initialize_kafka_topics(bus)
    await bus.close()

asyncio.run(create())
"
```

### בעיה: "Validation failed"

בדוק את ה-DLQ topics ב-Kafka UI או דרך CLI:

```bash
# צפייה ב-DLQ
docker exec -it algo-trade-kafka kafka-console-consumer \
    --bootstrap-server localhost:9092 \
    --topic dlq_market_events \
    --from-beginning
```

### בעיה: Consumer lag גבוה

**פתרון:**
- הגדל מספר partitions
- הוסף consumers נוספים (scale out)
- אופטימיזציה של processing logic

```yaml
topics:
  market_events:
    partitions: 12  # הגדל מ-6 ל-12
```

## Production Deployment

### 1. Kafka Cluster

בפרודקשן, השתמש ב-Kafka cluster עם:
- 3+ brokers
- Replication factor של 3
- Min in-sync replicas של 2

```yaml
kafka:
  bootstrap_servers: "kafka-1:9092,kafka-2:9092,kafka-3:9092"

topics:
  order_intents:
    replication_factor: 3
    min_insync_replicas: 2
```

### 2. Security

הוסף authentication ו-encryption:

```yaml
kafka:
  security_protocol: "SASL_SSL"
  sasl_mechanism: "PLAIN"
  sasl_username: "algo-trade-user"
  sasl_password: "${KAFKA_PASSWORD}"
  ssl_ca_location: "/etc/kafka/ca-cert.pem"
```

### 3. Monitoring

השתמש ב-Prometheus + Grafana:
- JMX metrics מ-Kafka
- Custom application metrics
- Consumer lag alerts

## טסטים

הרץ unit tests:

```bash
pytest tests/test_schema_validation.py -v
```

טסט integration עם Kafka מקומי:

```bash
# התחל Kafka
docker-compose -f docker-compose.kafka.yml up -d

# הרץ integration tests
pytest tests/test_kafka_integration.py -v

# נקה
docker-compose -f docker-compose.kafka.yml down -v
```

## תיעוד נוסף

- [Message Contracts & Schema Validation](./contracts/README.md)
- [Data Plane Architecture](./data_plane/README.md)
- [Kafka Best Practices](https://kafka.apache.org/documentation/#bestpractices)

## שינויים אחרונים

**17 נובמבר 2025:**
- ✅ יישום מלא של KafkaAdapter עם aiokafka
- ✅ אינטגרציה של validators בכל המישורים
- ✅ יצירה אוטומטית של topics
- ✅ תמיכה ב-DLQ
- ✅ Docker Compose לפיתוח מקומי
- ✅ Health check utility

---

**המערכת כעת יכולה לרוץ במתווה אסינכרוני מבוזר מלא דרך Kafka!** 🚀
