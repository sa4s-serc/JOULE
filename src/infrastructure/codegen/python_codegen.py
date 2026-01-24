from typing import List, Optional
from src.domain.ir import schema

class PythonCodeGenerator:
    """
    Converts Strict IR back into executable Python code.
    Updated to support full IR schema including modern Python features.
    """
    
    def generate(self, module: schema.Module) -> str:
        return self._generate_block(module.body, indent=0)
    
    def _generate_block(self, block: schema.Block, indent: int) -> str:
        lines = []
        for stmt in block.statements:
            lines.append(self._generate_stmt(stmt, indent))
        return "\n".join(lines)
    
    def _indent(self, indent: int) -> str:
        return "    " * indent

    def _generate_arguments(self, args: schema.Arguments) -> str:
        parts = []
        
        # Positional only
        for arg in args.posonlyargs:
            parts.append(self._generate_arg(arg))
        if args.posonlyargs:
            parts.append("/")
            
        # Positional or keyword
        for i, arg in enumerate(args.args):
            s = self._generate_arg(arg)
            # Handle defaults (from back to front)
            # defaults list corresponds to last n args
            defaults_start = len(args.args) - len(args.defaults)
            if i >= defaults_start:
                default_val = args.defaults[i - defaults_start]
                s += f"={self._generate_expr(default_val)}"
            parts.append(s)
            
        # Varargs
        if args.vararg:
             parts.append(f"*{self._generate_arg(args.vararg)}")
        
        # Keyword only
        if args.kwonlyargs and not args.vararg:
             parts.append("*")
             
        for i, arg in enumerate(args.kwonlyargs):
            s = self._generate_arg(arg)
            default_val = args.kw_defaults[i]
            if default_val:
                s += f"={self._generate_expr(default_val)}"
            parts.append(s)
            
        # Kwargs
        if args.kwarg:
            parts.append(f"**{self._generate_arg(args.kwarg)}")
            
        return ", ".join(parts)

    def _generate_arg(self, arg: schema.Arg) -> str:
        s = arg.arg
        if arg.annotation:
            s += f": {self._generate_expr(arg.annotation)}"
        return s

    def _generate_alias(self, alias: schema.Alias) -> str:
        if alias.asname:
            return f"{alias.name} as {alias.asname}"
        return alias.name

    def _generate_comprehension(self, comp: schema.Comprehension) -> str:
        s = "async for " if comp.is_async else "for "
        s += f"{self._generate_expr(comp.target)} in {self._generate_expr(comp.iter)}"
        for if_expr in comp.ifs:
            s += f" if {self._generate_expr(if_expr)}"
        return s

    def _generate_pattern(self, pattern: schema.Pattern) -> str:
        if isinstance(pattern, schema.MatchValue):
            return self._generate_expr(pattern.value)
        elif isinstance(pattern, schema.MatchSingleton):
            return str(pattern.value)
        elif isinstance(pattern, schema.MatchSequence):
            pats = [self._generate_pattern(p) for p in pattern.patterns]
            return f"[{', '.join(pats)}]"
        elif isinstance(pattern, schema.MatchMapping):
            items = []
            for k, p in zip(pattern.keys, pattern.patterns):
                items.append(f"{self._generate_expr(k)}: {self._generate_pattern(p)}")
            if pattern.rest:
                items.append(f"**{pattern.rest}")
            return f"{{{', '.join(items)}}}"
        elif isinstance(pattern, schema.MatchClass):
            cls = self._generate_expr(pattern.cls)
            pats = [self._generate_pattern(p) for p in pattern.patterns]
            kw_pats = [f"{k}={self._generate_pattern(p)}" for k, p in zip(pattern.kwd_attrs, pattern.kwd_patterns)]
            args = ", ".join(pats + kw_pats)
            return f"{cls}({args})"
        elif isinstance(pattern, schema.MatchStar):
            return f"*{pattern.name}" if pattern.name else "*"
        elif isinstance(pattern, schema.MatchAs):
            if pattern.pattern:
                return f"{self._generate_pattern(pattern.pattern)} as {pattern.name}"
            return pattern.name if pattern.name else "_"
        elif isinstance(pattern, schema.MatchOr):
            pats = [self._generate_pattern(p) for p in pattern.patterns]
            return " | ".join(pats)
        return "_"


    # --- Statement Generators ---
    
    def _generate_stmt(self, stmt: schema.Statement, indent: int) -> str:
        prefix = self._indent(indent)
        
        if isinstance(stmt, schema.Assign):
            targets = [self._generate_expr(t) for t in stmt.targets]
            value = self._generate_expr(stmt.value)
            s = f"{prefix}{' = '.join(targets)} = {value}"
            if stmt.type_comment:
                s += f"  # type: {stmt.type_comment}"
            return s
        
        elif isinstance(stmt, schema.AnnAssign):
            target = self._generate_expr(stmt.target)
            annotation = self._generate_expr(stmt.annotation)
            if stmt.value:
                value = self._generate_expr(stmt.value)
                return f"{prefix}{target}: {annotation} = {value}"
            return f"{prefix}{target}: {annotation}"
            
        elif isinstance(stmt, schema.AugAssign):
            target = self._generate_expr(stmt.target)
            value = self._generate_expr(stmt.value)
            return f"{prefix}{target} {stmt.op}= {value}"
            
        elif isinstance(stmt, schema.Return):
            if stmt.value:
                return f"{prefix}return {self._generate_expr(stmt.value)}"
            return f"{prefix}return"
            
        elif isinstance(stmt, schema.Pass):
            return f"{prefix}pass"
        elif isinstance(stmt, schema.Break):
            return f"{prefix}break"
        elif isinstance(stmt, schema.Continue):
            return f"{prefix}continue"
        
        elif isinstance(stmt, schema.Raise):
            s = f"{prefix}raise"
            if stmt.exc:
                s += f" {self._generate_expr(stmt.exc)}"
                if stmt.cause:
                    s += f" from {self._generate_expr(stmt.cause)}"
            return s
            
        elif isinstance(stmt, schema.Assert):
            s = f"{prefix}assert {self._generate_expr(stmt.test)}"
            if stmt.msg:
                s += f", {self._generate_expr(stmt.msg)}"
            return s
            
        elif isinstance(stmt, schema.Delete):
            targets = ", ".join([self._generate_expr(t) for t in stmt.targets])
            return f"{prefix}del {targets}"
            
        elif isinstance(stmt, schema.Global):
            return f"{prefix}global {', '.join(stmt.names)}"
            
        elif isinstance(stmt, schema.Nonlocal):
            return f"{prefix}nonlocal {', '.join(stmt.names)}"
            
        elif isinstance(stmt, schema.ExprStmt):
            return f"{prefix}{self._generate_expr(stmt.value)}"
            
        elif isinstance(stmt, schema.If):
            test = self._generate_expr(stmt.test)
            lines = [f"{prefix}if {test}:"]
            lines.append(self._generate_block(stmt.body, indent + 1))
            if stmt.orelse and stmt.orelse.statements:
                lines.append(f"{prefix}else:")
                lines.append(self._generate_block(stmt.orelse, indent + 1))
            return "\n".join(lines)
        
        elif isinstance(stmt, schema.Match):
            subject = self._generate_expr(stmt.subject)
            lines = [f"{prefix}match {subject}:"]
            for case in stmt.cases:
                pat = self._generate_pattern(case.pattern)
                guard = f" if {self._generate_expr(case.guard)}" if case.guard else ""
                lines.append(f"{prefix}    case {pat}{guard}:") 
                for s in case.body:
                    lines.append(self._generate_stmt(s, indent + 2))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.While):
            test = self._generate_expr(stmt.test)
            lines = [f"{prefix}while {test}:"]
            lines.append(self._generate_block(stmt.body, indent + 1))
            if stmt.orelse:
                lines.append(f"{prefix}else:")
                lines.append(self._generate_block(stmt.orelse, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.For):
            target = self._generate_expr(stmt.target)
            iter_ = self._generate_expr(stmt.iter)
            lines = [f"{prefix}for {target} in {iter_}:"]
            lines.append(self._generate_block(stmt.body, indent + 1))
            if stmt.orelse:
                lines.append(f"{prefix}else:")
                lines.append(self._generate_block(stmt.orelse, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.AsyncFor):
            target = self._generate_expr(stmt.target)
            iter_ = self._generate_expr(stmt.iter)
            lines = [f"{prefix}async for {target} in {iter_}:"]
            lines.append(self._generate_block(stmt.body, indent + 1))
            if stmt.orelse:
                lines.append(f"{prefix}else:")
                lines.append(self._generate_block(stmt.orelse, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.FunctionDef):
            args = self._generate_arguments(stmt.args)
            lines = []
            for dec in stmt.decorator_list:
                lines.append(f"{prefix}@{self._generate_expr(dec)}")
            
            ret = f" -> {self._generate_expr(stmt.returns)}" if stmt.returns else ""
            lines.append(f"{prefix}def {stmt.name}({args}){ret}:")
            lines.append(self._generate_block(stmt.body, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.AsyncFunctionDef):
            args = self._generate_arguments(stmt.args)
            lines = []
            for dec in stmt.decorator_list:
                lines.append(f"{prefix}@{self._generate_expr(dec)}")
            
            ret = f" -> {self._generate_expr(stmt.returns)}" if stmt.returns else ""
            lines.append(f"{prefix}async def {stmt.name}({args}){ret}:")
            lines.append(self._generate_block(stmt.body, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.ClassDef):
            bases = ", ".join([self._generate_expr(b) for b in stmt.bases])
            # Handle keywords
            keywords = ", ".join([f"{k.arg}={self._generate_expr(k.value)}" for k in stmt.keywords])
            
            parts = []
            if bases: parts.append(bases)
            if keywords: parts.append(keywords)
            bases_str = f"({', '.join(parts)})" if parts else ""
            
            lines = []
            for dec in stmt.decorator_list:
                lines.append(f"{prefix}@{self._generate_expr(dec)}")
            
            lines.append(f"{prefix}class {stmt.name}{bases_str}:")
            lines.append(self._generate_block(stmt.body, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.Import):
            names = [self._generate_alias(n) for n in stmt.names]
            return f"{prefix}import {', '.join(names)}"
            
        elif isinstance(stmt, schema.ImportFrom):
            names = [self._generate_alias(n) for n in stmt.names]
            module = stmt.module or ""
            dots = "." * stmt.level
            return f"{prefix}from {dots}{module} import {', '.join(names)}"
            
        elif isinstance(stmt, schema.Try):
            lines = [f"{prefix}try:"]
            lines.append(self._generate_block(stmt.body, indent + 1))
            
            for handler in stmt.handlers:
                name_part = f" as {handler.name}" if handler.name else ""
                type_part = f" {self._generate_expr(handler.type)}" if handler.type else ""
                lines.append(f"{prefix}except{type_part}{name_part}:")
                lines.append(self._generate_block(handler.body, indent + 1))
                
            if stmt.orelse:
                lines.append(f"{prefix}else:")
                lines.append(self._generate_block(stmt.orelse, indent + 1))
                
            if stmt.finalbody:
                lines.append(f"{prefix}finally:")
                lines.append(self._generate_block(stmt.finalbody, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.TryStar):
            lines = [f"{prefix}try:"]
            lines.append(self._generate_block(stmt.body, indent + 1))
            
            for handler in stmt.handlers:
                name_part = f" as {handler.name}" if handler.name else ""
                type_part = f" {self._generate_expr(handler.type)}" if handler.type else ""
                lines.append(f"{prefix}except*{type_part}{name_part}:")
                lines.append(self._generate_block(handler.body, indent + 1))
                
            if stmt.orelse:
                lines.append(f"{prefix}else:")
                lines.append(self._generate_block(stmt.orelse, indent + 1))
                
            if stmt.finalbody:
                lines.append(f"{prefix}finally:")
                lines.append(self._generate_block(stmt.finalbody, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.With):
            items = []
            for item in stmt.items:
                s = self._generate_expr(item.context_expr)
                if item.optional_vars:
                    s += f" as {self._generate_expr(item.optional_vars)}"
                items.append(s)
            
            lines = [f"{prefix}with {', '.join(items)}:"]
            lines.append(self._generate_block(stmt.body, indent + 1))
            return "\n".join(lines)
            
        elif isinstance(stmt, schema.AsyncWith):
            items = []
            for item in stmt.items:
                s = self._generate_expr(item.context_expr)
                if item.optional_vars:
                    s += f" as {self._generate_expr(item.optional_vars)}"
                items.append(s)
            
            lines = [f"{prefix}async with {', '.join(items)}:"]
            lines.append(self._generate_block(stmt.body, indent + 1))
            return "\n".join(lines)
            
        return f"{prefix}# Unsupported statement: {type(stmt).__name__}"

    def _generate_expr(self, expr: schema.Expression) -> str:
        if isinstance(expr, schema.Constant):
            if expr.kind == "str":
                return repr(expr.value)
            return str(expr.value)
            
        elif isinstance(expr, schema.Name):
            return expr.id
            
        elif isinstance(expr, schema.BinaryOp):
            left = self._generate_expr(expr.left)
            right = self._generate_expr(expr.right)
            return f"({left} {expr.op} {right})"
            
        elif isinstance(expr, schema.UnaryOp):
            operand = self._generate_expr(expr.operand)
            if expr.op == "not":
                return f"({expr.op} {operand})"
            return f"{expr.op}{operand}"
            
        elif isinstance(expr, schema.BoolOp):
            values = [self._generate_expr(v) for v in expr.values]
            return f"({f' {expr.op} '.join(values)})"
            
        elif isinstance(expr, schema.Compare):
            left = self._generate_expr(expr.left)
            comparisons = []
            for op, comp in zip(expr.ops, expr.comparators):
                comparisons.append(f"{op} {self._generate_expr(comp)}")
            return f"({left} {' '.join(comparisons)})"
            
        elif isinstance(expr, schema.Call):
            func = self._generate_expr(expr.func)
            args = [self._generate_expr(a) for a in expr.args]
            keywords = [f"{k}={self._generate_expr(v)}" for k, v in expr.keywords]
            all_args = ", ".join(args + keywords)
            return f"{func}({all_args})"
            
        elif isinstance(expr, schema.Attribute):
            value = self._generate_expr(expr.value)
            return f"{value}.{expr.attr}"
            
        elif isinstance(expr, schema.Subscript):
            value = self._generate_expr(expr.value)
            slice_ = self._generate_expr(expr.slice)
            return f"{value}[{slice_}]"
            
        elif isinstance(expr, schema.Starred):
            return f"*{self._generate_expr(expr.value)}"
            
        elif isinstance(expr, schema.NamedExpr):
            return f"({self._generate_expr(expr.target)} := {self._generate_expr(expr.value)})"
            
        elif isinstance(expr, schema.ListExpr):
            elts = [self._generate_expr(e) for e in expr.elts]
            return f"[{', '.join(elts)}]"
            
        elif isinstance(expr, schema.TupleExpr):
            elts = [self._generate_expr(e) for e in expr.elts]
            if len(elts) == 1:
                return f"({elts[0]},)"
            return f"({', '.join(elts)})"
            
        elif isinstance(expr, schema.DictExpr):
            items = []
            for k, v in zip(expr.keys, expr.values):
                key = self._generate_expr(k) if k else "None"
                val = self._generate_expr(v)
                items.append(f"{key}: {val}")
            return f"{{{', '.join(items)}}}"
            
        elif isinstance(expr, schema.SetExpr):
            elts = [self._generate_expr(e) for e in expr.elts]
            if not elts:
                return "set()"
            return f"{{{', '.join(elts)}}}"
            
        elif isinstance(expr, schema.ListComp):
            elt = self._generate_expr(expr.elt)
            gens = " ".join([self._generate_comprehension(c) for c in expr.generators])
            return f"[{elt} {gens}]"
            
        elif isinstance(expr, schema.SetComp):
            elt = self._generate_expr(expr.elt)
            gens = " ".join([self._generate_comprehension(c) for c in expr.generators])
            return f"{{{elt} {gens}}}"
            
        elif isinstance(expr, schema.DictComp):
            k = self._generate_expr(expr.key)
            v = self._generate_expr(expr.value)
            gens = " ".join([self._generate_comprehension(c) for c in expr.generators])
            return f"{{{k}: {v} {gens}}}"
            
        elif isinstance(expr, schema.GeneratorExp):
            elt = self._generate_expr(expr.elt)
            gens = " ".join([self._generate_comprehension(c) for c in expr.generators])
            return f"({elt} {gens})"
            
        elif isinstance(expr, schema.Lambda):
            # args is now Arguments object
            args = self._generate_arguments(expr.args)
            body = self._generate_expr(expr.body)
            return f"lambda {args}: {body}"
            
        elif isinstance(expr, schema.Yield):
            if expr.value:
                return f"yield {self._generate_expr(expr.value)}"
            return "yield"
            
        elif isinstance(expr, schema.YieldFrom):
            return f"yield from {self._generate_expr(expr.value)}"
            
        elif isinstance(expr, schema.Await):
            return f"await {self._generate_expr(expr.value)}"
            
        elif isinstance(expr, schema.JoinedStr):
            parts = []
            for v in expr.values:
                if isinstance(v, schema.Constant) and v.kind == "str":
                    # Directly append string content, escaping braces
                    val = str(v.value)
                    val = val.replace("{", "{{").replace("}", "}}")
                    parts.append(val)
                else:
                    parts.append(self._generate_expr(v))
            return f'f"{''.join(parts)}"'
            
        elif isinstance(expr, schema.FormattedValue):
            val = self._generate_expr(expr.value)
            spec_str = ""
            if expr.format_spec:
                 spec = self._generate_expr(expr.format_spec)
                 # Handle nested f-string specifiers (strip f"..." or f'...' or "..." or '...')
                 if (spec.startswith('f"') and spec.endswith('"')) or (spec.startswith("f'") and spec.endswith("'")):
                     spec = spec[2:-1]
                 elif (spec.startswith('"') and spec.endswith('"')) or (spec.startswith("'") and spec.endswith("'")):
                     spec = spec[1:-1]
                 spec_str = f":{spec}"
            
            if expr.conversion >= 0:
                conv = {115: "!s", 114: "!r", 97: "!a"}.get(expr.conversion, "")
                return f"{{{val}{conv}{spec_str}}}"
            return f"{{{val}{spec_str}}}"
            
        elif isinstance(expr, schema.IfExp):
            return f"{self._generate_expr(expr.body)} if {self._generate_expr(expr.test)} else {self._generate_expr(expr.orelse)}"
            
        elif isinstance(expr, schema.Slice):
            lower = self._generate_expr(expr.lower) if expr.lower else ""
            upper = self._generate_expr(expr.upper) if expr.upper else ""
            if expr.step:
                return f"{lower}:{upper}:{self._generate_expr(expr.step)}"
            return f"{lower}:{upper}"
            
        return f"<Unsupported Expr: {type(expr).__name__}>"
