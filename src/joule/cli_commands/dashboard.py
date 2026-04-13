from __future__ import annotations

from pathlib import Path

from joule.dashboard.app import render_dashboard_html, serve_dashboard


def run_dashboard(path: Path, host: str, port: int | None, run_id: str | None, once: bool, verbose: bool, quiet: bool, *, bootstrap_fn) -> None:
    settings, db, reporter = bootstrap_fn(path, verbose=verbose, quiet=quiet)
    chosen_port = port or settings.dashboard_port
    if once:
        reporter.console.print(render_dashboard_html(db, selected_run_id=run_id))
        return
    reporter.info("dashboard", f"Serving dashboard at http://{host}:{chosen_port}")
    serve_dashboard(settings.db_path, host=host, port=chosen_port, selected_run_id=run_id)
