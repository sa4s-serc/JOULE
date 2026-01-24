import unittest

from src.domain.ir import schema
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser


class TestExtendedIR(unittest.TestCase):
    def setUp(self):
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()

    def test_try_except(self):
        code = """
try:
    x = (1 / 0)
except ZeroDivisionError as e:
    print("Error")
else:
    print("Success")
finally:
    print("Done")
""".strip()
        ir = self.parser.parse(code)
        self.assertIsInstance(ir.body.statements[0], schema.Try)
        generated = self.codegen.generate(ir)
        # Normalize whitespace and quotes for comparison
        self.assertEqual(
            generated.replace(" ", "").replace("\n", "").replace('"', "'"),
            code.replace(" ", "").replace("\n", "").replace('"', "'"),
        )

    def test_with_statement(self):
        code = """
with open("file.txt") as f:
    content = f.read()
""".strip()
        ir = self.parser.parse(code)
        self.assertIsInstance(ir.body.statements[0], schema.With)
        generated = self.codegen.generate(ir)
        self.assertEqual(
            generated.replace(" ", "").replace("\n", "").replace('"', "'"),
            code.replace(" ", "").replace("\n", "").replace('"', "'"),
        )

    def test_lambda(self):
        code = "f = lambda x: x + 1"
        ir = self.parser.parse(code)
        self.assertIsInstance(ir.body.statements[0].value, schema.Lambda)
        generated = self.codegen.generate(ir)
        # Codegen adds parens around lambda body expression if it's binary op
        # Expected: f = lambda x: (x + 1)
        expected = "f = lambda x: (x + 1)"
        self.assertEqual(
            generated.replace(" ", "").replace("\n", ""),
            expected.replace(" ", "").replace("\n", ""),
        )

    def test_set_and_yield(self):
        code = """
def gen():
    yield 1
    yield from [2, 3]
    s = {1, 2, 3}
""".strip()
        ir = self.parser.parse(code)
        func_def = ir.body.statements[0]
        self.assertIsInstance(func_def.body.statements[0].value, schema.Yield)
        self.assertIsInstance(func_def.body.statements[1].value, schema.YieldFrom)
        self.assertIsInstance(func_def.body.statements[2].value, schema.SetExpr)

        generated = self.codegen.generate(ir)
        self.assertEqual(
            generated.replace(" ", "").replace("\n", "").replace('"', "'"),
            code.replace(" ", "").replace("\n", "").replace('"', "'"),
        )


if __name__ == "__main__":
    unittest.main()
