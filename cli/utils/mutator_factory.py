"""Factory for creating mutators based on configuration."""

import os
import logging
from typing import List, Set, Optional, Tuple, Any

from src.application.mutators.base import MutationLayer
from src.application.mutators.semantic_layer import AlgorithmicIntentMutator, ProgramIntentMutator
from src.application.mutators.algorithmic_layer import DataStructureOptimizer, ComplexityReducer
from src.application.mutators.syntactic_layer import PythonicIdiomOptimizer, CodePatternOptimizer
from src.application.mutators.micro_layer import ConstantOptimizer, DeadCodeEliminator, LoopMicroOptimizer
from src.infrastructure.llm.client import create_llm_client

logger = logging.getLogger(__name__)

def create_mutators(level: str = 'standard', 
                   layers: Optional[str] = None,
                   llm_provider: Optional[str] = None,
                   llm_model: Optional[str] = None,
                   exclude_mutators: Optional[str] = None,
                   progress=None,
                   task=None) -> Tuple[List, Set[MutationLayer], Any]:
    """
    Create mutators based on optimization level and configuration.
    
    Args:
        level: Optimization level (micro, basic, standard, advanced, aggressive)
        layers: Comma-separated list of specific layers to enable
        llm_provider: LLM provider (loads from config if None)
        llm_model: Custom LLM model name (loads from config if None)
        exclude_mutators: Comma-separated list of mutators to exclude
        progress: Rich progress instance for updates
        task: Progress task ID for updates
        
    Returns:
        Tuple of (mutators_list, enabled_layers_set, llm_client)
    """
    
    # Determine enabled layers
    enabled_layers = _get_enabled_layers(level, layers)
    
    # Initialize LLM if needed
    llm = None
    # Level 'basic' and above have SYNTACTIC layer which can use LLM
    # Level 'advanced' and above have SEMANTIC layer which requires LLM
    use_llm = level in ['basic', 'standard', 'advanced', 'aggressive']
    
    if use_llm:
        try:
            # create_llm_client will handle its own config if llm_provider/llm_model are None
            llm = create_llm_client(llm_provider, None, llm_model)
            if progress:
                progress.update(task, description="✓ LLM client initialized")
        except Exception as e:
            # Only warn if it's strictly required (advanced/aggressive)
            if level in ['advanced', 'aggressive']:
                logger.warning(f"LLM client initialization failed: {e}. Disabling semantic layer.")
                enabled_layers.discard(MutationLayer.SEMANTIC)
                if progress:
                    progress.update(task, description="⚠ Semantic layer disabled")
            else:
                logger.debug(f"LLM client not initialized: {e}")
    
    # Create mutators
    mutators = []
    
    # Semantic Layer Mutators
    if MutationLayer.SEMANTIC in enabled_layers and llm:
        mutators.extend([
            AlgorithmicIntentMutator(llm),
            ProgramIntentMutator(llm)
        ])
        if progress:
            progress.update(task, description="✓ Semantic layer mutators enabled")
    
    # Algorithmic Layer Mutators  
    if MutationLayer.ALGORITHMIC in enabled_layers:
        mutators.extend([
            DataStructureOptimizer(),
            ComplexityReducer()
        ])
        if progress:
            progress.update(task, description="✓ Algorithmic layer mutators enabled")
    
    # Syntactic Layer Mutators
    if MutationLayer.SYNTACTIC in enabled_layers:
        syntactic_mutators = [PythonicIdiomOptimizer()]
        if llm:  # LLM-based syntactic mutators
            syntactic_mutators.append(CodePatternOptimizer(llm))
        mutators.extend(syntactic_mutators)
        if progress:
            progress.update(task, description="✓ Syntactic layer mutators enabled")
    
    # Micro Layer Mutators
    if MutationLayer.MICRO in enabled_layers:
        mutators.extend([
            ConstantOptimizer(),
            DeadCodeEliminator(), 
            LoopMicroOptimizer()
        ])
        if progress:
            progress.update(task, description="✓ Micro layer mutators enabled")
    
    # Filter excluded mutators
    if exclude_mutators:
        excluded = [m.strip() for m in exclude_mutators.split(',')]
        mutators = [m for m in mutators if m.__class__.__name__ not in excluded]
        if progress:
            progress.update(task, description=f"✓ Mutators filtered: {len(mutators)} active")
    
    return mutators, enabled_layers, llm

def _get_enabled_layers(level: str, layers: Optional[str]) -> Set[MutationLayer]:
    """Determine which mutation layers are enabled based on optimization level."""
    
    # Parse custom layer specification if provided
    if layers:
        layer_names = [name.strip().lower() for name in layers.split(',')]
        enabled_layers = set()
        for name in layer_names:
            try:
                enabled_layers.add(MutationLayer(name))
            except ValueError:
                logger.warning(f"Unknown layer: {name}")
        return enabled_layers
    
    # Default layer sets based on optimization level
    if level == 'micro':
        return {MutationLayer.MICRO}
    elif level == 'basic':
        return {MutationLayer.MICRO, MutationLayer.SYNTACTIC}
    elif level == 'standard':
        return {MutationLayer.MICRO, MutationLayer.SYNTACTIC, MutationLayer.ALGORITHMIC}
    elif level == 'advanced':
        return {MutationLayer.MICRO, MutationLayer.SYNTACTIC, MutationLayer.ALGORITHMIC, MutationLayer.SEMANTIC}
    elif level == 'aggressive':
        return set(MutationLayer)  # All layers
    else:
        # Default to standard
        return {MutationLayer.MICRO, MutationLayer.SYNTACTIC, MutationLayer.ALGORITHMIC}

def list_available_mutators() -> dict:
    """Return a dictionary of available mutators organized by layer."""
    return {
        'semantic': [
            {'name': 'AlgorithmicIntentMutator', 'description': 'Algorithm selection and complexity optimization'},
            {'name': 'ProgramIntentMutator', 'description': 'Program logic and intent optimization'}
        ],
        'algorithmic': [
            {'name': 'DataStructureOptimizer', 'description': 'Data structure selection optimization'},
            {'name': 'ComplexityReducer', 'description': 'Algorithmic complexity reduction'}
        ],
        'syntactic': [
            {'name': 'PythonicIdiomOptimizer', 'description': 'Python idiom and pattern optimization'},
            {'name': 'CodePatternOptimizer', 'description': 'LLM-based code pattern improvements'}
        ],
        'micro': [
            {'name': 'ConstantOptimizer', 'description': 'Constant folding and propagation'},
            {'name': 'DeadCodeEliminator', 'description': 'Dead code and unreachable code elimination'},
            {'name': 'LoopMicroOptimizer', 'description': 'Loop unrolling and micro-optimizations'}
        ]
    }