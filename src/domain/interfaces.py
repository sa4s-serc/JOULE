from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from src.domain.ir.schema import Module


class Mutator(ABC):
    """
    Abstract base class for all mutators.
    Mutators operate strictly on the IR (Module) and return new IR variants.
    """

    @abstractmethod
    def mutate(self, ir: Module) -> List[Any]:
        """
        Apply mutations to the given IR.

        Args:
            ir: The source IR module.

        Returns:
            A list of MutationResult objects containing:
            - The mutated IR Module.
            - Strategy name and layer information.
            - Confidence and description metadata.
        """


class CodeRunner(ABC):
    """
    Abstract base class for code execution environments.
    """

    @abstractmethod
    def run(self, code: str, test_code: str) -> Tuple[bool, Dict[str, float], str]:
        """
        Execute the code and return metrics.

        Args:
            code: The source code to run.
            test_code: The test harness code.

        Returns:
            Tuple containing:
            - Success (bool)
            - Metrics (dict) e.g. {'energy': 1.0, 'time': 0.5}
            - Output/Error logs (str)
        """
