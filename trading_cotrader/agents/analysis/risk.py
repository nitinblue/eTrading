"""
Risk Agent — Calculates portfolio VaR and concentration metrics.

Wraps VaRCalculator and correlation services.

Enriches context with:
    - risk_snapshot: dict (var_95, var_99, es_95, concentration)
"""

import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class RiskAgent:
    """Calculates current portfolio risk metrics."""

    name = "risk"

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Calculate risk metrics for all portfolios.

        Writes 'risk_snapshot' to context.
        """
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import TradeORM, PortfolioORM

            risk_data = {
                'var_95': 0.0,
                'var_99': 0.0,
                'es_95': 0.0,
                'open_positions': 0,
                'underlying_concentration': {},
            }

            with session_scope() as session:
                # Count open positions
                open_trades = session.query(TradeORM).filter(
                    TradeORM.is_open == True
                ).all()

                risk_data['open_positions'] = len(open_trades)

                # Underlying concentration
                underlying_counts: dict[str, int] = {}
                for t in open_trades:
                    sym = t.underlying_symbol
                    underlying_counts[sym] = underlying_counts.get(sym, 0) + 1
                risk_data['underlying_concentration'] = underlying_counts

                # Try to calculate VaR if we have positions
                if open_trades:
                    try:
                        from trading_cotrader.services.risk.var_calculator import VaRCalculator
                        calculator = VaRCalculator()
                        # VaR calculation requires trade domain objects — skip if complex
                        # For now, use stored VaR from portfolio records
                        portfolios = session.query(PortfolioORM).all()
                        total_var_95 = sum(float(p.var_1d_95 or 0) for p in portfolios)
                        total_var_99 = sum(float(p.var_1d_99 or 0) for p in portfolios)
                        risk_data['var_95'] = total_var_95
                        risk_data['var_99'] = total_var_99
                    except Exception as e:
                        logger.debug(f"VaR calculation skipped: {e}")

            context['risk_snapshot'] = risk_data

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data=risk_data,
                messages=[
                    f"Risk: {risk_data['open_positions']} positions, "
                    f"VaR95=${risk_data['var_95']:.0f}"
                ],
            )

        except Exception as e:
            logger.error(f"RiskAgent failed: {e}")
            context['risk_snapshot'] = {}
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Risk calculation error: {e}"],
            )
