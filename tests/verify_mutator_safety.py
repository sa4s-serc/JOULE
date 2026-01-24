import logging

from src.application.mutators.structural import StructuralMutator
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser

# Configure logging to see mutator decisions
logging.basicConfig(level=logging.DEBUG)


def verify_safety():
    parser = PythonParser()
    codegen = PythonCodeGenerator()
    mutator = StructuralMutator(use_context=True)

    print("--- Test 1: Data Dependency (Unsafe) ---")
    code_dep = """
x = 1
y = x + 1
"""
    ir_dep = parser.parse(code_dep.strip())
    # Try to mutate multiple times
    for _ in range(20):
        variants = mutator.mutate(ir_dep)
        for var, name in variants:
            if name == "Structural_ReorderStatements":
                print("FAILED: Reordered dependent statements!")
                print(codegen.generate(var))
                return

    print("PASSED: Did not reorder dependent statements.")

    print("\n--- Test 2: Side Effects (Unsafe) ---")
    code_side_effect = """
print("A")
print("B")
"""
    ir_side = parser.parse(code_side_effect.strip())
    for _ in range(20):
        variants = mutator.mutate(ir_side)
        for var, name in variants:
            if name == "Structural_ReorderStatements":
                print("FAILED: Reordered side-effect statements!")
                print(codegen.generate(var))
                return
    print("PASSED: Did not reorder side-effect statements.")

    print("\n--- Test 3: Independent Pure Statements (Safe) ---")
    code_safe = """
x = 1
y = 2
"""
    ir_safe = parser.parse(code_safe.strip())
    reordered_count = 0
    for _ in range(20):
        variants = mutator.mutate(ir_safe)
        for var, name in variants:
            if name == "Structural_ReorderStatements":
                reordered_count += 1
                gen = codegen.generate(var)
                # Check if it actually swapped
                if "y = 2" in gen.split("\n")[0]:
                    pass  # Good

    if reordered_count > 0:
        print(f"PASSED: Reordered independent statements {reordered_count} times.")
    else:
        print("WARNING: Failed to reorder independent statements (might be random luck, or bug).")

    print("\n--- Test 4: Impure Operands Swap (Unsafe) ---")
    # f() + g() -> g() + f() is unsafe
    code_impure_op = """
z = f() + g()
"""
    ir_impure_op = parser.parse(code_impure_op.strip())
    swapped = False
    for _ in range(20):
        variants = mutator.mutate(ir_impure_op)
        for var, name in variants:
            if name == "Structural_SwapOperands":
                swapped = True
                print("FAILED: Swapped impure operands!")
                print(codegen.generate(var))

    if not swapped:
        print("PASSED: Did not swap impure operands.")

    print("\n--- Test 5: Pure Operands Swap (Safe) ---")
    code_pure_op = """
z = a + b
"""
    ir_pure_op = parser.parse(code_pure_op.strip())
    swapped_pure = False
    for _ in range(20):
        variants = mutator.mutate(ir_pure_op)
        for var, name in variants:
            if name == "Structural_SwapOperands":
                swapped_pure = True

    if swapped_pure:
        print("PASSED: Swapped pure operands.")
    else:
        print("WARNING: Did not swap pure operands (random luck?)")


if __name__ == "__main__":
    verify_safety()
