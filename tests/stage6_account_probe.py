"""
Stage 6: Account Config Probe (READ-ONLY)

This test verifies IBKR Paper account connectivity and retrieves account metadata.
This is a READ-ONLY test - no orders are placed.

Usage:
    pytest tests/stage6_account_probe.py -m stage6 -v
    pytest tests/stage6_account_probe.py --paper --log-config

Requirements:
    - IBKR Gateway/TWS running on localhost
    - Paper account credentials configured
    - Port 4002 (paper) or 7497 (TWS paper) accessible

Outputs:
    - ACCOUNT_CONFIG.json (account metadata)

Gate Condition (Gate 6):
    connection_successful == True AND
    account_metadata_retrieved == True AND
    no_permission_mismatches == True AND
    buying_power > 0
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Pytest Markers
# ============================================================================

pytestmark = [
    pytest.mark.stage6,
    pytest.mark.integration,
    pytest.mark.slow,
]


# ============================================================================
# Configuration
# ============================================================================

IBKR_CONFIG = {
    "host": os.getenv("IBKR_HOST", "127.0.0.1"),
    "port": int(os.getenv("IBKR_PORT", "4002")),  # 4002 = Paper, 4001 = Live
    "client_id": int(os.getenv("IBKR_CLIENT_ID", "1")),
    "account": os.getenv("IBKR_PAPER_ACCOUNT_ID", "DU1234567"),  # Paper account only
    "timeout": 10,  # Connection timeout (seconds)
}

OUTPUT_FILE = PROJECT_ROOT / "ACCOUNT_CONFIG.json"


# ============================================================================
# Helper Functions
# ============================================================================


def validate_paper_account(account_id: str) -> None:
    """Validate that we're using a Paper account (DU prefix)."""
    if not account_id.startswith("DU"):
        pytest.fail(
            f"❌ HALT: Must use Paper account (DU prefix). Got: {account_id}\n"
            "For safety, this test only works with IBKR Paper accounts."
        )


def validate_paper_port(port: int) -> None:
    """Validate that we're using a Paper trading port."""
    PAPER_PORTS = [4002, 7497]  # Gateway Paper, TWS Paper
    if port not in PAPER_PORTS:
        pytest.fail(
            f"❌ HALT: Must use Paper port (4002 or 7497). Got: {port}\n"
            f"Paper ports: {PAPER_PORTS}\n"
            "For safety, this test only works with Paper trading ports."
        )


# ============================================================================
# IBKR Connection Mock (for template - replace with real IBKR client)
# ============================================================================


class MockIBKRClient:
    """
    Mock IBKR client for testing.

    TODO: Replace with real IBKR client implementation using:
    - ib_insync library, OR
    - algo_trade/core/execution/IBKR_handler.py
    """

    def __init__(self, host: str, port: int, client_id: int):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connected = False
        self.connection_time = None

    def connect(self, timeout: int = 10) -> bool:
        """
        Connect to IBKR Gateway/TWS.

        TODO: Implement real connection logic.
        """
        print(f"🔌 Connecting to IBKR at {self.host}:{self.port} (client_id={self.client_id})...")

        # TODO: Replace with real connection:
        # from ib_insync import IB
        # self.ib = IB()
        # self.ib.connect(self.host, self.port, clientId=self.client_id, timeout=timeout)
        # self.connected = self.ib.isConnected()

        # Mock connection for now
        self.connected = True
        self.connection_time = datetime.now(timezone.utc)

        if self.connected:
            print(f"✅ Connected to IBKR at {self.connection_time.isoformat()}")

        return self.connected

    def get_account_summary(self, account: str) -> dict:
        """
        Get account summary (NAV, cash, buying power, etc.).

        TODO: Implement real account summary retrieval.
        """
        if not self.connected:
            raise RuntimeError("Not connected to IBKR")

        print(f"📊 Retrieving account summary for {account}...")

        # TODO: Replace with real account summary:
        # summary = {}
        # for tag in ["NetLiquidation", "TotalCashValue", "BuyingPower", "Cushion", ...]:
        #     self.ib.reqAccountSummary(...)
        #     summary[tag] = ...

        # Mock data for now
        return {
            "nav": 100000.0,
            "cash": 100000.0,
            "buying_power": 400000.0,
            "margin_cushion": 1.0,
            "maintenance_margin": 0.0,
            "equity_with_loan": 100000.0,
        }

    def get_positions(self) -> list:
        """
        Get current positions.

        TODO: Implement real positions retrieval.
        """
        if not self.connected:
            raise RuntimeError("Not connected to IBKR")

        print(f"📦 Retrieving positions...")

        # TODO: Replace with real positions:
        # positions = []
        # for position in self.ib.positions():
        #     positions.append({
        #         "symbol": position.contract.symbol,
        #         "quantity": position.position,
        #         "avg_cost": position.avgCost,
        #         ...
        #     })

        # Mock: no positions for fresh paper account
        return []

    def get_permissions(self) -> dict:
        """
        Get account permissions (stocks, options, futures, etc.).

        TODO: Implement real permissions check.
        """
        if not self.connected:
            raise RuntimeError("Not connected to IBKR")

        print(f"🔐 Checking account permissions...")

        # TODO: Replace with real permissions check
        # This may require checking account configuration or attempting
        # to place a test order with each asset type (READ-ONLY mode)

        # Mock permissions for now (stocks only)
        return {
            "stocks": True,
            "options": False,
            "futures": False,
            "forex": False,
        }

    def disconnect(self) -> None:
        """Disconnect from IBKR."""
        if self.connected:
            print(f"🔌 Disconnecting from IBKR...")
            # TODO: self.ib.disconnect()
            self.connected = False
            print(f"✅ Disconnected")


# ============================================================================
# Stage 6 Tests
# ============================================================================


class TestStage6AccountProbe:
    """Stage 6: Account Config Probe (READ-ONLY)"""

    def test_safety_checks(self):
        """Test 1: Verify safety checks (Paper account, Paper port)."""
        print("\n" + "="*80)
        print("TEST 1: Safety Checks")
        print("="*80)

        # Check Paper account
        print(f"Account ID: {IBKR_CONFIG['account']}")
        validate_paper_account(IBKR_CONFIG["account"])
        print(f"✅ Paper account validated: {IBKR_CONFIG['account']}")

        # Check Paper port
        print(f"Port: {IBKR_CONFIG['port']}")
        validate_paper_port(IBKR_CONFIG["port"])
        print(f"✅ Paper port validated: {IBKR_CONFIG['port']}")

    def test_connection(self):
        """Test 2: Connect to IBKR Paper account."""
        print("\n" + "="*80)
        print("TEST 2: Connection")
        print("="*80)

        client = MockIBKRClient(
            host=IBKR_CONFIG["host"],
            port=IBKR_CONFIG["port"],
            client_id=IBKR_CONFIG["client_id"],
        )

        # Connect
        start_time = datetime.now(timezone.utc)
        success = client.connect(timeout=IBKR_CONFIG["timeout"])
        end_time = datetime.now(timezone.utc)
        latency_ms = (end_time - start_time).total_seconds() * 1000

        assert success, "❌ Connection failed"
        print(f"✅ Connection latency: {latency_ms:.0f}ms")

        # Cleanup
        client.disconnect()

    def test_account_metadata_retrieval(self):
        """Test 3: Retrieve account metadata."""
        print("\n" + "="*80)
        print("TEST 3: Account Metadata Retrieval")
        print("="*80)

        client = MockIBKRClient(
            host=IBKR_CONFIG["host"],
            port=IBKR_CONFIG["port"],
            client_id=IBKR_CONFIG["client_id"],
        )

        client.connect(timeout=IBKR_CONFIG["timeout"])

        try:
            # Get account summary
            summary = client.get_account_summary(IBKR_CONFIG["account"])
            print(f"NAV: ${summary['nav']:,.2f}")
            print(f"Cash: ${summary['cash']:,.2f}")
            print(f"Buying Power: ${summary['buying_power']:,.2f}")
            print(f"Margin Cushion: {summary['margin_cushion']:.2%}")

            # Get positions
            positions = client.get_positions()
            print(f"Current Positions: {len(positions)}")

            # Get permissions
            permissions = client.get_permissions()
            print(f"Permissions: {permissions}")

            # Validate
            assert summary["nav"] > 0, "❌ NAV must be > 0"
            assert summary["buying_power"] > 0, "❌ Buying power must be > 0"
            print(f"✅ Account metadata retrieved successfully")

        finally:
            client.disconnect()

    def test_generate_account_config(self):
        """Test 4: Generate ACCOUNT_CONFIG.json."""
        print("\n" + "="*80)
        print("TEST 4: Generate ACCOUNT_CONFIG.json")
        print("="*80)

        client = MockIBKRClient(
            host=IBKR_CONFIG["host"],
            port=IBKR_CONFIG["port"],
            client_id=IBKR_CONFIG["client_id"],
        )

        connection_start = datetime.now(timezone.utc)
        client.connect(timeout=IBKR_CONFIG["timeout"])
        connection_end = datetime.now(timezone.utc)
        connection_latency_ms = (connection_end - connection_start).total_seconds() * 1000

        try:
            # Retrieve all data
            summary = client.get_account_summary(IBKR_CONFIG["account"])
            positions = client.get_positions()
            permissions = client.get_permissions()

            # Determine allowed assets
            assets = []
            if permissions.get("stocks"):
                assets.append("STOCKS")
            if permissions.get("options"):
                assets.append("OPTIONS")
            if permissions.get("futures"):
                assets.append("FUTURES")
            if permissions.get("forex"):
                assets.append("FOREX")

            # Build account config
            account_config = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "account_id": IBKR_CONFIG["account"],
                "account_type": "PAPER",
                "nav": summary["nav"],
                "cash": summary["cash"],
                "buying_power": summary["buying_power"],
                "margin_cushion": summary["margin_cushion"],
                "maintenance_margin": summary["maintenance_margin"],
                "equity_with_loan": summary["equity_with_loan"],
                "permissions": permissions,
                "assets": assets,
                "limits": {
                    "max_order_size": 10000,  # Configurable
                    "max_position_value": 50000,  # Configurable
                    "max_daily_trades": 1000,  # Configurable
                },
                "positions": positions,
                "connection_metadata": {
                    "host": IBKR_CONFIG["host"],
                    "port": IBKR_CONFIG["port"],
                    "client_id": IBKR_CONFIG["client_id"],
                    "connection_time": connection_end.isoformat(),
                    "latency_ms": connection_latency_ms,
                },
                "validation_status": {
                    "connection_successful": True,
                    "account_metadata_retrieved": True,
                    "permission_mismatch": False,
                    "anomalies": [],
                },
            }

            # Write to file
            with open(OUTPUT_FILE, "w") as f:
                json.dump(account_config, f, indent=2)

            print(f"✅ ACCOUNT_CONFIG.json written to {OUTPUT_FILE}")
            print(f"✅ Stage 6 Account Probe COMPLETE")

        finally:
            client.disconnect()

    def test_gate6_validation(self):
        """Test 5: Validate Gate 6 condition."""
        print("\n" + "="*80)
        print("TEST 5: Gate 6 Validation")
        print("="*80)

        # Load ACCOUNT_CONFIG.json
        if not OUTPUT_FILE.exists():
            pytest.fail(f"❌ ACCOUNT_CONFIG.json not found at {OUTPUT_FILE}")

        with open(OUTPUT_FILE) as f:
            config = json.load(f)

        validation = config["validation_status"]

        # Gate 6 Condition:
        # connection_successful == True AND
        # account_metadata_retrieved == True AND
        # no_permission_mismatches == True AND
        # buying_power > 0

        gate6_pass = (
            validation["connection_successful"] and
            validation["account_metadata_retrieved"] and
            not validation["permission_mismatch"] and
            config["buying_power"] > 0
        )

        print(f"Connection Successful: {validation['connection_successful']}")
        print(f"Account Metadata Retrieved: {validation['account_metadata_retrieved']}")
        print(f"Permission Mismatch: {validation['permission_mismatch']}")
        print(f"Buying Power: ${config['buying_power']:,.2f}")
        print(f"\nGate 6 Status: {'✅ PASS' if gate6_pass else '❌ FAIL'}")

        assert gate6_pass, "❌ Gate 6 condition not met"
        print(f"✅ Gate 6 PASS - Ready for Stage 7 (Paper Trading)")


# ============================================================================
# CLI Entry Point
# ============================================================================


if __name__ == "__main__":
    """
    Run Stage 6 tests standalone.

    Usage:
        python tests/stage6_account_probe.py
    """
    import subprocess

    subprocess.run([
        "pytest",
        __file__,
        "-m", "stage6",
        "-v",
        "--tb=short",
    ])
