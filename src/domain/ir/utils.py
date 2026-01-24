"""
IR Traversal and Transformation Utilities.

This module provides the NodeVisitor and NodeTransformer base classes,
patterned after Python's ast module, to facilitate safe and easy
manipulation of the HEDGE IR.

Also provides utility functions for common traversal patterns.
"""

from typing import Any, Callable, List, Optional, Set, Type

from src.domain.ir import schema


class NodeVisitor:
    """
    A node visitor base class that walks the IR tree and calls a
    visitor function for every node found.

    This function may return a value which is forwarded by the `visit` method.

    Methods:
        visit(node): Visit a node.
        generic_visit(node): Called if no explicit visitor function exists for a node.
    """

    def visit(self, node: schema.IRNode) -> Any:
        """Visit a node."""
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: schema.IRNode) -> Any:
        """Called if no explicit visitor function exists for a node."""
        if hasattr(node, "__dict__"):
            for field, value in node.__dict__.items():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, schema.IRNode):
                            self.visit(item)
                elif isinstance(value, schema.IRNode):
                    self.visit(value)


class NodeTransformer(NodeVisitor):
    """
    A :class:`NodeVisitor` subclass that walks the IR tree and allows
    modification of nodes.

    The `visit` method returns the modified node (or None if the node should be deleted).
    """

    def generic_visit(self, node: schema.IRNode) -> Any:
        if hasattr(node, "__dict__"):
            for field, value in node.__dict__.items():
                if isinstance(value, list):
                    new_values = []
                    for item in value:
                        if isinstance(item, schema.IRNode):
                            new_node = self.visit(item)
                            if new_node is None:
                                continue
                            elif isinstance(new_node, list):
                                new_values.extend(new_node)
                            else:
                                new_values.append(new_node)
                        else:
                            new_values.append(item)
                    setattr(node, field, new_values)
                elif isinstance(value, schema.IRNode):
                    new_node = self.visit(value)
                    if new_node is None:
                        delattr(node, field)
                    else:
                        setattr(node, field, new_node)
        return node


# =============================================================================
# Utility Functions for Common Traversal Patterns
# =============================================================================


def find_nodes(node: schema.IRNode, node_type: Type[schema.IRNode]) -> List[schema.IRNode]:
    """
    Find all nodes of a specific type in the IR tree.

    Args:
        node: Root node to search from
        node_type: Type of nodes to find

    Returns:
        List of matching nodes

    Example:
        binops = find_nodes(ir, schema.BinaryOp)
    """
    collector = _NodeCollector(node_type)
    collector.visit(node)
    return collector.nodes


def find_all_nodes(node: schema.IRNode, node_types: tuple) -> List[schema.IRNode]:
    """
    Find all nodes matching any of the specified types.

    Args:
        node: Root node to search from
        node_types: Tuple of types to match

    Returns:
        List of matching nodes
    """
    collector = _MultiTypeCollector(node_types)
    collector.visit(node)
    return collector.nodes


def collect_names(node: schema.IRNode, ctx_filter: Optional[str] = None) -> Set[str]:
    """
    Collect all Name identifiers from the IR tree.

    Args:
        node: Root node to search from
        ctx_filter: Optional context filter ("Load", "Store", "Del")

    Returns:
        Set of name identifiers
    """
    collector = _NameCollector(ctx_filter)
    collector.visit(node)
    return collector.names


def traverse(node: schema.IRNode, callback: Callable[[schema.IRNode], None]) -> None:
    """
    Traverse the IR tree and call callback for each node.

    Args:
        node: Root node to traverse
        callback: Function to call for each node
    """
    traverser = _CallbackTraverser(callback)
    traverser.visit(node)


class _NodeCollector(NodeVisitor):
    """Helper visitor to collect nodes of a specific type."""

    __slots__ = ("node_type", "nodes")

    def __init__(self, node_type: Type[schema.IRNode]):
        self.node_type = node_type
        self.nodes: List[schema.IRNode] = []

    def generic_visit(self, node: schema.IRNode) -> None:
        if isinstance(node, self.node_type):
            self.nodes.append(node)
        super().generic_visit(node)


class _MultiTypeCollector(NodeVisitor):
    """Helper visitor to collect nodes matching multiple types."""

    __slots__ = ("node_types", "nodes")

    def __init__(self, node_types: tuple):
        self.node_types = node_types
        self.nodes: List[schema.IRNode] = []

    def generic_visit(self, node: schema.IRNode) -> None:
        if isinstance(node, self.node_types):
            self.nodes.append(node)
        super().generic_visit(node)


class _NameCollector(NodeVisitor):
    """Helper visitor to collect Name identifiers."""

    __slots__ = ("ctx_filter", "names")

    def __init__(self, ctx_filter: Optional[str] = None):
        self.ctx_filter = ctx_filter
        self.names: Set[str] = set()

    def visit_Name(self, node: schema.Name) -> None:
        if self.ctx_filter is None or node.ctx == self.ctx_filter:
            self.names.add(node.id)

    def generic_visit(self, node: schema.IRNode) -> None:
        super().generic_visit(node)


class _CallbackTraverser(NodeVisitor):
    """Helper visitor that calls a callback for each node."""

    __slots__ = ("callback",)

    def __init__(self, callback: Callable[[schema.IRNode], None]):
        self.callback = callback

    def generic_visit(self, node: schema.IRNode) -> None:
        self.callback(node)
        super().generic_visit(node)


class VariableReplacer(NodeTransformer):
    """
    Replace occurrences of a variable with a constant value.

    Useful for loop unrolling and constant propagation.
    """

    def __init__(self, var_name: str, value: Any):
        self.var_name = var_name
        self.value = value

    def visit_Name(self, node: schema.Name) -> schema.Expression:
        if node.id == self.var_name and node.ctx == "Load":
            return schema.Constant(value=self.value, kind=type(self.value).__name__)
        return node
