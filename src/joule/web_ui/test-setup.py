#!/usr/bin/env python3
"""
Test script to verify JOULE Web UI setup.
This script checks that all necessary components are in place and can be imported.
"""

import sys
from pathlib import Path

def test_backend_setup():
    """Test that backend components can be imported."""
    print("Testing backend setup...")
    
    # Add backend to path
    backend_dir = Path(__file__).parent / "backend"
    if backend_dir.exists():
        sys.path.insert(0, str(backend_dir))
    
    try:
        import main
        print("✓ Backend main module can be imported")
        
        # Check FastAPI app
        from fastapi import FastAPI
        app = main.app
        assert isinstance(app, FastAPI), "App should be FastAPI instance"
        print("✓ FastAPI app created successfully")
        
        return True
    except ImportError as e:
        print(f"✗ Backend import failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Backend setup failed: {e}")
        return False

def test_frontend_structure():
    """Test that frontend structure exists."""
    print("\nTesting frontend structure...")
    
    frontend_dir = Path(__file__).parent / "frontend"
    
    required_files = [
        "package.json",
        "vite.config.ts",
        "tsconfig.json",
        "tailwind.config.js",
        "index.html",
        "src/main.tsx",
        "src/App.tsx",
    ]
    
    required_dirs = [
        "src/components",
        "src/pages",
        "src/hooks",
        "src/stores",
        "src/types",
        "src/utils",
    ]
    
    all_good = True
    
    for file_path in required_files:
        full_path = frontend_dir / file_path
        if full_path.exists():
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} missing")
            all_good = False
    
    for dir_path in required_dirs:
        full_path = frontend_dir / dir_path
        if full_path.exists() and full_path.is_dir():
            print(f"✓ {dir_path}/")
        else:
            print(f"✗ {dir_path}/ missing")
            all_good = False
    
    return all_good

def test_cli_integration():
    """Test that CLI command is available."""
    print("\nTesting CLI integration...")
    
    try:
        # Try to import the UI command
        from joule.cli_commands.ui import run_ui
        print("✓ UI command can be imported")
        
        # Check if it's added to CLI - use a simpler approach
        import joule.cli
        import inspect
        
        # Get all functions in the CLI module that have typer.command decorator
        for name, obj in inspect.getmembers(joule.cli):
            if inspect.isfunction(obj) and hasattr(obj, '__name__'):
                if name == 'ui':
                    print("✓ UI command found in CLI module")
                    return True
        
        print("✗ UI command function not found in CLI module")
        return False
            
    except ImportError as e:
        print(f"✗ CLI integration failed: {e}")
        return False

def test_dependencies():
    """Test that required dependencies are available."""
    print("\nTesting dependencies...")
    
    backend_deps = [
        "fastapi",
        "uvicorn", 
        "websockets",
        "pydantic",
    ]
    
    missing = []
    
    for dep in backend_deps:
        try:
            __import__(dep)
            print(f"✓ {dep}")
        except ImportError:
            print(f"✗ {dep} missing")
            missing.append(dep)
    
    return len(missing) == 0

def main():
    """Run all tests."""
    print("JOULE Web UI Setup Test")
    print("=" * 30)
    
    tests = [
        test_backend_setup,
        test_frontend_structure,
        test_cli_integration,
        test_dependencies,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            results.append(False)
    
    print("\n" + "=" * 30)
    print("Test Summary:")
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 All {total} tests passed!")
        print("\nThe JOULE Web UI is ready to use!")
        print("\nTo start the web UI:")
        print("  joule ui .")
        print("\nOr use the development script:")
        print("  ./src/joule/web_ui/start-dev.sh")
        return 0
    else:
        print(f"❌ {total - passed} out of {total} tests failed")
        print("\nPlease fix the issues above before using the web UI.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
