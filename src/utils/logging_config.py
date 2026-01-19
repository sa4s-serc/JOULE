"""
Logging configuration for HEDGE.

Provides standardized logging setup across all modules.
"""
import logging
import sys
from pathlib import Path
from typing import Optional

def silence_noisy_libraries(level: int = logging.DEBUG):
    """
    Silence verbose logging from third-party libraries.
    
    Args:
        level: Only silence if logging level is at or below this value
    """
    noisy_libraries = [
        "matplotlib",
        "matplotlib.font_manager",
        "matplotlib.pyplot",
        "matplotlib.backends",
        "PIL",
        "urllib3",
        "git",
        "markdown_it",
        "rich",
        "requests",
        "openai",
        "httpcore",
        "httpx",
        "google",
        "google.auth",
        "absl"
    ]
    for lib in noisy_libraries:
        logging.getLogger(lib).setLevel(logging.INFO)

def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    verbose: bool = False,
    log_to_console: bool = True
) -> logging.Logger:
    """
    Set up logging configuration for HEDGE.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        verbose: If True, use more detailed format
        log_to_console: If True, log to stdout
        
    Returns:
        Configured root logger
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatters
    if verbose:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Silence noisy libraries if level is DEBUG
    if numeric_level == logging.DEBUG:
        silence_noisy_libraries(numeric_level)
            
    return root_logger

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)
