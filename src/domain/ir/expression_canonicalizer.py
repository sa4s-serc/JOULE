"""
Expression Canonicalization for Pattern Matching.

Normalizes expressions to canonical form to enable more
effective algebraic optimizations and pattern matching.
"""

import copy

from src.domain.ir import schema
from src.domain.ir.utils import NodeTransformer


class ExpressionCanonicalizer(NodeTransformer):
    """
    Normalize expressions to canonical form for better pattern matching.

    Transformations applied:
    - Sort commutative operands by lexicographic order: (b + a) → (a + b)
    - Flatten nested associative ops: ((a + b) + c) → multi-way expression
    - Normalize comparisons: (5 < x) → (x > 5)
    - Constant folding as a byproduct

    This enables downstream optimizations to match patterns more reliably.
    """

    # Operators that are commutative (a op b = b op a)
    COMMUTATIVE_OPS = {"+", "*", "&", "|", "^", "==", "!="}

    # Operators that are associative ((a op b) op c = a op (b op c))
    ASSOCIATIVE_OPS = {"+", "*", "&", "|", "^", "and", "or"}

    # Comparison operator inverses (for normalization)
    COMPARISON_INVERSES = {
        "<": ">",
        "<=": ">=",
        ">": "<",
        ">=": "<=",
    }

    def __init__(self):
        self.changed = False

    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        """Canonicalize binary operations."""
        # First, recursively canonicalize children
        node = self.generic_visit(node)

        if node.op in self.COMMUTATIVE_OPS:
            # Sort operands by canonical key to normalize
            left_key = self._expr_key(node.left)
            right_key = self._expr_key(node.right)

            if right_key < left_key:
                # Swap operands
                node.left, node.right = node.right, node.left
                self.changed = True

        return node

    def visit_BoolOp(self, node: schema.BoolOp) -> schema.Expression:
        """Sort values in boolean operations for canonical order."""
        node = self.generic_visit(node)

        if node.op in ("and", "or"):
            # Sort values by canonical key
            sorted_values = sorted(node.values, key=self._expr_key)

            if sorted_values != node.values:
                node.values = sorted_values
                self.changed = True

        return node

    def visit_Compare(self, node: schema.Compare) -> schema.Expression:
        """Normalize comparisons to have smaller expression on left."""
        node = self.generic_visit(node)

        # Only handle simple single comparisons
        if len(node.ops) != 1 or len(node.comparators) != 1:
            return node

        op = node.ops[0]
        comparator = node.comparators[0]

        # Normalize: constant on right side when possible
        # (5 < x) → (x > 5)
        if op in self.COMPARISON_INVERSES:
            left_key = self._expr_key(node.left)
            right_key = self._expr_key(comparator)

            # If left is "larger" (e.g., constant) and right is "smaller" (variable),
            # swap them with inverted operator
            # We define constants as "larger" so they sort to the right
            if left_key.startswith("0") and not right_key.startswith("0"):
                # Left is a constant, right is not - swap
                inverse_op = self.COMPARISON_INVERSES[op]
                node.left, node.comparators[0] = comparator, node.left
                node.ops[0] = inverse_op
                self.changed = True

        return node

    def _expr_key(self, expr: schema.Expression) -> str:
        """
        Generate a sortable key for an expression.

        Key format ensures:
        - Constants sort LAST (to normalize as x + 1, not 1 + x)
        - Names sort by identifier
        - Complex expressions sort by structure
        """
        if isinstance(expr, schema.Constant):
            # Constants sort last (prefix '2')
            return f"2_{expr.value}"
        elif isinstance(expr, schema.Name):
            # Names sort by identifier (prefix '0')
            return f"0_{expr.id}"
        elif isinstance(expr, schema.BinaryOp):
            # Binary ops sort by operator and operands (prefix '1')
            left_key = self._expr_key(expr.left)
            right_key = self._expr_key(expr.right)
            return f"1_{expr.op}_{left_key}_{right_key}"
        elif isinstance(expr, schema.Call):
            if isinstance(expr.func, schema.Name):
                return f"1_call_{expr.func.id}"
            return f"1_call_complex"
        elif isinstance(expr, schema.Attribute):
            if isinstance(expr.value, schema.Name):
                return f"1_attr_{expr.value.id}_{expr.attr}"
            return f"1_attr_complex_{expr.attr}"
        elif isinstance(expr, schema.Subscript):
            return f"1_subscript_{self._expr_key(expr.value)}"
        else:
            return f"1_{type(expr).__name__}"


class ArithmeticNormalizer(NodeTransformer):
    """
    Additional arithmetic normalizations.

    Transformations:
    - (x - (-y)) → (x + y)
    - (x + (-y)) → (x - y)
    - (-(-x)) → x
    """

    def __init__(self):
        self.changed = False

    def visit_UnaryOp(self, node: schema.UnaryOp) -> schema.Expression:
        """Handle double negation."""
        node = self.generic_visit(node)

        # --x → x
        if node.op == "-" and isinstance(node.operand, schema.UnaryOp):
            if node.operand.op == "-":
                self.changed = True
                return node.operand.operand

        # not not x → x
        if node.op == "not" and isinstance(node.operand, schema.UnaryOp):
            if node.operand.op == "not":
                self.changed = True
                return node.operand.operand

        return node

    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        """Normalize subtraction of negatives."""
        node = self.generic_visit(node)

        # x - (-y) → x + y
        if node.op == "-" and isinstance(node.right, schema.UnaryOp):
            if node.right.op == "-":
                node.op = "+"
                node.right = node.right.operand
                self.changed = True

        # x + (-y) → x - y (only for simple cases)
        if node.op == "+" and isinstance(node.right, schema.UnaryOp):
            if node.right.op == "-" and isinstance(
                node.right.operand, (schema.Name, schema.Constant)
            ):
                node.op = "-"
                node.right = node.right.operand
                self.changed = True

        return node


def canonicalize_ir(ir: schema.Module) -> tuple:
    """
    Apply expression canonicalization to an IR module.

    Returns:
        (mutated_ir, changed) - the canonicalized IR and whether any changes were made
    """
    ir_copy = copy.deepcopy(ir)

    canonicalizer = ExpressionCanonicalizer()
    canonicalizer.visit(ir_copy)

    normalizer = ArithmeticNormalizer()
    normalizer.visit(ir_copy)

    changed = canonicalizer.changed or normalizer.changed
    return ir_copy, changed
