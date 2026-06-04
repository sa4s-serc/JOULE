#!/usr/bin/env python3
"""
Phase 3: Hotspot Selection from Discovery Results.

Selects a diverse, proportionally-sampled set of functions from discovery
output and writes a CSV of (absolute_file_path, function_name, ...) that
downstream shell scripts can consume without any further path translation.
"""

import json
import sys
import argparse
from pathlib import Path
from collections import defaultdict


def load_discovery(discovery_file: Path) -> list:
    with open(discovery_file) as f:
        return json.load(f)


def select_sample_targets(discovery_data: list, sample_size: int, repo_path: Path) -> list:
    """
    Select a diverse sample of functions for hotspot analysis.

    Strategy: proportional sampling across modules, ranked by score within
    each module. Filters out any entry whose file does not actually exist
    on disk so downstream scripts never receive phantom paths.
    """
    if not discovery_data:
        return []

    # Group by module
    modules: dict = defaultdict(list)
    for func in discovery_data:
        module = func.get("target", {}).get("module", "unknown")
        modules[module].append(func)

    total_funcs = sum(len(v) for v in modules.values())
    if total_funcs == 0:
        return []

    selected = []
    for module, funcs in modules.items():
        count = max(1, int(sample_size * len(funcs) / total_funcs))
        sorted_funcs = sorted(funcs, key=lambda x: x.get("score", 0), reverse=True)
        selected.extend(sorted_funcs[:count])

    # Sort overall by score, cap at sample_size
    selected = sorted(selected, key=lambda x: x.get("score", 0), reverse=True)[:sample_size]

    # Filter to entries whose files exist under the current repo root
    # BUG FIX: normalise stored absolute paths against the *current* repo_path
    # so we catch both old-machine paths and current-machine paths.
    valid = []
    skipped = 0
    for func in selected:
        target = func.get("target", {})
        stored_path = target.get("file_path", "")
        resolved = resolve_file_path(stored_path, repo_path)
        if resolved is None:
            skipped += 1
            continue
        # Attach the resolved absolute path so save_sample_targets has it
        func["_resolved_path"] = str(resolved)
        valid.append(func)

    if skipped:
        print(f"  Warning: {skipped} entries skipped (file not found under {repo_path})")

    return valid


def resolve_file_path(stored_path: str, repo_path: Path) -> Path | None:
    """
    Convert a stored file path (possibly from a different machine) to an
    absolute path valid on the current machine.

    Strategy (in order):
      1. Path is already absolute and exists → use it directly.
      2. Strip everything up to and including /repos/<repo_name>/ and
         treat the remainder as relative to repo_path.
      3. Treat stored_path as relative to repo_path directly.

    Returns None if the file cannot be found.
    """
    p = Path(stored_path)
    repo_name = repo_path.name

    # Case 1: absolute and exists
    if p.is_absolute() and p.exists():
        return p

    # Case 2: strip up to /repos/<repo_name>/ prefix
    # Works for any machine path like /any/prefix/repos/<repo_name>/src/...
    parts = p.parts
    for i, part in enumerate(parts):
        if part == repo_name and i > 0 and parts[i - 1] == "repos":
            rel = Path(*parts[i + 1:])
            candidate = repo_path / rel
            if candidate.exists():
                return candidate
            break

    # Case 3: try as relative path directly
    candidate = repo_path / stored_path
    if candidate.exists():
        return candidate

    # Case 4: try stripping any leading path components one at a time
    # (handles partial matches like "src/black/__init__.py")
    rel_parts = p.parts
    for start in range(len(rel_parts)):
        candidate = repo_path / Path(*rel_parts[start:])
        if candidate.exists():
            return candidate

    return None


def save_sample_targets(selected: list, output_file: Path) -> None:
    """
    Write CSV with fully-resolved absolute paths so no shell path
    reconstruction is needed in Phases 4/6/7.
    """
    with open(output_file, "w") as f:
        f.write("file_path,function_name,qualname,line_start,score\n")
        for func in selected:
            target = func.get("target", {})
            # Use the pre-resolved absolute path
            file_path = func.get("_resolved_path", target.get("file_path", ""))
            function_name = target.get("function_name", "")
            qualname = target.get("qualname", "")
            line_start = target.get("line_start", "")
            score = func.get("score", 0)
            # Escape any commas in qualname (e.g. "Class.method")
            qualname_safe = f'"{qualname}"' if "," in qualname else qualname
            f.write(f"{file_path},{function_name},{qualname_safe},{line_start},{score}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Select hotspot targets from discovery results")
    parser.add_argument("--repo", required=True, help="Repository name (black, networkx, sympy)")
    parser.add_argument("--sample-size", type=int, default=80)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument("--repos-dir", default=None)
    args = parser.parse_args()

    script_dir = Path(__file__).parent
    results_dir = Path(args.results_dir) if args.results_dir else script_dir.parent / "results"
    repos_dir = Path(args.repos_dir) if args.repos_dir else script_dir.parent / "repos"

    repo_path = repos_dir / args.repo
    discovery_file = results_dir / "discovery" / f"{args.repo}_discovery.json"
    output_file = results_dir / "hotspots" / f"{args.repo}_sample_targets.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not repo_path.exists():
        print(f"Error: repo directory not found: {repo_path}", file=sys.stderr)
        sys.exit(1)

    if not discovery_file.exists():
        print(f"Error: discovery file not found: {discovery_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading discovery from: {discovery_file}")
    discovery_data = load_discovery(discovery_file)
    print(f"  {len(discovery_data)} candidate functions found")

    print(f"Selecting up to {args.sample_size} functions (repo root: {repo_path})...")
    selected = select_sample_targets(discovery_data, args.sample_size, repo_path)
    print(f"  {len(selected)} functions selected after path validation")

    if not selected:
        print("ERROR: No valid functions selected — check that discovery paths match repo location.",
              file=sys.stderr)
        sys.exit(1)

    save_sample_targets(selected, output_file)
    print(f"Sample targets written to: {output_file}")

    print("\nTop 10 selected functions:")
    for i, func in enumerate(selected[:10], 1):
        target = func.get("target", {})
        print(f"  {i:2d}. {target.get('module','?')}::{target.get('function_name','?')} "
              f"(score={func.get('score', 0)}, path={func.get('_resolved_path','?')})")


if __name__ == "__main__":
    main()
