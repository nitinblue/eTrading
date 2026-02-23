"""
Trade Discipline Agent — Trading workflow & accountability.

Absorbs logic from: accountability, session_objectives.
Skeleton for now — run() returns no-op until logic is implemented.
"""

import logging
from typing import ClassVar, List

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class TradeDisciplineAgent(BaseAgent):
    """Trading workflow manager: session objectives, decision tracking, accountability."""

    # Class-level metadata
    name: ClassVar[str] = "trade_discipline"
    display_name: ClassVar[str] = "Trade Discipline"
    category: ClassVar[str] = "learning"
    role: ClassVar[str] = "Trading workflow & accountability"
    intro: ClassVar[str] = (
        "I enforce process discipline. Morning objectives, decision tracking, "
        "time-to-action, ignored recs, EOD grading — I make sure the trading "
        "workflow stays honest."
    )
    responsibilities: ClassVar[List[str]] = [
        "Session objectives",
        "Decision tracking",
        "Time-to-decision",
        "Rec expiry",
        "EOD grading",
        "Gap analysis",
        "Corrective plans",
    ]
    datasources: ClassVar[List[str]] = [
        "DecisionLogORM",
        "RecommendationORM",
        "AgentObjectiveORM",
        "Agent run history",
        "Portfolio performance",
    ]
    boundaries: ClassVar[List[str]] = [
        "Cannot force decisions",
        "Observes and grades only",
        "No trading authority",
    ]
    runs_during: ClassVar[List[str]] = ["booting", "reporting"]

    def __init__(self, container=None, config=None):
        super().__init__(container=container, config=config)

    def run(self, context: dict) -> AgentResult:
        """Skeleton — no-op until accountability/objectives logic is wired."""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            messages=["Trade Discipline: skeleton (no-op)"],
        )
