# Database Integration Plan
## TimescaleDB + PostgreSQL Integration for Algo-Trade System

**תאריך:** 2025-11-17
**גרסה:** 1.0
**מצב:** 📋 PLANNING DOCUMENT
**Estimated Effort:** 2-3 weeks (L size)

---

## 🎯 מטרה

אינטגרציה מלאה של Database לאחסון:
- **Historical Market Data** - נתונים היסטוריים (bars, ticks, OFI events)
- **Live Trading Data** - נתוני מסחר real-time
- **Positions & P&L** - פוזיציות, P&L, ביצועים
- **Logs & Audit Trail** - לוגים, רשימות ביקורת
- **Backtest Results** - תוצאות backtests

**למה TimescaleDB?**
- Built on PostgreSQL (SQL + ACID)
- Optimized for time-series data
- Automatic partitioning
- Compression (90%+ savings)
- Continuous aggregates (fast queries)
- Excellent for financial data

---

## 📊 ארכיטקטורה

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Sources                            │
│  (IBKR, Market Data APIs, Internal Signals)                 │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                  Kafka Message Bus                          │
│  (market_events, order_intents, exec_reports)               │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                 DB Writer Service                           │
│  (Batch Insert, Deduplication, Schema Validation)           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│           TimescaleDB (PostgreSQL 15+)                      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Market Data  │  │ Trading Data │  │  Analytics   │     │
│  │ (Hypertables)│  │ (Orders, P&L)│  │(Backtests)   │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│          Readers (Strategy, Analytics, API)                 │
│  - Data Plane: Historical bars for signals                 │
│  - Strategy Plane: Backtest data                           │
│  - API: Dashboard queries                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🗃️ Schema Design

### 1. Market Data Schema

#### `market_bars` (Hypertable)
```sql
CREATE TABLE market_bars (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,  -- '1min', '5min', '1hour', '1day'
    open DECIMAL(15, 4) NOT NULL,
    high DECIMAL(15, 4) NOT NULL,
    low DECIMAL(15, 4) NOT NULL,
    close DECIMAL(15, 4) NOT NULL,
    volume BIGINT NOT NULL,
    vwap DECIMAL(15, 4),
    num_trades INTEGER,
    PRIMARY KEY (time, symbol, timeframe)
);

-- Create hypertable
SELECT create_hypertable('market_bars', 'time', chunk_time_interval => INTERVAL '1 day');

-- Create indexes
CREATE INDEX idx_market_bars_symbol ON market_bars (symbol, time DESC);
CREATE INDEX idx_market_bars_timeframe ON market_bars (timeframe, time DESC);

-- Enable compression (after 7 days)
ALTER TABLE market_bars SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol,timeframe',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('market_bars', INTERVAL '7 days');

-- Retention policy (keep 2 years of data)
SELECT add_retention_policy('market_bars', INTERVAL '2 years');
```

#### `market_ticks` (Hypertable)
```sql
CREATE TABLE market_ticks (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(15, 4) NOT NULL,
    size INTEGER NOT NULL,
    bid DECIMAL(15, 4),
    ask DECIMAL(15, 4),
    bid_size INTEGER,
    ask_size INTEGER,
    exchange VARCHAR(20),
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('market_ticks', 'time', chunk_time_interval => INTERVAL '1 hour');

-- Aggressive compression for ticks (lots of data)
ALTER TABLE market_ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('market_ticks', INTERVAL '1 day');
SELECT add_retention_policy('market_ticks', INTERVAL '90 days');  -- Keep 3 months
```

#### `ofi_events` (Hypertable)
```sql
CREATE TABLE ofi_events (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    ofi_value DECIMAL(10, 6) NOT NULL,
    bid_volume BIGINT,
    ask_volume BIGINT,
    imbalance DECIMAL(10, 6),
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('ofi_events', 'time');
```

---

### 2. Trading Data Schema

#### `orders` (Regular table + partitioning)
```sql
CREATE TABLE orders (
    order_id UUID PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- 'BUY', 'SELL'
    quantity INTEGER NOT NULL,
    order_type VARCHAR(20) NOT NULL,  -- 'MARKET', 'LIMIT', 'STOP'
    limit_price DECIMAL(15, 4),
    status VARCHAR(20) NOT NULL,  -- 'PENDING', 'FILLED', 'CANCELLED', 'REJECTED'
    filled_quantity INTEGER DEFAULT 0,
    avg_fill_price DECIMAL(15, 4),
    commission DECIMAL(10, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT orders_quantity_positive CHECK (quantity > 0)
);

CREATE INDEX idx_orders_time ON orders (time DESC);
CREATE INDEX idx_orders_symbol ON orders (symbol, time DESC);
CREATE INDEX idx_orders_status ON orders (status, time DESC);
```

#### `executions` (Hypertable)
```sql
CREATE TABLE executions (
    execution_id UUID PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL,
    order_id UUID NOT NULL REFERENCES orders(order_id),
    symbol VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(15, 4) NOT NULL,
    commission DECIMAL(10, 2),
    exchange VARCHAR(20),
    exec_type VARCHAR(20),  -- 'PARTIAL', 'FULL'
    CONSTRAINT executions_quantity_positive CHECK (quantity > 0)
);

SELECT create_hypertable('executions', 'time');
```

#### `positions` (Materialized view + updates)
```sql
CREATE TABLE positions_snapshot (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    avg_price DECIMAL(15, 4) NOT NULL,
    market_value DECIMAL(15, 2),
    unrealized_pnl DECIMAL(15, 2),
    realized_pnl DECIMAL(15, 2),
    PRIMARY KEY (time, symbol)
);

SELECT create_hypertable('positions_snapshot', 'time');

-- Continuous aggregate for current positions
CREATE MATERIALIZED VIEW positions_current
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS bucket,
    symbol,
    last(quantity, time) AS quantity,
    last(avg_price, time) AS avg_price,
    last(market_value, time) AS market_value
FROM positions_snapshot
GROUP BY bucket, symbol
WITH NO DATA;

SELECT add_continuous_aggregate_policy('positions_current',
    start_offset => INTERVAL '1 hour',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

#### `pnl_daily` (Hypertable)
```sql
CREATE TABLE pnl_daily (
    date DATE PRIMARY KEY,
    realized_pnl DECIMAL(15, 2) NOT NULL,
    unrealized_pnl DECIMAL(15, 2) NOT NULL,
    total_pnl DECIMAL(15, 2) NOT NULL,
    nav DECIMAL(15, 2) NOT NULL,
    sharpe_30d DECIMAL(8, 4),
    max_drawdown DECIMAL(8, 4),
    num_trades INTEGER,
    win_rate DECIMAL(5, 2)
);
```

---

### 3. Analytics Schema

#### `backtest_results` (Regular table)
```sql
CREATE TABLE backtest_results (
    backtest_id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    strategy VARCHAR(50) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DECIMAL(15, 2) NOT NULL,
    final_capital DECIMAL(15, 2) NOT NULL,
    total_return DECIMAL(8, 4),
    sharpe_ratio DECIMAL(8, 4),
    max_drawdown DECIMAL(8, 4),
    num_trades INTEGER,
    win_rate DECIMAL(5, 2),
    profit_factor DECIMAL(8, 4),
    config JSONB,  -- Strategy config
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_backtest_strategy ON backtest_results (strategy, created_at DESC);
```

#### `backtest_trades` (Hypertable)
```sql
CREATE TABLE backtest_trades (
    trade_id UUID PRIMARY KEY,
    backtest_id UUID NOT NULL REFERENCES backtest_results(backtest_id) ON DELETE CASCADE,
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    entry_price DECIMAL(15, 4),
    exit_price DECIMAL(15, 4),
    pnl DECIMAL(15, 2),
    commission DECIMAL(10, 2)
);

SELECT create_hypertable('backtest_trades', 'time');
CREATE INDEX idx_backtest_trades_backtest_id ON backtest_trades (backtest_id, time);
```

---

### 4. Audit & Logs Schema

#### `audit_log` (Hypertable)
```sql
CREATE TABLE audit_log (
    time TIMESTAMPTZ NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- 'ORDER_PLACED', 'RISK_LIMIT_HIT', 'KILL_SWITCH', etc.
    severity VARCHAR(20) NOT NULL,  -- 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    user_id VARCHAR(50),
    details JSONB,
    PRIMARY KEY (time, event_type)
);

SELECT create_hypertable('audit_log', 'time');
CREATE INDEX idx_audit_log_event_type ON audit_log (event_type, time DESC);
CREATE INDEX idx_audit_log_severity ON audit_log (severity, time DESC);

-- Retention: keep 5 years (regulatory)
SELECT add_retention_policy('audit_log', INTERVAL '5 years');
```

---

## 🔧 Implementation Plan

### Phase 1: Infrastructure Setup (Week 1)

**Tasks:**
1. **Docker Setup**
   ```yaml
   # docker-compose.yml
   services:
     timescaledb:
       image: timescale/timescaledb:latest-pg15
       ports:
         - "5432:5432"
       environment:
         POSTGRES_DB: algotradedb
         POSTGRES_USER: algotrader
         POSTGRES_PASSWORD: ${DB_PASSWORD}
       volumes:
         - timescaledb_data:/var/lib/postgresql/data
         - ./db/init:/docker-entrypoint-initdb.d
       healthcheck:
         test: ["CMD-SHELL", "pg_isready -U algotrader"]
         interval: 10s
         timeout: 5s
         retries: 5

   volumes:
     timescaledb_data:
   ```

2. **Migration Tool**
   - Use Alembic for schema migrations
   - Create initial migration: `alembic init alembic`
   - First migration: create all tables

3. **Connection Pooling**
   - Use SQLAlchemy with asyncpg
   - Connection pool: min=5, max=20

**Deliverables:**
- [ ] docker-compose.yml with TimescaleDB
- [ ] Alembic setup and initial migration
- [ ] Connection pool configuration

---

### Phase 2: DB Client Library (Week 1-2)

**Tasks:**
1. **Create `db_client.py`**
   ```python
   from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
   from sqlalchemy.orm import sessionmaker
   import asyncpg

   class DBClient:
       def __init__(self, connection_string):
           self.engine = create_async_engine(
               connection_string,
               pool_size=20,
               max_overflow=10,
               pool_pre_ping=True,
           )
           self.SessionLocal = sessionmaker(
               self.engine,
               class_=AsyncSession,
               expire_on_commit=False,
           )

       async def batch_insert_bars(self, bars: List[Dict]):
           """Batch insert market bars."""
           async with self.SessionLocal() as session:
               # Use COPY for fast bulk insert
               await session.execute(...)

       async def get_historical_bars(
           self, symbol: str, start: datetime, end: datetime, timeframe: str
       ):
           """Get historical bars."""
           async with self.SessionLocal() as session:
               result = await session.execute(...)
               return result.fetchall()
   ```

2. **Implement CRUD operations**
   - Market Data: insert_bars(), get_bars(), get_ticks()
   - Trading: insert_order(), update_order(), get_positions()
   - Analytics: insert_backtest(), get_backtest_results()

3. **Batch Insert Optimization**
   - Use PostgreSQL COPY for bulk inserts (100x faster)
   - Buffer messages before insert (batch size: 1000)
   - Async writes to avoid blocking

**Deliverables:**
- [ ] `shared/db/db_client.py` - DB client library
- [ ] `shared/db/models.py` - SQLAlchemy models
- [ ] `shared/db/queries.py` - Common queries
- [ ] Unit tests for DB client

---

### Phase 3: Kafka → DB Writer Service (Week 2)

**Tasks:**
1. **Create `db_writer_service.py`**
   - Consume from Kafka topics
   - Validate messages (schema validation)
   - Batch insert to DB
   - Handle duplicates (upsert)

2. **Buffering & Batching**
   - Buffer messages in memory
   - Flush every N messages or M seconds
   - Backpressure handling

3. **Error Handling**
   - Retry failed inserts (3 attempts)
   - Dead Letter Queue for persistent failures
   - Log errors to audit_log table

**Deliverables:**
- [ ] `shared/db/writer_service.py`
- [ ] Configuration for batch size, flush interval
- [ ] Monitoring metrics (insert rate, errors)

---

### Phase 4: Integration with Planes (Week 2-3)

**Tasks:**
1. **Data Plane Integration**
   - Write market_bars to DB
   - Write market_ticks to DB
   - Read historical data for signals

2. **Strategy Plane Integration**
   - Write backtest results to DB
   - Read historical data for backtesting

3. **Order Plane Integration**
   - Write orders to DB
   - Write executions to DB
   - Update positions_snapshot

**Deliverables:**
- [ ] Updated Data Plane with DB writes
- [ ] Updated Strategy Plane with DB reads/writes
- [ ] Updated Order Plane with DB writes

---

### Phase 5: Querying & Analytics (Week 3)

**Tasks:**
1. **Create Continuous Aggregates**
   - Daily P&L aggregates
   - Hourly volume aggregates
   - 1-minute OHLCV from ticks

2. **Create Materialized Views**
   - Current positions view
   - Recent trades view (last 24h)
   - Performance metrics view

3. **API Endpoints**
   - GET /api/v1/historical/bars
   - GET /api/v1/positions/current
   - GET /api/v1/pnl/daily

**Deliverables:**
- [ ] Continuous aggregates configured
- [ ] Materialized views created
- [ ] API endpoints for querying

---

### Phase 6: Performance Optimization (Week 3)

**Tasks:**
1. **Indexing**
   - Create indexes on frequently queried columns
   - Analyze slow queries with EXPLAIN
   - Add composite indexes where needed

2. **Compression**
   - Enable compression on old chunks
   - Verify compression ratios (target: >90%)

3. **Query Optimization**
   - Use time_bucket for aggregations
   - Use continuous aggregates for common queries
   - Cache frequent queries (Redis)

**Deliverables:**
- [ ] Optimized indexes
- [ ] Compression policies active
- [ ] Query performance benchmarks

---

## 📊 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| **Insert Throughput** | >10,000 bars/sec | Using COPY, batched |
| **Query Latency (recent)** | <50ms | Last 1 hour data |
| **Query Latency (historical)** | <500ms | 1 year data |
| **Compression Ratio** | >90% | For bars >7 days old |
| **Storage Growth** | <10 GB/month | With compression |
| **Connection Pool** | 20 connections | Max concurrent |

---

## 🔒 Security

1. **Authentication**
   - Use strong passwords
   - Rotate credentials every 90 days
   - Store passwords in environment variables

2. **Network**
   - Database not exposed to internet
   - Only accessible from application network
   - Use SSL/TLS for connections

3. **Permissions**
   - Read-only user for analytics
   - Read-write user for services
   - Admin user for migrations only

4. **Backups**
   - Daily full backups to S3
   - Point-in-time recovery enabled
   - Test restore monthly

---

## 📝 Monitoring & Alerts

**Metrics to Track:**
- Insert rate (rows/sec)
- Query latency (p50, p95, p99)
- Connection pool usage
- Disk usage
- Replication lag (if using replicas)

**Alerts:**
- Disk usage >80%
- Query latency >1s
- Failed inserts >10/min
- Connection pool exhausted

---

## 🧪 Testing

1. **Unit Tests**
   - Test all CRUD operations
   - Test batch inserts
   - Test error handling

2. **Integration Tests**
   - Test Kafka → DB flow
   - Test concurrent writes
   - Test query performance

3. **Load Tests**
   - Insert 100,000 bars/sec
   - Query under load
   - Measure degradation

---

## 📚 References

- [TimescaleDB Docs](https://docs.timescale.com/)
- [PostgreSQL Best Practices](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic Migrations](https://alembic.sqlalchemy.org/en/latest/)

---

**נוצר על ידי:** Claude Code (AI Assistant)
**תאריך:** 2025-11-17
**גרסה:** 1.0
**מצב:** 📋 PLANNING DOCUMENT

**הערה:** מסמך זה הוא תכנון ראשוני ודורש עדכון לפי התקדמות היישום.

---

**Next Steps:**
1. Review and approve plan
2. Start with Phase 1 (Infrastructure Setup)
3. Iterate based on feedback

---

**End of Database Integration Plan v1.0**
