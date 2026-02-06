"""
Transformer Base Template

Provides a common template for IR transformers to eliminate duplication
across algorithmic and syntactic layer transformers. Handles common patterns
like change tracking, metadata recording, and generic visit patterns.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

from src.domain.ir import schema
from src.utils.constants import ConfidenceScores

logger = logging.getLogger(__name__)


class TransformerTemplate(ABC):
    """
    Base template for IR transformers with common patterns.

    Provides:
    - Automatic change tracking
    - Metadata recording
    - Generic visit patterns
    - Consistent error handling
    - Performance metrics
    """

    def __init__(self, confidence: float = ConfidenceScores.ALGORITHMIC_IMPROVEMENT):
        self.changed = False
        self.changes_made: List[str] = []
        self.confidence = confidence
        self.visit_count = 0
        self.transformation_count = 0

    def transform(self, ir: schema.Module) -> Optional[schema.Module]:
        """
        Main transformation entry point.

        Args:
            ir: IR module to transform

        Returns:
            Transformed IR if changes were made, None otherwise
        """
        self._reset_state()

        try:
            transformed_ir = self._apply_transformations(ir)

            if self.changed:
                logger.debug(
                    f"{self.__class__.__name__} made {self.transformation_count} "
                    f"transformations: {', '.join(self.changes_made)}"
                )
                return transformed_ir
            else:
                logger.debug(f"{self.__class__.__name__} made no changes")
                return None

        except Exception as e:
            logger.error(f"Transformation failed in {self.__class__.__name__}: {e}")
            return None

    def _reset_state(self) -> None:
        """Reset transformer state for new transformation."""
        self.changed = False
        self.changes_made.clear()
        self.visit_count = 0
        self.transformation_count = 0

    @abstractmethod
    def _apply_transformations(self, ir: schema.Module) -> schema.Module:
        """
        Apply specific transformations to the IR.

        Subclasses must implement this method to define their transformations.
        Use _record_change() to track modifications.

        Args:
            ir: IR module to transform

        Returns:
            Transformed IR module
        """

    def _record_change(self, description: str) -> None:
        """
        Record that a change was made.

        Args:
            description: Description of the change made
        """
        self.changed = True
        self.changes_made.append(description)
        self.transformation_count += 1

    def _visit_node(self, node: schema.IRNode) -> schema.IRNode:
        """
        Generic node visitor with automatic counting.

        Args:
            node: Node to visit

        Returns:
            Potentially transformed node
        """
        self.visit_count += 1

        # Dispatch to specific visitor method if it exists
        method_name = f"_visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, None)

        if visitor:
            return visitor(node)
        else:
            return self._visit_generic(node)

    def _visit_generic(self, node: schema.IRNode) -> schema.IRNode:
        """
        Generic visitor for nodes without specific handlers.

        Args:
            node: Node to visit

        Returns:
            Unmodified node (subclasses can override for generic transformations)
        """
        return node

    def _should_transform_node(self, node: schema.IRNode) -> bool:
        """
        Check if a node should be transformed.

        Subclasses can override this for common filtering logic.

        Args:
            node: Node to check

        Returns:
            True if node should be transformed
        """
        return True

    def _create_replacement_node(
        self, original: schema.IRNode, node_type: Type[schema.IRNode], **kwargs
    ) -> schema.IRNode:
        """
        Create a replacement node with preserved metadata.

        Args:
            original: Original node to replace
            node_type: Type of new node to create
            **kwargs: Arguments for new node constructor

        Returns:
            New node with preserved location metadata
        """
        # Preserve location information
        if hasattr(original, "lineno"):
            kwargs.setdefault("lineno", original.lineno)
        if hasattr(original, "col_offset"):
            kwargs.setdefault("col_offset", original.col_offset)
        if hasattr(original, "end_lineno"):
            kwargs.setdefault("end_lineno", original.end_lineno)
        if hasattr(original, "end_col_offset"):
            kwargs.setdefault("end_col_offset", original.end_col_offset)

        return node_type(**kwargs)

    def get_transformation_summary(self) -> Dict[str, Any]:
        """
        Get summary of transformations performed.

        Returns:
            Dictionary with transformation statistics
        """
        return {
            "transformer": self.__class__.__name__,
            "changed": self.changed,
            "transformation_count": self.transformation_count,
            "visit_count": self.visit_count,
            "changes_made": self.changes_made.copy(),
            "confidence": self.confidence,
        }


class LoopTransformerTemplate(TransformerTemplate):
    """
    Specialized template for loop-related transformations.

    Provides common patterns for loop optimization transformers.
    """

    def __init__(self, confidence: float = ConfidenceScores.LOOP_OPTIMIZATION):
        super().__init__(confidence)
        self.loops_processed = 0
        self.loops_optimized = 0

    def _apply_transformations(self, ir: schema.Module) -> schema.Module:
        """Apply loop transformations to the IR."""
        return self._transform_block(ir.body)

    def _transform_block(self, block: schema.Block) -> schema.Block:
        """Transform statements in a block, looking for loops."""
        new_statements = []

        for stmt in block.statements:
            if isinstance(stmt, (schema.For, schema.While)):
                self.loops_processed += 1
                transformed_loop = self._transform_loop(stmt)
                if transformed_loop != stmt:
                    self.loops_optimized += 1
                    self._record_change(f"Optimized {stmt.__class__.__name__} loop")
                new_statements.append(transformed_loop)
            else:
                new_statements.append(self._transform_statement(stmt))

        return schema.Block(statements=new_statements)

    @abstractmethod
    def _transform_loop(self, loop: schema.IRNode) -> schema.IRNode:
        """
        Transform a loop node.

        Args:
            loop: Loop node (For or While)

        Returns:
            Transformed loop node
        """

    def _transform_statement(self, stmt: schema.Statement) -> schema.Statement:
        """
        Transform a non-loop statement.

        Default implementation recursively processes nested blocks.

        Args:
            stmt: Statement to transform

        Returns:
            Transformed statement
        """
        # Handle statements with nested blocks
        if hasattr(stmt, "body") and isinstance(stmt.body, schema.Block):
            new_body = self._transform_block(stmt.body)
            if new_body != stmt.body:
                return stmt.model_copy(update={"body": new_body})

        if hasattr(stmt, "orelse") and isinstance(stmt.orelse, schema.Block):
            new_orelse = self._transform_block(stmt.orelse)
            if new_orelse != stmt.orelse:
                return stmt.model_copy(update={"orelse": new_orelse})

        return stmt

    def get_transformation_summary(self) -> Dict[str, Any]:
        """Get loop-specific transformation summary."""
        summary = super().get_transformation_summary()
        summary.update(
            {
                "loops_processed": self.loops_processed,
                "loops_optimized": self.loops_optimized,
                "optimization_rate": (
                    self.loops_optimized / self.loops_processed if self.loops_processed > 0 else 0.0
                ),
            }
        )
        return summary


class ExpressionTransformerTemplate(TransformerTemplate):
    """
    Specialized template for expression-related transformations.

    Provides common patterns for expression optimization transformers.
    """

    def __init__(self, confidence: float = ConfidenceScores.CONSTANT_FOLDING):
        super().__init__(confidence)
        self.expressions_processed = 0
        self.expressions_optimized = 0

    def _apply_transformations(self, ir: schema.Module) -> schema.Module:
        """Apply expression transformations to the IR."""
        new_body = self._transform_block(ir.body)
        return ir.model_copy(update={"body": new_body})

    def _transform_block(self, block: schema.Block) -> schema.Block:
        """Transform expressions in a block."""
        new_statements = []

        for stmt in block.statements:
            new_statements.append(self._transform_statement(stmt))

        return schema.Block(statements=new_statements)

    def _transform_statement(self, stmt: schema.Statement) -> schema.Statement:
        """Transform expressions within a statement."""
        # This is a simplified implementation - real transformers would
        # need to handle all statement types that can contain expressions
        if hasattr(stmt, "value") and isinstance(stmt.value, schema.Expression):
            new_value = self._transform_expression(stmt.value)
            if new_value != stmt.value:
                return stmt.model_copy(update={"value": new_value})

        return stmt

    @abstractmethod
    def _transform_expression(self, expr: schema.Expression) -> schema.Expression:
        """
        Transform an expression.

        Args:
            expr: Expression to transform

        Returns:
            Transformed expression
        """

    def get_transformation_summary(self) -> Dict[str, Any]:
        """Get expression-specific transformation summary."""
        summary = super().get_transformation_summary()
        summary.update(
            {
                "expressions_processed": self.expressions_processed,
                "expressions_optimized": self.expressions_optimized,
                "optimization_rate": (
                    self.expressions_optimized / self.expressions_processed
                    if self.expressions_processed > 0
                    else 0.0
                ),
            }
        )
        return summary
