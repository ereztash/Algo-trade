#!/usr/bin/env python3
"""
Paper Trading Validation Script

This script validates the complete IBKR paper trading setup by:
1. Testing connection to TWS/Gateway
2. Retrieving account information
3. Checking positions and orders
4. Validating data integrity
5. Testing basic order placement (read-only mode)

Usage:
    python scripts/validate_paper_trading.py
    python scripts/validate_paper_trading.py --port 7497
    python scripts/validate_paper_trading.py --full-test  # Includes order placement test
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from algo_trade.core.execution.IBKR_handler import IBKRHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_success(text):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text):
    """Print error message."""
    print(f"❌ {text}")


def print_warning(text):
    """Print warning message."""
    print(f"⚠️  {text}")


def validate_connection(handler):
    """Validate IBKR connection."""
    print_header("Step 1: Testing Connection")

    try:
        success = handler.connect(timeout=10)

        if success:
            print_success(f"Connected to IBKR at {handler.host}:{handler.port}")
            print(f"   Client ID: {handler.client_id}")
            print(f"   Account: {handler.account}")
            return True
        else:
            print_error("Failed to connect to IBKR")
            print("\n📋 Troubleshooting:")
            print("   1. Ensure TWS or IB Gateway is running")
            print("   2. Check that API connections are enabled:")
            print("      TWS: Configure > Settings > API > Settings")
            print("      - Enable ActiveX and Socket Clients")
            print("      - Set Socket port to 7497 (paper) or 7496 (live)")
            print("   3. Verify firewall settings allow localhost connections")
            return False

    except Exception as e:
        print_error(f"Connection error: {e}")
        return False


def validate_account_summary(handler):
    """Validate account summary retrieval."""
    print_header("Step 2: Retrieving Account Summary")

    try:
        summary = handler.get_account_summary()

        if not summary:
            print_error("Failed to retrieve account summary")
            return False

        print_success("Account summary retrieved")
        print(f"\n   Account Details:")
        print(f"   ├─ Account Number: {summary.get('account', 'N/A')}")
        print(f"   ├─ Net Liquidation: ${summary.get('net_liquidation', 0):,.2f}")
        print(f"   ├─ Cash: ${summary.get('cash', 0):,.2f}")
        print(f"   ├─ Buying Power: ${summary.get('buying_power', 0):,.2f}")
        print(f"   ├─ Gross Position Value: ${summary.get('gross_position_value', 0):,.2f}")
        print(f"   ├─ Unrealized P&L: ${summary.get('pnl', 0):,.2f}")
        print(f"   └─ Realized P&L: ${summary.get('realized_pnl', 0):,.2f}")

        # Validate values
        if summary.get('net_liquidation', 0) <= 0:
            print_warning("Net liquidation value is zero or negative")

        return True

    except Exception as e:
        print_error(f"Error retrieving account summary: {e}")
        return False


def validate_positions(handler):
    """Validate positions retrieval."""
    print_header("Step 3: Retrieving Positions")

    try:
        positions = handler.get_positions()

        print_success(f"Retrieved {len(positions)} position(s)")

        if positions:
            print("\n   Current Positions:")
            for i, pos in enumerate(positions, 1):
                print(f"   {i}. {pos['symbol']}")
                print(f"      ├─ Position: {pos['position']:,.0f} shares")
                print(f"      ├─ Avg Cost: ${pos['avg_cost']:.2f}")
                print(f"      ├─ Market Value: ${pos['market_value']:,.2f}")
                print(f"      └─ Unrealized P&L: ${pos['pnl']:,.2f}")
        else:
            print("   No open positions")

        return True

    except Exception as e:
        print_error(f"Error retrieving positions: {e}")
        return False


def validate_orders(handler):
    """Validate orders retrieval."""
    print_header("Step 4: Retrieving Orders")

    try:
        orders = handler.get_orders()

        print_success(f"Retrieved {len(orders)} order(s)")

        if orders:
            print("\n   Recent Orders:")
            for i, order in enumerate(orders[:5], 1):  # Show max 5 recent orders
                print(f"   {i}. Order #{order['order_id']}")
                print(f"      ├─ Symbol: {order['symbol']}")
                print(f"      ├─ Action: {order['action']}")
                print(f"      ├─ Quantity: {order['quantity']}")
                print(f"      ├─ Type: {order['order_type']}")
                print(f"      ├─ Status: {order['status']}")
                print(f"      ├─ Filled: {order['filled']}/{order['quantity']}")
                print(f"      └─ Avg Fill Price: ${order['avg_fill_price']:.2f}")
        else:
            print("   No recent orders")

        return True

    except Exception as e:
        print_error(f"Error retrieving orders: {e}")
        return False


def validate_health(handler):
    """Validate health check."""
    print_header("Step 5: Health Check")

    try:
        health = handler.health_check()

        print_success("Health check completed")
        print(f"\n   Status:")
        print(f"   ├─ Connected: {health['connected']}")
        print(f"   ├─ State: {health['state']}")
        print(f"   ├─ Host: {health['host']}")
        print(f"   ├─ Port: {health['port']}")
        print(f"   ├─ Account: {health['account']}")
        print(f"   ├─ Read-Only: {health['readonly']}")
        print(f"   └─ Reconnect Attempts: {health['reconnect_attempts']}")

        if health.get('last_error'):
            print_warning(f"Last Error: {health['last_error'].get('message', 'N/A')}")

        return True

    except Exception as e:
        print_error(f"Error during health check: {e}")
        return False


def test_order_placement(handler):
    """Test order placement (paper trading only)."""
    print_header("Step 6: Testing Order Placement (Paper Trading)")

    print_warning("This test will place a small test order in paper trading")
    print("   Order: BUY 1 share of AAPL at MARKET")

    response = input("\nProceed with test order? (yes/no): ").strip().lower()

    if response != 'yes':
        print("Skipping order placement test")
        return True

    try:
        # Place a small test order
        trade = handler.place_order(
            symbol='AAPL',
            quantity=1,
            action='BUY',
            order_type='MARKET'
        )

        if trade:
            print_success(f"Test order placed successfully (Order ID: {trade.order.orderId})")
            print("\n   ⚠️  Note: This is a paper trading order. No real money involved.")
            print("   You can cancel it in TWS if desired.")
            return True
        else:
            print_error("Failed to place test order")
            return False

    except Exception as e:
        print_error(f"Error placing test order: {e}")
        return False


def main():
    """Main validation routine."""
    parser = argparse.ArgumentParser(description='Validate IBKR Paper Trading Setup')
    parser.add_argument('--host', default='127.0.0.1', help='IBKR host address')
    parser.add_argument('--port', type=int, default=7497, help='IBKR port (7497 for paper, 7496 for live)')
    parser.add_argument('--client-id', type=int, default=999, help='Client ID')
    parser.add_argument('--full-test', action='store_true', help='Include order placement test')
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("  📊 AlgoTrader Paper Trading Validation")
    print("=" * 70)
    print(f"\nTarget: {args.host}:{args.port}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create handler
    handler = IBKRHandler(
        host=args.host,
        port=args.port,
        client_id=args.client_id,
        readonly=not args.full_test  # Only allow orders in full test mode
    )

    results = []

    try:
        # Run validation steps
        results.append(("Connection", validate_connection(handler)))

        if results[-1][1]:  # If connected
            results.append(("Account Summary", validate_account_summary(handler)))
            results.append(("Positions", validate_positions(handler)))
            results.append(("Orders", validate_orders(handler)))
            results.append(("Health Check", validate_health(handler)))

            if args.full_test:
                results.append(("Order Placement", test_order_placement(handler)))

    finally:
        # Cleanup
        if handler.is_connected():
            handler.disconnect()

    # Print summary
    print_header("Validation Summary")

    total = len(results)
    passed = sum(1 for _, result in results if result)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:.<40} {status}")

    print(f"\n   Total: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All validation tests passed!")
        print("\nNext steps:")
        print("   1. Review the account summary and positions above")
        print("   2. Test the full trading pipeline:")
        print("      docker-compose up -d")
        print("   3. Monitor logs for any issues")
        return 0
    else:
        print("\n⚠️  Some validation tests failed")
        print("\nPlease review the errors above and:")
        print("   1. Ensure TWS/Gateway is running and configured correctly")
        print("   2. Check API settings in TWS")
        print("   3. Review logs for detailed error messages")
        return 1


if __name__ == '__main__':
    sys.exit(main())
