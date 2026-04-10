from __future__ import annotations

import ast

from joule.models import TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class ContainerMembershipOperator(BaseOperator):
    name = "container_membership"
    family = "deterministic"

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_Compare(self, node: ast.Compare):
                nonlocal changed
                self.generic_visit(node)
                if len(node.ops) != 1 or not isinstance(node.ops[0], ast.In):
                    return node
                comparator = node.comparators[0]
                if isinstance(comparator, (ast.List, ast.Tuple)) and len(comparator.elts) > 3:
                    if all(isinstance(item, ast.Constant) for item in comparator.elts):
                        changed = True
                        return ast.copy_location(
                            ast.Compare(
                                left=node.left,
                                ops=node.ops,
                                comparators=[ast.Set(elts=comparator.elts)],
                            ),
                            node,
                        )
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            TransformationResult(
                operator_name=self.name,
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced repeated linear membership checks with a set literal for faster lookups.",
                operator_family=self.family,
                proposal_rank=0,
            )
        ]


class SumListComprehensionOperator(BaseOperator):
    name = "sum_generator"
    family = "deterministic"

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_Call(self, node: ast.Call):
                nonlocal changed
                self.generic_visit(node)
                if isinstance(node.func, ast.Name) and node.func.id == "sum" and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.ListComp):
                        changed = True
                        node.args[0] = ast.GeneratorExp(
                            elt=first.elt,
                            generators=first.generators,
                        )
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            TransformationResult(
                operator_name=self.name,
                candidate_source=ast.unparse(new_tree),
                reasoning="Converted list materialization inside sum() into a generator to reduce memory pressure.",
                operator_family=self.family,
                proposal_rank=0,
            )
        ]


class EmptyLiteralOperator(BaseOperator):
    name = "empty_literal"
    family = "deterministic"

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_Call(self, node: ast.Call):
                nonlocal changed
                self.generic_visit(node)
                if isinstance(node.func, ast.Name) and not node.args and not node.keywords:
                    if node.func.id == "list":
                        changed = True
                        return ast.List(elts=[], ctx=ast.Load())
                    if node.func.id == "dict":
                        changed = True
                        return ast.Dict(keys=[], values=[])
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            TransformationResult(
                operator_name=self.name,
                candidate_source=ast.unparse(new_tree),
                reasoning="Replaced zero-argument constructor calls with literal forms.",
                operator_family=self.family,
                proposal_rank=0,
            )
        ]


def default_deterministic_operators() -> list[BaseOperator]:
    return [
        ContainerMembershipOperator(),
        SumListComprehensionOperator(),
        EmptyLiteralOperator(),
    ]
