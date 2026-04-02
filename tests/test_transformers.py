from __future__ import annotations

from joule.discovery.resolver import resolve_target
from joule.transformers.deterministic import ContainerMembershipOperator, SumListComprehensionOperator


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
