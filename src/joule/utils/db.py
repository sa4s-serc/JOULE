from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from typing import Any, Iterator

from joule.models import MeasurementReport, RunRecord, RunType, TargetSpec, WorkloadBundle


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
  reward REAL NOT NULL DEFAULT 0
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
"""


class JouleDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

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

    def bump_operator(self, operator_name: str, success: bool, reward: float) -> None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT attempts, successes, reward FROM operator_stats WHERE operator_name = ?",
                (operator_name,),
            ).fetchone()
            if row is None:
                attempts, successes, total_reward = 0, 0, 0.0
            else:
                attempts, successes, total_reward = row
            attempts += 1
            successes += int(success)
            total_reward += reward
            conn.execute(
                """
                INSERT OR REPLACE INTO operator_stats(operator_name, attempts, successes, reward)
                VALUES(?, ?, ?, ?)
                """,
                (operator_name, attempts, successes, total_reward),
            )

    def get_operator_stats(self) -> dict[str, dict[str, float]]:
        rows = self._fetchall("SELECT operator_name, attempts, successes, reward FROM operator_stats")
        return {
            row[0]: {"attempts": float(row[1]), "successes": float(row[2]), "reward": float(row[3])}
            for row in rows
        }

    def get_recent_candidate_observations(self, *, limit: int) -> list[tuple[str, float]]:
        rows = self._fetchall(
            """
            SELECT source_code, score
            FROM candidates
            WHERE score < 1e308
            ORDER BY rowid DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [(str(row[0]), float(row[1])) for row in rows]

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

    def get_candidates(self, run_id: str) -> list[dict]:
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

    def _candidate_row_to_record(self, row: tuple[Any, ...]) -> dict[str, Any]:
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
