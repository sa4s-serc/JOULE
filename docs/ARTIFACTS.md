# Artifacts Guide

This guide answers a practical question: which artifact should I inspect first?

## Quick Lookup

Question: Did a run complete and which target did it use?
- Check `.joule.lock` for run id, target, backend, hashes, and config snapshot.
- Check `.joule/runs/<run_id>/run_summary.json` for final status and selected best candidate.

Question: What baseline numbers were measured?
- Check `.joule/runs/<run_id>/baseline.json` for full samples.
- Check `.joule/runs/<run_id>/baseline_analysis.json` for summary plus hotspots (if enabled).

Question: Why was a candidate rejected?
- Run `./joule inspect <project> --run-id <run_id> --candidate-id <candidate_id>`.
- Check `metadata.rejected`, `metadata.stage`, and `metadata.surrogate`.

Question: Which candidate is best and what changed?
- Check `.joule/runs/<run_id>/run_summary.json` -> `best_candidate`.
- Open `.joule/runs/<run_id>/best.patch` for the diff.
- Open `.joule/runs/<run_id>/best_candidate.py` for full source.

Question: Why did a worker fail or produce noise?
- Check `.joule/runs/<run_id>/events.jsonl` for structured warning/debug events.
- Check sample-level `stderr` in `baseline.json` or inspect output.

Question: What happened during optimization flow?
- Check `.joule/runs/<run_id>/optimization_analysis.json` for funnel and operator stats.
- Check `.joule/runs/<run_id>/events.jsonl` for stage-by-stage timeline.

Question: Which transformations exist and what do they do?
- Run `./joule transformations <project> --output human` for the runtime catalog.
- Read [docs/TRANSFORMATIONS.md](TRANSFORMATIONS.md) for tiering, operator intent, and implementation notes.

Question: How do I verify deterministic rewrite output shape stability?
- Check [tests/golden/deterministic_operator_snapshots.json](../tests/golden/deterministic_operator_snapshots.json).
- Run [tests/test_transformer_golden_snapshots.py](../tests/test_transformer_golden_snapshots.py).

Question: Was anything applied to source control?
- Check `apply_audits` in `inspect` output.
- Check git history if `apply --branch` or `apply --commit` was used.

## Persona Views

### New User
- Start with `run_summary.json`, `dashboard.html`, and `best.patch`.
- Use `inspect --output human` when you need a readable diagnosis.

### CI User
- Prefer `--output json --no-dashboard` for machine stability.
- Parse `run_summary.json` and `events.jsonl` for alerts and thresholds.

### Advanced User
- Use `optimization_analysis.json`, candidate packs in `candidates/`, and `events.jsonl` together.
- Compare multiple runs by target and rejection reasons to tune workloads/operators.

## Artifact Structure

```text
<project>/
├── .joule.lock
└── .joule/
    ├── joule.db
    └── runs/
        └── <run_id>/
            ├── baseline.json
            ├── baseline_analysis.json
            ├── run_summary.json
            ├── optimization_analysis.json
            ├── hotspots.json
            ├── dashboard.html
            ├── events.jsonl
            ├── best.patch
            ├── best_candidate.py
            └── candidates/
                └── <candidate_id>/
                    ├── candidate.json
                    └── candidate.py
```
