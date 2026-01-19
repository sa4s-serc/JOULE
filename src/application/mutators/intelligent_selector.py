"""
Intelligent Mutation Selection System - ML-Driven Optimization

This module provides machine learning-driven mutation selection:
- Performance history analysis and prediction
- Code pattern recognition for optimal mutator selection
- Adaptive learning from optimization outcomes
- Multi-objective optimization with preference learning
"""
import logging
import json
import pickle
import time
import numpy as np
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict, deque
import hashlib

from src.application.mutators.base import MutationLayer, LayeredMutator
from src.application.mutators.registry import get_registry
from src.domain.ir import schema
from src.domain.ir.metrics import IRMetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class MutationOutcome:
    """Record of a mutation attempt and its outcome."""
    mutator_name: str
    strategy_name: str
    layer: MutationLayer
    code_features: Dict[str, float]
    success: bool
    improvement_ratio: float  # Positive = improvement, negative = degradation
    execution_time: float
    energy_improvement: float
    complexity_change: float
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'mutator_name': self.mutator_name,
            'strategy_name': self.strategy_name,
            'layer': self.layer.value,
            'code_features': self.code_features,
            'success': self.success,
            'improvement_ratio': self.improvement_ratio,
            'execution_time': self.execution_time,
            'energy_improvement': self.energy_improvement,
            'complexity_change': self.complexity_change,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MutationOutcome':
        """Create from dictionary."""
        return cls(
            mutator_name=data['mutator_name'],
            strategy_name=data['strategy_name'],
            layer=MutationLayer(data['layer']),
            code_features=data['code_features'],
            success=data['success'],
            improvement_ratio=data['improvement_ratio'],
            execution_time=data['execution_time'],
            energy_improvement=data['energy_improvement'],
            complexity_change=data['complexity_change'],
            timestamp=data['timestamp']
        )


@dataclass
class CodeFeatures:
    """Extracted features from code for ML prediction."""
    cyclomatic_complexity: float = 0.0
    nesting_depth: int = 0
    num_loops: int = 0
    num_functions: int = 0
    num_conditionals: int = 0
    num_variables: int = 0
    has_recursion: bool = False
    has_nested_loops: bool = False
    has_list_comprehensions: bool = False
    has_generators: bool = False
    avg_function_length: float = 0.0
    code_size: int = 0
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to feature vector."""
        return {
            'cyclomatic_complexity': self.cyclomatic_complexity,
            'nesting_depth': float(self.nesting_depth),
            'num_loops': float(self.num_loops),
            'num_functions': float(self.num_functions),
            'num_conditionals': float(self.num_conditionals),
            'num_variables': float(self.num_variables),
            'has_recursion': float(self.has_recursion),
            'has_nested_loops': float(self.has_nested_loops),
            'has_list_comprehensions': float(self.has_list_comprehensions),
            'has_generators': float(self.has_generators),
            'avg_function_length': self.avg_function_length,
            'code_size': float(self.code_size)
        }


class CodeFeatureExtractor:
    """Extracts features from IR for ML prediction."""
    
    def __init__(self):
        self.metrics_collector = IRMetricsCollector()
    
    def extract_features(self, ir: schema.Module) -> CodeFeatures:
        """Extract features from IR module."""
        features = CodeFeatures()
        
        # Basic metrics
        metrics = self.metrics_collector.collect(ir)
        features.cyclomatic_complexity = float(metrics.cyclomatic_complexity)
        features.nesting_depth = metrics.max_depth
        features.code_size = metrics.total_nodes
        
        # Count specific constructs
        counter = ConstructCounter()
        counter.visit(ir)
        
        features.num_loops = counter.num_loops
        features.num_functions = counter.num_functions
        features.num_conditionals = counter.num_conditionals
        features.num_variables = counter.num_variables
        features.has_recursion = counter.has_recursion
        features.has_nested_loops = counter.has_nested_loops
        features.has_list_comprehensions = counter.has_list_comprehensions
        features.has_generators = counter.has_generators
        
        # Calculate average function length
        if counter.num_functions > 0:
            features.avg_function_length = counter.total_function_length / counter.num_functions
        
        return features


class ConstructCounter:
    """Counts various code constructs in IR."""
    
    def __init__(self):
        self.num_loops = 0
        self.num_functions = 0
        self.num_conditionals = 0
        self.num_variables = 0
        self.has_recursion = False
        self.has_nested_loops = False
        self.has_list_comprehensions = False
        self.has_generators = False
        self.total_function_length = 0
        self.current_function = None
        self.loop_depth = 0
    
    def visit(self, node: schema.IRNode):
        """Visit IR node and count constructs."""
        method_name = f'visit_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        visitor(node)
    
    def generic_visit(self, node: schema.IRNode):
        """Generic visitor for all nodes."""
        for field_name, field_value in node.__dict__.items():
            if isinstance(field_value, schema.IRNode):
                self.visit(field_value)
            elif isinstance(field_value, list):
                for item in field_value:
                    if isinstance(item, schema.IRNode):
                        self.visit(item)
    
    def visit_FunctionDef(self, node: schema.FunctionDef):
        """Visit function definition."""
        self.num_functions += 1
        old_function = self.current_function
        self.current_function = node.name
        
        # Count function length
        if isinstance(node.body, schema.Block):
            self.total_function_length += len(node.body.statements)
        
        self.generic_visit(node)
        self.current_function = old_function
    
    def visit_For(self, node: schema.For):
        """Visit for loop."""
        self.num_loops += 1
        old_depth = self.loop_depth
        self.loop_depth += 1
        
        if self.loop_depth > 1:
            self.has_nested_loops = True
        
        self.generic_visit(node)
        self.loop_depth = old_depth
    
    def visit_While(self, node: schema.While):
        """Visit while loop."""
        self.num_loops += 1
        old_depth = self.loop_depth
        self.loop_depth += 1
        
        if self.loop_depth > 1:
            self.has_nested_loops = True
        
        self.generic_visit(node)
        self.loop_depth = old_depth
    
    def visit_If(self, node: schema.If):
        """Visit if statement."""
        self.num_conditionals += 1
        self.generic_visit(node)
    
    def visit_Assign(self, node: schema.Assign):
        """Visit assignment."""
        self.num_variables += len(node.targets)
        self.generic_visit(node)
    
    def visit_Call(self, node: schema.Call):
        """Visit function call."""
        if isinstance(node.func, schema.Name):
            if node.func.id == self.current_function:
                self.has_recursion = True
        self.generic_visit(node)
    
    def visit_ListComp(self, node: schema.ListComp):
        """Visit list comprehension."""
        self.has_list_comprehensions = True
        self.generic_visit(node)
    
    def visit_GeneratorExp(self, node: schema.GeneratorExp):
        """Visit generator expression."""
        self.has_generators = True
        self.generic_visit(node)


class MutationPredictor:
    """Predicts mutation success using simple ML models."""
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.outcomes: deque = deque(maxlen=history_size)
        self.mutator_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            'success_rate': 0.5,
            'avg_improvement': 0.0,
            'total_attempts': 0,
            'successful_attempts': 0
        })
        self.feature_weights: Dict[str, Dict[str, float]] = defaultdict(dict)
    
    def record_outcome(self, outcome: MutationOutcome):
        """Record a mutation outcome for learning."""
        self.outcomes.append(outcome)
        
        # Update mutator statistics
        key = f"{outcome.mutator_name}:{outcome.strategy_name}"
        stats = self.mutator_stats[key]
        stats['total_attempts'] += 1
        
        if outcome.success:
            stats['successful_attempts'] += 1
            stats['avg_improvement'] = (
                stats['avg_improvement'] * (stats['successful_attempts'] - 1) + 
                outcome.improvement_ratio
            ) / stats['successful_attempts']
        
        stats['success_rate'] = stats['successful_attempts'] / stats['total_attempts']
        
        # Update feature weights (simplified learning)
        self._update_feature_weights(outcome)
    
    def _update_feature_weights(self, outcome: MutationOutcome):
        """Update feature weights based on outcome."""
        key = f"{outcome.mutator_name}:{outcome.strategy_name}"
        
        if key not in self.feature_weights:
            self.feature_weights[key] = {feature: 0.0 for feature in outcome.code_features.keys()}
        
        # Simple weight update based on success
        learning_rate = 0.01
        reward = outcome.improvement_ratio if outcome.success else -0.1
        
        for feature, value in outcome.code_features.items():
            if value > 0:  # Only update for present features
                self.feature_weights[key][feature] += learning_rate * reward * value
    
    def predict_success_probability(
        self, 
        mutator_name: str, 
        strategy_name: str, 
        code_features: Dict[str, float]
    ) -> float:
        """Predict probability of successful mutation."""
        key = f"{mutator_name}:{strategy_name}"
        
        # Base probability from historical success rate
        base_prob = self.mutator_stats[key]['success_rate']
        
        # Adjust based on code features
        if key in self.feature_weights:
            feature_score = sum(
                self.feature_weights[key].get(feature, 0.0) * value
                for feature, value in code_features.items()
            )
            # Sigmoid activation to keep probability in [0, 1]
            adjustment = 1 / (1 + np.exp(-feature_score))
            return 0.5 * base_prob + 0.5 * adjustment
        
        return base_prob
    
    def predict_improvement(
        self, 
        mutator_name: str, 
        strategy_name: str, 
        code_features: Dict[str, float]
    ) -> float:
        """Predict expected improvement from mutation."""
        key = f"{mutator_name}:{strategy_name}"
        
        # Base improvement from historical average
        base_improvement = self.mutator_stats[key]['avg_improvement']
        
        # Adjust based on success probability
        success_prob = self.predict_success_probability(mutator_name, strategy_name, code_features)
        
        return base_improvement * success_prob
    
    def get_top_mutators(
        self, 
        code_features: Dict[str, float], 
        layer: Optional[MutationLayer] = None,
        top_k: int = 5
    ) -> List[Tuple[str, str, float]]:
        """Get top mutators for given code features."""
        registry = get_registry()
        candidates = []
        
        # Get all available mutators
        if layer:
            mutators = registry.get_mutators_for_layer(layer, llm_client=None)
        else:
            mutators = []
            for l in MutationLayer:
                mutators.extend(registry.get_mutators_for_layer(l, llm_client=None))
        
        # Score each mutator strategy
        for mutator in mutators:
            mutator_name = mutator.__class__.__name__
            strategies = mutator.get_available_strategies()
            
            for strategy in strategies:
                score = self.predict_improvement(mutator_name, strategy, code_features)
                candidates.append((mutator_name, strategy, score))
        
        # Sort by score and return top k
        candidates.sort(key=lambda x: x[2], reverse=True)
        return candidates[:top_k]


class IntelligentMutationSelector:
    """
    Intelligent mutation selector using ML-driven optimization.
    
    Features:
    - Performance history analysis and prediction
    - Code pattern recognition for optimal mutator selection
    - Adaptive learning from optimization outcomes
    - Multi-objective optimization with preference learning
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(".hedge_cache")
        self.data_dir.mkdir(exist_ok=True)
        
        self.feature_extractor = CodeFeatureExtractor()
        self.predictor = MutationPredictor()
        self.registry = get_registry()
        
        # Load historical data
        self._load_history()
    
    def select_mutators(
        self, 
        ir: schema.Module, 
        enabled_layers: Optional[Set[MutationLayer]] = None,
        max_mutators: int = 10,
        llm_client=None
    ) -> List[Tuple[LayeredMutator, str, float]]:
        """
        Select optimal mutators for given IR.
        
        Args:
            ir: Input IR module
            enabled_layers: Set of enabled layers
            max_mutators: Maximum number of mutators to select
            
        Returns:
            List of (mutator, strategy, confidence_score) tuples
        """
        # Extract code features
        features = self.feature_extractor.extract_features(ir)
        feature_dict = features.to_dict()
        
        # Get top mutator strategies
        selected_mutators = []
        
        if enabled_layers:
            for layer in enabled_layers:
                top_strategies = self.predictor.get_top_mutators(
                    feature_dict, layer, max_mutators // len(enabled_layers)
                )
                
                for mutator_name, strategy_name, score in top_strategies:
                    mutator = self._get_mutator_by_name(mutator_name, layer, llm_client=llm_client)
                    if mutator:
                        selected_mutators.append((mutator, strategy_name, score))
        else:
            top_strategies = self.predictor.get_top_mutators(
                feature_dict, None, max_mutators
            )
            
            for mutator_name, strategy_name, score in top_strategies:
                # Find the mutator in registry
                for layer in MutationLayer:
                    mutator = self._get_mutator_by_name(mutator_name, layer, llm_client=llm_client)
                    if mutator:
                        selected_mutators.append((mutator, strategy_name, score))
                        break
        
        # Sort by confidence score
        selected_mutators.sort(key=lambda x: x[2], reverse=True)
        
        logger.info(f"Selected {len(selected_mutators)} mutators based on code analysis")
        for mutator, strategy, score in selected_mutators[:5]:
            logger.debug(f"  {mutator.__class__.__name__}:{strategy} (score: {score:.3f})")
        
        return selected_mutators[:max_mutators]
    
    def _get_mutator_by_name(self, mutator_name: str, layer: MutationLayer, llm_client=None) -> Optional[LayeredMutator]:
        """Get mutator instance by name and layer."""
        mutators = self.registry.get_mutators_for_layer(layer, llm_client=llm_client)
        for mutator in mutators:
            if mutator.__class__.__name__ == mutator_name:
                return mutator
        return None
    
    def record_mutation_outcome(
        self,
        ir: schema.Module,
        mutator: LayeredMutator,
        strategy_name: str,
        success: bool,
        improvement_ratio: float,
        execution_time: float = 0.0,
        energy_improvement: float = 0.0,
        complexity_change: float = 0.0
    ):
        """Record the outcome of a mutation for learning."""
        features = self.feature_extractor.extract_features(ir)
        
        outcome = MutationOutcome(
            mutator_name=mutator.__class__.__name__,
            strategy_name=strategy_name,
            layer=mutator.layer,
            code_features=features.to_dict(),
            success=success,
            improvement_ratio=improvement_ratio,
            execution_time=execution_time,
            energy_improvement=energy_improvement,
            complexity_change=complexity_change,
            timestamp=time.time()
        )
        
        self.predictor.record_outcome(outcome)
        
        # Periodically save history
        if len(self.predictor.outcomes) % 50 == 0:
            self._save_history()
    
    def _save_history(self):
        """Save learning history to disk."""
        try:
            history_file = self.data_dir / "mutation_history.json"
            
            # Convert outcomes to serializable format
            outcomes_data = [outcome.to_dict() for outcome in self.predictor.outcomes]
            
            data = {
                'outcomes': outcomes_data,
                'mutator_stats': dict(self.predictor.mutator_stats),
                'feature_weights': dict(self.predictor.feature_weights)
            }
            
            with open(history_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.debug(f"Saved mutation history to {history_file}")
            
        except Exception as e:
            logger.warning(f"Failed to save mutation history: {e}")
    
    def _load_history(self):
        """Load learning history from disk."""
        try:
            history_file = self.data_dir / "mutation_history.json"
            
            if history_file.exists():
                with open(history_file, 'r') as f:
                    data = json.load(f)
                
                # Restore outcomes
                for outcome_data in data.get('outcomes', []):
                    outcome = MutationOutcome.from_dict(outcome_data)
                    self.predictor.outcomes.append(outcome)
                
                # Restore statistics
                self.predictor.mutator_stats.update(data.get('mutator_stats', {}))
                self.predictor.feature_weights.update(data.get('feature_weights', {}))
                
                logger.info(f"Loaded {len(self.predictor.outcomes)} historical outcomes")
            
        except Exception as e:
            logger.warning(f"Failed to load mutation history: {e}")
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get learning statistics."""
        return {
            'total_outcomes': len(self.predictor.outcomes),
            'mutator_count': len(self.predictor.mutator_stats),
            'top_mutators': sorted(
                [(k, v['success_rate'], v['avg_improvement']) 
                 for k, v in self.predictor.mutator_stats.items()],
                key=lambda x: x[2], reverse=True
            )[:10],
            'feature_importance': self._calculate_feature_importance()
        }
    
    def _calculate_feature_importance(self) -> Dict[str, float]:
        """Calculate feature importance across all mutators."""
        feature_importance = defaultdict(float)
        
        for mutator_weights in self.predictor.feature_weights.values():
            for feature, weight in mutator_weights.items():
                feature_importance[feature] += abs(weight)
        
        # Normalize
        total_weight = sum(feature_importance.values())
        if total_weight > 0:
            feature_importance = {
                k: v / total_weight for k, v in feature_importance.items()
            }
        
        return dict(sorted(feature_importance.items(), key=lambda x: x[1], reverse=True))


# Global selector instance
_global_selector = None

def get_intelligent_selector() -> IntelligentMutationSelector:
    """Get global intelligent mutation selector."""
    global _global_selector
    if _global_selector is None:
        _global_selector = IntelligentMutationSelector()
    return _global_selector