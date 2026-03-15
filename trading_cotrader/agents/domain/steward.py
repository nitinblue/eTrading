"""
Steward Agent (Portfolio Manager) — Portfolio state, positions, P&L, capital utilization.

Absorbs:
  - PortfolioStateAgent (populate) — reads portfolio state from DB via ContainerManager
  - CapitalUtilizationAgent (run) — monitors idle capital, generates alerts

Pattern (follows Scout exemplar):
  1. Owns containers via ContainerManager (PortfolioBundle per portfolio)
  2. populate() fills containers from DB (like Scout fills ResearchContainer from MarketAnalyzer)
  3. run() analyzes capital utilization from container data
  4. API reads from containers, never DB directly

Usage:
    steward = StewardAgent(container_manager=cm, config=config)
    steward.populate(context)  # fills PortfolioBundle containers from DB
    steward.run(context)       # capital utilization analysis + alerts
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, TYPE_CHECKING
import logging

import yaml

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus

if TYPE_CHECKING:
    from trading_cotrader.containers.container_manager import ContainerManager
    from trading_cotrader.config.workflow_config_loader import WorkflowConfig

logger = logging.getLogger(__name__)


class StewardAgent(BaseAgent):
    """Portfolio manager: state, positions, P&L, capital utilization."""

    # Class-level metadata
    name: ClassVar[str] = "steward"
    display_name: ClassVar[str] = "Steward (Portfolio)"
    category: ClassVar[str] = "domain"
    role: ClassVar[str] = "Portfolio state, positions, P&L, capital utilization"
    intro: ClassVar[str] = (
        "I manage portfolio state. Positions, P&L tracking, capital utilization, "
        "position monitoring -- the single source of truth for what we own "
        "and how it is performing."
    )
    responsibilities: ClassVar[List[str]] = [
        "Portfolio state",
        "Position monitoring",
        "P&L tracking",
        "Capital utilization",
        "Broker sync coordination",
    ]
    datasources: ClassVar[List[str]] = [
        "PortfolioORM",
        "PositionORM",
        "TradeORM",
        "Broker adapters",
        "PortfolioBundle",
    ]
    boundaries: ClassVar[List[str]] = [
        "Read-only portfolio state",
        "Does not place trades",
        "Does not evaluate risk",
    ]
    runs_during: ClassVar[List[str]] = ["booting", "monitoring"]

    def __init__(self, container_manager: 'ContainerManager' = None, config: 'WorkflowConfig' = None):
        super().__init__(container=None, config=config)
        self._container_manager = container_manager

    # -----------------------------------------------------------------
    # populate() — Fill PortfolioBundle containers from DB
    # -----------------------------------------------------------------

    def populate(self, context: dict) -> AgentResult:
        """
        Fill PortfolioBundle containers from DB.

        Replaces PortfolioStateAgent.run():
          1. Load all bundles from DB (positions, trades, risk factors)
          2. Build portfolio summaries from bundles
          3. Query trade counts from DB (containers don't track historical counts)
          4. Set context keys for downstream agents (Sentinel, etc.)

        Returns AgentResult with portfolio stats.
        """
        if self._container_manager is None:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=["No container_manager -- cannot populate"],
            )

        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import PortfolioORM, TradeORM

            # 1. Load all bundles from DB (positions, trades, risk factors)
            with session_scope() as session:
                self._container_manager.load_all_bundles(session)

            # 2. Build portfolio summaries from container data
            bundles = self._container_manager.get_all_bundles()
            portfolio_summaries = []
            total_equity = Decimal('0')
            total_daily_pnl = Decimal('0')

            for bundle in bundles:
                # PortfolioContainer.state is a PortfolioState dataclass (or None)
                pstate = bundle.portfolio.state
                if pstate is None:
                    continue

                equity = pstate.total_equity or Decimal('0')
                daily = pstate.daily_pnl or Decimal('0')
                total_equity += equity
                total_daily_pnl += daily

                portfolio_summaries.append({
                    'id': pstate.portfolio_id,
                    'name': pstate.name or bundle.config_name,
                    'account_id': bundle.account_number,
                    'broker': bundle.broker_firm,
                    'portfolio_type': pstate.portfolio_type or '',
                    'equity': float(equity),
                    'daily_pnl': float(daily),
                    'cash': float(pstate.cash_balance or 0),
                    'delta': float(pstate.delta or 0),
                    'theta': float(pstate.theta or 0),
                })

            # Build open trades list from containers (TradeState objects)
            open_trade_list = []
            for bundle in bundles:
                for trade in bundle.trades.get_all():
                    open_trade_list.append({
                        'id': trade.trade_id,
                        'underlying': trade.underlying,
                        'portfolio_id': getattr(trade, 'portfolio_id', ''),
                        'status': trade.trade_status,
                        'pnl': float(getattr(trade, 'total_pnl', 0) or 0),
                        'delta': float(trade.delta or 0),
                        'theta': float(trade.theta or 0),
                    })

            # 3. Trade counts still need DB queries (containers don't track historical counts)
            with session_scope() as session:
                today_start = datetime.combine(date.today(), datetime.min.time())
                trades_today = session.query(TradeORM).filter(
                    TradeORM.created_at >= today_start,
                    TradeORM.trade_status.in_(['executed', 'partial', 'closed']),
                ).count()

                week_start = today_start - timedelta(days=date.today().weekday())
                weekly_trades_query = session.query(
                    TradeORM.portfolio_id, TradeORM.id
                ).filter(
                    TradeORM.created_at >= week_start,
                    TradeORM.trade_status.in_(['executed', 'partial', 'closed']),
                ).all()

                # Map portfolio_id -> name
                portfolios_orm = session.query(PortfolioORM).all()
                portfolio_id_to_name = {
                    p.id: (p.account_id or p.name) for p in portfolios_orm
                }
                weekly_per_portfolio: Dict[str, int] = {}
                for portfolio_id, _ in weekly_trades_query:
                    pname = portfolio_id_to_name.get(portfolio_id, portfolio_id)
                    weekly_per_portfolio[pname] = weekly_per_portfolio.get(pname, 0) + 1

            # 4. Calculate daily P&L percentage
            daily_pnl_pct = 0.0
            if total_equity > 0:
                daily_pnl_pct = float(total_daily_pnl / total_equity * 100)

            # 5. Enrich context
            context['portfolios'] = portfolio_summaries
            context['open_trades'] = open_trade_list
            context['total_equity'] = float(total_equity)
            context['daily_pnl_pct'] = daily_pnl_pct
            context['weekly_pnl_pct'] = context.get('weekly_pnl_pct', 0.0)
            context['trades_today_count'] = trades_today
            context['weekly_trades_per_portfolio'] = weekly_per_portfolio
            context['portfolio_drawdowns'] = context.get('portfolio_drawdowns', {})
            context['consecutive_losses'] = context.get('consecutive_losses', {})

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={
                    'portfolio_count': len(portfolio_summaries),
                    'open_trade_count': len(open_trade_list),
                    'total_equity': float(total_equity),
                    'trades_today': trades_today,
                },
                messages=[
                    f"Portfolios: {len(portfolio_summaries)}, "
                    f"Open trades: {len(open_trade_list)}, "
                    f"Daily P&L: {daily_pnl_pct:+.2f}%"
                ],
            )

        except Exception as e:
            logger.error(f"StewardAgent.populate failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Portfolio state error: {e}"],
            )

    # -----------------------------------------------------------------
    # run() — Capital utilization analysis (absorbs CapitalUtilizationAgent)
    # -----------------------------------------------------------------

    def run(self, context: dict) -> AgentResult:
        """
        Analyze capital utilization per portfolio.

        Reads from context:
            - portfolios (from populate)
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
            logger.error(f"StewardAgent.run failed: {e}")
            context['capital_utilization'] = {}
            context['capital_alerts'] = []
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Capital utilization error: {e}"],
            )

    # -----------------------------------------------------------------
    # Capital utilization internals (from CapitalUtilizationAgent)
    # -----------------------------------------------------------------

    def _analyze_utilization(self, context: dict) -> Dict[str, dict]:
        """Calculate deployment metrics per portfolio."""
        portfolio_configs = self._load_portfolio_configs()
        portfolios = context.get('portfolios', [])
        capital_deployment = context.get('capital_deployment', {})

        if self.config is None:
            return {}

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

            # Target vs actual -- apply staggered ramp if early
            full_target_pct = 100.0 - min_cash_pct
            target_deployed_pct = self._apply_staggered_ramp(
                pname, full_target_pct, ramp_weeks, max_deploy_per_week, context,
            )
            actual_deployed_pct = ((equity - cash) / equity) * 100.0
            gap_pct = target_deployed_pct - actual_deployed_pct

            # Idle capital
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

        Target ramps up linearly over `ramp_weeks` to prevent
        deploying all capital on day one.
        """
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

        weekly_cap = max_deploy_per_week.get(portfolio_name, 15.0)
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

        if gap_pct > threshold * 3 or (days_idle is not None and days_idle >= critical_days):
            return 'critical'

        if gap_pct > threshold * 2 or (days_idle is not None and days_idle >= warning_days):
            return 'warning'

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

            matching_recs = [
                r for r in pending_recs
                if r.get('portfolio', '') == pname or r.get('target_portfolio', '') == pname
            ]

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

    # -----------------------------------------------------------------
    # K9: Daily P&L Report
    # -----------------------------------------------------------------

    def generate_daily_report(self) -> dict:
        """Generate daily P&L report across all desks (K9)."""
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import TradeORM, PortfolioORM

        report = {
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'desks': {},
            'totals': {
                'total_pnl': 0, 'realized_pnl': 0, 'unrealized_pnl': 0,
                'daily_theta': 0, 'open_positions': 0, 'trades_today': 0,
                'total_capital': 0, 'total_deployed': 0,
            },
            'positions_at_risk': [],
            'exits_today': [],
            'messages': [],
        }

        today = datetime.utcnow().date()

        with session_scope() as session:
            desks = session.query(PortfolioORM).filter(
                PortfolioORM.portfolio_type == 'what_if'
            ).all()

            for desk in desks:
                trades = session.query(TradeORM).filter(
                    TradeORM.portfolio_id == desk.id,
                ).all()

                open_trades = [t for t in trades if t.is_open]
                closed_today = [t for t in trades if not t.is_open
                                and t.closed_at and t.closed_at.date() == today]

                desk_pnl = sum(float(t.total_pnl or 0) for t in trades)
                realized = sum(float(t.total_pnl or 0) for t in trades if not t.is_open)
                unrealized = sum(float(t.total_pnl or 0) for t in open_trades)
                daily_theta = sum(float(t.current_theta or 0) for t in open_trades)
                deployed = sum(float(t.max_risk or 0) for t in open_trades)
                capital = float(desk.initial_capital or 0)

                desk_data = {
                    'capital': capital,
                    'deployed': round(deployed, 0),
                    'deployed_pct': round(deployed / capital * 100, 1) if capital else 0,
                    'total_pnl': round(desk_pnl, 2),
                    'realized_pnl': round(realized, 2),
                    'unrealized_pnl': round(unrealized, 2),
                    'daily_theta': round(daily_theta, 2),
                    'open_positions': len(open_trades),
                    'closed_today': len(closed_today),
                }
                report['desks'][desk.name] = desk_data

                # Totals
                report['totals']['total_pnl'] += desk_pnl
                report['totals']['realized_pnl'] += realized
                report['totals']['unrealized_pnl'] += unrealized
                report['totals']['daily_theta'] += daily_theta
                report['totals']['open_positions'] += len(open_trades)
                report['totals']['trades_today'] += len(closed_today)
                report['totals']['total_capital'] += capital
                report['totals']['total_deployed'] += deployed

                # Positions at risk
                for t in open_trades:
                    health = t.health_status or 'unknown'
                    if health in ('tested', 'breached', 'exit_triggered'):
                        report['positions_at_risk'].append({
                            'ticker': t.underlying_symbol,
                            'desk': desk.name,
                            'health': health,
                            'pnl': round(float(t.total_pnl or 0), 2),
                        })

                # Exits today
                for t in closed_today:
                    report['exits_today'].append({
                        'ticker': t.underlying_symbol,
                        'desk': desk.name,
                        'pnl': round(float(t.total_pnl or 0), 2),
                        'reason': t.exit_reason or '?',
                    })

        # Round totals
        for key in report['totals']:
            if isinstance(report['totals'][key], float):
                report['totals'][key] = round(report['totals'][key], 2)

        # Generate messages
        t = report['totals']
        report['messages'].append(
            f"Total P&L: ${t['total_pnl']:+,.2f} "
            f"(realized ${t['realized_pnl']:+,.2f}, unrealized ${t['unrealized_pnl']:+,.2f})"
        )
        report['messages'].append(
            f"Theta earning: ${t['daily_theta']:.2f}/day across {t['open_positions']} positions"
        )
        if t['total_capital'] > 0:
            deploy_pct = t['total_deployed'] / t['total_capital'] * 100
            report['messages'].append(f"Capital: ${t['total_capital']:,.0f} deployed {deploy_pct:.0f}%")
        if report['positions_at_risk']:
            report['messages'].append(
                f"AT RISK: {len(report['positions_at_risk'])} positions "
                f"({', '.join(p['ticker'] for p in report['positions_at_risk'])})"
            )
        if report['exits_today']:
            exits_pnl = sum(e['pnl'] for e in report['exits_today'])
            report['messages'].append(
                f"Exits today: {len(report['exits_today'])} trades, P&L ${exits_pnl:+,.2f}"
            )

        return report

    # -----------------------------------------------------------------
    # K6: Desk Performance Comparison
    # -----------------------------------------------------------------

    def compare_desk_performance(self, days: int = 90) -> dict:
        """Compare performance across all desks using MA analytics (K6).

        Returns Sharpe, drawdown, regime performance per desk.
        """
        from trading_cotrader.services.ml_learning_service import MLLearningService

        result = {'desks': {}, 'recommendation': '', 'messages': []}
        ml = MLLearningService()

        with session_scope() as session:
            desks = session.query(PortfolioORM).filter(
                PortfolioORM.portfolio_type == 'what_if'
            ).all()

            all_outcomes = ml._build_outcomes(days=days)
            if not all_outcomes:
                result['messages'].append("No closed trades to analyze")
                return result

            for desk in desks:
                # Filter outcomes to this desk's trades
                desk_trades = session.query(TradeORM).filter(
                    TradeORM.portfolio_id == desk.id,
                    TradeORM.is_open == False,
                ).all()
                desk_trade_ids = {t.id for t in desk_trades}
                desk_outcomes = [o for o in all_outcomes if o.trade_id in desk_trade_ids]

                if not desk_outcomes:
                    result['desks'][desk.name] = {
                        'trades': 0, 'message': 'No closed trades yet'
                    }
                    continue

                desk_data = {
                    'trades': len(desk_outcomes),
                    'capital': float(desk.initial_capital or 0),
                }

                # Sharpe
                try:
                    from market_analyzer import compute_sharpe
                    sharpe = compute_sharpe(desk_outcomes)
                    desk_data['sharpe'] = round(sharpe.sharpe_ratio, 2)
                    desk_data['sortino'] = round(sharpe.sortino_ratio, 2)
                    desk_data['annualized_return'] = round(sharpe.annualized_return_pct, 1)
                except Exception as e:
                    desk_data['sharpe_error'] = str(e)

                # Drawdown
                try:
                    from market_analyzer import compute_drawdown
                    dd = compute_drawdown(desk_outcomes)
                    desk_data['max_drawdown_pct'] = round(dd.max_drawdown_pct, 1)
                    desk_data['max_drawdown_dollars'] = round(dd.max_drawdown_dollars, 0)
                except Exception as e:
                    desk_data['drawdown_error'] = str(e)

                # Regime performance
                try:
                    from market_analyzer import compute_regime_performance
                    regime_perf = compute_regime_performance(desk_outcomes)
                    desk_data['regime_performance'] = {}
                    for regime_id, perf in regime_perf.items():
                        desk_data['regime_performance'][f'R{regime_id}'] = {
                            'win_rate': round(perf.win_rate * 100, 0),
                            'avg_pnl': round(perf.avg_pnl_pct * 100, 1),
                            'trades': perf.trade_count,
                        }
                except Exception as e:
                    desk_data['regime_error'] = str(e)

                # Win rate + P&L
                wins = sum(1 for o in desk_outcomes if o.pnl_dollars > 0)
                total_pnl = sum(o.pnl_dollars for o in desk_outcomes)
                desk_data['win_rate'] = round(wins / len(desk_outcomes) * 100, 0)
                desk_data['total_pnl'] = round(total_pnl, 2)
                desk_data['avg_pnl'] = round(total_pnl / len(desk_outcomes), 2)
                desk_data['avg_holding_days'] = round(
                    sum(o.holding_days for o in desk_outcomes) / len(desk_outcomes), 1
                )

                result['desks'][desk.name] = desk_data

            # Recommendation: which desk deserves more capital?
            best_sharpe = -999
            best_desk = None
            for name, data in result['desks'].items():
                sharpe = data.get('sharpe', -999)
                if sharpe > best_sharpe and data.get('trades', 0) >= 5:
                    best_sharpe = sharpe
                    best_desk = name

            if best_desk:
                result['recommendation'] = (
                    f"{best_desk} has the best risk-adjusted return (Sharpe {best_sharpe:.2f}). "
                    f"Consider increasing its capital allocation."
                )
                result['messages'].append(result['recommendation'])
            else:
                result['messages'].append("Not enough trades for capital reallocation recommendation (need 5+ per desk)")

        return result
