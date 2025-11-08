"""
Alerting System for Algo-Trade
================================

Multi-channel alerting with rate limiting, aggregation, and escalation.

Supported Channels:
- Slack (webhooks)
- Email (SMTP)
- PagerDuty (API) - optional
- Console logging

Alert Severity Levels (from SECURITY_EXECUTION_SUMMARY.md):
- P0 (Critical): System-threatening, immediate action (<5 min)
- P1 (High): Service degradation, urgent action (<1 hour)
- P2 (Medium): Performance issue, action within 4 hours
- INFO: Informational, no immediate action

Features:
- Rate limiting to prevent alert fatigue
- Alert aggregation (deduplication)
- Escalation policies
- Alert playbooks (automatic runbook links)

Usage:
    from data_plane.monitoring.alerting import AlertManager

    alert_mgr = AlertManager(config_path='monitoring_config.yaml')

    # Send critical alert
    alert_mgr.send_alert(
        severity='P0',
        title='Kill Switch Activated',
        message='PnL kill switch triggered: -5.2%',
        component='risk_management'
    )
"""

import logging
import smtplib
import requests
import json
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict
from threading import Lock
import yaml

logger = logging.getLogger(__name__)


# ============================================================================
# Alert Data Structures
# ============================================================================

@dataclass
class Alert:
    """Alert data structure."""
    severity: str  # P0, P1, P2, INFO
    title: str
    message: str
    component: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    runbook_url: Optional[str] = None
    fingerprint: Optional[str] = None  # For deduplication

    def __post_init__(self):
        """Generate fingerprint for deduplication."""
        if self.fingerprint is None:
            self.fingerprint = f"{self.component}:{self.severity}:{self.title}"


@dataclass
class AlertConfig:
    """Alert configuration."""
    # Slack
    slack_webhook_url: Optional[str] = None
    slack_channel: str = "#algo-trade-alerts"

    # Email
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    email_from: Optional[str] = None
    email_to: List[str] = field(default_factory=list)

    # PagerDuty
    pagerduty_api_key: Optional[str] = None
    pagerduty_service_id: Optional[str] = None

    # Rate Limiting
    rate_limit_window_seconds: int = 300  # 5 minutes
    rate_limit_max_alerts: int = 10  # Max alerts per window

    # Aggregation
    aggregation_window_seconds: int = 60  # 1 minute
    enable_aggregation: bool = True

    # On-call schedule
    oncall_trader_hours: str = "09:00-18:00 UTC"  # Trading hours
    oncall_security_hours: str = "00:00-23:59 UTC"  # 24/7

    # Escalation
    escalation_p0_minutes: int = 5  # Escalate P0 if not acked in 5 min
    escalation_p1_minutes: int = 60  # Escalate P1 if not acked in 1 hour


class AlertManager:
    """
    Multi-channel alert manager with rate limiting and aggregation.
    """

    # Severity level priorities (lower = more urgent)
    SEVERITY_PRIORITY = {
        "P0": 0,  # Critical
        "P1": 1,  # High
        "P2": 2,  # Medium
        "INFO": 3,  # Informational
    }

    # Alert emojis for Slack
    SEVERITY_EMOJI = {
        "P0": ":rotating_light:",
        "P1": ":warning:",
        "P2": ":large_orange_diamond:",
        "INFO": ":information_source:",
    }

    # Alert colors for Slack
    SEVERITY_COLOR = {
        "P0": "#FF0000",  # Red
        "P1": "#FF9900",  # Orange
        "P2": "#FFCC00",  # Yellow
        "INFO": "#36A64F",  # Green
    }

    def __init__(self, config: Optional[AlertConfig] = None, config_path: Optional[str] = None):
        """
        Initialize alert manager.

        Args:
            config: AlertConfig object
            config_path: Path to YAML config file
        """
        if config_path:
            self.config = self._load_config(config_path)
        elif config:
            self.config = config
        else:
            self.config = AlertConfig()  # Default config

        # Rate limiting state
        self._rate_limit_lock = Lock()
        self._rate_limit_counts: Dict[str, List[datetime]] = defaultdict(list)

        # Aggregation state
        self._aggregation_lock = Lock()
        self._pending_alerts: Dict[str, Alert] = {}  # fingerprint -> Alert
        self._last_aggregation_flush = datetime.utcnow()

        # Alert history (for deduplication)
        self._alert_history_lock = Lock()
        self._recent_alerts: Set[str] = set()  # fingerprints
        self._last_history_cleanup = datetime.utcnow()

        logger.info("AlertManager initialized")

    def _load_config(self, config_path: str) -> AlertConfig:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                config_dict = yaml.safe_load(f).get('alerting', {})
            return AlertConfig(**config_dict)
        except Exception as e:
            logger.error(f"Failed to load alerting config: {e}. Using defaults.")
            return AlertConfig()

    # ========================================================================
    # Main Alert Sending Method
    # ========================================================================

    def send_alert(
        self,
        severity: str,
        title: str,
        message: str,
        component: str,
        tags: Optional[Dict[str, str]] = None,
        runbook_url: Optional[str] = None,
    ) -> bool:
        """
        Send alert through configured channels.

        Args:
            severity: Alert severity (P0, P1, P2, INFO)
            title: Alert title (short description)
            message: Alert message (detailed description)
            component: Component that generated the alert
            tags: Additional tags (e.g., {"environment": "production"})
            runbook_url: URL to runbook for this alert

        Returns:
            True if alert sent successfully, False otherwise
        """
        # Validate severity
        if severity not in self.SEVERITY_PRIORITY:
            logger.error(f"Invalid severity: {severity}. Using INFO.")
            severity = "INFO"

        # Create alert object
        alert = Alert(
            severity=severity,
            title=title,
            message=message,
            component=component,
            tags=tags or {},
            runbook_url=runbook_url,
        )

        # Check if alert should be suppressed (rate limit or deduplication)
        if self._should_suppress_alert(alert):
            logger.debug(f"Alert suppressed: {alert.fingerprint}")
            return False

        # If aggregation enabled, add to pending alerts
        if self.config.enable_aggregation and severity in ["P2", "INFO"]:
            self._add_to_aggregation(alert)
            return True

        # Send alert immediately (P0, P1, or aggregation disabled)
        return self._send_alert_now(alert)

    def _should_suppress_alert(self, alert: Alert) -> bool:
        """Check if alert should be suppressed due to rate limiting or deduplication."""

        # Check rate limiting
        if self._is_rate_limited(alert.severity):
            return True

        # Check deduplication (skip for P0 alerts)
        if alert.severity != "P0" and self._is_duplicate(alert.fingerprint):
            return True

        return False

    def _is_rate_limited(self, severity: str) -> bool:
        """Check if alerts of this severity are rate limited."""
        with self._rate_limit_lock:
            now = datetime.utcnow()
            window_start = now - timedelta(seconds=self.config.rate_limit_window_seconds)

            # Get recent alerts for this severity
            recent = self._rate_limit_counts[severity]

            # Remove old alerts
            recent = [ts for ts in recent if ts > window_start]
            self._rate_limit_counts[severity] = recent

            # Check if limit exceeded
            if len(recent) >= self.config.rate_limit_max_alerts:
                logger.warning(f"Rate limit exceeded for severity {severity}")
                return True

            # Record this alert
            recent.append(now)
            return False

    def _is_duplicate(self, fingerprint: str) -> bool:
        """Check if alert is a duplicate of a recent alert."""
        with self._alert_history_lock:
            now = datetime.utcnow()

            # Clean up old history (every 10 minutes)
            if (now - self._last_history_cleanup).total_seconds() > 600:
                self._recent_alerts.clear()
                self._last_history_cleanup = now

            # Check if duplicate
            if fingerprint in self._recent_alerts:
                return True

            # Record this alert
            self._recent_alerts.add(fingerprint)
            return False

    # ========================================================================
    # Aggregation
    # ========================================================================

    def _add_to_aggregation(self, alert: Alert):
        """Add alert to pending aggregation buffer."""
        with self._aggregation_lock:
            # Add or update alert in buffer
            self._pending_alerts[alert.fingerprint] = alert

            # Check if aggregation window expired
            now = datetime.utcnow()
            if (now - self._last_aggregation_flush).total_seconds() > self.config.aggregation_window_seconds:
                self._flush_aggregated_alerts()

    def _flush_aggregated_alerts(self):
        """Flush aggregated alerts."""
        if not self._pending_alerts:
            return

        logger.info(f"Flushing {len(self._pending_alerts)} aggregated alerts")

        # Group alerts by severity
        alerts_by_severity = defaultdict(list)
        for alert in self._pending_alerts.values():
            alerts_by_severity[alert.severity].append(alert)

        # Send aggregated alerts
        for severity, alerts in alerts_by_severity.items():
            if len(alerts) == 1:
                # Send single alert
                self._send_alert_now(alerts[0])
            else:
                # Send aggregated alert
                self._send_aggregated_alert(severity, alerts)

        # Clear buffer
        self._pending_alerts.clear()
        self._last_aggregation_flush = datetime.utcnow()

    def _send_aggregated_alert(self, severity: str, alerts: List[Alert]):
        """Send aggregated alert summary."""
        title = f"{len(alerts)} {severity} Alerts"
        message = "\n\n".join([
            f"• {alert.component}: {alert.title}\n  {alert.message}"
            for alert in alerts
        ])

        aggregated = Alert(
            severity=severity,
            title=title,
            message=message,
            component="aggregation",
            timestamp=datetime.utcnow(),
        )

        self._send_alert_now(aggregated)

    # ========================================================================
    # Alert Sending to Channels
    # ========================================================================

    def _send_alert_now(self, alert: Alert) -> bool:
        """Send alert immediately through all configured channels."""
        success = True

        # Send to Slack
        if self.config.slack_webhook_url:
            if not self._send_to_slack(alert):
                success = False

        # Send to Email
        if self.config.smtp_host and self.config.email_to:
            if not self._send_to_email(alert):
                success = False

        # Send to PagerDuty (P0/P1 only)
        if self.config.pagerduty_api_key and alert.severity in ["P0", "P1"]:
            if not self._send_to_pagerduty(alert):
                success = False

        # Always log to console
        self._log_to_console(alert)

        return success

    def _send_to_slack(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        try:
            emoji = self.SEVERITY_EMOJI.get(alert.severity, ":bell:")
            color = self.SEVERITY_COLOR.get(alert.severity, "#808080")

            # Build Slack message
            attachments = [{
                "color": color,
                "title": f"{emoji} {alert.title}",
                "text": alert.message,
                "fields": [
                    {
                        "title": "Severity",
                        "value": alert.severity,
                        "short": True
                    },
                    {
                        "title": "Component",
                        "value": alert.component,
                        "short": True
                    },
                    {
                        "title": "Timestamp",
                        "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "short": True
                    },
                ],
                "footer": "Algo-Trade Alert System",
                "ts": int(alert.timestamp.timestamp())
            }]

            # Add runbook link if available
            if alert.runbook_url:
                attachments[0]["fields"].append({
                    "title": "Runbook",
                    "value": f"<{alert.runbook_url}|View Runbook>",
                    "short": False
                })

            # Add tags
            if alert.tags:
                tags_str = ", ".join([f"{k}={v}" for k, v in alert.tags.items()])
                attachments[0]["fields"].append({
                    "title": "Tags",
                    "value": tags_str,
                    "short": False
                })

            payload = {
                "channel": self.config.slack_channel,
                "username": "Algo-Trade Alert",
                "attachments": attachments
            }

            response = requests.post(
                self.config.slack_webhook_url,
                json=payload,
                timeout=5
            )

            if response.status_code == 200:
                logger.info(f"Slack alert sent: {alert.title}")
                return True
            else:
                logger.error(f"Slack alert failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _send_to_email(self, alert: Alert) -> bool:
        """Send alert via email."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity}] {alert.title}"
            msg['From'] = self.config.email_from
            msg['To'] = ', '.join(self.config.email_to)

            # HTML body
            html = f"""
            <html>
              <body style="font-family: Arial, sans-serif;">
                <h2 style="color: {self.SEVERITY_COLOR.get(alert.severity, '#000')};">
                  {alert.title}
                </h2>
                <p><strong>Severity:</strong> {alert.severity}</p>
                <p><strong>Component:</strong> {alert.component}</p>
                <p><strong>Timestamp:</strong> {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
                <hr>
                <p>{alert.message.replace(chr(10), '<br>')}</p>
                {f'<p><a href="{alert.runbook_url}">View Runbook</a></p>' if alert.runbook_url else ''}
              </body>
            </html>
            """

            # Plain text body (fallback)
            text = f"""
{alert.title}

Severity: {alert.severity}
Component: {alert.component}
Timestamp: {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")}

{alert.message}

{f'Runbook: {alert.runbook_url}' if alert.runbook_url else ''}
            """

            msg.attach(MIMEText(text, 'plain'))
            msg.attach(MIMEText(html, 'html'))

            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)

            logger.info(f"Email alert sent: {alert.title}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False

    def _send_to_pagerduty(self, alert: Alert) -> bool:
        """Send alert to PagerDuty."""
        try:
            payload = {
                "routing_key": self.config.pagerduty_api_key,
                "event_action": "trigger",
                "dedup_key": alert.fingerprint,
                "payload": {
                    "summary": alert.title,
                    "severity": alert.severity.lower(),
                    "source": alert.component,
                    "timestamp": alert.timestamp.isoformat(),
                    "custom_details": {
                        "message": alert.message,
                        "tags": alert.tags,
                    }
                },
                "links": [
                    {"href": alert.runbook_url, "text": "Runbook"}
                ] if alert.runbook_url else []
            }

            response = requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            if response.status_code == 202:
                logger.info(f"PagerDuty alert sent: {alert.title}")
                return True
            else:
                logger.error(f"PagerDuty alert failed: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {e}")
            return False

    def _log_to_console(self, alert: Alert):
        """Log alert to console."""
        log_level = {
            "P0": logging.CRITICAL,
            "P1": logging.ERROR,
            "P2": logging.WARNING,
            "INFO": logging.INFO,
        }.get(alert.severity, logging.INFO)

        logger.log(
            log_level,
            f"[{alert.severity}] {alert.component}: {alert.title} - {alert.message}"
        )

    # ========================================================================
    # Convenience Methods
    # ========================================================================

    def critical(self, title: str, message: str, component: str, **kwargs):
        """Send P0 (critical) alert."""
        self.send_alert("P0", title, message, component, **kwargs)

    def high(self, title: str, message: str, component: str, **kwargs):
        """Send P1 (high) alert."""
        self.send_alert("P1", title, message, component, **kwargs)

    def medium(self, title: str, message: str, component: str, **kwargs):
        """Send P2 (medium) alert."""
        self.send_alert("P2", title, message, component, **kwargs)

    def info(self, title: str, message: str, component: str, **kwargs):
        """Send INFO alert."""
        self.send_alert("INFO", title, message, component, **kwargs)

    def flush(self):
        """Manually flush pending aggregated alerts."""
        with self._aggregation_lock:
            self._flush_aggregated_alerts()


# ============================================================================
# Predefined Alert Templates
# ============================================================================

class AlertTemplates:
    """Predefined alert templates for common scenarios."""

    @staticmethod
    def kill_switch_activated(switch_type: str, value: float, threshold: float) -> Dict:
        """Kill switch activation alert."""
        return {
            "severity": "P0",
            "title": f"Kill Switch Activated: {switch_type}",
            "message": f"{switch_type} kill switch triggered. Current: {value:.2%}, Threshold: {threshold:.2%}",
            "component": "risk_management",
            "runbook_url": "https://docs.example.com/runbooks/kill-switch"
        }

    @staticmethod
    def ibkr_connection_lost() -> Dict:
        """IBKR connection lost alert."""
        return {
            "severity": "P0",
            "title": "IBKR Connection Lost",
            "message": "Connection to Interactive Brokers lost. Trading halted.",
            "component": "ibkr_integration",
            "runbook_url": "https://docs.example.com/runbooks/ibkr-connection"
        }

    @staticmethod
    def high_latency(latency_ms: float, threshold_ms: float) -> Dict:
        """High latency alert."""
        return {
            "severity": "P1",
            "title": "High Order Latency Detected",
            "message": f"Order latency ({latency_ms:.1f}ms) exceeds threshold ({threshold_ms:.1f}ms)",
            "component": "order_execution",
            "runbook_url": "https://docs.example.com/runbooks/high-latency"
        }

    @staticmethod
    def data_quality_issue(issue_type: str, details: str) -> Dict:
        """Data quality issue alert."""
        return {
            "severity": "P2",
            "title": f"Data Quality Issue: {issue_type}",
            "message": details,
            "component": "data_pipeline",
            "runbook_url": "https://docs.example.com/runbooks/data-quality"
        }

    @staticmethod
    def optimization_failure(error: str) -> Dict:
        """Portfolio optimization failure alert."""
        return {
            "severity": "P1",
            "title": "Portfolio Optimization Failed",
            "message": f"Optimization failed: {error}. Using previous weights.",
            "component": "portfolio_optimization",
            "runbook_url": "https://docs.example.com/runbooks/optimization-failure"
        }
