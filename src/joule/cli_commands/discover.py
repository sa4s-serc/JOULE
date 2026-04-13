from __future__ import annotations

from pathlib import Path

from joule.cli_helpers.output import resolve_output_mode
from joule.config import load_settings
from joule.discovery.resolver import discover_targets
from joule.utils.analysis import human_discover_summary


def run_discover(path: Path, output: str, verbose: bool, quiet: bool, *, console, bootstrap_fn) -> None:
    from typer import echo

    settings, _db, reporter = bootstrap_fn(path, verbose=verbose, quiet=quiet)
    reporter.verbose("discovery", f"Scanning {settings.project_root}")
    results = discover_targets(settings, path)
    payload = [
        {
            "target": result.target.to_record(),
            "score": result.score,
            "reasons": result.reasons,
            "workloads": [workload.to_record() for workload in result.workloads],
            "workload_provenance": [
                {
                    "identifier": workload.identifier,
                    "provenance": workload.metadata.get("provenance", "unknown"),
                    "resolution_strategy": workload.metadata.get("resolution_strategy", "unknown"),
                    "alignment_score": workload.metadata.get("alignment_score"),
                }
                for workload in result.workloads
            ],
        }
        for result in results
    ]
    output_mode = resolve_output_mode(output)
    if output_mode == "json":
        import json

        echo(json.dumps(payload, indent=2))
    else:
        console.print(human_discover_summary(payload))
