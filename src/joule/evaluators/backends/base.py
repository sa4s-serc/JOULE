from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import resource
import subprocess
import time
from typing import Protocol

import psutil

from joule.models import TargetSpec, WorkloadSpec
from joule.runtime import subprocess_env, worker_command


@dataclass(slots=True)
class BackendMeasurement:
    wall_time_s: float
    cpu_time_s: float
    peak_memory_bytes: int
    energy_j: float
    return_code: int
    success: bool
    stdout: str = ""
    stderr: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class WorkerExecution:
    wall_time_s: float
    cpu_time_s: float
    peak_memory_bytes: int
    payload: dict


class EnergyBackend(Protocol):
    name: str

    def measure(
        self,
        target: TargetSpec,
        workload: WorkloadSpec,
        *,
        overlay_root: Path | None = None,
        inner_repetitions: int = 1,
        timeout_s: float = 30.0,
    ) -> BackendMeasurement:
        ...


def run_worker_process(
    target: TargetSpec,
    workload: WorkloadSpec,
    *,
    overlay_root: Path | None = None,
    inner_repetitions: int = 1,
    timeout_s: float = 30.0,
) -> WorkerExecution:
    command = worker_command(target, workload, overlay_root=overlay_root, inner_repetitions=inner_repetitions)
    env = subprocess_env(target.project_root, overlay_root)
    wall_started = time.perf_counter()
    cpu_started = resource.getrusage(resource.RUSAGE_CHILDREN)
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    peak_memory = 0
    ps_process: psutil.Process | None = None
    try:
        ps_process = psutil.Process(process.pid)
    except psutil.Error:
        ps_process = None

    timed_out = False
    while process.poll() is None:
        if ps_process is not None:
            peak_memory = max(peak_memory, _rss_tree(ps_process))
        if (time.perf_counter() - wall_started) > timeout_s:
            timed_out = True
            _terminate_tree(ps_process, process)
            break
        time.sleep(0.005)
    stdout, stderr = process.communicate()
    wall_elapsed = time.perf_counter() - wall_started
    cpu_finished = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu_elapsed = (cpu_finished.ru_utime + cpu_finished.ru_stime) - (cpu_started.ru_utime + cpu_started.ru_stime)
    if ps_process is not None:
        peak_memory = max(peak_memory, _rss_tree(ps_process))

    if timed_out:
        payload = {
            "success": False,
            "return_code": 124,
            "stdout": stdout or "",
            "stderr": (stderr or "").strip() or f"Timed out after {timeout_s:.1f}s",
            "logical_invocations": inner_repetitions,
            "inner_repetitions": inner_repetitions,
        }
    elif stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {
                "success": False,
                "return_code": process.returncode or 1,
                "stdout": stdout,
                "stderr": stderr.strip(),
                "logical_invocations": inner_repetitions,
                "inner_repetitions": inner_repetitions,
            }
    else:
        payload = {
            "success": False,
            "return_code": process.returncode or 1,
            "stdout": "",
            "stderr": stderr.strip(),
            "logical_invocations": inner_repetitions,
            "inner_repetitions": inner_repetitions,
        }

    payload["stdout"] = payload.get("stdout", "")
    payload["stderr"] = payload.get("stderr", "") or stderr.strip()
    payload["return_code"] = int(payload.get("return_code", process.returncode or 1))
    payload["success"] = bool(payload.get("success", False))
    payload["logical_invocations"] = int(payload.get("logical_invocations", inner_repetitions))
    payload["inner_repetitions"] = int(payload.get("inner_repetitions", inner_repetitions))
    return WorkerExecution(
        wall_time_s=wall_elapsed,
        cpu_time_s=max(cpu_elapsed, 0.0),
        peak_memory_bytes=max(int(peak_memory), 0),
        payload=payload,
    )


def _rss_tree(process: psutil.Process) -> int:
    try:
        total = process.memory_info().rss
    except psutil.Error:
        return 0
    try:
        children = process.children(recursive=True)
    except psutil.Error:
        children = []
    for child in children:
        try:
            total += child.memory_info().rss
        except psutil.Error:
            continue
    return total


def _terminate_tree(ps_process: psutil.Process | None, process: subprocess.Popen) -> None:
    if ps_process is not None:
        try:
            for child in ps_process.children(recursive=True):
                child.kill()
        except psutil.Error:
            pass
    process.kill()
