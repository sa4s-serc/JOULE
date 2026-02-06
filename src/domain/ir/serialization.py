"""
IR Serialization and Deserialization for persistence and debugging.
"""

import json
from pathlib import Path
from typing import Any, Dict

from src.domain.ir.schema import IRNode, Module


class IRJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle IR nodes and other non-serializable types."""
    
    def default(self, obj: Any) -> Any:
        """Handle special types that json.dumps doesn't know about."""
        # Handle IRNode and Pydantic models
        if hasattr(obj, 'model_dump'):
            try:
                return obj.model_dump()
            except Exception:
                pass
        # Handle objects with __dict__
        if hasattr(obj, '__dict__'):
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        # Fallback to string representation
        return str(obj)


class IRSerializer:
    """
    Serializes IR to JSON for storage and debugging.
    Enables saving IR snapshots at different mutation stages.

    Uses custom serialization to preserve type information for Union types.
    """

    @staticmethod
    def _add_type_info(obj: Any) -> Any:
        """Recursively add __type__ field to all IRNode instances."""
        if isinstance(obj, IRNode):
            # Get the class name first
            type_name = obj.__class__.__name__

            # Now get all fields from the model
            data = {"__type__": type_name}

            # Process each field manually to preserve nested IRNodes
            # Access model_fields from class to avoid deprecation warning
            for field_name in obj.__class__.model_fields.keys():
                field_value = getattr(obj, field_name)
                data[field_name] = IRSerializer._add_type_info(field_value)

            return data
        elif isinstance(obj, list):
            return [IRSerializer._add_type_info(item) for item in obj]
        elif isinstance(obj, tuple):
            # Handle tuples (used in keywords)
            return tuple(IRSerializer._add_type_info(item) for item in obj)
        elif isinstance(obj, dict):
            return {k: IRSerializer._add_type_info(v) for k, v in obj.items()}
        else:
            # Primitive types (int, str, bool, None, etc.)
            return obj

    @staticmethod
    def serialize(module: Module) -> str:
        """Convert IR Module to JSON string with type information."""
        data = IRSerializer._add_type_info(module)
        # Use custom encoder as fallback to handle any non-serializable types
        return json.dumps(data, indent=2, cls=IRJSONEncoder)

    @staticmethod
    def deserialize(json_str: str) -> Module:
        """Convert JSON string to IR Module."""
        data = json.loads(json_str)
        # Note: Full deserialization would require reconstructing types from __type__ field
        # For now, this is primarily used for saving snapshots, not loading
        return Module(**data)

    @staticmethod
    def save(module: Module, filepath: Path):
        """Save IR to a file."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            f.write(IRSerializer.serialize(module))

    @staticmethod
    def load(filepath: Path) -> Module:
        """Load IR from a file."""
        with open(filepath, "r") as f:
            return IRSerializer.deserialize(f.read())


class IRDiffer:
    """
    Compares two IR trees and produces a diff.
    Useful for understanding what mutations changed.
    """

    @staticmethod
    def diff(ir1: Module, ir2: Module) -> Dict[str, Any]:
        """
        Compare two IR modules and return differences.
        Returns a dictionary describing the changes.
        """
        changes = {"added": [], "removed": [], "modified": []}

        # Convert to JSON for comparison
        dict1 = ir1.model_dump()
        dict2 = ir2.model_dump()

        # Simple comparison (could be more sophisticated)
        if dict1 != dict2:
            changes["modified"].append({"type": "module", "details": "Module structure changed"})

        return changes

    @staticmethod
    def format_diff(diff: Dict[str, Any]) -> str:
        """Format diff as human-readable string."""
        lines = []

        if diff["added"]:
            lines.append("Added:")
            for item in diff["added"]:
                lines.append(f"  + {item}")

        if diff["removed"]:
            lines.append("Removed:")
            for item in diff["removed"]:
                lines.append(f"  - {item}")

        if diff["modified"]:
            lines.append("Modified:")
            for item in diff["modified"]:
                lines.append(f"  ~ {item}")

        return "\n".join(lines) if lines else "No changes"
