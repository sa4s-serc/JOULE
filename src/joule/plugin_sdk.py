"""JOULE Operator Plugin SDK.

This module re-exports the public interface that external operator
plugins should depend on.  Plugin authors should import from
``joule.plugin_sdk`` rather than reaching into internal modules,
to remain insulated from implementation changes.

Quick start
-----------

1. Create a class that extends :class:`~joule.transformers.base.BaseOperator`::

    from joule.plugin_sdk import BaseOperator, TransformationResult, TargetSpec, Tier

    class MyOptimizer(BaseOperator):
        name = "my_optimizer"
        tier = Tier.M
        targets_smells = frozenset({"C3", "C10"})

        def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
            # ... apply transformation to target.source ...
            return [self.build_result(
                candidate_source=new_source,
                reasoning="applied my optimization",
            )]

2. Register your operator via the ``joule.operators`` entry point in
   ``pyproject.toml``::

    [project.entry-points."joule.operators"]
    my_optimizer = "my_package.optimizers:MyOptimizer"

3. Validate the plugin with ``joule doctor --plugin-check``.

See ``docs/PLUGIN_SDK.md`` for a complete walkthrough.
"""

from __future__ import annotations

# Core data models used in operator interfaces
from joule.models import (
    SearchContext,
    SearchPhase,
    TargetSpec,
    Tier,
    TransformationResult,
    tier_descriptor,
)

# Base operator class — subclass this to create your operator
from joule.transformers.base import BaseOperator

# Protocol — use this for type annotations when accepting a registry
from joule.transformers.protocols import OperatorSelectorProtocol

__all__ = [
    # Models
    "SearchContext",
    "SearchPhase",
    "TargetSpec",
    "Tier",
    "TransformationResult",
    "tier_descriptor",
    # Core
    "BaseOperator",
    "OperatorSelectorProtocol",
]
