#!/usr/bin/env python3
"""
Verification script for HEDGE codebase cleanup.

This script verifies that all imports are correct and the codebase
is ready to run after the cleanup.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all critical imports work."""
    print("Testing imports...")
    
    tests = []
    
    # Test config imports
    try:
        from src.utils.config_manager import (
            load_config, 
            get_llm_config, 
            GLOBAL_CONFIG,
            get_default_config,
            save_config,
            get_config_setting
        )
        tests.append(("✓", "Config manager imports"))
    except Exception as e:
        tests.append(("✗", f"Config manager imports: {e}"))
    
    # Test logging imports
    try:
        from src.utils.logging_config import (
            setup_logging,
            ExperimentLogger,
            silence_noisy_libraries
        )
        tests.append(("✓", "Logging config imports"))
    except Exception as e:
        tests.append(("✗", f"Logging config imports: {e}"))
    
    # Test mutation factory imports
    try:
        from src.utils.mutation_factory import (
            create_mutation_result,
            MutationResultFactory
        )
        tests.append(("✓", "Mutation factory imports"))
    except Exception as e:
        tests.append(("✗", f"Mutation factory imports: {e}"))
    
    # Test base mutator imports
    try:
        from src.application.mutators.base import (
            LayeredMutator,
            MutationLayer,
            MutationResult,
            LazyIRWrapper
        )
        tests.append(("✓", "Base mutator imports"))
    except Exception as e:
        tests.append(("✗", f"Base mutator imports: {e}"))
    
    # Test CLI imports
    try:
        from cli.commands.optimize import optimize_cmd
        from cli.commands.config import config_cmd
        tests.append(("✓", "CLI command imports"))
    except Exception as e:
        tests.append(("✗", f"CLI command imports: {e}"))
    
    # Test API imports
    try:
        from api.main import app
        from api.manager import OptimizationTaskManager
        from api.utils import sanitize_for_json
        tests.append(("✓", "API imports"))
    except Exception as e:
        tests.append(("✗", f"API imports: {e}"))
    
    # Print results
    print("\n" + "="*60)
    print("IMPORT VERIFICATION RESULTS")
    print("="*60)
    for status, message in tests:
        print(f"{status} {message}")
    
    # Check if all passed
    failed = [t for t in tests if t[0] == "✗"]
    if failed:
        print(f"\n❌ {len(failed)} test(s) failed")
        return False
    else:
        print(f"\n✅ All {len(tests)} import tests passed!")
        return True


def verify_deleted_files():
    """Verify that deleted files are actually gone."""
    print("\n" + "="*60)
    print("DELETED FILES VERIFICATION")
    print("="*60)
    
    deleted_files = [
        "src/domain/ir/schema_backup.py",
        "src/utils/config.py",
        "src/utils/logging.py"
    ]
    
    all_deleted = True
    for filepath in deleted_files:
        path = Path(filepath)
        if path.exists():
            print(f"✗ {filepath} still exists (should be deleted)")
            all_deleted = False
        else:
            print(f"✓ {filepath} deleted")
    
    if all_deleted:
        print(f"\n✅ All {len(deleted_files)} files successfully deleted")
    else:
        print("\n❌ Some files were not deleted")
    
    return all_deleted


def verify_file_structure():
    """Verify that the file structure is correct."""
    print("\n" + "="*60)
    print("FILE STRUCTURE VERIFICATION")
    print("="*60)
    
    required_files = [
        "src/utils/config_manager.py",
        "src/utils/logging_config.py",
        "src/utils/mutation_factory.py",
        "src/application/mutators/base.py",
        "src/domain/ir/schema.py",
        "cli/commands/optimize.py",
        "cli/commands/config.py",
        "api/main.py",
        "api/manager.py",
        "api/utils.py"
    ]
    
    all_exist = True
    for filepath in required_files:
        path = Path(filepath)
        if not path.exists():
            print(f"✗ {filepath} missing")
            all_exist = False
        else:
            print(f"✓ {filepath} exists")
    
    if all_exist:
        print(f"\n✅ All {len(required_files)} required files exist")
    else:
        print("\n❌ Some required files are missing")
    
    return all_exist


def test_functionality():
    """Test basic functionality."""
    print("\n" + "="*60)
    print("FUNCTIONALITY VERIFICATION")
    print("="*60)
    
    tests = []
    
    # Test config loading
    try:
        from src.utils.config_manager import load_config
        config = load_config()
        assert isinstance(config, dict)
        assert "optimization" in config
        tests.append(("✓", "Config loading works"))
    except Exception as e:
        tests.append(("✗", f"Config loading: {e}"))
    
    # Test logging setup
    try:
        from src.utils.logging_config import setup_logging
        import logging
        setup_logging(level="INFO", log_to_console=False)
        assert logging.root.level == logging.INFO
        tests.append(("✓", "Logging setup works"))
    except Exception as e:
        tests.append(("✗", f"Logging setup: {e}"))
    
    # Test mutation result creation
    try:
        from src.utils.mutation_factory import create_mutation_result
        from src.application.mutators.base import MutationLayer
        from src.domain.ir.schema import Module, Block
        
        test_ir = Module(body=Block(statements=[]))
        result = create_mutation_result(
            ir=test_ir,
            strategy_name="test_strategy",
            layer=MutationLayer.MICRO,
            mutator_name="TestMutator"
        )
        assert result.strategy_name == "test_strategy"
        tests.append(("✓", "Mutation result creation works"))
    except Exception as e:
        tests.append(("✗", f"Mutation result creation: {e}"))
    
    # Print results
    for status, message in tests:
        print(f"{status} {message}")
    
    failed = [t for t in tests if t[0] == "✗"]
    if failed:
        print(f"\n❌ {len(failed)} functionality test(s) failed")
        return False
    else:
        print(f"\n✅ All {len(tests)} functionality tests passed!")
        return True


def main():
    """Run all verification tests."""
    print("\n" + "="*60)
    print("HEDGE CODEBASE CLEANUP VERIFICATION")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Deleted Files", verify_deleted_files()))
    results.append(("File Structure", verify_file_structure()))
    results.append(("Imports", test_imports()))
    results.append(("Functionality", test_functionality()))
    
    # Final summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n" + "="*60)
        print("🎉 ALL VERIFICATIONS PASSED!")
        print("="*60)
        print("\nThe codebase cleanup is complete and verified.")
        print("The code is ready to run.")
        return 0
    else:
        print("\n" + "="*60)
        print("⚠️  SOME VERIFICATIONS FAILED")
        print("="*60)
        print("\nPlease review the failures above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
