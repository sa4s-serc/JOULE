from __future__ import annotations

from pathlib import Path

from joule.evaluators.backends.base import BackendMeasurement, run_worker_process
from joule.models import TargetSpec, WorkloadSpec


class MockEnergyBackend:
    name = "mock"
    supports_parallel_measurement = True

    def measure(
        self,
        target: TargetSpec,
        workload: WorkloadSpec,
        *,
        overlay_root: Path | None = None,
        inner_repetitions: int = 1,
        timeout_s: float = 30.0,
    ) -> BackendMeasurement:
        execution = run_worker_process(
            target,
            workload,
            overlay_root=overlay_root,
            inner_repetitions=inner_repetitions,
            timeout_s=timeout_s,
        )
        memory_mib = execution.peak_memory_bytes / (1024 * 1024)
        energy = (execution.cpu_time_s * 12.0) + (execution.wall_time_s * 4.0) + (memory_mib * 0.0025)
        return BackendMeasurement(
            wall_time_s=execution.wall_time_s,
            cpu_time_s=execution.cpu_time_s,
            peak_memory_bytes=execution.peak_memory_bytes,
            energy_j=energy,
            return_code=int(execution.payload["return_code"]),
            success=bool(execution.payload["success"]),
            stdout=str(execution.payload.get("stdout", "")),
            stderr=str(execution.payload.get("stderr", "")),
            metadata={
                "formula": "cpu*12 + wall*4 + mem_mib*0.0025",
                "logical_invocations": execution.payload.get("logical_invocations", inner_repetitions),
            },
        )
