from __future__ import annotations

import ast
import json
from pathlib import Path

from joule.models import TargetSpec
from joule.transformers.generative import default_llm_operators, escape_llm_operators


def _target(source: str) -> TargetSpec:
    return TargetSpec(
        project_root=Path("."),
        module="sample",
        file_path=Path("sample.py"),
        function_name="target",
        qualname="target",
        owner_path=[],
        line_start=1,
        line_end=max(1, source.count("\n") + 1),
        source=source,
    )


def test_llm_operators_define_operator_specific_precheck_nodes():
    operators = [*default_llm_operators("fake-model"), *escape_llm_operators("fake-model")]
    generic_precheck = (ast.FunctionDef, ast.AsyncFunctionDef)
    for operator in operators:
        assert operator.precheck_node_types
        assert operator.precheck_node_types != generic_precheck


def test_fake_llm_golden_per_operator_objective(monkeypatch):
    operators = [*default_llm_operators("fake-model"), *escape_llm_operators("fake-model")]
    fake_payload = {
        operator.name: {
            "candidate_source": "from collections import deque\n\ndef target(values):\n    out = deque(values)\n    return len(out)\n",
            "reasoning": f"rewrite for {operator.name}",
            "dependencies": ["collections"],
            "proposal_rank": 0,
            "feature_hints": {"objective_signal": 1.0},
        }
        for operator in operators
    }
    monkeypatch.setenv("JOULE_FAKE_LLM_RESPONSE", json.dumps(fake_payload))
    target = _target("def target(values):\n    return len(values)\n")

    for operator in operators:
        results = operator.generate(target)
        assert len(results) == 1
        result = results[0]
        assert result.operator_name == operator.name
        assert result.metadata.get("objective") == operator.objective
        assert result.metadata.get("source") == "fake-env"
        assert result.metadata.get("skipped") is not True


def test_llm_candidate_structure_validator_rejects_disallowed_scope_edits(monkeypatch):
    operator = default_llm_operators("fake-model")[-1]
    fake_payload = {
        operator.name: {
            "candidate_source": "x = 1\n\ndef target(values):\n    return len(values)\n",
            "reasoning": "has disallowed scope edit",
            "dependencies": [],
            "proposal_rank": 0,
            "feature_hints": {},
        }
    }
    monkeypatch.setenv("JOULE_FAKE_LLM_RESPONSE", json.dumps(fake_payload))
    target = _target("def target(values):\n    return len(values)\n")

    result = operator.generate(target)[0]
    assert result.metadata.get("skipped") is True
    assert result.metadata.get("llm_invalid_structure") is True
    assert any(str(item).startswith("disallowed_top_level_statement") for item in result.metadata.get("validation_issues", []))


def test_llm_static_safety_lint_rejects_dynamic_execution(monkeypatch):
    operator = default_llm_operators("fake-model")[-1]
    fake_payload = {
        operator.name: {
            "candidate_source": "def target(values):\n    exec('print(1)')\n    return len(values)\n",
            "reasoning": "unsafe",
            "dependencies": [],
            "proposal_rank": 0,
            "feature_hints": {},
        }
    }
    monkeypatch.setenv("JOULE_FAKE_LLM_RESPONSE", json.dumps(fake_payload))
    target = _target("def target(values):\n    return len(values)\n")

    result = operator.generate(target)[0]
    assert result.metadata.get("skipped") is True
    assert result.metadata.get("llm_safety_lint_failed") is True
    assert any("dangerous_call_disallowed:exec" == item for item in result.metadata.get("validation_issues", []))

def test_llm_static_safety_lint_rejects_builtins_dynamic_execution(monkeypatch):
    operator = default_llm_operators("fake-model")[-1]
    fake_payload = {
        operator.name: {
            "candidate_source": "import builtins\n\ndef target(values):\n    builtins.exec('print(1)')\n    return len(values)\n",
            "reasoning": "unsafe via builtins",
            "dependencies": ["builtins"],
            "proposal_rank": 0,
            "feature_hints": {},
        }
    }
    monkeypatch.setenv("JOULE_FAKE_LLM_RESPONSE", json.dumps(fake_payload))
    target = _target("def target(values):\n    return len(values)\n")

    result = operator.generate(target)[0]
    assert result.metadata.get("skipped") is True
    assert result.metadata.get("llm_safety_lint_failed") is True
    assert any("dangerous_call_disallowed:builtins.exec" == item for item in result.metadata.get("validation_issues", []))

def test_llm_dependency_extraction_and_classification(monkeypatch):
    operator = default_llm_operators("fake-model")[-1]
    fake_payload = {
        operator.name: {
            "candidate_source": (
                "import numpy as np\n"
                "from collections import defaultdict\n\n"
                "def target(values):\n"
                "    groups = defaultdict(list)\n"
                "    for value in values:\n"
                "        groups[value % 2].append(value)\n"
                "    return np.array(groups[0]).size\n"
            ),
            "reasoning": "dependency extraction",
            "dependencies": ["numpy"],
            "proposal_rank": 0,
            "feature_hints": {},
        }
    }
    monkeypatch.setenv("JOULE_FAKE_LLM_RESPONSE", json.dumps(fake_payload))
    target = _target("def target(values):\n    return len(values)\n")

    result = operator.generate(target)[0]
    assert result.metadata.get("skipped") is not True
    assert result.dependencies == ["collections", "numpy"]
    assert result.metadata.get("dependency_extracted") == ["collections", "numpy"]
    assert result.metadata.get("dependency_declared") == ["numpy"]
    assert result.metadata.get("dependency_mismatch") is True
    classification = result.metadata.get("dependency_classification", {})
    assert classification.get("stdlib") == ["collections"]
    assert classification.get("external") == ["numpy"]


def test_llm_dependency_extraction_includes_function_local_imports(monkeypatch):
    operator = default_llm_operators("fake-model")[-1]
    fake_payload = {
        operator.name: {
            "candidate_source": (
                "def target(values):\n"
                "    import numpy as np\n"
                "    from collections import Counter\n"
                "    return int(np.array(values).size) + len(Counter(values))\n"
            ),
            "reasoning": "local imports",
            "dependencies": [],
            "proposal_rank": 0,
            "feature_hints": {},
        }
    }
    monkeypatch.setenv("JOULE_FAKE_LLM_RESPONSE", json.dumps(fake_payload))
    target = _target("def target(values):\n    return len(values)\n")

    result = operator.generate(target)[0]
    assert result.metadata.get("skipped") is not True
    assert result.dependencies == ["collections", "numpy"]
    assert result.metadata.get("dependency_extracted") == ["collections", "numpy"]
    assert result.metadata.get("dependency_declared") == []
    assert result.metadata.get("dependency_mismatch") is True
    classification = result.metadata.get("dependency_classification", {})
    assert classification.get("stdlib") == ["collections"]
    assert classification.get("external") == ["numpy"]


def test_sorted_reuse_llm_precheck_detects_repeated_sorted_calls():
    operator = next(item for item in default_llm_operators("fake-model") if item.name == "SortedReuseLLM")
    assert operator.precheck(
        _target(
            "def target(values):\n"
            "    a = sorted(values)\n"
            "    b = sorted(values)\n"
            "    return a, b\n"
        )
    )
    assert not operator.precheck(
        _target(
            "def target(values):\n"
            "    return sorted(values)\n"
        )
    )
