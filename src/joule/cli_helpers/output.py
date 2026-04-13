from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Literal

import typer


def resolve_output_mode(output: str) -> Literal["human", "json"]:
    normalized = output.strip().lower()
    if normalized in {"human", "json"}:
        return normalized  # type: ignore[return-value]
    if normalized == "parsed":
        return "human"
    raise typer.BadParameter(f"--output must be either 'human' or 'json', got {output!r}")


def load_json_input(file: Path | None) -> Any:
    raw = file.read_text(encoding="utf-8") if file else sys.stdin.read()
    if not raw.strip():
        raise typer.BadParameter("No JSON payload provided. Pass --file or pipe JSON to stdin.")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON payload: {exc.msg} at line {exc.lineno} column {exc.colno}")
