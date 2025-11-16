"""
End-to-End (E2E) Test Suite

Comprehensive E2E tests for the algo-trading system covering:
- Full trading loop (data → signal → order → execution)
- Kill-switch activation scenarios
- Order lifecycle management
- Market regime transitions
- System recovery scenarios

Test Categories:
- test_trading_loop.py: Complete pipeline tests
- test_kill_switches.py: Risk management kill-switch tests
- test_order_lifecycle.py: Order state transitions and regime handling
- test_recovery_scenarios.py: System restart and failure recovery

All E2E tests are marked with @pytest.mark.e2e decorator.
Run with: pytest tests/e2e/ -v -m e2e
"""

__all__ = [
    'test_trading_loop',
    'test_kill_switches',
    'test_order_lifecycle',
    'test_recovery_scenarios',
]
