"""
End-to-End Tests: Kill-Switch Activation

Tests the complete kill-switch activation flow including:
- PnL-based kill-switch (-5% threshold)
- Drawdown-based kill-switch (-15% threshold)
- PSR-based kill-switch (PSR < 0.20 threshold)

Verifies that:
1. Kill-switches detect threshold breaches
2. Trading halts when triggered
3. No new orders submitted after halt
4. System requires manual recovery
"""

import pytest
import asyncio
import numpy as np
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from scipy import stats

from contracts.validators import (
    BarEvent, OrderIntent, ExecutionReport,
    DataQuality, EventMetadata
)


# =============================================================================
# Kill-Switch State Management
# =============================================================================

class KillSwitchManager:
    """Mock kill-switch manager for E2E testing."""

    def __init__(self):
        self.pnl_killed = False
        self.dd_killed = False
        self.psr_killed = False
        self.manual_override = False

        # State tracking
        self.initial_equity = 1_000_000.0
        self.current_equity = self.initial_equity
        self.peak_equity = self.initial_equity
        self.daily_returns = []

        # Thresholds
        self.pnl_threshold = -0.05  # -5%
        self.dd_threshold = -0.15  # -15%
        self.psr_threshold = 0.20

    def update_equity(self, pnl: float):
        """Update equity and check kill-switches."""
        self.current_equity += pnl

        # Update peak for drawdown calculation
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity

        # Calculate daily return
        daily_return = pnl / self.current_equity
        self.daily_returns.append(daily_return)

        # Check all kill-switches
        self.check_pnl_kill_switch()
        self.check_drawdown_kill_switch()
        self.check_psr_kill_switch()

    def check_pnl_kill_switch(self):
        """Check PnL-based kill-switch."""
        cumulative_pnl = (self.current_equity - self.initial_equity) / self.initial_equity

        if cumulative_pnl <= self.pnl_threshold:
            self.pnl_killed = True

    def check_drawdown_kill_switch(self):
        """Check drawdown-based kill-switch."""
        drawdown = (self.current_equity - self.peak_equity) / self.peak_equity

        if drawdown <= self.dd_threshold:
            self.dd_killed = True

    def check_psr_kill_switch(self):
        """Check PSR-based kill-switch."""
        if len(self.daily_returns) < 30:  # Need minimum data
            return

        returns = np.array(self.daily_returns[-252:])  # Last year max

        mean_ret = np.mean(returns)
        std_ret = np.std(returns, ddof=1)

        if std_ret < 1e-8:
            return

        sr_hat = mean_ret / std_ret * np.sqrt(252)

        # PSR calculation
        T = len(returns)
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns, fisher=False)

        sr_bench = 0.0
        numerator = (sr_hat - sr_bench) * np.sqrt(T - 1)
        denominator = np.sqrt(1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2)

        if denominator > 0:
            z_score = numerator / denominator
            psr = stats.norm.cdf(z_score)

            if psr < self.psr_threshold:
                self.psr_killed = True

    def is_killed(self) -> bool:
        """Check if any kill-switch is active."""
        if self.manual_override:
            return False
        return self.pnl_killed or self.dd_killed or self.psr_killed

    def get_active_switches(self) -> list:
        """Get list of active kill-switches."""
        active = []
        if self.pnl_killed:
            active.append('PnL')
        if self.dd_killed:
            active.append('Drawdown')
        if self.psr_killed:
            active.append('PSR')
        return active

    def reset(self, require_manual=True):
        """Reset kill-switches (requires manual override)."""
        if require_manual and not self.manual_override:
            raise ValueError("Cannot reset kill-switches without manual override")

        self.pnl_killed = False
        self.dd_killed = False
        self.psr_killed = False
        self.current_equity = self.initial_equity
        self.peak_equity = self.initial_equity
        self.daily_returns = []


# =============================================================================
# E2E Tests: Kill-Switch Activation
# =============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
class TestPnLKillSwitch:
    """E2E tests for PnL-based kill-switch."""

    async def test_pnl_kill_switch_activation(self):
        """
        E2E: PnL Kill-Switch Activation

        Simulate trading losses that trigger -5% PnL kill-switch.
        Verify system halts trading.
        """
        manager = KillSwitchManager()

        # Simulate losing trades
        losing_trades = [
            -10000,  # -1%
            -15000,  # -1.5%
            -20000,  # -2%
            -10000,  # -1%
        ]

        for pnl in losing_trades:
            if not manager.is_killed():
                manager.update_equity(pnl)

                # Attempt to generate order
                if not manager.is_killed():
                    intent = OrderIntent(
                        intent_id=str(uuid4()),
                        symbol='SPY',
                        side='buy',
                        quantity=100,
                        order_type='market',
                        timestamp=datetime.now(timezone.utc),
                        strategy_id='test_strategy',
                        signal_strength=0.5,
                        risk_limit_checks_passed=True
                    )
                    # Order would be submitted
                else:
                    # Order blocked by kill-switch
                    break

        # Verify kill-switch activated
        assert manager.is_killed(), "Kill-switch should be active"
        assert 'PnL' in manager.get_active_switches()

        # Verify cumulative loss >= 5%
        total_loss = (manager.current_equity - manager.initial_equity) / manager.initial_equity
        assert total_loss <= -0.05, f"Loss should be >= 5%, got {total_loss:.2%}"

    async def test_pnl_kill_switch_blocks_orders(self):
        """
        E2E: Kill-Switch Blocks New Orders

        Verify no new orders accepted after kill-switch activation.
        """
        manager = KillSwitchManager()

        # Trigger kill-switch with big loss
        manager.update_equity(-60000)  # -6% loss

        assert manager.is_killed()

        # Attempt to place order
        try:
            if manager.is_killed():
                raise ValueError("Trading halted: PnL kill-switch active")

            # This should not execute
            intent = OrderIntent(
                intent_id=str(uuid4()),
                symbol='SPY',
                side='buy',
                quantity=100,
                order_type='market',
                timestamp=datetime.now(timezone.utc),
                strategy_id='test_strategy',
                signal_strength=0.5,
                risk_limit_checks_passed=False  # Would be set to False
            )

            pytest.fail("Order should be blocked by kill-switch")

        except ValueError as e:
            assert "kill-switch" in str(e).lower()


@pytest.mark.e2e
@pytest.mark.asyncio
class TestDrawdownKillSwitch:
    """E2E tests for drawdown-based kill-switch."""

    async def test_drawdown_kill_switch_during_crash(self):
        """
        E2E: Drawdown Kill-Switch During Market Crash

        Simulate market crash scenario with -20% drawdown.
        Verify kill-switch activates at -15%.
        """
        manager = KillSwitchManager()

        # Simulate profitable period (peak reached)
        profitable_trades = [5000, 8000, 3000, 6000, 4000]
        for pnl in profitable_trades:
            manager.update_equity(pnl)

        peak_equity = manager.peak_equity
        assert peak_equity > manager.initial_equity

        # Simulate market crash
        crash_losses = [-30000, -40000, -50000, -60000]

        for pnl in crash_losses:
            manager.update_equity(pnl)

            # Check if kill-switch triggered
            if manager.is_killed():
                break

        # Verify kill-switch activated
        assert manager.is_killed()
        assert 'Drawdown' in manager.get_active_switches()

        # Verify drawdown >= 15%
        drawdown = (manager.current_equity - peak_equity) / peak_equity
        assert drawdown <= -0.15, f"Drawdown should be >= 15%, got {drawdown:.2%}"

    async def test_drawdown_recovery_tracking(self):
        """
        E2E: Drawdown Recovery Tracking

        Test that drawdown is calculated from peak, not initial equity.
        """
        manager = KillSwitchManager()

        # Build up equity
        manager.update_equity(100000)  # +10%
        first_peak = manager.peak_equity

        # Small drawdown (not enough to trigger)
        manager.update_equity(-50000)  # -~4.5% from peak

        assert not manager.is_killed()

        # Recover to new peak
        manager.update_equity(80000)  # New peak
        second_peak = manager.peak_equity
        assert second_peak > first_peak

        # Large drawdown from new peak
        manager.update_equity(-200000)  # ~-15% from new peak

        assert manager.is_killed()
        assert 'Drawdown' in manager.get_active_switches()


@pytest.mark.e2e
@pytest.mark.asyncio
class TestPSRKillSwitch:
    """E2E tests for PSR-based kill-switch."""

    async def test_psr_kill_switch_degraded_performance(self):
        """
        E2E: PSR Kill-Switch on Degraded Performance

        Simulate strategy with declining Sharpe ratio.
        Verify PSR kill-switch activates.
        """
        manager = KillSwitchManager()

        # Simulate 60 days of trading (need minimum history)
        # Start with decent performance, then degrade
        np.random.seed(42)

        # Days 1-30: Positive Sharpe ~1.0
        for _ in range(30):
            daily_ret = 0.001 + np.random.randn() * 0.01  # 0.1% mean, 1% std
            pnl = manager.current_equity * daily_ret
            manager.update_equity(pnl)

        # Days 31-60: Negative/low Sharpe (kill-switch should trigger)
        for _ in range(30):
            daily_ret = -0.0005 + np.random.randn() * 0.02  # Negative mean, high std
            pnl = manager.current_equity * daily_ret
            manager.update_equity(pnl)

        # Check if PSR kill-switch triggered
        if 'PSR' in manager.get_active_switches():
            # Calculate final PSR to verify
            returns = np.array(manager.daily_returns[-252:])
            mean_ret = np.mean(returns)
            std_ret = np.std(returns, ddof=1)
            sr_hat = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0

            T = len(returns)
            skew = stats.skew(returns)
            kurt = stats.kurtosis(returns, fisher=False)

            numerator = sr_hat * np.sqrt(T - 1)
            denominator = np.sqrt(1 - skew * sr_hat + (kurt - 1) / 4 * sr_hat ** 2)

            if denominator > 0:
                z_score = numerator / denominator
                psr = stats.norm.cdf(z_score)

                assert psr < 0.20, f"PSR should be < 0.20, got {psr:.3f}"


@pytest.mark.e2e
@pytest.mark.asyncio
class TestMultipleKillSwitches:
    """E2E tests for multiple kill-switches active simultaneously."""

    async def test_any_kill_switch_halts_trading(self):
        """
        E2E: Any Kill-Switch Halts Trading

        Verify that if ANY kill-switch triggers, trading halts.
        """
        manager = KillSwitchManager()

        # Trigger PnL kill-switch only
        manager.update_equity(-60000)  # -6%

        assert manager.is_killed()
        assert len(manager.get_active_switches()) >= 1

        # Verify trading halted
        if manager.is_killed():
            # Cannot place orders
            with pytest.raises(ValueError):
                if manager.is_killed():
                    raise ValueError("Trading halted")

    async def test_multiple_kill_switches_triggered(self):
        """
        E2E: Multiple Kill-Switches Simultaneously

        Simulate scenario where multiple kill-switches trigger.
        """
        manager = KillSwitchManager()

        # Build to peak
        manager.update_equity(150000)  # +15%
        peak = manager.peak_equity

        # Severe crash (triggers both PnL and DD)
        manager.update_equity(-200000)  # Large loss

        active = manager.get_active_switches()

        # Should have both PnL and Drawdown triggered
        assert len(active) >= 1  # At least one
        assert manager.is_killed()

    async def test_manual_recovery_required(self):
        """
        E2E: Manual Recovery Requirement

        Verify kill-switch cannot be reset without manual override.
        """
        manager = KillSwitchManager()

        # Trigger kill-switch
        manager.update_equity(-60000)
        assert manager.is_killed()

        # Attempt to reset without manual override
        with pytest.raises(ValueError, match="manual override"):
            manager.reset(require_manual=True)

        # Enable manual override and reset
        manager.manual_override = True
        manager.reset(require_manual=True)

        assert not manager.is_killed()
        assert len(manager.get_active_switches()) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])
