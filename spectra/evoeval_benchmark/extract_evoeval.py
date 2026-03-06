#!/usr/bin/env python3
"""
Extract EvoEval benchmark problems into organized folders for HEDGE optimization.
"""

import json
import os
from pathlib import Path


def extract_evoeval_problems(json_path: str, output_dir: str = "evoeval_benchmark"):
    """Extract problems from JSON and create organized folder structure."""

    # Read the JSON file
    with open(json_path, 'r') as f:
        problems = json.load(f)

    # Create base output directory
    base_path = Path(output_dir)
    base_path.mkdir(exist_ok=True)

    print(f"Extracting {len(problems)} EvoEval problems to {output_dir}/\n")

    for problem_id, problem_data in problems.items():
        print(f"Processing {problem_id}...")

        # Create problem directory
        problem_dir = base_path / problem_id
        problem_dir.mkdir(exist_ok=True)

        # Extract data
        prompt = problem_data.get('prompt', '')
        canonical_solution = problem_data.get('canonical_solution', '')
        entry_point = problem_data.get('entry_point', '')
        inputs = problem_data.get('inputs', [])

        # Create target.py (the code to optimize)
        target_code = f"{prompt}\n{canonical_solution}\n"
        target_path = problem_dir / "target.py"
        with open(target_path, 'w') as f:
            f.write(target_code)

        # Create test_target.py
        test_code = generate_test_code(entry_point, inputs, problem_data)
        test_path = problem_dir / "test_target.py"
        with open(test_path, 'w') as f:
            f.write(test_code)

        # Create README with problem info
        readme_content = f"""# {problem_id}

**Benchmark**: {problem_data.get('benchmark', 'N/A')}
**Parent**: {problem_data.get('parent', 'N/A')}
**Entry Point**: {entry_point}

## Problem Description

{prompt}

## Test Inputs

Total test cases: {len(inputs)}

## Running HEDGE

```bash
cd ../..
python main.py --target evoeval_benchmark/{problem_id}/target.py \\
               --tests evoeval_benchmark/{problem_id}/test_target.py \\
               --generations 5 \\
               --layers L1 L2
```
"""
        readme_path = problem_dir / "README.md"
        with open(readme_path, 'w') as f:
            f.write(readme_content)

        print(f"  ✓ Created {problem_dir}/")
        print(f"    - target.py ({len(target_code)} bytes)")
        print(f"    - test_target.py ({len(inputs)} test cases)")
        print(f"    - README.md")

    # Create master README
    create_master_readme(base_path, problems)

    print(f"\n✅ Successfully extracted {len(problems)} problems to {output_dir}/")
    print(f"\nTo run all benchmarks:")
    print(f"  python run_evoeval_benchmarks.py")


def generate_test_code(entry_point: str, inputs: list, problem_data: dict) -> str:
    """Generate test file content."""

    # Import the target module
    test_code = f'''"""
Test suite for {problem_data.get('task_id', 'N/A')}
Auto-generated from EvoEval benchmark
"""

from target import {entry_point}


def test_{entry_point}():
    """Test all cases for {entry_point}."""

    test_cases = [
'''

    # Add each test case
    for i, input_str in enumerate(inputs):
        # Clean up the input string
        input_str = input_str.strip()
        test_code += f"        ({input_str}),  # Test case {i+1}\n"

    test_code += "    ]\n\n"
    test_code += f'''    for i, test_input in enumerate(test_cases):
        try:
            # Handle single vs multiple arguments
            if isinstance(test_input, tuple):
                result = {entry_point}(*test_input)
            else:
                result = {entry_point}(test_input)
            # Test passed if no exception
        except Exception as e:
            print(f"Test case {{i+1}} failed: {{e}}")
            raise


if __name__ == "__main__":
    test_{entry_point}()
    print(f"All tests passed for {entry_point}!")
'''

    return test_code


def create_master_readme(base_path: Path, problems: dict):
    """Create a master README for all problems."""

    readme_content = f"""# EvoEval Benchmark Suite for HEDGE

This directory contains {len(problems)} difficult problems from the EvoEval benchmark, organized for optimization with HEDGE.

## Problems

| Problem ID | Function | Description |
|------------|----------|-------------|
"""

    for problem_id, problem_data in problems.items():
        entry_point = problem_data.get('entry_point', 'N/A')
        task_id = problem_data.get('task_id', 'N/A')
        # Extract first line of prompt as description
        prompt = problem_data.get('prompt', '')
        first_line = prompt.split('\\n')[0][:60] + '...' if len(prompt) > 60 else prompt.split('\\n')[0]

        readme_content += f"| {problem_id} | `{entry_point}` | {first_line} |\n"

    readme_content += f"""
## Quick Start

### Run a Single Problem

```bash
# Example: Run EvoEval_difficult_4
python main.py --target evoeval_benchmark/EvoEval_difficult_4/target.py \\
               --tests evoeval_benchmark/EvoEval_difficult_4/test_target.py \\
               --generations 5 \\
               --layers L1 L2 \\
               --visualize
```

### Run All Problems

```bash
python run_evoeval_benchmarks.py
```

## Structure

Each problem directory contains:
- `target.py` - The canonical solution to optimize
- `test_target.py` - Test suite with multiple test cases
- `README.md` - Problem-specific documentation

## Expected Optimizations

HEDGE will attempt to optimize these implementations through:
- **L1 (Intent)**: Algorithmic improvements (e.g., O(n²) → O(n log n))
- **L2 (Syntax)**: Code-level optimizations (list comprehensions, library usage, etc.)

Results will show Pareto-optimal solutions balancing energy consumption and execution time.

## Generated

This benchmark suite was auto-generated from `evoeval_difficult_entries.json`.
"""

    readme_path = base_path / "README.md"
    with open(readme_path, 'w') as f:
        f.write(readme_content)

    print(f"\n  ✓ Created master README.md")


if __name__ == "__main__":
    import sys

    json_file = "evoeval_difficult_entries.json"
    output_dir = "evoeval_benchmark"

    if len(sys.argv) > 1:
        json_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]

    extract_evoeval_problems(json_file, output_dir)
