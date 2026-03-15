"""
Atlas Agent (Vishwakarma) — System Health, Analytics & Infrastructure.

Watches the watchers. Monitors:
  - Trading floor health (broker, prices, agents, DB)
  - AI/ML model freshness (bandits, thresholds, POP factors)
  - Data pipeline integrity (lineage, outcomes, reconciliation)
  - Cross-system analytics (regime×P&L, Greek attribution, gate efficiency)

Runs every cycle in the monitoring pipeline.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import ClassVar, Dict, List

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.core.database.schema import TradeORM, MLStateORM, PortfolioORM, SystemEventORM

logger = logging.getLogger(__name__)


class AtlasAgent(BaseAgent):
    """System health, ML monitoring, data analytics, infrastructure."""

    name: ClassVar[str] = "atlas"
    display_name: ClassVar[str] = "Vishwakarma (Infrastructure)"
    category: ClassVar[str] = "domain"
    role: ClassVar[str] = "System health, ML monitoring, analytics, infrastructure"
    intro: ClassVar[str] = (
        "I watch the watchers. I monitor broker connections, agent health, "
        "ML model freshness, data pipelines, and system performance. "
        "I sound the alarm when the machine stops improving."
    )
    responsibilities: ClassVar[List[str]] = [
        "Trading floor health checks",
        "AI/ML model freshness monitoring",
        "Data pipeline validation",
        "Cross-system analytics",
        "System performance benchmarks",
    ]
    datasources: ClassVar[List[str]] = [
        "MLStateORM", "TradeORM", "AgentRunORM", "PortfolioORM",
    ]
    boundaries: ClassVar[List[str]] = [
        "Cannot make trading decisions",
        "Cannot modify trades or positions",
        "Infrastructure, monitoring, and analytics only",
    ]
    runs_during: ClassVar[List[str]] = [
        "monitoring", "reporting", "eod_evaluation",
    ]

    def __init__(self, container=None, config=None, broker=None, ma=None):
        super().__init__(container=container, config=config)
        self._broker = broker
        self._ma = ma

    def run(self, context: dict) -> AgentResult:
        """Run all health checks and analytics. Returns findings."""
        findings: List[str] = []
        alerts: List[Dict] = []
        metrics: Dict = {}

        # V1: Agent run health
        agent_health = self._check_agent_health(context)
        findings.extend(agent_health['messages'])
        metrics['agent_health'] = agent_health

        # V2: Broker connection
        broker_health = self._check_broker_health()
        findings.extend(broker_health['messages'])
        metrics['broker_health'] = broker_health
        if not broker_health['connected']:
            alerts.append({'type': 'broker_disconnected', 'severity': 'HIGH',
                           'message': 'Broker not connected — prices will be stale'})

        # V3: Price freshness
        price_health = self._check_price_freshness()
        findings.extend(price_health['messages'])
        metrics['price_health'] = price_health
        if price_health['stale_count'] > 0:
            alerts.append({'type': 'stale_prices', 'severity': 'HIGH',
                           'message': f"{price_health['stale_count']} positions with stale prices"})

        # V4: ML model freshness
        ml_health = self._check_ml_freshness()
        findings.extend(ml_health['messages'])
        metrics['ml_health'] = ml_health
        for stale in ml_health.get('stale_models', []):
            alerts.append({'type': 'ml_stale', 'severity': 'MEDIUM',
                           'message': f"ML model '{stale}' needs retraining"})

        # V5: Data pipeline integrity
        pipeline_health = self._check_data_pipeline()
        findings.extend(pipeline_health['messages'])
        metrics['pipeline_health'] = pipeline_health

        # V6: Position reconciliation (basic)
        recon = self._check_position_consistency()
        findings.extend(recon['messages'])
        metrics['position_consistency'] = recon

        # B14: Cross-desk risk aggregation
        cross_desk = self._compute_cross_desk_risk()
        findings.extend(cross_desk['messages'])
        metrics['cross_desk_risk'] = cross_desk
        context['cross_desk_risk'] = cross_desk

        # K7: Greek P&L attribution
        attribution = self._compute_greek_attribution()
        findings.extend(attribution['messages'])
        metrics['greek_attribution'] = attribution
        context['greek_attribution'] = attribution

        # Persist alerts to SystemEventORM
        self._log_events(alerts)

        # Store alerts in context
        context['system_alerts'] = alerts

        status = AgentStatus.COMPLETED
        if any(a['severity'] == 'HIGH' for a in alerts):
            status = AgentStatus.WARNING

        return AgentResult(
            agent_name=self.name,
            status=status,
            data=metrics,
            messages=findings,
            metrics={
                'alerts': len(alerts),
                'high_alerts': sum(1 for a in alerts if a['severity'] == 'HIGH'),
                'checks_passed': sum(1 for f in findings if 'OK' in f or 'healthy' in f.lower()),
            },
        )

    # -----------------------------------------------------------------
    # Event logging — persistent system health log
    # -----------------------------------------------------------------

    def _log_events(self, alerts: List[Dict]) -> None:
        """Persist alerts to SystemEventORM."""
        import uuid
        if not alerts:
            return
        try:
            with session_scope() as session:
                for alert in alerts:
                    session.add(SystemEventORM(
                        id=str(uuid.uuid4()),
                        event_type=alert.get('type', 'unknown'),
                        severity=alert.get('severity', 'INFO'),
                        source='atlas',
                        message=alert.get('message', ''),
                        details=alert,
                    ))
                session.commit()
        except Exception as e:
            logger.debug(f"Failed to log system events: {e}")

    @staticmethod
    def log_error(source: str, message: str, details: dict = None) -> None:
        """Static method for ANY component to report errors to Atlas.

        Usage from anywhere:
            AtlasAgent.log_error('scout', 'Screening failed: timeout', {'tickers': 25})
        """
        import uuid
        try:
            with session_scope() as session:
                session.add(SystemEventORM(
                    id=str(uuid.uuid4()),
                    event_type='agent_error',
                    severity='HIGH',
                    source=source,
                    message=message,
                    details=details or {},
                ))
                session.commit()
        except Exception:
            pass  # Don't let error logging cause errors

    @staticmethod
    def log_warning(source: str, message: str, event_type: str = 'warning', details: dict = None) -> None:
        """Static method for warnings."""
        import uuid
        try:
            with session_scope() as session:
                session.add(SystemEventORM(
                    id=str(uuid.uuid4()),
                    event_type=event_type,
                    severity='WARNING',
                    source=source,
                    message=message,
                    details=details or {},
                ))
                session.commit()
        except Exception:
            pass

    # -----------------------------------------------------------------
    # V1: Agent run health
    # -----------------------------------------------------------------
    def _check_agent_health(self, context: dict) -> dict:
        """Check if all agents completed their last run successfully."""
        result = {'healthy': True, 'messages': []}
        cycle = context.get('cycle_count', 0)

        if cycle == 0:
            result['messages'].append("Agent health: first cycle, no history yet")
            return result

        # Check agent run history from DB
        try:
            from trading_cotrader.core.database.schema import AgentRunORM
            with session_scope() as session:
                recent = session.query(AgentRunORM).filter(
                    AgentRunORM.started_at >= datetime.utcnow() - timedelta(hours=2),
                ).all()

                if not recent:
                    result['messages'].append("Agent health: no recent runs found")
                    return result

                errors = [r for r in recent if r.status == 'error']
                if errors:
                    result['healthy'] = False
                    for e in errors[-3:]:
                        result['messages'].append(
                            f"Agent FAIL: {e.agent_name} — {e.error_message or 'unknown error'}"
                        )
                else:
                    agents = set(r.agent_name for r in recent)
                    result['messages'].append(f"Agent health: {len(agents)} agents ran, all OK")
        except Exception as e:
            result['messages'].append(f"Agent health: check skipped ({e})")

        return result

    # -----------------------------------------------------------------
    # V2: Broker connection
    # -----------------------------------------------------------------
    def _check_broker_health(self) -> dict:
        """Check if broker is connected and responsive."""
        result = {'connected': False, 'messages': []}

        if not self._broker:
            result['messages'].append("Broker: NOT CONNECTED — running offline")
            return result

        try:
            if hasattr(self._broker, 'session') and self._broker.session:
                result['connected'] = True
                result['messages'].append("Broker: connected")
            else:
                result['messages'].append("Broker: adapter exists but no session")
        except Exception as e:
            result['messages'].append(f"Broker: health check failed ({e})")

        return result

    # -----------------------------------------------------------------
    # V3: Price freshness
    # -----------------------------------------------------------------
    def _check_price_freshness(self) -> dict:
        """Check if open positions have recent prices."""
        result = {'stale_count': 0, 'total': 0, 'messages': []}

        with session_scope() as session:
            trades = session.query(TradeORM).filter(TradeORM.is_open == True).all()
            result['total'] = len(trades)

            stale_threshold = datetime.utcnow() - timedelta(minutes=60)
            for t in trades:
                if not t.current_price or t.current_price == 0:
                    result['stale_count'] += 1
                elif t.last_updated and t.last_updated < stale_threshold:
                    result['stale_count'] += 1

            if result['stale_count'] > 0:
                result['messages'].append(
                    f"Price freshness: {result['stale_count']}/{result['total']} positions stale (> 60 min)"
                )
            elif result['total'] > 0:
                result['messages'].append(f"Price freshness: all {result['total']} positions current")
            else:
                result['messages'].append("Price freshness: no open positions")

        return result

    # -----------------------------------------------------------------
    # V4: ML model freshness
    # -----------------------------------------------------------------
    def _check_ml_freshness(self) -> dict:
        """Check if ML models have been updated recently."""
        result = {'stale_models': [], 'messages': []}

        thresholds = {
            'bandits': 7,       # days
            'thresholds': 30,
            'drift_alerts': 3,
            'pop_factors': 14,
        }

        with session_scope() as session:
            for state_type, max_age_days in thresholds.items():
                row = session.query(MLStateORM).filter(
                    MLStateORM.state_type == state_type
                ).first()

                if not row:
                    result['stale_models'].append(state_type)
                    result['messages'].append(f"ML {state_type}: NEVER TRAINED")
                elif row.last_updated:
                    age = (datetime.utcnow() - row.last_updated).days
                    if age > max_age_days:
                        result['stale_models'].append(state_type)
                        result['messages'].append(
                            f"ML {state_type}: {age} days old (max {max_age_days}). "
                            f"Analyzed {row.trades_analyzed} trades."
                        )

        if not result['stale_models']:
            result['messages'].append("ML models: all current")

        return result

    # -----------------------------------------------------------------
    # V5: Data pipeline integrity
    # -----------------------------------------------------------------
    def _check_data_pipeline(self) -> dict:
        """Check if data pipelines are complete."""
        result = {'issues': 0, 'messages': []}

        with session_scope() as session:
            # Check closed trades have lineage
            closed_no_lineage = session.query(TradeORM).filter(
                TradeORM.is_open == False,
                TradeORM.decision_lineage == None,
            ).count()

            if closed_no_lineage > 0:
                result['issues'] += 1
                result['messages'].append(
                    f"Pipeline: {closed_no_lineage} closed trades missing decision lineage"
                )

            # Check open trades have health status
            open_no_health = session.query(TradeORM).filter(
                TradeORM.is_open == True,
                TradeORM.health_status.in_([None, 'unknown']),
            ).count()

            if open_no_health > 0:
                result['issues'] += 1
                result['messages'].append(
                    f"Pipeline: {open_no_health} open trades missing health status"
                )

            if result['issues'] == 0:
                result['messages'].append("Pipeline: all data complete")

        return result

    # -----------------------------------------------------------------
    # V6: Position consistency
    # -----------------------------------------------------------------
    def _check_position_consistency(self) -> dict:
        """Basic position consistency checks."""
        result = {'issues': 0, 'messages': []}

        with session_scope() as session:
            # Trades with no legs
            no_legs = session.query(TradeORM).filter(
                TradeORM.is_open == True,
            ).all()

            orphans = [t for t in no_legs if not t.legs]
            if orphans:
                result['issues'] += len(orphans)
                result['messages'].append(
                    f"Consistency: {len(orphans)} open trades with no legs"
                )

            # Negative buying power on any desk
            desks = session.query(PortfolioORM).filter(
                PortfolioORM.portfolio_type == 'what_if'
            ).all()
            for d in desks:
                bp = float(d.buying_power or 0)
                if bp < 0:
                    result['issues'] += 1
                    result['messages'].append(
                        f"Consistency: {d.name} has negative buying power (${bp:,.0f})"
                    )

            if result['issues'] == 0:
                result['messages'].append("Consistency: all checks passed")

        return result

    # -----------------------------------------------------------------
    # B14: Cross-desk risk aggregation
    # -----------------------------------------------------------------
    def _compute_cross_desk_risk(self) -> dict:
        """Compute aggregate risk across ALL desks."""
        result = {
            'total_delta': 0, 'total_gamma': 0, 'total_theta': 0, 'total_vega': 0,
            'total_positions': 0, 'total_risk': 0, 'desks': {},
            'messages': [],
        }

        with session_scope() as session:
            desks = session.query(PortfolioORM).filter(
                PortfolioORM.portfolio_type == 'what_if'
            ).all()

            for desk in desks:
                trades = session.query(TradeORM).filter(
                    TradeORM.portfolio_id == desk.id,
                    TradeORM.is_open == True,
                ).all()

                desk_delta = sum(float(t.current_delta or 0) for t in trades)
                desk_theta = sum(float(t.current_theta or 0) for t in trades)
                desk_gamma = sum(float(t.current_gamma or 0) for t in trades)
                desk_vega = sum(float(t.current_vega or 0) for t in trades)
                desk_risk = sum(float(t.max_risk or 0) for t in trades)

                result['desks'][desk.name] = {
                    'delta': round(desk_delta, 2),
                    'theta': round(desk_theta, 2),
                    'gamma': round(desk_gamma, 4),
                    'vega': round(desk_vega, 2),
                    'positions': len(trades),
                    'risk': round(desk_risk, 0),
                }

                result['total_delta'] += desk_delta
                result['total_gamma'] += desk_gamma
                result['total_theta'] += desk_theta
                result['total_vega'] += desk_vega
                result['total_positions'] += len(trades)
                result['total_risk'] += desk_risk

        result['total_delta'] = round(result['total_delta'], 2)
        result['total_theta'] = round(result['total_theta'], 2)
        result['total_risk'] = round(result['total_risk'], 0)

        if result['total_positions'] > 0:
            result['messages'].append(
                f"Cross-desk: {result['total_positions']} positions, "
                f"net \u0394={result['total_delta']:+.1f}, "
                f"\u0398=${result['total_theta']:.0f}/day, "
                f"risk=${result['total_risk']:,.0f}"
            )
        else:
            result['messages'].append("Cross-desk: no open positions")

        return result

    # -----------------------------------------------------------------
    # K7: Greek P&L attribution
    # -----------------------------------------------------------------
    def _compute_greek_attribution(self) -> dict:
        """Compute P&L attribution by Greek across all desks."""
        result = {
            'delta_pnl': 0, 'theta_pnl': 0, 'gamma_pnl': 0, 'vega_pnl': 0,
            'unexplained_pnl': 0, 'total_pnl': 0,
            'by_desk': {},
            'messages': [],
        }

        with session_scope() as session:
            desks = session.query(PortfolioORM).filter(
                PortfolioORM.portfolio_type == 'what_if'
            ).all()

            for desk in desks:
                trades = session.query(TradeORM).filter(
                    TradeORM.portfolio_id == desk.id,
                ).all()

                desk_attr = {
                    'delta_pnl': sum(float(t.delta_pnl or 0) for t in trades),
                    'theta_pnl': sum(float(t.theta_pnl or 0) for t in trades),
                    'gamma_pnl': sum(float(t.gamma_pnl or 0) for t in trades),
                    'vega_pnl': sum(float(t.vega_pnl or 0) for t in trades),
                    'unexplained_pnl': sum(float(t.unexplained_pnl or 0) for t in trades),
                    'total_pnl': sum(float(t.total_pnl or 0) for t in trades),
                }
                result['by_desk'][desk.name] = desk_attr

                for key in ['delta_pnl', 'theta_pnl', 'gamma_pnl', 'vega_pnl', 'unexplained_pnl', 'total_pnl']:
                    result[key] += desk_attr[key]

        for key in result:
            if isinstance(result[key], float):
                result[key] = round(result[key], 2)

        if result['total_pnl'] != 0:
            theta_pct = abs(result['theta_pnl'] / result['total_pnl'] * 100) if result['total_pnl'] else 0
            delta_pct = abs(result['delta_pnl'] / result['total_pnl'] * 100) if result['total_pnl'] else 0
            result['messages'].append(
                f"P&L attribution: total=${result['total_pnl']:+,.0f} "
                f"(\u0398={theta_pct:.0f}%, \u0394={delta_pct:.0f}%)"
            )
        else:
            result['messages'].append("P&L attribution: no P&L data yet")

        return result
