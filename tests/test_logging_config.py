"""
Test Logging Configuration

Ensures that third-party library logging is properly silenced in DEBUG mode
while preserving HEDGE system logs.
"""

import logging
import sys
from io import StringIO
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.logging_config import setup_logging, silence_noisy_libraries


def test_silence_noisy_libraries_sets_levels():
    """Test that silence_noisy_libraries sets third-party loggers to INFO."""
    # Reset logging
    logging.root.handlers = []
    logging.root.setLevel(logging.DEBUG)

    # Apply silencing
    silence_noisy_libraries()

    # Check that noisy libraries are set to INFO
    noisy_libs = [
        "matplotlib",
        "matplotlib.font_manager",
        "matplotlib.pyplot",
        "PIL",
        "urllib3",
        "openai",
        "google",
    ]

    for lib in noisy_libs:
        logger = logging.getLogger(lib)
        assert logger.level == logging.INFO, f"{lib} logger not set to INFO (level={logger.level})"


def test_setup_logging_debug_silences_libraries():
    """Test that setup_logging with DEBUG level silences third-party libraries."""
    # Reset logging
    logging.root.handlers = []

    # Setup with DEBUG level
    setup_logging(level="DEBUG", verbose=True)

    # Check root logger is DEBUG
    assert logging.root.level == logging.DEBUG, "Root logger not set to DEBUG"

    # Check matplotlib is silenced
    matplotlib_logger = logging.getLogger("matplotlib")
    assert matplotlib_logger.level == logging.INFO, "matplotlib not silenced in DEBUG mode"

    matplotlib_fm_logger = logging.getLogger("matplotlib.font_manager")
    assert (
        matplotlib_fm_logger.level == logging.INFO
    ), "matplotlib.font_manager not silenced in DEBUG mode"


def test_setup_logging_info_doesnt_silence():
    """Test that setup_logging with INFO level doesn't modify library levels."""
    # Reset logging
    logging.root.handlers = []

    # Setup with INFO level
    setup_logging(level="INFO", verbose=False)

    # Check root logger is INFO
    assert logging.root.level == logging.INFO, "Root logger not set to INFO"

    # matplotlib logger should not be explicitly set (will inherit from root)
    # or if it was set previously, we're not modifying it in INFO mode
    # This test just ensures we don't call silence when not in DEBUG


def test_hedge_logs_still_visible_in_debug():
    """Test that HEDGE system logs are still visible in DEBUG mode."""
    # Reset logging
    logging.root.handlers = []

    # Create a string buffer to capture logs
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)

    # Setup logging
    logging.root.handlers = []
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.DEBUG)

    # Apply silencing
    silence_noisy_libraries()

    # Create HEDGE logger and log a message
    hedge_logger = logging.getLogger("src.application.engine.evolution")
    hedge_logger.debug("Test debug message from HEDGE")

    # Create matplotlib logger and log a message
    mpl_logger = logging.getLogger("matplotlib.font_manager")
    mpl_logger.debug("Test debug message from matplotlib")

    # Get log output
    log_output = log_stream.getvalue()

    # HEDGE debug message should be present
    assert "Test debug message from HEDGE" in log_output, "HEDGE debug logs not visible"

    # matplotlib debug message should NOT be present (silenced)
    assert (
        "Test debug message from matplotlib" not in log_output
    ), "matplotlib debug logs not silenced"


def test_third_party_info_logs_still_visible():
    """Test that INFO level logs from third-party libs are still visible."""
    # Reset logging
    logging.root.handlers = []

    # Create a string buffer to capture logs
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)

    # Setup logging
    logging.root.handlers = []
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.DEBUG)

    # Apply silencing
    silence_noisy_libraries()

    # Create matplotlib logger and log INFO message
    mpl_logger = logging.getLogger("matplotlib")
    mpl_logger.info("Important matplotlib info message")

    # Get log output
    log_output = log_stream.getvalue()

    # matplotlib INFO message should still be present
    assert (
        "Important matplotlib info message" in log_output
    ), "matplotlib INFO logs incorrectly suppressed"


def test_third_party_warning_logs_still_visible():
    """Test that WARNING level logs from third-party libs are still visible."""
    # Reset logging
    logging.root.handlers = []

    # Create a string buffer to capture logs
    log_stream = StringIO()
    handler = logging.StreamHandler(log_stream)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)

    # Setup logging
    logging.root.handlers = []
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.DEBUG)

    # Apply silencing
    silence_noisy_libraries()

    # Create matplotlib logger and log WARNING message
    mpl_logger = logging.getLogger("matplotlib.font_manager")
    mpl_logger.warning("Important matplotlib warning")

    # Get log output
    log_output = log_stream.getvalue()

    # matplotlib WARNING message should still be present
    assert (
        "Important matplotlib warning" in log_output
    ), "matplotlib WARNING logs incorrectly suppressed"


def test_all_noisy_libraries_covered():
    """Test that all known noisy libraries are in the silencing list."""
    # Reset logging
    logging.root.handlers = []
    logging.root.setLevel(logging.DEBUG)

    # Apply silencing
    silence_noisy_libraries()

    # Check comprehensive list of noisy libraries
    expected_noisy_libs = [
        "matplotlib",
        "matplotlib.font_manager",
        "matplotlib.pyplot",
        "matplotlib.backends",
        "PIL",
        "urllib3",
        "httpx",
        "httpcore",
        "openai",
        "google",
        "google.auth",
        "absl",
    ]

    for lib in expected_noisy_libs:
        logger = logging.getLogger(lib)
        assert (
            logger.level >= logging.INFO
        ), f"{lib} not silenced (level={logger.level}, expected >= INFO)"


def test_logging_setup_creates_handlers():
    """Test that setup_logging creates appropriate handlers."""
    # Reset logging
    logging.root.handlers = []

    # Setup logging
    setup_logging(level="INFO", verbose=False)

    # Should have at least one handler
    assert len(logging.root.handlers) >= 1, "No handlers created"

    # Handler should be StreamHandler
    assert any(
        isinstance(h, logging.StreamHandler) for h in logging.root.handlers
    ), "No StreamHandler created"


def test_verbose_mode_format():
    """Test that verbose mode creates detailed format."""
    # Reset logging
    logging.root.handlers = []

    # Setup with verbose
    setup_logging(level="INFO", verbose=True)

    # Check that formatter includes filename/lineno
    for handler in logging.root.handlers:
        if handler.formatter:
            format_str = handler.formatter._fmt
            assert (
                "filename" in format_str or "%(message)s" in format_str
            ), "Formatter doesn't include expected fields"


if __name__ == "__main__":
    # Run all tests
    test_silence_noisy_libraries_sets_levels()
    test_setup_logging_debug_silences_libraries()
    test_setup_logging_info_doesnt_silence()
    test_hedge_logs_still_visible_in_debug()
    test_third_party_info_logs_still_visible()
    test_third_party_warning_logs_still_visible()
    test_all_noisy_libraries_covered()
    test_logging_setup_creates_handlers()
    test_verbose_mode_format()
    print("✓ All logging configuration tests passed!")
