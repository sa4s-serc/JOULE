"""
Code Execution Runner - Test Harness for Candidate Solutions

Provides:
- Subprocess-based code execution with timeout
- Energy and performance monitoring
- Parallel evaluation support
- Metrics aggregation
"""
import subprocess
import sys
import os
import json
import tempfile
import logging
from typing import Tuple, Dict, List, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

from src.domain.interfaces import CodeRunner as ICodeRunner

logger = logging.getLogger(__name__)


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
        timeout_seconds: int = 10, 
        samples: int = 1,
        max_workers: int = 1
    ):
        """
        Args:
            timeout_seconds: Maximum execution time per sample
            samples: Number of samples to run for metrics aggregation
            max_workers: Number of parallel workers for batch evaluation
        """
        self.timeout_seconds = timeout_seconds
        self.samples = samples
        self.max_workers = max_workers

    def run(self, code_str: str, test_code_str: str) -> Tuple[bool, Dict[str, float], str]:
        """
        Run code and collect metrics.
        
        Args:
            code_str: The candidate code to evaluate
            test_code_str: The test harness code
            
        Returns:
            Tuple of (success, metrics_dict, output_string)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write candidate code
            candidate_path = os.path.join(tmpdir, "candidate.py")
            with open(candidate_path, "w") as f:
                f.write(code_str)
            
            # Write harness
            harness_code = self._get_harness_code(test_code_str, tmpdir)
            harness_path = os.path.join(tmpdir, "harness.py")
            with open(harness_path, "w") as f:
                f.write(harness_code)

            # Run samples and aggregate
            all_metrics: Dict[str, List[float]] = {}
            last_output = ""
            success_count = 0
            
            for _ in range(self.samples):
                success, metrics, output = self._run_single_sample(harness_path, tmpdir)
                last_output = output
                
                if success:
                    success_count += 1
                    for k, v in metrics.items():
                        if k not in all_metrics:
                            all_metrics[k] = []
                        all_metrics[k].append(v)
            
            # Require all samples to pass
            overall_success = (success_count == self.samples)
            if not overall_success and success_count > 0:
                logger.warning(f"Flaky execution: {success_count}/{self.samples} passed")
            
            if not overall_success:
                return False, {}, last_output
            
            # Aggregate using median
            aggregated = {k: self._median(v) for k, v in all_metrics.items()}
            return True, aggregated, last_output

    def run_batch(
        self, 
        candidates: List[Tuple[str, str, str]],  # (code, test_code, identifier)
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
                EvaluationResult(
                    *self.run(code, test_code),
                    code_hash=identifier
                )
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
                    results.append(EvaluationResult(
                        success=success,
                        metrics=metrics,
                        output=output,
                        code_hash=identifier
                    ))
                except Exception as e:
                    logger.error(f"Parallel evaluation failed for {identifier}: {e}")
                    results.append(EvaluationResult(
                        success=False,
                        metrics={},
                        output=str(e),
                        code_hash=identifier
                    ))
        
        return results
    
    def _run_isolated(self, code_str: str, test_code_str: str) -> Tuple[bool, Dict[str, float], str]:
        """Run evaluation in isolation (for parallel execution)."""
        return self.run(code_str, test_code_str)

    def _median(self, values: List[float]) -> float:
        """Calculate median of a list of values."""
        if not values:
            return 0.0
        sorted_v = sorted(values)
        n = len(sorted_v)
        mid = n // 2
        if n % 2 == 1:
            return sorted_v[mid]
        return (sorted_v[mid-1] + sorted_v[mid]) / 2.0

    def _run_single_sample(self, harness_path: str, cwd: str) -> Tuple[bool, Dict[str, float], str]:
        """Execute a single sample run."""
        cmd = [sys.executable, harness_path]
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=env,
                cwd=cwd
            )
            
            stdout = process.stdout
            stderr = process.stderr
            
            # Check for result marker even if return code is non-zero
            if "__HEDGE_RESULT_START__" in stdout:
                try:
                    json_str = stdout.split("__HEDGE_RESULT_START__")[1].split("__HEDGE_RESULT_END__")[0]
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

    def _get_harness_code(self, test_code_str: str, tmpdir: str) -> str:
        """Generate the test harness code."""
        return f'''
import sys
import os
import json
import traceback
import time

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

# Import candidate
import candidate
from candidate import *

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
    monitor.start()
    
    success = False
    error_msg = ""
    
    try:
        # Try different test function patterns
        if 'test' in dir() and callable(test):
            test()
            success = True
        else:
            # Look for test_* functions
            test_funcs = [
                (name, obj) for name, obj in list(globals().items())
                if name.startswith('test_') and callable(obj)
            ]
            
            if test_funcs:
                for name, func in test_funcs:
                    func()
                success = True
            else:
                # Assume script body is the test
                success = True
                
    except AssertionError as e:
        error_msg = f"Assertion failed: {{e}}"
        traceback.print_exc()
    except Exception as e:
        error_msg = f"Error: {{e}}"
        traceback.print_exc()
        
    metrics = monitor.stop()
    
    result = {{
        "success": success,
        "metrics": metrics,
        "error": error_msg
    }}
    
    print("__HEDGE_RESULT_START__")
    print(json.dumps(result))
    print("__HEDGE_RESULT_END__")
'''
