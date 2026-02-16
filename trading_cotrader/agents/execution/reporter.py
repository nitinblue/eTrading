"""
Reporter Agent — Generates daily and weekly reports.

Summarizes trades, P&L, portfolio state, pending decisions,
risk utilization, and tomorrow's calendar.
"""

from datetime import date, datetime
import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class ReporterAgent:
    """Generates structured reports from workflow context."""

    name = "reporter"

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """Generate daily summary report."""
        return self.generate_daily_summary(context)

    def generate_daily_summary(self, context: dict) -> AgentResult:
        """
        Generate end-of-day summary.

        Reads from context: portfolios, open_trades, risk_snapshot,
        pending_recommendations, exit_signals, accountability_metrics.

        Writes 'daily_report' to context.
        """
        try:
            lines = []
            lines.append(f"\n{'='*60}")
            lines.append(f"DAILY TRADING SUMMARY — {date.today()}")
            lines.append(f"{'='*60}")

            # Portfolio overview
            portfolios = context.get('portfolios', [])
            if portfolios:
                lines.append("\nPORTFOLIO SNAPSHOT:")
                lines.append(f"  {'Name':<20} {'Equity':>12} {'Daily P&L':>12} {'Delta':>8} {'Theta':>8}")
                lines.append(f"  {'-'*60}")
                for p in portfolios:
                    lines.append(
                        f"  {p.get('name', '?'):<20} "
                        f"${p.get('equity', 0):>10,.0f} "
                        f"${p.get('daily_pnl', 0):>10,.0f} "
                        f"{p.get('delta', 0):>8.1f} "
                        f"{p.get('theta', 0):>8.1f}"
                    )

            # Open trades
            open_trades = context.get('open_trades', [])
            lines.append(f"\nOPEN TRADES: {len(open_trades)}")
            if open_trades:
                for t in open_trades[:10]:  # cap at 10
                    lines.append(
                        f"  {t.get('underlying', '?'):<8} "
                        f"P&L=${t.get('pnl', 0):>8,.0f} "
                        f"delta={t.get('delta', 0):.1f}"
                    )
                if len(open_trades) > 10:
                    lines.append(f"  ... and {len(open_trades) - 10} more")

            # Risk
            risk = context.get('risk_snapshot', {})
            if risk:
                lines.append(f"\nRISK:")
                lines.append(f"  VaR 95%: ${risk.get('var_95', 0):,.0f}")
                lines.append(f"  Positions: {risk.get('open_positions', 0)}")

            # Pending decisions
            pending_recs = context.get('pending_recommendations', [])
            exit_signals = context.get('exit_signals', [])
            if pending_recs or exit_signals:
                lines.append(f"\nPENDING DECISIONS:")
                if pending_recs:
                    lines.append(f"  Entry recommendations: {len(pending_recs)}")
                if exit_signals:
                    lines.append(f"  Exit signals: {len(exit_signals)}")

            # Accountability
            acct = context.get('accountability_metrics', {})
            if acct:
                lines.append(f"\nACCOUNTABILITY:")
                lines.append(f"  Trades today: {acct.get('trades_today', 0)}")
                lines.append(f"  Recs ignored: {acct.get('recs_ignored', 0)}")
                lines.append(f"  Avg time-to-decision: {acct.get('avg_ttd_minutes', 'N/A')} min")

            # Capital efficiency
            utilization = context.get('capital_utilization', {})
            if utilization:
                lines.append(f"\nCAPITAL EFFICIENCY:")
                lines.append(
                    f"  {'Portfolio':<20} {'Target':>7} {'Actual':>7} "
                    f"{'Gap':>6} {'Idle $':>10} {'Cost/Day':>10} {'Days Idle':>10}"
                )
                lines.append(f"  {'-'*72}")
                for pname, data in utilization.items():
                    severity_flag = ""
                    if data.get('severity') == 'critical':
                        severity_flag = " << CRITICAL"
                    elif data.get('severity') == 'warning':
                        severity_flag = " << WARNING"

                    days_str = str(data.get('days_idle', '?'))
                    lines.append(
                        f"  {pname:<20} "
                        f"{data.get('target_deployed_pct', 0):>6.0f}% "
                        f"{data.get('actual_deployed_pct', 0):>6.0f}% "
                        f"{data.get('gap_pct', 0):>+5.0f}% "
                        f"${data.get('idle_capital', 0):>9,.0f} "
                        f"${data.get('opp_cost_daily', 0):>9,.2f} "
                        f"{days_str:>10}{severity_flag}"
                    )

            # Session performance
            session_perf = context.get('session_performance', [])
            if session_perf:
                lines.append(f"\nSESSION PERFORMANCE:")
                lines.append(
                    f"  {'Agent':<22} {'Objective':<36} "
                    f"{'Target':>8} {'Actual':>8} {'Grade':>6}"
                )
                lines.append(f"  {'-'*82}")
                for r in session_perf:
                    flag = " << INACTION" if r.get('grade') == 'F' else ""
                    lines.append(
                        f"  {r.get('agent_name', '?'):<22} "
                        f"{str(r.get('objective', ''))[:34]:<36} "
                        f"{str(r.get('target_value', '')):>8} "
                        f"{str(r.get('actual_value', '')):>8} "
                        f"{r.get('grade', '?'):>6}{flag}"
                    )

            # Corrective plan
            corrective = context.get('corrective_plan', [])
            if corrective:
                lines.append(f"\nCORRECTIVE PLAN:")
                for i, item in enumerate(corrective, 1):
                    lines.append(f"  {i}. {item}")

            # Calendar
            cadences = context.get('cadences', [])
            if cadences:
                lines.append(f"\nTODAY'S CADENCES: {', '.join(cadences)}")

            lines.append(f"\n{'='*60}\n")

            report = "\n".join(lines)
            context['daily_report'] = report

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'report_lines': len(lines)},
                messages=["Daily report generated"],
            )

        except Exception as e:
            logger.error(f"ReporterAgent failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Report generation error: {e}"],
            )

    def generate_weekly_digest(self, context: dict) -> AgentResult:
        """Generate weekly performance digest."""
        try:
            lines = []
            lines.append(f"\n{'='*60}")
            lines.append(f"WEEKLY TRADING DIGEST — Week of {date.today()}")
            lines.append(f"{'='*60}")

            acct = context.get('accountability_metrics', {})
            capital = context.get('capital_deployment', {})

            if capital:
                lines.append("\nCAPITAL DEPLOYMENT:")
                for name, data in capital.items():
                    lines.append(
                        f"  {name}: {data.get('deployed_pct', 0):.0f}% deployed, "
                        f"{data.get('days_since_trade', '?')} days since last trade"
                    )

            lines.append(f"\n{'='*60}\n")

            report = "\n".join(lines)
            context['weekly_report'] = report

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                messages=["Weekly digest generated"],
            )

        except Exception as e:
            logger.error(f"ReporterAgent weekly digest failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Weekly digest error: {e}"],
            )
