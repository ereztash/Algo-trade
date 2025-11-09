"""
Example Usage: Monitoring & Alerting
=====================================

Demonstrates how to integrate monitoring into the trading system.
"""

import time
import numpy as np
from data_plane.monitoring import get_metrics_exporter, AlertManager, AlertTemplates


def example_metrics_recording():
    """Example: Recording metrics during trading."""

    print("=" * 70)
    print("Example 1: Recording Metrics")
    print("=" * 70)

    # Initialize metrics exporter (starts HTTP server on port 8000)
    exporter = get_metrics_exporter(port=8000)

    print(f"\n✅ Metrics endpoint started at http://localhost:8000/metrics\n")

    # Simulate trading loop
    print("Simulating trading day with metrics...")

    for t in range(10):
        # Simulate metrics
        cumulative_pnl = 0.01 + t * 0.002  # Growing PnL
        daily_pnl = 0.002
        sharpe_30d = 1.5 + t * 0.05
        current_dd = 0.02 if t < 5 else 0.05  # Drawdown increases
        max_dd = 0.05

        # Record performance metrics
        exporter.record_pnl(cumulative_pnl=cumulative_pnl, daily_pnl=daily_pnl)
        exporter.record_sharpe_ratio(sharpe_30d=sharpe_30d)
        exporter.record_drawdown(current_dd=current_dd, max_dd=max_dd)

        # Record risk metrics
        gross = 1.8 + t * 0.05
        net = 0.6 + t * 0.02
        vol = 0.12 + t * 0.005
        exporter.record_exposure(gross=gross, net=net)
        exporter.record_portfolio_risk(volatility=vol)

        # Record order latency (simulate)
        latency_ms = np.random.normal(45, 15)  # ~45ms average
        exporter.record_order_latency(latency_ms, latency_type="intent_to_ack")

        # Record orders
        if t % 3 == 0:
            exporter.record_order_event("submitted")
            exporter.record_order_event("filled")

        # Record system health
        exporter.record_system_health(
            cpu_percent=50 + t * 2,
            memory_mb=2048 + t * 100,
            throughput=150.0
        )

        # Set market regime
        regime = "Calm" if t < 3 else ("Normal" if t < 7 else "Storm")
        exporter.set_market_regime(regime)

        print(f"  Day {t+1}: PnL={cumulative_pnl:.2%}, Sharpe={sharpe_30d:.2f}, "
              f"DD={current_dd:.2%}, Regime={regime}")

        time.sleep(0.5)

    print(f"\n✅ Metrics recorded. View at: http://localhost:8000/metrics\n")

    # Get metrics summary
    summary = exporter.get_metrics_summary()
    print("Final Metrics Summary:")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print()


def example_alerting():
    """Example: Sending alerts."""

    print("=" * 70)
    print("Example 2: Sending Alerts")
    print("=" * 70)

    # Initialize alert manager (uses config file)
    alert_mgr = AlertManager(config_path='data_plane/monitoring/monitoring_config.yaml')

    print("\n✅ Alert Manager initialized\n")

    # Example 1: Info alert
    print("Sending INFO alert...")
    alert_mgr.info(
        title="System Started",
        message="Trading system initialized successfully",
        component="system"
    )

    time.sleep(1)

    # Example 2: Medium alert (P2)
    print("Sending P2 (Medium) alert...")
    alert_mgr.medium(
        title="High CPU Usage",
        message="CPU usage at 75%",
        component="system_health",
        tags={"cpu_percent": "75"}
    )

    time.sleep(1)

    # Example 3: High alert (P1)
    print("Sending P1 (High) alert...")
    alert_mgr.high(
        title="High Order Latency",
        message="Order latency exceeded 200ms (current: 245ms)",
        component="order_execution",
        runbook_url="https://docs.example.com/runbooks/high-latency"
    )

    time.sleep(1)

    # Example 4: Critical alert (P0) using template
    print("Sending P0 (Critical) alert...")
    alert_mgr.send_alert(
        **AlertTemplates.kill_switch_activated("PnL", -0.052, -0.05)
    )

    time.sleep(1)

    # Example 5: IBKR connection lost
    print("Sending IBKR connection alert...")
    alert_mgr.send_alert(
        **AlertTemplates.ibkr_connection_lost()
    )

    print("\n✅ All alerts sent\n")

    # Flush any pending aggregated alerts
    alert_mgr.flush()


def example_kill_switch_monitoring():
    """Example: Monitoring kill switches."""

    print("=" * 70)
    print("Example 3: Kill Switch Monitoring")
    print("=" * 70)

    exporter = get_metrics_exporter(port=8000)
    alert_mgr = AlertManager(config_path='data_plane/monitoring/monitoring_config.yaml')

    print("\n✅ Monitoring kill switches...\n")

    # Simulate deteriorating performance
    pnl_values = [0.01, 0.005, 0.0, -0.01, -0.03, -0.052]  # Triggers at -0.05

    for i, pnl in enumerate(pnl_values):
        exporter.record_pnl(cumulative_pnl=pnl)
        exporter.record_drawdown(current_dd=abs(min(pnl, 0)), max_dd=0.052)

        print(f"  Iteration {i+1}: PnL={pnl:.2%}", end="")

        # Check if kill switch should activate
        if pnl <= -0.05:
            # Activate kill switch
            exporter.set_kill_switch("pnl", active=True)
            print(" 🚨 KILL SWITCH ACTIVATED!")

            # Send critical alert
            alert_mgr.send_alert(
                **AlertTemplates.kill_switch_activated("PnL", pnl, -0.05)
            )

            break
        else:
            exporter.set_kill_switch("pnl", active=False)
            print(" ✓ OK")

        time.sleep(0.5)

    print()


def example_data_quality_monitoring():
    """Example: Data quality monitoring."""

    print("=" * 70)
    print("Example 4: Data Quality Monitoring")
    print("=" * 70)

    exporter = get_metrics_exporter(port=8000)
    alert_mgr = AlertManager(config_path='data_plane/monitoring/monitoring_config.yaml')

    print("\n✅ Monitoring data quality...\n")

    # Simulate data quality metrics
    for i in range(10):
        # Simulate degrading data quality
        completeness = 1.0 - i * 0.03  # Decreases from 100% to 73%
        staleness = i * 10  # Increases from 0 to 90 seconds

        exporter.record_data_quality(
            completeness=completeness,
            staleness_seconds=staleness
        )

        print(f"  Time {i+1}: Completeness={completeness:.1%}, Staleness={staleness}s", end="")

        # Alert on low completeness
        if completeness < 0.95:
            print(" ⚠️ LOW COMPLETENESS")
            alert_mgr.send_alert(
                **AlertTemplates.data_quality_issue(
                    "Low Completeness",
                    f"Data completeness at {completeness:.1%} (threshold: 95%)"
                )
            )
        # Alert on high staleness
        elif staleness > 60:
            print(" ⚠️ HIGH STALENESS")
            alert_mgr.medium(
                title="Data Staleness High",
                message=f"Data staleness at {staleness}s (threshold: 60s)",
                component="data_pipeline"
            )
        else:
            print(" ✓ OK")

        time.sleep(0.5)

    print()


def example_integrated_monitoring():
    """Example: Full integrated monitoring (realistic scenario)."""

    print("=" * 70)
    print("Example 5: Integrated Monitoring (Realistic Scenario)")
    print("=" * 70)

    exporter = get_metrics_exporter(port=8000)
    alert_mgr = AlertManager(config_path='data_plane/monitoring/monitoring_config.yaml')

    print("\n✅ Running full trading simulation with monitoring...\n")

    # Simulate a trading day
    for hour in range(7):  # 7 hours of trading
        print(f"Hour {hour + 1}/7:")

        # Simulate normal trading
        pnl = 0.01 + hour * 0.003
        sharpe = 1.5 + hour * 0.1
        latency = np.random.normal(45, 10)

        exporter.record_pnl(cumulative_pnl=pnl)
        exporter.record_sharpe_ratio(sharpe_30d=sharpe)
        exporter.record_order_latency(latency, "intent_to_ack")
        exporter.record_exposure(gross=1.5, net=0.6)

        print(f"  PnL={pnl:.2%}, Sharpe={sharpe:.2f}, Latency={latency:.1f}ms")

        # Simulate occasional events
        if hour == 3:
            # High latency spike
            spike_latency = 250
            exporter.record_order_latency(spike_latency, "intent_to_ack")
            alert_mgr.send_alert(
                **AlertTemplates.high_latency(spike_latency, 200)
            )
            print("  ⚠️  High latency spike detected and alerted")

        if hour == 5:
            # Optimization failure
            exporter.record_optimization_failure()
            alert_mgr.send_alert(
                **AlertTemplates.optimization_failure("Matrix not PSD")
            )
            print("  ⚠️  Optimization failure detected and alerted")

        # Record system health
        exporter.record_system_health(
            cpu_percent=50 + hour * 5,
            memory_mb=2048 + hour * 200
        )

        time.sleep(1)

    print("\n✅ Trading day complete. Check metrics and alerts.\n")
    print(f"View metrics at: http://localhost:8000/metrics")
    print(f"Alerts sent to configured channels (Slack/Email)")
    print()


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  Algo-Trade Monitoring & Alerting Examples".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    try:
        # Run examples
        example_metrics_recording()
        input("Press Enter to continue to alerting examples...")

        example_alerting()
        input("Press Enter to continue to kill switch monitoring...")

        example_kill_switch_monitoring()
        input("Press Enter to continue to data quality monitoring...")

        example_data_quality_monitoring()
        input("Press Enter to continue to integrated monitoring...")

        example_integrated_monitoring()

        print("\n" + "=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Configure Prometheus to scrape http://localhost:8000/metrics")
        print("2. Import Grafana dashboards (see README.md)")
        print("3. Configure alert channels in monitoring_config.yaml")
        print("4. Integrate monitoring into main trading engine")
        print()

    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
