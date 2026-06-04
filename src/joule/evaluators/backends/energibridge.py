from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from joule.evaluators.backends.base import BackendMeasurement, run_worker_process
from joule.models import TargetSpec, WorkloadSpec

LOGGER = logging.getLogger(__name__)


class EnergiBridgeBackend:
    """Energy backend using pyEnergiBridge (luiscruz/pyEnergiBridge).

    Wraps ``EnergiBridgeRunner`` to bracket each worker subprocess with
    real hardware energy measurements.  Because EnergiBridge reads
    system-level power sensors (RAPL / NVIDIA / Apple Silicon etc.),
    concurrent measurements would contaminate each other, so parallel
    measurement is disabled.

    Configuration (via ``joule.toml`` ``[backends.options.energibridge]``):
        binary_path  – path to the EnergiBridge binary (optional; falls back
                       to pyEnergiBridge's own discovery logic).
        results_dir  – directory to write per-run CSV files (optional; uses
                       a system temp dir when omitted).
    """

    name = "energibridge"
    supports_parallel_measurement = False

    def __init__(
        self,
        *,
        binary_path: str | None = None,
        results_dir: Path | None = None,
    ) -> None:
        self._binary_path = binary_path
        self._results_dir = results_dir

    # ------------------------------------------------------------------
    # EnergyBackend protocol
    # ------------------------------------------------------------------

    def measure(
        self,
        target: TargetSpec,
        workload: WorkloadSpec,
        *,
        overlay_root: Path | None = None,
        inner_repetitions: int = 1,
        timeout_s: float = 30.0,
    ) -> BackendMeasurement:
        try:
            from pyEnergiBridge.api import EnergiBridgeRunner  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "pyEnergiBridge is not installed. "
                "Install it with: pip install git+https://github.com/luiscruz/pyEnergiBridge.git"
            ) from exc

        results_file = self._make_results_file(workload)

        runner_kwargs: dict = {}
        if self._binary_path is not None:
            runner_kwargs["binary_path"] = self._binary_path

        runner = EnergiBridgeRunner(**runner_kwargs)

        try:
            runner.start(results_file=str(results_file))
        except Exception as exc:
            raise RuntimeError(
                f"EnergiBridge failed to start (binary_path={self._binary_path!r}): {exc}"
            ) from exc

        try:
            execution = run_worker_process(
                target,
                workload,
                overlay_root=overlay_root,
                inner_repetitions=inner_repetitions,
                timeout_s=timeout_s,
            )
        finally:
            try:
                energy_j, duration_s = runner.stop()
            except Exception as exc:
                LOGGER.warning("EnergiBridge stop() failed: %s", exc)
                energy_j, duration_s = 0.0, 0.0

        # EnergiBridge returns total energy for the bracketed window, which
        # includes both the worker process and a small measurement overhead.
        # We report it directly — callers can normalise by inner_repetitions
        # if they need per-invocation figures.
        return BackendMeasurement(
            wall_time_s=execution.wall_time_s,
            cpu_time_s=execution.cpu_time_s,
            peak_memory_bytes=execution.peak_memory_bytes,
            energy_j=float(energy_j),
            return_code=int(execution.payload["return_code"]),
            success=bool(execution.payload["success"]),
            stdout=str(execution.payload.get("stdout", "")),
            stderr=str(execution.payload.get("stderr", "")),
            metadata={
                "energibridge_duration_s": float(duration_s),
                "results_file": str(results_file),
                "binary_path": self._binary_path,
                "logical_invocations": execution.payload.get(
                    "logical_invocations", inner_repetitions
                ),
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_results_file(self, workload: WorkloadSpec) -> Path:
        """Return a unique CSV path for this measurement."""
        safe_id = "".join(c if c.isalnum() else "_" for c in workload.identifier)[:48]
        filename = f"energibridge_{safe_id}.csv"
        if self._results_dir is not None:
            self._results_dir.mkdir(parents=True, exist_ok=True)
            return self._results_dir / filename
        # Fall back to a temp directory so we don't litter the project root.
        return Path(tempfile.gettempdir()) / filename
