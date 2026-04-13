from __future__ import annotations

import ast
import hashlib
import math
from typing import cast
from typing import Literal
from typing import Any

import numpy as np

from joule.models import SearchContext, SearchPhase


_SUPPORTED_ACQUISITIONS = {"ei", "ucb", "thompson"}


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


class GaussianProcessSurrogate:
    def __init__(
        self,
        *,
        mode: str | None = None,
        acquisition: str = "ei",
        gp_noise: float = 1e-6,
        gp_length_scale: float = 1.0,
        gp_nu: float = 1.5,
        gp_ucb_beta: float = 1.0,
    ) -> None:
        _ = mode
        normalized_acquisition = acquisition.strip().lower()
        resolved_acquisition = (
            normalized_acquisition if normalized_acquisition in _SUPPORTED_ACQUISITIONS else "ei"
        )
        self.mode: Literal["gp"] = "gp"
        self.acquisition: Literal["ei", "ucb", "thompson"] = cast(
            Literal["ei", "ucb", "thompson"],
            resolved_acquisition,
        )
        self._gp_noise = max(float(gp_noise), 1e-9)
        self._gp_length_scale = max(float(gp_length_scale), 1e-6)
        self._gp_nu = 2.5 if float(gp_nu) > 1.5 else 1.5
        self._gp_ucb_beta = max(float(gp_ucb_beta), 1e-9)
        self._x: list[np.ndarray] = []
        self._y: list[float] = []
        self._source_to_index: dict[str, int] = {}

    def features(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> np.ndarray:
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
        hints = feature_hints or {}
        parent_len_delta = float(hints.get("parent_len_delta", 0.0))
        generation_depth = float(hints.get("generation_depth", 0.0))
        if context is not None:
            parent_len_delta = float(abs(len(source) - len(context.parent_source)))
            generation_depth = float(context.generation_depth)
        return np.array(
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
                parent_len_delta,
                generation_depth,
                float(hints.get("ast_shape_delta", 0.0)),
                float(hints.get("allocation_pattern_delta", 0.0)),
                float(hints.get("call_density_delta", 0.0)),
            ],
            dtype=float,
        )

    def record(
        self,
        source: str,
        score: float,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> None:
        features = self.features(source, feature_hints=feature_hints, context=context)
        if source in self._source_to_index:
            index = self._source_to_index[source]
            self._x[index] = features
            self._y[index] = float(score)
            return
        self._source_to_index[source] = len(self._x)
        self._x.append(features)
        self._y.append(float(score))

    def predict(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> tuple[float, float]:
        if not self._x:
            return 0.0, 1.0
        x = self.features(source, feature_hints=feature_hints, context=context)
        if len(self._y) >= 3:
            gp_mean, gp_std = self._predict_gp(x)
            if math.isfinite(gp_mean) and math.isfinite(gp_std):
                return gp_mean, max(gp_std, 1e-6)
        return self._predict_local(x)

    def novelty(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> float:
        if not self._x:
            return 1.0
        x = self.features(source, feature_hints=feature_hints, context=context)
        x_train = np.vstack(self._x)
        distances = np.linalg.norm(x_train - x, axis=1)
        nearest = float(distances.min())
        spread = float(np.mean(distances)) if len(distances) else 1.0
        if spread <= 1e-9:
            return 0.0 if nearest <= 1e-9 else 1.0
        return max(0.0, min(1.0, nearest / (spread + 1e-9)))

    def screen_candidate(
        self,
        *,
        source: str,
        best_score: float,
        phase: SearchPhase,
        min_novelty: float,
        min_training_points: int,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> dict[str, Any]:
        novelty = self.novelty(source, feature_hints=feature_hints, context=context)
        mean, uncertainty = self.predict(source, feature_hints=feature_hints, context=context)
        expected_improvement = max(0.0, best_score - mean)
        acquisition_score = self._acquisition_score(
            source=source,
            best_score=best_score,
            mean=mean,
            uncertainty=uncertainty,
            expected_improvement=expected_improvement,
        )
        exploration_weight = {
            SearchPhase.EXPLORATION: 1.0,
            SearchPhase.EXPLOITATION: 0.6,
            SearchPhase.CONFIRMATION: 0.3,
        }[phase]
        acquisition_score = max(acquisition_score, expected_improvement + (exploration_weight * uncertainty))
        decision = "escalate"
        reason = ""
        if novelty < min_novelty:
            decision = "reject"
            reason = "low_novelty"
        elif len(self._y) < min_training_points:
            decision = "escalate"
            reason = "insufficient_training"
        elif acquisition_score <= 0.0 and uncertainty < 0.10:
            decision = "reject"
            reason = "low_value_of_information"
        elif phase is SearchPhase.CONFIRMATION and acquisition_score < 0.03:
            decision = "measure_partial"
            reason = "low_confirmation_value"
        elif expected_improvement < 0.01 and uncertainty < 0.20:
            decision = "measure_partial"
            reason = "uncertain_small_gain"
        return {
            "decision": decision,
            "reason": reason,
            "predicted_score": mean,
            "uncertainty": uncertainty,
            "novelty": novelty,
            "acquisition_score": acquisition_score,
            "expected_improvement": expected_improvement,
            "model_mode": self.mode,
            "acquisition": self.acquisition,
        }

    def _predict_local(self, x: np.ndarray) -> tuple[float, float]:
        x_train = np.vstack(self._x)
        y_train = np.array(self._y, dtype=float)
        distances = np.linalg.norm(x_train - x, axis=1)
        scale = float(np.median(distances)) if len(distances) else 1.0
        bandwidth = max(1e-6, scale)
        weights = np.exp(-(distances**2) / (2.0 * (bandwidth**2)))
        if float(weights.sum()) == 0.0:
            return float(y_train.mean()), float(y_train.std() if len(y_train) > 1 else 1.0)
        mean = float(np.dot(weights, y_train) / weights.sum())
        variance = float(np.average((y_train - mean) ** 2, weights=weights)) if len(y_train) > 1 else 1.0
        return mean, math.sqrt(max(variance, 1e-6))

    def _predict_gp(self, x: np.ndarray) -> tuple[float, float]:
        x_train = np.vstack(self._x)
        y_train = np.array(self._y, dtype=float)
        if len(y_train) == 1:
            return float(y_train[0]), 1.0

        y_mean = float(np.mean(y_train))
        y_std = float(np.std(y_train))
        y_scale = y_std if y_std > 1e-9 else 1.0
        y_norm = (y_train - y_mean) / y_scale

        length_scale = self._adaptive_length_scale(x_train)
        kernel = self._matern_kernel(x_train, x_train, length_scale=length_scale)
        jitter_schedule = (self._gp_noise, 1e-6, 1e-5, 1e-4, 1e-3)

        for jitter in jitter_schedule:
            stabilized = kernel + (np.eye(len(x_train)) * jitter)
            try:
                chol = np.linalg.cholesky(stabilized)
                alpha = np.linalg.solve(chol.T, np.linalg.solve(chol, y_norm))
                k_star = self._matern_kernel(x_train, x.reshape(1, -1), length_scale=length_scale).reshape(-1)
                mean_norm = float(k_star @ alpha)

                v = np.linalg.solve(chol, k_star)
                k_self = float(self._matern_kernel(x.reshape(1, -1), x.reshape(1, -1), length_scale=length_scale)[0, 0])
                variance_norm = max(k_self - float(v @ v), 1e-9)
                mean = y_mean + (y_scale * mean_norm)
                uncertainty = abs(y_scale) * math.sqrt(variance_norm)
                return float(mean), float(uncertainty)
            except np.linalg.LinAlgError:
                continue
        return self._predict_local(x)

    def _adaptive_length_scale(self, x_train: np.ndarray) -> float:
        if len(x_train) < 2:
            return self._gp_length_scale
        diffs = x_train[:, None, :] - x_train[None, :, :]
        distances = np.linalg.norm(diffs, axis=2)
        tri_upper = distances[np.triu_indices(len(x_train), k=1)]
        non_zero = tri_upper[tri_upper > 1e-9]
        if non_zero.size == 0:
            return self._gp_length_scale
        median_distance = float(np.median(non_zero))
        return max(self._gp_length_scale, median_distance)

    def _matern_kernel(self, left: np.ndarray, right: np.ndarray, *, length_scale: float) -> np.ndarray:
        scale = max(length_scale, 1e-6)
        deltas = (left[:, None, :] - right[None, :, :]) / scale
        distances = np.linalg.norm(deltas, axis=2)
        if self._gp_nu <= 1.5:
            root3 = math.sqrt(3.0)
            return (1.0 + (root3 * distances)) * np.exp(-root3 * distances)
        root5 = math.sqrt(5.0)
        return (1.0 + (root5 * distances) + ((5.0 / 3.0) * (distances**2))) * np.exp(-root5 * distances)

    def _expected_improvement(self, *, best_score: float, mean: float, uncertainty: float) -> float:
        sigma = max(uncertainty, 1e-9)
        improvement = best_score - mean
        z_score = improvement / sigma
        return max(0.0, (improvement * _normal_cdf(z_score)) + (sigma * _normal_pdf(z_score)))

    def _thompson_improvement(self, *, source: str, best_score: float, mean: float, uncertainty: float) -> float:
        sigma = max(uncertainty, 1e-9)
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        seed = int(digest[:16], 16) % (2**32)
        sample = float(np.random.default_rng(seed).normal(loc=mean, scale=sigma))
        return max(0.0, best_score - sample)

    def _acquisition_score(
        self,
        *,
        source: str,
        best_score: float,
        mean: float,
        uncertainty: float,
        expected_improvement: float,
    ) -> float:
        if self.acquisition == "ucb":
            return max(0.0, (best_score - mean) + (self._gp_ucb_beta * uncertainty))
        if self.acquisition == "thompson":
            return self._thompson_improvement(
                source=source,
                best_score=best_score,
                mean=mean,
                uncertainty=uncertainty,
            )
        return self._expected_improvement(best_score=best_score, mean=mean, uncertainty=uncertainty)
