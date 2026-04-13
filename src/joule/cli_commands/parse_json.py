from __future__ import annotations

from pathlib import Path

from joule.cli_helpers.output import load_json_input
from joule.utils.analysis import human_json_payload_summary


def run_parse_json(file: Path | None, *, console) -> None:
    payload = load_json_input(file)
    console.print(human_json_payload_summary(payload))
