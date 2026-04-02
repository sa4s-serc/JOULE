from __future__ import annotations

from pathlib import Path

from joule.evaluators.backends.base import BackendMeasurement, run_worker_process
from joule.models import TargetSpec, WorkloadSpec


class RaplEnergyBackend:
    name = "rapl"

    def __init__(self, rapl_path: Path | None = None) -> None:
        self.rapl_path = rapl_path or Path("/sys/class/powercap/intel-rapl:0/energy_uj")

    def measure(
        self,
        target: TargetSpec,
        workload: WorkloadSpec,
        *,
        overlay_root: Path | None = None,
        inner_repetitions: int = 1,
        timeout_s: float = 30.0,
    ) -> BackendMeasurement:
        if not self.rapl_path.exists():
            raise RuntimeError(f"RAPL path not available: {self.rapl_path}")
        start = int(self.rapl_path.read_text(encoding="utf-8").strip())
        execution = run_worker_process(
            target,
            workload,
            overlay_root=overlay_root,
            inner_repetitions=inner_repetitions,
            timeout_s=timeout_s,
        )
        end = int(self.rapl_path.read_text(encoding="utf-8").strip())
        delta = max(0, end - start) / 1_000_000.0
        return BackendMeasurement(
            wall_time_s=execution.wall_time_s,
            cpu_time_s=execution.cpu_time_s,
            peak_memory_bytes=execution.peak_memory_bytes,
            energy_j=delta,
            return_code=int(execution.payload["return_code"]),
            success=bool(execution.payload["success"]),
            stdout=str(execution.payload.get("stdout", "")),
            stderr=str(execution.payload.get("stderr", "")),
            metadata={
                "path": str(self.rapl_path),
                "logical_invocations": execution.payload.get("logical_invocations", inner_repetitions),
            },
        )
