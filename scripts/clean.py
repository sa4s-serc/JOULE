#!/usr/bin/env python3
"""
HEDGE Cleanup Script
====================

Clean up temporary files, caches, and experiment results.
"""

import argparse
import shutil
from pathlib import Path


def clean_pycache(root_dir="."):
    """Remove __pycache__ directories."""
    removed = 0
    for pycache_dir in Path(root_dir).rglob("__pycache__"):
        try:
            shutil.rmtree(pycache_dir)
            print(f"✅ Removed {pycache_dir}")
            removed += 1
        except Exception as e:
            print(f"❌ Failed to remove {pycache_dir}: {e}")
    return removed


def clean_pyc_files(root_dir="."):
    """Remove .pyc files."""
    removed = 0
    for pyc_file in Path(root_dir).rglob("*.pyc"):
        try:
            pyc_file.unlink()
            print(f"✅ Removed {pyc_file}")
            removed += 1
        except Exception as e:
            print(f"❌ Failed to remove {pyc_file}: {e}")
    return removed


def clean_experiments(root_dir=".", keep_recent=0):
    """Remove experiment directories."""
    exp_dir = Path(root_dir) / "experiments"
    if not exp_dir.exists():
        return 0

    # Get all experiment directories sorted by modification time
    exp_dirs = [d for d in exp_dir.iterdir() if d.is_dir()]
    exp_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    # Keep the most recent ones
    to_remove = exp_dirs[keep_recent:] if keep_recent > 0 else exp_dirs

    removed = 0
    for exp_path in to_remove:
        try:
            shutil.rmtree(exp_path)
            print(f"✅ Removed experiment {exp_path.name}")
            removed += 1
        except Exception as e:
            print(f"❌ Failed to remove {exp_path}: {e}")

    return removed


def clean_temp_files(root_dir="."):
    """Remove temporary files."""
    patterns = ["*.tmp", "*_optimized.py", "*.log", ".pytest_cache", "*.egg-info"]

    removed = 0
    root_path = Path(root_dir)

    for pattern in patterns:
        for temp_file in root_path.rglob(pattern):
            try:
                if temp_file.is_dir():
                    shutil.rmtree(temp_file)
                else:
                    temp_file.unlink()
                print(f"✅ Removed {temp_file}")
                removed += 1
            except Exception as e:
                print(f"❌ Failed to remove {temp_file}: {e}")

    return removed


def clean_benchmarks(root_dir="."):
    """Remove benchmark results."""
    benchmark_dir = Path(root_dir) / "benchmarks"
    if not benchmark_dir.exists():
        return 0

    removed = 0
    for item in benchmark_dir.iterdir():
        if item.is_dir() and item.name.startswith("run_"):
            try:
                shutil.rmtree(item)
                print(f"✅ Removed benchmark {item.name}")
                removed += 1
            except Exception as e:
                print(f"❌ Failed to remove {item}: {e}")

    return removed


def main():
    parser = argparse.ArgumentParser(description="Clean HEDGE temporary files and caches")
    parser.add_argument("--cache", action="store_true", help="Clean Python cache files")
    parser.add_argument("--experiments", action="store_true", help="Clean experiment results")
    parser.add_argument("--keep-recent", type=int, default=0, help="Keep N most recent experiments")
    parser.add_argument("--temp", action="store_true", help="Clean temporary files")
    parser.add_argument("--benchmarks", action="store_true", help="Clean benchmark results")
    parser.add_argument("--all", action="store_true", help="Clean everything")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without actually cleaning",
    )

    args = parser.parse_args()

    if not any([args.cache, args.experiments, args.temp, args.benchmarks, args.all]):
        print("No cleaning options specified. Use --help for options.")
        return 1

    print("🧹 HEDGE Cleanup Script")
    print("=" * 40)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be actually removed")
        print()

    total_removed = 0

    if args.all or args.cache:
        print("🗑️  Cleaning Python cache files...")
        removed = clean_pycache()
        removed += clean_pyc_files()
        print(f"   Removed {removed} cache items")
        total_removed += removed

    if args.all or args.experiments:
        print("🗑️  Cleaning experiment results...")
        removed = clean_experiments(keep_recent=args.keep_recent)
        print(f"   Removed {removed} experiments")
        total_removed += removed

    if args.all or args.temp:
        print("🗑️  Cleaning temporary files...")
        removed = clean_temp_files()
        print(f"   Removed {removed} temporary files")
        total_removed += removed

    if args.all or args.benchmarks:
        print("🗑️  Cleaning benchmark results...")
        removed = clean_benchmarks()
        print(f"   Removed {removed} benchmark results")
        total_removed += removed

    print(f"\n✅ Cleanup complete! Removed {total_removed} items total.")

    return 0


if __name__ == "__main__":
    exit(main())
