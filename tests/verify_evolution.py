import logging

from src.application.engine.evolution import EvolutionaryEngine
from src.application.mutators.structural import StructuralMutator
from src.domain.interfaces import CodeRunner

# Configure logging
logging.basicConfig(level=logging.INFO)


class DummyRunner(CodeRunner):
    def run(self, code: str, test_code: str):
        # Dummy runner that always succeeds and returns random metrics
        import random

        energy = random.uniform(0.1, 1.0)
        time = random.uniform(0.01, 0.1)
        # Simulate "better" code: if code is shorter, slightly better metrics
        if len(code) < 100:
            energy *= 0.8

        return True, {"energy_joules": energy, "duration_seconds": time}, "Success"


def verify_evolution():
    print("Initializing Engine...")
    mutators = [StructuralMutator(use_context=True)]
    runner = DummyRunner()

    engine = EvolutionaryEngine(mutators=mutators, runner=runner, generations=3, population_size=5)

    initial_code = """
def foo(x):
    y = x + 1
    return y

z = foo(10)
"""
    test_code = "pass"

    print("Starting Optimization...")
    solutions = engine.optimize(initial_code, test_code)

    print(f"Optimization complete. Found {len(solutions)} Pareto solutions.")
    for sol in solutions:
        print(
            f"Sol ID: {sol.variant_id[:8]} | Gen: {sol.generation} | Type: {sol.mutation_type} | Metrics: {sol.metrics}"
        )

    print("\nMutation Stats:")
    print(engine.statistics.to_dict())


if __name__ == "__main__":
    verify_evolution()
