from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from joule.config import load_settings
from joule.cli_helpers.output import resolve_output_mode
from joule.transformers.registry import OperatorRegistry
from joule.utils.analysis import json_pretty


def _transformation_catalog(settings) -> list[dict[str, Any]]:
    configured_model = settings.llm_model.strip()
    registry = OperatorRegistry(llm_model=configured_model or "unconfigured", include_llm=True)
    llm_enabled = bool(configured_model)
    records: list[dict[str, Any]] = []
    for operator in registry.operators:
        llm_like = operator.family != "deterministic"
        records.append(
            {
                "name": operator.name,
                "family": operator.family,
                "tier": operator.tier_name(),
                "descriptor": operator.tier_description(),
                "escape_only": operator.escape_only,
                "precheck_pattern_nodes": [item.__name__ for item in operator.precheck_node_types],
                "active_by_default": llm_enabled if llm_like else True,
            }
        )
    for operator in registry.escape_operators:
        records.append(
            {
                "name": operator.name,
                "family": operator.family,
                "tier": operator.tier_name(),
                "descriptor": operator.tier_description(),
                "escape_only": operator.escape_only,
                "precheck_pattern_nodes": [item.__name__ for item in operator.precheck_node_types],
                "active_by_default": llm_enabled,
            }
        )
    records.sort(key=lambda item: (item["family"], item["tier"], item["name"]))
    return records


def run_transformations(path: Path, output: str, *, console) -> None:
    from rich.table import Table

    output_mode = resolve_output_mode(output)
    settings = load_settings(path)
    payload = _transformation_catalog(settings)
    if output_mode == "json":
        from typer import echo

        echo(json_pretty({"transformations": payload}))
        return
    family_counts = Counter(item["family"] for item in payload)
    tier_counts = Counter(item["tier"] for item in payload)
    table = Table(title="Registered Transformations")
    table.add_column("Name", no_wrap=True)
    table.add_column("Family", no_wrap=True)
    table.add_column("Tier", no_wrap=True)
    table.add_column("Descriptor", no_wrap=True)
    table.add_column("Active", no_wrap=True)
    table.add_column("Escape", no_wrap=True)
    table.add_column("Precheck Pattern", overflow="fold")
    for item in payload:
        table.add_row(
            item["name"],
            item["family"],
            item["tier"],
            item["descriptor"],
            "yes" if item["active_by_default"] else "no",
            "yes" if item["escape_only"] else "no",
            ", ".join(item["precheck_pattern_nodes"]) or "none",
        )
    console.print(table)
    console.print(
        "Summary: "
        + f"total={len(payload)} "
        + " ".join(f"{family}={count}" for family, count in sorted(family_counts.items()))
        + " "
        + " ".join(f"tier_{tier}={count}" for tier, count in sorted(tier_counts.items()))
    )
