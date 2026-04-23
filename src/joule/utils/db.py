from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import json
import sqlite3
from threading import RLock
from typing import Any, Iterator, TypedDict

from joule.models import MeasurementReport, RunRecord, RunType, TargetSpec, WorkloadBundle

DB_SCHEMA_VERSION = 5


class CandidateRecord(TypedDict):
    candidate_id: str
    parent_id: str | None
    operator_name: str
    reasoning: str
    dependencies: list[str]
    source_code: str
    status: str
    score: float
    metadata: dict[str, Any]


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  run_type TEXT NOT NULL,
  target_json TEXT NOT NULL,
  bundle_json TEXT NOT NULL,
  status TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workloads (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  workload_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  label TEXT NOT NULL,
  selector TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
  candidate_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  parent_id TEXT,
  operator_name TEXT NOT NULL,
  reasoning TEXT NOT NULL,
  dependencies_json TEXT NOT NULL,
  source_code TEXT NOT NULL,
  status TEXT NOT NULL,
  score REAL NOT NULL,
  metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measurements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  candidate_id TEXT,
  fidelity TEXT NOT NULL,
  report_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apply_audits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL,
  applied_at TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operator_stats (
  operator_name TEXT PRIMARY KEY,
  attempts INTEGER NOT NULL DEFAULT 0,
  successes INTEGER NOT NULL DEFAULT 0,
  reward REAL NOT NULL DEFAULT 0,
  duplicates INTEGER NOT NULL DEFAULT 0,
  correctness_failures INTEGER NOT NULL DEFAULT 0,
  frontier_contributions INTEGER NOT NULL DEFAULT 0,
  precheck_failures INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS search_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  candidate_id TEXT,
  operator_name TEXT,
  event_type TEXT NOT NULL,
  stage TEXT NOT NULL,
  detail_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hotspot_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  candidate_id TEXT,
  workload_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checkpoints (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  generation INTEGER NOT NULL,
  candidate_id TEXT NOT NULL,
  pareto_front_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS measurements_cache (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_hash TEXT NOT NULL,
  workload_id TEXT NOT NULL,
  fidelity TEXT NOT NULL,
  report_json TEXT NOT NULL,
  file_mtime REAL NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cache_lookup ON measurements_cache(source_hash, workload_id, fidelity);
CREATE TABLE IF NOT EXISTS surrogate_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  target_key TEXT NOT NULL,
  source_hash TEXT NOT NULL,
  source_code TEXT NOT NULL,
  targets_json TEXT NOT NULL,
  feature_hints_json TEXT NOT NULL,
  feature_schema_version INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(target_key, source_hash)
);
CREATE INDEX IF NOT EXISTS idx_surrogate_obs_target_recent ON surrogate_observations(target_key, id DESC);
"""


class JouleDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._conn_lock = RLock()
        self._check_schema_compatibility()
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
            current_version = int(row[0]) if row else 0
            if current_version == 0:
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (DB_SCHEMA_VERSION, datetime.now(UTC).isoformat()),
                )

    def _check_schema_compatibility(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        conn = sqlite3.connect(self.path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            if not tables:
                return
            if "schema_version" not in tables:
                raise ValueError(
                    "Detected incompatible JOULE database schema. "
                    "Remove .joule/ and rerun to initialize the clean multi-surrogate schema."
                )
            row = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1").fetchone()
            current_version = int(row[0]) if row else 0
            if current_version != 0 and current_version < DB_SCHEMA_VERSION:
                raise ValueError(
                    "Detected incompatible JOULE database schema version "
                    f"{current_version}. Remove .joule/ and rerun to initialize schema version {DB_SCHEMA_VERSION}."
                )
        finally:
            conn.close()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with self._conn_lock:
            conn = self._get_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn

    def _fetchall(self, query: str, params: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def _fetchone(self, query: str, params: tuple[object, ...] = ()) -> tuple[Any, ...] | None:
        with self.connect() as conn:
            return conn.execute(query, params).fetchone()

    def create_run(self, record: RunRecord) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(run_id, run_type, target_json, bundle_json, status, metadata_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.run_type.value,
                    json.dumps(record.target.to_record()),
                    json.dumps(record.bundle.to_record()),
                    record.status,
                    json.dumps(record.metadata),
                    record.created_at,
                ),
            )
            for workload in record.bundle.workloads:
                conn.execute(
                    """
                    INSERT INTO workloads(run_id, workload_id, kind, label, selector, metadata_json)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.run_id,
                        workload.identifier,
                        workload.kind.value,
                        workload.label,
                        workload.selector,
                        json.dumps(workload.metadata),
                    ),
                )

    def update_run_status(self, run_id: str, status: str, metadata: dict | None = None) -> None:
        with self.connect() as conn:
            if metadata is None:
                conn.execute("UPDATE runs SET status = ? WHERE run_id = ?", (status, run_id))
            else:
                conn.execute(
                    "UPDATE runs SET status = ?, metadata_json = ? WHERE run_id = ?",
                    (status, json.dumps(metadata), run_id),
                )

    def record_candidate(
        self,
        *,
        candidate_id: str,
        run_id: str,
        parent_id: str | None,
        operator_name: str,
        reasoning: str,
        dependencies: list[str],
        source_code: str,
        status: str,
        score: float,
        metadata: dict,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO candidates(candidate_id, run_id, parent_id, operator_name, reasoning,
                                       dependencies_json, source_code, status, score, metadata_json)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    run_id,
                    parent_id,
                    operator_name,
                    reasoning,
                    json.dumps(dependencies),
                    source_code,
                    status,
                    score,
                    json.dumps(metadata),
                ),
            )

    def record_measurement(self, report: MeasurementReport, created_at: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO measurements(run_id, candidate_id, fidelity, report_json, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    report.run_id,
                    report.candidate_id,
                    report.fidelity.value,
                    json.dumps(report.to_record()),
                    created_at,
                ),
            )

    def record_artifact(self, run_id: str, name: str, kind: str, payload: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO artifacts(run_id, name, kind, payload) VALUES(?, ?, ?, ?)",
                (run_id, name, kind, payload),
            )

    def bump_operator(
        self,
        operator_name: str,
        success: bool,
        reward: float,
        *,
        duplicate: bool = False,
        correctness_failure: bool = False,
        frontier_contribution: bool = False,
        precheck_failure: bool = False,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO operator_stats(
                    operator_name,
                    attempts,
                    successes,
                    reward,
                    duplicates,
                    correctness_failures,
                    frontier_contributions,
                    precheck_failures
                )
                VALUES(?, 1, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(operator_name) DO UPDATE SET
                    attempts = operator_stats.attempts + 1,
                    successes = operator_stats.successes + excluded.successes,
                    reward = operator_stats.reward + excluded.reward,
                    duplicates = operator_stats.duplicates + excluded.duplicates,
                    correctness_failures = operator_stats.correctness_failures + excluded.correctness_failures,
                    frontier_contributions = operator_stats.frontier_contributions + excluded.frontier_contributions,
                    precheck_failures = operator_stats.precheck_failures + excluded.precheck_failures
                """,
                (
                    operator_name,
                    int(success),
                    float(reward),
                    int(duplicate),
                    int(correctness_failure),
                    int(frontier_contribution),
                    int(precheck_failure),
                ),
            )

    def get_operator_stats(self) -> dict[str, dict[str, float]]:
        rows = self._fetchall("SELECT operator_name, attempts, successes, reward, duplicates, correctness_failures, frontier_contributions, precheck_failures FROM operator_stats")
        return {
            row[0]: {
                "attempts": float(row[1]),
                "successes": float(row[2]),
                "reward": float(row[3]),
                "duplicates": float(row[4]),
                "correctness_failures": float(row[5]),
                "frontier_contributions": float(row[6]),
                "precheck_failures": float(row[7]),
            }
            for row in rows
        }

    def save_surrogate_observation(
        self,
        *,
        run_id: str,
        target_key: str,
        source_code: str,
        targets: dict[str, float],
        feature_hints: dict[str, float] | None = None,
        feature_schema_version: int,
    ) -> None:
        created_at = datetime.now(UTC).isoformat()
        source_hash = hashlib.sha256(source_code.encode("utf-8")).hexdigest()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO surrogate_observations(
                    run_id,
                    target_key,
                    source_hash,
                    source_code,
                    targets_json,
                    feature_hints_json,
                    feature_schema_version,
                    created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(target_key, source_hash)
                DO UPDATE SET
                    run_id=excluded.run_id,
                    source_code=excluded.source_code,
                    targets_json=excluded.targets_json,
                    feature_hints_json=excluded.feature_hints_json,
                    feature_schema_version=excluded.feature_schema_version,
                    created_at=excluded.created_at
                """,
                (
                    run_id,
                    target_key,
                    source_hash,
                    source_code,
                    json.dumps({str(key): float(value) for key, value in targets.items()}),
                    json.dumps(feature_hints or {}),
                    int(feature_schema_version),
                    created_at,
                ),
            )

    def get_surrogate_observations(self, *, limit: int, target_key: str | None = None) -> list[dict[str, Any]]:
        if target_key is None:
            rows = self._fetchall(
                """
                SELECT source_code, targets_json, feature_hints_json, feature_schema_version
                FROM surrogate_observations
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        else:
            rows = self._fetchall(
                """
                SELECT source_code, targets_json, feature_hints_json, feature_schema_version
                FROM surrogate_observations
                WHERE target_key = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (target_key, limit),
            )
        return [
            {
                "source": str(row[0]),
                "targets": json.loads(str(row[1])) if row[1] else {},
                "feature_hints": json.loads(str(row[2])) if row[2] else {},
                "feature_schema_version": int(row[3]),
            }
            for row in rows
        ]

    def count_surrogate_observations(self, *, target_key: str | None = None) -> int:
        if target_key is None:
            row = self._fetchone("SELECT COUNT(1) FROM surrogate_observations")
        else:
            row = self._fetchone(
                "SELECT COUNT(1) FROM surrogate_observations WHERE target_key = ?",
                (target_key,),
            )
        if row is None:
            return 0
        return int(row[0])

    def list_runs(self) -> list[dict]:
        rows = self._fetchall(
            "SELECT run_id, run_type, status, created_at, metadata_json FROM runs ORDER BY created_at DESC"
        )
        return [self._run_summary_row_to_record(row) for row in rows]

    def get_run(self, run_id: str) -> RunRecord:
        row = self._fetchone(
            "SELECT run_type, target_json, bundle_json, status, created_at, metadata_json FROM runs WHERE run_id = ?",
            (run_id,),
        )
        if row is None:
            raise KeyError(f"Unknown run_id: {run_id}")
        return RunRecord(
            run_id=run_id,
            run_type=RunType(row[0]),
            target=TargetSpec.from_record(json.loads(row[1])),
            bundle=WorkloadBundle.from_record(json.loads(row[2])),
            status=row[3],
            created_at=row[4],
            metadata=json.loads(row[5]),
        )

    def get_measurements(self, run_id: str) -> list[dict]:
        rows = self._fetchall(
            "SELECT report_json FROM measurements WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [json.loads(row[0]) for row in rows]

    def get_artifacts(self, run_id: str) -> list[dict]:
        rows = self._fetchall(
            "SELECT name, kind, payload FROM artifacts WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [self._artifact_row_to_record(row) for row in rows]

    def get_candidates(self, run_id: str) -> list[CandidateRecord]:
        rows = self._fetchall(
            """
            SELECT candidate_id, parent_id, operator_name, reasoning, dependencies_json,
                   source_code, status, score, metadata_json
            FROM candidates WHERE run_id = ? ORDER BY score ASC
            """,
            (run_id,),
        )
        return [self._candidate_row_to_record(row) for row in rows]

    def record_apply_audit(self, run_id: str, candidate_id: str, applied_at: str, metadata: dict) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO apply_audits(run_id, candidate_id, applied_at, metadata_json) VALUES(?, ?, ?, ?)",
                (run_id, candidate_id, applied_at, json.dumps(metadata)),
            )

    def record_search_event(
        self,
        *,
        run_id: str,
        event_type: str,
        stage: str,
        created_at: str,
        detail: dict,
        candidate_id: str | None = None,
        operator_name: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO search_events(run_id, candidate_id, operator_name, event_type, stage, detail_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, candidate_id, operator_name, event_type, stage, json.dumps(detail), created_at),
            )

    def get_search_events(self, run_id: str) -> list[dict]:
        rows = self._fetchall(
            """
            SELECT candidate_id, operator_name, event_type, stage, detail_json, created_at
            FROM search_events
            WHERE run_id = ?
            ORDER BY id
            """,
            (run_id,),
        )
        return [self._search_event_row_to_record(row) for row in rows]

    def record_hotspot_profile(
        self,
        *,
        run_id: str,
        workload_id: str,
        kind: str,
        payload: dict,
        created_at: str,
        candidate_id: str | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO hotspot_profiles(run_id, candidate_id, workload_id, kind, payload_json, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (run_id, candidate_id, workload_id, kind, json.dumps(payload), created_at),
            )

    def get_hotspot_profiles(self, run_id: str, candidate_id: str | None = None) -> list[dict]:
        query = """
            SELECT candidate_id, workload_id, kind, payload_json, created_at
            FROM hotspot_profiles
            WHERE run_id = ?
        """
        params: list[object] = [run_id]
        if candidate_id is None:
            query += " AND candidate_id IS NULL"
        else:
            query += " AND candidate_id = ?"
            params.append(candidate_id)
        query += " ORDER BY id"
        rows = self._fetchall(query, tuple(params))
        return [self._hotspot_row_to_record(row) for row in rows]

    def get_apply_audits(self, run_id: str) -> list[dict]:
        rows = self._fetchall(
            "SELECT candidate_id, applied_at, metadata_json FROM apply_audits WHERE run_id = ? ORDER BY id",
            (run_id,),
        )
        return [self._apply_audit_row_to_record(row) for row in rows]

    def save_checkpoint(
        self,
        run_id: str,
        generation: int,
        candidate_id: str,
        pareto_front_json: str,
        metadata_json: str,
    ) -> None:
        created_at = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO checkpoints (run_id, generation, candidate_id, pareto_front_json, metadata_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, generation, candidate_id, pareto_front_json, metadata_json, created_at),
            )

    def get_latest_checkpoint(self, run_id: str) -> dict | None:
        rows = self._fetchall(
            "SELECT generation, candidate_id, pareto_front_json, metadata_json, created_at FROM checkpoints WHERE run_id = ? ORDER BY generation DESC LIMIT 1",
            (run_id,),
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "generation": row[0],
            "candidate_id": row[1],
            "pareto_front_json": row[2],
            "metadata": json.loads(row[3]),
            "created_at": row[4],
        }

    def get_checkpoints(self, run_id: str) -> list[dict]:
        rows = self._fetchall(
            "SELECT generation, candidate_id, pareto_front_json, metadata_json, created_at FROM checkpoints WHERE run_id = ? ORDER BY generation",
            (run_id,),
        )
        return [
            {
                "generation": row[0],
                "candidate_id": row[1],
                "pareto_front_json": row[2],
                "metadata": json.loads(row[3]),
                "created_at": row[4],
            }
            for row in rows
        ]

    def get_cached_measurement(
        self, source_hash: str, workload_id: str, fidelity: str, file_mtime: float
    ) -> dict | None:
        rows = self._fetchall(
            """
            SELECT report_json, file_mtime
            FROM measurements_cache
            WHERE source_hash = ? AND workload_id = ? AND fidelity = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (source_hash, workload_id, fidelity),
        )
        if not rows:
            return None
        row = rows[0]
        cached_mtime = row[1]
        if cached_mtime < file_mtime:
            return None
        return json.loads(row[0])

    def save_cached_measurement(
        self, source_hash: str, workload_id: str, fidelity: str, report_json: str, file_mtime: float
    ) -> None:
        created_at = datetime.now(UTC).isoformat()
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM measurements_cache WHERE source_hash = ? AND workload_id = ? AND fidelity = ?",
                (source_hash, workload_id, fidelity),
            )
            conn.execute(
                """INSERT INTO measurements_cache (source_hash, workload_id, fidelity, report_json, file_mtime, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (source_hash, workload_id, fidelity, report_json, file_mtime, created_at),
            )

    def clear_measurements_cache(self) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM measurements_cache")

    def _run_summary_row_to_record(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "run_id": row[0],
            "run_type": row[1],
            "status": row[2],
            "created_at": row[3],
            "metadata": json.loads(row[4]),
        }

    def _artifact_row_to_record(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {"name": row[0], "kind": row[1], "payload": row[2]}

    def _candidate_row_to_record(self, row: tuple[Any, ...]) -> CandidateRecord:
        return {
            "candidate_id": row[0],
            "parent_id": row[1],
            "operator_name": row[2],
            "reasoning": row[3],
            "dependencies": json.loads(row[4]),
            "source_code": row[5],
            "status": row[6],
            "score": row[7],
            "metadata": json.loads(row[8]),
        }

    def _search_event_row_to_record(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "candidate_id": row[0],
            "operator_name": row[1],
            "event_type": row[2],
            "stage": row[3],
            "detail": json.loads(row[4]),
            "created_at": row[5],
        }

    def _hotspot_row_to_record(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "candidate_id": row[0],
            "workload_id": row[1],
            "kind": row[2],
            "payload": json.loads(row[3]),
            "created_at": row[4],
        }

    def _apply_audit_row_to_record(self, row: tuple[Any, ...]) -> dict[str, Any]:
        return {"candidate_id": row[0], "applied_at": row[1], "metadata": json.loads(row[2])}
