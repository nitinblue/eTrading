"""
Human Interface Models — Structured messages between user and workflow engine.
"""

from pydantic import BaseModel, Field


class UserIntent(BaseModel):
    """A structured command from the user to the workflow engine."""
    action: str                          # approve, reject, defer, status, list, halt, resume, override
    target: str | None = None            # rec ID, portfolio name, etc.
    parameters: dict = Field(default_factory=dict)
    rationale: str = ""                  # required for overrides


class SystemResponse(BaseModel):
    """A structured response from the workflow engine to the user."""
    message: str
    data: dict = Field(default_factory=dict)
    requires_action: bool = False
    available_actions: list[str] = Field(default_factory=list)
    pending_decisions: list[dict] = Field(default_factory=list)
