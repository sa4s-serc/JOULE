from __future__ import annotations

import ast
import hashlib
from collections import OrderedDict

import numpy as np

from joule.models import SearchContext
from joule.surrogate.types import FEATURE_SCHEMA_VERSION


class SourceFeatureExtractor:
    def __init__(self, *, cache_size: int = 2048) -> None:
        self.schema_version = FEATURE_SCHEMA_VERSION
        self._cache_size = max(64, int(cache_size))
        self._base_cache: OrderedDict[str, np.ndarray] = OrderedDict()

    def features(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> np.ndarray:
        base_features = self._base_features(source)
        hints = feature_hints or {}
        parent_len_delta = float(hints.get("parent_len_delta", 0.0))
        generation_depth = float(hints.get("generation_depth", 0.0))
        if context is not None:
            parent_len_delta = float(abs(len(source) - len(context.parent_source)))
            generation_depth = float(context.generation_depth)
        dynamic = np.array(
            [
                parent_len_delta,
                generation_depth,
                float(hints.get("ast_shape_delta", 0.0)),
                float(hints.get("allocation_pattern_delta", 0.0)),
                float(hints.get("call_density_delta", 0.0)),
            ],
            dtype=float,
        )
        return np.concatenate((base_features, dynamic))

    def source_hash(self, source: str) -> str:
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    def _base_features(self, source: str) -> np.ndarray:
        source_hash = self.source_hash(source)
        cached = self._base_cache.get(source_hash)
        if cached is not None:
            self._base_cache.move_to_end(source_hash)
            return cached
        try:
            tree = ast.parse(source)
            nodes = list(ast.walk(tree))
        except SyntaxError:
            nodes = []
        node_count = len(nodes)
        loop_count = sum(isinstance(node, (ast.For, ast.While, ast.comprehension)) for node in nodes)
        comp_count = sum(isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) for node in nodes)
        call_count = sum(isinstance(node, ast.Call) for node in nodes)
        branch_count = sum(isinstance(node, (ast.If, ast.Match, ast.IfExp)) for node in nodes)
        assign_count = sum(isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)) for node in nodes)
        container_count = sum(isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)) for node in nodes)
        literal_count = sum(isinstance(node, ast.Constant) for node in nodes)
        subscript_count = sum(isinstance(node, ast.Subscript) for node in nodes)
        lambda_count = sum(isinstance(node, ast.Lambda) for node in nodes)
        function_count = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in nodes)
        try_count = sum(isinstance(node, ast.Try) for node in nodes)
        compare_count = sum(isinstance(node, ast.Compare) for node in nodes)
        return_count = sum(isinstance(node, ast.Return) for node in nodes)
        annotated_assign_count = sum(isinstance(node, ast.AnnAssign) for node in nodes)
        annotation_density = float(annotated_assign_count) / max(1.0, float(node_count))
        branch_density = float(branch_count) / max(1.0, float(node_count))
        base = np.array(
            [
                float(len(source)),
                float(node_count),
                float(loop_count),
                float(comp_count),
                float(call_count),
                float(branch_count),
                float(assign_count),
                float(container_count),
                float(literal_count),
                float(subscript_count),
                float(lambda_count),
                float(function_count),
                float(try_count),
                float(compare_count),
                float(return_count),
                annotation_density,
                branch_density,
            ],
            dtype=float,
        )
        self._base_cache[source_hash] = base
        self._base_cache.move_to_end(source_hash)
        while len(self._base_cache) > self._cache_size:
            self._base_cache.popitem(last=False)
        return base
