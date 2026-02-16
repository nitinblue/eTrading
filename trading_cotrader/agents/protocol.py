"""
Agent Protocol — Defines the contract all agents must follow.

Every agent:
    1. Implements run(context) → AgentResult
    2. Implements safety_check(context) → (bool, str)
    3. Has a unique name
"""

from enum import Enum
from typing import Protocol, runtime_checkable
from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Status of an agent after execution."""
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ERROR = "error"


class AgentResult(BaseModel):
    """Result returned by every agent after execution."""
    agent_name: str
    status: AgentStatus
    data: dict = Field(default_factory=dict)
    messages: list[str] = Field(default_factory=list)
    requires_human: bool = False
    human_prompt: str | None = None
    objectives: list[str] = Field(default_factory=list)
    metrics: dict = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}


@runtime_checkable
class Agent(Protocol):
    """Protocol that all agents must implement."""
    name: str

    def run(self, context: dict) -> AgentResult:
        """Execute the agent's primary logic."""
        ...

    def safety_check(self, context: dict) -> tuple[bool, str]:
        """Pre-flight safety check. Returns (is_safe, reason_if_not)."""
        ...
