import ast
import sys
from typing import Any, List, Optional

from src.domain.ir import schema


class PythonParser:
    """
    Converts Python source code (via AST) into Strict IR.
    """

    def parse(self, code: str) -> schema.Module:
        tree = ast.parse(code, type_comments=True)
        return self._visit_module(tree)

    def _visit_module(self, node: ast.Module) -> schema.Module:
        return schema.Module(
            body=self._visit_block(node.body),
            type_ignores=[str(ignore) for ignore in node.type_ignores],
        )

    def _attach_loc(self, ir_node: schema.IRNode, ast_node: Any) -> schema.IRNode:
        """Attach source location metadata if available."""
        if hasattr(ast_node, "lineno"):
            ir_node.lineno = ast_node.lineno
        if hasattr(ast_node, "col_offset"):
            ir_node.col_offset = ast_node.col_offset
        if hasattr(ast_node, "end_lineno"):
            ir_node.end_lineno = ast_node.end_lineno
        if hasattr(ast_node, "end_col_offset"):
            ir_node.end_col_offset = ast_node.end_col_offset
        return ir_node

    def _visit_block(self, stmts: List[ast.stmt]) -> schema.Block:
        ir_stmts = []
        for stmt in stmts:
            ir_stmt = self._visit_stmt(stmt)
            if ir_stmt:
                ir_stmts.append(ir_stmt)
        # Block doesn't have direct mapping to a single AST node usually,
        # unless it is a body list. We usually don't attach loc to Block.
        return schema.Block(statements=ir_stmts)

    # --- Helper Visitors ---

    def _visit_arg(self, node: ast.arg) -> schema.Arg:
        return self._attach_loc(
            schema.Arg(
                arg=node.arg,
                annotation=self._visit_expr(node.annotation) if node.annotation else None,
                type_comment=node.type_comment,
            ),
            node,
        )

    def _visit_arguments(self, node: ast.arguments) -> schema.Arguments:
        return schema.Arguments(
            posonlyargs=[self._visit_arg(a) for a in node.posonlyargs],
            args=[self._visit_arg(a) for a in node.args],
            vararg=self._visit_arg(node.vararg) if node.vararg else None,
            kwonlyargs=[self._visit_arg(a) for a in node.kwonlyargs],
            kw_defaults=[self._visit_expr(d) if d else None for d in node.kw_defaults],
            kwarg=self._visit_arg(node.kwarg) if node.kwarg else None,
            defaults=[self._visit_expr(d) for d in node.defaults],
        )

    def _visit_keyword(self, node: ast.keyword) -> schema.Keyword:
        return self._attach_loc(
            schema.Keyword(arg=node.arg, value=self._visit_expr(node.value)), node
        )

    def _visit_alias(self, node: ast.alias) -> schema.Alias:
        # ast.alias usually doesn't have location info?
        # But we'll try just in case provided by some parsers or future versions
        return self._attach_loc(schema.Alias(name=node.name, asname=node.asname), node)

    def _visit_comprehension(self, node: ast.comprehension) -> schema.Comprehension:
        return self._attach_loc(
            schema.Comprehension(
                target=self._visit_expr(node.target),
                iter=self._visit_expr(node.iter),
                ifs=[self._visit_expr(if_expr) for if_expr in node.ifs],
                is_async=node.is_async,
            ),
            node,
        )

    def _visit_match_case(self, node: ast.match_case) -> schema.MatchCase:
        return self._attach_loc(
            schema.MatchCase(
                pattern=self._visit_pattern(node.pattern),
                guard=self._visit_expr(node.guard) if node.guard else None,
                body=[self._visit_stmt(s) for s in node.body],
            ),
            node,
        )

    def _visit_pattern(self, node: ast.pattern) -> schema.Pattern:
        """Convert AST pattern to IR Pattern."""
        p = self._visit_pattern_inner(node)
        return self._attach_loc(p, node)

    def _visit_pattern_inner(self, node: ast.pattern) -> schema.Pattern:
        if isinstance(node, ast.MatchValue):
            return schema.MatchValue(value=self._visit_expr(node.value))
        elif isinstance(node, ast.MatchSingleton):
            return schema.MatchSingleton(value=node.value)
        elif isinstance(node, ast.MatchSequence):
            return schema.MatchSequence(patterns=[self._visit_pattern(p) for p in node.patterns])
        elif isinstance(node, ast.MatchMapping):
            return schema.MatchMapping(
                keys=[self._visit_expr(k) for k in node.keys],
                patterns=[self._visit_pattern(p) for p in node.patterns],
                rest=node.rest,
            )
        elif isinstance(node, ast.MatchClass):
            return schema.MatchClass(
                cls=self._visit_expr(node.cls),
                patterns=[self._visit_pattern(p) for p in node.patterns],
                kwd_attrs=node.kwd_attrs,
                kwd_patterns=[self._visit_pattern(p) for p in node.kwd_patterns],
            )
        elif isinstance(node, ast.MatchStar):
            return schema.MatchStar(name=node.name)
        elif isinstance(node, ast.MatchAs):
            return schema.MatchAs(
                pattern=self._visit_pattern(node.pattern) if node.pattern else None, name=node.name
            )
        elif isinstance(node, ast.MatchOr):
            return schema.MatchOr(patterns=[self._visit_pattern(p) for p in node.patterns])

        # Fallback/Placeholder if unknown
        return schema.Pattern()

    def _visit_with_item(self, node: ast.withitem) -> schema.WithItem:
        return self._attach_loc(
            schema.WithItem(
                context_expr=self._visit_expr(node.context_expr),
                optional_vars=self._visit_expr(node.optional_vars) if node.optional_vars else None,
            ),
            node,
        )

    def _visit_except_handler(self, node: ast.ExceptHandler) -> schema.ExceptHandler:
        return self._attach_loc(
            schema.ExceptHandler(
                type=self._visit_expr(node.type) if node.type else None,
                name=node.name,
                body=self._visit_block(node.body),
            ),
            node,
        )

    # --- Statement Visitor ---

    def _visit_stmt(self, node: ast.stmt) -> Optional[schema.Statement]:
        ir_stmt = self._visit_stmt_inner(node)
        if ir_stmt:
            self._attach_loc(ir_stmt, node)
        return ir_stmt

    def _visit_stmt_inner(self, node: ast.stmt) -> Optional[schema.Statement]:
        if isinstance(node, ast.Assign):
            return schema.Assign(
                targets=[self._visit_expr(t) for t in node.targets],
                value=self._visit_expr(node.value),
                type_comment=node.type_comment,
            )
        elif isinstance(node, ast.AnnAssign):
            return schema.AnnAssign(
                target=self._visit_expr(node.target),
                annotation=self._visit_expr(node.annotation),
                value=self._visit_expr(node.value) if node.value else None,
                simple=node.simple,
            )
        elif isinstance(node, ast.AugAssign):
            return schema.AugAssign(
                target=self._visit_expr(node.target),
                op=self._get_op_name(node.op),
                value=self._visit_expr(node.value),
            )
        elif isinstance(node, ast.Raise):
            return schema.Raise(
                exc=self._visit_expr(node.exc) if node.exc else None,
                cause=self._visit_expr(node.cause) if node.cause else None,
            )
        elif isinstance(node, ast.Assert):
            return schema.Assert(
                test=self._visit_expr(node.test),
                msg=self._visit_expr(node.msg) if node.msg else None,
            )
        elif isinstance(node, ast.Delete):
            return schema.Delete(targets=[self._visit_expr(t) for t in node.targets])
        elif isinstance(node, ast.Return):
            return schema.Return(value=self._visit_expr(node.value) if node.value else None)
        elif isinstance(node, ast.Pass):
            return schema.Pass()
        elif isinstance(node, ast.Break):
            return schema.Break()
        elif isinstance(node, ast.Continue):
            return schema.Continue()
        elif isinstance(node, ast.Global):
            return schema.Global(names=node.names)
        elif isinstance(node, ast.Nonlocal):
            return schema.Nonlocal(names=node.names)
        elif isinstance(node, ast.Expr):
            return schema.ExprStmt(value=self._visit_expr(node.value))
        elif isinstance(node, ast.If):
            return schema.If(
                test=self._visit_expr(node.test),
                body=self._visit_block(node.body),
                orelse=self._visit_block(node.orelse) if node.orelse else None,
            )
        elif isinstance(node, ast.Match):
            return schema.Match(
                subject=self._visit_expr(node.subject),
                cases=[self._visit_match_case(c) for c in node.cases],
            )
        elif isinstance(node, ast.While):
            return schema.While(
                test=self._visit_expr(node.test),
                body=self._visit_block(node.body),
                orelse=self._visit_block(node.orelse) if node.orelse else None,
            )
        elif isinstance(node, ast.For):
            return schema.For(
                target=self._visit_expr(node.target),
                iter=self._visit_expr(node.iter),
                body=self._visit_block(node.body),
                orelse=self._visit_block(node.orelse) if node.orelse else None,
                type_comment=node.type_comment,
            )
        elif isinstance(node, ast.AsyncFor):
            return schema.AsyncFor(
                target=self._visit_expr(node.target),
                iter=self._visit_expr(node.iter),
                body=self._visit_block(node.body),
                orelse=self._visit_block(node.orelse) if node.orelse else None,
                type_comment=node.type_comment,
            )
        elif isinstance(node, ast.FunctionDef):
            return schema.FunctionDef(
                name=node.name,
                args=self._visit_arguments(node.args),
                body=self._visit_block(node.body),
                decorator_list=[self._visit_expr(d) for d in node.decorator_list],
                returns=self._visit_expr(node.returns) if node.returns else None,
                type_comment=node.type_comment,
            )
        elif isinstance(node, ast.AsyncFunctionDef):
            return schema.AsyncFunctionDef(
                name=node.name,
                args=self._visit_arguments(node.args),
                body=self._visit_block(node.body),
                decorator_list=[self._visit_expr(d) for d in node.decorator_list],
                returns=self._visit_expr(node.returns) if node.returns else None,
                type_comment=node.type_comment,
            )
        elif isinstance(node, ast.ClassDef):
            return schema.ClassDef(
                name=node.name,
                bases=[self._visit_expr(b) for b in node.bases],
                keywords=[self._visit_keyword(k) for k in node.keywords],
                body=self._visit_block(node.body),
                decorator_list=[self._visit_expr(d) for d in node.decorator_list],
            )
        elif isinstance(node, ast.Import):
            return schema.Import(names=[self._visit_alias(n) for n in node.names])
        elif isinstance(node, ast.ImportFrom):
            return schema.ImportFrom(
                module=node.module,
                names=[self._visit_alias(n) for n in node.names],
                level=node.level,
            )
        elif isinstance(node, ast.Try):
            return schema.Try(
                body=self._visit_block(node.body),
                handlers=[self._visit_except_handler(h) for h in node.handlers],
                orelse=self._visit_block(node.orelse) if node.orelse else None,
                finalbody=self._visit_block(node.finalbody) if node.finalbody else None,
            )
        elif sys.version_info >= (3, 11) and isinstance(node, ast.TryStar):
            return schema.TryStar(
                body=self._visit_block(node.body),
                handlers=[self._visit_except_handler(h) for h in node.handlers],
                orelse=self._visit_block(node.orelse) if node.orelse else None,
                finalbody=self._visit_block(node.finalbody) if node.finalbody else None,
            )
        elif isinstance(node, ast.With):
            return schema.With(
                items=[self._visit_with_item(i) for i in node.items],
                body=self._visit_block(node.body),
                type_comment=node.type_comment,
            )
        elif isinstance(node, ast.AsyncWith):
            return schema.AsyncWith(
                items=[self._visit_with_item(i) for i in node.items],
                body=self._visit_block(node.body),
                type_comment=node.type_comment,
            )

        return None  # Unsupported statement

    # --- Expression Visitor ---

    def _visit_expr(self, node: ast.expr) -> schema.Expression:
        """Visit an expression node and attach metadata."""
        ir_expr = self._visit_expr_inner(node)
        self._attach_loc(ir_expr, node)
        return ir_expr

    def _visit_expr_inner(self, node: ast.expr) -> schema.Expression:
        if isinstance(node, ast.Constant):
            kind = "None"
            if isinstance(node.value, bool):
                kind = "bool"
            elif isinstance(node.value, int):
                kind = "int"
            elif isinstance(node.value, float):
                kind = "float"
            elif isinstance(node.value, str):
                kind = "str"
            return schema.Constant(value=node.value, kind=kind)
        elif isinstance(node, ast.Name):
            return schema.Name(id=node.id, ctx=type(node.ctx).__name__)
        elif isinstance(node, ast.BinOp):
            return schema.BinaryOp(
                left=self._visit_expr(node.left),
                op=self._get_op_name(node.op),
                right=self._visit_expr(node.right),
            )
        elif isinstance(node, ast.UnaryOp):
            return schema.UnaryOp(
                op=self._get_op_name(node.op), operand=self._visit_expr(node.operand)
            )
        elif isinstance(node, ast.BoolOp):
            return schema.BoolOp(
                op=self._get_op_name(node.op), values=[self._visit_expr(v) for v in node.values]
            )
        elif isinstance(node, ast.Compare):
            return schema.Compare(
                left=self._visit_expr(node.left),
                ops=[self._get_op_name(op) for op in node.ops],
                comparators=[self._visit_expr(c) for c in node.comparators],
            )
        elif isinstance(node, ast.Call):
            return schema.Call(
                func=self._visit_expr(node.func),
                args=[self._visit_expr(a) for a in node.args],
                keywords=[(k.arg, self._visit_expr(k.value)) for k in node.keywords],
            )
        elif isinstance(node, ast.Attribute):
            return schema.Attribute(
                value=self._visit_expr(node.value), attr=node.attr, ctx=type(node.ctx).__name__
            )
        elif isinstance(node, ast.Subscript):
            return schema.Subscript(
                value=self._visit_expr(node.value),
                slice=self._visit_expr(node.slice),
                ctx=type(node.ctx).__name__,
            )
        elif isinstance(node, ast.Starred):
            return schema.Starred(value=self._visit_expr(node.value), ctx=type(node.ctx).__name__)
        elif isinstance(node, ast.NamedExpr):
            return schema.NamedExpr(
                target=self._visit_expr(node.target), value=self._visit_expr(node.value)
            )
        elif isinstance(node, ast.List):
            return schema.ListExpr(
                elts=[self._visit_expr(e) for e in node.elts], ctx=type(node.ctx).__name__
            )
        elif isinstance(node, ast.Tuple):
            return schema.TupleExpr(
                elts=[self._visit_expr(e) for e in node.elts], ctx=type(node.ctx).__name__
            )
        elif isinstance(node, ast.Dict):
            return schema.DictExpr(
                keys=[self._visit_expr(k) if k else None for k in node.keys],
                values=[self._visit_expr(v) for v in node.values],
            )
        elif isinstance(node, ast.Set):
            return schema.SetExpr(
                elts=[self._visit_expr(e) for e in node.elts],
                ctx=type(node.ctx).__name__ if hasattr(node, "ctx") else "Load",
            )
        elif isinstance(node, ast.ListComp):
            return schema.ListComp(
                elt=self._visit_expr(node.elt),
                generators=[self._visit_comprehension(c) for c in node.generators],
            )
        elif isinstance(node, ast.SetComp):
            return schema.SetComp(
                elt=self._visit_expr(node.elt),
                generators=[self._visit_comprehension(c) for c in node.generators],
            )
        elif isinstance(node, ast.DictComp):
            return schema.DictComp(
                key=self._visit_expr(node.key),
                value=self._visit_expr(node.value),
                generators=[self._visit_comprehension(c) for c in node.generators],
            )
        elif isinstance(node, ast.GeneratorExp):
            return schema.GeneratorExp(
                elt=self._visit_expr(node.elt),
                generators=[self._visit_comprehension(c) for c in node.generators],
            )
        elif isinstance(node, ast.Lambda):
            return schema.Lambda(
                args=self._visit_arguments(node.args), body=self._visit_expr(node.body)
            )
        elif isinstance(node, ast.Yield):
            return schema.Yield(value=self._visit_expr(node.value) if node.value else None)
        elif isinstance(node, ast.YieldFrom):
            return schema.YieldFrom(value=self._visit_expr(node.value))
        elif isinstance(node, ast.Await):
            return schema.Await(value=self._visit_expr(node.value))
        elif isinstance(node, ast.JoinedStr):
            return schema.JoinedStr(values=[self._visit_expr(v) for v in node.values])
        elif isinstance(node, ast.FormattedValue):
            return schema.FormattedValue(
                value=self._visit_expr(node.value),
                conversion=node.conversion,
                format_spec=self._visit_expr(node.format_spec) if node.format_spec else None,
            )
        elif isinstance(node, ast.IfExp):
            return schema.IfExp(
                test=self._visit_expr(node.test),
                body=self._visit_expr(node.body),
                orelse=self._visit_expr(node.orelse),
            )
        elif isinstance(node, ast.Slice):
            return schema.Slice(
                lower=self._visit_expr(node.lower) if node.lower else None,
                upper=self._visit_expr(node.upper) if node.upper else None,
                step=self._visit_expr(node.step) if node.step else None,
            )

        # Fallback for unsupported expressions
        return schema.Constant(value=f"<Unsupported: {type(node).__name__}>", kind="str")

    def _get_op_name(self, op: Any) -> str:
        op_map = {
            ast.Add: "+",
            ast.Sub: "-",
            ast.Mult: "*",
            ast.Div: "/",
            ast.Mod: "%",
            ast.Pow: "**",
            ast.FloorDiv: "//",
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
            ast.Is: "is",
            ast.IsNot: "is not",
            ast.In: "in",
            ast.NotIn: "not in",
            ast.And: "and",
            ast.Or: "or",
            ast.Not: "not",
            ast.Invert: "~",
            ast.UAdd: "+",
            ast.USub: "-",
            ast.MatMult: "@",
        }
        return op_map.get(type(op), "?")
