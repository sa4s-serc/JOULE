from __future__ import annotations

import math

import numpy as np

from joule.config import JouleSettings, ParetoWeights
from joule.models import SearchContext, SearchPhase
from joule.surrogate.features import SourceFeatureExtractor
from joule.surrogate.models import SurrogateModel, SurrogateModelError
from joule.surrogate.registry import SurrogateRegistry
from joule.surrogate.types import (
    METRIC_NAMES,
    MetricPrediction,
    SurrogateMetricTargets,
    SurrogateObservation,
    SurrogatePrediction,
    SurrogateQuery,
    SurrogateScreeningDecision,
)


_SUPPORTED_ACQUISITIONS = {"ei", "ucb", "thompson"}


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


def weighted_objective_from_targets(
    targets: SurrogateMetricTargets,
    weights: tuple[float, float, float],
) -> float:
    return (
        (float(targets.energy) * float(weights[0]))
        + (float(targets.latency) * float(weights[1]))
        + ((float(targets.memory) / (1024 * 1024)) * float(weights[2]))
    )


def weighted_objective_uncertainty(
    uncertainties: SurrogateMetricTargets,
    weights: tuple[float, float, float],
) -> float:
    return math.sqrt(
        ((float(weights[0]) * float(uncertainties.energy)) ** 2)
        + ((float(weights[1]) * float(uncertainties.latency)) ** 2)
        + (((float(weights[2]) * float(uncertainties.memory)) / (1024 * 1024)) ** 2)
    )


class ObjectiveSurrogate:
    def __init__(
        self,
        *,
        settings: JouleSettings,
        weights: ParetoWeights,
        registry: SurrogateRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.weights = weights.as_tuple()
        self.model_kind = settings.surrogate.model
        self.fallback_model_kind = settings.surrogate.fallback_model
        self.objective_kind = settings.surrogate.objective
        self.screening_kind = settings.surrogate.screening
        normalized_acquisition = settings.surrogate.acquisition.strip().lower()
        self.acquisition = normalized_acquisition if normalized_acquisition in _SUPPORTED_ACQUISITIONS else "ei"
        self.ucb_beta = max(float(settings.surrogate.ucb_beta), 1e-9)
        self._max_observations = max(3, int(settings.surrogate.max_observations))
        self._extractor = SourceFeatureExtractor(cache_size=settings.surrogate.feature_cache_size)
        self._registry = registry or SurrogateRegistry()
        self._primary_model = self._registry.create(self.model_kind, settings)
        self._fallback_model: SurrogateModel | None = None
        if self.fallback_model_kind != self.model_kind:
            self._fallback_model = self._registry.create(self.fallback_model_kind, settings)
        self._features: list[np.ndarray] = []
        self._targets: list[SurrogateMetricTargets] = []
        self._source_hashes: list[str] = []
        self._source_hash_to_index: dict[str, int] = {}
        self._training_revision = 0

    @property
    def feature_schema_version(self) -> int:
        return self._extractor.schema_version

    def describe(self) -> dict[str, object]:
        return {
            "model": self.model_kind,
            "fallback_model": self.fallback_model_kind,
            "objective": self.objective_kind,
            "screening": self.screening_kind,
            "acquisition": self.acquisition,
            "objective_weights": list(self.weights),
            "feature_schema_version": self.feature_schema_version,
            "max_observations": self._max_observations,
        }

    def features(
        self,
        source: str,
        *,
        feature_hints: dict[str, float] | None = None,
        context: SearchContext | None = None,
    ) -> np.ndarray:
        return self._extractor.features(source, feature_hints=feature_hints, context=context)

    def record(self, observation: SurrogateObservation, *, context: SearchContext | None = None) -> None:
        features = self.features(observation.source, feature_hints=observation.feature_hints, context=context)
        source_hash = self._extractor.source_hash(observation.source)
        if source_hash in self._source_hash_to_index:
            index = self._source_hash_to_index[source_hash]
            self._features[index] = features
            self._targets[index] = observation.targets
            self._training_revision += 1
            return
        self._source_hash_to_index[source_hash] = len(self._features)
        self._source_hashes.append(source_hash)
        self._features.append(features)
        self._targets.append(observation.targets)
        if len(self._features) > self._max_observations:
            self._features.pop(0)
            self._targets.pop(0)
            self._source_hashes.pop(0)
            self._source_hash_to_index = {
                item_hash: idx for idx, item_hash in enumerate(self._source_hashes)
            }
        self._training_revision += 1

    def predict(self, query: SurrogateQuery, *, context: SearchContext | None = None) -> SurrogatePrediction:
        if not self._features:
            zero_metrics = {
                metric: MetricPrediction(mean=0.0, uncertainty=1.0)
                for metric in METRIC_NAMES
            }
            return SurrogatePrediction(
                metrics=zero_metrics,
                predicted_score=0.0,
                uncertainty=weighted_objective_uncertainty(
                    SurrogateMetricTargets(energy=1.0, latency=1.0, memory=1.0),
                    self.weights,
                ),
                model_kind=self.model_kind,
                fallback_used=False,
            )
        x_query = self.features(query.source, feature_hints=query.feature_hints, context=context)
        x_train = np.vstack(self._features)
        y_train = {
            "energy": np.array([targets.energy for targets in self._targets], dtype=float),
            "latency": np.array([targets.latency for targets in self._targets], dtype=float),
            "memory": np.array([targets.memory for targets in self._targets], dtype=float),
        }
        used_fallback = False
        try:
            predictions = self._primary_model.predict(
                x_train=x_train,
                y_train=y_train,
                x_query=x_query,
                training_revision=self._training_revision,
            )
            model_kind = self._primary_model.kind
        except Exception as exc:
            if self._fallback_model is None:
                raise SurrogateModelError(str(exc)) from exc
            predictions = self._fallback_model.predict(
                x_train=x_train,
                y_train=y_train,
                x_query=x_query,
                training_revision=self._training_revision,
            )
            model_kind = self._fallback_model.kind
            used_fallback = True
        metric_means = SurrogateMetricTargets(
            energy=float(predictions["energy"].mean),
            latency=float(predictions["latency"].mean),
            memory=float(predictions["memory"].mean),
        )
        metric_uncertainties = SurrogateMetricTargets(
            energy=float(predictions["energy"].uncertainty),
            latency=float(predictions["latency"].uncertainty),
            memory=float(predictions["memory"].uncertainty),
        )
        return SurrogatePrediction(
            metrics=predictions,
            predicted_score=weighted_objective_from_targets(metric_means, self.weights),
            uncertainty=weighted_objective_uncertainty(metric_uncertainties, self.weights),
            model_kind=model_kind,
            fallback_used=used_fallback,
        )

    def novelty(self, query: SurrogateQuery, *, context: SearchContext | None = None) -> float:
        if not self._features:
            return 1.0
        x = self.features(query.source, feature_hints=query.feature_hints, context=context)
        x_train = np.vstack(self._features)
        distances = np.linalg.norm(x_train - x, axis=1)
        nearest = float(distances.min())
        spread = float(np.mean(distances)) if len(distances) else 1.0
        if spread <= 1e-9:
            return 0.0 if nearest <= 1e-9 else 1.0
        return max(0.0, min(1.0, nearest / (spread + 1e-9)))

    def screen_candidate(
        self,
        *,
        query: SurrogateQuery,
        best_score: float,
        phase: SearchPhase,
        min_novelty: float,
        min_training_points: int,
        context: SearchContext | None = None,
    ) -> SurrogateScreeningDecision:
        novelty = self.novelty(query, context=context)
        prediction = self.predict(query, context=context)
        expected_improvement = max(0.0, best_score - prediction.predicted_score)
        acquisition_score = self._acquisition_score(
            source=query.source,
            best_score=best_score,
            mean=prediction.predicted_score,
            uncertainty=prediction.uncertainty,
            expected_improvement=expected_improvement,
        )
        exploration_weight = {
            SearchPhase.EXPLORATION: 1.0,
            SearchPhase.EXPLOITATION: 0.6,
            SearchPhase.CONFIRMATION: 0.3,
        }[phase]
        acquisition_score = max(acquisition_score, expected_improvement + (exploration_weight * prediction.uncertainty))
        decision = "escalate"
        reason = ""
        if novelty < min_novelty:
            decision = "reject"
            reason = "low_novelty"
        elif len(self._targets) < min_training_points:
            decision = "escalate"
            reason = "insufficient_training"
        elif acquisition_score <= 0.0 and prediction.uncertainty < 0.10:
            decision = "reject"
            reason = "low_value_of_information"
        elif phase is SearchPhase.CONFIRMATION and acquisition_score < 0.03:
            decision = "measure_partial"
            reason = "low_confirmation_value"
        elif expected_improvement < 0.01 and prediction.uncertainty < 0.20:
            decision = "measure_partial"
            reason = "uncertain_small_gain"
        return SurrogateScreeningDecision(
            decision=decision,
            reason=reason,
            predicted_score=prediction.predicted_score,
            uncertainty=prediction.uncertainty,
            novelty=novelty,
            acquisition_score=acquisition_score,
            expected_improvement=expected_improvement,
            model_kind=prediction.model_kind,
            acquisition=self.acquisition,
            objective_kind=self.objective_kind,
            objective_weights=self.weights,
            predicted_metrics=prediction.metric_means(),
            metric_uncertainties=prediction.metric_uncertainties(),
            phase=phase,
        )

    def _thompson_improvement(self, *, source: str, best_score: float, mean: float, uncertainty: float) -> float:
        sigma = max(uncertainty, 1e-9)
        digest = self._extractor.source_hash(source)
        seed = int(digest[:16], 16) % (2**32)
        sample = float(np.random.default_rng(seed).normal(loc=mean, scale=sigma))
        return max(0.0, best_score - sample)

    def _expected_improvement(self, *, best_score: float, mean: float, uncertainty: float) -> float:
        sigma = max(uncertainty, 1e-9)
        improvement = best_score - mean
        z_score = improvement / sigma
        return max(0.0, (improvement * _normal_cdf(z_score)) + (sigma * _normal_pdf(z_score)))

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
            return max(0.0, (best_score - mean) + (self.ucb_beta * uncertainty))
        if self.acquisition == "thompson":
            return self._thompson_improvement(
                source=source,
                best_score=best_score,
                mean=mean,
                uncertainty=uncertainty,
            )
        return self._expected_improvement(best_score=best_score, mean=mean, uncertainty=uncertainty)
