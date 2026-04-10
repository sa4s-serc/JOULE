from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from joule.utils.terminal import TerminalReporter


def _console_buffer():
    import io

    stream = io.StringIO()
    return stream, Console(file=stream, color_system=None, force_terminal=False)


def test_reporter_quiet_suppresses_terminal_output():
    stream, console = _console_buffer()
    reporter = TerminalReporter(console, verbosity="quiet")

    reporter.info("setup", "hello")
    reporter.warn("warn", "be careful")

    assert stream.getvalue() == ""


def test_reporter_debug_and_trace_levels():
    stream, console = _console_buffer()
    reporter = TerminalReporter(console, verbosity="debug")

    reporter.debug("dbg", "debug visible")
    reporter.trace("trc", "trace hidden")

    output = stream.getvalue()
    assert "debug visible" in output
    assert "trace hidden" not in output


def test_reporter_writes_jsonl_log(tmp_path: Path):
    stream, console = _console_buffer()
    log_file = tmp_path / "events.jsonl"
    reporter = TerminalReporter(console, verbosity="normal", log_file=log_file)

    reporter.info("run", "start")
    reporter.verbose("run", "detail")

    lines = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["level"] == "event"
    assert lines[0]["stage"] == "run"
    assert lines[0]["message"] == "start"
    assert lines[0]["emitted"] is True
    assert lines[1]["message"] == "detail"
    assert lines[1]["emitted"] is False
