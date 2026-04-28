from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class CodeBlockType(Enum):
    """Types of code blocks that can be identified in a function."""

    FOR_LOOP = "for_loop"
    WHILE_LOOP = "while_loop"
    IF_BRANCH = "if_branch"
    ELIF_BRANCH = "elif_branch"
    ELSE_BRANCH = "else_branch"
    ASSIGNMENT = "assignment"
    AUGMENTED_ASSIGNMENT = "augmented_assignment"
    CALL = "function_call"
    LIST_COMPREHENSION = "list_comprehension"
    DICT_COMPREHENSION = "dict_comprehension"
    SET_COMPREHENSION = "set_comprehension"
    GENERATOR_EXPRESSION = "generator_expression"
    TRY_BLOCK = "try_block"
    EXCEPT_BLOCK = "except_block"
    FINALLY_BLOCK = "finally_block"
    WITH_BLOCK = "with_block"
    GENERIC = "generic"


@dataclass
class CodeBlock:
    """Represents a code block within a function with its metadata."""

    block_type: CodeBlockType
    line_start: int
    line_end: int
    description: str
    nesting_level: int = 0
    parent_block: CodeBlock | None = None
    child_blocks: list[CodeBlock] = field(default_factory=list)
    ast_node: ast.AST | None = None

    def contains_line(self, line_num: int) -> bool:
        """Check if a line number falls within this block."""
        return self.line_start <= line_num <= self.line_end

    def add_child(self, child: CodeBlock) -> None:
        """Add a child block and update its parent reference."""
        child.parent_block = self
        child.nesting_level = self.nesting_level + 1
        self.child_blocks.append(child)


@dataclass
class LineMetrics:
    """Metrics for a single line of code."""

    line_num: int
    hits: int
    time_s: float
    time_per_hit_ms: float = 0.0


class FunctionAnalyzer(ast.NodeVisitor):
    """AST visitor that extracts code blocks from a function."""

    def __init__(self, source_lines: list[str]) -> None:
        self.source_lines = source_lines
        self.blocks: list[CodeBlock] = []
        self.current_parent: CodeBlock | None = None
        self.nesting_level = 0

    def _get_description(self, node: ast.AST) -> str:
        """Generate a human-readable description from AST node."""
        if isinstance(node, ast.For):
            # Extract 'for x in y:' pattern
            target = ast.unparse(node.target) if hasattr(ast, "unparse") else "<target>"
            iter_node = ast.unparse(node.iter) if hasattr(ast, "unparse") else "<iterable>"
            return f"for {target} in {iter_node}:"
        elif isinstance(node, ast.While):
            test = ast.unparse(node.test) if hasattr(ast, "unparse") else "<condition>"
            return f"while {test}:"
        elif isinstance(node, ast.If):
            test = ast.unparse(node.test) if hasattr(ast, "unparse") else "<condition>"
            return f"if {test}:"
        elif isinstance(node, ast.Assign):
            targets = ", ".join(
                ast.unparse(t) if hasattr(ast, "unparse") else "<var>" for t in node.targets
            )
            return f"{targets} = ..."
        elif isinstance(node, ast.AugAssign):
            target = ast.unparse(node.target) if hasattr(ast, "unparse") else "<var>"
            return f"{target} <op>= ..."
        elif isinstance(node, ast.Call):
            func = ast.unparse(node.func) if hasattr(ast, "unparse") else "<func>"
            return f"{func}(...)"
        elif isinstance(node, ast.ListComp):
            return "[<list comprehension>]"
        elif isinstance(node, ast.DictComp):
            return "{<dict comprehension>}"
        elif isinstance(node, ast.SetComp):
            return "{<set comprehension>}"
        elif isinstance(node, ast.GeneratorExp):
            return "(<generator expression>)"
        elif isinstance(node, ast.Try):
            return "try:"
        elif isinstance(node, ast.ExceptHandler):
            return f"except {ast.unparse(node.type) if node.type and hasattr(ast, 'unparse') else ''}:"
        elif isinstance(node, ast.With):
            return "with <context>:"
        else:
            return f"<{node.__class__.__name__}>"

    def _get_block_type(self, node: ast.AST) -> CodeBlockType:
        """Map AST node to block type."""
        mapping = {
            ast.For: CodeBlockType.FOR_LOOP,
            ast.While: CodeBlockType.WHILE_LOOP,
            ast.If: CodeBlockType.IF_BRANCH,
            ast.Assign: CodeBlockType.ASSIGNMENT,
            ast.AnnAssign: CodeBlockType.ASSIGNMENT,
            ast.AugAssign: CodeBlockType.AUGMENTED_ASSIGNMENT,
            ast.Call: CodeBlockType.CALL,
            ast.Expr: CodeBlockType.CALL,  # For function calls as expressions
            ast.ListComp: CodeBlockType.LIST_COMPREHENSION,
            ast.DictComp: CodeBlockType.DICT_COMPREHENSION,
            ast.SetComp: CodeBlockType.SET_COMPREHENSION,
            ast.GeneratorExp: CodeBlockType.GENERATOR_EXPRESSION,
            ast.Try: CodeBlockType.TRY_BLOCK,
            ast.ExceptHandler: CodeBlockType.EXCEPT_BLOCK,
            ast.With: CodeBlockType.WITH_BLOCK,
        }
        return mapping.get(type(node), CodeBlockType.GENERIC)

    def _create_block(self, node: ast.AST) -> CodeBlock:
        """Create a CodeBlock from an AST node."""
        block = CodeBlock(
            block_type=self._get_block_type(node),
            line_start=getattr(node, "lineno", 1),
            line_end=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
            description=self._get_description(node),
            nesting_level=self.nesting_level,
            parent_block=self.current_parent,
            ast_node=node,
        )
        return block

    def _is_pure_expression(self, node: ast.AST) -> bool:
        """Check if node is a pure expression (not a statement)."""
        return isinstance(
            node, (ast.Expr, ast.Call, ast.Name, ast.Constant, ast.BinOp, ast.Compare)
        )

    def _is_function_call(self, node: ast.AST) -> bool:
        """Check if node is or contains a function call."""
        if isinstance(node, ast.Call):
            return True
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            return True
        return False

    def visit_For(self, node: ast.For) -> None:
        """Visit for loop node."""
        block = self._create_block(node)
        self.blocks.append(block)

        old_parent = self.current_parent
        old_level = self.nesting_level
        self.current_parent = block
        self.nesting_level += 1

        # Visit body
        for child in node.body:
            self.visit(child)

        # Visit else clause (orelse in AST)
        if node.orelse:
            else_block = CodeBlock(
                block_type=CodeBlockType.ELSE_BRANCH,
                line_start=node.orelse[0].lineno if node.orelse else node.end_lineno or node.lineno,
                line_end=node.orelse[-1].end_lineno or node.orelse[-1].lineno if node.orelse else node.end_lineno or node.lineno,
                description="else:",
                nesting_level=self.nesting_level,
                parent_block=self.current_parent,
            )
            self.blocks.append(else_block)
            self.current_parent = else_block
            for child in node.orelse:
                self.visit(child)
            self.current_parent = block

        self.current_parent = old_parent
        self.nesting_level = old_level

    def visit_While(self, node: ast.While) -> None:
        """Visit while loop node."""
        block = self._create_block(node)
        self.blocks.append(block)

        old_parent = self.current_parent
        old_level = self.nesting_level
        self.current_parent = block
        self.nesting_level += 1

        for child in node.body:
            self.visit(child)

        if node.orelse:
            else_block = CodeBlock(
                block_type=CodeBlockType.ELSE_BRANCH,
                line_start=node.orelse[0].lineno,
                line_end=node.orelse[-1].end_lineno or node.orelse[-1].lineno,
                description="else:",
                nesting_level=self.nesting_level,
                parent_block=self.current_parent,
            )
            self.blocks.append(else_block)
            for child in node.orelse:
                self.visit(child)

        self.current_parent = old_parent
        self.nesting_level = old_level

    def visit_If(self, node: ast.If) -> None:
        """Visit if statement node."""
        block = self._create_block(node)
        self.blocks.append(block)

        old_parent = self.current_parent
        old_level = self.nesting_level
        self.current_parent = block
        self.nesting_level += 1

        for child in node.body:
            self.visit(child)

        self.current_parent = old_parent
        self.nesting_level = old_level

        # Handle elif/else chains
        current = node
        while current.orelse:
            if len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
                # elif
                elif_node = current.orelse[0]
                elif_block = CodeBlock(
                    block_type=CodeBlockType.ELIF_BRANCH,
                    line_start=elif_node.lineno,
                    line_end=elif_node.end_lineno or elif_node.lineno,
                    description=f"elif {self._get_description(elif_node).replace('if ', '')}",
                    nesting_level=old_level,
                    parent_block=old_parent,
                )
                self.blocks.append(elif_block)

                self.current_parent = elif_block
                self.nesting_level = old_level + 1
                for child in elif_node.body:
                    self.visit(child)
                self.current_parent = old_parent
                self.nesting_level = old_level
                current = elif_node
            else:
                # else
                else_block = CodeBlock(
                    block_type=CodeBlockType.ELSE_BRANCH,
                    line_start=current.orelse[0].lineno,
                    line_end=current.orelse[-1].end_lineno or current.orelse[-1].lineno,
                    description="else:",
                    nesting_level=old_level,
                    parent_block=old_parent,
                )
                self.blocks.append(else_block)

                self.current_parent = else_block
                self.nesting_level = old_level + 1
                for child in current.orelse:
                    self.visit(child)
                self.current_parent = old_parent
                self.nesting_level = old_level
                break

    def visit_Try(self, node: ast.Try) -> None:
        """Visit try block."""
        block = self._create_block(node)
        self.blocks.append(block)

        old_parent = self.current_parent
        old_level = self.nesting_level
        self.current_parent = block
        self.nesting_level += 1

        for child in node.body:
            self.visit(child)

        for handler in node.handlers:
            handler_block = CodeBlock(
                block_type=CodeBlockType.EXCEPT_BLOCK,
                line_start=handler.lineno,
                line_end=handler.end_lineno or handler.lineno,
                description=self._get_description(handler),
                nesting_level=self.nesting_level,
                parent_block=block,
            )
            self.blocks.append(handler_block)
            self.current_parent = handler_block
            for child in handler.body:
                self.visit(child)

        if node.finalbody:
            finally_block = CodeBlock(
                block_type=CodeBlockType.FINALLY_BLOCK,
                line_start=node.finalbody[0].lineno,
                line_end=node.finalbody[-1].end_lineno or node.finalbody[-1].lineno,
                description="finally:",
                nesting_level=self.nesting_level,
                parent_block=block,
            )
            self.blocks.append(finally_block)
            self.current_parent = finally_block
            for child in node.finalbody:
                self.visit(child)

        self.current_parent = old_parent
        self.nesting_level = old_level

    def visit_With(self, node: ast.With) -> None:
        """Visit with block."""
        block = self._create_block(node)
        self.blocks.append(block)

        old_parent = self.current_parent
        old_level = self.nesting_level
        self.current_parent = block
        self.nesting_level += 1

        for child in node.body:
            self.visit(child)

        self.current_parent = old_parent
        self.nesting_level = old_level

    def visit_ListComp(self, node: ast.ListComp) -> None:
        """Visit list comprehension."""
        block = self._create_block(node)
        self.blocks.append(block)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        """Visit dict comprehension."""
        block = self._create_block(node)
        self.blocks.append(block)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        """Visit set comprehension."""
        block = self._create_block(node)
        self.blocks.append(block)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        """Visit generator expression."""
        block = self._create_block(node)
        self.blocks.append(block)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Visit assignment."""
        block = self._create_block(node)
        self.blocks.append(block)
        # Don't call generic_visit to avoid double-counting nested calls

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Visit augmented assignment (+=, -=, etc.)."""
        block = self._create_block(node)
        self.blocks.append(block)
        # Don't call generic_visit to avoid double-counting nested calls

    def visit_Expr(self, node: ast.Expr) -> None:
        """Visit expression statement (often function calls)."""
        if self._is_function_call(node):
            block = CodeBlock(
                block_type=CodeBlockType.CALL,
                line_start=getattr(node, "lineno", 1),
                line_end=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                description=self._get_description(node.value if isinstance(node.value, ast.Call) else node),
                nesting_level=self.nesting_level,
                parent_block=self.current_parent,
                ast_node=node,
            )
            self.blocks.append(block)
        # Don't visit children to avoid double-counting


class LineProfilerMapper:
    """Maps line-level profiler output to code blocks."""

    def __init__(self, code_blocks: list[CodeBlock]) -> None:
        self.code_blocks = code_blocks
        self.block_metrics: dict[int, dict[str, Any]] = {}

    def map_line_stats(
        self, line_stats: dict[int, tuple[int, float]]
    ) -> list[dict[str, Any]]:
        """
        Map line-level stats to code blocks.

        Args:
            line_stats: Dict mapping line_number -> (hits, time_s)

        Returns:
            List of code blocks enriched with metrics
        """
        # Sort blocks by line range for efficient lookup
        sorted_blocks = sorted(self.code_blocks, key=lambda b: (b.line_start, -b.line_end))

        # Initialize metrics for each block
        block_data: dict[int, dict[str, Any]] = {}
        for i, block in enumerate(sorted_blocks):
            block_data[i] = {
                "block": block,
                "hits": 0,
                "time_s": 0.0,
                "lines_covered": 0,
                "line_details": [],
            }

        # Aggregate line stats into blocks
        for line_num, (hits, time_s) in line_stats.items():
            # Find the most specific (smallest) block containing this line
            best_block_idx = None
            best_size = float("inf")

            for i, block in enumerate(sorted_blocks):
                if block.contains_line(line_num):
                    size = block.line_end - block.line_start
                    if size < best_size:
                        best_size = size
                        best_block_idx = i

            if best_block_idx is not None:
                data = block_data[best_block_idx]
                data["hits"] += hits
                data["time_s"] += time_s
                data["lines_covered"] += 1
                data["line_details"].append(
                    {"line": line_num, "hits": hits, "time_s": time_s}
                )

        # Convert to enriched block data
        result = []
        total_time = sum(d["time_s"] for d in block_data.values())

        for data in block_data.values():
            if data["lines_covered"] == 0:
                continue

            block = data["block"]
            time_s = data["time_s"]
            hits = data["hits"]

            enriched = {
                "type": block.block_type.value,
                "line_range": [block.line_start, block.line_end],
                "description": block.description,
                "nesting_level": block.nesting_level,
                "hits": hits,
                "time_s": round(time_s, 6),
                "time_per_hit_ms": round((time_s / max(hits, 1)) * 1000, 4),
                "share_of_function": round(time_s / max(total_time, 0.0001), 4),
                "lines_covered": data["lines_covered"],
            }
            result.append(enriched)

        # Sort by time (descending)
        result.sort(key=lambda x: x["time_s"], reverse=True)
        return result


def _dedent_source(source: str) -> str:
    """Remove common leading whitespace from source code.

    This is essential for parsing nested methods and classes where the
    function source has additional indentation from its containing scope.
    """
    lines = source.splitlines()
    if not lines:
        return source

    # Find the minimum indentation of non-blank lines
    indent_levels = []
    for line in lines:
        stripped = line.lstrip()
        if stripped:  # Non-blank line
            indent_levels.append(len(line) - len(stripped))

    if not indent_levels:
        return source

    min_indent = min(indent_levels)
    if min_indent == 0:
        return source

    # Remove common leading whitespace
    dedented_lines = []
    for line in lines:
        if line.strip():  # Non-blank line
            dedented_lines.append(line[min_indent:])
        else:  # Blank line - preserve as is or keep minimal
            dedented_lines.append(line.lstrip())

    return "\n".join(dedented_lines)


def analyze_function_ast(func: Callable[..., Any]) -> list[CodeBlock]:
    """
    Analyze a function using AST to identify code blocks.

    Args:
        func: The function to analyze

    Returns:
        List of CodeBlock objects representing code structure
    """
    try:
        source = inspect.getsource(func)
        source_lines = source.splitlines()
    except (OSError, TypeError) as exc:
        raise ValueError(f"Could not get source for {func}: {exc}") from exc

    # Handle decorated functions - find the actual def
    dedent_source = source
    if source_lines and source_lines[0].lstrip().startswith("@"):
        # Find first non-decorator, non-blank line
        for i, line in enumerate(source_lines):
            stripped = line.lstrip()
            if stripped and not stripped.startswith("@"):
                dedent_source = "\n".join(source_lines[i:])
                break

    # Dedent the source for proper AST parsing of nested methods/classes
    dedent_source = _dedent_source(dedent_source)

    try:
        tree = ast.parse(dedent_source)
    except SyntaxError as exc:
        raise ValueError(f"Could not parse source: {exc}") from exc

    # Find the function definition
    func_def = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_def = node
            break

    if func_def is None:
        raise ValueError("No function definition found in source")

    # Use dedented source lines for line number calculations
    dedented_lines = dedent_source.splitlines()
    analyzer = FunctionAnalyzer(dedented_lines)

    # Calculate offset: map dedented AST line numbers back to original file lines.
    # func.__code__.co_firstlineno is the actual first line in the source file.
    code_obj = getattr(func, "__code__", None)
    if code_obj is not None:
        offset = code_obj.co_firstlineno - func_def.lineno
    else:
        offset = 0

    for node in func_def.body:
        analyzer.visit(node)

    # Adjust line numbers by offset
    for block in analyzer.blocks:
        block.line_start += offset
        block.line_end += offset

    return analyzer.blocks


def map_line_profiler_to_blocks(
    line_stats: dict[int, tuple[int, float]], code_blocks: list[CodeBlock]
) -> list[dict[str, Any]]:
    """
    Map line-level profiler statistics to code blocks.

    Args:
        line_stats: Dictionary mapping line numbers to (hits, time_s)
        code_blocks: List of CodeBlock objects from AST analysis

    Returns:
        List of enriched code block data with metrics
    """
    mapper = LineProfilerMapper(code_blocks)
    return mapper.map_line_stats(line_stats)


def get_function_line_range(func: Callable[..., Any]) -> tuple[int, int]:
    """Get the start and end line numbers of a function."""
    code = getattr(func, "__code__", None)
    if code is None:
        raise ValueError(f"Could not get code object for {func}")

    # Get the start line from the code object
    start_line = code.co_firstlineno

    # Try to get source and find actual end line
    try:
        source = inspect.getsource(func)
        source_lines = source.splitlines()
        # Calculate actual end line accounting for decorators
        end_line = start_line + len(source_lines) - 1
        return (start_line, end_line)
    except (OSError, TypeError):
        # Fallback: estimate based on bytecode length (rough approximation)
        # co_code is bytes of bytecode, not lines, so this is a rough guess
        return (start_line, start_line + 100)  # Conservative estimate
