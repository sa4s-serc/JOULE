"""
HEDGE Mutator System - Hierarchical Code Optimization

This package provides a comprehensive mutation system for code optimization
organized in hierarchical layers from high-level semantic changes to low-level
micro-optimizations.

Main Components:
- Base classes for layered mutations
- Registry system for mutator management
- Enhanced orchestration with intelligent pruning
- IR-only mutation framework for type safety
- Comment sanitization for LLM security

Layers:
- SEMANTIC: Algorithm intent and high-level logic (LLM-powered)
- ALGORITHMIC: Data structures and complexity improvements
- SYNTACTIC: Python idioms and code patterns
- MICRO: Low-level optimizations (constant folding, dead code elimination)
"""

# Core base classes
from .base import (
    MutationLayer,
    MutationResult,
    LayeredMutator,
    MutationOrchestrator as LegacyMutationOrchestrator,  # Legacy
    create_mutation_result,
    safe_deepcopy_ir,
    mutate_ir,
    LazyIRWrapper
)

# Enhanced system
from .orchestrator import MutationOrchestrator, OrchestrationConfig, LayerResult
from .registry import (
    MutatorRegistry,
    get_registry,
    register_mutator,
    auto_discover_mutators
)
from .ir_mutator_base import IROnlyMutator, IRTransformerBase, IRMutationMetadata

# LLM base with security
from .semantic_base import LLMMutatorBase, get_llm_cache

# Layer implementations
from .semantic_layer import AlgorithmicIntentMutator, ProgramIntentMutator
from .algorithmic_layer import DataStructureOptimizer, ComplexityReducer
from .syntactic_layer import PythonicIdiomOptimizer, CodePatternOptimizer
from .micro_layer import ConstantOptimizer, DeadCodeEliminator, LoopMicroOptimizer
from .advanced_performance import AdvancedAlgorithmicOptimizer, MemoryOptimizer, VectorizationOptimizer

# Utility functions
def initialize_mutator_system():
    """Initialize the mutator system with auto-discovery."""
    auto_discover_mutators()
    return get_registry()

def get_available_mutators():
    """Get all available mutators organized by layer."""
    registry = get_registry()
    return {
        layer: registry.get_layer_mutators(layer)
        for layer in MutationLayer
    }

def create_orchestrator(config=None):
    """Create a new mutation orchestrator with optional configuration."""
    return MutationOrchestrator(config)

# Auto-initialize on import
try:
    initialize_mutator_system()
except Exception as e:
    import logging
    logging.warning(f"Failed to auto-initialize mutator system: {e}")

__all__ = [
    # Core classes
    'MutationLayer',
    'MutationResult', 
    'LayeredMutator',
    'MutationOrchestrator',
    'OrchestrationConfig',
    'LayerResult',
    
    # Registry system
    'MutatorRegistry',
    'get_registry',
    'register_mutator',
    'auto_discover_mutators',
    
    # Enhanced base classes
    'IROnlyMutator',
    'IRTransformerBase',
    'IRMutationMetadata',
    'LLMMutatorBase',
    
    # Layer mutators
    'AlgorithmicIntentMutator',
    'ProgramIntentMutator', 
    'DataStructureOptimizer',
    'ComplexityReducer',
    'PythonicIdiomOptimizer',
    'CodePatternOptimizer',
    'ConstantOptimizer',
    'DeadCodeEliminator',
    'LoopMicroOptimizer',
    'AdvancedAlgorithmicOptimizer',
    'MemoryOptimizer',
    'VectorizationOptimizer',
    
    # Utility functions
    'initialize_mutator_system',
    'get_available_mutators',
    'create_orchestrator',
    'create_mutation_result',
    'safe_deepcopy_ir',
    'mutate_ir',
    'get_llm_cache'
]