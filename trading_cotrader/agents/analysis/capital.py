"""
Capital Utilization Agent — Proactively monitors idle capital across portfolios.

Per portfolio each monitoring cycle:
    target_deployed_pct = 100 - min_cash_reserve_pct
    actual_deployed_pct = (equity - cash) / equity * 100
    idle_capital = cash - (equity * min_cash_reserve_pct / 100)
    gap_pct = target_deployed_pct - actual_deployed_pct
    opportunity_cost_per_day = idle_capital * target_annual_return / 365

Severity escalation (from workflow_rules.yaml):
    info:     gap > idle_alert_pct threshold
    warning:  gap > 2x threshold OR days_idle > warning_days_idle
    critical: gap > 3x threshold OR days_idle > critical_days_idle

Correlates with pending recommendations to suggest concrete actions.
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus
from trading_cotrader.config.workflow_config_loader import WorkflowConfig

logger = logging.getLogger(__name__)


class CapitalUtilizationAgent:
    """Monitors capital deployment and generates idle-capital alerts."""

    name = "capital_utilization"

    def __init__(self, config: WorkflowConfig):
        self.config = config

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Analyze capital utilization per portfolio.

        Reads from context:
            - portfolios (from PortfolioStateAgent)
            - capital_deployment (from AccountabilityAgent)
            - pending_recommendations (from ScreenerAgent)

        Writes to context:
            - capital_utilization: per-portfolio deployment analysis
            - capital_alerts: list of severity-graded alerts
        """
        try:
            utilization = self._analyze_utilization(context)
            alerts = self._generate_alerts(utilization, context)

            context['capital_utilization'] = utilization
            context['capital_alerts'] = alerts

            alert_count = len(alerts)
            critical_count = sum(1 for a in alerts if a['severity'] == 'critical')
            warning_count = sum(1 for a in alerts if a['severity'] == 'warning')

            messages = []
            if alert_count == 0:
                messages.append("Capital utilization: all portfolios within targets")
            else:
                messages.append(
                    f"Capital alerts: {critical_count} critical, "
                    f"{warning_count} warning, "
                    f"{alert_count - critical_count - warning_count} info"
                )

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={
                    'alert_count': alert_count,
                    'critical_count': critical_count,
                    'portfolios_analyzed': len(utilization),
                },
                messages=messages,
                objectives=["Keep capital deployed per allocation targets"],
                metrics={'alert_count': alert_count, 'critical_count': critical_count},
            )

        except Exception as e:
            logger.error(f"CapitalUtilizationAgent failed: {e}")
            context['capital_utilization'] = {}
            context['capital_alerts'] = []
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Capital utilization error: {e}"],
            )

    def _analyze_utilization(self, context: dict) -> Dict[str, dict]:
        """Calculate deployment metrics per portfolio."""
        portfolio_configs = self._load_portfolio_configs()
        portfolios = context.get('portfolios', [])
        capital_deployment = context.get('capital_deployment', {})

        # Escalation config from workflow rules
        escalation = self.config.capital_deployment.escalation
        target_returns = self.config.capital_deployment.target_annual_return_pct

        # Staggered deployment config
        staggered = self.config.capital_deployment.staggered
        ramp_weeks = staggered.ramp_weeks
        max_deploy_per_week = staggered.max_deploy_per_week_pct

        utilization: Dict[str, dict] = {}

        for p in portfolios:
            pname = p.get('account_id') or p.get('name', '')
            equity = p.get('equity', 0)
            cash = p.get('cash', 0)

            if equity <= 0:
                continue

            # Get min_cash_reserve_pct from risk_config.yaml
            pcfg = portfolio_configs.get(pname, {})
            risk_limits = pcfg.get('risk_limits', {})
            min_cash_pct = risk_limits.get('min_cash_reserve_pct', 10.0)

            # Target vs actual — apply staggered ramp if early
            full_target_pct = 100.0 - min_cash_pct
            target_deployed_pct = self._apply_staggered_ramp(
                pname, full_target_pct, ramp_weeks, max_deploy_per_week, context,
            )
            actual_deployed_pct = ((equity - cash) / equity) * 100.0
            gap_pct = target_deployed_pct - actual_deployed_pct

            # Idle capital — relative to the ramped target, not the full target.
            # If ramped target says deploy 30% and we're at 0%, idle = 30% of equity.
            ramped_cash_target_pct = 100.0 - target_deployed_pct
            ramped_reserve = equity * ramped_cash_target_pct / 100.0
            idle_capital = max(0.0, cash - ramped_reserve)

            # Opportunity cost
            annual_return = target_returns.get(pname, 0.0) / 100.0
            opp_cost_daily = idle_capital * annual_return / 365.0

            # Days since last trade
            deploy_data = capital_deployment.get(pname, {})
            days_idle = deploy_data.get('days_since_trade')

            # Severity
            idle_alert_threshold = self.config.capital_deployment.idle_alert_pct.get(pname, 10.0)
            severity = self._calc_severity(
                gap_pct, idle_alert_threshold, days_idle, escalation,
            )

            utilization[pname] = {
                'equity': round(equity, 2),
                'cash': round(cash, 2),
                'full_target_deployed_pct': round(full_target_pct, 1),
                'target_deployed_pct': round(target_deployed_pct, 1),
                'actual_deployed_pct': round(actual_deployed_pct, 1),
                'gap_pct': round(gap_pct, 1),
                'idle_capital': round(idle_capital, 2),
                'opp_cost_daily': round(opp_cost_daily, 2),
                'days_idle': days_idle,
                'severity': severity,
                'min_cash_reserve_pct': min_cash_pct,
                'target_annual_return_pct': target_returns.get(pname, 0.0),
            }

        return utilization

    def _load_portfolio_configs(self) -> Dict[str, dict]:
        """Load portfolio section from risk_config.yaml as raw dict."""
        from pathlib import Path
        import yaml

        paths = [
            Path('config/risk_config.yaml'),
            Path(__file__).parent.parent.parent / 'config' / 'risk_config.yaml',
        ]
        for p in paths:
            if p.exists():
                with open(p, 'r') as f:
                    raw = yaml.safe_load(f)
                return raw.get('portfolios', {})
        return {}

    def _apply_staggered_ramp(
        self,
        portfolio_name: str,
        full_target_pct: float,
        ramp_weeks: int,
        max_deploy_per_week: Dict[str, float],
        context: dict,
    ) -> float:
        """
        Apply staggered deployment ramp-up.

        Instead of expecting full deployment from day 1, the target ramps up
        linearly over `ramp_weeks`. This prevents the agent from nagging to
        deploy $200K on the first morning.

        Uses engine_start_time or first trade date as ramp start.
        """
        # Determine how many weeks since ramp started
        start_str = context.get('engine_start_time', '')
        if start_str:
            try:
                start_dt = datetime.fromisoformat(start_str)
            except (ValueError, TypeError):
                start_dt = datetime.utcnow()
        else:
            start_dt = datetime.utcnow()

        weeks_elapsed = max(1, (datetime.utcnow() - start_dt).days / 7)

        if weeks_elapsed >= ramp_weeks:
            return full_target_pct

        # Weekly cap for this portfolio
        weekly_cap = max_deploy_per_week.get(portfolio_name, 15.0)

        # Ramped target: min(weeks * weekly_cap, full_target)
        ramped_target = min(weeks_elapsed * weekly_cap, full_target_pct)

        return ramped_target

    def _calc_severity(
        self,
        gap_pct: float,
        threshold: float,
        days_idle: Optional[int],
        escalation: dict,
    ) -> str:
        """Determine alert severity based on gap and idle days."""
        warning_days = escalation.get('warning_days_idle', 5)
        critical_days = escalation.get('critical_days_idle', 10)

        if gap_pct <= 0:
            return 'ok'

        # Critical: gap > 3x threshold OR days_idle > critical_days
        if gap_pct > threshold * 3 or (days_idle is not None and days_idle >= critical_days):
            return 'critical'

        # Warning: gap > 2x threshold OR days_idle > warning_days
        if gap_pct > threshold * 2 or (days_idle is not None and days_idle >= warning_days):
            return 'warning'

        # Info: gap > threshold
        if gap_pct > threshold:
            return 'info'

        return 'ok'

    def _generate_alerts(self, utilization: Dict[str, dict], context: dict) -> List[dict]:
        """Generate actionable alerts for portfolios with idle capital."""
        alerts = []
        pending_recs = context.get('pending_recommendations', [])

        for pname, data in utilization.items():
            severity = data['severity']
            if severity == 'ok':
                continue

            # Find pending recs for this portfolio
            matching_recs = [
                r for r in pending_recs
                if r.get('portfolio', '') == pname or r.get('target_portfolio', '') == pname
            ]

            # Build suggested action
            action = self._suggest_action(pname, data, matching_recs)

            alerts.append({
                'portfolio': pname,
                'severity': severity,
                'gap_pct': data['gap_pct'],
                'idle_capital': data['idle_capital'],
                'opp_cost_daily': data['opp_cost_daily'],
                'days_idle': data['days_idle'],
                'actual_deployed_pct': data['actual_deployed_pct'],
                'target_deployed_pct': data['target_deployed_pct'],
                'matching_recs': len(matching_recs),
                'suggested_action': action,
            })

        # Sort: critical first, then warning, then info
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        alerts.sort(key=lambda a: severity_order.get(a['severity'], 3))

        return alerts

    def _suggest_action(
        self,
        portfolio_name: str,
        data: dict,
        matching_recs: List[dict],
    ) -> str:
        """Generate a concrete suggested action for idle capital."""
        idle = data['idle_capital']
        days = data['days_idle']

        if matching_recs:
            rec_count = len(matching_recs)
            return (
                f"You have ${idle:,.0f} idle AND {rec_count} pending "
                f"recommendation(s) for {portfolio_name} - approve them?"
            )

        if days is not None and days > 10:
            return (
                f"${idle:,.0f} idle for {days} days. "
                f"Run screeners for {portfolio_name} preferred underlyings."
            )

        if days is not None and days > 5:
            return (
                f"${idle:,.0f} idle for {days} days. "
                f"Review screener output or adjust active strategies."
            )

        return f"${idle:,.0f} above reserve. Consider deploying via active strategies."
