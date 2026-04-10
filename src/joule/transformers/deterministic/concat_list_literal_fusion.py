from __future__ import annotations

import ast

from joule.models import Tier, TargetSpec, TransformationResult
from joule.transformers.base import BaseOperator


class ConcatListLiteralFusion(BaseOperator):
    name = "ConcatListLiteralFusion"
    family = "deterministic"
    tier = Tier.L
    precheck_node_types = (ast.BinOp,)

    def generate(self, target: TargetSpec, context=None) -> list[TransformationResult]:
        del context
        tree = ast.parse(target.source)
        changed = False

        class Rewriter(ast.NodeTransformer):
            def visit_BinOp(self, node: ast.BinOp):
                nonlocal changed
                self.generic_visit(node)
                if isinstance(node.op, ast.Add) and isinstance(node.left, ast.List) and isinstance(node.right, ast.List):
                    changed = True
                    return ast.List(elts=[*node.left.elts, *node.right.elts], ctx=ast.Load())
                return node

        new_tree = Rewriter().visit(tree)
        ast.fix_missing_locations(new_tree)
        if not changed:
            return []
        return [
            self.build_result(
                candidate_source=ast.unparse(new_tree),
                reasoning="Merged concatenated list literals into a single literal.",
            )
        ]
