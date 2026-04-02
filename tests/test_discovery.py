from __future__ import annotations

from joule.config import load_settings
from joule.discovery.resolver import discover_targets, resolve_target, resolve_workload_bundle
from joule.models import WorkloadKind


def test_discover_targets_aligns_tests(sample_project):
    settings = load_settings(sample_project)
    results = discover_targets(settings, sample_project)
    membership = next(result for result in results if result.target.function_name == "membership_total")
    assert membership.workloads
    assert membership.workloads[0].kind is WorkloadKind.PYTEST


def test_workload_bundle_falls_back_to_golden_trace(sample_project):
    settings = load_settings(sample_project)
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "unreferenced_total", project_root=sample_project)
    bundle = resolve_workload_bundle(settings, target, tests=None, properties=None, harness=None)
    assert bundle.workloads[0].kind is WorkloadKind.GOLDEN_TRACE
