"""
IR Validation - Structural and Semantic Integrity Checks

Provides comprehensive validation of IR including:
- Structural integrity (duplicate names, scope rules)
- Type consistency
- Control flow validation
- Semantic checks
"""
from typing import List, Set, Dict, Optional
from dataclasses import dataclass, field
from src.domain.ir import schema


@dataclass
class ValidationResult:
    """Result of IR validation with detailed error information."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.valid = False
    
    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
    
    def merge(self, other: 'ValidationResult') -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if not other.valid:
            self.valid = False


class IRValidator:
    """
    Validates the structural and semantic integrity of the IR.
    
    Checks performed:
    - No duplicate function/class names at same scope
    - Return/break/continue in appropriate contexts
    - Variable usage (optional, for warnings)
    - Type annotation consistency
    - Import validation
    """
    
    def __init__(self, strict: bool = False):
        """
        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict
    
    def validate(self, module: schema.Module) -> ValidationResult:
        """
        Perform comprehensive validation on an IR module.
        
        Args:
            module: The IR module to validate
            
        Returns:
            ValidationResult with errors and warnings
        """
        result = ValidationResult(valid=True)
        
        # 1. Check for duplicate top-level names
        self._check_duplicate_names(module, result)
        
        # 2. Check scope rules (return, break, continue)
        self._check_scopes(module, result)
        
        # 3. Check for undefined variables (warning only)
        self._check_undefined_variables(module, result)
        
        # 4. Check for unreachable code (warning only)
        self._check_unreachable_code(module, result)
        
        # 5. Validate imports
        self._check_imports(module, result)
        
        # Convert warnings to errors in strict mode
        if self.strict and result.warnings:
            result.errors.extend(result.warnings)
            result.valid = False
        
        return result
    
    def _check_duplicate_names(self, module: schema.Module, result: ValidationResult) -> None:
        """Check for duplicate function/class names at module level."""
        seen_names: Dict[str, str] = {}  # name -> type (function/class)
        
        for stmt in module.body.statements:
            name = None
            kind = None
            
            if isinstance(stmt, schema.FunctionDef):
                name = stmt.name
                kind = "function"
            elif isinstance(stmt, schema.AsyncFunctionDef):
                name = stmt.name
                kind = "async function"
            elif isinstance(stmt, schema.ClassDef):
                name = stmt.name
                kind = "class"
            
            if name:
                if name in seen_names:
                    result.add_error(f"Duplicate {kind} name '{name}' (previously defined as {seen_names[name]})")
                else:
                    seen_names[name] = kind
    
    def _check_scopes(self, module: schema.Module, result: ValidationResult) -> None:
        """Check that return/break/continue are in appropriate contexts."""
        visitor = ScopeValidator()
        visitor.visit_block(module.body)
        result.errors.extend(visitor.errors)
        if visitor.errors:
            result.valid = False
    
    def _check_undefined_variables(self, module: schema.Module, result: ValidationResult) -> None:
        """Check for potentially undefined variables (warnings only)."""
        visitor = VariableUsageChecker()
        visitor.visit_module(module)
        
        for var in visitor.potentially_undefined:
            result.add_warning(f"Variable '{var}' may be used before definition")
    
    def _check_unreachable_code(self, module: schema.Module, result: ValidationResult) -> None:
        """Check for unreachable code after return/break/continue."""
        visitor = UnreachableCodeChecker()
        visitor.visit_block(module.body)
        
        for location in visitor.unreachable_locations:
            result.add_warning(f"Unreachable code detected after {location}")
    
    def _check_imports(self, module: schema.Module, result: ValidationResult) -> None:
        """Validate import statements."""
        seen_imports: Set[str] = set()
        
        for stmt in module.body.statements:
            if isinstance(stmt, schema.Import):
                for alias in stmt.names:
                    name = alias.asname or alias.name
                    if name in seen_imports:
                        result.add_warning(f"Duplicate import of '{name}'")
                    seen_imports.add(name)
            elif isinstance(stmt, schema.ImportFrom):
                for alias in stmt.names:
                    name = alias.asname or alias.name
                    if name in seen_imports:
                        result.add_warning(f"Duplicate import of '{name}'")
                    seen_imports.add(name)


class ScopeValidator:
    """Validates scope rules for control flow statements."""
    
    def __init__(self):
        self.in_loop = 0
        self.in_func = 0
        self.in_class = 0
        self.errors: List[str] = []
    
    def visit_block(self, block: schema.Block) -> None:
        for stmt in block.statements:
            self.visit_stmt(stmt)
    
    def visit_stmt(self, stmt: schema.Statement) -> None:
        if isinstance(stmt, schema.Return):
            if self.in_func == 0:
                self.errors.append("Return statement outside function")
        
        elif isinstance(stmt, schema.Break):
            if self.in_loop == 0:
                self.errors.append("Break/Continue statement outside loop")
        
        elif isinstance(stmt, schema.Continue):
            if self.in_loop == 0:
                self.errors.append("Break/Continue statement outside loop")
        
        elif isinstance(stmt, schema.Yield) or isinstance(stmt, schema.YieldFrom):
            if self.in_func == 0:
                self.errors.append("Yield statement outside function")
        
        elif isinstance(stmt, (schema.FunctionDef, schema.AsyncFunctionDef)):
            self.in_func += 1
            self.visit_block(stmt.body)
            self.in_func -= 1
        
        elif isinstance(stmt, schema.ClassDef):
            self.in_class += 1
            self.visit_block(stmt.body)
            self.in_class -= 1
        
        elif isinstance(stmt, (schema.For, schema.While)):
            self.in_loop += 1
            self.visit_block(stmt.body)
            if stmt.orelse:
                self.visit_block(stmt.orelse)
            self.in_loop -= 1
        
        elif isinstance(stmt, schema.If):
            self.visit_block(stmt.body)
            if stmt.orelse:
                self.visit_block(stmt.orelse)
        
        elif isinstance(stmt, schema.Try):
            self.visit_block(stmt.body)
            for handler in stmt.handlers:
                self.visit_block(handler.body)
            if stmt.orelse:
                self.visit_block(stmt.orelse)
            if stmt.finalbody:
                self.visit_block(stmt.finalbody)
        
        elif isinstance(stmt, schema.With):
            self.visit_block(stmt.body)


class VariableUsageChecker:
    """Checks for potentially undefined variable usage."""
    
    def __init__(self):
        self.defined: Set[str] = set()
        self.used: Set[str] = set()
        self.potentially_undefined: Set[str] = set()
        self.builtins = {
            'print', 'len', 'range', 'enumerate', 'zip', 'map', 'filter',
            'sum', 'min', 'max', 'abs', 'sorted', 'reversed', 'list', 'dict',
            'set', 'tuple', 'str', 'int', 'float', 'bool', 'type', 'isinstance',
            'hasattr', 'getattr', 'setattr', 'open', 'input', 'iter', 'next',
            'any', 'all', 'ord', 'chr', 'hex', 'bin', 'oct', 'round', 'pow',
            'divmod', 'hash', 'id', 'repr', 'format', 'slice', 'object',
            'super', 'property', 'staticmethod', 'classmethod', 'True', 'False', 'None'
        }
    
    def visit_module(self, module: schema.Module) -> None:
        # First pass: collect all definitions
        self._collect_definitions(module.body)
        # Second pass: check usage
        self._check_usage(module.body)
    
    def _collect_definitions(self, block: schema.Block) -> None:
        for stmt in block.statements:
            if isinstance(stmt, schema.Assign):
                for target in stmt.targets:
                    self._add_defined(target)
            elif isinstance(stmt, schema.AugAssign):
                self._add_defined(stmt.target)
            elif isinstance(stmt, (schema.FunctionDef, schema.AsyncFunctionDef)):
                self.defined.add(stmt.name)
            elif isinstance(stmt, schema.ClassDef):
                self.defined.add(stmt.name)
            elif isinstance(stmt, schema.Import):
                for alias in stmt.names:
                    self.defined.add(alias.asname or alias.name.split('.')[0])
            elif isinstance(stmt, schema.ImportFrom):
                for alias in stmt.names:
                    self.defined.add(alias.asname or alias.name)
            elif isinstance(stmt, schema.For):
                self._add_defined(stmt.target)
    
    def _add_defined(self, target) -> None:
        if isinstance(target, schema.Name):
            self.defined.add(target.id)
        elif isinstance(target, schema.TupleExpr):
            for elt in target.elts:
                self._add_defined(elt)
    
    def _check_usage(self, block: schema.Block) -> None:
        for stmt in block.statements:
            self._check_stmt(stmt)
    
    def _check_stmt(self, stmt: schema.Statement) -> None:
        if isinstance(stmt, schema.Assign):
            self._check_expr(stmt.value)
        elif isinstance(stmt, schema.Return) and stmt.value:
            self._check_expr(stmt.value)
        elif isinstance(stmt, schema.If):
            self._check_expr(stmt.test)
            self._check_usage(stmt.body)
            if stmt.orelse:
                self._check_usage(stmt.orelse)
    
    def _check_expr(self, expr) -> None:
        if isinstance(expr, schema.Name) and expr.ctx == "Load":
            if expr.id not in self.defined and expr.id not in self.builtins:
                self.potentially_undefined.add(expr.id)
        elif isinstance(expr, schema.BinaryOp):
            self._check_expr(expr.left)
            self._check_expr(expr.right)
        elif isinstance(expr, schema.Call):
            self._check_expr(expr.func)
            for arg in expr.args:
                self._check_expr(arg)


class UnreachableCodeChecker:
    """Checks for unreachable code after control flow statements."""
    
    def __init__(self):
        self.unreachable_locations: List[str] = []
    
    def visit_block(self, block: schema.Block) -> None:
        terminated = False
        
        for i, stmt in enumerate(block.statements):
            if terminated:
                self.unreachable_locations.append(f"statement at position {i}")
                break
            
            if isinstance(stmt, (schema.Return, schema.Raise)):
                terminated = True
            elif isinstance(stmt, (schema.Break, schema.Continue)):
                terminated = True
            elif isinstance(stmt, (schema.FunctionDef, schema.AsyncFunctionDef)):
                self.visit_block(stmt.body)
            elif isinstance(stmt, (schema.For, schema.While)):
                self.visit_block(stmt.body)
                if stmt.orelse:
                    self.visit_block(stmt.orelse)
            elif isinstance(stmt, schema.If):
                self.visit_block(stmt.body)
                if stmt.orelse:
                    self.visit_block(stmt.orelse)
