# Paper Trading Environment Setup Plan
## 🎯 Mission: Full Paper Trading System Running End-to-End

**Target:** Complete distributed Paper Trading environment with Kafka + IBKR Paper account running for extended period

**Duration:** 4 weeks (estimated)

**Current Status:** Infrastructure design complete, implementation pending

---

## 📊 Current State Assessment

### ✅ What's Ready (70% Architecture):
- ✅ Message contracts (5 types: BarEvent, TickEvent, OFIEvent, OrderIntent, ExecutionReport)
- ✅ Schema validation framework (Pydantic + JSON Schema)
- ✅ Dead Letter Queue (DLQ) handling
- ✅ Plane-specific validators (Data, Strategy, Order)
- ✅ IBKR interface specification (8 operations, 12 error codes)
- ✅ 8-stage pre-live validation framework
- ✅ Unit tests (35+ tests, 628 lines)
- ✅ Mock clients for testing

### ❌ Critical Gaps (30% Implementation):
- ❌ **Kafka Implementation:** Only 5-line stub (no producer/consumer)
- ❌ **IBKR Implementation:** Only stubs (no actual broker connection)
- ❌ **Dependencies:** Missing `ib_insync`, `kafka-python`/`confluent-kafka`
- ❌ **Deployment:** No Docker/docker-compose infrastructure
- ❌ **IBKR Paper Account:** Not created yet
- ❌ **Configuration:** No environment-specific configs (dev/staging/paper)
- ❌ **Monitoring:** Prometheus/Grafana not integrated with Kafka

---

## 🗓️ 4-Week Phased Approach

### Phase 1: Core Infrastructure (Week 1) - FOUNDATION
**Goal:** Get basic messaging and broker connectivity working

#### 1.1 Dependencies & Requirements (Day 1)
- [ ] Add Kafka client library to requirements.txt
  - Decision: `confluent-kafka` (production-grade) vs `kafka-python` (simpler)
  - Recommendation: `confluent-kafka>=2.3.0` for performance
- [ ] Add IBKR client: `ib_insync>=0.9.86`
- [ ] Add monitoring: `prometheus-client>=0.17.0`
- [ ] Add async support: `aiokafka>=0.9.0`
- [ ] Update requirements-dev.txt with testing tools
- [ ] Run `pip install -r requirements.txt` and verify no conflicts

**Deliverable:** Updated requirements.txt with all dependencies

#### 1.2 Kafka Infrastructure (Days 2-3)
- [ ] Create `docker-compose.yml` with:
  - Kafka broker (Confluent Platform or Apache Kafka)
  - Zookeeper (required for Kafka)
  - Schema Registry (optional but recommended)
  - Kafka UI (for debugging - e.g., `provectuslabs/kafka-ui`)
- [ ] Create `.env.example` with all required environment variables
- [ ] Create topic initialization script:
  - `market_raw` (retention: 8h, ordering: per-partition)
  - `market_events` (retention: 24h, compaction: true, keys: conid)
  - `ofi_events` (retention: 24h)
  - `order_intents` (retention: 6h, acks: all)
  - `exec_reports` (retention: 7d)
  - DLQ topics: `dlq_market_events`, `dlq_order_intents`, `dlq_execution_reports`
- [ ] Test: `docker-compose up -d && kafka-topics.sh --list --bootstrap-server localhost:9092`

**Deliverable:** Working local Kafka cluster with all topics created

#### 1.3 Implement KafkaAdapter (Days 4-5)
**File:** `/home/user/Algo-trade/data_plane/bus/kafka_adapter.py`

Current state: 5-line stub
Target: Full implementation (~200-300 lines)

**Core Functionality:**
- [ ] Producer implementation:
  - Async/await support with `aiokafka`
  - Batching (batch.size=16384, linger.ms=10)
  - Compression (snappy or lz4)
  - Retry logic (max 3 attempts, exponential backoff)
  - Error handling and logging
- [ ] Consumer implementation:
  - Consumer group management
  - Offset tracking (auto-commit with 5s interval)
  - Message deserialization
  - Error handling for malformed messages → DLQ
- [ ] Health check implementation:
  - Broker connectivity check
  - Topic existence validation
  - Consumer lag monitoring
  - Producer queue status
- [ ] Configuration:
  - Bootstrap servers from env var
  - Security protocol (PLAINTEXT for dev, SASL_SSL for prod)
  - Client ID generation
  - Timeout configurations

**Code Structure:**
```python
class KafkaAdapter:
    def __init__(self, cfg: KafkaConfig):
        self.producer = AIOKafkaProducer(...)
        self.consumer = AIOKafkaConsumer(...)
        self.bootstrap_servers = cfg.bootstrap_servers
        self.client_id = cfg.client_id

    async def connect(self):
        """Initialize producer and consumer connections"""
        await self.producer.start()
        await self.consumer.start()

    async def publish(self, topic: str, msg: dict, key: Optional[str] = None):
        """Publish message to topic with validation"""
        # Serialize to JSON
        # Send with key for partitioning
        # Handle errors → DLQ if validation fails

    async def consume(self, topic: str, group_id: str) -> AsyncIterator[dict]:
        """Consume messages from topic"""
        # Subscribe to topic
        # Deserialize messages
        # Yield validated messages
        # Route invalid → DLQ

    async def health(self) -> dict:
        """Return health status"""
        return {
            "connected": self._is_connected(),
            "topics": await self._list_topics(),
            "consumer_lag": await self._get_consumer_lag(),
            "producer_queue_size": self.producer.queue_size()
        }
```

**Testing:**
- [ ] Unit tests: test producer, consumer, health check
- [ ] Integration test: publish → consume roundtrip
- [ ] Error tests: broker down, invalid message, DLQ routing

**Deliverable:** Fully functional KafkaAdapter with tests

#### 1.4 IBKR Handler Implementation (Days 6-7)
**Files:**
- `/home/user/Algo-trade/algo_trade/core/execution/IBKR_handler.py`
- `/home/user/Algo-trade/order_plane/broker/ibkr_exec_client.py`
- `/home/user/Algo-trade/data_plane/connectors/ibkr/client.py`

Current state: 34-line stub
Target: Full implementation (~400-500 lines total)

**Core Functionality:**
- [ ] Connection management:
  - Connect to TWS/IB Gateway (host, port, client_id)
  - Reconnection logic (max 3 retries, exponential backoff)
  - Connection state machine (DISCONNECTED → CONNECTING → CONNECTED → ERROR)
  - Health monitoring
- [ ] Order execution operations:
  - `place_order(order_intent: OrderIntent) -> str` (returns order_id)
  - `cancel_order(order_id: str) -> bool`
  - `get_order_status(order_id: str) -> ExecutionReport`
  - `poll_reports() -> List[ExecutionReport]` (async polling for fills)
- [ ] Market data operations:
  - `subscribe_rt(symbol: str, bar_size: str) -> None`
  - `request_hist(symbol: str, duration: str, bar_size: str) -> List[BarEvent]`
  - Handle real-time updates → publish to `market_raw` topic
- [ ] Account operations:
  - `get_account_info() -> dict` (balance, buying power, etc.)
  - `get_positions() -> List[dict]` (current positions)
- [ ] Error handling:
  - Map IBKR error codes (100, 103, 201, 321, 504, 1100, etc.)
  - Rate limiting: Token bucket (50 orders/sec, 60 hist requests/10min)
  - Pacing limits enforcement
  - Error → DLQ for invalid orders

**Configuration (env vars):**
```bash
IBKR_HOST=127.0.0.1
IBKR_PORT=4002              # Paper: 4002 (Gateway) or 7497 (TWS)
IBKR_CLIENT_ID=1
IBKR_ACCOUNT_ID=DU1234567   # Paper account (DU prefix)
IBKR_PAPER_MODE=true
IBKR_TIMEOUT_SEC=10
IBKR_RECONNECT_ATTEMPTS=3
```

**Testing:**
- [ ] Unit tests with mock IBKR client (use existing `/tests/e2e/ibkr_mock.py`)
- [ ] Integration test: connect → place order → get status → cancel
- [ ] Error tests: rate limit, insufficient funds, connection loss

**Deliverable:** Fully functional IBKR client with connection and order execution

---

### Phase 2: Integration & Configuration (Week 2) - CONNECTIVITY
**Goal:** Connect all planes together via Kafka, configure environments

#### 2.1 Configuration Management (Days 1-2)
- [ ] Create environment-specific config files:
  - `config/dev.yaml` - Local development (mock broker)
  - `config/paper.yaml` - Paper trading (IBKR Paper account)
  - `config/prod.yaml` - Production (placeholder, requires approval)
- [ ] Create comprehensive `.env.example`:
  ```bash
  # Kafka Configuration
  KAFKA_BOOTSTRAP_SERVERS=localhost:9092
  KAFKA_SECURITY_PROTOCOL=PLAINTEXT
  KAFKA_CLIENT_ID=algo-trade-client
  KAFKA_CONSUMER_GROUP=algo-trade-group

  # IBKR Configuration
  IBKR_HOST=127.0.0.1
  IBKR_PORT=4002
  IBKR_ACCOUNT_ID=DU1234567
  IBKR_PAPER_MODE=true

  # Application Configuration
  ENVIRONMENT=paper
  LOG_LEVEL=INFO
  METRICS_PORT=9090

  # Vault (optional - for secure credentials)
  USE_VAULT=false
  VAULT_ADDR=https://vault.example.com
  VAULT_TOKEN=
  ```
- [ ] Update `/data_plane/config/utils.py` to support all env vars
- [ ] Create config validation script to check all required vars are set

**Deliverable:** Complete configuration system for all environments

#### 2.2 End-to-End Data Flow (Days 3-4)
**Goal:** Implement complete message flow from IBKR → Kafka → Strategy → Order → IBKR

**Data Plane → Kafka:**
- [ ] Implement historical data producer:
  - File: `/data_plane/connectors/ibkr/producers_hist.py`
  - Fetch historical bars from IBKR
  - Normalize to `BarEvent` format
  - Validate with `DataPlaneValidator`
  - Publish to `market_events` topic
  - Invalid → `dlq_market_events`
- [ ] Implement real-time data producer:
  - File: `/data_plane/connectors/ibkr/producers_rt.py`
  - Subscribe to real-time bars from IBKR
  - Normalize to `BarEvent` or `TickEvent`
  - Validate and publish to `market_events`
- [ ] Test: Verify messages appear in Kafka topic (use Kafka UI)

**Strategy Plane ← Kafka → Order Plane:**
- [ ] Strategy Plane:
  - Consume from `market_events` topic
  - Generate signals (OFI calculation)
  - Create `OrderIntent` messages
  - Validate with `StrategyPlaneValidator`
  - Publish to `order_intents` topic
- [ ] Order Plane:
  - Consume from `order_intents` topic
  - Validate with `OrderPlaneValidator`
  - Run pre-trade risk checks
  - Place order via `IBKRExecClient`
  - Poll for fills
  - Create `ExecutionReport` messages
  - Publish to `exec_reports` topic
- [ ] Test: Full roundtrip from market data → signal → order → execution

**Deliverable:** Working end-to-end message flow (can run in dev mode with mocks)

#### 2.3 Monitoring & Observability (Days 5-7)
- [ ] Add Prometheus to docker-compose.yml
- [ ] Add Grafana to docker-compose.yml
- [ ] Implement Kafka metrics export:
  - Topic lag per consumer group
  - Message rate (produce/consume per topic)
  - DLQ message count
  - Validation error rate
- [ ] Implement application metrics:
  - Order latency (intent → submit → ack → fill)
  - Fill rate (% of orders filled)
  - Rejection rate (% of orders rejected)
  - IBKR connection status
  - API rate limit usage
- [ ] Create Grafana dashboards:
  - Kafka health (topic lag, throughput)
  - Trading metrics (PnL, Sharpe, drawdown)
  - System health (latency, error rate, connection status)
- [ ] Set up alerting rules:
  - Kafka consumer lag > 1000 messages
  - Order latency p95 > 1s
  - IBKR connection down
  - DLQ message count > 10

**Deliverable:** Monitoring dashboards and alerting

---

### Phase 3: IBKR Paper Account Setup (Week 3) - CREDENTIALS
**Goal:** Create and configure real IBKR Paper account, validate connectivity

#### 3.1 Account Creation (Days 1-2)
**MANUAL STEP - Requires user action**

- [ ] **User Action Required:** Open IBKR Paper Trading account
  - Go to: https://www.interactivebrokers.com/en/trading/paper-trading.php
  - Sign up for Paper Trading account
  - Note down account ID (should start with `DU`, e.g., `DU1234567`)
  - Set up TWS or IB Gateway credentials (username/password)

- [ ] **User Action Required:** Install TWS or IB Gateway
  - Download: https://www.interactivebrokers.com/en/trading/tws.php
  - Install and configure
  - Enable API connections in settings:
    - TWS: Edit → Global Configuration → API → Settings
    - Enable "Enable ActiveX and Socket Clients"
    - Trusted IPs: 127.0.0.1
    - Master API client ID: (leave blank)
    - Read-Only API: No (we need order placement)
  - Set listening port: 4002 (Paper) or 7497 (TWS Paper)

- [ ] **Security Setup:**
  - Create secure credential storage (Vault or encrypted .env)
  - Never commit credentials to git (.gitignore .env files)
  - Use environment variables for all secrets

**Deliverable:** Active IBKR Paper account with API access

#### 3.2 Stage 6: Account Config Probe (Days 3-4)
**Reference:** `/home/user/Algo-trade/docs/IBKR_INTEGRATION_FLOW.md` (Stage 6)

**Goal:** Validate connectivity to Paper account in read-only mode

- [ ] Create Stage 6 test script:
  - File: `/tests/stages/stage6_account_probe.py`
  - Connect to IBKR Paper account
  - **Read-only operations only** (no order placement)
  - Validate:
    - Connection successful
    - Account ID correct (DU prefix)
    - Can fetch account info (balance, buying power)
    - Can fetch positions (should be empty initially)
    - Can subscribe to market data (SPY, QQQ test symbols)
    - Latency < 1s for all operations
    - No errors in error log

- [ ] Run Stage 6 test and collect evidence:
  - Capture logs
  - Take screenshots of TWS/Gateway showing connection
  - Record latency metrics
  - Document any errors or issues

- [ ] Gate Condition (must pass to proceed):
  - ✅ Connection stable for 10+ minutes
  - ✅ Can fetch real-time market data (at least 3 symbols)
  - ✅ No authentication errors
  - ✅ Account ID verified as Paper (DU prefix)

**Deliverable:** Stage 6 validation report with evidence

#### 3.3 Stage 7 Preparation (Days 5-7)
**Reference:** Stage 7 - Paper Trading Validation

**Goal:** Prepare for 6-hour Paper Trading session

- [ ] Create Stage 7 test script:
  - File: `/tests/stages/stage7_paper_trading.py`
  - Full trading loop with real Paper account
  - Strategy: Simple OFI strategy (conservative parameters)
  - Symbols: SPY, QQQ (liquid, low volatility)
  - Position limits: Max 10 shares per symbol, max $1000 gross
  - Risk checks enabled: PnL kill-switch (-$100), drawdown kill-switch (-5%)

- [ ] Define success criteria:
  - Session duration: 6 hours continuous
  - At least 10 order intents generated
  - Fill rate > 70%
  - No unhandled exceptions
  - Kafka message flow consistent
  - Latency p95 < 500ms (intent → fill)
  - No IBKR errors (except expected rejections)

- [ ] Set up monitoring for Stage 7:
  - Real-time Grafana dashboard
  - Alert on critical errors
  - Log all order intents, execution reports
  - Capture metrics: PnL, Sharpe, drawdown, fill rate, latency

- [ ] Create rollback procedure:
  - Immediate kill-switch on PnL breach
  - Cancel all open orders
  - Close all positions
  - Disconnect from IBKR
  - Logs preserved for post-mortem

**Deliverable:** Stage 7 test script ready to execute

---

### Phase 4: Paper Trading Validation (Week 4) - LIVE VALIDATION
**Goal:** Execute Stage 7 and collect production-readiness evidence

#### 4.1 Stage 7: 6-Hour Paper Trading Session (Days 1-3)
**CRITICAL: This is the main validation milestone**

**Pre-flight Checklist:**
- [ ] Kafka cluster running and healthy
- [ ] All topics created with correct configurations
- [ ] IBKR TWS/Gateway connected to Paper account
- [ ] Monitoring dashboards operational
- [ ] Rollback procedure tested
- [ ] Risk limits configured correctly
- [ ] Strategy parameters set to conservative values
- [ ] Dry-run completed successfully (1-hour test)

**Execution:**
- [ ] **Day 1:** Dry-run (1 hour)
  - Run Stage 7 script for 1 hour
  - Validate message flow
  - Check for errors
  - Adjust parameters if needed

- [ ] **Day 2:** Full 6-hour session
  - Start monitoring dashboard
  - Launch Stage 7 script
  - Monitor continuously for first 30 minutes
  - Check every hour thereafter
  - Collect metrics continuously
  - **Do not interfere unless critical error**

- [ ] **Day 3:** Analysis and reporting
  - Aggregate metrics:
    - Total orders: Intent count, submitted, filled, rejected, canceled
    - Fill rate: Filled / Submitted
    - Latency: p50, p95, p99 (intent → submit → ack → fill)
    - PnL: Realized PnL, unrealized PnL, Sharpe ratio
    - Risk metrics: Max drawdown, max position size, gross exposure
    - Errors: Count by type, DLQ messages
  - Generate Stage 7 validation report
  - Identify issues and gaps

**Success Criteria (Gate Conditions):**
- ✅ Session completed 6 hours without crash
- ✅ Fill rate ≥ 70%
- ✅ Latency p95 < 500ms (intent → fill)
- ✅ No critical errors (connection loss OK if recovered)
- ✅ Risk limits enforced (no breaches)
- ✅ PnL within expected range (positive or negative, but reasonable)
- ✅ All Kafka messages validated (DLQ rate < 1%)
- ✅ Monitoring dashboards functional

**Deliverable:** Stage 7 validation report with metrics and evidence

#### 4.2 Post-Session Analysis (Days 4-5)
- [ ] Performance review:
  - What worked well?
  - What failed or had issues?
  - Latency bottlenecks
  - Error patterns
  - Strategy performance (PnL, Sharpe)

- [ ] Code review:
  - Review all error logs
  - Identify code improvements
  - Refactor hot paths if needed
  - Add missing error handling

- [ ] Documentation:
  - Update RUNBOOK.md with operational procedures
  - Document any configuration changes
  - Record lessons learned

- [ ] Create action items:
  - List of bugs to fix
  - Performance optimizations
  - Missing features
  - Priority: P0 (must fix before next session), P1 (nice to have)

**Deliverable:** Post-session analysis report with action items

#### 4.3 Stage 8: Go-Live Decision Gate (Days 6-7)
**Reference:** `/home/user/Algo-trade/docs/GO_LIVE_DECISION_GATE.md`

**Goal:** Obtain governance sign-offs for production readiness

**Prerequisites:**
- ✅ Stage 7 completed successfully
- ✅ All P0 action items from post-session analysis fixed
- ✅ Architecture review completed
- ✅ Security review completed (secrets, API keys, firewall)
- ✅ Runbook complete and tested
- ✅ Rollback procedure tested
- ✅ Monitoring and alerting operational

**Sign-off Process:**
- [ ] **Risk Officer Sign-off:**
  - Review risk limits and kill-switches
  - Validate position sizing
  - Approve PnL/drawdown limits
  - Signature required

- [ ] **CTO/Tech Lead Sign-off:**
  - Code quality review
  - Architecture review
  - Security review
  - Infrastructure stability
  - Monitoring coverage
  - Signature required

- [ ] **Lead Trader Sign-off:**
  - Strategy performance validation
  - Paper trading results acceptable
  - Trading logic correct
  - Signature required

**Final Checklist:**
- [ ] All 8 stages completed
- [ ] All sign-offs obtained
- [ ] Production deployment plan ready
- [ ] Gradual scale-up plan: 10% capital → 30% → 100%
- [ ] Emergency contacts and escalation procedures
- [ ] Post-deployment monitoring plan (first 24h, first week)

**Decision:**
- ✅ **GO:** Proceed to production deployment with approved capital
- ❌ **NO-GO:** Additional validation required (specify gaps)

**Deliverable:** Go-Live Decision Gate document with all sign-offs

---

## 📦 Deliverables Summary

| Phase | Week | Deliverable | Owner |
|---|---|---|---|
| Phase 1 | Week 1 | Updated requirements.txt | Dev |
| Phase 1 | Week 1 | docker-compose.yml with Kafka | DevOps |
| Phase 1 | Week 1 | Fully functional KafkaAdapter | Dev |
| Phase 1 | Week 1 | IBKR Handler implementation | Dev |
| Phase 2 | Week 2 | Environment configs (dev/paper/prod) | Dev |
| Phase 2 | Week 2 | End-to-end message flow working | Dev |
| Phase 2 | Week 2 | Monitoring dashboards (Grafana) | DevOps |
| Phase 3 | Week 3 | Active IBKR Paper account | User (manual) |
| Phase 3 | Week 3 | Stage 6 validation report | Quant/Dev |
| Phase 3 | Week 3 | Stage 7 test script ready | Dev |
| Phase 4 | Week 4 | Stage 7 validation report (6h session) | Quant |
| Phase 4 | Week 4 | Post-session analysis with action items | Quant/Dev |
| Phase 4 | Week 4 | Go-Live Decision Gate with sign-offs | Risk/CTO/Trader |

---

## 🚨 Critical Path & Blockers

### Critical Path:
1. **Week 1:** Implement Kafka + IBKR (no external dependencies)
2. **Week 2:** Integrate and configure (no external dependencies)
3. **Week 3:** **BLOCKER** - Requires user to create IBKR Paper account
4. **Week 4:** Execute validation (depends on Week 3)

### Key Blocker:
**IBKR Paper Account Creation (Week 3)** - This is a manual step that requires:
- User to sign up at IBKR
- Install TWS or IB Gateway
- Configure API access
- Share credentials securely

**Recommendation:** Start this in parallel with Week 1/2 development to avoid delays.

---

## 📈 Success Metrics

### Technical Metrics:
- **Latency:** p95 < 500ms (intent → fill)
- **Fill Rate:** > 70%
- **Uptime:** 99.5% over 6-hour session
- **Error Rate:** < 1% (DLQ rate)
- **Message Throughput:** > 100 msg/sec (Kafka)

### Business Metrics:
- **Sharpe Ratio:** > 0.5 (Paper trading session)
- **Max Drawdown:** < 5%
- **PnL Variance:** Within expected range (based on strategy backtest)

### Governance Metrics:
- **Stage Completion:** 8/8 stages passed
- **Sign-offs:** 3/3 obtained (Risk Officer, CTO, Lead Trader)
- **Documentation:** 100% complete (RUNBOOK, configs, architecture)

---

## 🔄 Iterative Approach

This is NOT a waterfall project. Expected workflow:

1. **Week 1:** Build core → test → iterate → stabilize
2. **Week 2:** Integrate → test E2E → find issues → fix → re-test
3. **Week 3:** Connect to Paper account → fail → debug → retry → succeed
4. **Week 4:** Run validation → identify gaps → fix → re-run → obtain sign-offs

**Expect 20-30% of time spent on debugging and iteration.**

---

## 📚 Reference Documents

| Document | Purpose | Location |
|---|---|---|
| IBKR_INTERFACE_MAP.md | IBKR API specification | `/docs/IBKR_INTERFACE_MAP.md` |
| IBKR_INTEGRATION_FLOW.md | 8-stage validation framework | `/docs/IBKR_INTEGRATION_FLOW.md` |
| IBKR_PRELIVE_EXECUTION_SUMMARY.md | Pre-live readiness report | `/docs/IBKR_PRELIVE_EXECUTION_SUMMARY.md` |
| GO_LIVE_DECISION_GATE.md | Go-live approval template | `/docs/GO_LIVE_DECISION_GATE.md` |
| ROLLBACK_PROCEDURE.md | Emergency rollback | `/docs/ROLLBACK_PROCEDURE.md` |
| 2-WEEK_ROADMAP.md | PR timeline | `/2-WEEK_ROADMAP.md` |
| topics.yaml | Kafka topic definitions | `/contracts/topics.yaml` |

---

## 🎯 Next Immediate Actions

1. **Create GitHub Issue:** "Paper Trading Environment Setup" with this plan
2. **Break down into sub-issues:**
   - Issue #1: Implement KafkaAdapter
   - Issue #2: Implement IBKR Handler
   - Issue #3: Docker-compose infrastructure
   - Issue #4: End-to-end integration
   - Issue #5: IBKR Paper account setup
   - Issue #6: Stage 6 validation
   - Issue #7: Stage 7 validation
   - Issue #8: Go-Live Decision Gate
3. **Assign owners and start Week 1 tasks**

---

## 📝 Notes

- This plan assumes 1-2 developers working full-time
- IBKR Paper account creation is manual and may take 1-3 business days for approval
- Kafka and monitoring setup is one-time effort, can be reused for all environments
- Once Paper Trading is stable, migration to Live is primarily configuration change (port 4002→4001, account DU→U)

---

**Status:** READY TO START
**Next Step:** Begin Phase 1 - Core Infrastructure
**Estimated Start Date:** [To be filled]
**Target Completion:** 4 weeks from start
