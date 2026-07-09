from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Callable
import sys
from typing import Any, ClassVar

from joule.integrations.llm import LLMClient, LLMUnavailableError
from joule.models import SearchContext, TargetSpec, Tier, TransformationResult
from joule.transformers.base import BaseOperator


def _stable_dump(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=False, include_attributes=False)


def _loop_contains_nested_loop(node: ast.AST) -> bool:
    return any(isinstance(child, (ast.For, ast.While)) for child in ast.walk(node) if child is not node)


def _function_has_recursive_call(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    return any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == node.name for call in ast.walk(node))


def _function_has_repeated_calls(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    calls = [
        _stable_dump(call.func)
        for call in ast.walk(node)
        if isinstance(call, ast.Call)
    ]
    if not calls:
        return False
    return any(count > 1 for count in Counter(calls).values())


def _if_has_dict_double_hash_pattern(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.In)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Name)
    ):
        return False
    mapping_name = test.comparators[0].id
    key_dump = _stable_dump(test.left)
    for stmt in node.body:
        for child in ast.walk(stmt):
            if isinstance(child, ast.Subscript) and isinstance(child.value, ast.Name) and child.value.id == mapping_name:
                if _stable_dump(child.slice) == key_dump:
                    return True
    return False


def _loop_has_membership_check(node: ast.AST) -> bool:
    if not isinstance(node, (ast.For, ast.While)):
        return False
    return any(
        isinstance(child, ast.Compare)
        and len(child.ops) == 1
        and isinstance(child.ops[0], (ast.In, ast.NotIn))
        and len(child.comparators) == 1
        and isinstance(child.comparators[0], ast.Name)
        for child in ast.walk(node)
    )


def _loop_has_early_exit(node: ast.AST) -> bool:
    if not isinstance(node, (ast.For, ast.While)):
        return False
    for child in ast.walk(node):
        if isinstance(child, ast.If):
            if any(isinstance(stmt, (ast.Return, ast.Break, ast.Continue)) for stmt in child.body):
                return True
    return False


def _loop_without_early_exit(node: ast.AST) -> bool:
    if not isinstance(node, (ast.For, ast.While)):
        return False
    return not _loop_has_early_exit(node)


def _eager_materialisation_precheck(node: ast.AST) -> bool:
    if isinstance(node, ast.ListComp):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"list", "set", "dict", "tuple"}:
        return True
    return False


def _call_has_generator_chain(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return any(isinstance(arg, (ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)) for arg in node.args)


def _loop_invariant_precheck(node: ast.AST) -> bool:
    return isinstance(node, (ast.For, ast.While)) and any(isinstance(child, (ast.Call, ast.Attribute)) for child in ast.walk(node) if child is not node)


def _loop_has_append_call(node: ast.AST) -> bool:
    if not isinstance(node, (ast.For, ast.While)):
        return False
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute) and child.func.attr == "append":
            return True
    return False


def _loop_has_augassign_reduction(node: ast.AST) -> bool:
    if not isinstance(node, (ast.For, ast.While)):
        return False
    return any(
        isinstance(child, ast.AugAssign)
        and isinstance(child.target, ast.Name)
        and isinstance(child.op, (ast.Add, ast.Mult, ast.BitOr, ast.BitAnd))
        for child in ast.walk(node)
    )


def _math_to_bitwise_candidate(node: ast.AST) -> bool:
    if not isinstance(node, ast.BinOp):
        return False
    if isinstance(node.op, (ast.Mult, ast.FloorDiv)) and isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
        value = int(node.right.value)
        return value > 0 and (value & (value - 1)) == 0
    return False


def _regex_runtime_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "re":
        return node.func.attr in {"search", "match", "fullmatch", "findall", "sub", "split"} and bool(node.args)
    return False


def _seen_set_dedup_pattern(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not (
        isinstance(test, ast.Compare)
        and len(test.ops) == 1
        and isinstance(test.ops[0], ast.NotIn)
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Name)
    ):
        return False
    if len(node.body) != 1:
        return False
    stmt = node.body[0]
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Attribute)
        and stmt.value.func.attr == "append"
    )


def _class_without_slots(node: ast.AST) -> bool:
    if not isinstance(node, ast.ClassDef):
        return False
    has_slots = any(
        isinstance(stmt, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__slots__" for target in stmt.targets)
        for stmt in node.body
    )
    if has_slots:
        return False
    for stmt in node.body:
        if isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__":
            if any(
                isinstance(child, ast.Assign)
                and any(
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    for target in child.targets
                )
                for child in ast.walk(stmt)
            ):
                return True
    return False


def _try_except_fast_path_candidate(node: ast.AST) -> bool:
    if not isinstance(node, ast.Try):
        return False
    return any(handler.type is None for handler in node.handlers)


def _loop_arithmetic_candidate(node: ast.AST) -> bool:
    if not isinstance(node, (ast.For, ast.While)):
        return False
    return any(isinstance(child, ast.BinOp) for child in ast.walk(node)) and _loop_has_append_call(node)


def _naive_search_candidate(node: ast.AST) -> bool:
    return isinstance(node, (ast.For, ast.While)) and _loop_contains_nested_loop(node)


def _always_true(_node: ast.AST) -> bool:
    return True


def _is_docstring_stmt(stmt: ast.stmt, *, index: int) -> bool:
    return (
        index == 0
        and isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Constant)
        and isinstance(stmt.value.value, str)
    )


def _normalize_dependencies(values: list[str]) -> list[str]:
    normalized = {str(value).strip().split(".", 1)[0] for value in values if str(value).strip()}
    return sorted(normalized)


def _extract_import_dependencies(module: ast.Module) -> list[str]:
    roots: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module is None or node.module == "__future__":
                continue
            roots.add(node.module.split(".", 1)[0])
    return sorted(roots)


def _classify_dependencies(roots: list[str]) -> dict[str, list[str]]:
    stdlib = sorted([item for item in roots if item in sys.stdlib_module_names])
    external = sorted([item for item in roots if item not in sys.stdlib_module_names])
    return {"stdlib": stdlib, "external": external}


def _candidate_structure_issues(module: ast.Module, target: TargetSpec) -> list[str]:
    issues: list[str] = []
    function_defs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for index, stmt in enumerate(module.body):
        if _is_docstring_stmt(stmt, index=index):
            continue
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_defs.append(stmt)
            continue
        if isinstance(stmt, ast.Import):
            continue
        if isinstance(stmt, ast.ImportFrom):
            if stmt.level != 0:
                issues.append("relative_import_disallowed")
            if any(alias.name == "*" for alias in stmt.names):
                issues.append("wildcard_import_disallowed")
            continue
        issues.append(f"disallowed_top_level_statement:{type(stmt).__name__}")

    matching = [item for item in function_defs if item.name == target.function_name]
    if len(matching) != 1:
        issues.append("target_function_must_exist_exactly_once")
    if any(item.name != target.function_name for item in function_defs):
        issues.append("extra_function_definitions_disallowed")
    if matching:
        candidate_function = matching[0]
        if target.is_async and not isinstance(candidate_function, ast.AsyncFunctionDef):
            issues.append("target_async_mismatch")
        if not target.is_async and isinstance(candidate_function, ast.AsyncFunctionDef):
            issues.append("target_sync_mismatch")
    return sorted(set(issues))


def _static_safety_issues(module: ast.Module) -> list[str]:
    def dynamic_call_name(node: ast.Call) -> str | None:
        if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec", "compile", "__import__"}:
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in {"eval", "exec", "compile", "__import__"} and isinstance(node.func.value, ast.Name):
                if node.func.value.id in {"builtins", "__builtins__"}:
                    return f"{node.func.value.id}.{node.func.attr}"
            if isinstance(node.func.value, ast.Name):
                if node.func.value.id == "subprocess":
                    return f"subprocess.{node.func.attr}"
                if node.func.value.id == "os" and node.func.attr in {"system", "popen", "execv", "execve", "spawnl", "spawnle", "fork", "removedirs", "remove", "rmdir", "rename", "renames"}:
                    return f"os.{node.func.attr}"
        return None

    def dangerous_decorator(node: ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef) -> str | None:
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id == "property":
                return "property"
            if isinstance(dec, ast.Attribute) and dec.attr in {"setter", "deleter"}:
                return dec.attr
        return None

    issues: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Call):
            name = dynamic_call_name(node)
            if name is not None:
                issues.add(f"dangerous_call_disallowed:{name}")
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            dec_name = dangerous_decorator(node)
            if dec_name is not None:
                issues.add(f"dangerous_decorator_disallowed:{dec_name}")
        if isinstance(node, ast.Global):
            issues.add("global_statement_disallowed")
        if isinstance(node, ast.Nonlocal):
            issues.add("nonlocal_statement_disallowed")
    return sorted(issues)


class LLMTransformationOperator(BaseOperator):
    family: ClassVar[str] = "llm"
    tier: ClassVar[Tier] = Tier.M
    objective: ClassVar[str] = "Generate a semantics-preserving optimization candidate."
    precheck_node_types: ClassVar[tuple[type[ast.AST], ...]] = (ast.For, ast.While, ast.Call, ast.If, ast.BinOp)
    precheck_predicate: ClassVar[Callable[[ast.AST], bool]] = _always_true

    def __init__(self, model: str) -> None:
        self.client = LLMClient(model=model)

    def _precheck_node(self, node: ast.AST) -> bool:
        return type(self).precheck_predicate(node)

    def _skipped_result(
        self,
        *,
        target: TargetSpec,
        reasoning: str,
        metadata: dict[str, Any],
    ) -> list[TransformationResult]:
        return [
            self.build_result(
                candidate_source=target.source,
                reasoning=reasoning,
                proposal_rank=100,
                metadata={"skipped": True, **metadata},
            )
        ]

    def generate(self, target: TargetSpec, context: SearchContext | None = None) -> list[TransformationResult]:
        try:
            generated = self.client.generate_transformation(
                target,
                context,
                operator_name=self.name,
                objective=self.objective,
                operator_tier=self.tier,
            )
        except LLMUnavailableError as exc:
            return self._skipped_result(target=target, reasoning=str(exc), metadata={"llm_unavailable": True})
        except (RuntimeError, ValueError, SyntaxError) as exc:
            return self._skipped_result(
                target=target,
                reasoning=f"LLM generation failed: {exc}",
                metadata={"llm_error": True},
            )

        candidate = generated.candidate_source.strip()
        if not candidate:
            return self._skipped_result(
                target=target,
                reasoning="LLM returned an empty candidate.",
                metadata={"llm_invalid_output": True},
            )

        try:
            module = ast.parse(generated.candidate_source)
        except SyntaxError as exc:
            return self._skipped_result(
                target=target,
                reasoning=f"LLM candidate failed syntax validation: {exc.msg}",
                metadata={"llm_invalid_syntax": True},
            )

        if not isinstance(module, ast.Module):
            return self._skipped_result(
                target=target,
                reasoning="LLM candidate must parse to a module.",
                metadata={"llm_invalid_structure": True},
            )

        structure_issues = _candidate_structure_issues(module, target)
        lint_issues = _static_safety_issues(module)
        if structure_issues or lint_issues:
            issues = [*structure_issues, *lint_issues]
            return self._skipped_result(
                target=target,
                reasoning="LLM candidate failed structural safety validation.",
                metadata={
                    "llm_invalid_structure": bool(structure_issues),
                    "llm_safety_lint_failed": bool(lint_issues),
                    "validation_issues": issues,
                },
            )

        extracted_dependencies = _extract_import_dependencies(module)
        declared_dependencies = _normalize_dependencies(generated.dependencies)
        dependencies = sorted(set([*extracted_dependencies, *declared_dependencies]))
        classification = _classify_dependencies(dependencies)
        
        # Verify external dependencies are resolvable
        import importlib.util
        for ext_dep in classification["external"]:
            if ext_dep and getattr(importlib.util, "find_spec", None) is not None:
                try:
                    if importlib.util.find_spec(ext_dep) is None:
                        return self._skipped_result(
                            target=target,
                            reasoning=f"LLM generated unresolvable external dependency: {ext_dep}",
                            metadata={"unresolvable_dependency": ext_dep}
                        )
                except Exception:
                    pass

        dependency_mismatch = set(extracted_dependencies) != set(declared_dependencies)

        generated.dependencies = dependencies
        generated.metadata.update(
            {
                "dependency_extracted": extracted_dependencies,
                "dependency_declared": declared_dependencies,
                "dependency_mismatch": dependency_mismatch,
                "dependency_classification": classification,
                "ownership_expected": list(target.owner_path),
                "validation_issues": [],
            }
        )

        generated.operator_name = self.name
        generated.operator_family = self.family
        generated.operator_tier = self.tier
        generated.metadata.setdefault("operator_tier", self.tier.value)
        generated.metadata.setdefault("operator_tier_descriptor", self.tier_description())
        return [generated]
