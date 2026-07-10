"""ASCII Pareto front visualization for terminal output.

Renders a 2-D projection of the 3-D Pareto frontier as a
scatter-plot in the terminal using ``rich`` panels.  When
``rich`` is not available the function falls back to plain text.

Usage::

    from joule.utils.pareto_chart import render_pareto_chart
    panel = render_pareto_chart(pareto_points, baseline_metrics)
    console.print(panel)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

# Width / height of the ASCII canvas (characters)
_CANVAS_W = 60
_CANVAS_H = 18
_AXES = ("energy_j", "latency_s", "memory_mb")
_AXIS_LABELS = ("Energy (J)", "Latency (s)", "Memory (MB)")


def _scale(value: float, lo: float, hi: float, n: int) -> int:
    """Map *value* from [lo, hi] into [0, n-1]."""
    if hi <= lo:
        return n // 2
    return max(0, min(n - 1, int((value - lo) / (hi - lo) * (n - 1))))


def render_pareto_ascii(
    points: list[dict[str, Any]],
    baseline: dict[str, float] | None = None,
    *,
    x_metric: str = "energy_j",
    y_metric: str = "latency_s",
    width: int = _CANVAS_W,
    height: int = _CANVAS_H,
) -> str:
    """Return a multi-line ASCII Pareto scatter plot.

    Parameters
    ----------
    points:
        List of Pareto point dicts.  Each must contain a
        ``"metrics"`` key with at minimum ``x_metric`` and
        ``y_metric`` float values, and a ``"candidate_id"``
        string.
    baseline:
        Optional dict with baseline metric values (same keys).
    x_metric / y_metric:
        Which metric to plot on each axis.
    width / height:
        ASCII canvas dimensions.

    Returns
    -------
    str
        Multi-line string ready for ``print()`` or ``rich.console.print()``.
    """
    if not points:
        return "(no Pareto points to display)"

    # Collect all x/y values including the baseline for scaling.
    def _get(d: dict, key: str) -> float:
        metrics = d.get("metrics", d)
        if not isinstance(metrics, dict):
            # Try asdict/record format or fallback
            try:
                metrics = metrics.to_record()
            except AttributeError:
                pass
        
        # Check aliases
        aliases = [key]
        if "energy" in key:
            aliases.extend(["energy_j", "mean_energy_j", "energy"])
        elif "latency" in key or "time" in key:
            aliases.extend(["latency_s", "mean_wall_time_s", "mean_cpu_time_s", "latency"])
        elif "memory" in key:
            aliases.extend(["memory_bytes", "mean_peak_memory_bytes", "memory"])
            
        for alias in aliases:
            if alias in metrics:
                raw = metrics[alias]
                if isinstance(raw, dict):
                    raw = raw.get("mean", 0.0)
                return float(raw)
        return 0.0


    xs = [_get(p, x_metric) for p in points]
    ys = [_get(p, y_metric) for p in points]
    if baseline:
        xs.append(float(baseline.get(x_metric, 0.0)))
        ys.append(float(baseline.get(y_metric, 0.0)))

    x_lo, x_hi = min(xs), max(xs)
    y_lo, y_hi = min(ys), max(ys)

    # Add a 5 % margin
    x_pad = max(1e-9, (x_hi - x_lo) * 0.05)
    y_pad = max(1e-9, (y_hi - y_lo) * 0.05)
    x_lo -= x_pad
    x_hi += x_pad
    y_lo -= y_pad
    y_hi += y_pad

    # Build canvas
    canvas = [[" "] * width for _ in range(height)]

    def _plot(xv: float, yv: float, char: str) -> None:
        col = _scale(xv, x_lo, x_hi, width)
        # Y is inverted: higher y → lower row
        row = height - 1 - _scale(yv, y_lo, y_hi, height)
        canvas[row][col] = char

    # Draw baseline star
    if baseline:
        _plot(float(baseline.get(x_metric, 0.0)), float(baseline.get(y_metric, 0.0)), "B")

    # Draw Pareto points
    for p in points:
        xv = _get(p, x_metric)
        yv = _get(p, y_metric)
        is_active = bool(p.get("active", True))
        char = "●" if is_active else "○"
        _plot(xv, yv, char)

    # Compose lines
    lines: list[str] = []
    x_label = x_metric.replace("_", " ").title()
    y_label = y_metric.replace("_", " ").title()

    # Top border + Y-axis label
    lines.append(f"  ┌{'─' * width}┐  {y_label} ↑")
    for i, row in enumerate(canvas):
        y_val = y_hi - (y_hi - y_lo) * i / max(1, height - 1)
        prefix = f"{y_val:6.3g} " if i % (height // 3 + 1) == 0 else "       "
        lines.append(f"{prefix}│{''.join(row)}│")
    lines.append(f"  └{'─' * width}┘")

    # X-axis ticks
    tick_lo = f"{x_lo + x_pad:.3g}"
    tick_hi = f"{x_hi - x_pad:.3g}"
    pad = width - len(tick_lo) - len(tick_hi) - 2
    lines.append(f"       {tick_lo}{' ' * max(0, pad)}{tick_hi}")
    lines.append(f"       {' ' * (width // 2 - len(x_label) // 2)}{x_label} →")
    lines.append("")
    lines.append("  Legend:  B = baseline   ● = active Pareto point   ○ = dominated")

    return "\n".join(lines)


def build_pareto_summary(
    points: list[dict[str, Any]],
    baseline_aggregate: dict[str, Any],
) -> dict[str, Any]:
    """Return a structured ``pareto_summary`` dict for ``run_summary.json``.

    Parameters
    ----------
    points:
        List of raw Pareto point dicts from the DB/checkpoint.
    baseline_aggregate:
        The ``AggregateMetrics.to_record()`` dict for the baseline.

    Returns
    -------
    dict with keys:
        - ``frontier_size``: number of active Pareto points
        - ``dominated_size``: number of dominated (inactive) points
        - ``best_per_metric``: dict mapping metric → best candidate_id
        - ``improvement_ratios``: per-candidate improvement over baseline
    """
    active = [p for p in points if p.get("active", True)]
    dominated = [p for p in points if not p.get("active", True)]

    def _metric(p: dict, key: str) -> float:
        metrics = p.get("metrics", p)
        if not isinstance(metrics, dict):
            try:
                metrics = metrics.to_record()
            except AttributeError:
                pass
        
        # Check aliases
        aliases = [key]
        if "energy" in key:
            aliases.extend(["energy_j", "mean_energy_j", "energy"])
        elif "latency" in key or "time" in key:
            aliases.extend(["latency_s", "mean_wall_time_s", "mean_cpu_time_s", "latency"])
        elif "memory" in key:
            aliases.extend(["memory_bytes", "mean_peak_memory_bytes", "memory"])
            
        for alias in aliases:
            if alias in metrics:
                raw = metrics[alias]
                if isinstance(raw, dict):
                    raw = raw.get("mean", 0.0)
                return float(raw)
        return 0.0


    bl_energy = float(baseline_aggregate.get("mean_energy_j", 1.0))
    bl_latency = float(baseline_aggregate.get("mean_wall_time_s", 1.0))
    bl_memory = float(baseline_aggregate.get("mean_peak_memory_bytes", 1.0))

    best_energy: tuple[float, str] = (float("inf"), "")
    best_latency: tuple[float, str] = (float("inf"), "")
    best_memory: tuple[float, str] = (float("inf"), "")
    improvement_ratios: list[dict] = []

    for p in active:
        cid = str(p.get("candidate_id", ""))
        e = _metric(p, "energy_j")
        lat = _metric(p, "latency_s")
        mem = _metric(p, "memory_bytes")
        if e < best_energy[0]:
            best_energy = (e, cid)
        if lat < best_latency[0]:
            best_latency = (lat, cid)
        if mem < best_memory[0]:
            best_memory = (mem, cid)
        improvement_ratios.append({
            "candidate_id": cid,
            "operator": p.get("operator_name", ""),
            "energy_improvement_pct": round(100.0 * (bl_energy - e) / max(1e-9, bl_energy), 2) if e else None,
            "latency_improvement_pct": round(100.0 * (bl_latency - lat) / max(1e-9, bl_latency), 2) if lat else None,
            "memory_improvement_pct": round(100.0 * (bl_memory - mem) / max(1e-9, bl_memory), 2) if mem else None,
        })

    return {
        "frontier_size": len(active),
        "dominated_size": len(dominated),
        "best_per_metric": {
            "energy": best_energy[1] or None,
            "latency": best_latency[1] or None,
            "memory": best_memory[1] or None,
        },
        "improvement_ratios": improvement_ratios,
    }
