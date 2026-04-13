from __future__ import annotations

from pathlib import Path

from joule.cli_helpers.output import resolve_output_mode
from joule.config import load_settings
from joule.utils.analysis import json_pretty


def run_config_show(path: Path, output: str, *, console) -> None:
    from rich.table import Table
    from typer import BadParameter, echo

    output_mode = resolve_output_mode(output)
    try:
        settings = load_settings(path)
    except ValueError as exc:
        raise BadParameter(str(exc)) from exc
    record = settings.to_record()
    payload = {
        "project_root": str(settings.project_root),
        "resolved": record,
    }
    if output_mode == "json":
        echo(json_pretty(payload))
        return

    table = Table(title="Resolved JOULE Configuration")
    table.add_column("Key", no_wrap=True)
    table.add_column("Value", overflow="fold")
    for key in sorted(record):
        value = record[key]
        if isinstance(value, (dict, list)):
            rendered = json_pretty(value)
        else:
            rendered = str(value)
        table.add_row(key, rendered)
    console.print(table)
