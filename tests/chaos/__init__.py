"""
Chaos Engineering Tests for Algo-Trading System

This module implements resilience and chaos engineering tests to verify:
- System recovery from network failures
- Component failure isolation
- Recovery time objectives (RTO ≤30 seconds)
- Data consistency and order integrity after failures

Test Categories:
- Network chaos: disconnections, latency, packet loss
- Component failures: IBKR, Kafka, orchestrators
- Cascading failures: multi-component scenarios
- Recovery validation: RTO compliance, state consistency
"""

__all__ = [
    'ChaosIBKRClient',
    'NetworkFaultInjector',
    'RecoveryTimer',
    'StateValidator',
]
