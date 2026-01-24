"""
Strict Intermediate Representation (IR) Schema.

This module defines a fully-typed, structural IR for Python code.
Unlike traditional "stringly-typed" representations, every expression
and statement is represented as a strongly-typed Pydantic model.

This enables:
- Type-safe mutations
- Structural validation
- Deterministic code generation
- Safe program transformations
"""

from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- Base Nodes ---


class IRNode(BaseModel):
    """
    Base class for all IR nodes.

    All IR nodes are immutable Pydantic models that can be:
    - Serialized to JSON
    - Validated at runtime
    - Deep-copied for mutations
    """

    lineno: Optional[int] = None
    col_offset: Optional[int] = None
    end_lineno: Optional[int] = None
    end_col_offset: Optional[int] = None

    model_config = ConfigDict(
        frozen=False, validate_assignment=True
    )  # Allow mutations during transformation, but keep them valid


class Expression(IRNode):
    """
    Base class for all expressions.

    Expressions are nodes that evaluate to a value.
    Examples: BinaryOp, Call, Name, Constant
    """


class Statement(IRNode):
    """
    Base class for all statements.

    Statements are nodes that perform actions but don't return values.
    Examples: Assign, Return, If, While, For
    """


# --- Expressions ---


class Constant(Expression):
    value: Union[int, float, str, bool, None]
    kind: Literal["int", "float", "str", "bool", "None"]


class Name(Expression):
    id: str
    ctx: Literal["Load", "Store", "Del"] = "Load"


class BinaryOp(Expression):
    left: Expression
    op: str  # +, -, *, /, etc.
    right: Expression


class UnaryOp(Expression):
    op: str  # not, -, +, ~
    operand: Expression


class BoolOp(Expression):
    op: str  # and, or
    values: List[Expression]


class Compare(Expression):
    left: Expression
    ops: List[str]
    comparators: List[Expression]


class Call(Expression):
    func: Expression
    args: List[Expression]
    keywords: List[tuple[str, Expression]] = Field(default_factory=list)


class Attribute(Expression):
    value: Expression
    attr: str
    ctx: Literal["Load", "Store", "Del"] = "Load"


class Subscript(Expression):
    value: Expression
    slice: Expression
    ctx: Literal["Load", "Store", "Del"] = "Load"


class Starred(Expression):
    value: Expression
    ctx: Literal["Load", "Store", "Del"] = "Load"


class NamedExpr(Expression):
    target: Expression
    value: Expression


class ListExpr(Expression):
    elts: List[Expression]
    ctx: Literal["Load", "Store", "Del"] = "Load"


class TupleExpr(Expression):
    elts: List[Expression]
    ctx: Literal["Load", "Store", "Del"] = "Load"


class DictExpr(Expression):
    keys: List[Optional[Expression]]
    values: List[Expression]


class SetExpr(Expression):
    elts: List[Expression]
    ctx: Literal["Load", "Store", "Del"] = "Load"


class Comprehension(IRNode):
    target: Expression
    iter: Expression
    ifs: List[Expression] = Field(default_factory=list)
    is_async: int = 0


class ListComp(Expression):
    elt: Expression
    generators: List[Comprehension]


class SetComp(Expression):
    elt: Expression
    generators: List[Comprehension]


class GeneratorExp(Expression):
    elt: Expression
    generators: List[Comprehension]


class DictComp(Expression):
    key: Expression
    value: Expression
    generators: List[Comprehension]


class FormattedValue(Expression):
    value: Expression
    conversion: int = -1
    format_spec: Optional[Expression] = None


class JoinedStr(Expression):
    values: List[Expression]


class Lambda(Expression):
    args: "Arguments"  # Forward reference
    body: Expression


class Yield(Expression):
    value: Optional[Expression] = None


class YieldFrom(Expression):
    value: Expression


class Await(Expression):
    value: Expression


class Slice(Expression):
    lower: Optional[Expression] = None
    upper: Optional[Expression] = None
    step: Optional[Expression] = None


class IfExp(Expression):
    test: Expression
    body: Expression
    orelse: Expression


# --- Helper Nodes ---


class Arg(IRNode):
    arg: str
    annotation: Optional[Expression] = None
    type_comment: Optional[str] = None


class Arguments(IRNode):
    posonlyargs: List[Arg] = Field(default_factory=list)
    args: List[Arg] = Field(default_factory=list)
    vararg: Optional[Arg] = None
    kwonlyargs: List[Arg] = Field(default_factory=list)
    kw_defaults: List[Optional[Expression]] = Field(default_factory=list)
    kwarg: Optional[Arg] = None
    defaults: List[Expression] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def handle_list(cls, v: Any) -> Any:
        if isinstance(v, list):
            return {"args": [Arg(arg=a) if isinstance(a, str) else a for a in v]}
        return v

    def __len__(self):
        return len(self.args)

    def __getitem__(self, idx):
        return self.args[idx]

    def __iter__(self):
        return iter(self.args)


class Keyword(IRNode):
    arg: Optional[str]
    value: Expression


class Alias(IRNode):
    name: str
    asname: Optional[str] = None


class WithItem(IRNode):
    context_expr: Expression
    optional_vars: Optional[Expression] = None


class MatchCase(IRNode):
    pattern: "Pattern"  # Forward Ref
    guard: Optional[Expression]
    body: List["Statement"]


class Pattern(IRNode):
    """Base class for match patterns."""


class MatchValue(Pattern):
    value: Expression


class MatchSingleton(Pattern):
    value: Union[int, float, str, bool, None]


class MatchSequence(Pattern):
    patterns: List[Pattern]


class MatchMapping(Pattern):
    keys: List[Expression]
    patterns: List[Pattern]
    rest: Optional[str] = None


class MatchClass(Pattern):
    cls: Expression
    patterns: List[Pattern]
    kwd_attrs: List[str]
    kwd_patterns: List[Pattern]


class MatchStar(Pattern):
    name: Optional[str] = None


class MatchAs(Pattern):
    pattern: Optional[Pattern] = None
    name: Optional[str] = None


class MatchOr(Pattern):
    patterns: List[Pattern]


# --- Statements ---


class Assign(Statement):
    targets: List[Expression]
    value: Expression
    type_comment: Optional[str] = None


class AnnAssign(Statement):
    target: Expression
    annotation: Expression
    value: Optional[Expression] = None
    simple: int = 1


class AugAssign(Statement):
    target: Expression
    op: str
    value: Expression


class Raise(Statement):
    exc: Optional[Expression] = None
    cause: Optional[Expression] = None


class Assert(Statement):
    test: Expression
    msg: Optional[Expression] = None


class Delete(Statement):
    targets: List[Expression]


class Return(Statement):
    value: Optional[Expression] = None


class Pass(Statement):
    pass


class Break(Statement):
    pass


class Continue(Statement):
    pass


class Global(Statement):
    names: List[str]


class Nonlocal(Statement):
    names: List[str]


class ExprStmt(Statement):
    value: Expression


class Block(IRNode):
    statements: List[Statement]


class If(Statement):
    test: Expression
    body: Block
    orelse: Optional[Block] = None


class Match(Statement):
    subject: Expression
    cases: List[MatchCase]


class While(Statement):
    test: Expression
    body: Block
    orelse: Optional[Block] = None


class For(Statement):
    target: Expression
    iter: Expression
    body: Block
    orelse: Optional[Block] = None
    type_comment: Optional[str] = None


class AsyncFor(Statement):
    target: Expression
    iter: Expression
    body: Block
    orelse: Optional[Block] = None
    type_comment: Optional[str] = None


class FunctionDef(Statement):
    name: str
    args: Arguments
    body: Block
    decorator_list: List[Expression] = Field(default_factory=list)
    returns: Optional[Expression] = None
    type_comment: Optional[str] = None


class AsyncFunctionDef(Statement):
    name: str
    args: Arguments
    body: Block
    decorator_list: List[Expression] = Field(default_factory=list)
    returns: Optional[Expression] = None
    type_comment: Optional[str] = None


class ClassDef(Statement):
    name: str
    bases: List[Expression]
    keywords: List[Keyword] = Field(default_factory=list)
    body: Block
    decorator_list: List[Expression] = Field(default_factory=list)


class Import(Statement):
    names: List[Alias]


class ImportFrom(Statement):
    module: Optional[str]
    names: List[Alias]
    level: int = 0


class ExceptHandler(IRNode):
    type: Optional[Expression] = None
    name: Optional[str] = None
    body: Block


class Try(Statement):
    body: Block
    handlers: List[ExceptHandler]
    orelse: Optional[Block] = None
    finalbody: Optional[Block] = None


class TryStar(Statement):
    body: Block
    handlers: List[ExceptHandler]
    orelse: Optional[Block] = None
    finalbody: Optional[Block] = None


class With(Statement):
    items: List[WithItem]
    body: Block
    type_comment: Optional[str] = None


class AsyncWith(Statement):
    items: List[WithItem]
    body: Block
    type_comment: Optional[str] = None


# --- Top Level ---


class Module(IRNode):
    body: Block
    type_ignores: List[str] = Field(default_factory=list)


# --- Rebuild Models for Forward Refs ---
MatchCase.model_rebuild()
Lambda.model_rebuild()
Block.model_rebuild()
If.model_rebuild()
While.model_rebuild()
For.model_rebuild()
AsyncFor.model_rebuild()
Try.model_rebuild()
TryStar.model_rebuild()
With.model_rebuild()
AsyncWith.model_rebuild()
ExceptHandler.model_rebuild()
FunctionDef.model_rebuild()
AsyncFunctionDef.model_rebuild()
ClassDef.model_rebuild()
