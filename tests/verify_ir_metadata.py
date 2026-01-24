from src.domain.ir import schema
from src.infrastructure.parsing.python_parser import PythonParser


def test_metadata():
    code = """
def foo(x):
    return x + 1

y = foo(10)
"""
    parser = PythonParser()
    ir_module = parser.parse(code.strip())

    # Check FunctionDef
    func_def = ir_module.body.statements[0]
    assert isinstance(func_def, schema.FunctionDef)
    assert func_def.name == "foo"
    print(f"FunctionDef loc: line={func_def.lineno}, col={func_def.col_offset}")
    assert func_def.lineno is not None
    assert func_def.col_offset is not None

    # Check Return
    ret_stmt = func_def.body.statements[0]
    assert isinstance(ret_stmt, schema.Return)
    print(f"Return loc: line={ret_stmt.lineno}, col={ret_stmt.col_offset}")
    assert ret_stmt.lineno is not None

    # Check Expression (x + 1)
    bin_op = ret_stmt.value
    assert isinstance(bin_op, schema.BinaryOp)
    print(f"BinaryOp loc: line={bin_op.lineno}, col={bin_op.col_offset}")
    assert bin_op.lineno is not None

    # Check Assign
    assign = ir_module.body.statements[1]
    assert isinstance(assign, schema.Assign)
    print(f"Assign loc: line={assign.lineno}, col={assign.col_offset}")
    assert assign.lineno is not None

    print("SUCCESS: Metadata populated correctly.")


if __name__ == "__main__":
    try:
        test_metadata()
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback

        traceback.print_exc()
