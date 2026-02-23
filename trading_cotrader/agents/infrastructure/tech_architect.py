"""
Tech Architect Agent — Infrastructure, ops & QA.

Absorbs logic from: broker_router, notifier, reporter, qa_agent.
Skeleton for now — run() returns no-op until logic is implemented.
"""

import logging
from typing import ClassVar, List

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class TechArchitectAgent(BaseAgent):
    """Consolidated infrastructure: broker routing, notifications, reporting, QA."""

    # Class-level metadata
    name: ClassVar[str] = "tech_architect"
    display_name: ClassVar[str] = "Tech Architect"
    category: ClassVar[str] = "infrastructure"
    role: ClassVar[str] = "Infrastructure, ops & QA"
    intro: ClassVar[str] = (
        "I handle the plumbing. Broker routing, notifications, reports, test health, "
        "performance tracking — the operational backbone that keeps everything "
        "running and verified."
    )
    responsibilities: ClassVar[List[str]] = [
        "Broker routing",
        "Order routing",
        "Notifications",
        "Daily reports",
        "Performance reports",
        "Test suite health",
        "Coverage analysis",
    ]
    datasources: ClassVar[List[str]] = [
        "config/brokers.yaml",
        "Broker adapters",
        "PortfolioORM",
        "TradeORM",
        "PerformanceMetricsService",
        "pytest runner",
    ]
    boundaries: ClassVar[List[str]] = [
        "Cannot make trading decisions",
        "Infrastructure and reporting only",
        "Does not evaluate strategies",
    ]
    runs_during: ClassVar[List[str]] = [
        "execution",
        "recommendation_review",
        "trade_review",
        "reporting",
    ]

    def __init__(self, container=None, config=None):
        super().__init__(container=container, config=config)

    def run(self, context: dict) -> AgentResult:
        """Skeleton — no-op until broker/notification/report logic is wired."""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            messages=["Tech Architect: skeleton (no-op)"],
        )
