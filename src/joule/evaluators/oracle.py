from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from pathlib import Path
import tempfile

from joule.config import JouleSettings
from joule.evaluators.backends import MockEnergyBackend, RaplEnergyBackend
from joule.evaluators.correctness import _materialize_overlay
from joule.runtime import invoke_profile_worker
from joule.models import CalibrationResult, Fidelity, MeasurementReport, MetricSample, TargetSpec, WorkloadBundle
from joule.utils.metrics import aggregate_samples


class PerformanceOracle:
    def __init__(self, settings: JouleSettings, backend_name: str | None = None, reporter=None) -> None:
        self.settings = settings
        self.reporter = reporter
        self.backend = _get_backend(backend_name or settings.default_backend, settings)

    def repetitions_for(self, fidelity: Fidelity, explicit: int | None = None) -> int:
        if explicit is not None:
            return explicit
        if fidelity is Fidelity.F1:
            return self.settings.fidelity.f1_repetitions
        if fidelity is Fidelity.F2:
            return self.settings.fidelity.f2_repetitions
        return self.settings.fidelity.f3_repetitions

    def measure_bundle(
        self,
        *,
        run_id: str,
        target: TargetSpec,
        bundle: WorkloadBundle,
        fidelity: Fidelity,
        candidate_id: str | None = None,
        candidate_source: str | None = None,
        repetitions: int | None = None,
    ) -> MeasurementReport:
        overlay_context = tempfile.TemporaryDirectory(prefix="joule-overlay-") if candidate_source else None
        overlay_root = Path(overlay_context.name) if overlay_context else None
        if overlay_root and candidate_source:
            _materialize_overlay(target, overlay_root, candidate_source)
        try:
            all_samples: list[MetricSample] = []
            calibration_records: list[dict] = []
            reps = self.repetitions_for(fidelity, explicit=repetitions)
            for workload in bundle.workloads:
                calibration = self._calibrate(
                    target=target,
                    workload=workload,
                    fidelity=fidelity,
                    overlay_root=overlay_root,
                )
                calibration_records.append(calibration.to_record())
                if self.reporter:
                    self.reporter.verbose(
                        "calibration",
                        f"{workload.identifier} -> inner_repetitions={calibration.inner_repetitions} "
                        f"mode={calibration.adaptive_mode} target={calibration.adaptive_target_window_s:.3f}s",
                    )
                for repetition in range(1, reps + 1):
                    if self.reporter:
                        self.reporter.verbose(
                            "measurement",
                            f"{workload.identifier} {fidelity.value} sample {repetition}/{reps}",
                        )
                    measurement = self.backend.measure(
                        target,
                        workload,
                        overlay_root=overlay_root,
                        inner_repetitions=calibration.inner_repetitions,
                        timeout_s=self.settings.workload_timeout_s,
                    )
                    sample = self._to_metric_sample(
                        measurement=measurement,
                        workload_id=workload.identifier,
                        fidelity=fidelity,
                        repetition=repetition,
                        calibration=calibration,
                    )
                    all_samples.append(sample)
            aggregate, per_workload = aggregate_samples(all_samples)
            return MeasurementReport(
                run_id=run_id,
                candidate_id=candidate_id,
                fidelity=fidelity,
                aggregate=aggregate,
                per_workload=per_workload,
                samples=all_samples,
                environment={
                    "backend": getattr(self.backend, "name", type(self.backend).__name__),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "overlay": str(overlay_root) if overlay_root else None,
                },
                metadata={"calibration": calibration_records},
            )
        finally:
            if overlay_context:
                overlay_context.cleanup()

    def _calibrate(
        self,
        *,
        target: TargetSpec,
        workload,
        fidelity: Fidelity,
        overlay_root: Path | None,
    ) -> CalibrationResult:
        fixed = max(self.settings.inner_repetitions_min, self.settings.inner_repetitions_fixed)
        if self.settings.inner_repetitions_mode == "fixed":
            return CalibrationResult(
                workload_id=workload.identifier,
                inner_repetitions=min(fixed, self.settings.inner_repetitions_max),
                adaptive_applied=False,
                adaptive_estimated_wall_time_s=0.0,
                adaptive_target_window_s=self.settings.adaptive_min_window_s,
                adaptive_mode="fixed",
            )

        probe_walls: list[float] = []
        for _ in range(max(1, self.settings.adaptive_probe_samples)):
            probe = self.backend.measure(
                target,
                workload,
                overlay_root=overlay_root,
                inner_repetitions=1,
                timeout_s=self.settings.workload_timeout_s,
            )
            probe_walls.append(probe.wall_time_s)
        estimated_wall = sum(probe_walls) / len(probe_walls)
        if estimated_wall >= self.settings.adaptive_min_window_s:
            return CalibrationResult(
                workload_id=workload.identifier,
                inner_repetitions=1,
                adaptive_applied=False,
                adaptive_estimated_wall_time_s=estimated_wall,
                adaptive_target_window_s=self.settings.adaptive_min_window_s,
                adaptive_mode="adaptive",
            )

        multiplier = ceil(self.settings.adaptive_min_window_s / max(estimated_wall, 1e-9))
        multiplier = max(multiplier, self.settings.inner_repetitions_min)
        capped = multiplier > self.settings.inner_repetitions_max
        multiplier = min(multiplier, self.settings.inner_repetitions_max)
        return CalibrationResult(
            workload_id=workload.identifier,
            inner_repetitions=multiplier,
            adaptive_applied=multiplier > 1,
            adaptive_estimated_wall_time_s=estimated_wall,
            adaptive_target_window_s=self.settings.adaptive_min_window_s,
            adaptive_mode="adaptive",
            capped=capped,
        )

    def _to_metric_sample(self, *, measurement, workload_id: str, fidelity: Fidelity, repetition: int, calibration: CalibrationResult):
        divisor = max(1, int(measurement.metadata.get("logical_invocations", calibration.inner_repetitions)))
        metadata = {
            "backend": getattr(self.backend, "name", type(self.backend).__name__),
            "inner_repetitions": calibration.inner_repetitions,
            "adaptive_applied": calibration.adaptive_applied,
            "adaptive_estimated_wall_time_s": calibration.adaptive_estimated_wall_time_s,
            "adaptive_target_window_s": calibration.adaptive_target_window_s,
            "adaptive_mode": calibration.adaptive_mode,
            "adaptive_capped": calibration.capped,
            "outer_repetition_index": repetition,
            **measurement.metadata,
        }
        return MetricSample(
            workload_id=workload_id,
            fidelity=fidelity,
            repetition=repetition,
            success=measurement.success,
            wall_time_s=measurement.wall_time_s / divisor,
            cpu_time_s=measurement.cpu_time_s / divisor,
            peak_memory_bytes=max(1, int(measurement.peak_memory_bytes / divisor)) if measurement.peak_memory_bytes else 0,
            energy_j=measurement.energy_j / divisor,
            return_code=measurement.return_code,
            stdout=measurement.stdout,
            stderr=measurement.stderr,
            metadata=metadata,
        )

    def profile_bundle_hotspots(
        self,
        *,
        target: TargetSpec,
        bundle: WorkloadBundle,
        candidate_source: str | None = None,
    ) -> list[dict]:
        overlay_context = tempfile.TemporaryDirectory(prefix="joule-overlay-") if candidate_source else None
        overlay_root = Path(overlay_context.name) if overlay_context else None
        if overlay_root and candidate_source:
            _materialize_overlay(target, overlay_root, candidate_source)
        try:
            records: list[dict] = []
            for workload in bundle.workloads:
                profiled = invoke_profile_worker(
                    target,
                    workload,
                    overlay_root=overlay_root,
                    inner_repetitions=1,
                    timeout_s=self.settings.workload_timeout_s,
                )
                profile = profiled.get("profile", {"functions": [], "ownership": []})
                records.append(
                    {
                        "workload_id": workload.identifier,
                        "success": bool(profiled.get("success", False)),
                        "return_code": int(profiled.get("return_code", 1)),
                        "stderr": str(profiled.get("stderr", "")),
                        "profile": profile,
                    }
                )
            return records
        finally:
            if overlay_context:
                overlay_context.cleanup()


def _get_backend(name: str, settings: JouleSettings):
    if name == "rapl":
        rapl_options = settings.backends.options.get("rapl", {}) if settings.backends.options else {}
        rapl_path = rapl_options.get("path")
        return RaplEnergyBackend(rapl_path=Path(rapl_path) if isinstance(rapl_path, str) else None)
    return MockEnergyBackend()
