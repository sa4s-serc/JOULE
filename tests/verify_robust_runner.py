import logging
import os
import sys

# Ensure src is in path
sys.path.append(os.getcwd())

from src.infrastructure.execution.runner import GreenGymRunner

# Configure logging
logging.basicConfig(level=logging.INFO)


def verify_robust_runner():
    print("Initializing Robust Runner (samples=3)...")
    runner = GreenGymRunner(timeout_seconds=30, samples=3)

    # Simple code that does some work
    code = """
import time
def compute():
    # Simulate work
    val = 0
    for i in range(100):
        val += i
    time.sleep(0.01) # Sleep to ensure non-zero duration
    return val
"""

    # Test harness calls compute
    test_code = """
import candidate
candidate.compute()
"""

    print("Running execution...")
    success, metrics, output = runner.run(code, test_code)

    if success:
        print("SUCCESS: Execution passed.")
        print(f"Aggregated Metrics: {metrics}")
        # Verify metrics look reasonable (e.g. median)
        # Note: Since we can't see individual runs easily without debug logs, we just check existence.
        if "duration_seconds" in metrics:
            print(f"Duration: {metrics['duration_seconds']:.6f}s")
    else:
        print("FAILED: Execution failed.")
        print("Output:", output)


if __name__ == "__main__":
    verify_robust_runner()
