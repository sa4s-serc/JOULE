"""
MutationContext provides metadata and analysis information to mutators.
This enables intelligent, safe mutations that respect program semantics.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from src.domain.ir import schema
from src.domain.ir.schema import Module, Name


@dataclass
class SymbolInfo:
    """Information about a symbol in the program."""

    name: str
    type_hint: Optional[str] = None
    is_constant: bool = False
    defined_at: Optional[int] = None  # Line number
    used_at: List[int] = field(default_factory=list)  # Line numbers where used


@dataclass
class ScopeInfo:
    """Information about a lexical scope."""

    scope_type: str  # "module", "function", "class", "block"
    parent: Optional["ScopeInfo"] = None
    symbols: Dict[str, SymbolInfo] = field(default_factory=dict)
    children: List["ScopeInfo"] = field(default_factory=list)


class DependencyGraph:
    """
    Tracks data dependencies between statements.
    Used to determine if mutations are semantics-preserving.
    """

    def __init__(self):
        self.dependencies: Dict[int, Set[int]] = {}  # stmt_id -> set of dependent stmt_ids
        self.stmt_defs: Dict[int, Set[str]] = {}  # stmt_id -> variables defined
        self.stmt_uses: Dict[int, Set[str]] = {}  # stmt_id -> variables used

    def add_statement(self, stmt_id: int, defines: Set[str], uses: Set[str]):
        """Register a statement with its definitions and uses."""
        self.stmt_defs[stmt_id] = defines
        self.stmt_uses[stmt_id] = uses
        self.dependencies[stmt_id] = set()

        # Build dependency edges
        for other_id in self.stmt_defs:
            if other_id == stmt_id:
                continue
            # If other defines something we use, we depend on it
            if self.stmt_defs[other_id] & uses:
                self.dependencies[stmt_id].add(other_id)

    def can_swap(self, stmt1_id: int, stmt2_id: int) -> bool:
        """Check if two statements can be safely swapped."""
        # Cannot swap if they have a dependency relationship
        if stmt2_id in self.dependencies.get(stmt1_id, set()):
            return False
        if stmt1_id in self.dependencies.get(stmt2_id, set()):
            return False

        # Check for write-after-read, read-after-write, write-after-write conflicts
        defs1 = self.stmt_defs.get(stmt1_id, set())
        uses1 = self.stmt_uses.get(stmt1_id, set())
        defs2 = self.stmt_defs.get(stmt2_id, set())
        uses2 = self.stmt_uses.get(stmt2_id, set())

        # Write-after-read: stmt1 uses X, stmt2 defines X
        if uses1 & defs2:
            return False
        # Read-after-write: stmt1 defines X, stmt2 uses X
        if defs1 & uses2:
            return False
        # Write-after-write: both define same variable
        if defs1 & defs2:
            return False

        return True


class MutationContext:
    """
    Provides contextual information to mutators.
    This is the "smart" layer that enables safe, semantics-preserving mutations.
    """

    def __init__(self, ir: Module):
        self.ir = ir
        self.symbol_table: Dict[str, SymbolInfo] = {}
        self.scopes: List[ScopeInfo] = []
        self.dependency_graph = DependencyGraph()

        # Build the context
        self._build_symbol_table()
        self._build_dependency_graph()

    def _build_symbol_table(self):
        """Extract all symbols from the IR."""
        # Simple implementation - traverse IR and collect Names
        self._traverse_for_symbols(self.ir)

    def _traverse_for_symbols(self, node):
        """Recursively traverse IR to find symbol definitions and uses."""
        if isinstance(node, Name):
            if node.id not in self.symbol_table:
                self.symbol_table[node.id] = SymbolInfo(name=node.id)

            # Track usage
            if node.ctx == "Load":
                self.symbol_table[node.id].used_at.append(0)  # Simplified

        # Recurse through the IR tree
        if hasattr(node, "__dict__"):
            for value in node.__dict__.values():
                if isinstance(value, list):
                    for item in value:
                        self._traverse_for_symbols(item)
                elif hasattr(value, "__dict__"):
                    self._traverse_for_symbols(value)

    def _build_dependency_graph(self):
        """Analyze data flow to build dependency graph."""
        # This is a simplified version - a full implementation would do
        # more sophisticated data flow analysis

    def get_defined_vars(self, node: schema.IRNode) -> Set[str]:
        """
        Get all variables defined by this node.
        Includes assignments, function/class definitions, imports, etc.
        """
        defined = set()

        # 1. Specialized definitions (stmts that define names directly)
        if isinstance(node, (schema.FunctionDef, schema.AsyncFunctionDef, schema.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, (schema.Import, schema.ImportFrom)):
            for alias in node.names:
                defined.add(alias.asname if alias.asname else alias.name)

        # 2. General definitions (Name context=Store)
        # We traverse the node to find all writes (Store)
        self._collect_names(node, defined, ctx_filter="Store")

        # 3. Deletions (Name context=Del) treated as structural updates
        self._collect_names(node, defined, ctx_filter="Del")

        return defined

    def get_used_vars(self, node: schema.IRNode) -> Set[str]:
        """Get all variables used (read) by this node."""
        used = set()
        self._collect_names(node, used, ctx_filter="Load")
        return used

    def is_pure(self, node: schema.IRNode) -> bool:
        """
        Check if the node is side-effect free.
        Impure: Calls (unless whitelisted), Await, Yield, Raise, Assert,
        Global/Nonlocal modifications, Assignments (NamedExpr), etc.
        """
        SAFE_BUILTINS = {
            "len",
            "range",
            "enumerate",
            "zip",
            "int",
            "float",
            "str",
            "bool",
            "abs",
            "min",
            "max",
            "sum",
            "divmod",
        }

        impure_types = (
            schema.Await,
            schema.Yield,
            schema.YieldFrom,
            schema.Raise,
            schema.Assert,
            schema.Global,
            schema.Nonlocal,
            schema.Delete,
            schema.NamedExpr,
        )

        is_pure = True

        def check(n):
            nonlocal is_pure
            if not is_pure:
                return

            if isinstance(n, impure_types):
                is_pure = False
                return

            # handling Call nodes specifically
            if isinstance(n, schema.Call):
                # check if function is a safe builtin
                if isinstance(n.func, schema.Name) and n.func.id in SAFE_BUILTINS:
                    # check if arguments are pure (will be checked by visitor recursion)
                    pass
                else:
                    # Unknown call -> assumed impure
                    is_pure = False

        self._traverse(node, check)
        return is_pure

    def _collect_names(self, node, result: Set[str], ctx_filter: str = None):
        """Recursively collect all Name nodes."""

        def visitor(n):
            if isinstance(n, schema.Name):
                if ctx_filter is None or n.ctx == ctx_filter:
                    result.add(n.id)

        self._traverse(node, visitor)

    def _traverse(self, node, callback):
        """Generic traversal."""
        callback(node)
        if hasattr(node, "__dict__"):
            for value in node.__dict__.values():
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, schema.IRNode):
                            self._traverse(item, callback)
                elif isinstance(value, schema.IRNode):
                    self._traverse(value, callback)
