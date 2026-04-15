from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

from joule.metadata import parse_candidate_metadata
from joule.utils.db import JouleDB
from joule.utils.analysis import FUNNEL_ORDER, cross_run_trends
from joule.utils.reporting import workload_provenance_records


def render_dashboard_html(db: JouleDB, selected_run_id: str | None = None) -> str:
    runs = db.list_runs()
    run_ids = {item["run_id"] for item in runs}
    latest = selected_run_id if selected_run_id in run_ids else (runs[0]["run_id"] if runs else None)
    current = _run_section(db, latest) if latest else "<p>No runs recorded yet.</p>"
    trends = _trends_section(runs)
    total_runs = len(runs)
    completed_runs = sum(1 for item in runs if item.get("status") == "completed")
    running_runs = sum(1 for item in runs if item.get("status") == "running")
    failed_runs = sum(1 for item in runs if item.get("status") not in {"completed", "running"})
    run_type_counts: dict[str, int] = {}
    rows_parts: list[str] = []
    for run in runs:
        run_id = str(run.get("run_id", ""))
        run_type = str(run.get("run_type", "-"))
        status = str(run.get("status", "-"))
        created_at = str(run.get("created_at", "-"))
        run_type_counts[run_type] = run_type_counts.get(run_type, 0) + 1
        rows_parts.append(
            f"<tr><td><a href='/?run_id={quote_plus(run_id)}'>{escape(run_id)}</a></td>"
            f"<td>{escape(run_type)}</td>"
            f"<td><span class='status-badge {_status_css_class(status)}'>{escape(status)}</span></td>"
            f"<td>{escape(created_at)}</td></tr>"
        )
    rows = "".join(rows_parts) if rows_parts else "<tr><td colspan='4'>No runs</td></tr>"
    run_options = "".join(
        f"<option value='{escape(str(run.get('run_id', '')))}'"
        f"{' selected' if run.get('run_id') == latest else ''}>{escape(str(run.get('run_id', '')))}</option>"
        for run in runs
    )
    run_type_chips = "".join(
        f"<span class='chip'>{escape(run_type)}={count}</span>"
        for run_type, count in sorted(run_type_counts.items())
    )
    if run_options:
        run_selector = (
            "<form class='controls' method='get'>"
            "<label for='run-selector'>Run</label>"
            f"<select id='run-selector' name='run_id'>{run_options}</select>"
            "<button type='submit'>Open</button>"
            "<button type='button' onclick='window.location.reload()'>Refresh</button>"
            "</form>"
        )
    else:
        run_selector = (
            "<div class='controls'>"
            "<button type='button' onclick='window.location.reload()'>Refresh</button>"
            "</div>"
        )
    selected_label = escape(str(latest)) if latest else "none"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
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
            --running: #8a5b00;
            --chip: #f2eadf;
    }}
    body {{ font-family: Georgia, "Iowan Old Style", serif; background: linear-gradient(180deg, #f8f5ef 0%, #efe7da 100%); color: var(--ink); margin: 0; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 48px; }}
    h1, h2 {{ margin: 0 0 12px; }}
        h3 {{ margin: 16px 0 10px; }}
        a {{ color: var(--accent); }}
    .grid {{ display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }}
    .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 18px; padding: 18px; box-shadow: 0 10px 24px rgba(30, 42, 47, 0.06); }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--border); vertical-align: top; }}
    code, pre {{ font-family: "IBM Plex Mono", "SFMono-Regular", monospace; font-size: 12px; }}
    pre {{ white-space: pre-wrap; background: #f4efe6; padding: 12px; border-radius: 12px; overflow: auto; }}
        .hero {{ display: grid; gap: 10px; margin-bottom: 18px; }}
        .chips {{ display: flex; gap: 8px; flex-wrap: wrap; }}
        .chip {{ background: var(--chip); border: 1px solid var(--border); border-radius: 999px; padding: 4px 10px; font-size: 12px; }}
        .controls {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; align-items: center; }}
        .controls select,
        .controls button,
        .controls input {{
            border: 1px solid var(--border);
            border-radius: 10px;
            background: #fff;
            padding: 6px 8px;
            font-family: inherit;
            color: var(--ink);
        }}
        .controls label {{ display: inline-flex; gap: 6px; align-items: center; font-size: 13px; }}
        .next-steps li {{ margin-bottom: 6px; }}
        .status-badge {{ display: inline-block; border: 1px solid currentColor; border-radius: 999px; padding: 1px 8px; font-size: 12px; font-weight: 600; }}
        .status-ok {{ color: var(--ok); }}
        .status-running {{ color: var(--running); }}
        .status-bad {{ color: var(--bad); }}
    .ok {{ color: var(--ok); }}
    .bad {{ color: var(--bad); }}
    .muted {{ color: var(--muted); }}
        .small {{ font-size: 13px; }}
  </style>
</head>
<body>
  <main>
        <section class="hero panel">
            <h1>JOULE Dashboard</h1>
            <p class="muted">Guided run review with candidate filtering, trend context, and recommended next actions.</p>
            <div class="chips">
                <span class="chip">runs={total_runs}</span>
                <span class="chip">completed={completed_runs}</span>
                <span class="chip">running={running_runs}</span>
                <span class="chip">other={failed_runs}</span>
            </div>
            {"<div class='chips'>" + run_type_chips + "</div>" if run_type_chips else ""}
            <p class="muted small">selected_run={selected_label}</p>
            {run_selector}
        </section>
    <div class="grid">
      <section class="panel">
        <h2>Runs</h2>
                <p class="muted">Select a run ID to inspect candidate details, hotspot diagnostics, and artifacts.</p>
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
            query = parse_qs(urlparse(self.path).query)
            requested_run_id = query.get("run_id", [selected_run_id])[0]
            payload = render_dashboard_html(db, selected_run_id=requested_run_id).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, max-age=0")
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
    try:
        run = db.get_run(run_id)
    except KeyError:
        return "<p>Requested run was not found.</p>"
    candidates = db.get_candidates(run_id)
    measurements = db.get_measurements(run_id)
    artifacts = db.get_artifacts(run_id)
    audits = db.get_apply_audits(run_id)
    search_events = db.get_search_events(run_id)
    hotspots = db.get_hotspot_profiles(run_id)
    latest_measurement = measurements[-1]["aggregate"] if measurements else None
    accepted_count = sum(1 for item in candidates if item.get("status") == "accepted")
    rejected_count = sum(1 for item in candidates if item.get("status") == "rejected")
    skipped_count = sum(1 for item in candidates if item.get("status") == "skipped")
    candidate_rows_parts: list[str] = []
    for item in candidates:
        metadata = parse_candidate_metadata(item.get("metadata", {}))
        stage_value = metadata.stage or "-"
        tier_value = metadata.operator_tier or "-"
        reason_value = metadata.rejected or "-"
        detail_value = _candidate_detail(item.get("metadata", {}))
        searchable = " ".join(
            [
                str(item.get("candidate_id", "")),
                str(item.get("operator_name", "")),
                str(stage_value),
                str(tier_value),
                str(reason_value),
                str(detail_value),
            ]
        ).lower()
        status_value = str(item.get("status", "-"))
        score_value = float(item.get("score", 0.0))
        candidate_rows_parts.append(
            f"<tr class='candidate-row' data-status='{escape(status_value)}' data-score='{score_value:.12f}' "
            f"data-stage='{escape(stage_value)}' data-tier='{escape(tier_value)}' data-search='{escape(searchable)}'>"
            f"<td>{escape(str(item.get('candidate_id', '-')))}</td><td>{escape(str(item.get('operator_name', '-')))}</td>"
            f"<td>{escape(tier_value)}</td>"
            f"<td><span class='status-badge {_status_css_class(status_value)}'>{escape(status_value)}</span></td><td>{score_value:.6f}</td>"
            f"<td>{escape(stage_value)}</td>"
            f"<td>{escape(reason_value)}</td>"
            f"<td>{escape(detail_value)}</td></tr>"
        )
    candidate_rows = "".join(candidate_rows_parts)
    if not candidate_rows:
        candidate_rows = "<tr><td colspan='8'>No candidates yet</td></tr>"
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
    next_steps = _recommended_actions(
        run_status=run.status,
        run_type=run.run_type.value,
        accepted_count=accepted_count,
        artifacts=artifacts,
        audits=audits,
    )
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
        <div class="chips">
            <span class="chip">accepted={accepted_count}</span>
            <span class="chip">rejected={rejected_count}</span>
            <span class="chip">skipped={skipped_count}</span>
            <span class="chip">events={len(search_events)}</span>
        </div>
    {aggregate_html}
    <p><strong>Search funnel</strong><br>{search_summary}</p>
        <h3>Recommended Next Steps</h3>
        <ul class="next-steps">{next_steps}</ul>
    <h3>Workload Provenance</h3>
    <ul>{provenance_items}</ul>
    <p><strong>Adaptive Calibration</strong><br>{calibration_html}</p>
    <h3>Hotspots</h3>
    {hotspot_html}
    <h3>Candidates</h3>
        <div class="controls">
            <label for="candidate-search-filter">Search
                <input id="candidate-search-filter" type="search" oninput="filterCandidates()" placeholder="id, operator, reason, details">
            </label>
            <label for="candidate-status-filter">Status
                <select id="candidate-status-filter" onchange="filterCandidates()">
                    <option value="all">all</option>
                    <option value="accepted">accepted</option>
                    <option value="rejected">rejected</option>
                    <option value="skipped">skipped</option>
                </select>
            </label>
            <label for="candidate-tier-filter">Tier
                <select id="candidate-tier-filter" onchange="filterCandidates()">
                    <option value="all">all</option>
                    <option value="L">L</option>
                    <option value="M">M</option>
                    <option value="H">H</option>
                </select>
            </label>
            <label for="candidate-stage-filter">Stage
                <select id="candidate-stage-filter" onchange="filterCandidates()">
                    <option value="all">all</option>
                </select>
            </label>
            <label for="candidate-sort">Sort
                <select id="candidate-sort" onchange="filterCandidates()">
                    <option value="score-asc">score asc</option>
                    <option value="score-desc">score desc</option>
                    <option value="stage">stage</option>
                </select>
            </label>
            <button type="button" onclick="resetCandidateFilters()">Clear filters</button>
        </div>
        <p class="muted small" id="candidate-visible-count" aria-live="polite"></p>
    <table>
      <thead><tr><th>ID</th><th>Operator</th><th>Tier</th><th>Status</th><th>Score</th><th>Stage</th><th>Reason</th><th>Details</th></tr></thead>
            <tbody id="candidate-table-body">{candidate_rows}</tbody>
    </table>
    <h3>Artifacts</h3>
    <ul>{artifact_items}</ul>
    <h3>Apply Audits</h3>
    <ul>{audit_items}</ul>
        <script>
            function candidateRows() {{
                const body = document.getElementById('candidate-table-body');
                if (!body) return [];
                return Array.from(body.querySelectorAll('.candidate-row'));
            }}

            function scoreValue(row) {{
                const score = Number(row.dataset.score);
                return Number.isFinite(score) ? score : 0;
            }}

            function populateStageFilter() {{
                const stageFilter = document.getElementById('candidate-stage-filter');
                if (!stageFilter || stageFilter.dataset.ready === '1') return;
                const stages = Array.from(new Set(candidateRows().map((row) => String(row.dataset.stage || '-'))));
                stages.sort((left, right) => left.localeCompare(right));
                stages.forEach((stage) => {{
                    const option = document.createElement('option');
                    option.value = stage;
                    option.textContent = stage;
                    stageFilter.appendChild(option);
                }});
                stageFilter.dataset.ready = '1';
            }}

            function resetCandidateFilters() {{
                const search = document.getElementById('candidate-search-filter');
                const status = document.getElementById('candidate-status-filter');
                const tier = document.getElementById('candidate-tier-filter');
                const stage = document.getElementById('candidate-stage-filter');
                const sort = document.getElementById('candidate-sort');
                if (search) search.value = '';
                if (status) status.value = 'all';
                if (tier) tier.value = 'all';
                if (stage) stage.value = 'all';
                if (sort) sort.value = 'score-asc';
                filterCandidates();
            }}

            function filterCandidates() {{
                const statusFilter = document.getElementById('candidate-status-filter');
                const tierFilter = document.getElementById('candidate-tier-filter');
                const stageFilter = document.getElementById('candidate-stage-filter');
                const searchFilter = document.getElementById('candidate-search-filter');
                const sortMode = document.getElementById('candidate-sort');
                const body = document.getElementById('candidate-table-body');
                if (!body) return;

                const rows = candidateRows();
                const wantedStatus = statusFilter ? statusFilter.value : 'all';
                const wantedTier = tierFilter ? tierFilter.value : 'all';
                const wantedStage = stageFilter ? stageFilter.value : 'all';
                const wantedText = searchFilter ? searchFilter.value.trim().toLowerCase() : '';

                rows.forEach((row) => {{
                    const statusOk = wantedStatus === 'all' || row.dataset.status === wantedStatus;
                    const tierOk = wantedTier === 'all' || row.dataset.tier === wantedTier;
                    const stageOk = wantedStage === 'all' || row.dataset.stage === wantedStage;
                    const haystack = String(row.dataset.search || '');
                    const textOk = !wantedText || haystack.includes(wantedText);
                    const keep = statusOk && tierOk && stageOk && textOk;
                    row.style.display = keep ? '' : 'none';
                }});

                const visible = rows.filter((row) => row.style.display !== 'none');
                const mode = sortMode ? sortMode.value : 'score-asc';
                visible.sort((a, b) => {{
                    if (mode === 'score-desc') return scoreValue(b) - scoreValue(a);
                    if (mode === 'stage') {{
                        const stageDelta = String(a.dataset.stage || '').localeCompare(String(b.dataset.stage || ''));
                        if (stageDelta !== 0) return stageDelta;
                        return scoreValue(a) - scoreValue(b);
                    }}
                    return scoreValue(a) - scoreValue(b);
                }});
                visible.forEach((row) => body.appendChild(row));

                const countLabel = document.getElementById('candidate-visible-count');
                if (countLabel) {{
                    countLabel.textContent = `Showing ${{visible.length}} of ${{rows.length}} candidates`;
                }}
            }}

            populateStageFilter();
            filterCandidates();
        </script>
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
        return "<span class='muted'>No search events</span>"
    counts: dict[str, int] = {}
    for event in events:
        event_type = str(event.get("event_type", "unknown"))
        counts[event_type] = counts.get(event_type, 0) + 1
    ordered_counts = sorted(counts.items(), key=lambda item: _event_sort_key(item[0]))
    chips = "".join(
        f"<span class='chip'>{escape(name)}={count}</span>"
        for name, count in ordered_counts
    )
    return f"<div class='chips'>{chips}</div>"


def _event_sort_key(event_type: str) -> tuple[int, int | str]:
    if event_type in FUNNEL_ORDER:
        return (0, FUNNEL_ORDER.index(event_type))
    return (1, event_type)


def _status_css_class(status: str) -> str:
    normalized = str(status).strip().lower()
    if normalized == "completed":
        return "status-ok"
    if normalized == "running":
        return "status-running"
    return "status-bad"


def _hotspot_section(records: list[dict]) -> str:
    summary = next((item["payload"] for item in records if item["kind"] == "summary"), None)
    if not summary:
        return "<p>No hotspot analysis recorded.</p>"
    top_functions = summary.get("top_functions", [])
    target_top_functions = summary.get("target_top_functions", [])
    ownership = summary.get("ownership", [])
    by_workload = summary.get("by_workload", [])
    workload_kind_counts = summary.get("workload_kind_counts", {})
    signal_quality = summary.get("signal_quality", {})
    insights = summary.get("insights", {})
    recommendations = summary.get("recommendations", [])
    schema_version = summary.get("schema_version", "-")

    def _workload_signal_line(label: str, payload: dict | None) -> str | None:
        if not isinstance(payload, dict) or not payload:
            return None
        return (
            f"{label}="
            f"{payload.get('workload_id', '-')}/{payload.get('workload_kind', '-')} "
            f"(project_share={float(payload.get('project_share', 0.0)) * 100:.1f}%, "
            f"target_share={float(payload.get('target_share', 0.0)) * 100:.1f}%)"
        )

    fn_rows = "".join(
        f"<tr><td>{escape(Path(item['file']).name)}</td><td>{item['line']}</td><td>{escape(item['function'])}</td>"
        f"<td>{item['cumulative_time_s']:.4f}s</td><td>{float(item.get('share', 0.0)) * 100:.1f}%</td><td>{escape(item['ownership'])}</td></tr>"
        for item in top_functions
    ) or "<tr><td colspan='6'>No hotspot functions</td></tr>"

    target_rows = "".join(
        f"<tr><td>{escape(Path(item['file']).name)}</td><td>{item['line']}</td><td>{escape(item['function'])}</td>"
        f"<td>{item['cumulative_time_s']:.4f}s</td><td>{float(item.get('share', 0.0)) * 100:.1f}%</td></tr>"
        for item in target_top_functions[:8]
    ) or "<tr><td colspan='5'>No target-file hotspots captured</td></tr>"

    owner_rows = "".join(
        f"<li>{escape(item['bucket'])}: {item['cumulative_time_s']:.4f}s</li>"
        for item in ownership
    ) or "<li>No ownership data</li>"

    workload_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('workload_id', '-')))}</td>"
        f"<td>{escape(str(item.get('workload_kind', '-')))}</td>"
        f"<td>{float((item.get('signal') or {}).get('project_share', 0.0)) * 100:.1f}%</td>"
        f"<td>{float((item.get('signal') or {}).get('target_share', 0.0)) * 100:.1f}%</td>"
        f"<td>{escape(str((item.get('signal') or {}).get('dominant_ownership_bucket', '-')))}</td>"
        f"<td>{'yes' if bool((item.get('signal') or {}).get('low_signal', False)) else 'no'}</td>"
        "</tr>"
        for item in by_workload[:10]
    ) or "<tr><td colspan='6'>No workload signal diagnostics</td></tr>"

    workload_kind_chips = "".join(
        f"<span class='chip'>{escape(str(kind))}={count}</span>"
        for kind, count in workload_kind_counts.items()
    ) or "<span class='chip'>no-workload-kinds</span>"

    low_signal = bool(signal_quality.get("low_signal", False))
    low_signal_reasons = signal_quality.get("low_signal_reasons", []) or []
    reason_items = "".join(f"<li>{escape(str(reason))}</li>" for reason in low_signal_reasons)
    if not reason_items:
        reason_items = "<li>none</li>"

    recommendation_items = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in recommendations
    ) or "<li>No recommendations yet</li>"

    insight_lines: list[str] = [
        f"profiled_workloads={insights.get('profiled_workload_count', len(by_workload))}",
    ]
    primary_target_hotspot = insights.get("primary_target_hotspot")
    if isinstance(primary_target_hotspot, dict) and primary_target_hotspot:
        insight_lines.append(
            "primary_target_hotspot="
            f"{Path(str(primary_target_hotspot.get('file', 'unknown'))).name}:"
            f"{primary_target_hotspot.get('line', '-')}:"
            f"{primary_target_hotspot.get('function', 'unknown')} "
            f"(share={float(primary_target_hotspot.get('share', 0.0)) * 100:.1f}%)"
        )
    strongest_line = _workload_signal_line("strongest_signal_workload", insights.get("strongest_signal_workload"))
    if strongest_line:
        insight_lines.append(strongest_line)
    weakest_line = _workload_signal_line("weakest_signal_workload", insights.get("weakest_signal_workload"))
    if weakest_line:
        insight_lines.append(weakest_line)
    insight_items = "".join(f"<li>{escape(line)}</li>" for line in insight_lines)

    return (
        "<p><strong>Hotspot Signal Quality</strong>: "
        f"low_signal={'yes' if low_signal else 'no'} "
        f"project_share={float(signal_quality.get('project_share', 0.0)) * 100:.1f}% "
        f"target_share={float(signal_quality.get('target_share', 0.0)) * 100:.1f}% "
        f"dominant_owner={escape(str(signal_quality.get('dominant_ownership_bucket', '-')))}</p>"
        f"<p class='muted small'>schema_version={escape(str(schema_version))}</p>"
        f"<ul>{reason_items}</ul>"
        "<p><strong>Hotspot Insights</strong></p>"
        f"<ul>{insight_items}</ul>"
        "<p><strong>Workload Mix</strong></p>"
        f"<div class='chips'>{workload_kind_chips}</div>"
        "<table><thead><tr><th>Workload</th><th>Kind</th><th>Project Share</th><th>Target Share</th><th>Top Owner</th><th>Low Signal</th></tr></thead>"
        f"<tbody>{workload_rows}</tbody></table>"
        "<p><strong>Target Hotspots</strong></p>"
        "<table><thead><tr><th>File</th><th>Line</th><th>Function</th><th>Cumulative</th><th>Share</th></tr></thead>"
        f"<tbody>{target_rows}</tbody></table>"
        "<p><strong>Overall Hotspots</strong></p>"
        "<table><thead><tr><th>File</th><th>Line</th><th>Function</th><th>Cumulative</th><th>Share</th><th>Owner</th></tr></thead>"
        f"<tbody>{fn_rows}</tbody></table>"
        "<p><strong>Ownership Totals</strong></p>"
        f"<ul>{owner_rows}</ul>"
        "<p><strong>Hotspot Recommendations</strong></p>"
        f"<ul>{recommendation_items}</ul>"
    )


def _candidate_detail(metadata: dict) -> str:
    parsed = parse_candidate_metadata(metadata)
    parts = []
    tier = parsed.operator_tier
    descriptor = parsed.operator_tier_descriptor
    if tier:
        if descriptor:
            parts.append(f"tier={tier} ({descriptor})")
        else:
            parts.append(f"tier={tier}")
    summary = parsed.improvement_summary.summary
    if summary:
        parts.append(summary)
    dependency_state = parsed.dependency_policy_state
    if dependency_state:
        parts.append(f"deps={dependency_state}")
    explanation = parsed.explanation_summary
    if explanation:
        parts.append(str(explanation).splitlines()[0])
    return " | ".join(parts) if parts else "-"


def _recommended_actions(
    *,
    run_status: str,
    run_type: str,
    accepted_count: int,
    artifacts: list[dict],
    audits: list[dict],
) -> str:
    artifact_names = {item.get("name") for item in artifacts}
    actions: list[str] = []
    if run_status != "completed":
        actions.append("<li>Wait for completion, then refresh to inspect final metrics and candidate outcomes.</li>")
    if run_type == "baseline":
        actions.append("<li>Run optimization next: <code>joule run ... --analysis</code> to generate candidate comparisons.</li>")
    if accepted_count > 0:
        actions.append("<li>Review best candidate details in the table, then apply with <code>joule apply ... --run-id ...</code>.</li>")
    else:
        actions.append("<li>No accepted candidates yet: inspect rejection reasons and consider stronger workload selectors.</li>")
    if "events.jsonl" in artifact_names:
        actions.append("<li>Inspect <code>events.jsonl</code> for structured diagnostics and CI triage.</li>")
    if "best.patch" in artifact_names:
        actions.append("<li>Open <code>best.patch</code> to review code diffs before applying changes.</li>")
    if not audits:
        actions.append("<li>No apply audits recorded yet; once applied, this view will track candidate application history.</li>")
    return "".join(actions)
