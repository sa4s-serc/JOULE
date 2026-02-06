"""
Import Validation Utility

Centralized import validation logic to eliminate duplication across LLM mutators.
Provides security-focused import checking with configurable whitelists.
"""

import logging
from typing import Set

from src.domain.ir import schema
from src.utils.constants import STDLIB_WHITELIST

logger = logging.getLogger(__name__)


class ImportValidator:
    """
    Centralized import validation for mutation safety.

    Validates that mutations don't introduce unauthorized imports,
    maintaining security and consistency across all mutators.
    """

    def __init__(self, additional_allowed: Set[str] = None):
        """
        Initialize validator with optional additional allowed imports.

        Args:
            additional_allowed: Additional imports to allow beyond stdlib
        """
        self.additional_allowed = additional_allowed or set()

    def extract_imports(self, ir: schema.Module) -> Set[str]:
        """
        Extract set of imported module names from IR.

        Returns the base module name (e.g., 'os' from 'os.path').

        Args:
            ir: IR module to extract imports from

        Returns:
            Set of base module names
        """
        imports = set()

        for stmt in ir.body.statements:
            if isinstance(stmt, schema.Import):
                for alias in stmt.names:
                    # Get base module name (before first dot)
                    base_module = alias.name.split(".")[0]
                    imports.add(base_module)

            elif isinstance(stmt, schema.ImportFrom):
                if stmt.module:
                    # Get base module name (before first dot)
                    base_module = stmt.module.split(".")[0]
                    imports.add(base_module)

        return imports

    def validate_imports(self, new_ir: schema.Module, original_imports: Set[str]) -> bool:
        """
        Validate that new IR doesn't introduce unauthorized imports.

        Allows:
        - Imports already present in the original code
        - Standard library imports from STDLIB_WHITELIST
        - Additional imports specified in constructor

        Args:
            new_ir: New IR module to validate
            original_imports: Set of imports from original code

        Returns:
            True if all imports are authorized, False otherwise
        """
        new_imports = self.extract_imports(new_ir)

        # Check each new import
        for imp in new_imports:
            if self._is_import_allowed(imp, original_imports):
                continue
            else:
                logger.warning(f"Mutation rejected: unauthorized import '{imp}'")
                return False

        return True

    def _is_import_allowed(self, import_name: str, original_imports: Set[str]) -> bool:
        """
        Check if a specific import is allowed.

        Args:
            import_name: Name of import to check
            original_imports: Set of imports from original code

        Returns:
            True if import is allowed
        """
        return (
            import_name in original_imports
            or import_name in STDLIB_WHITELIST
            or import_name in self.additional_allowed
        )

    def get_unauthorized_imports(
        self, new_ir: schema.Module, original_imports: Set[str]
    ) -> Set[str]:
        """
        Get set of unauthorized imports in new IR.

        Args:
            new_ir: New IR module to check
            original_imports: Set of imports from original code

        Returns:
            Set of unauthorized import names
        """
        new_imports = self.extract_imports(new_ir)
        unauthorized = set()

        for imp in new_imports:
            if not self._is_import_allowed(imp, original_imports):
                unauthorized.add(imp)

        return unauthorized

    def add_allowed_import(self, import_name: str) -> None:
        """
        Add an import to the allowed list.

        Args:
            import_name: Import name to allow
        """
        self.additional_allowed.add(import_name)

    def remove_allowed_import(self, import_name: str) -> None:
        """
        Remove an import from the allowed list.

        Args:
            import_name: Import name to remove
        """
        self.additional_allowed.discard(import_name)

    def get_allowed_imports(self) -> Set[str]:
        """
        Get complete set of allowed imports.

        Returns:
            Set containing stdlib whitelist + additional allowed imports
        """
        return STDLIB_WHITELIST | self.additional_allowed


# Global validator instance for convenience
_default_validator = ImportValidator()


def validate_imports(new_ir: schema.Module, original_imports: Set[str]) -> bool:
    """
    Convenience function using default validator.

    Args:
        new_ir: New IR module to validate
        original_imports: Set of imports from original code

    Returns:
        True if all imports are authorized
    """
    return _default_validator.validate_imports(new_ir, original_imports)


def extract_imports(ir: schema.Module) -> Set[str]:
    """
    Convenience function to extract imports using default validator.

    Args:
        ir: IR module to extract imports from

    Returns:
        Set of base module names
    """
    return _default_validator.extract_imports(ir)


def get_unauthorized_imports(new_ir: schema.Module, original_imports: Set[str]) -> Set[str]:
    """
    Convenience function to get unauthorized imports using default validator.

    Args:
        new_ir: New IR module to check
        original_imports: Set of imports from original code

    Returns:
        Set of unauthorized import names
    """
    return _default_validator.get_unauthorized_imports(new_ir, original_imports)
