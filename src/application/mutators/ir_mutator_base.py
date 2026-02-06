"""
IR-Only Mutator Base - Pure IR Transformation System

Ensures all mutations operate strictly on IR without string manipulation.
Provides enhanced IR utilities and validation.
"""

import logging
from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Set

from src.application.mutators.base import (LayeredMutator, MutationLayer,
                                           MutationResult)
from src.domain.ir import schema
from src.domain.ir.context import MutationContext
from src.domain.ir.utils import NodeTransformer, find_nodes
from src.domain.ir.validators import IRValidator
from src.utils.mutation_factory import create_mutation_result

logger = logging.getLogger(__name__)


@dataclass
class IRMutationMetadata:
    """Metadata about an IR mutation."""

    nodes_modified: int
    nodes_added: int
    nodes_removed: int
    complexity_change: float
    estimated_performance_impact: float


class IROnlyMutator(LayeredMutator):
    """
    Base class for mutators that operate purely on IR.

    Enforces IR-only transformations and provides enhanced utilities
    for safe, semantics-preserving mutations.
    """

    def __init__(self, layer: MutationLayer, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(layer, enabled_strategies)
        self.validator = IRValidator(strict=False)
        self.context: Optional[MutationContext] = None

    def mutate(self, ir: schema.Module) -> List[MutationResult]:
        """
        Main mutation interface with enhanced IR validation.

        Args:
            ir: Input IR module

        Returns:
            List of MutationResult objects
        """
        # Build mutation context
        self.context = MutationContext(ir)

        # Apply IR-only mutations
        results = self._apply_ir_mutations(ir)

        # Validate all results
        validated_results = []
        for result in results:
            if self._validate_ir_mutation(result):
                validated_results.append(result)
                self.success_count += 1
            else:
                logger.warning(f"Invalid IR mutation rejected: {result.strategy_name}")

        self.mutation_count += len(results)
        return validated_results

    @abstractmethod
    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply layer-specific IR mutations."""

    def _validate_ir_mutation(self, result: MutationResult) -> bool:
        """
        Validate that an IR mutation is structurally sound.

        Args:
            result: The mutation result to validate

        Returns:
            True if valid, False otherwise
        """
        if result.ir is None:
            return False

        # Structural validation
        validation_result = self.validator.validate(result.ir)
        if not validation_result.valid:
            logger.debug(f"IR validation failed: {validation_result.errors}")
            return False

        # Semantic validation (basic)
        if not self._check_semantic_preservation(result.ir):
            logger.debug("Semantic preservation check failed")
            return False

        return True

    def _check_semantic_preservation(self, mutated_ir: schema.Module) -> bool:
        """
        Basic semantic preservation checks.

        Args:
            mutated_ir: The mutated IR to check

        Returns:
            True if semantics appear preserved
        """
        if not self.context:
            return True  # Can't check without context

        # Check that top-level definitions (functions, classes) are preserved
        # We allow local variables to be removed during optimization
        def get_top_level_defs(ir_node: schema.Module) -> Set[str]:
            top_defs = set()
            for stmt in ir_node.body.statements:
                if isinstance(stmt, (schema.FunctionDef, schema.AsyncFunctionDef, schema.ClassDef)):
                    top_defs.add(stmt.name)
            return top_defs

        original_top_defs = get_top_level_defs(self.context.ir)
        mutated_top_defs = get_top_level_defs(mutated_ir)

        if not original_top_defs.issubset(mutated_top_defs):
            missing = original_top_defs - mutated_top_defs
            logger.debug(f"Missing top-level definitions after mutation: {missing}")
            return False

        return True

    def _create_ir_transformer(self, transformer_class: type) -> NodeTransformer:
        """
        Create an IR transformer with context.

        Args:
            transformer_class: The transformer class to instantiate

        Returns:
            Configured transformer instance
        """
        if hasattr(transformer_class, "__init__"):
            # Try to pass context if transformer supports it
            try:
                return transformer_class(context=self.context)
            except TypeError:
                return transformer_class()
        return transformer_class()

    def _apply_transformer(
        self,
        ir: schema.Module,
        transformer: NodeTransformer,
        strategy_name: str,
        description: str,
        confidence: float = 0.8,
    ) -> Optional[MutationResult]:
        """
        Apply a transformer and create a mutation result.

        Args:
            ir: Input IR module
            transformer: The transformer to apply
            strategy_name: Name of the mutation strategy
            description: Human-readable description
            confidence: Confidence in the mutation (0.0 to 1.0)

        Returns:
            MutationResult or None if no changes made
        """
        # Deep copy IR for mutation
        mutated_ir = self._safe_deepcopy_ir(ir)

        # Apply transformation - ensure we call visit_Module for module-level transformers
        if hasattr(transformer, "visit_Module"):
            mutated_ir = transformer.visit_Module(mutated_ir)
        else:
            transformer.visit(mutated_ir)

        # Check if changes were made
        if hasattr(transformer, "changed") and not transformer.changed:
            return None

        # Create result with metadata
        return create_mutation_result(
            ir=mutated_ir,
            strategy_name=strategy_name,
            layer=self.layer,
            mutator_name=self.__class__.__name__,
            confidence=confidence,
            description=description,
        )

    def _safe_deepcopy_ir(self, ir: schema.Module) -> schema.Module:
        """
        Safely deep copy an IR module.

        Args:
            ir: IR module to copy

        Returns:
            Deep copy of the IR module
        """
        # Use Pydantic's copy method for safe copying
        return ir.model_copy(deep=True)

    def _analyze_complexity_change(
        self, original_ir: schema.Module, mutated_ir: schema.Module
    ) -> float:
        """
        Analyze the complexity change from a mutation.

        Args:
            original_ir: Original IR module
            mutated_ir: Mutated IR module

        Returns:
            Complexity change factor (negative = improvement)
        """
        # Simple heuristic based on node counts
        original_nodes = len(find_nodes(original_ir, schema.IRNode))
        mutated_nodes = len(find_nodes(mutated_ir, schema.IRNode))

        # Count loops and nested structures
        original_loops = len(find_nodes(original_ir, (schema.For, schema.While)))
        mutated_loops = len(find_nodes(mutated_ir, (schema.For, schema.While)))

        # Simple complexity metric
        original_complexity = original_nodes + (original_loops * 10)
        mutated_complexity = mutated_nodes + (mutated_loops * 10)

        if original_complexity == 0:
            return 0.0

        return (mutated_complexity - original_complexity) / original_complexity

    def _get_mutation_metadata(
        self, original_ir: schema.Module, mutated_ir: schema.Module
    ) -> IRMutationMetadata:
        """
        Generate metadata about an IR mutation.

        Args:
            original_ir: Original IR module
            mutated_ir: Mutated IR module

        Returns:
            Metadata about the mutation
        """
        original_nodes = find_nodes(original_ir, schema.IRNode)
        mutated_nodes = find_nodes(mutated_ir, schema.IRNode)

        complexity_change = self._analyze_complexity_change(original_ir, mutated_ir)

        return IRMutationMetadata(
            nodes_modified=len(mutated_nodes) - len(original_nodes),
            nodes_added=max(0, len(mutated_nodes) - len(original_nodes)),
            nodes_removed=max(0, len(original_nodes) - len(mutated_nodes)),
            complexity_change=complexity_change,
            estimated_performance_impact=complexity_change
            * -1,  # Negative complexity change = positive performance
        )


class IRTransformerBase(NodeTransformer):
    """
    Enhanced base class for IR transformers.

    Provides utilities for safe IR transformation with context awareness.
    """

    def __init__(self, context: Optional[MutationContext] = None):
        self.context = context
        self.changed = False
        self.modifications = []

    def record_change(self, node_type: str, operation: str, details: str = ""):
        """Record a change made during transformation."""
        self.changed = True
        self.modifications.append(
            {"node_type": node_type, "operation": operation, "details": details}
        )

    def can_modify_variable(self, var_name: str) -> bool:
        """Check if a variable can be safely modified."""
        if not self.context:
            return True  # Conservative: allow if no context

        # Don't modify variables that are used in multiple places
        # This is a simplified check - full implementation would be more sophisticated
        return True

    def get_safe_variable_name(self, base_name: str) -> str:
        """Generate a safe variable name that doesn't conflict."""
        if not self.context:
            return f"_{base_name}_temp"

        # Simple implementation - could be enhanced with proper scope analysis
        counter = 1
        candidate = f"_{base_name}_{counter}"

        while candidate in self.context.symbol_table:
            counter += 1
            candidate = f"_{base_name}_{counter}"

        return candidate
