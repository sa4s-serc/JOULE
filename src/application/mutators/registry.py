"""
Mutator Registry - Centralized Mutator Management

Provides:
- Dynamic mutator discovery and registration
- Dependency resolution between mutators
- Performance tracking and adaptive selection
- Plugin system for custom mutators
"""
import logging
from typing import Dict, List, Set, Type, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from src.application.mutators.base import LayeredMutator, MutationLayer, MutationResult
from src.domain.ir import schema

logger = logging.getLogger(__name__)


@dataclass
class MutatorMetrics:
    """Performance metrics for a mutator."""
    total_attempts: int = 0
    successful_mutations: int = 0
    avg_confidence: float = 0.0
    avg_execution_time: float = 0.0
    energy_improvements: List[float] = field(default_factory=list)
    
    @property
    def success_rate(self) -> float:
        return self.successful_mutations / max(1, self.total_attempts)
    
    @property
    def avg_energy_improvement(self) -> float:
        return sum(self.energy_improvements) / max(1, len(self.energy_improvements))


@dataclass
class MutatorInfo:
    """Information about a registered mutator."""
    mutator_class: Type[LayeredMutator]
    layer: MutationLayer
    strategies: List[str]
    dependencies: Set[str] = field(default_factory=set)
    conflicts: Set[str] = field(default_factory=set)
    enabled: bool = True
    metrics: MutatorMetrics = field(default_factory=MutatorMetrics)


class MutatorRegistry:
    """
    Central registry for all mutators with intelligent selection.
    
    Features:
    - Automatic mutator discovery
    - Performance-based adaptive selection
    - Dependency and conflict resolution
    - Plugin system for custom mutators
    """
    
    def __init__(self):
        self._mutators: Dict[str, MutatorInfo] = {}
        self._layer_mutators: Dict[MutationLayer, List[str]] = {
            layer: [] for layer in MutationLayer
        }
        self._strategy_map: Dict[str, str] = {}  # strategy -> mutator_name
        self._initialized = False
    
    def register_mutator(
        self, 
        name: str, 
        mutator_class: Type[LayeredMutator],
        dependencies: Optional[Set[str]] = None,
        conflicts: Optional[Set[str]] = None
    ) -> None:
        """
        Register a mutator with the registry.
        
        Args:
            name: Unique name for the mutator
            mutator_class: The mutator class
            dependencies: Set of mutator names this depends on
            conflicts: Set of mutator names this conflicts with
        """
        # Create temporary instance to get metadata
        try:
            # Try to create instance with default parameters
            if hasattr(mutator_class, '__init__'):
                import inspect
                sig = inspect.signature(mutator_class.__init__)
                params = list(sig.parameters.keys())[1:]  # Skip 'self'
                
                # Create with minimal parameters
                if 'llm_client' in params:
                    temp_instance = mutator_class(llm_client=None, enabled_strategies=set())
                else:
                    temp_instance = mutator_class(enabled_strategies=set())
            else:
                temp_instance = mutator_class()
        except Exception as e:
            logger.warning(f"Could not create instance of {mutator_class.__name__}: {e}")
            return
        
        info = MutatorInfo(
            mutator_class=mutator_class,
            layer=temp_instance.layer,
            strategies=temp_instance.get_available_strategies(),
            dependencies=dependencies or set(),
            conflicts=conflicts or set()
        )
        
        self._mutators[name] = info
        self._layer_mutators[info.layer].append(name)
        
        # Map strategies to mutator
        for strategy in info.strategies:
            self._strategy_map[strategy] = name
        
        logger.info(f"Registered mutator '{name}' with {len(info.strategies)} strategies")
    
    def get_mutator(self, name: str, enabled_strategies: Optional[Set[str]] = None, llm_client=None) -> Optional[LayeredMutator]:
        """Get a mutator instance by name."""
        if name not in self._mutators:
            return None
        
        info = self._mutators[name]
        if not info.enabled:
            return None
        
        # Try to create instance with appropriate parameters
        try:
            import inspect
            sig = inspect.signature(info.mutator_class.__init__)
            params = list(sig.parameters.keys())[1:]  # Skip 'self'
            
            # Handle different constructor patterns
            if 'llm_client' in params and params[0] == 'llm_client':
                # LLM client is first positional argument
                if llm_client is not None:
                    if 'enabled_strategies' in params:
                        return info.mutator_class(llm_client, enabled_strategies=enabled_strategies or set())
                    else:
                        return info.mutator_class(llm_client)
                else:
                    # Skip mutators that require LLM client when none provided
                    logger.debug(f"Skipping mutator {name}: requires llm_client but none provided")
                    return None
            else:
                # Standard keyword arguments
                kwargs = {}
                if 'enabled_strategies' in params:
                    kwargs['enabled_strategies'] = enabled_strategies or set()
                if 'llm_client' in params and llm_client is not None:
                    kwargs['llm_client'] = llm_client
                
                return info.mutator_class(**kwargs)
        except Exception as e:
            logger.warning(f"Failed to create mutator {name}: {e}")
            return None
    
    def get_layer_mutators(self, layer: MutationLayer) -> List[str]:
        """Get all mutator names for a specific layer."""
        return [name for name in self._layer_mutators[layer] 
                if self._mutators[name].enabled]
    
    def get_mutators_for_layer(self, layer: MutationLayer, llm_client=None) -> List[LayeredMutator]:
        """Get all mutator instances for a specific layer."""
        instances = []
        for name in self._layer_mutators[layer]:
            if self._mutators[name].enabled:
                mutator = self.get_mutator(name, llm_client=llm_client)
                if mutator:
                    instances.append(mutator)
        return instances
    
    def get_strategy_mutator(self, strategy: str) -> Optional[str]:
        """Get the mutator name that provides a specific strategy."""
        return self._strategy_map.get(strategy)
    
    def resolve_dependencies(self, mutator_names: List[str]) -> List[str]:
        """
        Resolve dependencies and return ordered list of mutators.
        
        Args:
            mutator_names: List of requested mutator names
            
        Returns:
            Ordered list with dependencies resolved
        """
        resolved = []
        visited = set()
        
        def visit(name: str):
            if name in visited:
                return
            visited.add(name)
            
            if name not in self._mutators:
                logger.warning(f"Unknown mutator: {name}")
                return
            
            info = self._mutators[name]
            
            # Visit dependencies first
            for dep in info.dependencies:
                visit(dep)
            
            if info.enabled:
                resolved.append(name)
        
        for name in mutator_names:
            visit(name)
        
        return resolved
    
    def check_conflicts(self, mutator_names: List[str]) -> List[Tuple[str, str]]:
        """
        Check for conflicts between mutators.
        
        Args:
            mutator_names: List of mutator names to check
            
        Returns:
            List of conflicting pairs
        """
        conflicts = []
        
        for i, name1 in enumerate(mutator_names):
            if name1 not in self._mutators:
                continue
                
            info1 = self._mutators[name1]
            
            for name2 in mutator_names[i+1:]:
                if name2 in info1.conflicts:
                    conflicts.append((name1, name2))
        
        return conflicts
    
    def update_metrics(self, mutator_name: str, result: MutationResult, 
                      execution_time: float, energy_improvement: Optional[float] = None):
        """Update performance metrics for a mutator."""
        if mutator_name not in self._mutators:
            return
        
        metrics = self._mutators[mutator_name].metrics
        metrics.total_attempts += 1
        
        if result.ir is not None:
            metrics.successful_mutations += 1
            metrics.avg_confidence = (
                (metrics.avg_confidence * (metrics.successful_mutations - 1) + result.confidence) 
                / metrics.successful_mutations
            )
            
            if energy_improvement is not None:
                metrics.energy_improvements.append(energy_improvement)
        
        metrics.avg_execution_time = (
            (metrics.avg_execution_time * (metrics.total_attempts - 1) + execution_time)
            / metrics.total_attempts
        )
    
    def get_adaptive_selection(self, layer: MutationLayer, max_mutators: int = 3) -> List[str]:
        """
        Select mutators adaptively based on performance metrics.
        
        Args:
            layer: The mutation layer
            max_mutators: Maximum number of mutators to select
            
        Returns:
            List of selected mutator names
        """
        candidates = self.get_layer_mutators(layer)
        
        if len(candidates) <= max_mutators:
            return candidates
        
        # Score mutators based on success rate and energy improvement
        scored = []
        for name in candidates:
            metrics = self._mutators[name].metrics
            
            # Combine success rate and energy improvement
            score = (
                metrics.success_rate * 0.6 + 
                min(1.0, metrics.avg_energy_improvement / 50.0) * 0.4
            )
            
            scored.append((score, name))
        
        # Sort by score and take top performers
        scored.sort(reverse=True)
        return [name for _, name in scored[:max_mutators]]
    
    def list_all_mutators(self) -> Dict[str, MutatorInfo]:
        """Get all registered mutators."""
        return self._mutators.copy()
    
    def enable_mutator(self, name: str) -> bool:
        """Enable a mutator."""
        if name in self._mutators:
            self._mutators[name].enabled = True
            return True
        return False
    
    def disable_mutator(self, name: str) -> bool:
        """Disable a mutator."""
        if name in self._mutators:
            self._mutators[name].enabled = False
            return True
        return False
    
    def get_statistics(self) -> Dict[str, Dict]:
        """Get performance statistics for all mutators."""
        stats = {}
        
        for name, info in self._mutators.items():
            stats[name] = {
                'layer': info.layer.value,
                'strategies': len(info.strategies),
                'enabled': info.enabled,
                'success_rate': info.metrics.success_rate,
                'avg_confidence': info.metrics.avg_confidence,
                'avg_energy_improvement': info.metrics.avg_energy_improvement,
                'total_attempts': info.metrics.total_attempts
            }
        
        return stats


# Global registry instance
_registry = MutatorRegistry()


def get_registry() -> MutatorRegistry:
    """Get the global mutator registry."""
    return _registry


def register_mutator(name: str, mutator_class: Type[LayeredMutator], 
                    dependencies: Optional[Set[str]] = None,
                    conflicts: Optional[Set[str]] = None) -> None:
    """Register a mutator with the global registry."""
    _registry.register_mutator(name, mutator_class, dependencies, conflicts)


def auto_discover_mutators():
    """Automatically discover and register all mutators."""
    # Import all mutator modules to trigger registration
    from src.application.mutators import (
        semantic_layer, algorithmic_layer, syntactic_layer, micro_layer
    )
    
    # Register semantic layer mutators
    register_mutator("AlgorithmicIntentMutator", semantic_layer.AlgorithmicIntentMutator)
    register_mutator("ProgramIntentMutator", semantic_layer.ProgramIntentMutator)
    
    # Register algorithmic layer mutators
    register_mutator("DataStructureOptimizer", algorithmic_layer.DataStructureOptimizer)
    register_mutator("ComplexityReducer", algorithmic_layer.ComplexityReducer)
    
    # Register syntactic layer mutators
    register_mutator("PythonicIdiomOptimizer", syntactic_layer.PythonicIdiomOptimizer)
    register_mutator("CodePatternOptimizer", syntactic_layer.CodePatternOptimizer)
    
    # Register micro layer mutators
    register_mutator("ConstantOptimizer", micro_layer.ConstantOptimizer)
    register_mutator("DeadCodeEliminator", micro_layer.DeadCodeEliminator)
    register_mutator("LoopMicroOptimizer", micro_layer.LoopMicroOptimizer)
    
    logger.info("Auto-discovery completed: registered 9 mutators")