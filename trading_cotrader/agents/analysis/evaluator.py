"""
Evaluator Agent — Evaluates all open positions across portfolios for exit signals.

Wraps PortfolioEvaluationService. Generates exit/roll/adjust recommendations.

Enriches context with:
    - exit_signals: list of recommendation dicts
"""

import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class EvaluatorAgent:
    """Evaluates open positions for exit/roll/adjust signals."""

    name = "evaluator"

    def __init__(self, broker=None):
        self.broker = broker

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Evaluate all open trades across all portfolios.

        Writes 'exit_signals' to context.
        """
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.services.portfolio_evaluation_service import PortfolioEvaluationService
            from trading_cotrader.config.risk_config_loader import get_risk_config

            risk_config = get_risk_config()
            all_signals = []
            messages = []

            with session_scope() as session:
                svc = PortfolioEvaluationService(session, broker=self.broker)

                for portfolio_config in risk_config.portfolios.get_all():
                    try:
                        recs = svc.evaluate_portfolio(portfolio_config.name)
                        for rec in recs:
                            all_signals.append({
                                'id': rec.id,
                                'type': rec.recommendation_type.value if hasattr(rec.recommendation_type, 'value') else str(rec.recommendation_type),
                                'underlying': rec.underlying,
                                'strategy_type': rec.strategy_type,
                                'rationale': rec.rationale,
                                'exit_urgency': rec.exit_urgency,
                                'trade_id_to_close': rec.trade_id_to_close,
                                'portfolio': portfolio_config.name,
                            })
                        if recs:
                            messages.append(f"{portfolio_config.name}: {len(recs)} exit signals")
                    except Exception as e:
                        logger.warning(f"Evaluation failed for {portfolio_config.name}: {e}")
                        messages.append(f"{portfolio_config.name}: FAILED ({e})")

            context['exit_signals'] = all_signals

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={'exit_signal_count': len(all_signals)},
                messages=messages or ["No exit signals"],
            )

        except Exception as e:
            logger.error(f"EvaluatorAgent failed: {e}")
            context['exit_signals'] = []
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Evaluator error: {e}"],
            )
