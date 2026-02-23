"""
BaseAgent — Abstract base class for all agents in the Trading CoTrader system.

Every agent:
    1. Has class-level identity metadata (name, role, responsibilities, etc.)
    2. Implements run(context) -> AgentResult (primary business logic)
    3. Optionally implements populate(context) -> AgentResult (fill container from external APIs)
    4. Optionally implements analyze(context) -> AgentResult (future AI/ML on container data)
    5. Implements safety_check(context) -> (bool, str) (pre-flight check)

Backward-compatible with the Agent Protocol (name, run, safety_check).
"""

from abc import ABC, abstractmethod
from typing import ClassVar, List

from trading_cotrader.agents.protocol import AgentResult, AgentStatus


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    # Class-level identity — override in subclass
    name: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    category: ClassVar[str] = ""  # 'domain' | 'safety' | 'infrastructure' | 'learning'
    role: ClassVar[str] = ""
    intro: ClassVar[str] = ""
    responsibilities: ClassVar[List[str]] = []
    datasources: ClassVar[List[str]] = []
    boundaries: ClassVar[List[str]] = []
    runs_during: ClassVar[List[str]] = []

    def __init__(self, container=None, config=None):
        self.container = container
        self.config = config

    def populate(self, context: dict) -> AgentResult:
        """Fill container from external APIs. Domain agents override. Default: no-op."""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            messages=["No populate logic (default no-op)"],
        )

    @abstractmethod
    def run(self, context: dict) -> AgentResult:
        """Primary business logic."""
        ...

    def safety_check(self, context: dict) -> tuple[bool, str]:
        """Pre-flight check. Default: always safe."""
        return True, ""

    def analyze(self, context: dict) -> AgentResult:
        """Future AI/ML on container data. Default: no-op."""
        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            messages=["No analyze logic (default no-op)"],
        )

    @classmethod
    def get_metadata(cls) -> dict:
        """Returns registry-style dict for API/UI. Replaces AGENT_REGISTRY."""
        return {
            'name': cls.name,
            'display_name': cls.display_name,
            'category': cls.category,
            'role': cls.role,
            'intro': cls.intro,
            'description': cls.role,
            'responsibilities': list(cls.responsibilities),
            'datasources': list(cls.datasources),
            'boundaries': list(cls.boundaries),
            'runs_during': list(cls.runs_during),
        }
