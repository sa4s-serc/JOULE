"""
Micro Layer Mutators - Low-Level Optimizations

These mutators focus on:
- Low-level performance optimizations
- Constant folding and propagation
- Dead code elimination
- Loop unrolling and micro-optimizations
"""
import copy
import operator
import logging
from typing import List, Optional, Set, Any
from src.application.mutators.base import LayeredMutator, MutationLayer, MutationResult, safe_deepcopy_ir, create_mutation_result
from src.domain.ir import schema
from src.domain.ir.utils import NodeTransformer, collect_names
from src.domain.ir.context import MutationContext

logger = logging.getLogger(__name__)


class ConstantOptimizer(LayeredMutator):
    """
    Performs constant folding, propagation, and related optimizations.
    
    Focuses on compile-time evaluation of constant expressions and
    propagation of constant values through the program.
    """
    
    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.MICRO, enabled_strategies)
    
    def get_available_strategies(self) -> List[str]:
        return [
            "Constant_Folding",
            "Constant_Propagation",
            "Constant_BooleanSimplification",
            "Constant_ArithmeticSimplification"
        ]
    
    def _apply_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply constant optimization mutations."""
        results = []
        
        # Strategy 1: Constant Folding
        if self._is_strategy_enabled("Constant_Folding"):
            variant = self._fold_constants(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Constant_Folding",
                    layer=MutationLayer.MICRO,
                    confidence=1.0,
                    description="Evaluated constant expressions at compile time"
                ))
        
        # Strategy 2: Constant Propagation
        if self._is_strategy_enabled("Constant_Propagation"):
            variant = self._propagate_constants(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Constant_Propagation",
                    layer=MutationLayer.MICRO,
                    confidence=0.95,
                    description="Propagated constant values through variable assignments"
                ))
        
        # Strategy 3: Boolean Simplification
        if self._is_strategy_enabled("Constant_BooleanSimplification"):
            variant = self._simplify_boolean_constants(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Constant_BooleanSimplification",
                    layer=MutationLayer.MICRO,
                    confidence=1.0,
                    description="Simplified boolean expressions with constant values"
                ))
        
        # Strategy 4: Arithmetic Simplification
        if self._is_strategy_enabled("Constant_ArithmeticSimplification"):
            variant = self._simplify_arithmetic_constants(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Constant_ArithmeticSimplification",
                    layer=MutationLayer.MICRO,
                    confidence=1.0,
                    description="Simplified arithmetic expressions with constant operands"
                ))
        
        return results
    
    def _fold_constants(self, ir: schema.Module) -> Optional[schema.Module]:
        """Fold constant expressions."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = ConstantFoldingTransformer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _propagate_constants(self, ir: schema.Module) -> Optional[schema.Module]:
        """Propagate constant values through assignments."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = ConstantPropagationTransformer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _simplify_boolean_constants(self, ir: schema.Module) -> Optional[schema.Module]:
        """Simplify boolean expressions with constants."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = BooleanConstantSimplifier()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _simplify_arithmetic_constants(self, ir: schema.Module) -> Optional[schema.Module]:
        """Simplify arithmetic expressions with constants."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = ArithmeticConstantSimplifier()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None


class DeadCodeEliminator(LayeredMutator):
    """
    Eliminates dead and unreachable code.
    
    Removes code that cannot be executed or whose results are never used.
    """
    
    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.MICRO, enabled_strategies)
    
    def get_available_strategies(self) -> List[str]:
        return [
            "DeadCode_UnreachableElimination",
            "DeadCode_UnusedVariableElimination",
            "DeadCode_PureExpressionElimination",
            "DeadCode_EmptyBlockElimination"
        ]
    
    def _apply_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply dead code elimination mutations."""
        results = []
        
        # Strategy 1: Unreachable Code Elimination
        if self._is_strategy_enabled("DeadCode_UnreachableElimination"):
            variant = self._eliminate_unreachable_code(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="DeadCode_UnreachableElimination",
                    layer=MutationLayer.MICRO,
                    confidence=1.0,
                    description="Eliminated unreachable code after returns and breaks"
                ))
        
        # Strategy 2: Unused Variable Elimination
        if self._is_strategy_enabled("DeadCode_UnusedVariableElimination"):
            variant = self._eliminate_unused_variables(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="DeadCode_UnusedVariableElimination",
                    layer=MutationLayer.MICRO,
                    confidence=0.9,
                    description="Eliminated assignments to unused variables"
                ))
        
        # Strategy 3: Pure Expression Elimination
        if self._is_strategy_enabled("DeadCode_PureExpressionElimination"):
            variant = self._eliminate_pure_expressions(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="DeadCode_PureExpressionElimination",
                    layer=MutationLayer.MICRO,
                    confidence=0.95,
                    description="Eliminated pure expressions with no side effects"
                ))
        
        # Strategy 4: Empty Block Elimination
        if self._is_strategy_enabled("DeadCode_EmptyBlockElimination"):
            variant = self._eliminate_empty_blocks(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="DeadCode_EmptyBlockElimination",
                    layer=MutationLayer.MICRO,
                    confidence=1.0,
                    description="Eliminated empty code blocks and unnecessary structures"
                ))
        
        return results
    
    def _eliminate_unreachable_code(self, ir: schema.Module) -> Optional[schema.Module]:
        """Eliminate unreachable code."""
        new_ir = safe_deepcopy_ir(ir)
        context = MutationContext(new_ir)
        transformer = UnreachableCodeEliminator(context)
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _eliminate_unused_variables(self, ir: schema.Module) -> Optional[schema.Module]:
        """Eliminate unused variable assignments."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = UnusedVariableEliminator()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _eliminate_pure_expressions(self, ir: schema.Module) -> Optional[schema.Module]:
        """Eliminate pure expressions with no side effects."""
        new_ir = safe_deepcopy_ir(ir)
        context = MutationContext(new_ir)
        transformer = PureExpressionEliminator(context)
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _eliminate_empty_blocks(self, ir: schema.Module) -> Optional[schema.Module]:
        """Eliminate empty blocks and unnecessary structures."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = EmptyBlockEliminator()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None


class LoopMicroOptimizer(LayeredMutator):
    """
    Performs micro-optimizations on loops.
    
    Applies low-level loop optimizations like unrolling, strength reduction,
    and invariant code motion.
    """
    
    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.MICRO, enabled_strategies)
    
    def get_available_strategies(self) -> List[str]:
        return [
            "Loop_SmallUnrolling",
            "Loop_StrengthReduction",
            "Loop_InvariantMotion",
            "Loop_BoundsOptimization"
        ]
    
    def _apply_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply loop micro-optimization mutations."""
        results = []
        
        # Strategy 1: Small Loop Unrolling
        if self._is_strategy_enabled("Loop_SmallUnrolling"):
            variant = self._unroll_small_loops(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Loop_SmallUnrolling",
                    layer=MutationLayer.MICRO,
                    confidence=0.8,
                    description="Unrolled small loops for better performance"
                ))
        
        # Strategy 2: Strength Reduction in Loops
        if self._is_strategy_enabled("Loop_StrengthReduction"):
            variant = self._apply_loop_strength_reduction(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Loop_StrengthReduction",
                    layer=MutationLayer.MICRO,
                    confidence=0.9,
                    description="Applied strength reduction to loop operations"
                ))
        
        # Strategy 3: Loop Invariant Code Motion
        if self._is_strategy_enabled("Loop_InvariantMotion"):
            variant = self._move_loop_invariants(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Loop_InvariantMotion",
                    layer=MutationLayer.MICRO,
                    confidence=0.85,
                    description="Moved loop-invariant code outside loops"
                ))
        
        # Strategy 4: Loop Bounds Optimization
        if self._is_strategy_enabled("Loop_BoundsOptimization"):
            variant = self._optimize_loop_bounds(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Loop_BoundsOptimization",
                    layer=MutationLayer.MICRO,
                    confidence=0.75,
                    description="Optimized loop bounds and iteration patterns"
                ))
        
        return results
    
    def _unroll_small_loops(self, ir: schema.Module) -> Optional[schema.Module]:
        """Unroll small loops for better performance."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = SmallLoopUnroller(max_unroll=4)
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _apply_loop_strength_reduction(self, ir: schema.Module) -> Optional[schema.Module]:
        """Apply strength reduction to loop operations."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = LoopStrengthReducer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _move_loop_invariants(self, ir: schema.Module) -> Optional[schema.Module]:
        """Move loop-invariant code outside loops."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = LoopInvariantMover()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _optimize_loop_bounds(self, ir: schema.Module) -> Optional[schema.Module]:
        """Optimize loop bounds and iteration patterns."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = LoopBoundsOptimizer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None


# Transformer implementations for micro-optimizations
class ConstantFoldingTransformer(NodeTransformer):
    """Folds constant expressions at compile time."""
    
    def __init__(self):
        self.changed = False
        self.ops = {
            '+': operator.add, '-': operator.sub, '*': operator.mul,
            '/': operator.truediv, '//': operator.floordiv, '%': operator.mod,
            '**': operator.pow, '<<': operator.lshift, '>>': operator.rshift,
            '|': operator.or_, '^': operator.xor, '&': operator.and_,
            '==': operator.eq, '!=': operator.ne, '<': operator.lt,
            '<=': operator.le, '>': operator.gt, '>=': operator.ge,
        }
    
    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        if isinstance(node.left, schema.Constant) and isinstance(node.right, schema.Constant):
            try:
                op_func = self.ops.get(node.op)
                if op_func:
                    val = op_func(node.left.value, node.right.value)
                    self.changed = True
                    return schema.Constant(value=val, kind=type(val).__name__)
            except Exception:
                pass  # Division by zero, overflow, etc.
        
        return node
    
    def visit_UnaryOp(self, node: schema.UnaryOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        if isinstance(node.operand, schema.Constant):
            try:
                if node.op == 'not':
                    val = not node.operand.value
                elif node.op == '-':
                    val = -node.operand.value
                elif node.op == '+':
                    val = +node.operand.value
                elif node.op == '~':
                    val = ~node.operand.value
                else:
                    return node
                
                self.changed = True
                return schema.Constant(value=val, kind=type(val).__name__)
            except Exception:
                pass
        
        return node


class ConstantPropagationTransformer(NodeTransformer):
    """
    Enhanced constant propagation with scope-aware tracking.
    
    Features:
    - Maintains a scope stack for function/class boundaries
    - Invalidates constants on reassignment to non-constants
    - Properly handles nested scopes
    - Checks all enclosing scopes for constant lookup
    """
    
    def __init__(self):
        self.changed = False
        self.scope_stack = [{}]  # Stack of {var_name -> Constant}
    
    def _push_scope(self):
        """Push a new scope onto the stack."""
        self.scope_stack.append({})
    
    def _pop_scope(self):
        """Pop the current scope from the stack."""
        if len(self.scope_stack) > 1:
            self.scope_stack.pop()
    
    def _set_constant(self, var_name: str, value: schema.Constant):
        """Set a constant in the current scope."""
        self.scope_stack[-1][var_name] = value
    
    def _invalidate_constant(self, var_name: str):
        """Remove constant tracking when reassigned to non-constant."""
        self.scope_stack[-1].pop(var_name, None)
    
    def _lookup_constant(self, var_name: str) -> Optional[schema.Constant]:
        """Look up a constant, checking from innermost to outermost scope."""
        for scope in reversed(self.scope_stack):
            if var_name in scope:
                return scope[var_name]
        return None
    
    def visit_FunctionDef(self, node: schema.FunctionDef) -> schema.Statement:
        """Create new scope for function body."""
        self._push_scope()
        
        # Parameters shadow any outer constants
        for arg in node.args.args:
            self._invalidate_constant(arg.arg)
        
        node = self.generic_visit(node)
        self._pop_scope()
        return node
    
    def visit_AsyncFunctionDef(self, node: schema.AsyncFunctionDef) -> schema.Statement:
        """Create new scope for async function body."""
        self._push_scope()
        
        for arg in node.args.args:
            self._invalidate_constant(arg.arg)
        
        node = self.generic_visit(node)
        self._pop_scope()
        return node
    
    def visit_ClassDef(self, node: schema.ClassDef) -> schema.Statement:
        """Create new scope for class body."""
        self._push_scope()
        node = self.generic_visit(node)
        self._pop_scope()
        return node
    
    def visit_For(self, node: schema.For) -> schema.Statement:
        """Loop variables can change, so invalidate them."""
        # Invalidate the loop variable
        if isinstance(node.target, schema.Name):
            self._invalidate_constant(node.target.id)
        
        return self.generic_visit(node)
    
    def visit_Assign(self, node: schema.Assign) -> schema.Statement:
        # First, propagate constants in the RHS
        node.value = self.visit(node.value)
        
        # Then track the assignment
        if len(node.targets) == 1 and isinstance(node.targets[0], schema.Name):
            var_name = node.targets[0].id
            
            if isinstance(node.value, schema.Constant):
                # Track constant assignment
                self._set_constant(var_name, node.value)
            else:
                # Invalidate on non-constant assignment
                self._invalidate_constant(var_name)
        
        return node
    
    def visit_AugAssign(self, node: schema.AugAssign) -> schema.Statement:
        """Augmented assignment (x += 1) may invalidate constants."""
        if isinstance(node.target, schema.Name):
            var_name = node.target.id
            
            # Check if we can compute the new constant value
            current = self._lookup_constant(var_name)
            if current and isinstance(node.value, schema.Constant):
                try:
                    new_val = self._compute_aug_assign(current.value, node.op, node.value.value)
                    if new_val is not None:
                        self._set_constant(var_name, schema.Constant(
                            value=new_val,
                            kind=type(new_val).__name__
                        ))
                        return node
                except Exception:
                    pass
            
            # Can't track, invalidate
            self._invalidate_constant(var_name)
        
        return self.generic_visit(node)
    
    def _compute_aug_assign(self, left, op: str, right):
        """Compute the result of augmented assignment if possible."""
        ops = {
            '+': lambda a, b: a + b,
            '-': lambda a, b: a - b,
            '*': lambda a, b: a * b,
            '/': lambda a, b: a / b if b != 0 else None,
            '//': lambda a, b: a // b if b != 0 else None,
            '%': lambda a, b: a % b if b != 0 else None,
        }
        if op in ops:
            return ops[op](left, right)
        return None
    
    def visit_Name(self, node: schema.Name) -> schema.Expression:
        """Replace Name with constant if tracked."""
        if node.ctx == "Load":
            const = self._lookup_constant(node.id)
            if const:
                self.changed = True
                return copy.deepcopy(const)
        return node


class BooleanConstantSimplifier(NodeTransformer):
    """Simplifies boolean expressions with constant values."""
    
    def __init__(self):
        self.changed = False
    
    def visit_BoolOp(self, node: schema.BoolOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        if node.op == 'and':
            # Remove True values, return False if any False found
            filtered_values = []
            for val in node.values:
                if isinstance(val, schema.Constant):
                    if val.value is False:
                        self.changed = True
                        return schema.Constant(value=False, kind="bool")
                    elif val.value is True:
                        self.changed = True
                        continue  # Skip True values
                filtered_values.append(val)
            
            if len(filtered_values) != len(node.values):
                if len(filtered_values) == 0:
                    return schema.Constant(value=True, kind="bool")
                elif len(filtered_values) == 1:
                    return filtered_values[0]
                else:
                    node.values = filtered_values
        
        elif node.op == 'or':
            # Remove False values, return True if any True found
            filtered_values = []
            for val in node.values:
                if isinstance(val, schema.Constant):
                    if val.value is True:
                        self.changed = True
                        return schema.Constant(value=True, kind="bool")
                    elif val.value is False:
                        self.changed = True
                        continue  # Skip False values
                filtered_values.append(val)
            
            if len(filtered_values) != len(node.values):
                if len(filtered_values) == 0:
                    return schema.Constant(value=False, kind="bool")
                elif len(filtered_values) == 1:
                    return filtered_values[0]
                else:
                    node.values = filtered_values
        
        return node


class ArithmeticConstantSimplifier(NodeTransformer):
    """Simplifies arithmetic expressions with constant operands."""
    
    def __init__(self):
        self.changed = False
    
    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Identity operations
        if isinstance(node.right, schema.Constant):
            if node.op == '+' and node.right.value == 0:
                self.changed = True
                return node.left
            elif node.op == '-' and node.right.value == 0:
                self.changed = True
                return node.left
            elif node.op == '*' and node.right.value == 1:
                self.changed = True
                return node.left
            elif node.op == '*' and node.right.value == 0:
                self.changed = True
                return schema.Constant(value=0, kind="int")
        
        if isinstance(node.left, schema.Constant):
            if node.op == '+' and node.left.value == 0:
                self.changed = True
                return node.right
            elif node.op == '*' and node.left.value == 1:
                self.changed = True
                return node.right
            elif node.op == '*' and node.left.value == 0:
                self.changed = True
                return schema.Constant(value=0, kind="int")
        
        return node


class UnreachableCodeEliminator(NodeTransformer):
    """Eliminates unreachable code after returns, breaks, etc."""
    
    def __init__(self, context: MutationContext):
        self.context = context
        self.changed = False
    
    def visit_Block(self, node: schema.Block) -> schema.Block:
        new_stmts = []
        terminated = False
        
        for stmt in node.statements:
            if terminated:
                self.changed = True
                continue  # Skip unreachable statements
            
            new_stmt = self.visit(stmt)
            if new_stmt is not None:
                new_stmts.append(new_stmt)
            
            # Check if this statement terminates control flow
            if isinstance(stmt, (schema.Return, schema.Break, schema.Continue, schema.Raise)):
                terminated = True
        
        node.statements = new_stmts
        return node


class UnusedVariableEliminator(NodeTransformer):
    """Eliminates assignments to unused variables.
    
    Uses a two-pass approach:
    1. First pass: collect all used variables in the IR
    2. Second pass: remove assignments to variables that are never used
    
    Preserves assignments with side effects (function calls, etc.)
    """
    
    def __init__(self):
        self.changed = False
        self.used_vars: Set[str] = set()
        self._collecting_phase = True  # True during first pass
    
    def visit(self, node: schema.IRNode) -> Any:
        """Override visit to implement two-pass algorithm."""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            # First pass: collect all used variables
            self._collecting_phase = True
            super().visit(node)
            # Second pass: eliminate unused assignments
            self._collecting_phase = False
        return super().visit(node)
    
    def visit_Assign(self, node: schema.Assign) -> Optional[schema.Statement]:
        """Handle assignments - remove if target is unused and RHS has no side effects."""
        node = self.generic_visit(node)
        
        if self._collecting_phase:
            return node
        
        # Only consider simple single-target assignments
        if len(node.targets) != 1 or not isinstance(node.targets[0], schema.Name):
            return node
        
        target_name = node.targets[0].id
        
        # Don't eliminate if variable is used
        if target_name in self.used_vars:
            return node
        
        # Don't eliminate if RHS might have side effects
        if self._has_side_effects(node.value):
            return node
        
        # Safe to eliminate this unused assignment
        self.changed = True
        return None
    
    def visit_Name(self, node: schema.Name) -> schema.Expression:
        """Track all variable uses (loads)."""
        if node.ctx == "Load":
            self.used_vars.add(node.id)
        return node
    
    def _has_side_effects(self, expr: schema.Expression) -> bool:
        """Check if an expression might have side effects.
        
        Conservatively returns True for:
        - Function calls (may have side effects)
        - Attribute accesses (may be property with side effects)
        - Subscript stores (modifying data structures)
        """
        if isinstance(expr, schema.Call):
            return True
        elif isinstance(expr, schema.Attribute):
            # Method calls have side effects
            return True
        elif isinstance(expr, (schema.Constant, schema.Name)):
            return False
        elif isinstance(expr, schema.BinaryOp):
            return self._has_side_effects(expr.left) or self._has_side_effects(expr.right)
        elif isinstance(expr, schema.UnaryOp):
            return self._has_side_effects(expr.operand)
        elif isinstance(expr, (schema.ListExpr, schema.TupleExpr, schema.SetExpr)):
            return any(self._has_side_effects(elt) for elt in expr.elts)
        elif isinstance(expr, schema.DictExpr):
            for k, v in zip(expr.keys, expr.values):
                if k and self._has_side_effects(k):
                    return True
                if self._has_side_effects(v):
                    return True
            return False
        # Be conservative for unknown expression types
        return True


class PureExpressionEliminator(NodeTransformer):
    """Eliminates pure expressions with no side effects."""
    
    def __init__(self, context: MutationContext):
        self.context = context
        self.changed = False
    
    def visit_ExprStmt(self, node: schema.ExprStmt) -> Optional[schema.Statement]:
        if self.context.is_pure(node.value):
            self.changed = True
            return None  # Remove pure expression statement
        return node


class EmptyBlockEliminator(NodeTransformer):
    """Eliminates empty blocks and unnecessary structures."""
    
    def __init__(self):
        self.changed = False
    
    def visit_If(self, node: schema.If) -> Optional[schema.Statement]:
        node = self.generic_visit(node)
        
        if len(node.body.statements) == 0:
            if node.orelse and len(node.orelse.statements) > 0:
                # Convert to inverted condition
                self.changed = True
                return schema.If(
                    test=schema.UnaryOp(op='not', operand=node.test),
                    body=node.orelse,
                    orelse=None
                )
            else:
                # Remove empty if statement
                self.changed = True
                return None
        
        return node


class SmallLoopUnroller(NodeTransformer):
    """Unrolls small loops for better performance."""
    
    def __init__(self, max_unroll: int = 4):
        self.max_unroll = max_unroll
        self.changed = False
    
    def visit_For(self, node: schema.For) -> Any:
        if (isinstance(node.iter, schema.Call) and 
            isinstance(node.iter.func, schema.Name) and 
            node.iter.func.id == 'range'):
            
            args = node.iter.args
            if (len(args) == 1 and isinstance(args[0], schema.Constant) and 
                isinstance(args[0].value, int) and 0 < args[0].value <= self.max_unroll):
                
                # Unroll the loop
                self.changed = True
                unrolled_stmts = []
                
                for i in range(args[0].value):
                    body_copy = copy.deepcopy(node.body.statements)
                    if isinstance(node.target, schema.Name):
                        replacer = VariableReplacer(node.target.id, i)
                        for stmt in body_copy:
                            replacer.visit(stmt)
                    unrolled_stmts.extend(body_copy)
                
                return unrolled_stmts
        
        return self.generic_visit(node)


class LoopStrengthReducer(NodeTransformer):
    """Applies strength reduction to loop operations.
    
    Transforms expensive operations into cheaper equivalent operations:
    - x ** 2 → x * x (avoid exponentiation function call)
    - x ** 3 → x * x * x
    - x * 2 → x << 1 (bit shift instead of multiplication) - ONLY if known int
    
    Note: Bit shift optimizations are only applied if we can guarantee operands
    are integers. Since we lack full type inference, we only apply bit shifts
    when both operands are integer constants (constant folding essentially) 
    or logic explicitly permits. For now, we are conservative.
    """
    
    def __init__(self):
        self.changed = False
    
    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Power to multiplication: x ** 2 → x * x
        # This is generally safe for floats too
        if node.op == '**' and isinstance(node.right, schema.Constant):
            if int(node.right.value) == node.right.value: # Check if integer value
                if node.right.value == 2:
                    self.changed = True
                    return schema.BinaryOp(
                        left=copy.deepcopy(node.left),
                        op='*',
                        right=copy.deepcopy(node.left)
                    )
                elif node.right.value == 3:
                    # x ** 3 → x * x * x
                    self.changed = True
                    x_squared = schema.BinaryOp(
                        left=copy.deepcopy(node.left),
                        op='*',
                        right=copy.deepcopy(node.left)
                    )
                    return schema.BinaryOp(
                        left=x_squared,
                        op='*',
                        right=copy.deepcopy(node.left)
                    )
        
        # Multiplication by power of 2 to bit shift: x * 2 → x << 1
        # unsafe for floats, so only apply if we know it's an int
        if node.op == '*' and isinstance(node.right, schema.Constant):
            # Strict type check for int (no floats like 2.0)
            if type(node.right.value) is int:
                shift_map = {2: 1, 4: 2, 8: 3, 16: 4, 32: 5, 64: 6}
                if node.right.value in shift_map:
                    # Check if left is also known int (Constant int)
                    # If left is variable, we skip to avoid TypeError on floats
                    if isinstance(node.left, schema.Constant) and type(node.left.value) is int:
                        self.changed = True
                        return schema.BinaryOp(
                            left=node.left,
                            op='<<',
                            right=schema.Constant(value=shift_map[node.right.value], kind='int')
                        )
        
        # Also handle left operand being constant: 2 * x → x << 1
        if node.op == '*' and isinstance(node.left, schema.Constant):
            # Strict type check for int
            if type(node.left.value) is int:
                shift_map = {2: 1, 4: 2, 8: 3, 16: 4, 32: 5, 64: 6}
                if node.left.value in shift_map:
                     # Check if right is also known int
                    if isinstance(node.right, schema.Constant) and type(node.right.value) is int:
                        self.changed = True
                        return schema.BinaryOp(
                            left=node.right,
                            op='<<',
                            right=schema.Constant(value=shift_map[node.left.value], kind='int')
                        )
        
        return node


class LoopInvariantMover(NodeTransformer):
    """Moves loop-invariant code outside loops.
    
    A statement is loop-invariant if:
    1. It doesn't use any loop variables (including the loop target)
    2. It doesn't use any variables modified within the loop
    3. It doesn't have side effects (function calls, etc.)
    4. Its target variable is not used before this statement in the loop
    
    This transformer returns a list when hoisting is performed, which NodeTransformer
    handles by flattening into the parent block.
    """
    
    def __init__(self):
        self.changed = False
        self.loop_vars: Set[str] = set()
    
    def visit_For(self, node: schema.For) -> Any:
        """Process for loops to find invariant statements."""
        if isinstance(node.target, schema.Name):
            old_loop_vars = self.loop_vars.copy()
            self.loop_vars.add(node.target.id)
            
            # First pass: collect all variables modified in the loop
            modified_in_loop = self._collect_modified_vars(node.body)
            self.loop_vars.update(modified_in_loop)
            
            # Find invariant statements
            invariant_stmts = []
            remaining_stmts = []
            hoisted_vars: Set[str] = set()
            
            for stmt in node.body.statements:
                can_hoist, stmt_target = self._can_hoist_statement(stmt, hoisted_vars)
                if can_hoist:
                    invariant_stmts.append(stmt)
                    if stmt_target:
                        hoisted_vars.add(stmt_target)
                    self.changed = True
                else:
                    remaining_stmts.append(self.visit(stmt))
            
            node.body.statements = remaining_stmts
            self.loop_vars = old_loop_vars
            
            # Return hoisted statements before the loop
            if invariant_stmts:
                return invariant_stmts + [node]
        
        return self.generic_visit(node)
    
    def _collect_modified_vars(self, block: schema.Block) -> Set[str]:
        """Collect all variables that are assigned within a block."""
        modified = set()
        for stmt in block.statements:
            if isinstance(stmt, schema.Assign):
                for target in stmt.targets:
                    if isinstance(target, schema.Name):
                        modified.add(target.id)
            elif isinstance(stmt, schema.AugAssign):
                if isinstance(stmt.target, schema.Name):
                    modified.add(stmt.target.id)
            elif isinstance(stmt, (schema.For, schema.While)):
                # Recursively check nested loops
                modified.update(self._collect_modified_vars(stmt.body))
            elif isinstance(stmt, schema.If):
                modified.update(self._collect_modified_vars(stmt.body))
                if stmt.orelse:
                    modified.update(self._collect_modified_vars(stmt.orelse))
        return modified
    
    def _can_hoist_statement(self, stmt: schema.Statement, hoisted_vars: Set[str]) -> tuple:
        """Check if a statement can be hoisted out of the loop.
        
        Returns (can_hoist: bool, target_var: Optional[str])
        """
        if isinstance(stmt, schema.Assign):
            # Only consider simple single-target assignments
            if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], schema.Name):
                return False, None
            
            target_name = stmt.targets[0].id
            
            # Don't hoist if target is a loop variable or modified elsewhere
            if target_name in self.loop_vars:
                return False, None
            
            # Don't hoist if RHS has side effects
            if self._has_side_effects(stmt.value):
                return False, None
            
            # Don't hoist if RHS uses loop variables or hoisted variables
            used_vars = self._get_used_vars(stmt.value)
            if used_vars & self.loop_vars:
                return False, None
            if used_vars & hoisted_vars:
                # Depends on another hoisted var - this is fine, as long as 
                # it comes after the dependency
                pass  # Allow this case
            
            return True, target_name
        
        return False, None
    
    def _has_side_effects(self, expr: schema.Expression) -> bool:
        """Check if an expression might have side effects."""
        if isinstance(expr, schema.Call):
            return True
        elif isinstance(expr, schema.Attribute):
            # Could be a property with side effects
            return self._has_side_effects(expr.value)
        elif isinstance(expr, (schema.Constant, schema.Name)):
            return False
        elif isinstance(expr, schema.BinaryOp):
            return self._has_side_effects(expr.left) or self._has_side_effects(expr.right)
        elif isinstance(expr, schema.UnaryOp):
            return self._has_side_effects(expr.operand)
        elif isinstance(expr, (schema.ListExpr, schema.TupleExpr, schema.SetExpr)):
            return any(self._has_side_effects(elt) for elt in expr.elts)
        elif isinstance(expr, schema.Subscript):
            return self._has_side_effects(expr.value) or self._has_side_effects(expr.slice)
        return True  # Conservative for unknown types
    
    def _get_used_vars(self, expr: schema.Expression) -> Set[str]:
        """Get all variables used in an expression."""
        used: Set[str] = set()
        if isinstance(expr, schema.Name):
            if expr.ctx == "Load":
                used.add(expr.id)
        elif isinstance(expr, schema.BinaryOp):
            used.update(self._get_used_vars(expr.left))
            used.update(self._get_used_vars(expr.right))
        elif isinstance(expr, schema.UnaryOp):
            used.update(self._get_used_vars(expr.operand))
        elif isinstance(expr, schema.Compare):
            used.update(self._get_used_vars(expr.left))
            for comp in expr.comparators:
                used.update(self._get_used_vars(comp))
        elif isinstance(expr, schema.Call):
            if isinstance(expr.func, schema.Name):
                pass  # Function names are not variables in our sense
            used.update(self._get_used_vars(expr.func))
            for arg in expr.args:
                used.update(self._get_used_vars(arg))
        elif isinstance(expr, schema.Attribute):
            used.update(self._get_used_vars(expr.value))
        elif isinstance(expr, schema.Subscript):
            used.update(self._get_used_vars(expr.value))
            used.update(self._get_used_vars(expr.slice))
        elif isinstance(expr, (schema.ListExpr, schema.TupleExpr, schema.SetExpr)):
            for elt in expr.elts:
                used.update(self._get_used_vars(elt))
        elif isinstance(expr, schema.DictExpr):
            for k, v in zip(expr.keys, expr.values):
                if k:
                    used.update(self._get_used_vars(k))
                used.update(self._get_used_vars(v))
        elif isinstance(expr, schema.IfExp):
            used.update(self._get_used_vars(expr.test))
            used.update(self._get_used_vars(expr.body))
            used.update(self._get_used_vars(expr.orelse))
        return used


class LoopBoundsOptimizer(NodeTransformer):
    """Optimizes loop bounds and iteration patterns."""
    
    def __init__(self):
        self.changed = False
    
    def visit_For(self, node: schema.For) -> schema.Statement:
        node = self.generic_visit(node)
        
        # Optimize range(0, n) to range(n)
        if (isinstance(node.iter, schema.Call) and 
            isinstance(node.iter.func, schema.Name) and 
            node.iter.func.id == 'range' and 
            len(node.iter.args) == 2):
            
            if (isinstance(node.iter.args[0], schema.Constant) and 
                node.iter.args[0].value == 0):
                self.changed = True
                node.iter.args = [node.iter.args[1]]
        
        return node


class VariableReplacer(NodeTransformer):
    """Replaces variable references with constants."""
    
    def __init__(self, var_name: str, value: Any):
        self.var_name = var_name
        self.value = value
    
    def visit_Name(self, node: schema.Name) -> schema.Expression:
        if node.id == self.var_name and node.ctx == "Load":
            return schema.Constant(value=self.value, kind=type(self.value).__name__)
        return node