from __future__ import annotations

from joule.discovery.resolver import resolve_target
from joule.models import SearchPhase, TargetSpec
from joule.transformers.deterministic import (
    ContainerMembershipOperator,
    DictKeysMembershipElision,
    IteratorSubstitution,
    SumListComprehensionOperator,
)
from joule.transformers.registry import OperatorRegistry


def test_container_membership_operator_rewrites_list_membership(sample_project):
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "membership_total", project_root=sample_project)
    results = ContainerMembershipOperator().generate(target)
    assert results
    assert "{1, 3, 5, 7, 9, 11, 13, 15}" in results[0].candidate_source


def test_sum_generator_operator_rewrites_list_comp(sample_project):
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "unreferenced_total", project_root=sample_project)
    results = SumListComprehensionOperator().generate(target)
    assert results
    assert "sum((value for value in range(limit) if value % 3 == 0))" in results[0].candidate_source


def test_operator_precheck_detects_matching_pattern(sample_project):
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "membership_total", project_root=sample_project)
    assert ContainerMembershipOperator().precheck(target) is True


def test_operator_precheck_rejects_non_matching_pattern(sample_project):
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "unreferenced_total", project_root=sample_project)
    assert DictKeysMembershipElision().precheck(target) is False


def test_iterator_substitution_precheck_rejects_non_matching_target(sample_project):
    target = resolve_target(sample_project / "sample_pkg" / "algos.py", "unreferenced_total", project_root=sample_project)
    assert IteratorSubstitution().precheck(target) is False


def test_registry_precheck_prunes_when_no_operator_matches(tmp_path):
    target = TargetSpec(
        project_root=tmp_path,
        module="module",
        file_path=tmp_path / "module.py",
        function_name="target",
        qualname="target",
        owner_path=[],
        line_start=1,
        line_end=2,
        source="def target(x):\n    pass\n",
    )
    registry = OperatorRegistry(llm_model="", include_llm=False)
    selected = registry.select_operator_for_candidate(
        target=target,
        context=None,
        phase=SearchPhase.EXPLORATION,
        parent_generation=0,
    )
    assert selected is None
