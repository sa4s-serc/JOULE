from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import joule.discovery.profiler as profiler_module
import joule.discovery.resolver as resolver_module
from joule.cli import app
from joule.config import load_settings
from joule.discovery.resolver import discover_targets, resolve_target, resolve_workload_bundle
from joule.models import WorkloadKind


runner = CliRunner()


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
    assert bundle.workloads[0].metadata["provenance"] == "golden-default-args"


def test_resolve_target_supports_async_and_class_methods(sample_project):
    source = sample_project / "sample_pkg" / "algos.py"
    async_target = resolve_target(source, "async_square_total", project_root=sample_project)
    method_target = resolve_target(source, "NumberCruncher.generator_total", project_root=sample_project)

    assert async_target.is_async is True
    assert async_target.qualname == "async_square_total"
    assert method_target.owner_path == ["NumberCruncher"]
    assert method_target.qualname == "NumberCruncher.generator_total"


def test_resolve_target_rejects_impure_and_nested_targets(sample_project):
    source = sample_project / "sample_pkg" / "algos.py"

    with pytest.raises(ValueError, match="impure"):
        resolve_target(source, "impure_total", project_root=sample_project)
    with pytest.raises(ValueError, match="out of scope"):
        resolve_target(source, "inner_total", project_root=sample_project)


def test_workload_bundle_prefers_explicit_selectors(sample_project):
    settings = load_settings(sample_project)
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "membership_total", project_root=sample_project)
    bundle = resolve_workload_bundle(
        settings,
        target,
        tests=["tests/test_algos.py::test_membership_total"],
        properties=None,
        harness=None,
    )

    assert len(bundle.workloads) == 1
    assert bundle.workloads[0].metadata["provenance"] == "explicit"
    assert "using explicit workload selectors" in bundle.notes


def test_heuristic_discovery_preserves_class_based_pytest_selectors(sample_project):
    test_file = sample_project / "tests" / "test_class_based.py"
    test_file.write_text(
        "from sample_pkg.algos import membership_total\n\n"
        "class TestMembershipTotal:\n"
        "    def test_membership_total(self):\n"
        "        assert membership_total(1) == 2\n",
        encoding="utf-8",
    )

    settings = load_settings(sample_project)
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "membership_total", project_root=sample_project)
    bundle = resolve_workload_bundle(settings, target, tests=None, properties=None, harness=None)

    assert any("::TestMembershipTotal::test_membership_total" in workload.selector for workload in bundle.workloads)


def test_async_target_without_aligned_workloads_requires_explicit_selectors(sample_project):
    settings = load_settings(sample_project)
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "async_orphan_total", project_root=sample_project)

    with pytest.raises(ValueError, match="Provide --tests/--properties/--harness"):
        resolve_workload_bundle(settings, target, tests=None, properties=None, harness=None)


def test_discover_cli_returns_json_payload_with_provenance(sample_project):
    result = runner.invoke(app, ["discover", str(sample_project)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload
    first = payload[0]
    assert "target" in first
    assert "workload_provenance" in first
    if first["workload_provenance"]:
        item = first["workload_provenance"][0]
        assert "identifier" in item
        assert "provenance" in item
        assert "resolution_strategy" in item


def test_module_name_resolution_prefers_project_src_root(tmp_path: Path):
    project_root = tmp_path / "src" / "project_root"
    file_path = project_root / "src" / "sample_pkg" / "algos.py"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("def total(values):\n    return sum(values)\n", encoding="utf-8")

    assert resolver_module._module_name(project_root, file_path) == "sample_pkg.algos"
    assert profiler_module._module_name(project_root, file_path) == "sample_pkg.algos"


def test_resolve_target_supports_complex_module_targets(sample_project):
    source = sample_project / "sample_pkg" / "complex_cases.py"
    warehouse_target = resolve_target(source, "warehouse_balancing_pipeline", project_root=sample_project)
    telemetry_target = resolve_target(source, "telemetry_triage_pipeline", project_root=sample_project)

    assert warehouse_target.module == "sample_pkg.complex_cases"
    assert warehouse_target.qualname == "warehouse_balancing_pipeline"
    assert telemetry_target.qualname == "telemetry_triage_pipeline"


def test_workload_bundle_accepts_new_property_selector(sample_project):
    settings = load_settings(sample_project)
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "counter_histogram", project_root=sample_project)
    bundle = resolve_workload_bundle(
        settings,
        target,
        tests=None,
        properties=["sample_pkg.properties:property_counter_histogram"],
        harness=None,
    )

    assert len(bundle.workloads) == 1
    assert bundle.workloads[0].kind is WorkloadKind.PROPERTY
    assert bundle.workloads[0].metadata["provenance"] == "explicit"


def test_workload_bundle_accepts_new_harness_selector(sample_project):
    settings = load_settings(sample_project)
    target = resolve_target(
        sample_project / "sample_pkg" / "complex_cases.py",
        "warehouse_balancing_pipeline",
        project_root=sample_project,
    )
    bundle = resolve_workload_bundle(
        settings,
        target,
        tests=None,
        properties=None,
        harness="sample_pkg.harnesses:warehouse_pipeline_harness",
    )

    assert len(bundle.workloads) == 1
    assert bundle.workloads[0].kind is WorkloadKind.HARNESS
    assert bundle.workloads[0].metadata["provenance"] == "explicit"


def test_resolve_target_supports_recursive_example_target(sample_project):
    source = sample_project / "sample_pkg" / "edge_cases.py"
    target = resolve_target(source, "recursive_inventory_checksum", project_root=sample_project)

    assert target.qualname == "recursive_inventory_checksum"
