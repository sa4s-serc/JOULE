"""Base interface for all agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict

from src.application.agents.protocol import AgentContext, AgentResult, AgentRole


class Agent(ABC):
    """Abstract interface for agent implementations."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent name."""

    @property
    @abstractmethod
    def role(self) -> AgentRole:
        """Canonical agent role."""

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, type]:
        """Expected input schema as key->type mapping."""

    @property
    @abstractmethod
    def output_schema(self) -> Dict[str, type]:
        """Produced payload schema as key->type mapping."""

    @abstractmethod
    def run(self, context: AgentContext) -> AgentResult:
        """Run agent logic against shared context."""
