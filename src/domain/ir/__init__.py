"""
HEDGE Intermediate Representation (IR)

Provides the core IR schema and utilities for:
- Type-safe AST representation
- IR validation
- Serialization/deserialization
- Tree traversal and transformation
- Complexity metrics
"""

from src.domain.ir import schema
from src.domain.ir.context import (DependencyGraph, MutationContext, ScopeInfo,
                                   SymbolInfo)
from src.domain.ir.metrics import IRMetricsCollector, MutationStatistics
from src.domain.ir.serialization import IRSerializer
from src.domain.ir.utils import (NodeTransformer, NodeVisitor,
                                 VariableReplacer, collect_names,
                                 find_all_nodes, find_nodes, traverse)
from src.domain.ir.validators import IRValidator, ValidationResult

__all__ = [
    # Schema module
    "schema",
    # Traversal utilities
    "NodeVisitor",
    "NodeTransformer",
    "find_nodes",
    "find_all_nodes",
    "collect_names",
    "traverse",
    "VariableReplacer",
    # Context
    "MutationContext",
    "DependencyGraph",
    "SymbolInfo",
    "ScopeInfo",
    # Validation
    "IRValidator",
    "ValidationResult",
    # Serialization
    "IRSerializer",
    # Metrics
    "IRMetricsCollector",
    "MutationStatistics",
]
