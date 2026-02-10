"""Registry for role-based agent discovery."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Dict, List

from src.application.agents.base import Agent
from src.application.agents.protocol import AgentRole


class AgentRegistry:
    """Simple in-memory registry keyed by role."""

    def __init__(self):
        self._agents_by_role: DefaultDict[AgentRole, List[Agent]] = defaultdict(list)
        self._agents_by_name: Dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        if agent.name in self._agents_by_name:
            raise ValueError(f"Agent with name '{agent.name}' already registered")
        self._agents_by_role[agent.role].append(agent)
        self._agents_by_name[agent.name] = agent

    def get_by_role(self, role: AgentRole) -> List[Agent]:
        return list(self._agents_by_role.get(role, []))

    def get(self, name: str) -> Agent | None:
        return self._agents_by_name.get(name)

    def roles(self) -> List[AgentRole]:
        return list(self._agents_by_role.keys())
