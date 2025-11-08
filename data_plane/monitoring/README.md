# Monitoring & Observability

מערכת מוניטורינג מקיפה למערכת המסחר האלגוריתמית, כוללת Prometheus metrics, Grafana dashboards, ומערכת התראות רב-ערוצית.

---

## 📊 סקירה כללית

המערכת כוללת שלושה רכיבים עיקריים:

1. **Prometheus Metrics Exporter** (`metrics_exporter.py`)
   - יצוא מטריקות למוניטורינג בזמן אמת
   - 50+ מטריקות בקטגוריות: latency, performance, risk, errors, system health

2. **Alert Manager** (`alerting.py`)
   - מערכת התראות רב-ערוצית (Slack, Email, PagerDuty)
   - 4 רמות חומרה (P0, P1, P2, INFO)
   - Rate limiting ו-aggregation למניעת alert fatigue

3. **Grafana Dashboards** (`dashboards/`)
   - 4 דאשבורדים: System Health, Strategy Performance, Risk Monitor, Data Quality
   - Refresh intervals אוטומטיים
   - Alert panels משולבים

---

## 🚀 Quick Start

### 1. התקנת Dependencies

```bash
pip install prometheus-client requests pyyaml
```

### 2. הפעלת Metrics Exporter

```python
from data_plane.monitoring.metrics_exporter import get_metrics_exporter

# Initialize and start metrics endpoint
exporter = get_metrics_exporter(port=8000)

# Record metrics
exporter.record_pnl(cumulative_pnl=0.025, daily_pnl=0.003)
exporter.record_order_latency(latency_ms=45.3, latency_type="intent_to_ack")
exporter.record_exposure(gross=1.5, net=0.6)
exporter.set_kill_switch("pnl", active=False)
```

### 3. שליחת התראות

```python
from data_plane.monitoring.alerting import AlertManager

# Initialize alert manager
alert_mgr = AlertManager(config_path='monitoring_config.yaml')

# Send alerts
alert_mgr.critical(
    title="Kill Switch Activated",
    message="PnL kill switch triggered: -5.2%",
    component="risk_management"
)

alert_mgr.high(
    title="IBKR Connection Lost",
    message="Connection to Interactive Brokers lost",
    component="ibkr_integration"
)
```

### 4. הצגת Metrics

נווט ל-`http://localhost:8000/metrics` כדי לראות את כל המטריקות בפורמט Prometheus.

---

## 📈 Prometheus Setup

### התקנת Prometheus

```bash
# Download Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*
```

### קובץ התצורה (`prometheus.yml`)

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'algo_trade'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 10s
```

### הפעלת Prometheus

```bash
./prometheus --config.file=prometheus.yml
```

גש ל-`http://localhost:9090` כדי לגשת לממשק Prometheus.

---

## 📊 Grafana Dashboards

### התקנת Grafana

```bash
# Ubuntu/Debian
sudo apt-get install -y software-properties-common
sudo add-apt-repository "deb https://packages.grafana.com/oss/deb stable main"
sudo apt-get update
sudo apt-get install grafana

# Start Grafana
sudo systemctl start grafana-server
sudo systemctl enable grafana-server
```

גש ל-`http://localhost:3000` (default credentials: admin/admin)

### הוספת Data Source

1. לחץ על **Configuration → Data Sources**
2. לחץ **Add data source**
3. בחר **Prometheus**
4. הגדר URL: `http://localhost:9090`
5. לחץ **Save & Test**

### יצירת Dashboard #1: System Health

**Panels to Create:**

1. **CPU Usage**
   - Query: `algo_trade_cpu_usage_percent`
   - Visualization: Gauge
   - Thresholds: 70 (yellow), 90 (red)

2. **Memory Usage**
   - Query: `algo_trade_memory_usage_mb`
   - Visualization: Gauge
   - Thresholds: 8192 (yellow), 12288 (red)

3. **Order Latency (P50/P95/P99)**
   - Query P50: `histogram_quantile(0.50, rate(algo_trade_intent_to_ack_latency_ms_bucket[5m]))`
   - Query P95: `histogram_quantile(0.95, rate(algo_trade_intent_to_ack_latency_ms_bucket[5m]))`
   - Query P99: `histogram_quantile(0.99, rate(algo_trade_intent_to_ack_latency_ms_bucket[5m]))`
   - Visualization: Time series
   - Y-axis: Milliseconds

4. **Error Rate**
   - Query: `rate(algo_trade_errors_total[5m])`
   - Visualization: Graph
   - Alert: > 0.5 errors/sec

5. **Throughput**
   - Query: `algo_trade_throughput_msg_per_sec`
   - Visualization: Stat
   - Unit: msg/s

6. **Active Positions**
   - Query: `algo_trade_active_positions`
   - Visualization: Stat
   - Unit: positions

### יצירת Dashboard #2: Strategy Performance

**Panels:**

1. **Cumulative P&L**
   - Query: `algo_trade_pnl_cumulative`
   - Visualization: Graph with fill
   - Format: Percent (0.00%)

2. **Daily P&L**
   - Query: `algo_trade_pnl_daily`
   - Visualization: Bar gauge
   - Format: Percent

3. **Sharpe Ratio (30d)**
   - Query: `algo_trade_sharpe_ratio_rolling_30d`
   - Visualization: Gauge
   - Thresholds: 0.5 (yellow), 1.0 (green), 1.5 (bright green)

4. **Max Drawdown**
   - Query: `algo_trade_max_drawdown_current`
   - Visualization: Gauge (inverted colors)
   - Thresholds: 0.10 (yellow), 0.15 (red)

5. **Win Rate**
   - Query: `algo_trade_win_rate`
   - Visualization: Stat
   - Format: Percent
   - Thresholds: 0.50 (yellow), 0.60 (green)

6. **Profit Factor**
   - Query: `algo_trade_profit_factor`
   - Visualization: Stat
   - Thresholds: 1.0 (yellow), 1.5 (green)

### יצירת Dashboard #3: Risk Monitor

**Panels:**

1. **Gross Exposure**
   - Query: `algo_trade_gross_exposure`
   - Visualization: Gauge
   - Max: 2.5 (Calm limit)

2. **Net Exposure**
   - Query: `algo_trade_net_exposure`
   - Visualization: Graph with fill
   - Range: -1.0 to 1.0

3. **Portfolio Volatility**
   - Query: `algo_trade_portfolio_volatility`
   - Visualization: Stat
   - Format: Percent (annualized)

4. **VaR 95%**
   - Query: `algo_trade_var_95`
   - Visualization: Gauge
   - Thresholds: 0.05 (yellow), 0.10 (red)

5. **Kill Switches Status**
   - Query PnL: `algo_trade_kill_switch_pnl_active`
   - Query PSR: `algo_trade_kill_switch_psr_active`
   - Query DD: `algo_trade_kill_switch_drawdown_active`
   - Visualization: Stat (1=ACTIVE, 0=INACTIVE)
   - Color: Red if 1, Green if 0

6. **Market Regime**
   - Query: `algo_trade_market_regime`
   - Visualization: Stat
   - Values: Calm, Normal, Storm

### יצירת Dashboard #4: Data Quality

**Panels:**

1. **Data Completeness**
   - Query: `algo_trade_data_completeness`
   - Visualization: Gauge
   - Thresholds: 0.90 (yellow), 0.95 (green)

2. **Data Staleness**
   - Query: `algo_trade_data_staleness_seconds`
   - Visualization: Stat
   - Unit: Seconds
   - Alert: > 60 seconds

3. **Missing Ticks Rate**
   - Query: `rate(algo_trade_missing_ticks_total[1h])`
   - Visualization: Graph
   - Alert: > 10/hour

4. **Data Gaps**
   - Query: `rate(algo_trade_data_gaps_total[1h])`
   - Visualization: Stat
   - Alert: > 5/hour

5. **IBKR Pacing Violations**
   - Query: `rate(algo_trade_ibkr_pacing_violations_total[1h])`
   - Visualization: Stat
   - Alert: > 3/hour

6. **IBKR API Rate**
   - Query: `algo_trade_ibkr_api_rate`
   - Visualization: Graph
   - Max safe: 45 requests/sec
   - Hard limit: 50 requests/sec

### Import Dashboard from JSON

אם יש לך קבצי JSON של dashboards, תוכל לייבא אותם:

1. **Grafana UI** → **Dashboards** → **Import**
2. העלה את קובץ ה-JSON או הדבק את התוכן
3. בחר את ה-Prometheus data source
4. לחץ **Import**

---

## 🔔 Alerting Configuration

### Slack Integration

1. צור Slack App ב-[https://api.slack.com/apps](https://api.slack.com/apps)
2. הפעל **Incoming Webhooks**
3. הוסף webhook ל-channel `#algo-trade-alerts`
4. העתק את ה-Webhook URL
5. הגדר environment variable:

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

### Email Integration (Gmail)

1. צור App Password ב-Gmail:
   - Settings → Security → 2-Step Verification → App passwords
2. צור סיסמה ל-"Mail"
3. הגדר environment variables:

```bash
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-password"
```

### PagerDuty Integration (Optional)

1. צור Service ב-PagerDuty
2. צור Integration (Events API v2)
3. העתק את ה-Integration Key
4. הגדר environment variable:

```bash
export PAGERDUTY_API_KEY="your-integration-key"
```

---

## 📋 Alert Rules (Grafana)

### Creating Alert Rules in Grafana

1. **High Latency Alert**
   - Panel: Order Latency P95
   - Condition: `WHEN percentile(95) OF query(A, 5m) IS ABOVE 200`
   - Frequency: Evaluate every 1m for 5m
   - Send to: Slack, Email

2. **PnL Kill Switch Alert**
   - Panel: Cumulative P&L
   - Condition: `WHEN last() OF query(A, 5m) IS BELOW -0.05`
   - Frequency: Evaluate every 30s for 2m
   - Send to: Slack, Email, PagerDuty

3. **Data Staleness Alert**
   - Panel: Data Staleness
   - Condition: `WHEN last() OF query(A, 1m) IS ABOVE 60`
   - Frequency: Evaluate every 30s for 2m
   - Send to: Slack, Email

4. **IBKR Connection Lost**
   - Panel: IBKR Connection Errors
   - Condition: `WHEN diff() OF query(A, 1m) IS ABOVE 0`
   - Frequency: Evaluate every 10s for 30s
   - Send to: Slack, Email, PagerDuty

---

## 🛠️ Integration with Trading Engine

### הוספת Monitoring למנוע המסחר

**In `algo_trade/core/main.py`:**

```python
from data_plane.monitoring.metrics_exporter import get_metrics_exporter
from data_plane.monitoring.alerting import AlertManager, AlertTemplates

# Initialize monitoring
exporter = get_metrics_exporter(port=8000)
alert_mgr = AlertManager(config_path='data_plane/monitoring/monitoring_config.yaml')

def run_day(t, prices, returns, w, lam, linucb, C_prev, params):
    """Main trading loop with monitoring."""

    # Start timer for latency tracking
    start_time = time.time()

    # ... your trading logic ...

    # Record signal generation latency
    signal_time = time.time()
    exporter.record_signal_generation_latency((signal_time - start_time) * 1000)

    # ... portfolio optimization ...

    # Record optimization latency
    opt_time = time.time()
    exporter.record_optimization_latency((opt_time - signal_time) * 1000)

    # Record performance metrics
    exporter.record_pnl(cumulative_pnl=cum_pnl, daily_pnl=day_pnl)
    exporter.record_sharpe_ratio(sharpe_30d=sharpe)
    exporter.record_drawdown(current_dd=curr_dd, max_dd=max_dd)

    # Record risk metrics
    gross = np.abs(w).sum()
    net = w.sum()
    exporter.record_exposure(gross=gross, net=net)
    exporter.record_portfolio_risk(volatility=port_vol)

    # Check kill switches
    if pnl_kill_switch(pnl_hist):
        exporter.set_kill_switch("pnl", active=True)
        alert_mgr.send_alert(**AlertTemplates.kill_switch_activated(
            "PnL", cum_pnl, params["KILL_PNL"]
        ))

    # Record system health
    import psutil
    exporter.record_system_health(
        cpu_percent=psutil.cpu_percent(),
        memory_mb=psutil.Process().memory_info().rss / 1024 / 1024
    )

    return net_ret, w, lam, C_new, info, w_hrp, w_bl
```

---

## 📚 Available Metrics

### Latency Metrics (Histogram)
- `algo_trade_intent_to_ack_latency_ms` - Order intent to broker acknowledgment
- `algo_trade_order_placement_latency_ms` - Order placement time
- `algo_trade_order_fill_latency_ms` - Order submission to fill time
- `algo_trade_signal_generation_latency_ms` - Signal generation time
- `algo_trade_portfolio_optimization_latency_ms` - Portfolio optimization time

### Performance Metrics (Gauge)
- `algo_trade_pnl_cumulative` - Cumulative P&L
- `algo_trade_pnl_daily` - Daily P&L
- `algo_trade_sharpe_ratio_rolling_30d` - 30-day Sharpe ratio
- `algo_trade_sharpe_ratio_rolling_90d` - 90-day Sharpe ratio
- `algo_trade_max_drawdown_current` - Current drawdown
- `algo_trade_max_drawdown_historical` - Historical max drawdown
- `algo_trade_win_rate` - Win rate (fraction)
- `algo_trade_profit_factor` - Profit factor

### Risk Metrics (Gauge)
- `algo_trade_gross_exposure` - Gross exposure
- `algo_trade_net_exposure` - Net exposure
- `algo_trade_portfolio_volatility` - Portfolio volatility (annualized)
- `algo_trade_portfolio_beta` - Portfolio beta
- `algo_trade_largest_position_pct` - Largest position %
- `algo_trade_var_95` - Value at Risk 95%
- `algo_trade_cvar_95` - Conditional VaR 95%

### Kill Switches (Gauge 0/1)
- `algo_trade_kill_switch_pnl_active` - PnL kill switch status
- `algo_trade_kill_switch_psr_active` - PSR kill switch status
- `algo_trade_kill_switch_drawdown_active` - Drawdown kill switch status

### Order Metrics (Counter)
- `algo_trade_orders_submitted_total` - Total orders submitted
- `algo_trade_orders_filled_total` - Total orders filled
- `algo_trade_orders_cancelled_total` - Total orders cancelled
- `algo_trade_orders_rejected_total` - Total orders rejected

### Error Metrics (Counter)
- `algo_trade_errors_total{error_type}` - Total errors by type
- `algo_trade_ibkr_connection_errors_total` - IBKR connection errors
- `algo_trade_data_quality_errors_total{error_type}` - Data quality errors
- `algo_trade_optimization_failures_total` - Optimization failures

### System Health (Gauge)
- `algo_trade_cpu_usage_percent` - CPU usage %
- `algo_trade_memory_usage_mb` - Memory usage MB
- `algo_trade_throughput_msg_per_sec` - Message throughput
- `algo_trade_active_positions` - Active position count
- `algo_trade_connected_clients` - Connected client count

### Data Quality (Gauge/Counter)
- `algo_trade_data_completeness` - Data completeness (0-1)
- `algo_trade_data_staleness_seconds` - Data staleness (seconds)
- `algo_trade_missing_ticks_total` - Missing ticks count
- `algo_trade_data_gaps_total` - Data gaps count

### IBKR Specific (Counter/Gauge)
- `algo_trade_ibkr_pacing_violations_total` - Pacing violations
- `algo_trade_ibkr_reconnections_total` - Reconnection count
- `algo_trade_ibkr_api_rate` - API request rate (req/sec)

---

## 🧪 Testing

### Manual Testing

```python
# Start metrics exporter
from data_plane.monitoring.metrics_exporter import get_metrics_exporter

exporter = get_metrics_exporter(port=8000)

# Simulate metrics
import time
for i in range(100):
    exporter.record_pnl(cumulative_pnl=0.01 + i * 0.001)
    exporter.record_sharpe_ratio(sharpe_30d=1.5 + i * 0.01)
    exporter.record_exposure(gross=1.5, net=0.6)
    time.sleep(1)
```

Check metrics at: `http://localhost:8000/metrics`

### Alert Testing

```python
from data_plane.monitoring.alerting import AlertManager

alert_mgr = AlertManager(config_path='monitoring_config.yaml')

# Test all severity levels
alert_mgr.info("Test Info", "This is an info alert", "testing")
alert_mgr.medium("Test Medium", "This is a medium alert", "testing")
alert_mgr.high("Test High", "This is a high alert", "testing")
alert_mgr.critical("Test Critical", "This is a critical alert", "testing")
```

---

## 🔧 Troubleshooting

### Metrics endpoint not accessible

```bash
# Check if exporter is running
curl http://localhost:8000/metrics

# Check firewall
sudo ufw allow 8000/tcp
```

### Slack alerts not sending

```bash
# Test webhook manually
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test alert"}' \
  $SLACK_WEBHOOK_URL
```

### Grafana dashboard shows "No data"

1. Verify Prometheus is scraping:
   - Go to Prometheus UI → Status → Targets
   - Check if `algo_trade` target is UP

2. Verify metrics are being exported:
   - `curl http://localhost:8000/metrics | grep algo_trade`

3. Check Grafana data source:
   - Configuration → Data Sources → Prometheus → Test

---

## 📖 References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [PRE_LIVE_CHECKLIST.md](../../PRE_LIVE_CHECKLIST.md) - Section 7: Monitoring & Observability

---

**עודכן:** 2025-11-08
**גרסה:** 1.0
**מחבר:** Claude Code (AI Assistant)
