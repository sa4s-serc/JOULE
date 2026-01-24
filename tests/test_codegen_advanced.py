
import pytest
from src.domain.ir import schema
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser

class TestAdvancedCodeGen:
    
    def setup_method(self):
        self.codegen = PythonCodeGenerator()
        self.parser = PythonParser()

    def test_match_statement(self):
        """Test code generation for Python 3.10+ match statement."""
        ir = schema.Module(body=schema.Block(statements=[
            schema.Match(
                subject=schema.Name(id="x"),
                cases=[
                    schema.MatchCase(
                        pattern=schema.MatchValue(value=schema.Constant(value=1, kind="int")),
                        body=[schema.Return(value=schema.Constant(value="one", kind="str"))]
                    ),
                    schema.MatchCase(
                        pattern=schema.MatchAs(name="other"),
                        body=[schema.Return(value=schema.Name(id="other"))]
                    )
                ]
            )
        ]))
        
        code = self.codegen.generate(ir)
        assert "match x:" in code
        assert "case 1:" in code
        assert "case other:" in code
        
        # Verify it's valid Python
        self.parser.parse(code)

    def test_try_star_statement(self):
        """Test code generation for Python 3.11+ try* statement."""
        ir = schema.Module(body=schema.Block(statements=[
            schema.TryStar(
                body=schema.Block(statements=[schema.ExprStmt(value=schema.Call(func=schema.Name(id="func"), args=[]))]),
                handlers=[
                    schema.ExceptHandler(
                        type=schema.Name(id="ExceptionGroup"),
                        name="eg",
                        body=schema.Block(statements=[schema.Pass()])
                    )
                ],
                orelse=None,
                finalbody=None
            )
        ]))
        
        code = self.codegen.generate(ir)
        assert "try:" in code
        assert "except* ExceptionGroup as eg:" in code

    def test_async_with_for(self):
        """Test code generation for async constructs."""
        ir = schema.Module(body=schema.Block(statements=[
            schema.AsyncFunctionDef(
                name="async_test",
                args=schema.Arguments(),
                body=schema.Block(statements=[
                    schema.AsyncWith(
                        items=[schema.WithItem(context_expr=schema.Call(func=schema.Name(id="lock"), args=[]), optional_vars=schema.Name(id="l"))],
                        body=schema.Block(statements=[
                            schema.AsyncFor(
                                target=schema.Name(id="i"),
                                iter=schema.Name(id="items"),
                                body=schema.Block(statements=[schema.ExprStmt(value=schema.Await(value=schema.Call(func=schema.Name(id="process"), args=[schema.Name(id="i")])))])
                            )
                        ])
                    )
                ])
            )
        ]))
        
        code = self.codegen.generate(ir)
        assert "async def async_test():" in code
        assert "async with lock() as l:" in code
        assert "async for i in items:" in code
        assert "await process(i)" in code

    def test_named_expr(self):
        """Test code generation for walrus operator."""
        ir = schema.Module(body=schema.Block(statements=[
            schema.If(
                test=schema.NamedExpr(target=schema.Name(id="n"), value=schema.Call(func=schema.Name(id="len"), args=[schema.Name(id="data")])),
                body=schema.Block(statements=[schema.Return(value=schema.Name(id="n"))])
            )
        ]))
        
        code = self.codegen.generate(ir)
        assert "(n := len(data))" in code

    def test_f_strings_complex(self):
        """Test code generation for complex f-strings."""
        ir = schema.Module(body=schema.Block(statements=[
            schema.ExprStmt(value=schema.JoinedStr(values=[
                schema.Constant(value="Value: ", kind="str"),
                schema.FormattedValue(
                    value=schema.Name(id="x"),
                    conversion=114, # !r
                    format_spec=schema.JoinedStr(values=[schema.Constant(value=".2f", kind="str")])
                )
            ]))
        ]))
        
        code = self.codegen.generate(ir)
        # f"Value: {x!r:.2f}"
        assert 'f"Value: {x!r:.2f}"' in code
