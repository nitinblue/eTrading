"""
Executor Agent — Executes approved trades via RecommendationService.

In paper mode, books as WhatIf trades. In live mode (future),
converts to real broker orders with double confirmation.

Uses BrokerRouter to dispatch to the correct broker handler.
Manual-execution brokers (Fidelity, Stallion) return MANUAL status.
"""

import logging

from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class ExecutorAgent:
    """Executes approved trade actions."""

    name = "executor"

    def __init__(self, broker=None, paper_mode: bool = True, broker_router=None):
        self.broker = broker
        self.paper_mode = paper_mode
        self.broker_router = broker_router

    def safety_check(self, context: dict) -> tuple[bool, str]:
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Execute approved actions from context.

        Reads 'action' from context — a dict with recommendation details.
        Uses RecommendationService.accept_recommendation() to book the trade.

        If the portfolio's broker is manual-execution (Fidelity, Stallion),
        returns a MANUAL status message instead of booking.
        """
        action = context.get('action')
        if not action:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                messages=["No action to execute"],
            )

        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.services.recommendation_service import RecommendationService

            rec_id = action.get('recommendation_id')
            portfolio_name = action.get('portfolio')
            notes = action.get('notes', 'Approved via workflow engine')

            if not rec_id:
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.ERROR,
                    messages=["No recommendation_id in action"],
                )

            # Check if this portfolio requires manual execution
            if portfolio_name and self.broker_router:
                from trading_cotrader.services.portfolio_manager import PortfolioManager
                with session_scope() as session:
                    pm = PortfolioManager(session)
                    if pm.is_manual_execution(portfolio_name):
                        pc = pm.get_portfolio_config(portfolio_name)
                        msg = (
                            f"MANUAL EXECUTION REQUIRED at {pc.broker_firm}\n"
                            f"  Account: {pc.account_number}\n"
                            f"  Recommendation: {rec_id[:8]}...\n"
                            f"  Execute this trade at your broker and confirm."
                        )
                        return AgentResult(
                            agent_name=self.name,
                            status=AgentStatus.COMPLETED,
                            data={
                                'manual': True,
                                'recommendation_id': rec_id,
                                'broker': pc.broker_firm,
                            },
                            messages=[msg],
                        )

            with session_scope() as session:
                svc = RecommendationService(session, broker=self.broker)

                if self.paper_mode:
                    notes = f"[PAPER] {notes}"

                trade = svc.accept_recommendation(
                    recommendation_id=rec_id,
                    notes=notes,
                    portfolio_name=portfolio_name,
                )

            trade_id = trade.id if trade else "unknown"
            mode = "PAPER" if self.paper_mode else "LIVE"

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                data={
                    'trade_id': trade_id,
                    'mode': mode,
                    'recommendation_id': rec_id,
                },
                messages=[f"[{mode}] Executed rec {rec_id[:8]}... -> trade {trade_id[:8]}..."],
            )

        except Exception as e:
            logger.error(f"ExecutorAgent failed: {e}")
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                messages=[f"Execution error: {e}"],
            )
