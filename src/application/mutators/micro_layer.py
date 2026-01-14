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
from src.domain.ir.utils import NodeTransformer
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
    """Eliminates assignments to unused variables."""
    
    def __init__(self):
        self.changed = False
        self.defined_vars = set()
        self.used_vars = set()
    
    def visit_Assign(self, node: schema.Assign) -> Optional[schema.Statement]:
        node = self.generic_visit(node)
        
        # Track variable definitions
        for target in node.targets:
            if isinstance(target, schema.Name):
                self.defined_vars.add(target.id)
        
        return node
    
    def visit_Name(self, node: schema.Name) -> schema.Expression:
        if node.ctx == "Load":
            self.used_vars.add(node.id)
        return node


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
    """Applies strength reduction to loop operations."""
    
    def __init__(self):
        self.changed = False
    
    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Look for multiplication by loop variables that can be converted to addition
        # This is a simplified implementation
        if node.op == '*':
            # Could implement induction variable analysis here
            pass
        
        return node


class LoopInvariantMover(NodeTransformer):
    """Moves loop-invariant code outside loops."""
    
    def __init__(self):
        self.changed = False
        self.loop_vars = set()
    
    def visit_For(self, node: schema.For) -> schema.Statement:
        if isinstance(node.target, schema.Name):
            old_loop_vars = self.loop_vars.copy()
            self.loop_vars.add(node.target.id)
            
            # Find invariant statements
            invariant_stmts = []
            remaining_stmts = []
            
            for stmt in node.body.statements:
                if self._is_loop_invariant(stmt):
                    invariant_stmts.append(stmt)
                    self.changed = True
                else:
                    remaining_stmts.append(stmt)
            
            node.body.statements = remaining_stmts
            self.loop_vars = old_loop_vars
            
            if invariant_stmts:
                return invariant_stmts + [node]
        
        return self.generic_visit(node)
    
    def _is_loop_invariant(self, stmt: schema.Statement) -> bool:
        """Check if a statement is loop-invariant (simplified)."""
        if isinstance(stmt, schema.Assign):
            used_vars = self._get_used_vars(stmt.value)
            return not (used_vars & self.loop_vars)
        return False
    
    def _get_used_vars(self, expr: schema.Expression) -> Set[str]:
        """Get all variables used in an expression."""
        used = set()
        if isinstance(expr, schema.Name):
            used.add(expr.id)
        elif isinstance(expr, schema.BinaryOp):
            used.update(self._get_used_vars(expr.left))
            used.update(self._get_used_vars(expr.right))
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