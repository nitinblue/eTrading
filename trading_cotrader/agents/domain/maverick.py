"""
Maverick Agent (Trader) — Domain orchestrator for trading workflow.

Cross-references Steward's PortfolioBundle (positions, risk) with Scout's
ResearchContainer (market intelligence) to produce trading signals.

Future: absorbs executor + notifier + accountability + session_objectives.
"""

import logging
from typing import ClassVar, List, Optional

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class MaverickAgent(BaseAgent):
    """Trading orchestrator: brings Scout + Steward together for trading decisions."""

    # Class-level metadata
    name: ClassVar[str] = "maverick"
    display_name: ClassVar[str] = "Maverick (Trader)"
    category: ClassVar[str] = "domain"
    role: ClassVar[str] = "Trading orchestration & Scout/Steward cross-reference"
    intro: ClassVar[str] = (
        "I bring it all together. I cross-reference your portfolio positions with "
        "market intelligence to surface actionable trading signals. Execution, "
        "notifications, discipline — I make sure trades happen right."
    )
    responsibilities: ClassVar[List[str]] = [
        "Trading orchestration",
        "Scout/Steward cross-reference",
        "Trading signals",
        "Blotter data coordination",
        "Order execution",
        "Notifications",
        "Session objectives",
        "Decision tracking",
    ]
    datasources: ClassVar[List[str]] = [
        "PortfolioBundle (via ContainerManager)",
        "ResearchContainer (via ContainerManager)",
        "DecisionLogORM",
        "Broker adapters",
    ]
    boundaries: ClassVar[List[str]] = [
        "LIMIT orders only (no market orders)",
        "Requires explicit approval for execution",
        "Cannot override risk limits",
    ]
    runs_during: ClassVar[List[str]] = ["booting", "monitoring", "execution", "reporting"]

    def __init__(self, container_manager=None, config=None):
        super().__init__(container=None, config=config)
        self._container_manager = container_manager

    def run(self, context: dict) -> AgentResult:
        """Cross-reference Steward's portfolio positions with Scout's research.

        For each underlying in each portfolio bundle, produces a signal with:
        - Position summary (net delta, count) from Steward's containers
        - Market context (regime, phase, iv_rank, direction) from Scout's containers
        """
        if not self._container_manager:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                messages=["Maverick: no container_manager — skipped"],
            )

        research = self._container_manager.research
        trading_signals = []

        for bundle in self._container_manager.get_all_bundles():
            for underlying in bundle.positions.underlyings:
                positions = bundle.positions.get_by_underlying(underlying)
                net_delta = sum(float(p.delta) for p in positions)

                signal = {
                    'underlying': underlying,
                    'portfolio': bundle.config_name,
                    'net_delta': round(net_delta, 2),
                    'position_count': len(positions),
                }

                entry = research.get(underlying)
                if entry:
                    signal.update({
                        'regime': entry.hmm_regime_label,
                        'phase': entry.phase_name,
                        'iv_rank': entry.iv_rank,
                        'levels_direction': entry.levels_direction,
                    })

                trading_signals.append(signal)

        context['trading_signals'] = trading_signals

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            data={'signal_count': len(trading_signals)},
            messages=[f"Maverick: {len(trading_signals)} trading signals generated"],
        )
