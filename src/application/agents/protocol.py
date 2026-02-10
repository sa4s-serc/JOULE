"""Typed contracts for agentic optimization runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class AgentRole(str, Enum):
    """Canonical roles for agentic optimization."""

    ARCHITECT = "architect"
    STRATEGIST = "strategist"
    ENGINEER = "engineer"
    SENTINEL = "sentinel"


@dataclass(frozen=True)
class AgentMessage:
    """A message produced by one agent stage."""

    role: AgentRole
    stage: str
    payload: Dict[str, Any]
    correlation_id: str


@dataclass
class AgentContext:
    """Execution context shared across all agents."""

    inputs: Dict[str, Any]
    memory: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Structured result from an agent run."""

    success: bool
    payload: Dict[str, Any] = field(default_factory=dict)
    message: Optional[AgentMessage] = None


@dataclass
class AgentError(Exception):
    """Rich error object for runtime and policy failures."""

    stage: str
    role: AgentRole
    detail: str

    def __str__(self) -> str:
        return f"[{self.stage}:{self.role}] {self.detail}"
