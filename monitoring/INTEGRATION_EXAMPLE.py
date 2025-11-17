"""
Example: How to integrate metrics and logging into existing services

This file shows practical examples of adding monitoring to the Algo-Trading system.
"""

# =============================================================================
# EXAMPLE 1: Data Plane - Market Data Ingestion
# =============================================================================

def data_plane_example():
    """Example: Adding metrics to data plane ingestion."""
    import time
    from data_plane.monitoring.metrics_exporter import init_metrics_exporter, get_metrics_exporter
    from shared.logging import init_structured_logger, TraceContext, PerformanceLogger

    # Initialize at service startup (once)
    metrics = init_metrics_exporter(port=9090, start_system_monitor=True)
    logger = init_structured_logger("data_plane", environment="production")

    # Process market data event
    def process_bar_event(bar_event):
        conid = bar_event.conid
        market_timestamp = bar_event.timestamp
        system_timestamp = time.time()

        with TraceContext() as trace:
            logger.info("Processing bar event", conid=conid, symbol=bar_event.symbol)

            # Record ingestion
            metrics.inc("data_ingestion_events", labels={
                "event_type": "BarEvent",
                "conid": str(conid)
            })

            # Calculate and record latency
            latency_ms = (system_timestamp - market_timestamp) * 1000
            metrics.observe("data_ingestion_latency_ms", latency_ms, labels={
                "event_type": "BarEvent"
            })

            # Data quality check
            quality_score = check_data_quality(bar_event)
            metrics.set_gauge("data_quality_score", quality_score, labels={
                "conid": str(conid),
                "dimension": "completeness"
            })

            # If quality is low, alert
            if quality_score < 0.95:
                logger.warning("Low data quality", conid=conid, quality=quality_score)
                metrics.inc("data_gaps", labels={"conid": str(conid)})

            logger.info("Bar event processed", conid=conid, latency_ms=latency_ms)


# =============================================================================
# EXAMPLE 2: Strategy Plane - Signal Generation & Portfolio Optimization
# =============================================================================

def strategy_plane_example():
    """Example: Adding metrics to strategy plane."""
    import time
    from data_plane.monitoring.metrics_exporter import get_metrics_exporter
    from shared.logging import init_structured_logger, PerformanceLogger

    metrics = get_metrics_exporter()
    logger = init_structured_logger("strategy_plane", environment="production")

    # Generate trading signals
    def generate_signals(market_data):
        with PerformanceLogger(logger, "signal_generation") as perf:
            start = time.perf_counter()

            # Generate OFI signal
            ofi_signal = calculate_ofi(market_data)
            metrics.inc("signals_generated", labels={"signal_type": "OFI"})

            # Track signal generation duration
            duration_ms = (time.perf_counter() - start) * 1000
            metrics.observe("signal_generation_duration_ms", duration_ms, labels={
                "signal_type": "OFI"
            })

            logger.info("Signal generated", signal_type="OFI", value=ofi_signal)

        return ofi_signal

    # Portfolio optimization
    def optimize_portfolio(signals, covariance_matrix):
        with PerformanceLogger(logger, "portfolio_optimization"):
            start = time.perf_counter()

            try:
                # Run QP solver
                weights = qp_solver(signals, covariance_matrix)

                duration_ms = (time.perf_counter() - start) * 1000
                metrics.observe("optimization_duration_ms", duration_ms, labels={
                    "optimizer": "qp"
                })

                logger.info("Optimization succeeded", duration_ms=duration_ms)
                return weights

            except Exception as e:
                metrics.inc("optimization_errors", labels={"optimizer": "qp"})
                logger.exception("Optimization failed", optimizer="qp")
                raise

    # Update portfolio metrics
    def update_portfolio_metrics(portfolio_state):
        metrics.set_gauge("portfolio_value", portfolio_state.value_usd)
        metrics.set_gauge("portfolio_pnl", portfolio_state.daily_pnl, labels={
            "period": "daily"
        })
        metrics.set_gauge("portfolio_positions", len(portfolio_state.positions))
        metrics.set_gauge("max_drawdown", portfolio_state.max_drawdown_percent)
        metrics.set_gauge("sharpe_ratio", portfolio_state.sharpe_ratio, labels={
            "period": "daily"
        })

        # Market regime
        regime = portfolio_state.market_regime  # 0=Calm, 1=Normal, 2=Storm
        metrics.set_gauge("market_regime", regime)

        if regime == 2:  # Storm
            logger.warning("Market regime changed to STORM", regime=regime)


# =============================================================================
# EXAMPLE 3: Order Plane - Order Execution & Risk Checks
# =============================================================================

def order_plane_example():
    """Example: Adding metrics to order plane."""
    import time
    from data_plane.monitoring.metrics_exporter import get_metrics_exporter
    from shared.logging import init_structured_logger, TraceContext

    metrics = get_metrics_exporter()
    logger = init_structured_logger("order_plane", environment="production")

    # Submit order
    def submit_order(order_intent):
        with TraceContext() as trace:
            logger.info("Submitting order", order_id=order_intent.order_id,
                       symbol=order_intent.symbol, quantity=order_intent.quantity)

            # Pre-trade risk checks
            if not risk_check_passed(order_intent):
                logger.warning("Risk check failed", order_id=order_intent.order_id,
                              reason="position_limit_exceeded")
                metrics.inc("risk_check_rejects", labels={
                    "reason": "position_limit_exceeded"
                })
                return None

            # Track order submission
            start_time = time.perf_counter()

            # Submit to broker
            order_status = broker_submit(order_intent)

            metrics.inc("orders", labels={
                "order_type": order_intent.order_type,
                "side": order_intent.side,
                "status": "submitted"
            })

            logger.info("Order submitted", order_id=order_intent.order_id,
                       status=order_status)

            return order_status

    # Handle fill
    def handle_fill(execution_report):
        with TraceContext(trace_id=execution_report.trace_id):
            # Calculate order latency
            latency_ms = (time.time() - execution_report.submit_time) * 1000

            metrics.observe("order_latency_ms", latency_ms, labels={
                "order_type": execution_report.order_type
            })

            # Record fill
            metrics.inc("fills", labels={
                "conid": str(execution_report.conid),
                "symbol": execution_report.symbol
            })

            # Calculate slippage
            slippage_bps = calculate_slippage(execution_report)
            metrics.observe("slippage_bps", slippage_bps, labels={
                "conid": str(execution_report.conid),
                "symbol": execution_report.symbol
            })

            # Transaction cost
            cost_bps = execution_report.commission_bps + slippage_bps
            metrics.observe("transaction_cost_bps", cost_bps, labels={
                "conid": str(execution_report.conid),
                "symbol": execution_report.symbol
            })

            logger.info("Order filled", order_id=execution_report.order_id,
                       fill_price=execution_report.fill_price,
                       slippage_bps=slippage_bps,
                       latency_ms=latency_ms)

    # Kill switch trigger
    def check_kill_switch(portfolio_state):
        # Check max drawdown
        if portfolio_state.max_drawdown_percent > 15:
            logger.critical("KILL SWITCH TRIGGERED - Max Drawdown Exceeded",
                          drawdown=portfolio_state.max_drawdown_percent,
                          threshold=15)

            metrics.set_gauge("kill_switch_status", 1, labels={
                "switch_type": "max_drawdown"
            })
            metrics.inc("kill_switch_triggers", labels={
                "trigger_type": "max_drawdown"
            })

            return True

        return False


# =============================================================================
# EXAMPLE 4: IBKR Integration
# =============================================================================

def ibkr_integration_example():
    """Example: IBKR connection monitoring."""
    from data_plane.monitoring.metrics_exporter import get_metrics_exporter
    from shared.logging import init_structured_logger

    metrics = get_metrics_exporter()
    logger = init_structured_logger("order_plane", environment="production")

    # Track connection status
    def on_connected():
        logger.info("IBKR connected")
        metrics.set_gauge("ibkr_connection_status", 1)

    def on_disconnected():
        logger.error("IBKR disconnected")
        metrics.set_gauge("ibkr_connection_status", 0)
        metrics.inc("ibkr_reconnects", labels={"success": "false"})

    def on_reconnected():
        logger.info("IBKR reconnected")
        metrics.set_gauge("ibkr_connection_status", 1)
        metrics.inc("ibkr_reconnects", labels={"success": "true"})

    # Track API errors
    def on_error(error_code, error_msg):
        logger.error("IBKR API error", error_code=error_code, error_msg=error_msg)

        metrics.inc("ibkr_api_errors", labels={
            "error_code": str(error_code),
            "error_type": classify_error(error_code)
        })

    # Track throttling
    def on_pacing_violation(endpoint):
        logger.warning("IBKR pacing violation", endpoint=endpoint)
        metrics.inc("ibkr_throttle_violations", labels={"endpoint": endpoint})


# =============================================================================
# EXAMPLE 5: NTP Drift Monitoring
# =============================================================================

def ntp_monitoring_example():
    """Example: NTP time drift monitoring."""
    import ntplib
    from data_plane.monitoring.metrics_exporter import get_metrics_exporter
    from shared.logging import init_structured_logger

    metrics = get_metrics_exporter()
    logger = init_structured_logger("data_plane", environment="production")

    def check_ntp_drift():
        try:
            client = ntplib.NTPClient()
            response = client.request('pool.ntp.org')

            # Calculate drift
            drift_ms = abs(response.offset * 1000)

            metrics.set_gauge("ntp_drift_ms", drift_ms)

            if drift_ms > 250:
                logger.critical("Critical NTP drift", drift_ms=drift_ms, threshold=250)
                metrics.inc("ntp_rejects")
            elif drift_ms > 100:
                logger.warning("High NTP drift", drift_ms=drift_ms, threshold=100)

            return drift_ms

        except Exception as e:
            logger.exception("NTP check failed")
            return None


# =============================================================================
# Dummy helper functions (replace with actual implementations)
# =============================================================================

def check_data_quality(bar_event):
    return 0.98

def calculate_ofi(market_data):
    return 0.5

def qp_solver(signals, covariance_matrix):
    return [0.1, 0.2, 0.3]

def risk_check_passed(order_intent):
    return True

def broker_submit(order_intent):
    return "submitted"

def calculate_slippage(execution_report):
    return 5.0  # bps

def classify_error(error_code):
    if error_code < 1000:
        return "system"
    elif error_code < 2000:
        return "market_data"
    else:
        return "order"


if __name__ == "__main__":
    print("This is an example file showing how to integrate monitoring.")
    print("Copy relevant sections to your actual service code.")
