from __future__ import annotations

from joule.models import Tier

from .data_structure_substitution import ListToSetMembership


class ContainerMembershipOperator(ListToSetMembership):
    name = "container_membership"
    tier = Tier.L
    targets_smells = frozenset(["C5"])
