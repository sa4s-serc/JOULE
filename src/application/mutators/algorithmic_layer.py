"""
Algorithmic Layer Mutators - Data Structures and Complexity Improvements

These mutators focus on:
- Data structure selection and optimization
- Algorithm complexity improvements
- Memory access pattern optimization
- Computational efficiency enhancements
"""
import copy
import logging
from typing import List, Optional, Set
from src.application.mutators.ir_mutator_base import IROnlyMutator, IRTransformerBase
from src.application.mutators.base import MutationLayer, MutationResult, create_mutation_result, safe_deepcopy_ir
from src.domain.ir import schema
from src.domain.ir.utils import NodeTransformer, collect_names

logger = logging.getLogger(__name__)


class DataStructureOptimizer(IROnlyMutator):
    """
    Optimizes data structure selection for better algorithmic performance.
    
    Focuses on choosing the right data structure for the access patterns
    and operations performed in the code.
    """
    
    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.ALGORITHMIC, enabled_strategies)
    
    def get_available_strategies(self) -> List[str]:
        return [
            "DataStructure_MembershipOptimization",
            "DataStructure_AccessPatternOptimization", 
            "DataStructure_InsertionOptimization",
            "DataStructure_SearchOptimization"
        ]
    
    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply data structure optimization mutations."""
        results = []
        
        # Strategy 1: Membership Testing Optimization (list -> set)
        if self._is_strategy_enabled("DataStructure_MembershipOptimization"):
            transformer = self._create_ir_transformer(MembershipOptimizationTransformer)
            result = self._apply_transformer(
                ir, transformer,
                "DataStructure_MembershipOptimization",
                "Optimized membership testing from O(n) to O(1) using sets",
                confidence=0.95
            )
            if result:
                results.append(result)
        
        # Strategy 2: Access Pattern Optimization
        if self._is_strategy_enabled("DataStructure_AccessPatternOptimization"):
            transformer = self._create_ir_transformer(AccessPatternOptimizer)
            result = self._apply_transformer(
                ir, transformer,
                "DataStructure_AccessPatternOptimization",
                "Optimized data access patterns for better cache locality",
                confidence=0.8
            )
            if result:
                results.append(result)
        
        # Strategy 3: Insertion/Deletion Optimization
        if self._is_strategy_enabled("DataStructure_InsertionOptimization"):
            transformer = self._create_ir_transformer(InsertionDeletionOptimizer)
            result = self._apply_transformer(
                ir, transformer,
                "DataStructure_InsertionOptimization",
                "Optimized insertion/deletion operations using appropriate data structures",
                confidence=0.85
            )
            if result:
                results.append(result)
        
        # Strategy 4: Search Operation Optimization
        if self._is_strategy_enabled("DataStructure_SearchOptimization"):
            transformer = self._create_ir_transformer(SearchOptimizationTransformer)
            result = self._apply_transformer(
                ir, transformer,
                "DataStructure_SearchOptimization",
                "Optimized search operations using efficient algorithms and data structures",
                confidence=0.9
            )
            if result:
                results.append(result)
        
        return results

class ComplexityReducer(IROnlyMutator):
    """
    Reduces algorithmic complexity through better algorithm selection.
    
    Identifies opportunities to replace high-complexity operations with
    more efficient alternatives.
    """
    
    def __init__(self, enabled_strategies: Optional[Set[str]] = None):
        super().__init__(MutationLayer.ALGORITHMIC, enabled_strategies)
    
    def get_available_strategies(self) -> List[str]:
        return [
            "Complexity_NestedLoopReduction",
            "Complexity_SortingOptimization",
            "Complexity_DuplicateWorkElimination",
            "Complexity_MathematicalOptimization"
        ]
    
    def _apply_ir_mutations(self, ir: schema.Module) -> List[MutationResult]:
        """Apply complexity reduction mutations."""
        results = []
        
        # Strategy 1: Nested Loop Reduction
        if self._is_strategy_enabled("Complexity_NestedLoopReduction"):
            variant = self._reduce_nested_loops(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Complexity_NestedLoopReduction",
                    layer=MutationLayer.ALGORITHMIC,
                    confidence=0.8,
                    description="Reduced nested loop complexity using mathematical optimization"
                ))
        
        # Strategy 2: Sorting Optimization
        if self._is_strategy_enabled("Complexity_SortingOptimization"):
            variant = self._optimize_sorting_operations(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Complexity_SortingOptimization",
                    layer=MutationLayer.ALGORITHMIC,
                    confidence=0.9,
                    description="Optimized sorting operations for better complexity"
                ))
        
        # Strategy 3: Duplicate Work Elimination
        if self._is_strategy_enabled("Complexity_DuplicateWorkElimination"):
            variant = self._eliminate_duplicate_work(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Complexity_DuplicateWorkElimination",
                    layer=MutationLayer.ALGORITHMIC,
                    confidence=0.85,
                    description="Eliminated duplicate computations and redundant work"
                ))
        
        # Strategy 4: Mathematical Optimization
        if self._is_strategy_enabled("Complexity_MathematicalOptimization"):
            variant = self._apply_mathematical_optimizations(ir)
            if variant:
                results.append(create_mutation_result(
                    ir=variant,
                    strategy_name="Complexity_MathematicalOptimization",
                    layer=MutationLayer.ALGORITHMIC,
                    confidence=0.7,
                    description="Applied mathematical optimizations to reduce computational complexity"
                ))
        
        return results
    
    def _reduce_nested_loops(self, ir: schema.Module) -> Optional[schema.Module]:
        """Reduce nested loop complexity where possible."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = NestedLoopReducer()
        transformer.visit(new_ir)
        
        if transformer.changed and transformer.needs_itertools_import:
            self._ensure_import(new_ir, 'itertools')
        
        return new_ir if transformer.changed else None
    
    def _optimize_sorting_operations(self, ir: schema.Module) -> Optional[schema.Module]:
        """Optimize sorting operations for better performance."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = SortingOptimizer()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _eliminate_duplicate_work(self, ir: schema.Module) -> Optional[schema.Module]:
        """Eliminate duplicate computations and redundant work."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = DuplicateWorkEliminator()
        transformer.visit(new_ir)
        return new_ir if transformer.changed else None
    
    def _apply_mathematical_optimizations(self, ir: schema.Module) -> Optional[schema.Module]:
        """Apply mathematical optimizations to reduce complexity."""
        new_ir = safe_deepcopy_ir(ir)
        transformer = MathematicalOptimizer()
        transformer.visit(new_ir)
        
        if transformer.changed and transformer.needs_math_import:
            self._ensure_import(new_ir, 'math')
        
        return new_ir if transformer.changed else None
    
    def _ensure_import(self, ir: schema.Module, module_name: str):
        """Ensure a module is imported."""
        # Check if already imported
        for stmt in ir.body.statements:
            if isinstance(stmt, schema.Import):
                for alias in stmt.names:
                    if alias.name == module_name:
                        return
        
        # Add import at the beginning
        import_stmt = schema.Import(names=[schema.Alias(name=module_name)])
        ir.body.statements.insert(0, import_stmt)


class MembershipOptimizationTransformer(IRTransformerBase):
    """Optimizes membership testing operations."""
    
    def __init__(self):
        self.changed = False
    
    def visit_Compare(self, node: schema.Compare) -> schema.Expression:
        node = self.generic_visit(node)
        
        if (len(node.ops) == 1 and node.ops[0] in ('in', 'not in') and 
            len(node.comparators) == 1 and isinstance(node.comparators[0], schema.ListExpr)):
            
            list_expr = node.comparators[0]
            # Convert to set if all elements are constants (hashable)
            if all(isinstance(elt, schema.Constant) for elt in list_expr.elts):
                self.changed = True
                node.comparators[0] = schema.SetExpr(elts=list_expr.elts)
        
        return node


class AccessPatternOptimizer(NodeTransformer):
    """Optimizes data access patterns."""
    
    def __init__(self):
        self.changed = False
    
    def visit_For(self, node: schema.For) -> schema.Statement:
        node = self.generic_visit(node)
        
        # Look for patterns like: for i in range(len(arr)): use arr[i]
        # These can often be optimized to: for item in arr: use item
        if (isinstance(node.iter, schema.Call) and 
            isinstance(node.iter.func, schema.Name) and 
            node.iter.func.id == 'range' and 
            len(node.iter.args) == 1):
            
            range_arg = node.iter.args[0]
            if (isinstance(range_arg, schema.Call) and 
                isinstance(range_arg.func, schema.Name) and 
                range_arg.func.id == 'len'):
                
                # This is range(len(something)) - potential optimization target
                # For now, we'll mark it as changed but not implement the full transformation
                # as it requires more sophisticated analysis
                pass
        
        return node


class InsertionDeletionOptimizer(NodeTransformer):
    """Optimizes insertion and deletion operations."""
    
    def __init__(self):
        self.changed = False
        self.needs_collections_import = False
    
    def visit_Call(self, node: schema.Call) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Look for list.insert(0, item) or list.pop(0) patterns
        if (isinstance(node.func, schema.Attribute) and 
            node.func.attr in ('insert', 'pop')):
            
            if (node.func.attr == 'insert' and len(node.args) >= 2 and
                isinstance(node.args[0], schema.Constant) and node.args[0].value == 0):
                # This is insert(0, item) - could benefit from deque
                # Mark for potential optimization
                pass
            elif (node.func.attr == 'pop' and len(node.args) >= 1 and
                  isinstance(node.args[0], schema.Constant) and node.args[0].value == 0):
                # This is pop(0) - could benefit from deque
                # Mark for potential optimization
                pass
        
        return node


class SearchOptimizationTransformer(NodeTransformer):
    """Optimizes search operations."""
    
    def __init__(self):
        self.changed = False
        self.needs_bisect_import = False
    
    def visit_For(self, node: schema.For) -> schema.Statement:
        node = self.generic_visit(node)
        
        # Look for linear search patterns in sorted data
        # This would require more sophisticated analysis to detect
        # sorted data and linear search patterns
        
        return node


class NestedLoopReducer(NodeTransformer):
    """Reduces nested loop complexity."""
    
    def __init__(self):
        self.changed = False
        self.needs_itertools_import = False
    
    def visit_For(self, node: schema.For) -> schema.Statement:
        node = self.generic_visit(node)
        
        # Look for nested loops that can be converted to itertools.product
        if (len(node.body.statements) == 1 and 
            isinstance(node.body.statements[0], schema.For)):
            
            inner_loop = node.body.statements[0]
            
            # Check if loops are independent
            # Must ensure outer loop variables are not used in inner loop iterable
            
            # Get outer loop variables
            outer_vars = set()
            if isinstance(node.target, schema.Name):
                outer_vars.add(node.target.id)
            elif isinstance(node.target, schema.TupleExpr):
                # Handle tuple unpacking in for loop target
                for elt in node.target.elts:
                    if isinstance(elt, schema.Name):
                        outer_vars.add(elt.id)
            
            # Check dependency
            # We check if any of outer_vars appear in inner_loop.iter
            inner_iter_vars = collect_names(inner_loop.iter, ctx_filter="Load")
            
            # If there is an intersection, loops are dependent -> cannot use product
            is_dependent = not outer_vars.isdisjoint(inner_iter_vars)
            
            if (not is_dependent and
                isinstance(node.target, schema.Name) and 
                isinstance(inner_loop.target, schema.Name) and
                node.target.id != inner_loop.target.id):
                
                # Convert to itertools.product
                self.changed = True
                self.needs_itertools_import = True
                
                product_call = schema.Call(
                    func=schema.Attribute(value=schema.Name(id='itertools'), attr='product'),
                    args=[node.iter, inner_loop.iter]
                )
                
                tuple_target = schema.TupleExpr(
                    elts=[node.target, inner_loop.target],
                    ctx="Store"
                )
                
                return schema.For(
                    target=tuple_target,
                    iter=product_call,
                    body=inner_loop.body,
                    orelse=None
                )
        
        return node


class SortingOptimizer(NodeTransformer):
    """Optimizes sorting operations."""
    
    def __init__(self):
        self.changed = False
    
    def visit_Call(self, node: schema.Call) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Look for sorting operations that can be optimized
        if (isinstance(node.func, schema.Attribute) and 
            node.func.attr == 'sort'):
            # Could add key function optimizations or algorithm selection
            pass
        elif (isinstance(node.func, schema.Name) and 
              node.func.id == 'sorted'):
            # Could optimize sorted() calls
            pass
        
        return node


class DuplicateWorkEliminator(NodeTransformer):
    """Eliminates duplicate computations."""
    
    def __init__(self):
        self.changed = False
        self.seen_expressions = {}
    
    def visit_Assign(self, node: schema.Assign) -> schema.Statement:
        node = self.generic_visit(node)
        
        # Track expressions to identify duplicates
        expr_hash = self._hash_expression(node.value)
        if expr_hash and expr_hash in self.seen_expressions:
            # Found duplicate computation - could optimize
            pass
        elif expr_hash:
            self.seen_expressions[expr_hash] = node
        
        return node
    
    def _hash_expression(self, expr: schema.Expression) -> Optional[str]:
        """Create a simple hash for expressions."""
        if isinstance(expr, schema.BinaryOp):
            left_hash = self._hash_expression(expr.left)
            right_hash = self._hash_expression(expr.right)
            if left_hash and right_hash:
                return f"BinOp({expr.op},{left_hash},{right_hash})"
        elif isinstance(expr, schema.Name):
            return f"Name({expr.id})"
        elif isinstance(expr, schema.Constant):
            return f"Const({expr.value})"
        return None


class MathematicalOptimizer(NodeTransformer):
    """Applies mathematical optimizations."""
    
    def __init__(self):
        self.changed = False
        self.needs_math_import = False
    
    def visit_BinaryOp(self, node: schema.BinaryOp) -> schema.Expression:
        node = self.generic_visit(node)
        
        # Mathematical optimizations
        if node.op == '**' and isinstance(node.right, schema.Constant):
            if node.right.value == 0.5:
                # x ** 0.5 -> math.sqrt(x)
                self.changed = True
                self.needs_math_import = True
                return schema.Call(
                    func=schema.Attribute(value=schema.Name(id='math'), attr='sqrt'),
                    args=[node.left]
                )
        
        return node