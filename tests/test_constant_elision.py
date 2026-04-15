import ast
from pathlib import Path
from joule.transformers.deterministic.constant_condition_elision import ConstantConditionElision
from joule.models import TargetSpec

def _target(source: str) -> TargetSpec:
    return TargetSpec(
        project_root=Path("."),
        module="sample",
        function_name="dummy",
        qualname="dummy",
        owner_path=[],
        file_path=Path("dummy.py"),
        line_start=1,
        line_end=1,
        source=source,
    )

def test_elision_with_multistatement_blocks():
    source = "if True:\n    x = 1\n    y = 2\nelse:\n    z = 3"
    target = _target(source)
    results = ConstantConditionElision().generate(target)
    assert len(results) == 1
    assert "x = 1\ny = 2" in results[0].candidate_source
