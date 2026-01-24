"""
Integration tests for IR snapshot saving during evolution.

Tests the end-to-end functionality of the --save-ir flag.
"""
import sys
import json
import tempfile
from pathlib import Path

from src.application.engine.evolution import EvolutionaryEngine, EngineConfig
from src.application.mutators.syntactic_layer import PythonicIdiomOptimizer
from src.infrastructure.execution.runner import GreenGymRunner


def test_evolution_saves_ir_snapshots():
    """Test that EvolutionaryEngine saves IR snapshots when enabled."""
    code = """
def process(data):
    res = []
    for x in data:
        res.append(x * 2)
    return res
"""
    
    test_code = """
def test_process():
    assert candidate.process([1, 2]) == [2, 4]
"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        experiment_dir = Path(tmpdir)
        
        # Create engine with save_ir_snapshots enabled
        config = EngineConfig(
            generations=2,
            population_size=1,
            save_ir_snapshots=True
        )
        engine = EvolutionaryEngine(
            mutators=[PythonicIdiomOptimizer()],
            runner=GreenGymRunner(timeout_seconds=10),
            config=config,
            experiment_dir=experiment_dir
        )
        
        # Run optimization
        solutions = engine.optimize(code, test_code)
        
        # Check that ir_snapshots directory was created
        snapshots_dir = experiment_dir / "ir_snapshots"
        assert snapshots_dir.exists(), "ir_snapshots directory not created"
        
        # Check that snapshot files exist
        snapshot_files = list(snapshots_dir.glob("*.json"))
        # We need at least one mutation to be successful and better/non-dominated to save a snapshot
        assert len(snapshot_files) > 0, f"No IR snapshot files created in {snapshots_dir}"
        
        # Check each snapshot file
        for snapshot_file in snapshot_files:
            # File should not be empty
            assert snapshot_file.stat().st_size > 10, \
                f"{snapshot_file.name} is too small"
            
            # File should contain valid JSON
            with open(snapshot_file) as f:
                data = json.load(f)
            
            # Should have basic IR structure (Module)
            assert data.get('__type__') == 'Module' or 'body' in data


def test_evolution_without_save_ir_creates_no_snapshots():
    """Test that EvolutionaryEngine doesn't save snapshots when disabled."""
    code = """
def simple_add(a, b):
    return a + b
"""
    
    test_code = """
def test_add():
    assert candidate.simple_add(1, 2) == 3
"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        experiment_dir = Path(tmpdir)
        
        # Create engine with save_ir_snapshots disabled
        config = EngineConfig(
            generations=1,
            population_size=1,
            save_ir_snapshots=False
        )
        engine = EvolutionaryEngine(
            mutators=[PythonicIdiomOptimizer()],
            runner=GreenGymRunner(timeout_seconds=10),
            config=config,
            experiment_dir=experiment_dir
        )
        
        # Run optimization
        solutions = engine.optimize(code, test_code)
        
        # Check that ir_snapshots directory was NOT created or is empty
        snapshots_dir = experiment_dir / "ir_snapshots"
        if snapshots_dir.exists():
            snapshot_files = list(snapshots_dir.glob("*.json"))
            assert len(snapshot_files) == 0, \
                "IR snapshots created when save_ir_snapshots=False"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
