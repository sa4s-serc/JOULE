#!/usr/bin/env python3
"""
HEDGE Codebase Cleanup Script

Removes cache files, temporary files, and ensures the codebase is clean
after the major refactoring and improvements.
"""
import os
import shutil
import sys
from pathlib import Path

def cleanup_pycache():
    """Remove all __pycache__ directories."""
    print("Cleaning up __pycache__ directories...")
    
    root_dir = Path(__file__).parent.parent
    pycache_dirs = list(root_dir.rglob("__pycache__"))
    
    for pycache_dir in pycache_dirs:
        try:
            shutil.rmtree(pycache_dir)
            print(f"  Removed: {pycache_dir}")
        except Exception as e:
            print(f"  Failed to remove {pycache_dir}: {e}")
    
    print(f"Cleaned up {len(pycache_dirs)} __pycache__ directories")

def cleanup_pyc_files():
    """Remove all .pyc files."""
    print("Cleaning up .pyc files...")
    
    root_dir = Path(__file__).parent.parent
    pyc_files = list(root_dir.rglob("*.pyc"))
    
    for pyc_file in pyc_files:
        try:
            pyc_file.unlink()
            print(f"  Removed: {pyc_file}")
        except Exception as e:
            print(f"  Failed to remove {pyc_file}: {e}")
    
    print(f"Cleaned up {len(pyc_files)} .pyc files")

def cleanup_temp_files():
    """Remove temporary files and directories."""
    print("Cleaning up temporary files...")
    
    root_dir = Path(__file__).parent.parent
    temp_patterns = [
        "*.tmp",
        "*.temp", 
        ".DS_Store",
        "Thumbs.db",
        "*.log",
        ".pytest_cache",
        ".coverage",
        "htmlcov",
        "*.egg-info"
    ]
    
    removed_count = 0
    for pattern in temp_patterns:
        for temp_file in root_dir.rglob(pattern):
            try:
                if temp_file.is_dir():
                    shutil.rmtree(temp_file)
                else:
                    temp_file.unlink()
                print(f"  Removed: {temp_file}")
                removed_count += 1
            except Exception as e:
                print(f"  Failed to remove {temp_file}: {e}")
    
    print(f"Cleaned up {removed_count} temporary files")

def verify_imports():
    """Verify that key imports work after cleanup."""
    print("Verifying imports...")
    
    try:
        # Add project root to path for imports
        import sys
        from pathlib import Path
        project_root = Path(__file__).parent.parent
        sys.path.insert(0, str(project_root))
        
        # Test core imports
        from src.application.mutators import MutationOrchestrator, get_registry
        from src.utils.comment_sanitizer import sanitize_code_for_llm
        from src.domain.ir.schema import IRNode, Module
        
        print("  ✓ Core imports working")
        
        # Test registry initialization
        registry = get_registry()
        print(f"  ✓ Registry initialized with {len(registry.list_all_mutators())} mutators")
        
        # Test comment sanitization
        result = sanitize_code_for_llm("# API_KEY = 'test'\nprint('hello')")
        print(f"  ✓ Comment sanitization working (safe: {result.is_safe})")
        
        print("All imports verified successfully!")
        return True
        
    except Exception as e:
        print(f"  ✗ Import verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main cleanup function."""
    print("HEDGE Codebase Cleanup")
    print("=" * 50)
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Perform cleanup
    cleanup_pycache()
    print()
    
    cleanup_pyc_files()
    print()
    
    cleanup_temp_files()
    print()
    
    # Verify everything works
    if verify_imports():
        print("\n✅ Codebase cleanup completed successfully!")
        print("\nNext steps:")
        print("1. Run tests: python -m pytest tests/ -v")
        print("2. Try examples: python hedge.py optimize examples/target_fib.py examples/test_target_fib.py")
        print("3. Check documentation: see MIGRATION_GUIDE.md")
        return 0
    else:
        print("\n❌ Cleanup completed but imports failed!")
        print("Please check the error messages above and fix any issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())