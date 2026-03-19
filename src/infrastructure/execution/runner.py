"""
Code Execution Runner - Test Harness for Candidate Solutions

Provides:
- Subprocess-based code execution with timeout
- Energy and performance monitoring
- Parallel evaluation support
- Metrics aggregation
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.domain.interfaces import CodeRunner as ICodeRunner

logger = logging.getLogger(__name__)

MAX_SAMPLES = 50
MAX_WARMUP_ITERATIONS = 100


@dataclass
class EvaluationResult:
    """Result of a single code evaluation."""

    success: bool
    metrics: Dict[str, float]
    output: str
    code_hash: str = ""


class GreenGymRunner(ICodeRunner):
    """
    Code runner with energy monitoring and parallel evaluation support.

    Features:
    - Subprocess isolation for safety
    - Configurable timeout
    - Multiple sample aggregation
    - Parallel batch evaluation
    """

    def __init__(
        self,
        timeout_seconds: int = 600,
        samples: int = 1,
        max_workers: int = 1,
        warmup_iterations: int = 0,
        base_seed: Optional[int] = None,
        harness_repetitions: int = 1,
    ):
        """
        Args:
            timeout_seconds: Maximum execution time per sample
            samples: Number of samples to run for metrics aggregation
            max_workers: Number of parallel workers for batch evaluation
            harness_repetitions: Number of times to repeat the test function inside one
                monitored harness run. Increase for very fast functions so the energy
                monitor (CodeCarbon, 100ms sampling) has time to record at least one
                sample. Reported metrics are normalised per-call (divided by this value).
        """
        self.timeout_seconds = timeout_seconds
        self.samples = max(1, min(samples, MAX_SAMPLES))
        self.max_workers = max_workers
        self.warmup_iterations = max(0, min(warmup_iterations, MAX_WARMUP_ITERATIONS))
        self.base_seed = base_seed
        self.harness_repetitions = max(1, harness_repetitions)

    def run(
        self, code_str: str, test_code_str: str, allowed_imports: Optional[List[str]] = None
    ) -> Tuple[bool, Dict[str, float], str]:
        """
        Run code and collect metrics.

        Args:
            code_str: The candidate code to evaluate
            test_code_str: The test harness code
            allowed_imports: List of allowed module names to inject

        Returns:
            Tuple of (success, metrics_dict, output_string)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write candidate code
            candidate_path = os.path.join(tmpdir, "candidate.py")
            with open(candidate_path, "w") as f:
                f.write(code_str)

            # Write harness
            harness_code = self._get_harness_code(
                test_code_str, tmpdir, allowed_imports=allowed_imports
            )
            harness_path = os.path.join(tmpdir, "harness.py")
            with open(harness_path, "w") as f:
                f.write(harness_code)

            # Run samples and aggregate
            all_metrics: Dict[str, List[float]] = {}
            last_output = ""
            success_count = 0

            for i in range(self.samples):
                iteration_seed: Optional[int] = None
                if self.base_seed is not None:
                    iteration_seed = self.base_seed + i
                success, metrics, output = self._run_single_sample(
                    harness_path,
                    tmpdir,
                    iteration_index=i,
                    iteration_seed=iteration_seed,
                )
                last_output = output

                if success:
                    success_count += 1
                    for k, v in metrics.items():
                        if k not in all_metrics:
                            all_metrics[k] = []
                        all_metrics[k].append(v)

            # Require all samples to pass
            overall_success = success_count == self.samples
            if not overall_success and success_count > 0:
                logger.warning(f"Flaky execution: {success_count}/{self.samples} passed")

            if not overall_success:
                return False, {}, last_output

            # Aggregate using sum instead of median
            aggregated = {k: sum(v) for k, v in all_metrics.items()}
            return True, aggregated, last_output

    def run_batch(
        self,
        # (code, test_code, identifier)
        candidates: List[Tuple[str, str, str]],
    ) -> List[EvaluationResult]:
        """
        Evaluate multiple candidates in parallel.

        Args:
            candidates: List of (code_str, test_code_str, identifier) tuples

        Returns:
            List of EvaluationResult objects
        """
        if self.max_workers <= 1:
            # Sequential execution
            return [
                EvaluationResult(*self.run(code, test_code), code_hash=identifier)
                for code, test_code, identifier in candidates
            ]

        # Parallel execution
        results = []
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._run_isolated, code, test_code): identifier
                for code, test_code, identifier in candidates
            }

            for future in as_completed(futures):
                identifier = futures[future]
                try:
                    success, metrics, output = future.result()
                    results.append(
                        EvaluationResult(
                            success=success, metrics=metrics, output=output, code_hash=identifier
                        )
                    )
                except Exception as e:
                    logger.error(f"Parallel evaluation failed for {identifier}: {e}")
                    results.append(
                        EvaluationResult(
                            success=False, metrics={}, output=str(e), code_hash=identifier
                        )
                    )

        return results

    def _run_isolated(
        self, code_str: str, test_code_str: str, allowed_imports: Optional[List[str]] = None
    ) -> Tuple[bool, Dict[str, float], str]:
        """Run evaluation in isolation (for parallel execution)."""
        return self.run(code_str, test_code_str, allowed_imports=allowed_imports)

    def _run_single_sample(
        self,
        harness_path: str,
        cwd: str,
        iteration_index: int = 0,
        iteration_seed: Optional[int] = None,
    ) -> Tuple[bool, Dict[str, float], str]:
        """Execute a single sample run."""
        cmd = [sys.executable, harness_path]
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
            env["HEDGE_TEST_ITERATION"] = str(iteration_index)
            env["HEDGE_TEST_WARMUP_ITERATIONS"] = str(self.warmup_iterations)
            env["HEDGE_HARNESS_REPETITIONS"] = str(self.harness_repetitions)
            if iteration_seed is not None:
                env["HEDGE_TEST_SEED"] = str(iteration_seed)

            process = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout_seconds, env=env, cwd=cwd
            )

            stdout = process.stdout
            stderr = process.stderr

            # Check for result marker even if return code is non-zero
            if "__HEDGE_RESULT_START__" in stdout:
                try:
                    json_str = stdout.split("__HEDGE_RESULT_START__")[1].split(
                        "__HEDGE_RESULT_END__"
                    )[0]
                    result = json.loads(json_str)
                    return result["success"], result["metrics"], stdout
                except Exception as e:
                    return False, {}, f"Failed to parse result: {e}\nOutput:\n{stdout}"

            if process.returncode != 0:
                return False, {}, f"Exit code {process.returncode}\n{stdout}\n{stderr}"

            return False, {}, f"No result marker found\n{stdout}\n{stderr}"

        except subprocess.TimeoutExpired:
            return False, {"timeout": 1.0}, "Timeout expired"
        except Exception as e:
            return False, {}, str(e)

    def _get_harness_code(
        self, test_code_str: str, tmpdir: str, allowed_imports: Optional[List[str]] = None
    ) -> str:
        """Generate the test harness code."""
        import_lines = ""
        if allowed_imports:
            for imp in allowed_imports:
                import_lines += f"try: import {imp}\nexcept ImportError: pass\n"

        return f"""
import sys
import os
import json
import traceback
import time
import random

try:
    import numpy as _np
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False

# Setup paths
sys.path.insert(0, '{tmpdir}')
sys.path.insert(0, '{os.getcwd()}')

try:
    from src.infrastructure.execution.monitor import EnergyMonitor
except ImportError:
    print("Warning: EnergyMonitor not available", file=sys.stderr)
    class EnergyMonitor:
        def start(self): pass
        def stop(self): return {{"duration_seconds": 0, "energy_joules": 0}}

seed_env = os.environ.get("HEDGE_TEST_SEED")
if seed_env is not None:
    try:
        _seed_value = int(seed_env)
        random.seed(_seed_value)
        if _HAS_NUMPY:
            _np.random.seed(_seed_value)
    except Exception:
        pass

# Import candidate
import candidate
from candidate import *

{import_lines}

# Module aliasing for test compatibility
for alias in ['complex_target', 'target_complex', 'target', 'target_opt', 
              'target_fib', 'target_search', 'target_formal']:
    sys.modules[alias] = candidate
    # Also inject into globals if not already there
    try:
        globals()[alias] = candidate
    except:
        pass

{test_code_str}

if __name__ == "__main__":
    monitor = EnergyMonitor()
    warmup_env = os.environ.get("HEDGE_TEST_WARMUP_ITERATIONS", "0")
    try:
        warmup_iters = int(warmup_env)
    except Exception:
        warmup_iters = 0
    if warmup_iters < 0:
        warmup_iters = 0

    # Number of times to repeat the test inside the monitored window.
    # Increase via --harness-repetitions for very fast functions so the
    # energy monitor (CodeCarbon 100 ms sampling) captures at least one sample.
    try:
        harness_reps = max(1, int(os.environ.get("HEDGE_HARNESS_REPETITIONS", "1")))
    except Exception:
        harness_reps = 1

    def _run_tests_once(test_iteration=0):
        if 'test' in dir() and callable(test):
            try:
                import inspect as _inspect
                sig = _inspect.signature(test)
                if 'test_iteration' in sig.parameters:
                    test(test_iteration=test_iteration)
                else:
                    test()
            except Exception:
                test()
        else:
            test_funcs = [
                (name, obj) for name, obj in list(globals().items())
                if name.startswith('test_') and callable(obj)
            ]
            if test_funcs:
                for name, func in test_funcs:
                    try:
                        import inspect as _inspect
                        sig = _inspect.signature(func)
                        if 'test_iteration' in sig.parameters:
                            func(test_iteration=test_iteration)
                        else:
                            func()
                    except Exception:
                        func()

    for _ in range(warmup_iters):
        try:
            _run_tests_once()
        except Exception:
            traceback.print_exc()

    monitor.start()

    success = False
    error_msg = ""

    try:
        test_iteration = int(os.environ.get("HEDGE_TEST_ITERATION", "0"))
        # First call validates correctness; subsequent calls are for energy accumulation only
        _run_tests_once(test_iteration)
        for _ in range(harness_reps - 1):
            _run_tests_once(test_iteration)
        success = True
    except AssertionError as e:
        error_msg = f"Assertion failed: {{e}}"
        traceback.print_exc()
    except Exception as e:
        error_msg = f"Error: {{e}}"
        traceback.print_exc()

    metrics = monitor.stop()

    # Normalise to per-call metrics so comparisons are independent of harness_reps
    if harness_reps > 1:
        metrics = {{k: v / harness_reps for k, v in metrics.items()}}

    result = {{
        "success": success,
        "metrics": metrics,
        "error": error_msg
    }}

    print("__HEDGE_RESULT_START__")
    print(json.dumps(result))
    print("__HEDGE_RESULT_END__")
"""
