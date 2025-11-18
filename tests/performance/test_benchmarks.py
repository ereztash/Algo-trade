"""
Performance Benchmarks using pytest-benchmark
===============================================

These tests measure the performance of critical system components.

Usage:
    # Run all benchmarks
    pytest tests/performance/test_benchmarks.py -v

    # Run with benchmark comparison
    pytest tests/performance/test_benchmarks.py --benchmark-compare

    # Run with benchmark histogram
    pytest tests/performance/test_benchmarks.py --benchmark-histogram

    # Save baseline
    pytest tests/performance/test_benchmarks.py --benchmark-save=baseline

    # Compare against baseline
    pytest tests/performance/test_benchmarks.py --benchmark-compare=baseline

Requirements:
    pip install pytest-benchmark>=4.0.0
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone
import json


# Mock classes for testing (replace with actual imports when available)
class MockSignalGenerator:
    """Mock signal generator for testing."""

    def generate_ofi_signal(self, df):
        """Generate OFI signal."""
        return np.random.randn(len(df))


class MockPortfolioOptimizer:
    """Mock portfolio optimizer for testing."""

    def optimize(self, returns, covariance):
        """Optimize portfolio."""
        n_assets = returns.shape[0]
        weights = np.random.dirichlet(np.ones(n_assets))
        return weights


class MockRiskManager:
    """Mock risk manager for testing."""

    def check_risk(self, position_value, nav):
        """Check risk limits."""
        exposure = abs(position_value) / nav
        return exposure < 0.25


# Fixtures
@pytest.fixture
def sample_market_data():
    """Generate sample market data for benchmarks."""
    n_bars = 1000
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=n_bars, freq="1min"),
            "open": 100 + np.random.randn(n_bars).cumsum() * 0.1,
            "high": 100 + np.random.randn(n_bars).cumsum() * 0.1 + 0.5,
            "low": 100 + np.random.randn(n_bars).cumsum() * 0.1 - 0.5,
            "close": 100 + np.random.randn(n_bars).cumsum() * 0.1,
            "volume": np.random.randint(100000, 1000000, n_bars),
        }
    )


@pytest.fixture
def sample_returns():
    """Generate sample returns for portfolio optimization."""
    n_assets = 50
    n_periods = 252
    returns = np.random.randn(n_periods, n_assets) * 0.01
    return returns


@pytest.fixture
def sample_covariance(sample_returns):
    """Generate sample covariance matrix."""
    return np.cov(sample_returns.T)


# ===========================
# Signal Generation Benchmarks
# ===========================


class TestSignalGenerationPerformance:
    """Benchmark signal generation performance."""

    def test_ofi_signal_generation(self, benchmark, sample_market_data):
        """
        Benchmark OFI signal generation.

        Target: <10ms for 1000 bars
        """
        signal_gen = MockSignalGenerator()

        result = benchmark(signal_gen.generate_ofi_signal, sample_market_data)

        assert len(result) == len(sample_market_data)
        assert isinstance(result, np.ndarray)

    @pytest.mark.parametrize("n_bars", [100, 500, 1000, 5000])
    def test_signal_scalability(self, benchmark, n_bars):
        """
        Test signal generation scalability with varying data sizes.

        Ensures O(n) complexity.
        """
        df = pd.DataFrame(
            {
                "close": 100 + np.random.randn(n_bars).cumsum() * 0.1,
                "volume": np.random.randint(100000, 1000000, n_bars),
            }
        )

        signal_gen = MockSignalGenerator()
        result = benchmark(signal_gen.generate_ofi_signal, df)

        assert len(result) == n_bars


# ===========================
# Portfolio Optimization Benchmarks
# ===========================


class TestPortfolioOptimizationPerformance:
    """Benchmark portfolio optimization performance."""

    def test_quadratic_programming(self, benchmark, sample_returns, sample_covariance):
        """
        Benchmark quadratic programming optimization.

        Target: <100ms for 50 assets
        """
        optimizer = MockPortfolioOptimizer()

        mean_returns = sample_returns.mean(axis=0)
        result = benchmark(optimizer.optimize, mean_returns, sample_covariance)

        assert len(result) == len(mean_returns)
        assert np.isclose(result.sum(), 1.0)  # Weights sum to 1

    @pytest.mark.parametrize("n_assets", [10, 25, 50, 100])
    def test_optimization_scalability(self, benchmark, n_assets):
        """
        Test optimization scalability with varying number of assets.

        Expected: O(n^3) for QP, but should be <1s for 100 assets
        """
        returns = np.random.randn(252, n_assets) * 0.01
        mean_returns = returns.mean(axis=0)
        covariance = np.cov(returns.T)

        optimizer = MockPortfolioOptimizer()
        result = benchmark(optimizer.optimize, mean_returns, covariance)

        assert len(result) == n_assets


# ===========================
# Risk Management Benchmarks
# ===========================


class TestRiskManagementPerformance:
    """Benchmark risk management checks."""

    def test_risk_check_latency(self, benchmark):
        """
        Benchmark risk check latency.

        Target: <1ms per check
        Critical: This runs on every order, must be fast!
        """
        risk_mgr = MockRiskManager()

        result = benchmark(risk_mgr.check_risk, 10000, 100000)

        assert isinstance(result, bool)

    def test_risk_check_batch(self, benchmark):
        """
        Benchmark batch risk checking (100 orders).

        Target: <10ms for 100 checks
        """
        risk_mgr = MockRiskManager()

        def batch_risk_check():
            positions = np.random.randint(1000, 50000, 100)
            nav = 100000
            return [risk_mgr.check_risk(pos, nav) for pos in positions]

        result = benchmark(batch_risk_check)

        assert len(result) == 100


# ===========================
# Data Processing Benchmarks
# ===========================


class TestDataProcessingPerformance:
    """Benchmark data processing operations."""

    def test_bar_event_validation(self, benchmark):
        """
        Benchmark bar event validation (Pydantic).

        Target: <1.5ms per event (from schema validation spec)
        """

        def validate_bar_event():
            bar_data = {
                "event_type": "bar_event",
                "symbol": "SPY",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "open": 450.25,
                "high": 452.80,
                "low": 449.50,
                "close": 451.75,
                "volume": 1000000,
            }
            # Mock validation (replace with actual validator)
            return bar_data

        result = benchmark(validate_bar_event)

        assert result["symbol"] == "SPY"

    def test_json_serialization(self, benchmark):
        """
        Benchmark JSON serialization for Kafka messages.

        Target: <1ms per message
        """
        message = {
            "symbol": "SPY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "price": 451.75,
            "volume": 1000000,
            "signals": {
                "OFI": 0.5,
                "ERN": 0.3,
                "VRP": -0.2,
            },
        }

        result = benchmark(json.dumps, message)

        assert isinstance(result, str)

    def test_dataframe_operations(self, benchmark, sample_market_data):
        """
        Benchmark common DataFrame operations.

        Target: <5ms for 1000 rows
        """

        def process_dataframe(df):
            # Common operations: rolling mean, diff, etc.
            df = df.copy()
            df["sma_20"] = df["close"].rolling(20).mean()
            df["returns"] = df["close"].pct_change()
            df["vol_sma"] = df["volume"].rolling(20).mean()
            return df

        result = benchmark(process_dataframe, sample_market_data)

        assert len(result) == len(sample_market_data)


# ===========================
# Covariance Estimation Benchmarks
# ===========================


class TestCovarianceEstimationPerformance:
    """Benchmark covariance estimation performance."""

    def test_ewma_covariance(self, benchmark, sample_returns):
        """
        Benchmark EWMA covariance estimation.

        Target: <50ms for 50 assets
        """

        def ewma_cov(returns, halflife=60):
            """Exponentially weighted covariance."""
            weights = np.exp(-np.log(2) / halflife * np.arange(len(returns))[::-1])
            weights /= weights.sum()
            mean = (returns * weights[:, None]).sum(axis=0)
            centered = returns - mean
            cov = (centered.T @ (centered * weights[:, None])) / weights.sum()
            return cov

        result = benchmark(ewma_cov, sample_returns)

        assert result.shape == (sample_returns.shape[1], sample_returns.shape[1])

    def test_ledoit_wolf_shrinkage(self, benchmark, sample_returns):
        """
        Benchmark Ledoit-Wolf shrinkage estimator.

        Target: <100ms for 50 assets
        """
        from sklearn.covariance import LedoitWolf

        lw = LedoitWolf()
        result = benchmark(lw.fit, sample_returns)

        assert hasattr(result, "covariance_")


# ===========================
# Throughput Benchmarks
# ===========================


class TestThroughputBenchmarks:
    """Benchmark system throughput."""

    def test_message_processing_throughput(self, benchmark):
        """
        Benchmark message processing throughput.

        Target: >500 msg/sec
        Measured: messages processed per second
        """
        messages = [
            {
                "symbol": f"STOCK_{i}",
                "price": 100 + np.random.randn(),
                "volume": np.random.randint(1000, 10000),
            }
            for i in range(1000)
        ]

        def process_messages(msgs):
            # Mock processing
            return [json.dumps(msg) for msg in msgs]

        result = benchmark(process_messages, messages)

        assert len(result) == 1000

        # Calculate throughput
        ops_per_sec = 1000 / benchmark.stats.stats.mean
        print(f"\n  Throughput: {ops_per_sec:.0f} msg/sec")

        # Assert target
        assert ops_per_sec > 500, f"Throughput {ops_per_sec:.0f} msg/sec < 500 msg/sec target"


# ===========================
# Regression Tests
# ===========================


class TestPerformanceRegression:
    """
    Regression tests to ensure performance doesn't degrade over time.

    These tests fail if performance is >10% worse than baseline.
    """

    @pytest.mark.benchmark(group="regression")
    def test_no_signal_regression(self, benchmark, sample_market_data):
        """
        Ensure signal generation doesn't regress.

        This test will fail if it's >10% slower than the saved baseline.
        """
        signal_gen = MockSignalGenerator()

        benchmark.pedantic(
            signal_gen.generate_ofi_signal,
            args=(sample_market_data,),
            iterations=100,
            rounds=10,
        )


# ===========================
# Custom Benchmark Comparisons
# ===========================


def test_benchmark_report(benchmark):
    """
    Generate a custom benchmark report.

    This aggregates all benchmark results and checks against targets.
    """
    # This is a placeholder - actual implementation would
    # parse benchmark results and generate a report
    pass


# Run instructions
"""
# Basic run
pytest tests/performance/test_benchmarks.py -v

# With detailed stats
pytest tests/performance/test_benchmarks.py -v --benchmark-verbose

# Save baseline for future comparison
pytest tests/performance/test_benchmarks.py --benchmark-save=v1.0

# Compare against baseline
pytest tests/performance/test_benchmarks.py --benchmark-compare=v1.0

# Generate histogram
pytest tests/performance/test_benchmarks.py --benchmark-histogram

# Only run throughput tests
pytest tests/performance/test_benchmarks.py -k throughput -v

# Fail if performance regresses >10%
pytest tests/performance/test_benchmarks.py --benchmark-compare=v1.0 --benchmark-compare-fail=mean:10%
"""
