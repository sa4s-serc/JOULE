"""
API Utility Functions

Provides helper functions for API operations, including JSON serialization
of complex objects like IR nodes.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def sanitize_for_json(obj: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """
    Recursively sanitize an object to make it JSON-serializable.
    
    This function handles:
    - Pydantic models (IR nodes like Constant, Expression, etc.)
    - Nested dictionaries and lists
    - Datetime objects
    - Sets
    - Custom objects with __dict__
    
    Args:
        obj: The object to sanitize
        depth: Current recursion depth (for protection)
        max_depth: Maximum recursion depth before converting to string
        
    Returns:
        A JSON-serializable version of the object
        
    Examples:
        >>> from src.domain.ir.schema import Constant
        >>> const = Constant(value=42, kind="int")
        >>> sanitize_for_json(const)
        {'value': 42, 'kind': 'int', ...}
        
        >>> data = {"metrics": {"constant": const}, "values": [1, 2, const]}
        >>> sanitize_for_json(data)
        {'metrics': {'constant': {'value': 42, ...}}, 'values': [1, 2, {'value': 42, ...}]}
    """
    # Prevent infinite recursion
    if depth > max_depth:
        logger.warning(f"[JSON_SANITIZE] Max recursion depth {max_depth} reached for {type(obj).__name__}")
        try:
            return str(obj)
        except Exception:
            return f"<{type(obj).__name__} - max depth>"
    
    # Handle None
    if obj is None:
        return None
    
    # Handle basic JSON-safe types
    if isinstance(obj, (str, int, float, bool)):
        return obj
    
    # Handle datetime objects
    if isinstance(obj, datetime):
        return obj.isoformat()
    
    # Handle Pydantic models (IR nodes) - CRITICAL for IR objects
    try:
        from pydantic import BaseModel
        if isinstance(obj, BaseModel):
            try:
                # Use model_dump with mode='json' for JSON-compatible output
                # This handles nested models and converts them properly
                dumped = obj.model_dump(mode='json', exclude_none=True)
                # Recursively sanitize the dumped data (in case of nested non-standard types)
                return sanitize_for_json(dumped, depth + 1, max_depth)
            except Exception as e:
                logger.warning(f"[JSON_SANITIZE] Failed to dump Pydantic model {type(obj).__name__}: {e}")
                # Fallback: try to extract just the value if it's a simple value holder
                if hasattr(obj, 'value') and not hasattr(obj, 'left'):  # Avoid BinaryOp, etc.
                    return sanitize_for_json(obj.value, depth + 1, max_depth)
                # Otherwise convert to a simple representation
                return f"<{type(obj).__name__}>"
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"[JSON_SANITIZE] Error checking Pydantic model: {e}")
    
    # Handle lists and tuples
    if isinstance(obj, (list, tuple)):
        try:
            result = [sanitize_for_json(item, depth + 1, max_depth) for item in obj]
            return result
        except Exception as e:
            logger.warning(f"[JSON_SANITIZE] Failed to serialize list/tuple: {e}")
            # Fallback: convert each item to string
            return [str(item) for item in obj]
    
    # Handle dictionaries
    if isinstance(obj, dict):
        try:
            result = {}
            for key, value in obj.items():
                # Ensure key is a string (JSON keys must be strings)
                safe_key = str(key) if not isinstance(key, str) else key
                result[safe_key] = sanitize_for_json(value, depth + 1, max_depth)
            return result
        except Exception as e:
            logger.warning(f"[JSON_SANITIZE] Failed to serialize dict: {e}")
            # Fallback: convert everything to strings
            return {str(k): str(v) for k, v in obj.items()}
    
    # Handle sets (convert to lists)
    if isinstance(obj, set):
        try:
            return [sanitize_for_json(item, depth + 1, max_depth) for item in obj]
        except Exception as e:
            logger.warning(f"[JSON_SANITIZE] Failed to serialize set: {e}")
            return [str(item) for item in obj]
    
    # Handle enums
    try:
        from enum import Enum
        if isinstance(obj, Enum):
            return obj.value
    except ImportError:
        pass
    
    # Handle objects with __dict__ (custom classes)
    if hasattr(obj, '__dict__'):
        try:
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):  # Skip private attributes
                    result[key] = sanitize_for_json(value, depth + 1, max_depth)
            return result
        except Exception as e:
            logger.warning(f"[JSON_SANITIZE] Failed to serialize object with __dict__: {e}")
            return f"<{type(obj).__name__}>"
    
    # For any other type, convert to string as fallback
    try:
        # Try to get a meaningful representation
        if hasattr(obj, '__repr__'):
            return str(obj)
        return f"<{type(obj).__name__}>"
    except Exception:
        return "<unserializable>"


def validate_json_serializable(obj: Any) -> bool:
    """
    Check if an object is JSON-serializable without actually serializing it.
    
    Args:
        obj: The object to check
        
    Returns:
        True if the object appears to be JSON-serializable, False otherwise
    """
    import json
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Safely serialize an object to JSON, sanitizing it first if needed.
    
    Args:
        obj: The object to serialize
        **kwargs: Additional arguments to pass to json.dumps
        
    Returns:
        JSON string representation of the object
        
    Example:
        >>> data = {"constant": Constant(value=42, kind="int")}
        >>> json_str = safe_json_dumps(data, indent=2)
    """
    import json
    
    # First try direct serialization
    try:
        return json.dumps(obj, **kwargs)
    except (TypeError, ValueError):
        # If that fails, sanitize and try again
        sanitized = sanitize_for_json(obj)
        return json.dumps(sanitized, **kwargs)
