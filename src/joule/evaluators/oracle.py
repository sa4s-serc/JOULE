from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
import json
from math import ceil
from pathlib import Path
import tempfile
from typing import Any

from joule.config import JouleSettings
from joule.evaluators.backends.base import BackendMeasurement, EnergyBackend
from joule.evaluators.backends.registry import BackendRegistry
from joule.evaluators.correctness import _materialize_overlay
from joule.integrations.git import source_sha256
from joule.runtime import invoke_profile_worker
from joule.models import CalibrationResult, Fidelity, MeasurementReport, MetricSample, TargetSpec, WorkloadBundle, WorkloadSpec
from joule.utils.metrics import aggregate_samples


def _measure_workload_task(
    target: TargetSpec,
    workload: WorkloadSpec,
    overlay_root: Path | None,
    inner_repetitions: int,
    timeout_s: float,
    backend: EnergyBackend,
    reps: int,
) -> list[BackendMeasurement]:
    measurements = []
    for _ in range(1, reps + 1):
        measurement = backend.measure(
            target,
            workload,
            overlay_root=overlay_root,
            inner_repetitions=inner_repetitions,
            timeout_s=timeout_s,
        )
        measurements.append(measurement)
    return measurements


def _bundle_cache_key(bundle: WorkloadBundle) -> str:
    ids = sorted(item.identifier for item in bundle.workloads)
    return "bundle::" + "|".join(ids)


def _backend_cache_namespace(backend: EnergyBackend) -> str:
    name = str(getattr(backend, "name", type(backend).__name__)).strip().lower()
    return name or type(backend).__name__.lower()


def _measurement_cache_key(bundle: WorkloadBundle, backend: EnergyBackend) -> str:
    return f"backend::{_backend_cache_namespace(backend)}::{_bundle_cache_key(bundle)}"


class PerformanceOracle:
    def __init__(self, settings: JouleSettings, backend: EnergyBackend, reporter=None, db=None) -> None:
        self.settings = settings
        self.reporter = reporter
        self.backend = backend
        self.db = db

    @classmethod
    def create(cls, settings: JouleSettings, backend_name: str | None = None, reporter=None, db=None) -> "PerformanceOracle":
        backend = BackendRegistry().get(backend_name or settings.default_backend, settings)
        return cls(settings=settings, backend=backend, reporter=reporter, db=db)

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
        use_cache: bool = True,
    ) -> MeasurementReport:
        overlay_context = tempfile.TemporaryDirectory(prefix="joule-overlay-") if candidate_source else None
        overlay_root = Path(overlay_context.name) if overlay_context else None
        if overlay_root and candidate_source:
            _materialize_overlay(target, overlay_root, candidate_source)
        try:
            backend_name = _backend_cache_namespace(self.backend)
            source = candidate_source or target.source
            source_hash = source_sha256(source)
            file_mtime = target.file_path.stat().st_mtime if target.file_path.exists() else 0.0
            cache_key = _measurement_cache_key(bundle, self.backend)

            if use_cache and self.db and candidate_id is None:
                cached = self.db.get_cached_measurement(source_hash, cache_key, fidelity.value, file_mtime)
                if cached:
                    if self.reporter:
                        self.reporter.info(
                            "cache",
                            f"Cache hit for {cache_key} at {fidelity.value}",
                        )
                    report = MeasurementReport.from_record(cached)
                    report.run_id = run_id
                    report.candidate_id = candidate_id
                    report.metadata = {
                        **report.metadata,
                        "cache_hit": True,
                        "cache_key": cache_key,
                    }
                    return report

            all_samples: list[MetricSample] = []
            calibration_records: list[dict] = []
            reps = self.repetitions_for(fidelity, explicit=repetitions)
            backend_supports_parallel = self.backend.supports_parallel_measurement
            use_parallel = (
                backend_supports_parallel and self.settings.max_parallel_workers > 1 and len(bundle.workloads) > 1
            )

            if self.settings.max_parallel_workers > 1 and len(bundle.workloads) > 1 and not backend_supports_parallel:
                if self.reporter:
                    self.reporter.info(
                        "backend",
                        f"Backend {backend_name} does not support parallel measurement; using sequential mode",
                    )

            if use_parallel:
                calibrations = []
                for workload in bundle.workloads:
                    calibration = self._calibrate(
                        target=target,
                        workload=workload,
                        fidelity=fidelity,
                        overlay_root=overlay_root,
                    )
                    calibrations.append((workload, calibration))
                    calibration_records.append(calibration.to_record())
                    if self.reporter:
                        self.reporter.verbose(
                            "calibration",
                            f"{workload.identifier} -> inner_repetitions={calibration.inner_repetitions} "
                            f"mode={calibration.adaptive_mode} target={calibration.adaptive_target_window_s:.3f}s",
                        )
                
                with ProcessPoolExecutor(max_workers=self.settings.max_parallel_workers) as executor:
                    futures = {}
                    for workload, calibration in calibrations:
                        future = executor.submit(
                            _measure_workload_task,
                            target,
                            workload,
                            overlay_root,
                            calibration.inner_repetitions,
                            self.settings.workload_timeout_s,
                            self.backend,
                            reps,
                        )
                        futures[future] = (workload, calibration)

                    for future in as_completed(futures):
                        workload, calibration = futures[future]
                        measurements = future.result()
                        for i, measurement in enumerate(measurements, 1):
                            if self.reporter:
                                self.reporter.verbose(
                                    "measurement",
                                    f"{workload.identifier} {fidelity.value} sample {i}/{reps}",
                                )
                            self._report_worker_diagnostics(
                                workload_id=workload.identifier,
                                fidelity=fidelity,
                                repetition=i,
                                measurement=measurement,
                            )
                            sample = self._to_metric_sample(
                                measurement=measurement,
                                workload_id=workload.identifier,
                                fidelity=fidelity,
                                repetition=i,
                                calibration=calibration,
                            )
                            all_samples.append(sample)
            else:
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
                        self._report_worker_diagnostics(
                            workload_id=workload.identifier,
                            fidelity=fidelity,
                            repetition=repetition,
                            measurement=measurement,
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
            report = MeasurementReport(
                run_id=run_id,
                candidate_id=candidate_id,
                fidelity=fidelity,
                aggregate=aggregate,
                per_workload=per_workload,
                samples=all_samples,
                environment={
                    "backend": backend_name,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "overlay": str(overlay_root) if overlay_root else None,
                },
                metadata={"calibration": calibration_records},
            )

            if use_cache and self.db and candidate_id is None:
                self.db.save_cached_measurement(
                    source_hash=source_hash,
                    workload_id=cache_key,
                    fidelity=fidelity.value,
                    report_json=json.dumps(report.to_record()),
                    file_mtime=file_mtime,
                )

            return report
        finally:
            if overlay_context:
                overlay_context.cleanup()

    def _calibrate(
        self,
        *,
        target: TargetSpec,
        workload: WorkloadSpec,
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

    def _to_metric_sample(
        self,
        *,
        measurement: BackendMeasurement,
        workload_id: str,
        fidelity: Fidelity,
        repetition: int,
        calibration: CalibrationResult,
    ):
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
            peak_memory_bytes=max(0, int(measurement.peak_memory_bytes)),
            energy_j=measurement.energy_j / divisor,
            return_code=measurement.return_code,
            stdout=measurement.stdout,
            stderr=measurement.stderr,
            metadata=metadata,
        )

    def _report_worker_diagnostics(
        self,
        *,
        workload_id: str,
        fidelity: Fidelity,
        repetition: int,
        measurement: BackendMeasurement,
    ) -> None:
        if not self.reporter:
            return
        if not measurement.success:
            self.reporter.warn(
                "worker",
                f"{workload_id} {fidelity.value} sample {repetition} failed (return_code={measurement.return_code})",
            )
        stderr = str(measurement.stderr or "").strip()
        if stderr:
            excerpt = stderr.splitlines()[0][:180]
            self.reporter.debug(
                "worker",
                f"{workload_id} {fidelity.value} sample {repetition} stderr: {excerpt}",
            )

    def profile_bundle_hotspots(
        self,
        *,
        target: TargetSpec,
        bundle: WorkloadBundle,
        candidate_source: str | None = None,
        granular: bool = False,
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
                    profile_mode="granular" if granular else "hotspots",
                )
                profile = profiled.get("profile", {"functions": [], "ownership": []})
                records.append(
                    {
                        "workload_id": workload.identifier,
                        "workload_kind": workload.kind.value,
                        "workload_label": workload.label,
                        "workload_selector": workload.selector,
                        "workload_metadata": dict(workload.metadata),
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
