"""Tests for JouleDB hotspot_profiles table methods."""
from __future__ import annotations

from pathlib import Path

import pytest

from joule.utils.db import JouleDB


@pytest.fixture()
def db(tmp_path: Path) -> JouleDB:
    return JouleDB(tmp_path / "test.db")


class TestRecordHotspotProfile:
    def test_record_and_retrieve_baseline(self, db: JouleDB) -> None:
        db.record_hotspot_profile(
            run_id="run1",
            workload_id="w1",
            kind="workload",
            payload={"functions": [], "ownership": []},
            created_at="2024-01-01T00:00:00",
        )
        records = db.get_hotspot_profiles("run1")
        assert len(records) == 1
        assert records[0]["workload_id"] == "w1"
        assert records[0]["kind"] == "workload"
        assert records[0]["candidate_id"] is None

    def test_record_with_candidate_id(self, db: JouleDB) -> None:
        db.record_hotspot_profile(
            run_id="run1",
            workload_id="w1",
            kind="workload",
            payload={"functions": []},
            created_at="2024-01-01T00:00:00",
            candidate_id="cand-abc",
        )
        # Querying without candidate_id should NOT return it
        records_no_cand = db.get_hotspot_profiles("run1")
        assert len(records_no_cand) == 0

        # Querying with the correct candidate_id should return it
        records_with_cand = db.get_hotspot_profiles("run1", candidate_id="cand-abc")
        assert len(records_with_cand) == 1
        assert records_with_cand[0]["candidate_id"] == "cand-abc"

    def test_payload_roundtrips_correctly(self, db: JouleDB) -> None:
        payload = {
            "schema_version": 2,
            "signal_quality": {"low_signal": True, "project_share": 0.05},
            "recommendations": ["Add harness workloads."],
        }
        db.record_hotspot_profile(
            run_id="run1",
            workload_id="all",
            kind="summary",
            payload=payload,
            created_at="2024-01-01T00:00:00",
        )
        records = db.get_hotspot_profiles("run1")
        assert records[0]["payload"] == payload

    def test_multiple_workloads_ordered_by_id(self, db: JouleDB) -> None:
        for i in range(5):
            db.record_hotspot_profile(
                run_id="run1",
                workload_id=f"w{i}",
                kind="workload",
                payload={"index": i},
                created_at="2024-01-01T00:00:00",
            )
        records = db.get_hotspot_profiles("run1")
        assert len(records) == 5
        assert [r["workload_id"] for r in records] == [f"w{i}" for i in range(5)]

    def test_different_run_ids_isolated(self, db: JouleDB) -> None:
        db.record_hotspot_profile(
            run_id="run1", workload_id="w1", kind="workload",
            payload={}, created_at="2024-01-01T00:00:00",
        )
        db.record_hotspot_profile(
            run_id="run2", workload_id="w1", kind="workload",
            payload={}, created_at="2024-01-01T00:00:00",
        )
        assert len(db.get_hotspot_profiles("run1")) == 1
        assert len(db.get_hotspot_profiles("run2")) == 1

    def test_unknown_run_id_returns_empty(self, db: JouleDB) -> None:
        records = db.get_hotspot_profiles("nonexistent-run")
        assert records == []

    def test_candidate_id_none_query_excludes_candidate_records(self, db: JouleDB) -> None:
        db.record_hotspot_profile(
            run_id="run1", workload_id="w1", kind="workload",
            payload={}, created_at="2024-01-01T00:00:00",
        )
        db.record_hotspot_profile(
            run_id="run1", workload_id="w2", kind="workload",
            payload={}, created_at="2024-01-01T00:00:00",
            candidate_id="cand-1",
        )
        # Default query (candidate_id=None) should only return the baseline record
        records = db.get_hotspot_profiles("run1")
        assert len(records) == 1
        assert records[0]["workload_id"] == "w1"

    def test_wrong_candidate_id_returns_empty(self, db: JouleDB) -> None:
        db.record_hotspot_profile(
            run_id="run1", workload_id="w1", kind="workload",
            payload={}, created_at="2024-01-01T00:00:00",
            candidate_id="cand-1",
        )
        records = db.get_hotspot_profiles("run1", candidate_id="cand-999")
        assert records == []


class TestSurrogateObservations:
    def test_save_and_retrieve(self, db: JouleDB) -> None:
        db.save_surrogate_observation(
            run_id="run1",
            target_key="myapp::target_fn",
            source_code="def f(): pass",
            targets={"energy": 1.5, "latency": 0.3},
            feature_schema_version=1,
        )
        obs = db.get_surrogate_observations(limit=10, target_key="myapp::target_fn")
        assert len(obs) == 1
        assert obs[0]["source"] == "def f(): pass"
        assert obs[0]["targets"]["energy"] == pytest.approx(1.5)

    def test_duplicate_source_hash_upserts(self, db: JouleDB) -> None:
        code = "def f(): pass"
        db.save_surrogate_observation(
            run_id="run1", target_key="k", source_code=code,
            targets={"energy": 1.0}, feature_schema_version=1,
        )
        db.save_surrogate_observation(
            run_id="run2", target_key="k", source_code=code,
            targets={"energy": 2.0}, feature_schema_version=1,
        )
        obs = db.get_surrogate_observations(limit=10, target_key="k")
        # Should be 1 record (upserted), with the latest value
        assert len(obs) == 1
        assert obs[0]["targets"]["energy"] == pytest.approx(2.0)

    def test_count_observations(self, db: JouleDB) -> None:
        for i in range(3):
            db.save_surrogate_observation(
                run_id="run1", target_key="k",
                source_code=f"def f{i}(): pass",
                targets={"energy": float(i)}, feature_schema_version=1,
            )
        assert db.count_surrogate_observations(target_key="k") == 3

    def test_count_all_observations(self, db: JouleDB) -> None:
        db.save_surrogate_observation(
            run_id="r1", target_key="k1", source_code="def a(): pass",
            targets={}, feature_schema_version=1,
        )
        db.save_surrogate_observation(
            run_id="r1", target_key="k2", source_code="def b(): pass",
            targets={}, feature_schema_version=1,
        )
        assert db.count_surrogate_observations() == 2

    def test_limit_respected(self, db: JouleDB) -> None:
        for i in range(10):
            db.save_surrogate_observation(
                run_id="r1", target_key="k",
                source_code=f"def f{i}(): pass",
                targets={}, feature_schema_version=1,
            )
        obs = db.get_surrogate_observations(limit=3, target_key="k")
        assert len(obs) == 3

    def test_feature_hints_roundtrip(self, db: JouleDB) -> None:
        hints = {"complexity": 0.7, "loop_depth": 2.0}
        db.save_surrogate_observation(
            run_id="r1", target_key="k", source_code="def f(): pass",
            targets={}, feature_hints=hints, feature_schema_version=2,
        )
        obs = db.get_surrogate_observations(limit=1, target_key="k")
        assert obs[0]["feature_hints"] == hints
        assert obs[0]["feature_schema_version"] == 2


class TestMeasurementsCache:
    def test_save_and_retrieve_cache(self, db: JouleDB) -> None:
        db.save_cached_measurement(
            source_hash="abc123",
            workload_id="bundle::w1",
            fidelity="f1",
            report_json='{"run_id": "r1"}',
            file_mtime=1000.0,
        )
        result = db.get_cached_measurement("abc123", "bundle::w1", "f1", file_mtime=1000.0)
        assert result is not None
        assert result["run_id"] == "r1"

    def test_stale_cache_returns_none(self, db: JouleDB) -> None:
        db.save_cached_measurement(
            source_hash="abc123", workload_id="w1", fidelity="f1",
            report_json='{}', file_mtime=1000.0,
        )
        # File has been modified since cache was saved
        result = db.get_cached_measurement("abc123", "w1", "f1", file_mtime=2000.0)
        assert result is None

    def test_cache_miss_returns_none(self, db: JouleDB) -> None:
        result = db.get_cached_measurement("nonexistent", "w1", "f1", file_mtime=0.0)
        assert result is None

    def test_clear_cache(self, db: JouleDB) -> None:
        db.save_cached_measurement(
            source_hash="abc", workload_id="w1", fidelity="f1",
            report_json='{}', file_mtime=0.0,
        )
        db.clear_measurements_cache()
        result = db.get_cached_measurement("abc", "w1", "f1", file_mtime=0.0)
        assert result is None

    def test_different_fidelity_is_separate_entry(self, db: JouleDB) -> None:
        db.save_cached_measurement("h", "w", "f1", '{"v":1}', 0.0)
        db.save_cached_measurement("h", "w", "f2", '{"v":2}', 0.0)
        r1 = db.get_cached_measurement("h", "w", "f1", 0.0)
        r2 = db.get_cached_measurement("h", "w", "f2", 0.0)
        assert r1["v"] == 1
        assert r2["v"] == 2
