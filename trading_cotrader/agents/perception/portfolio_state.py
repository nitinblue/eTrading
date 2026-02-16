"""
Portfolio State Agent — Reads current portfolio state from DB.

Enriches context with:
    - portfolios: list of portfolio summaries
    - open_trades: list of open trades across all portfolios
    - total_equity: Decimal
    - daily_pnl_pct / weekly_pnl_pct: float
    - trades_today_count: int
    - weekly_trades_per_portfolio: dict
    - portfolio_drawdowns: dict
    - consecutive_losses: dict
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List
import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class PortfolioStateAgent:
    """Reads portfolio state from DB and enriches workflow context."""

    name = "portfolio_state"

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Read all portfolio state and populate context for Guardian and other agents.
        """
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import (
                PortfolioORM, TradeORM,
            )

            with session_scope() as session:
                # Get all portfolios
                portfolios = session.query(PortfolioORM).all()
                portfolio_summaries = []
                total_equity = Decimal('0')
                total_daily_pnl = Decimal('0')

                for p in portfolios:
                    equity = p.total_equity or Decimal('0')
                    daily = p.daily_pnl or Decimal('0')
                    total_equity += equity
                    total_daily_pnl += daily

                    portfolio_summaries.append({
                        'id': p.id,
                        'name': p.name,
                        'account_id': p.account_id,
                        'broker': p.broker or '',
                        'portfolio_type': p.portfolio_type or '',
                        'equity': float(equity),
                        'daily_pnl': float(daily),
                        'cash': float(p.cash_balance or 0),
                        'delta': float(p.portfolio_delta or 0),
                        'theta': float(p.portfolio_theta or 0),
                    })

                # Open trades
                open_trades = session.query(TradeORM).filter(
                    TradeORM.is_open == True
                ).all()

                open_trade_list = []
                for t in open_trades:
                    open_trade_list.append({
                        'id': t.id,
                        'underlying': t.underlying_symbol,
                        'portfolio_id': t.portfolio_id,
                        'status': t.trade_status,
                        'pnl': float(t.total_pnl or 0),
                        'delta': float(t.current_delta or 0),
                        'theta': float(t.current_theta or 0),
                    })

                # Trades today count
                today_start = datetime.combine(date.today(), datetime.min.time())
                trades_today = session.query(TradeORM).filter(
                    TradeORM.created_at >= today_start,
                    TradeORM.trade_status.in_(['executed', 'partial', 'closed']),
                ).count()

                # Weekly trades per portfolio
                week_start = today_start - timedelta(days=date.today().weekday())
                weekly_trades_query = session.query(
                    TradeORM.portfolio_id, TradeORM.id
                ).filter(
                    TradeORM.created_at >= week_start,
                    TradeORM.trade_status.in_(['executed', 'partial', 'closed']),
                ).all()

                # Map portfolio_id → account_id for lookup
                portfolio_id_to_name = {
                    p.id: (p.account_id or p.name) for p in portfolios
                }
                weekly_per_portfolio: Dict[str, int] = {}
                for portfolio_id, _ in weekly_trades_query:
                    pname = portfolio_id_to_name.get(portfolio_id, portfolio_id)
                    weekly_per_portfolio[pname] = weekly_per_portfolio.get(pname, 0) + 1

            # Calculate daily P&L percentage
            daily_pnl_pct = 0.0
            if total_equity > 0:
                daily_pnl_pct = float(total_daily_pnl / total_equity * 100)

            # Enrich context
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
            logger.error(f"PortfolioStateAgent failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Portfolio state error: {e}"],
            )
