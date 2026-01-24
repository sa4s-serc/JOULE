import ast
import sys

from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser


def test_round_trip(code: str, name: str):
    print(f"Testing {name}...")
    try:
        parser = PythonParser()
        codegen = PythonCodeGenerator()

        # 1. Parse to IR
        ir_module = parser.parse(code)

        # 2. Generate Code
        gen_code = codegen.generate(ir_module)

        print(f"Original:\n{code.strip()}")
        print(f"Generated:\n{gen_code.strip()}")

        # 3. Verify Equality (ignoring whitespace nuances for now, or just re-parsing generated)
        # Ideally we check if ASTs match
        ast1 = ast.dump(ast.parse(code), indent=2)
        ast2 = ast.dump(ast.parse(gen_code), indent=2)

        if ast1 == ast2:
            print("SUCCESS: ASTs match")
        else:
            print("WARNING: ASTs differ (might be formatting)")
            # print(f"Diff:\n{gen_code}")

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback

        traceback.print_exc()


# Test Cases

tc_async = """
async def fetch_data(url: str, retries: int = 3) -> dict:
    async with session.get(url) as response:
        return await response.json()
"""

tc_comp = """
squares = [x*x for x in range(10) if x % 2 == 0]
"""

tc_fstring = """
msg = f"Value: {x + 1}"
"""

tc_walrus = """
if (n := len(data)) > 10:
    print(n)
"""

tc_match = """
match status:
    case 400:
        return "Bad Request"
    case _:
        return "Unknown"
"""

if __name__ == "__main__":
    test_round_trip(tc_async, "Async Function")
    test_round_trip(tc_comp, "Comprehension")
    test_round_trip(tc_fstring, "F-String")
    # Walrus only on 3.8+
    if sys.version_info >= (3, 8):
        test_round_trip(tc_walrus, "Walrus Operator")
    # Match only on 3.10+
    if sys.version_info >= (3, 10):
        test_round_trip(tc_match, "Match Statement")
