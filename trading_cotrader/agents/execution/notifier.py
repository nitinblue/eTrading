"""
Notifier Agent — Sends notifications (console + optional email).

Email is off by default. Console logging always works.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus
from trading_cotrader.config.workflow_config_loader import WorkflowConfig

logger = logging.getLogger(__name__)


class NotifierAgent:
    """Sends notifications to console and optionally email."""

    name = "notifier"

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.email_config = config.notifications.email

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """Not called directly — use specific notify methods."""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            messages=["Notifier ready"],
        )

    def notify_recommendations(self, recs: List[dict]) -> None:
        """Notify user about new recommendations."""
        if not recs:
            return

        lines = [f"\n{'='*60}", "NEW RECOMMENDATIONS PENDING REVIEW", f"{'='*60}"]
        for rec in recs:
            lines.append(
                f"  [{rec.get('id', '?')[:8]}] {rec.get('underlying', '?')} "
                f"{rec.get('strategy_type', '?')} — "
                f"confidence={rec.get('confidence', '?')}"
            )
            if rec.get('rationale'):
                lines.append(f"    {rec['rationale'][:100]}")
        lines.append(f"{'='*60}")
        lines.append(f"  {len(recs)} recommendation(s). Use 'approve <id>' or 'reject <id>'.")
        lines.append("")

        msg = "\n".join(lines)
        self._log(msg)
        self._send(f"{len(recs)} New Recommendations Pending", msg)

    def notify_exits(self, signals: List[dict]) -> None:
        """Notify user about exit signals."""
        if not signals:
            return

        lines = [f"\n{'='*60}", "EXIT SIGNALS DETECTED", f"{'='*60}"]
        for sig in signals:
            urgency = sig.get('exit_urgency', 'normal')
            lines.append(
                f"  [{sig.get('id', '?')[:8]}] {sig.get('underlying', '?')} "
                f"{sig.get('type', '?')} — urgency={urgency}"
            )
            if sig.get('rationale'):
                lines.append(f"    {sig['rationale'][:100]}")
        lines.append(f"{'='*60}")
        lines.append("")

        msg = "\n".join(lines)
        self._log(msg)
        self._send(f"{len(signals)} Exit Signal(s)", msg)

    def notify_halt(self, reason: str) -> None:
        """Notify user about a trading halt."""
        msg = (
            f"\n{'!'*60}\n"
            f"TRADING HALTED\n"
            f"Reason: {reason}\n"
            f"Override requires written rationale.\n"
            f"{'!'*60}\n"
        )
        self._log(msg)
        self._send("TRADING HALTED", msg)

    def notify_idle_capital(self, alerts: List[dict]) -> None:
        """Notify user about idle capital with severity-graded alerts."""
        if not alerts:
            return

        lines = []
        for alert in alerts:
            sev = alert.get('severity', 'info').upper()
            pname = alert.get('portfolio', '?')
            idle = alert.get('idle_capital', 0)
            actual = alert.get('actual_deployed_pct', 0)
            target = alert.get('target_deployed_pct', 0)
            days = alert.get('days_idle')
            cost = alert.get('opp_cost_daily', 0)
            action = alert.get('suggested_action', '')

            lines.append(f"\nIDLE CAPITAL ALERT ({sev}):")
            lines.append(
                f"  {pname}: ${idle:,.0f} idle "
                f"({actual:.0f}% deployed, target {target:.0f}%)"
            )
            if days is not None:
                lines.append(f"  {days} days since last trade. Costing ${cost:,.2f}/day in missed returns.")
            if action:
                lines.append(f"  Action: {action}")

        msg = "\n".join(lines)
        self._log(msg)
        self._send("Idle Capital Alert", msg)

    def send_daily_summary(self, context: dict) -> None:
        """Send end-of-day summary."""
        report = context.get('daily_report', '')
        if report:
            self._log(report)
            self._send("Daily Trading Summary", report)

    def send_weekly_digest(self, context: dict) -> None:
        """Send weekly digest."""
        report = context.get('weekly_report', '')
        if report:
            self._log(report)
            self._send("Weekly Trading Digest", report)

    def _send(self, subject: str, body: str) -> None:
        """Send email if enabled."""
        if not self.email_config.enabled:
            return

        if not self.email_config.smtp_host or not self.email_config.to_address:
            logger.debug("Email enabled but SMTP not configured")
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config.from_address
            msg['To'] = self.email_config.to_address
            msg['Subject'] = f"[CoTrader] {subject}"
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(self.email_config.smtp_host, self.email_config.smtp_port) as server:
                server.starttls()
                server.send_message(msg)

            logger.info(f"Email sent: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email '{subject}': {e}")

    def _log(self, msg: str) -> None:
        """Always log to console."""
        print(f"[NOTIFY] {msg}")
