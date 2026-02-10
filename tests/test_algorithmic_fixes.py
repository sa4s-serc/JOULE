from src.application.mutators.algorithmic_layer import DataStructureOptimizer
from src.infrastructure.codegen.python_codegen import PythonCodeGenerator
from src.infrastructure.parsing.python_parser import PythonParser


class TestAlgorithmicFixes:

    def setup_method(self):
        self.parser = PythonParser()
        self.codegen = PythonCodeGenerator()

    def test_insertion_deletion_optimization_with_deque_init(self):
        """
        Test that InsertionDeletionOptimizer converts:
        queue = []
        queue.insert(0, 1)

        To:
        import collections
        queue = collections.deque()
        queue.appendleft(1)
        """
        code = """
def process_queue():
    queue = []
    queue.insert(0, 1)
    x = queue.pop(0)
    return x
"""
        ir = self.parser.parse(code)

        # Manually apply the specific transformer logic using DataStructureOptimizer
        # filtering for the specific strategy
        mutator = DataStructureOptimizer(enabled_strategies={"DataStructure_InsertionOptimization"})
        variants = mutator.mutate(ir)

        # Should have found a mutation
        assert len(variants) > 0, "No mutation produced"

        mutated_ir = variants[0].ir
        generated_code = self.codegen.generate(mutated_ir)

        # created code should convert list init to deque init
        assert "collections.deque()" in generated_code, "List initialization not converted to deque"
        assert "appendleft" in generated_code, "insert(0) not converted to appendleft"
        assert "popleft" in generated_code, "pop(0) not converted to popleft"
        assert (
            "import collections" in generated_code
            or "from collections import deque" in generated_code
            or (
                hasattr(mutated_ir.body.statements[0], "names")
                and mutated_ir.body.statements[0].names[0].name == "collections"
            )
        ), "Missing collections import"

    def test_search_optimization_bisect(self):
        """
        Test that SearchOptimizationTransformer converts linear search pattern to bisect.
        """
        code = """
def search(sorted_data, target):
    for i, x in enumerate(sorted_data):
        if x >= target:
            return i
    return len(sorted_data)
"""
        ir = self.parser.parse(code)

        mutator = DataStructureOptimizer(enabled_strategies={"DataStructure_SearchOptimization"})
        variants = mutator.mutate(ir)

        assert len(variants) > 0, "No mutation produced"

        mutated_ir = variants[0].ir
        generated_code = self.codegen.generate(mutated_ir)

        assert "bisect.bisect_left" in generated_code
        assert "sorted_data" in generated_code
        assert "target" in generated_code
        assert "enumerate" not in generated_code
