#!/usr/bin/env python3
"""
HEDGE Setup Script
==================

Automated setup and installation script for HEDGE.
"""

import shutil
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def check_dependencies():
    """Check if required system dependencies are available."""
    dependencies = ["git", "pip"]
    missing = []

    for dep in dependencies:
        if not shutil.which(dep):
            missing.append(dep)

    if missing:
        print(f"❌ Missing dependencies: {', '.join(missing)}")
        return False

    print("✅ System dependencies available")
    return True


def create_virtual_environment():
    """Create and activate virtual environment."""
    venv_path = Path(".venv")

    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True

    try:
        print("🔧 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", ".venv"], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to create virtual environment")
        return False


def install_requirements():
    """Install Python requirements."""
    try:
        print("📦 Installing requirements...")

        # Determine pip path based on OS
        if sys.platform == "win32":
            pip_path = Path(".venv/Scripts/pip")
        else:
            pip_path = Path(".venv/bin/pip")

        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], check=True)
        print("✅ Requirements installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install requirements")
        return False


def setup_environment_file():
    """Create .env file from template."""
    env_file = Path(".env")
    env_example = Path(".env.example")

    if env_file.exists():
        print("✅ .env file already exists")
        return True

    if env_example.exists():
        shutil.copy(env_example, env_file)
        print("✅ Created .env file from template")
        print("⚠️  Please edit .env file and add your API keys")
        return True
    else:
        # Create basic .env file
        with open(env_file, "w") as f:
            f.write("""# HEDGE Environment Configuration
# Add your API keys here

# OpenAI API Key (for advanced semantic optimizations)
# OPENAI_API_KEY=your_openai_api_key_here

# Google Gemini API Key (for advanced semantic optimizations)  
# GEMINI_API_KEY=your_gemini_api_key_here

# Optional: Custom model names
# OPENAI_MODEL=gpt-4
# GEMINI_MODEL=gemini-2.5-flash
""")
        print("✅ Created basic .env file")
        print("⚠️  Please edit .env file and add your API keys")
        return True


def make_executable():
    """Make CLI scripts executable."""
    scripts = ["hedge.py"]

    for script in scripts:
        script_path = Path(script)
        if script_path.exists():
            try:
                script_path.chmod(0o755)
                print(f"✅ Made {script} executable")
            except Exception as e:
                print(f"⚠️  Could not make {script} executable: {e}")

    return True


def run_tests():
    """Run basic tests to verify installation."""
    try:
        print("🧪 Running basic tests...")

        # Determine python path
        if sys.platform == "win32":
            python_path = Path(".venv/Scripts/python")
        else:
            python_path = Path(".venv/bin/python")

        # Run a simple import test
        result = subprocess.run(
            [
                str(python_path),
                "-c",
                'import src.domain.ir.schema; print("✅ Core modules import successfully")',
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(result.stdout.strip())
            return True
        else:
            print(f"❌ Import test failed: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "=" * 60)
    print("🎉 HEDGE Setup Complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Activate the virtual environment:")

    if sys.platform == "win32":
        print("   .venv\\Scripts\\activate")
    else:
        print("   source .venv/bin/activate")

    print("\n2. Edit .env file and add your API keys (optional for advanced features)")
    print("\n3. Try HEDGE:")
    print("   python hedge.py --help")
    print("   python hedge.py optimize examples/target_fib.py examples/test_target_fib.py")
    print("\n4. Create a new project:")
    print("   python hedge.py project init my_optimization_project")
    print("\nDocumentation: docs/README.md")
    print("Examples: examples/")


def main():
    """Main setup function."""
    print("🚀 HEDGE Setup Script")
    print("=" * 40)

    # Check prerequisites
    if not check_python_version():
        return 1

    if not check_dependencies():
        return 1

    # Setup steps
    steps = [
        ("Creating virtual environment", create_virtual_environment),
        ("Installing requirements", install_requirements),
        ("Setting up environment file", setup_environment_file),
        ("Making scripts executable", make_executable),
        ("Running basic tests", run_tests),
    ]

    for step_name, step_func in steps:
        print(f"\n🔧 {step_name}...")
        if not step_func():
            print(f"❌ Setup failed at: {step_name}")
            return 1

    print_next_steps()
    return 0


if __name__ == "__main__":
    sys.exit(main())
