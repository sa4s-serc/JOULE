import subprocess
import sys
import os
import json
import tempfile
import logging
from typing import Tuple, Dict

from src.domain.interfaces import CodeRunner as ICodeRunner

logger = logging.getLogger(__name__)

class GreenGymRunner(ICodeRunner):
    """
    Adapter for the existing Green Gym runner to match the domain interface.
    """
    
    def __init__(self, timeout_seconds: int = 10, samples: int = 1):
        self.timeout_seconds = timeout_seconds
        self.samples = samples

    def run(self, code_str: str, test_code_str: str) -> Tuple[bool, Dict[str, float], str]:
        """
        Runs the provided code string multiple times and aggregates metrics.
        """
        # Create a temporary directory for this run configuration
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write the candidate code
            candidate_path = os.path.join(tmpdir, "candidate.py")
            with open(candidate_path, "w") as f:
                f.write(code_str)
            
            # Write the harness script
            harness_code = self._get_harness_code(test_code_str, tmpdir)
            harness_path = os.path.join(tmpdir, "harness.py")
            with open(harness_path, "w") as f:
                f.write(harness_code)

            # Accumulate results
            all_metrics: Dict[str, list] = {}
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
            
            # Determine overall success (must pass all/majority? Let's say all for correctness)
            # If we are doing performance testing, we assume correctness is deterministic.
            # If it fails sporadically, it's flaky/incorrect.
            overall_success = (success_count == self.samples)
            if not overall_success and success_count > 0:
                 logger.warning(f"Flaky execution: {success_count}/{self.samples} passed.")
            
            if not overall_success:
                return False, {}, last_output
            
            # Aggregate metrics (Median)
            aggregated_metrics = {}
            for k, values in all_metrics.items():
                aggregated_metrics[k] = self._median(values)
                
            return True, aggregated_metrics, last_output

    def _median(self, values: list) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        n = len(sorted_v)
        mid = n // 2
        if n % 2 == 1:
            return sorted_v[mid]
        else:
            return (sorted_v[mid-1] + sorted_v[mid]) / 2.0

    def _run_single_sample(self, harness_path: str, cwd: str) -> Tuple[bool, Dict[str, float], str]:
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
            
            if process.returncode != 0:
                if "__HEDGE_RESULT_START__" in stdout:
                    pass 
                else:
                    return False, {}, stdout + "\n" + stderr

            if "__HEDGE_RESULT_START__" in stdout:
                try:
                    json_str = stdout.split("__HEDGE_RESULT_START__")[1].split("__HEDGE_RESULT_END__")[0]
                    result = json.loads(json_str)
                    return result["success"], result["metrics"], stdout
                except Exception as e:
                    return False, {}, f"Failed to parse result JSON: {e}\nOutput:\n{stdout}"
            else:
                return False, {}, "Could not find result in output.\n" + stdout + "\n" + stderr

        except subprocess.TimeoutExpired:
            return False, {"timeout": True}, "Timeout expired"
        except Exception as e:
            return False, {}, str(e)

    def _get_harness_code(self, test_code_str: str, tmpdir: str) -> str:
        return f"""
import sys
import os
import json
import traceback
import time

# Add current dir to path so we can import candidate
sys.path.append('{tmpdir}')
sys.path.append('{os.getcwd()}')
sys.path.insert(0, '{os.getcwd()}') # Prioritize CWD


try:
    from src.infrastructure.execution.monitor import EnergyMonitor
except ImportError:
    print("Error: Could not import EnergyMonitor. Check PYTHONPATH.", file=sys.stderr)
    sys.exit(1)


import candidate
# Hack to allow 'from complex_target import process_data' to work when we only have candidate.py
sys.modules['complex_target'] = candidate
sys.modules['target_complex'] = candidate
sys.modules['target'] = candidate
sys.modules['target_opt'] = candidate
sys.modules['target_fib'] = candidate
sys.modules['target_search'] = candidate
sys.modules['target_formal'] = candidate

{test_code_str}

if __name__ == "__main__":
    monitor = EnergyMonitor()
    monitor.start()
    
    success = False
    try:
        # Check if 'test' function exists
        if 'test' in globals():
            globals()['test']()
            success = True
        else:
            # If no test function, we assume the script body was the test
            # and if we reached here, it didn't crash.
            success = True
            
    except Exception:
        traceback.print_exc()
        success = False
        
    metrics = monitor.stop()
    
    result = {{
        "success": success,
        "metrics": metrics
    }}
    
    print("__HEDGE_RESULT_START__")
    print(json.dumps(result))
    print("__HEDGE_RESULT_END__")
"""
