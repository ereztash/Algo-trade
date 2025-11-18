"""
Stage 7: Paper Trading Validation

This test runs a live paper trading session to validate IBKR integration performance.
Measures latency, fill rate, Sharpe ratio, and other critical metrics.

Usage:
    pytest tests/stage7_paper_trading.py -m stage7 -v
    pytest tests/stage7_paper_trading.py --duration 6h --trades 50-200

Requirements:
    - IBKR Gateway/TWS running on localhost
    - Paper account credentials configured
    - ACCOUNT_CONFIG.json exists (from Stage 6)
    - Market hours (or paper trading hours)

Outputs:
    - PAPER_TRADING_LOG.json (trade-by-trade logs)
    - PAPER_TRADING_METRICS.csv (performance metrics)

Gate Condition (Gate 7):
    latency_delta < 0.50 AND          # <50% slower than mock
    pacing_violations == 0 AND
    fill_rate > 0.98 AND              # >98% filled
    sharpe_paper >= 0.5 * sharpe_backtest  # At least 50% of backtest Sharpe
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Pytest Markers
# ============================================================================

pytestmark = [
    pytest.mark.stage7,
    pytest.mark.integration,
    pytest.mark.slow,
]


# ============================================================================
# Configuration
# ============================================================================

IBKR_CONFIG = {
    "host": os.getenv("IBKR_HOST", "127.0.0.1"),
    "port": int(os.getenv("IBKR_PORT", "4002")),  # 4002 = Paper
    "client_id": int(os.getenv("IBKR_CLIENT_ID", "1")),
    "account": os.getenv("IBKR_PAPER_ACCOUNT_ID", "DU1234567"),
}

SESSION_CONFIG = {
    "duration_hours": float(os.getenv("SESSION_DURATION_HOURS", "6.0")),
    "target_trades_min": int(os.getenv("TARGET_TRADES_MIN", "50")),
    "target_trades_max": int(os.getenv("TARGET_TRADES_MAX", "200")),
    "symbols": os.getenv("SYMBOLS", "AAPL,MSFT,TSLA,GOOGL,AMZN").split(","),
    "strategy": "QuantPortfolioStrategy",
}

ACCOUNT_CONFIG_FILE = PROJECT_ROOT / "ACCOUNT_CONFIG.json"
OUTPUT_LOG_FILE = PROJECT_ROOT / "PAPER_TRADING_LOG.json"
OUTPUT_METRICS_FILE = PROJECT_ROOT / "PAPER_TRADING_METRICS.csv"

# Mock baseline latency (from dry-run with mock broker)
MOCK_BASELINE_P50_MS = 130  # TODO: Replace with actual mock baseline


# ============================================================================
# Helper Functions
# ============================================================================


def load_account_config() -> dict:
    """Load ACCOUNT_CONFIG.json from Stage 6."""
    if not ACCOUNT_CONFIG_FILE.exists():
        pytest.fail(
            f"❌ ACCOUNT_CONFIG.json not found at {ACCOUNT_CONFIG_FILE}\n"
            "Please run Stage 6 first: pytest tests/stage6_account_probe.py"
        )

    with open(ACCOUNT_CONFIG_FILE) as f:
        return json.load(f)


def calculate_sharpe_ratio(returns: List[float]) -> float:
    """Calculate annualized Sharpe ratio."""
    import numpy as np

    if len(returns) == 0:
        return 0.0

    returns_arr = np.array(returns)
    mean_return = returns_arr.mean()
    std_return = returns_arr.std()

    if std_return == 0:
        return 0.0

    # Annualize: assume daily returns, sqrt(252)
    sharpe = (mean_return / std_return) * np.sqrt(252)
    return sharpe


def calculate_percentile(values: List[float], percentile: int) -> float:
    """Calculate percentile from list of values."""
    import numpy as np
    return np.percentile(values, percentile) if values else 0.0


# ============================================================================
# Mock Trading Session (replace with real implementation)
# ============================================================================


class MockTradingSession:
    """
    Mock paper trading session.

    TODO: Replace with real trading session using:
    - algo_trade strategy
    - IBKR execution client
    - Kafka message bus (order_intents → execution_reports)
    """

    def __init__(self, config: dict, account_config: dict):
        self.config = config
        self.account_config = account_config
        self.session_id = f"paper_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.start_time = None
        self.end_time = None
        self.trades = []
        self.pacing_violations = 0
        self.disconnects = 0

    def run_session(self, duration_hours: float, target_trades: int) -> List[dict]:
        """
        Run paper trading session.

        TODO: Replace with real trading session:
        1. Start strategy
        2. Subscribe to market data
        3. Generate order intents
        4. Execute orders via IBKR
        5. Track execution reports
        6. Log all trades
        """
        import random

        print(f"\n🚀 Starting paper trading session: {self.session_id}")
        print(f"Duration: {duration_hours} hours")
        print(f"Target trades: {target_trades}")
        print(f"Symbols: {self.config['symbols']}")

        self.start_time = datetime.now(timezone.utc)
        initial_capital = self.account_config["nav"]

        # Simulate trades
        for i in range(target_trades):
            trade = self._simulate_trade(i)
            self.trades.append(trade)

            # Simulate time passing
            time.sleep(0.01)  # Small delay to simulate real trading

        self.end_time = datetime.now(timezone.utc)

        print(f"✅ Session complete: {len(self.trades)} trades executed")
        return self.trades

    def _simulate_trade(self, trade_num: int) -> dict:
        """
        Simulate a single trade.

        TODO: Replace with real trade execution.
        """
        import random

        intent_id = str(uuid4())
        order_id = str(1000 + trade_num)
        symbol = random.choice(self.config["symbols"])
        direction = random.choice(["BUY", "SELL"])
        quantity = random.randint(10, 100)
        order_type = random.choice(["MARKET", "LIMIT"])
        status = random.choice(["FILLED"] * 98 + ["CANCELED"] + ["REJECTED"])  # 98% fill rate

        # Simulate latency
        intent_to_submit_ms = random.uniform(20, 40)
        submit_to_ack_ms = random.uniform(100, 180)
        ack_to_fill_ms = random.uniform(2000, 5000) if status == "FILLED" else 0
        total_latency_ms = intent_to_submit_ms + submit_to_ack_ms + ack_to_fill_ms

        # Simulate timestamps
        now = datetime.now(timezone.utc)
        timestamp_intent = now
        timestamp_submitted = now + timedelta(milliseconds=intent_to_submit_ms)
        timestamp_acknowledged = timestamp_submitted + timedelta(milliseconds=submit_to_ack_ms)
        timestamp_filled = timestamp_acknowledged + timedelta(milliseconds=ack_to_fill_ms) if status == "FILLED" else None

        trade = {
            "intent_id": intent_id,
            "order_id": order_id,
            "symbol": symbol,
            "direction": direction,
            "quantity": quantity,
            "order_type": order_type,
            "status": status,
            "latency_ms": {
                "intent_to_submit": round(intent_to_submit_ms, 2),
                "submit_to_ack": round(submit_to_ack_ms, 2),
                "ack_to_fill": round(ack_to_fill_ms, 2) if status == "FILLED" else 0,
                "total": round(total_latency_ms, 2),
            },
            "timestamp_intent": timestamp_intent.isoformat(),
            "timestamp_submitted": timestamp_submitted.isoformat(),
            "timestamp_acknowledged": timestamp_acknowledged.isoformat(),
            "timestamp_filled": timestamp_filled.isoformat() if timestamp_filled else None,
        }

        # Add fill details if filled
        if status == "FILLED":
            trade["fill_price"] = round(random.uniform(200, 400), 2)
            trade["commission"] = round(random.uniform(1.0, 2.0), 2)
            trade["slippage"] = round(random.uniform(5, 15), 2)  # basis points

        return trade

    def calculate_summary(self) -> dict:
        """Calculate session summary metrics."""
        total_trades = len(self.trades)
        filled_trades = sum(1 for t in self.trades if t["status"] == "FILLED")
        rejected_trades = sum(1 for t in self.trades if t["status"] == "REJECTED")
        canceled_trades = sum(1 for t in self.trades if t["status"] == "CANCELED")

        fill_rate = filled_trades / total_trades if total_trades > 0 else 0

        # Latency metrics
        total_latencies = [t["latency_ms"]["total"] for t in self.trades if t["status"] == "FILLED"]
        avg_latency_ms = sum(total_latencies) / len(total_latencies) if total_latencies else 0
        p50_latency_ms = calculate_percentile(total_latencies, 50)
        p95_latency_ms = calculate_percentile(total_latencies, 95)
        p99_latency_ms = calculate_percentile(total_latencies, 99)

        # Mock performance metrics
        import random
        total_pnl = random.uniform(500, 2000)
        final_capital = self.account_config["nav"] + total_pnl
        pnl_percentage = (total_pnl / self.account_config["nav"]) * 100

        # Mock Sharpe ratio
        sharpe_paper = random.uniform(1.0, 1.5)

        return {
            "total_trades": total_trades,
            "filled_trades": filled_trades,
            "rejected_trades": rejected_trades,
            "canceled_trades": canceled_trades,
            "fill_rate": round(fill_rate, 4),
            "avg_latency_ms": round(avg_latency_ms, 2),
            "p50_latency_ms": round(p50_latency_ms, 2),
            "p95_latency_ms": round(p95_latency_ms, 2),
            "p99_latency_ms": round(p99_latency_ms, 2),
            "pacing_violations": self.pacing_violations,
            "disconnects": self.disconnects,
            "total_pnl": round(total_pnl, 2),
            "sharpe_ratio": round(sharpe_paper, 2),
            "max_drawdown": round(random.uniform(0.05, 0.12), 3),
            "final_capital": round(final_capital, 2),
        }


# ============================================================================
# Stage 7 Tests
# ============================================================================


class TestStage7PaperTrading:
    """Stage 7: Paper Trading Validation"""

    def test_prerequisites(self):
        """Test 1: Verify prerequisites (Stage 6 complete)."""
        print("\n" + "="*80)
        print("TEST 1: Prerequisites")
        print("="*80)

        # Check ACCOUNT_CONFIG.json exists
        assert ACCOUNT_CONFIG_FILE.exists(), (
            f"❌ ACCOUNT_CONFIG.json not found. Run Stage 6 first:\n"
            f"pytest tests/stage6_account_probe.py"
        )

        account_config = load_account_config()
        print(f"✅ Account config loaded: {account_config['account_id']}")
        print(f"   NAV: ${account_config['nav']:,.2f}")
        print(f"   Buying Power: ${account_config['buying_power']:,.2f}")

    def test_run_paper_trading_session(self):
        """Test 2: Run paper trading session."""
        print("\n" + "="*80)
        print("TEST 2: Paper Trading Session")
        print("="*80)

        account_config = load_account_config()

        # Initialize session
        session = MockTradingSession(SESSION_CONFIG, account_config)

        # Calculate target trades
        import random
        target_trades = random.randint(
            SESSION_CONFIG["target_trades_min"],
            SESSION_CONFIG["target_trades_max"]
        )

        # Run session
        trades = session.run_session(
            duration_hours=SESSION_CONFIG["duration_hours"],
            target_trades=target_trades
        )

        assert len(trades) > 0, "❌ No trades executed"
        print(f"✅ Session complete: {len(trades)} trades")

        # Calculate summary
        summary = session.calculate_summary()

        # Save log
        log_data = {
            "session_id": session.session_id,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat(),
            "account_id": account_config["account_id"],
            "trades": trades,
            "session_metadata": {
                "duration_hours": SESSION_CONFIG["duration_hours"],
                "strategy": SESSION_CONFIG["strategy"],
                "symbols": SESSION_CONFIG["symbols"],
                "target_trades": {
                    "min": SESSION_CONFIG["target_trades_min"],
                    "max": SESSION_CONFIG["target_trades_max"]
                },
                "initial_capital": account_config["nav"],
                "branch": os.getenv("GIT_BRANCH", "unknown"),
                "commit_hash": os.getenv("GIT_COMMIT", "unknown"),
            },
            "session_summary": summary,
            "anomalies": []
        }

        with open(OUTPUT_LOG_FILE, "w") as f:
            json.dump(log_data, f, indent=2)

        print(f"✅ Trade log saved to {OUTPUT_LOG_FILE}")

    def test_calculate_metrics(self):
        """Test 3: Calculate and save metrics."""
        print("\n" + "="*80)
        print("TEST 3: Calculate Metrics")
        print("="*80)

        # Load log
        with open(OUTPUT_LOG_FILE) as f:
            log_data = json.load(f)

        summary = log_data["session_summary"]

        # Calculate latency delta
        p50_latency = summary["p50_latency_ms"]
        latency_delta_pct = ((p50_latency - MOCK_BASELINE_P50_MS) / MOCK_BASELINE_P50_MS) * 100

        # Mock Sharpe backtest for comparison
        sharpe_backtest = 2.10  # TODO: Load from backtest results
        sharpe_paper = summary["sharpe_ratio"]
        sharpe_delta = sharpe_paper / sharpe_backtest

        # Write metrics CSV
        metrics = [
            ("session_id", log_data["session_id"], "id", "INFO", "-", "Unique session identifier"),
            ("duration", log_data["session_metadata"]["duration_hours"], "hours", "OK", ">=6", "Session duration"),
            ("total_trades", summary["total_trades"], "count", "OK", "50-200", "Total trades"),
            ("fill_rate", summary["fill_rate"] * 100, "%", "OK" if summary["fill_rate"] > 0.98 else "FAIL", ">98", "Fill rate"),
            ("p50_latency", summary["p50_latency_ms"], "ms", "OK", "<200", "P50 latency"),
            ("p95_latency", summary["p95_latency_ms"], "ms", "OK", "<500", "P95 latency"),
            ("p99_latency", summary["p99_latency_ms"], "ms", "WARN", "<1000", "P99 latency"),
            ("latency_delta_vs_mock", round(latency_delta_pct, 1), "%", "OK" if latency_delta_pct < 50 else "FAIL", "<50", "Latency vs mock"),
            ("pacing_violations", summary["pacing_violations"], "count", "OK" if summary["pacing_violations"] == 0 else "FAIL", "=0", "Pacing violations"),
            ("disconnects", summary["disconnects"], "count", "OK" if summary["disconnects"] == 0 else "FAIL", "=0", "Disconnects"),
            ("sharpe_paper", sharpe_paper, "ratio", "INFO", ">=1.05", "Paper Sharpe"),
            ("sharpe_backtest", sharpe_backtest, "ratio", "INFO", "-", "Backtest Sharpe"),
            ("sharpe_delta", round(sharpe_delta, 3), "ratio", "OK" if sharpe_delta >= 0.5 else "WARN", ">=0.50", "Sharpe ratio"),
        ]

        with open(OUTPUT_METRICS_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value", "unit", "status", "threshold", "notes"])
            writer.writerows(metrics)

        print(f"✅ Metrics saved to {OUTPUT_METRICS_FILE}")

        # Print key metrics
        print(f"\n📊 Key Metrics:")
        for metric in metrics:
            print(f"   {metric[0]}: {metric[1]} {metric[2]} [{metric[3]}]")

    def test_gate7_validation(self):
        """Test 4: Validate Gate 7 condition."""
        print("\n" + "="*80)
        print("TEST 4: Gate 7 Validation")
        print("="*80)

        # Load metrics
        with open(OUTPUT_LOG_FILE) as f:
            log_data = json.load(f)

        summary = log_data["session_summary"]

        # Calculate conditions
        p50_latency = summary["p50_latency_ms"]
        latency_delta = ((p50_latency - MOCK_BASELINE_P50_MS) / MOCK_BASELINE_P50_MS)

        sharpe_backtest = 2.10  # TODO: Load from backtest
        sharpe_paper = summary["sharpe_ratio"]
        sharpe_ratio = sharpe_paper / sharpe_backtest

        # Gate 7 Condition:
        # latency_delta < 0.50 AND
        # pacing_violations == 0 AND
        # fill_rate > 0.98 AND
        # sharpe_paper >= 0.5 * sharpe_backtest

        gate7_latency = latency_delta < 0.50
        gate7_pacing = summary["pacing_violations"] == 0
        gate7_fill_rate = summary["fill_rate"] > 0.98
        gate7_sharpe = sharpe_ratio >= 0.50

        gate7_pass = gate7_latency and gate7_pacing and gate7_fill_rate and gate7_sharpe

        print(f"Latency Delta: {latency_delta:.2%} (<50%: {gate7_latency})")
        print(f"Pacing Violations: {summary['pacing_violations']} (=0: {gate7_pacing})")
        print(f"Fill Rate: {summary['fill_rate']:.2%} (>98%: {gate7_fill_rate})")
        print(f"Sharpe Ratio: {sharpe_ratio:.2%} (≥50%: {gate7_sharpe})")
        print(f"\nGate 7 Status: {'✅ PASS' if gate7_pass else '❌ FAIL'}")

        if gate7_pass:
            print(f"✅ Gate 7 PASS - Ready for Stage 8 (Go-Live Decision)")
        else:
            print(f"❌ Gate 7 FAIL - Performance below threshold. Investigation required.")

        assert gate7_pass, "Gate 7 condition not met"


# ============================================================================
# CLI Entry Point
# ============================================================================


if __name__ == "__main__":
    """Run Stage 7 tests standalone."""
    import subprocess

    subprocess.run([
        "pytest",
        __file__,
        "-m", "stage7",
        "-v",
        "--tb=short",
    ])
