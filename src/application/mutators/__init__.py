"""
HEDGE Mutation System

Provides hierarchical mutation strategies organized in layers:
- Semantic: Algorithm intent and high-level logic (LLM-based)
- Algorithmic: Data structures and complexity
- Syntactic: Code patterns and idioms
- Micro: Low-level optimizations (constant folding, dead code elimination)
"""
from src.application.mutators.base import (
    MutationLayer,
    MutationResult,
    LayeredMutator,
    MutationOrchestrator,
    LazyIRWrapper,
    safe_deepcopy_ir,
    mutate_ir,
    create_mutation_result,
)
from src.application.mutators.structural import StructuralMutator
from src.application.mutators.semantic import SemanticMutator
from src.application.mutators.syntactic import SyntacticReasoningMutator
from src.application.mutators.semantic_base import (
    LLMMutatorBase,
    LLMResponseCache,
    get_llm_cache,
    STDLIB_WHITELIST,
)

__all__ = [
    # Base classes and utilities
    "MutationLayer",
    "MutationResult", 
    "LayeredMutator",
    "MutationOrchestrator",
    "LazyIRWrapper",
    "safe_deepcopy_ir",
    "mutate_ir",
    "create_mutation_result",
    # Mutators
    "StructuralMutator",
    "SemanticMutator",
    "SyntacticReasoningMutator",
    # LLM base
    "LLMMutatorBase",
    "LLMResponseCache",
    "get_llm_cache",
    "STDLIB_WHITELIST",
]
