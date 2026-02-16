"""
Accountability Agent — Tracks decision quality, capital deployment, and compliance.

Queries DecisionLogORM for metrics:
    - Average time-to-decision
    - Recommendations ignored/deferred
    - Capital idle percentage per portfolio
    - Days since last trade per portfolio
    - Template compliance (future)
"""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Dict
import logging
import uuid

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class AccountabilityAgent:
    """Tracks and reports on decision quality and capital deployment."""

    name = "accountability"

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Calculate accountability metrics for today.

        Writes 'accountability_metrics' and 'capital_deployment' to context.
        """
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import (
                DecisionLogORM, TradeORM, PortfolioORM,
            )

            metrics: Dict = {
                'trades_today': 0,
                'recs_ignored': 0,
                'recs_deferred': 0,
                'avg_ttd_minutes': None,
                'decisions_today': 0,
            }
            capital_deployment: Dict = {}

            today_start = datetime.combine(date.today(), datetime.min.time())

            with session_scope() as session:
                # Decision log metrics for today
                decisions = session.query(DecisionLogORM).filter(
                    DecisionLogORM.presented_at >= today_start,
                ).all()

                metrics['decisions_today'] = len(decisions)

                ttd_values = []
                for d in decisions:
                    if d.response == 'expired':
                        metrics['recs_ignored'] += 1
                    elif d.response == 'deferred':
                        metrics['recs_deferred'] += 1
                    if d.time_to_decision_seconds:
                        ttd_values.append(d.time_to_decision_seconds)

                if ttd_values:
                    avg_seconds = sum(ttd_values) / len(ttd_values)
                    metrics['avg_ttd_minutes'] = round(avg_seconds / 60, 1)

                # Trades today
                trades_today = session.query(TradeORM).filter(
                    TradeORM.created_at >= today_start,
                    TradeORM.trade_status.in_(['executed', 'partial', 'closed']),
                ).count()
                metrics['trades_today'] = trades_today

                # Capital deployment per portfolio
                portfolios = session.query(PortfolioORM).all()
                for p in portfolios:
                    equity = float(p.total_equity or 0)
                    cash = float(p.cash_balance or 0)
                    if equity > 0:
                        deployed_pct = ((equity - cash) / equity) * 100
                    else:
                        deployed_pct = 0.0

                    # Days since last trade in this portfolio
                    last_trade = session.query(TradeORM).filter(
                        TradeORM.portfolio_id == p.id,
                        TradeORM.trade_status.in_(['executed', 'partial', 'closed']),
                    ).order_by(TradeORM.created_at.desc()).first()

                    days_since = None
                    if last_trade and last_trade.created_at:
                        days_since = (datetime.utcnow() - last_trade.created_at).days

                    pname = p.account_id or p.name
                    capital_deployment[pname] = {
                        'equity': equity,
                        'cash': cash,
                        'deployed_pct': round(deployed_pct, 1),
                        'days_since_trade': days_since,
                    }

            context['accountability_metrics'] = metrics
            context['capital_deployment'] = capital_deployment

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data=metrics,
                messages=[
                    f"Accountability: {metrics['trades_today']} trades today, "
                    f"{metrics['recs_ignored']} ignored, "
                    f"TTD={metrics['avg_ttd_minutes'] or 'N/A'} min"
                ],
            )

        except Exception as e:
            logger.error(f"AccountabilityAgent failed: {e}")
            context['accountability_metrics'] = {}
            context['capital_deployment'] = {}
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Accountability error: {e}"],
            )

    def log_decision(
        self,
        rec_id: str,
        response: str,
        rationale: str,
        presented_at: datetime,
        responded_at: datetime,
        decision_type: str = "entry",
    ) -> None:
        """Write a decision to the DecisionLogORM."""
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import DecisionLogORM

            ttd = int((responded_at - presented_at).total_seconds()) if responded_at and presented_at else None

            with session_scope() as session:
                log = DecisionLogORM(
                    id=str(uuid.uuid4()),
                    recommendation_id=rec_id,
                    decision_type=decision_type,
                    presented_at=presented_at,
                    responded_at=responded_at,
                    response=response,
                    rationale=rationale,
                    time_to_decision_seconds=ttd,
                )
                session.add(log)

        except Exception as e:
            logger.error(f"Failed to log decision for rec {rec_id}: {e}")
