from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from joule.utils.db import JouleDB
from joule.utils.analysis import cross_run_trends
from joule.utils.reporting import workload_provenance_records


def render_dashboard_snapshot(db: JouleDB) -> str:
    lines = ["JOULE Dashboard Snapshot", ""]
    runs = db.list_runs()
    if not runs:
        return "JOULE Dashboard Snapshot\n\nNo runs recorded yet."
    for run in runs:
        lines.append(f"{run['run_id']} [{run['run_type']}] {run['status']} @ {run['created_at']}")
    return "\n".join(lines)


def render_dashboard_html(db: JouleDB, selected_run_id: str | None = None) -> str:
    runs = db.list_runs()
    latest = selected_run_id or (runs[0]["run_id"] if runs else None)
    current = _run_section(db, latest) if latest else "<p>No runs recorded yet.</p>"
    trends = _trends_section(runs)
    rows = "".join(
        f"<tr><td>{escape(run['run_id'])}</td><td>{escape(run['run_type'])}</td>"
        f"<td>{escape(run['status'])}</td><td>{escape(run['created_at'])}</td></tr>"
        for run in runs
    )
    if not rows:
        rows = "<tr><td colspan='4'>No runs</td></tr>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="2">
  <title>JOULE Dashboard</title>
  <style>
    :root {{
      --bg: #f8f5ef;
      --panel: #fffdf8;
      --ink: #1e2a2f;
      --muted: #5d6a70;
      --accent: #186a7b;
      --border: #d9d2c3;
      --ok: #2b7a0b;
      --bad: #8d1c13;
    }}
    body {{ font-family: Georgia, "Iowan Old Style", serif; background: linear-gradient(180deg, #f8f5ef 0%, #efe7da 100%); color: var(--ink); margin: 0; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 48px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .grid {{ display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
    .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 18px; padding: 18px; box-shadow: 0 10px 24px rgba(30, 42, 47, 0.06); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    code, pre {{ font-family: "IBM Plex Mono", "SFMono-Regular", monospace; font-size: 12px; }}
    pre {{ white-space: pre-wrap; background: #f4efe6; padding: 12px; border-radius: 12px; overflow: auto; }}
    .ok {{ color: var(--ok); }}
    .bad {{ color: var(--bad); }}
    .muted {{ color: var(--muted); }}
  </style>
</head>
<body>
  <main>
    <h1>JOULE Dashboard</h1>
    <p class="muted">Auto-refreshing view of recent runs, candidates, measurements, and adaptive calibration.</p>
    <div class="grid">
      <section class="panel">
        <h2>Runs</h2>
        <table>
          <thead><tr><th>Run</th><th>Type</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </section>
      <section class="panel">
        <h2>Latest Run</h2>
        {current}
      </section>
      <section class="panel">
        <h2>Trends</h2>
        {trends}
      </section>
    </div>
  </main>
</body>
</html>"""


def serve_dashboard(db_path: Path, host: str = "127.0.0.1", port: int = 8501, selected_run_id: str | None = None) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            db = JouleDB(db_path)
            payload = render_dashboard_html(db, selected_run_id=selected_run_id).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):  # noqa: A003
            del format, args

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _run_section(db: JouleDB, run_id: str | None) -> str:
    if not run_id:
        return "<p>No run selected.</p>"
    run = db.get_run(run_id)
    candidates = db.get_candidates(run_id)
    measurements = db.get_measurements(run_id)
    artifacts = db.get_artifacts(run_id)
    audits = db.get_apply_audits(run_id)
    search_events = db.get_search_events(run_id)
    hotspots = db.get_hotspot_profiles(run_id)
    latest_measurement = measurements[-1]["aggregate"] if measurements else None
    candidate_rows = "".join(
        f"<tr><td>{escape(item['candidate_id'])}</td><td>{escape(item['operator_name'])}</td>"
        f"<td>{escape(item['status'])}</td><td>{item['score']:.6f}</td>"
        f"<td>{escape(str(item['metadata'].get('stage', '-')))}</td>"
        f"<td>{escape(str(item['metadata'].get('rejected', '-')))}</td>"
        f"<td>{escape(_candidate_detail(item['metadata']))}</td></tr>"
        for item in candidates
    )
    if not candidate_rows:
        candidate_rows = "<tr><td colspan='7'>No candidates yet</td></tr>"
    artifact_items = "".join(
        f"<li><strong>{escape(item['name'])}</strong> <span class='muted'>({escape(item['kind'])})</span></li>"
        for item in artifacts
    ) or "<li>No artifacts yet</li>"
    audit_items = "".join(
        f"<li>{escape(item['candidate_id'])} at {escape(item['applied_at'])}</li>"
        for item in audits
    ) or "<li>No apply events yet</li>"
    calibration_lines = []
    for measurement in measurements:
        for calibration in measurement.get("metadata", {}).get("calibration", []):
            calibration_lines.append(
                f"{calibration['workload_id']}: inner={calibration['inner_repetitions']} "
                f"mode={calibration['adaptive_mode']} target={calibration['adaptive_target_window_s']:.3f}s"
            )
    calibration_html = "<br>".join(escape(line) for line in calibration_lines) or "No calibration data yet"
    provenance_items = "".join(
        (
            f"<li><strong>{escape(item['identifier'])}</strong> "
            f"<span class='muted'>{escape(item['provenance'])}/{escape(item['resolution_strategy'])}</span></li>"
        )
        for item in workload_provenance_records(run.bundle)
    ) or "<li>No workload provenance recorded</li>"
    search_summary = _search_summary(search_events)
    hotspot_html = _hotspot_section(hotspots)
    aggregate_html = (
        "<p><strong>Aggregate:</strong> "
        f"latency={latest_measurement['mean_wall_time_s']:.6f}s "
        f"energy={latest_measurement['mean_energy_j']:.6f}J "
        f"memory={latest_measurement['mean_peak_memory_bytes'] / (1024 * 1024):.3f}MiB</p>"
        if latest_measurement
        else "<p>No measurements yet.</p>"
    )
    return f"""
    <p><strong>{escape(run.target.qualname)}</strong> <span class='muted'>{escape(str(run.target.file_path))}</span></p>
    <p>Status: <strong>{escape(run.status)}</strong></p>
    {aggregate_html}
    <p><strong>Search funnel</strong><br>{search_summary}</p>
    <h3>Workload Provenance</h3>
    <ul>{provenance_items}</ul>
    <p><strong>Adaptive Calibration</strong><br>{calibration_html}</p>
    <h3>Hotspots</h3>
    {hotspot_html}
    <h3>Candidates</h3>
    <table>
      <thead><tr><th>ID</th><th>Operator</th><th>Status</th><th>Score</th><th>Stage</th><th>Reason</th><th>Details</th></tr></thead>
      <tbody>{candidate_rows}</tbody>
    </table>
    <h3>Artifacts</h3>
    <ul>{artifact_items}</ul>
    <h3>Apply Audits</h3>
    <ul>{audit_items}</ul>
    """


def _trends_section(runs: list[dict]) -> str:
    trends = cross_run_trends(runs)
    targets = trends.get("targets", {})
    if not targets:
        return "<p>No trend data yet.</p>"
    rows = []
    for target, items in targets.items():
        latest = items[0]
        rows.append(
            f"<tr><td>{escape(target)}</td><td>{len(items)}</td>"
            f"<td>{latest['energy_j']:.6f}J</td><td>{latest['latency_s']:.6f}s</td>"
            f"<td>{latest['memory_mb']:.3f}MiB</td></tr>"
        )
    return (
        "<table><thead><tr><th>Target</th><th>Runs</th><th>Energy</th><th>Latency</th><th>Memory</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def _search_summary(events: list[dict]) -> str:
    if not events:
        return "No search events"
    counts: dict[str, int] = {}
    for event in events:
        counts[event["event_type"]] = counts.get(event["event_type"], 0) + 1
    ordered = [f"{key}={counts[key]}" for key in sorted(counts)]
    return escape(" ".join(ordered))


def _hotspot_section(records: list[dict]) -> str:
    summary = next((item["payload"] for item in records if item["kind"] == "summary"), None)
    if not summary:
        return "<p>No hotspot analysis recorded.</p>"
    top_functions = summary.get("top_functions", [])
    ownership = summary.get("ownership", [])
    fn_rows = "".join(
        f"<tr><td>{escape(Path(item['file']).name)}</td><td>{item['line']}</td><td>{escape(item['function'])}</td>"
        f"<td>{item['cumulative_time_s']:.4f}s</td><td>{escape(item['ownership'])}</td></tr>"
        for item in top_functions
    ) or "<tr><td colspan='5'>No hotspot functions</td></tr>"
    owner_rows = "".join(
        f"<li>{escape(item['bucket'])}: {item['cumulative_time_s']:.4f}s</li>"
        for item in ownership
    ) or "<li>No ownership data</li>"
    return (
        "<table><thead><tr><th>File</th><th>Line</th><th>Function</th><th>Cumulative</th><th>Owner</th></tr></thead>"
        f"<tbody>{fn_rows}</tbody></table><ul>{owner_rows}</ul>"
    )


def _candidate_detail(metadata: dict) -> str:
    parts = []
    improvement = metadata.get("improvement_summary", {})
    summary = improvement.get("summary") if isinstance(improvement, dict) else None
    if summary:
        parts.append(summary)
    dependency_state = metadata.get("dependency_policy_state")
    if dependency_state:
        parts.append(f"deps={dependency_state}")
    explanation = metadata.get("explanation_summary")
    if explanation:
        parts.append(str(explanation).splitlines()[0])
    return " | ".join(parts) if parts else "-"
