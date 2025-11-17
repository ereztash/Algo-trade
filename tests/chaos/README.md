# Chaos Engineering Tests

Comprehensive chaos engineering test suite for validating system resilience before production deployment.

## Overview

This test suite implements chaos engineering principles to verify the system can:
- Recover from network failures within 30 seconds (RTO target)
- Maintain data consistency during and after failures
- Handle component failures without cascading breakdowns
- Preserve order integrity through disconnections
- Gracefully degrade when components are unavailable

## Test Categories

### 1. Network Chaos (`test_network_chaos.py`)

Tests network-level fault injection:

- **Network Disconnections**: 3s, 10s, 30s partitions
- **Latency Injection**: 100ms, 500ms, 2s, 5s delays
- **Packet Loss**: 5%, 20%, 50% loss rates
- **Combined Faults**: Multiple network issues simultaneously

**Key Metrics:**
- Recovery time from network partitions
- Throughput under high latency
- Data loss with packet loss
- Success rate with combined faults

### 2. IBKR Resilience (`test_ibkr_resilience.py`)

Tests IBKR connection resilience:

- **Connection Failures**: Disconnect/reconnect scenarios
- **Exponential Backoff**: Retry strategy validation
- **Timeout Handling**: Connection and request timeouts
- **Rate Limiting**: Rate limit detection and recovery
- **Order Placement**: Order handling during failures
- **Streaming Data**: Market data continuity

**Key Metrics:**
- Connection recovery time
- Order success rate during failures
- Data completeness during streaming
- Failed request tracking

### 3. Component Failures (`test_component_failures.py`)

Tests component-level resilience:

- **Kafka Broker**: Broker shutdown and recovery
- **Kafka Producer/Consumer**: Timeout and lag handling
- **Orchestrator**: Restart and state recovery
- **Cascading Failures**: Multi-component failures
- **Plane Isolation**: Data/Order plane independence

**Key Metrics:**
- Component recovery time
- Message buffering capacity
- State restoration accuracy
- Failure isolation effectiveness

### 4. Recovery Scenarios (`test_recovery_scenarios.py`)

Validates recovery objectives:

- **RTO Compliance**: ≤30 second recovery validation
- **State Consistency**: Order and position integrity
- **Data Completeness**: Zero/minimal data loss
- **Order Replay**: Failed order recovery
- **Graceful Operations**: Clean shutdown/restart

**Key Metrics:**
- Recovery Time Objective (RTO) compliance
- Order integrity (no duplicates/losses)
- Position accuracy (post-recovery)
- Data loss percentage

## Running the Tests

### Quick Start

Run all chaos tests:

```bash
pytest tests/chaos/ -v -m chaos
```

Run specific test category:

```bash
# Network chaos only
pytest tests/chaos/test_network_chaos.py -v

# IBKR resilience only
pytest tests/chaos/test_ibkr_resilience.py -v

# Component failures only
pytest tests/chaos/test_component_failures.py -v

# Recovery scenarios only
pytest tests/chaos/test_recovery_scenarios.py -v
```

### Advanced Usage

Run with detailed output:

```bash
pytest tests/chaos/ -v -s --tb=short
```

Run specific test:

```bash
pytest tests/chaos/test_network_chaos.py::TestNetworkDisconnection::test_network_partition_3s_recovery -v
```

Run with timeout protection:

```bash
pytest tests/chaos/ -v --timeout=600
```

Generate HTML report:

```bash
pytest tests/chaos/ -v --html=chaos-report.html --self-contained-html
```

Run parametrized tests with specific parameters:

```bash
# Test only 10s disconnect duration
pytest tests/chaos/test_recovery_scenarios.py -k "10" -v
```

### CI/CD Integration

Chaos tests run automatically:
- **Nightly**: Every night at 2 AM UTC
- **Manual**: Via workflow dispatch

GitHub Actions workflow: `.github/workflows/chaos-nightly.yml`

## Test Fixtures

### Chaos-Enabled Components

**`chaos_ibkr_client`** - IBKR client mock with fault injection:
```python
def test_example(chaos_ibkr_client):
    chaos_ibkr_client.inject_disconnect()
    chaos_ibkr_client.inject_timeout_on_next_request()
    chaos_ibkr_client.inject_slow_response(delay_ms=1000)
```

**`network_fault_injector`** - Network-level fault injection:
```python
def test_example(network_fault_injector):
    with network_fault_injector.inject_disconnect(duration_s=5.0):
        # Network is down for 5 seconds
        pass

    with network_fault_injector.inject_latency(latency_ms=500):
        # All operations delayed by 500ms
        pass

    with network_fault_injector.inject_packet_loss(loss_probability=0.20):
        # 20% of packets dropped
        pass
```

**`recovery_timer`** - Recovery time measurement:
```python
def test_example(recovery_timer):
    timer = RecoveryTimer()
    with timer:
        # Inject fault
        inject_failure()
        timer.mark_detected()

        # Recover
        timer.mark_recovery_started()
        perform_recovery()
        timer.mark_recovery_completed()

    assert timer.metrics.meets_rto  # ≤30s
    print(timer.metrics)
```

**`state_validator`** - State consistency validation:
```python
def test_example(state_validator):
    # Validate order integrity
    state_validator.validate_order_integrity(
        sent_orders=sent,
        received_orders=received,
    )

    # Validate position consistency
    state_validator.validate_position_consistency(
        expected_position={'AAPL': 100},
        actual_position={'AAPL': 100},
    )

    # Check violations
    violations = state_validator.get_violations()
    assert len(violations) == 0
```

### Configuration Fixture

**`chaos_config`** - Chaos testing configuration:
```python
{
    'rto_target_s': 30.0,
    'max_data_loss_ratio': 0.05,
    'max_retry_attempts': 5,
    'base_retry_delay_s': 1.0,
    'max_retry_delay_s': 30.0,
    'connection_timeout_s': 10.0,
    'request_timeout_s': 5.0,
    'rate_limit_per_minute': 100,
}
```

## Recovery Metrics

### Recovery Time Objective (RTO)

**Target: ≤30 seconds**

All recovery scenarios must complete within 30 seconds:

- Network partition recovery: ≤30s
- Component failure recovery: ≤30s
- Cascading failure recovery: ≤30s

Tests that exceed RTO fail with detailed metrics.

### Data Integrity

**Target: ≥95% completeness**

Maximum acceptable data loss: 5%

- Streaming data completeness: ≥95%
- Message delivery: ≥95%
- No permanent data loss

### Order Integrity

**Target: 100% (zero tolerance)**

- No duplicate orders
- No lost orders
- All orders accounted for after recovery
- Idempotent replay

### State Consistency

**Target: 100% (zero tolerance)**

- Position accuracy after recovery
- Order state correctness
- Message sequencing maintained
- No state corruption

## Interpreting Results

### Successful Test Output

```
CHAOS SCENARIO: Network Partition 3s
Fault Type: network_disconnect
============================================================

  Injected disconnect at tick 0
  Reconnected after 1 attempts

Recovery Metrics:
  Detection Time: 0.02s
  Recovery Time: 3.45s
  Meets RTO (≤30s): ✓ YES
  Data Loss: 0 events
  Order Violations: 0
  State Issues: 0

SCENARIO COMPLETED: Network Partition 3s
Duration: 3.50s
============================================================
```

### Failed Test Output

```
CHAOS SCENARIO: Network Partition 30s
Fault Type: network_disconnect
============================================================

  Injected disconnect at tick 0
  Reconnection attempts: 5

Recovery Metrics:
  Detection Time: 0.03s
  Recovery Time: 32.15s
  Meets RTO (≤30s): ✗ NO
  Data Loss: 0 events
  Order Violations: 0
  State Issues: 0

RTO VIOLATION: Recovery took 32.15s, target is 30.0s

SCENARIO FAILED: Network Partition 30s
Duration: 32.20s
============================================================
```

### Recovery Scorecard

The comprehensive scorecard shows overall system resilience:

```
============================================================
RECOVERY SCORECARD
============================================================

Quick Disconnect:
  Status: ✓ PASS
  Recovery Time: 1.23s / 30.0s
  Data Loss: 0
  Order Violations: 0

Component Restart:
  Status: ✓ PASS
  Recovery Time: 5.67s / 30.0s
  Data Loss: 0
  Order Violations: 0

Cascading Failure:
  Status: ✓ PASS
  Recovery Time: 12.34s / 30.0s
  Data Loss: 0
  Order Violations: 0

============================================================
OVERALL: 3 passed, 0 failed
Success Rate: 100%
============================================================
```

## Troubleshooting

### Common Issues

**Issue: Tests timing out**
- Solution: Increase timeout with `--timeout=1200`
- Check: System resources (CPU, memory)
- Verify: No actual network issues

**Issue: RTO violations**
- Solution: Optimize reconnection logic
- Check: Exponential backoff strategy
- Verify: No blocking operations

**Issue: Flaky tests**
- Solution: Add retry logic where appropriate
- Check: Race conditions
- Verify: Proper cleanup in fixtures

**Issue: Data loss exceeds tolerance**
- Solution: Implement buffering
- Check: Message acknowledgment
- Verify: Persistence mechanisms

### Debug Mode

Run with detailed logging:

```bash
pytest tests/chaos/ -v -s --log-cli-level=DEBUG
```

Run single test in debug mode:

```bash
pytest tests/chaos/test_network_chaos.py::test_network_partition_3s_recovery -v -s
```

## Extending the Tests

### Adding New Chaos Scenarios

1. Create test in appropriate module:

```python
@pytest.mark.chaos
@pytest.mark.slow
def test_new_chaos_scenario(chaos_ibkr_client, recovery_timer):
    """Test description"""
    with chaos_scenario("My Scenario", FaultType.NETWORK_DISCONNECT):
        timer = RecoveryTimer()
        with timer:
            # Inject fault
            chaos_ibkr_client.inject_disconnect()
            timer.mark_detected()

            # Recovery logic
            timer.mark_recovery_started()
            chaos_ibkr_client.connect()
            timer.mark_recovery_completed()

        assert timer.metrics.meets_rto
```

2. Add configuration if needed in `conftest.py`

3. Update this README with new scenario

### Adding New Fault Injectors

1. Extend `ChaosIBKRClient` or create new mock in `conftest.py`
2. Add injection methods following existing patterns
3. Add corresponding fixture
4. Document in this README

## Production Readiness Checklist

Before going live, verify:

- [ ] All chaos tests passing
- [ ] RTO met for all scenarios (≤30s)
- [ ] Data loss within tolerance (≤5%)
- [ ] Order integrity perfect (100%)
- [ ] State consistency perfect (100%)
- [ ] Cascading failures handled
- [ ] Graceful degradation working
- [ ] Recovery scorecard: 100% pass rate

## Configuration

See `contracts/resilience_config.yaml` for:
- RTO targets
- Retry policies
- Circuit breaker settings
- Rate limits
- Degradation strategies
- Health check configuration

## References

- [Chaos Engineering Principles](https://principlesofchaos.org/)
- [Netflix Chaos Monkey](https://netflix.github.io/chaosmonkey/)
- [Resilience Patterns](https://docs.microsoft.com/en-us/azure/architecture/patterns/category/resiliency)
- Project QA Gap Analysis: `docs/QA_GAP_ANALYSIS.md`
- Resilience Config: `contracts/resilience_config.yaml`

## Support

For issues or questions:
- Create GitHub issue with `chaos-testing` label
- Tag `@QA-team` or `@DevOps-team`
- Check existing chaos test results in CI/CD artifacts

## License

Part of the Algo-Trading System project.
