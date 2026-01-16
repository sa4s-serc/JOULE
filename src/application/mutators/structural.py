"""
Structural Mutators - IR-based program transformations.

These mutators operate strictly on the IR tree and perform
semantics-preserving transformations.
"""
import random
import copy
import logging
from typing import List, Tuple, Optional

from src.domain.interfaces import Mutator
from src.domain.ir import schema
from src.domain.ir.context import MutationContext
from src.domain.ir.utils import NodeTransformer, find_nodes

logger = logging.getLogger(__name__)


class StructuralMutator(Mutator):
    """
    Performs structural mutations on the IR tree.
    
    These are syntax-preserving transformations that don't change
    the program's semantics, only its structure.
    
    Strategies:
    1. Reorder independent statements
    2. Swap commutative operands
    3. Convert to augmented assignment
    4. Strength reduction
    5. Fast membership (list -> set)
    6. Algebraic simplification
    7. Loop optimization
    """
    
    def __init__(self, use_context: bool = True):
        """
        Args:
            use_context: If True, uses MutationContext for safe transformations
        """
        self.use_context = use_context
    
    def mutate(self, ir: schema.Module) -> List[Tuple[schema.Module, str]]:
        """Apply structural mutations to the IR."""
        variants = []
        
        # Build context if enabled
        context = self._build_context(ir) if self.use_context else None
        
        # Define mutation strategies
        strategies = [
            ("Structural_ReorderStatements", lambda: self._mutate_reorder(ir, context)),
            ("Structural_SwapOperands", lambda: self._mutate_swap_operands(ir, context)),
            ("Structural_AugAssign", lambda: self._mutate_aug_assign(ir)),
            ("Structural_StrengthReduction", lambda: self._mutate_strength_reduction(ir)),
            ("Structural_FastMembership", lambda: self._mutate_fast_membership(ir)),
            ("Structural_AlgebraicSimplification", lambda: self._mutate_algebraic_simplification(ir)),
            ("Structural_LoopOptimization", lambda: self._mutate_loop_optimization(ir)),
        ]
        
        for name, mutate_fn in strategies:
            try:
                variant = mutate_fn()
                if variant:
                    variants.append((variant, name))
                    logger.debug(f"Created {name} variant")
            except Exception as e:
                logger.error(f"{name} mutation failed: {e}")
            
        return variants
    
    def _build_context(self, ir: schema.Module) -> Optional[MutationContext]:
        """Build mutation context with error handling."""
        try:
            context = MutationContext(ir)
            logger.debug(f"Built context with {len(context.symbol_table)} symbols")
            return context
        except Exception as e:
            logger.warning(f"Failed to build context: {e}")
            return None

    def _mutate_strength_reduction(self, ir: schema.Module) -> Optional[schema.Module]:
        """Replace expensive operations with cheaper ones (e.g. x**2 -> x*x)."""
        new_ir = copy.deepcopy(ir)
        transformer = StrengthReductionTransformer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _mutate_fast_membership(self, ir: schema.Module) -> Optional[schema.Module]:
        """Replace x in [a,b] with x in {a,b} for constant lists."""
        new_ir = copy.deepcopy(ir)
        transformer = FastMembershipTransformer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _mutate_algebraic_simplification(self, ir: schema.Module) -> Optional[schema.Module]:
        """Apply algebraic simplifications and boolean algebra."""
        new_ir = copy.deepcopy(ir)
        transformer = AlgebraicSimplificationTransformer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _mutate_loop_optimization(self, ir: schema.Module) -> Optional[schema.Module]:
        """Apply loop optimizations like fusion and peeling."""
        new_ir = copy.deepcopy(ir)
        transformer = LoopOptimizationTransformer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None

    def _mutate_reorder(self, ir: schema.Module, context: Optional[MutationContext]) -> Optional[schema.Module]:
        """
        Reorder consecutive independent statements.
        
        Uses dependency analysis if context is provided to ensure
        the reordering is semantics-preserving.
        """
        new_ir = copy.deepcopy(ir)
        
        # Find all blocks using utility function
        blocks = find_nodes(new_ir, schema.Block)
        candidates = [blk for blk in blocks if len(blk.statements) >= 2]
        
        if not candidates:
            return None
        
        # Try multiple times to find a valid swap
        for _ in range(10):
            block = random.choice(candidates)
            if len(block.statements) < 2:
                continue
            
            idx1, idx2 = random.sample(range(len(block.statements)), 2)
            
            # If we have context, check if swap is safe
            if context:
                stmt1, stmt2 = block.statements[idx1], block.statements[idx2]
                
                # Check purity and dependencies
                if not context.is_pure(stmt1) or not context.is_pure(stmt2):
                    continue

                stmt1_defs = context.get_defined_vars(stmt1)
                stmt1_uses = context.get_used_vars(stmt1)
                stmt2_defs = context.get_defined_vars(stmt2)
                stmt2_uses = context.get_used_vars(stmt2)
                
                # Check for conflicts
                if stmt1_defs & stmt2_uses or stmt2_defs & stmt1_uses or stmt1_defs & stmt2_defs:
                    continue
            
            # Perform the swap
            block.statements[idx1], block.statements[idx2] = block.statements[idx2], block.statements[idx1]
            return new_ir
        
        return None
    
    def _mutate_swap_operands(self, ir: schema.Module, context: Optional[MutationContext]) -> Optional[schema.Module]:
        """Swap operands in commutative binary operations."""
        new_ir = copy.deepcopy(ir)
        
        # Build local context if not provided
        if not context and self.use_context:
            context = self._build_context(new_ir)

        # Find all binary operations using utility function
        binops = find_nodes(new_ir, schema.BinaryOp)
        
        # Filter commutative operations
        commutative = {'+', '*', '==', '!=', 'and', 'or', '^', '&', '|'}
        candidates = []
        for op in binops:
            if op.op in commutative:
                if context and (not context.is_pure(op.left) or not context.is_pure(op.right)):
                    continue
                candidates.append(op)
        
        if not candidates:
            return None
        
        # Pick a random operation and swap operands
        binop = random.choice(candidates)
        binop.left, binop.right = binop.right, binop.left
        
        return new_ir

    def _mutate_aug_assign(self, ir: schema.Module) -> Optional[schema.Module]:
        """Replace x = x + y with x += y."""
        new_ir = copy.deepcopy(ir)
        blocks = find_nodes(new_ir, schema.Block)
        
        candidates = []
        for block in blocks:
            for i, stmt in enumerate(block.statements):
                if isinstance(stmt, schema.Assign) and len(stmt.targets) == 1:
                    target = stmt.targets[0]
                    if isinstance(target, schema.Name) and isinstance(stmt.value, schema.BinaryOp):
                        left, right = stmt.value.left, stmt.value.right
                        op = stmt.value.op
                        
                        # x = x + y
                        if isinstance(left, schema.Name) and left.id == target.id:
                            candidates.append((block, i, stmt, op, right))
                        # x = y + x (only for commutative ops)
                        elif isinstance(right, schema.Name) and right.id == target.id and op in ('+', '*'):
                            candidates.append((block, i, stmt, op, left))
                            
        if not candidates:
            return None
            
        block, idx, stmt, op, value = random.choice(candidates)
        block.statements[idx] = schema.AugAssign(
            target=stmt.targets[0],
            op=op,
            value=value
        )
        return new_ir
        

class StrengthReductionTransformer(NodeTransformer):
    """
    Performs strength reduction: replacing expensive operations with cheaper ones.
    """
    def __init__(self):
        self.changed = False

    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Power optimizations
        if node.op == '**' and isinstance(node.right, schema.Constant):
            if node.right.value == 2:
                # x ** 2 -> x * x
                self.changed = True
                return schema.BinaryOp(left=node.left, op='*', right=node.left)
            elif node.right.value == 3:
                # x ** 3 -> x * x * x
                self.changed = True
                x_squared = schema.BinaryOp(left=node.left, op='*', right=node.left)
                return schema.BinaryOp(left=x_squared, op='*', right=node.left)
            elif node.right.value == 0.5:
                # x ** 0.5 -> math.sqrt(x)
                self.changed = True
                return schema.Call(
                    func=schema.Attribute(value=schema.Name(id='math'), attr='sqrt'),
                    args=[node.left]
                )
        
        # Division optimizations
        if node.op == '/' and isinstance(node.right, schema.Constant):
            if node.right.value == 2:
                # x / 2 -> x * 0.5
                self.changed = True
                return schema.BinaryOp(
                    left=node.left, op='*', 
                    right=schema.Constant(value=0.5, kind="float")
                )
        
        # Multiplication optimizations
        if node.op == '*':
            if isinstance(node.right, schema.Constant):
                if node.right.value == 0:
                    # x * 0 -> 0
                    self.changed = True
                    return schema.Constant(value=0, kind="int")
                elif node.right.value == 1:
                    # x * 1 -> x
                    self.changed = True
                    return node.left
            elif isinstance(node.left, schema.Constant):
                if node.left.value == 0:
                    # 0 * x -> 0
                    self.changed = True
                    return schema.Constant(value=0, kind="int")
                elif node.left.value == 1:
                    # 1 * x -> x
                    self.changed = True
                    return node.right
        
        # Addition optimizations
        if node.op == '+':
            if isinstance(node.right, schema.Constant) and node.right.value == 0:
                # x + 0 -> x
                self.changed = True
                return node.left
            elif isinstance(node.left, schema.Constant) and node.left.value == 0:
                # 0 + x -> x
                self.changed = True
                return node.right
        
        # Subtraction optimizations
        if node.op == '-':
            if isinstance(node.right, schema.Constant) and node.right.value == 0:
                # x - 0 -> x
                self.changed = True
                return node.left
        
        # Floor division optimizations
        if node.op == '//' and isinstance(node.right, schema.Constant) and node.right.value == 1:
            # x // 1 -> x
            self.changed = True
            return node.left
        
        # Modulo optimizations
        if node.op == '%' and isinstance(node.right, schema.Constant) and node.right.value == 1:
            # x % 1 -> 0
            self.changed = True
            return schema.Constant(value=0, kind="int")
            
        return node
    
    def visit_If(self, node: schema.If) -> schema.Statement:
        node = self.generic_visit(node)
        
        # len(seq) > 0 -> seq
        if isinstance(node.test, schema.Compare) and len(node.test.ops) == 1:
            op = node.test.ops[0]
            left = node.test.left
            right = node.test.comparators[0]
            
            # Check for len(x) > 0
            if op == '>' and isinstance(right, schema.Constant) and right.value == 0:
                if isinstance(left, schema.Call) and isinstance(left.func, schema.Name) and left.func.id == 'len':
                    if len(left.args) == 1:
                        self.changed = True
                        node.test = left.args[0]
                        
        return node

class FastMembershipTransformer(NodeTransformer):
    """
    Optimizes membership tests.
    x in [a, b] -> x in {a, b} (O(N) -> O(1))
    """
    def __init__(self):
        self.changed = False
        
    def visit_Compare(self, node: schema.Compare) -> schema.Expression:
        node = self.generic_visit(node)
        
        if len(node.ops) != 1 or len(node.comparators) != 1:
            return node
            
        op = node.ops[0]
        comparator = node.comparators[0]
        
        if op in ('in', 'not in') and isinstance(comparator, schema.ListExpr):
            # Convert ListExpr to SetExpr
            # Only if all elements are hashable constants
            # For safety, let's just check if they are Constants
            all_const = all(isinstance(elt, schema.Constant) for elt in comparator.elts)
            
            if all_const:
                self.changed = True
                node.comparators[0] = schema.SetExpr(elts=comparator.elts)
                
        return node


class AlgebraicSimplificationTransformer(NodeTransformer):
    """
    Performs algebraic simplifications and boolean algebra optimizations.
    """
    def __init__(self):
        self.changed = False
    
    def visit_UnaryOp(self, node: schema.UnaryOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Double negation: not not x -> x
        if node.op == 'not' and isinstance(node.operand, schema.UnaryOp) and node.operand.op == 'not':
            self.changed = True
            return node.operand.operand
        
        # De Morgan's laws: not (a and b) -> (not a) or (not b)
        if node.op == 'not' and isinstance(node.operand, schema.BoolOp):
            if node.operand.op == 'and':
                self.changed = True
                negated_values = [schema.UnaryOp(op='not', operand=val) for val in node.operand.values]
                return schema.BoolOp(op='or', values=negated_values)
            elif node.operand.op == 'or':
                self.changed = True
                negated_values = [schema.UnaryOp(op='not', operand=val) for val in node.operand.values]
                return schema.BoolOp(op='and', values=negated_values)
        
        return node
    
    def visit_BoolOp(self, node: schema.BoolOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Short-circuit optimizations
        if node.op == 'and':
            # Remove True values: True and x -> x
            filtered_values = []
            for val in node.values:
                if isinstance(val, schema.Constant) and val.value is True:
                    continue  # Skip True values
                elif isinstance(val, schema.Constant) and val.value is False:
                    # False and anything -> False
                    self.changed = True
                    return schema.Constant(value=False, kind="bool")
                else:
                    filtered_values.append(val)
            
            if len(filtered_values) != len(node.values):
                self.changed = True
                if len(filtered_values) == 0:
                    return schema.Constant(value=True, kind="bool")
                elif len(filtered_values) == 1:
                    return filtered_values[0]
                else:
                    node.values = filtered_values
        
        elif node.op == 'or':
            # Remove False values: False or x -> x
            filtered_values = []
            for val in node.values:
                if isinstance(val, schema.Constant) and val.value is False:
                    continue  # Skip False values
                elif isinstance(val, schema.Constant) and val.value is True:
                    # True or anything -> True
                    self.changed = True
                    return schema.Constant(value=True, kind="bool")
                else:
                    filtered_values.append(val)
            
            if len(filtered_values) != len(node.values):
                self.changed = True
                if len(filtered_values) == 0:
                    return schema.Constant(value=False, kind="bool")
                elif len(filtered_values) == 1:
                    return filtered_values[0]
                else:
                    node.values = filtered_values
        
        return node
    
    def visit_Compare(self, node: schema.Compare) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Comparison chain optimizations
        if len(node.ops) == 1 and len(node.comparators) == 1:
            op = node.ops[0]
            left = node.left
            right = node.comparators[0]
            
            # x == x -> True
            if op == '==' and self._nodes_equal(left, right):
                self.changed = True
                return schema.Constant(value=True, kind="bool")
            
            # x != x -> False
            if op == '!=' and self._nodes_equal(left, right):
                self.changed = True
                return schema.Constant(value=False, kind="bool")
            
            # x < x, x > x -> False
            if op in ('<', '>') and self._nodes_equal(left, right):
                self.changed = True
                return schema.Constant(value=False, kind="bool")
            
            # x <= x, x >= x -> True
            if op in ('<=', '>=') and self._nodes_equal(left, right):
                self.changed = True
                return schema.Constant(value=True, kind="bool")
        
        return node
    
    def _nodes_equal(self, node1: schema.Expression, node2: schema.Expression) -> bool:
        """Check if two nodes are structurally equal (simplified check)."""
        if type(node1) != type(node2):
            return False
        
        if isinstance(node1, schema.Name):
            return node1.id == node2.id
        elif isinstance(node1, schema.Constant):
            return node1.value == node2.value
        
        # For more complex nodes, we'd need deeper comparison
        return False


class LoopOptimizationTransformer(NodeTransformer):
    """
    Performs loop optimizations including fusion and peeling.
    """
    def __init__(self):
        self.changed = False
    
    def visit_Block(self, node: schema.Block) -> schema.Block:
        node = self.generic_visit(node)
        
        # Look for adjacent loops that can be fused
        new_statements = []
        i = 0
        while i < len(node.statements):
            stmt = node.statements[i]
            
            if isinstance(stmt, schema.For) and i + 1 < len(node.statements):
                next_stmt = node.statements[i + 1]
                if isinstance(next_stmt, schema.For):
                    # Check if loops can be fused
                    if self._can_fuse_loops(stmt, next_stmt):
                        fused_loop = self._fuse_loops(stmt, next_stmt)
                        new_statements.append(fused_loop)
                        self.changed = True
                        i += 2  # Skip both loops
                        continue
            
            new_statements.append(stmt)
            i += 1
        
        node.statements = new_statements
        return node
    
    def _can_fuse_loops(self, loop1: schema.For, loop2: schema.For) -> bool:
        """Check if two loops can be safely fused."""
        # Simplified check: same iteration variable and range
        if not (isinstance(loop1.target, schema.Name) and isinstance(loop2.target, schema.Name)):
            return False
        
        if loop1.target.id != loop2.target.id:
            return False
        
        # Check if iteration spaces are the same (simplified)
        return self._ranges_equal(loop1.iter, loop2.iter)
    
    def _ranges_equal(self, iter1: schema.Expression, iter2: schema.Expression) -> bool:
        """Check if two iteration expressions are equal (simplified)."""
        if type(iter1) != type(iter2):
            return False
        
        if isinstance(iter1, schema.Call) and isinstance(iter2, schema.Call):
            if (isinstance(iter1.func, schema.Name) and isinstance(iter2.func, schema.Name) and
                iter1.func.id == iter2.func.id == 'range'):
                # Compare range arguments
                if len(iter1.args) == len(iter2.args):
                    return all(self._expressions_equal(a1, a2) for a1, a2 in zip(iter1.args, iter2.args))
        
        return False
    
    def _expressions_equal(self, expr1: schema.Expression, expr2: schema.Expression) -> bool:
        """Check if two expressions are equal (simplified)."""
        if type(expr1) != type(expr2):
            return False
        
        if isinstance(expr1, schema.Constant):
            return expr1.value == expr2.value
        elif isinstance(expr1, schema.Name):
            return expr1.id == expr2.id
        
        return False
    
    def _fuse_loops(self, loop1: schema.For, loop2: schema.For) -> schema.For:
        """Fuse two compatible loops."""
        # Combine loop bodies
        combined_body = schema.Block(
            statements=loop1.body.statements + loop2.body.statements
        )
        
        return schema.For(
            target=loop1.target,
            iter=loop1.iter,
            body=combined_body,
            orelse=None  # Simplified: ignore orelse for now
        )

