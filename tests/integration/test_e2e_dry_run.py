"""End-to-end dry-run integration test."""

import pytest
import asyncio
from apps.strategy_loop.orchestrator import Orchestrator, OrchestratorConfig


@pytest.mark.asyncio
async def test_orchestrator_dry_run():
    """Test orchestrator executes dry-run successfully."""
    config = OrchestratorConfig(
        mode="dry",
        symbols=["AAPL"],
        max_iterations=1,
        event_log_path="reports/test_events.jsonl"
    )

    orchestrator = Orchestrator(config)
    await orchestrator.run()

    # Verify events were emitted
    assert len(orchestrator.event_log) >= 2  # At least START + SHUTDOWN
    assert orchestrator.event_log[0]["event_type"] == "START"
    assert orchestrator.event_log[-1]["event_type"] == "SHUTDOWN"


@pytest.mark.asyncio
async def test_orchestrator_completes_quickly():
    """Test orchestrator completes in <1s."""
    import time

    config = OrchestratorConfig(
        mode="dry",
        symbols=["AAPL", "SPY"],
        max_iterations=1
    )

    orchestrator = Orchestrator(config)

    start = time.perf_counter()
    await orchestrator.run()
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0, f"Orchestrator took {elapsed:.3f}s (should be <1s)"
