"""
Common utility functions and constants.

Provides shared utilities for:
- Code hashing
- Dictionary operations
- Metrics formatting
- JSON serialization
- Performance timing
"""
from typing import Any, Dict, List, Optional, Callable, TypeVar
from functools import wraps
import hashlib
import json
import time
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


def compute_code_hash(code: str) -> str:
    """
    Compute MD5 hash of code string.
    
    Args:
        code: Source code string
        
    Returns:
        Hexadecimal hash string
    """
    return hashlib.md5(code.encode('utf-8')).hexdigest()


def compute_content_hash(content: str, algorithm: str = 'sha256', length: int = 16) -> str:
    """
    Compute hash of content with configurable algorithm and length.
    
    Args:
        content: String content to hash
        algorithm: Hash algorithm ('md5', 'sha256', etc.)
        length: Number of hex characters to return
        
    Returns:
        Truncated hexadecimal hash string
    """
    hasher = hashlib.new(algorithm)
    hasher.update(content.encode('utf-8'))
    return hasher.hexdigest()[:length]


def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)
        
    Returns:
        Merged dictionary
    """
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def format_metrics(metrics: Dict[str, float], precision: int = 4) -> Dict[str, str]:
    """
    Format metrics dictionary for display.
    
    Args:
        metrics: Dictionary of metric names to values
        precision: Number of decimal places
        
    Returns:
        Dictionary with formatted values
    """
    return {k: f"{v:.{precision}f}" for k, v in metrics.items()}


def safe_json_dump(obj: Any, **kwargs) -> str:
    """
    Safely dump object to JSON, handling non-serializable types.
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments for json.dumps
        
    Returns:
        JSON string
    """
    def default_handler(o):
        if hasattr(o, '__dict__'):
            return o.__dict__
        if hasattr(o, 'value'):  # Handle enums
            return o.value
        return str(o)
    
    return json.dumps(obj, default=default_handler, **kwargs)


def timed(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to measure and log function execution time.
    
    Usage:
        @timed
        def my_function():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.perf_counter() - start
            logger.debug(f"{func.__name__} took {elapsed:.3f}s")
    return wrapper


class Timer:
    """
    Context manager for timing code blocks.
    
    Usage:
        with Timer("operation name") as t:
            ...
        print(f"Took {t.elapsed:.3f}s")
    """
    
    __slots__ = ('name', 'start', 'elapsed', 'log')
    
    def __init__(self, name: str = "operation", log: bool = True):
        self.name = name
        self.start: float = 0
        self.elapsed: float = 0
        self.log = log
    
    def __enter__(self) -> 'Timer':
        self.start = time.perf_counter()
        return self
    
    def __exit__(self, *args) -> None:
        self.elapsed = time.perf_counter() - self.start
        if self.log:
            logger.debug(f"{self.name} took {self.elapsed:.3f}s")


def chunk_list(lst: List[T], chunk_size: int) -> List[List[T]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        lst: List to split
        chunk_size: Maximum size of each chunk
        
    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def first_or_none(lst: List[T]) -> Optional[T]:
    """Return first element of list or None if empty."""
    return lst[0] if lst else None


def flatten(nested: List[List[T]]) -> List[T]:
    """Flatten a list of lists into a single list."""
    return [item for sublist in nested for item in sublist]
