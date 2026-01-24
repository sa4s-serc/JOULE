"""
Crossover Operations for Genetic Programming

Implements various crossover strategies for combining IR solutions
to create new candidate solutions.
"""

import copy
import logging
import random
from typing import List, Optional, Tuple

from src.domain.ir import schema
from src.domain.ir.utils import NodeVisitor

logger = logging.getLogger(__name__)


class CrossoverOperator:
    """Base class for crossover operations."""

    def crossover(self, parent1: schema.Module, parent2: schema.Module) -> List[schema.Module]:
        """
        Perform crossover between two parent IRs.

        Args:
            parent1: First parent IR
            parent2: Second parent IR

        Returns:
            List of offspring IR modules
        """
        raise NotImplementedError


class SubtreeCrossover(CrossoverOperator):
    """
    Subtree crossover: Exchange random subtrees between parents.
    This is the classic GP crossover operation.
    """

    def crossover(self, parent1: schema.Module, parent2: schema.Module) -> List[schema.Module]:
        """Perform subtree crossover with type safety."""
        try:
            # Create deep copies
            offspring1 = copy.deepcopy(parent1)
            offspring2 = copy.deepcopy(parent2)

            # Find crossover points with type compatibility
            success = self._perform_safe_crossover(offspring1, offspring2)

            if success:
                return [offspring1, offspring2]
            else:
                # Fall back to uniform crossover if subtree crossover fails
                logger.debug("Subtree crossover failed, falling back to uniform crossover")
                uniform = UniformCrossover(mix_probability=0.5)
                return uniform.crossover(parent1, parent2)

        except Exception as e:
            logger.error(f"Subtree crossover failed: {e}")

        return []

    def _perform_safe_crossover(self, offspring1: schema.Module, offspring2: schema.Module) -> bool:
        """Perform crossover with type safety checks."""
        # Collect nodes by type
        expressions1 = self._collect_expressions(offspring1)
        expressions2 = self._collect_expressions(offspring2)
        statements1 = self._collect_statements(offspring1)
        statements2 = self._collect_statements(offspring2)

        # Try expression crossover first
        if len(expressions1) > 1 and len(expressions2) > 1:
            expr1 = random.choice(expressions1[1:])  # Skip root expressions
            expr2 = random.choice(expressions2[1:])

            parent_info1 = self._find_parent(offspring1, expr1)
            parent_info2 = self._find_parent(offspring2, expr2)

            if parent_info1 and parent_info2:
                self._swap_nodes(parent_info1, parent_info2, expr1, expr2)
                return True

        # Try statement crossover
        if len(statements1) > 1 and len(statements2) > 1:
            stmt1 = random.choice(statements1[1:])  # Skip root statements
            stmt2 = random.choice(statements2[1:])

            parent_info1 = self._find_parent(offspring1, stmt1)
            parent_info2 = self._find_parent(offspring2, stmt2)

            if parent_info1 and parent_info2:
                self._swap_nodes(parent_info1, parent_info2, stmt1, stmt2)
                return True

        return False

    def _collect_expressions(self, ir: schema.Module) -> List[schema.Expression]:
        """Collect all expression nodes."""
        collector = ExpressionCollector()
        collector.visit(ir)
        return collector.expressions

    def _collect_statements(self, ir: schema.Module) -> List[schema.Statement]:
        """Collect all statement nodes."""
        collector = StatementCollector()
        collector.visit(ir)
        return collector.statements

    def _collect_nodes(self, ir: schema.Module) -> List[schema.IRNode]:
        """Collect all nodes in the IR tree."""
        collector = NodeCollector()
        collector.visit(ir)
        return collector.nodes

    def _find_parent(
        self, root: schema.Module, target: schema.IRNode
    ) -> Optional[Tuple[schema.IRNode, str, int]]:
        """Find the parent of a target node."""
        finder = ParentFinder(target)
        finder.visit(root)
        return finder.parent_info

    def _swap_nodes(
        self, parent_info1: Tuple, parent_info2: Tuple, node1: schema.IRNode, node2: schema.IRNode
    ):
        """Swap two nodes in their respective trees with type checking."""
        parent1, field1, index1 = parent_info1
        parent2, field2, index2 = parent_info2

        # Check type compatibility before swapping
        if not self._are_compatible_types(node1, node2):
            logger.debug(
                f"Skipping crossover: incompatible types {type(node1).__name__} and {type(node2).__name__}"
            )
            return

        # Get the field values
        field_value1 = getattr(parent1, field1)
        field_value2 = getattr(parent2, field2)

        try:
            if isinstance(field_value1, list) and isinstance(field_value2, list):
                # Both are lists
                field_value1[index1] = node2
                field_value2[index2] = node1
            elif isinstance(field_value1, list):
                # First is list, second is single value
                field_value1[index1] = node2
                setattr(parent2, field2, node1)
            elif isinstance(field_value2, list):
                # First is single value, second is list
                setattr(parent1, field1, node2)
                field_value2[index2] = node1
            else:
                # Both are single values
                setattr(parent1, field1, node2)
                setattr(parent2, field2, node1)
        except Exception as e:
            logger.debug(f"Crossover swap failed: {e}")

    def _are_compatible_types(self, node1: schema.IRNode, node2: schema.IRNode) -> bool:
        """Check if two nodes are type-compatible for swapping."""
        # Same type is always compatible
        if type(node1) == type(node2):
            return True

        # Check if both are expressions
        if isinstance(node1, schema.Expression) and isinstance(node2, schema.Expression):
            return True

        # Check if both are statements
        if isinstance(node1, schema.Statement) and isinstance(node2, schema.Statement):
            return True

        # Check specific compatible types
        compatible_groups = [
            # Numeric expressions
            (schema.Constant, schema.Name, schema.BinaryOp, schema.UnaryOp),
            # Control flow statements
            (schema.If, schema.While, schema.For),
            # Assignment-like statements
            (schema.Assign, schema.AugAssign, schema.AnnAssign),
        ]

        for group in compatible_groups:
            if isinstance(node1, group) and isinstance(node2, group):
                return True

        return False


class UniformCrossover(CrossoverOperator):
    """
    Uniform crossover: Mix statements/expressions uniformly between parents.
    """

    def __init__(self, mix_probability: float = 0.5):
        self.mix_probability = mix_probability

    def crossover(self, parent1: schema.Module, parent2: schema.Module) -> List[schema.Module]:
        """Perform uniform crossover."""
        try:
            offspring1 = copy.deepcopy(parent1)
            offspring2 = copy.deepcopy(parent2)

            # Mix at the statement level
            self._mix_blocks(offspring1.body, offspring2.body)

            return [offspring1, offspring2]

        except Exception as e:
            logger.error(f"Uniform crossover failed: {e}")
            return []

    def _mix_blocks(self, block1: schema.Block, block2: schema.Block):
        """Mix statements between two blocks."""
        min_len = min(len(block1.statements), len(block2.statements))

        for i in range(min_len):
            if random.random() < self.mix_probability:
                # Swap statements
                block1.statements[i], block2.statements[i] = (
                    block2.statements[i],
                    block1.statements[i],
                )


class SemanticCrossover(CrossoverOperator):
    """
    Semantic crossover: Preserve program semantics while mixing code.
    More conservative than syntactic crossover.
    """

    def crossover(self, parent1: schema.Module, parent2: schema.Module) -> List[schema.Module]:
        """Perform semantic crossover."""
        try:
            # For now, implement a simple function-level crossover
            offspring1 = copy.deepcopy(parent1)
            offspring2 = copy.deepcopy(parent2)

            # Find functions in both parents
            funcs1 = self._extract_functions(offspring1)
            funcs2 = self._extract_functions(offspring2)

            # Mix functions with same names
            for name in funcs1.keys() & funcs2.keys():
                if random.random() < 0.5:
                    # Swap function implementations
                    self._replace_function(offspring1, name, funcs2[name])
                    self._replace_function(offspring2, name, funcs1[name])

            return [offspring1, offspring2]

        except Exception as e:
            logger.error(f"Semantic crossover failed: {e}")
            return []

    def _extract_functions(self, ir: schema.Module) -> dict:
        """Extract all function definitions."""
        functions = {}
        for stmt in ir.body.statements:
            if isinstance(stmt, schema.FunctionDef):
                functions[stmt.name] = stmt
        return functions

    def _replace_function(self, ir: schema.Module, name: str, new_func: schema.FunctionDef):
        """Replace a function in the IR."""
        for i, stmt in enumerate(ir.body.statements):
            if isinstance(stmt, schema.FunctionDef) and stmt.name == name:
                ir.body.statements[i] = new_func
                break


class NodeCollector(NodeVisitor):
    """Visitor that collects all nodes in an IR tree."""

    def __init__(self):
        self.nodes = []

    def visit(self, node: schema.IRNode):
        self.nodes.append(node)
        self.generic_visit(node)


class ExpressionCollector(NodeVisitor):
    """Visitor that collects all expression nodes."""

    def __init__(self):
        self.expressions = []

    def visit(self, node: schema.IRNode):
        if isinstance(node, schema.Expression):
            self.expressions.append(node)
        self.generic_visit(node)


class StatementCollector(NodeVisitor):
    """Visitor that collects all statement nodes."""

    def __init__(self):
        self.statements = []

    def visit(self, node: schema.IRNode):
        if isinstance(node, schema.Statement):
            self.statements.append(node)
        self.generic_visit(node)


class ParentFinder(NodeVisitor):
    """Visitor that finds the parent of a specific node."""

    def __init__(self, target: schema.IRNode):
        self.target = target
        self.parent_info = None

    def visit(self, node: schema.IRNode):
        if hasattr(node, "__dict__"):
            for field, value in node.__dict__.items():
                if isinstance(value, list):
                    for i, item in enumerate(value):
                        if item is self.target:
                            self.parent_info = (node, field, i)
                            return
                        elif isinstance(item, schema.IRNode):
                            self.visit(item)
                elif value is self.target:
                    self.parent_info = (node, field, None)
                    return
                elif isinstance(value, schema.IRNode):
                    self.visit(value)


class CrossoverManager:
    """Manages multiple crossover operators and selection."""

    def __init__(self):
        self.operators = [
            SubtreeCrossover(),
            UniformCrossover(mix_probability=0.3),
            UniformCrossover(mix_probability=0.7),
            SemanticCrossover(),
        ]

    def perform_crossover(
        self, parent1: schema.Module, parent2: schema.Module
    ) -> List[schema.Module]:
        """Perform crossover using a randomly selected operator."""
        operator = random.choice(self.operators)
        return operator.crossover(parent1, parent2)
