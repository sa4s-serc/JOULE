"""Tests for InsightRecord generation thresholds and edge cases."""
from __future__ import annotations

import pytest

from joule.profiling.schema import (
    BlockMetrics,
    InsightRecord,
    CRITICAL_HOTSPOT_THRESHOLD,
    HOTSPOT_THRESHOLD,
    LOOP_DOMINANT_THRESHOLD,
)


def _make_block(
    *,
    block_type: str = "for_loop",
    line_start: int = 10,
    line_end: int = 20,
    hits: int = 100,
    time_s: float = 0.5,
    share: float = 0.5,
    nesting_level: int = 0,
    time_per_hit_ms: float = 5.0,
) -> BlockMetrics:
    return BlockMetrics(
        block_id=f"block:{block_type}:{line_start}",
        block_type=block_type,
        line_range=(line_start, line_end),
        description=f"{block_type} block",
        nesting_level=nesting_level,
        hits=hits,
        time_s=time_s,
        time_per_hit_ms=time_per_hit_ms,
        share_of_function=share,
    )


class TestCriticalHotspotInsight:
    def test_just_above_critical_threshold(self) -> None:
        block = _make_block(share=CRITICAL_HOTSPOT_THRESHOLD + 0.01)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "critical_hotspot" in kinds

    def test_exactly_at_critical_threshold_is_critical(self) -> None:
        # share > threshold, so exactly at threshold is NOT critical
        block = _make_block(share=CRITICAL_HOTSPOT_THRESHOLD)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "critical_hotspot" not in kinds

    def test_between_hotspot_and_critical(self) -> None:
        share = (HOTSPOT_THRESHOLD + CRITICAL_HOTSPOT_THRESHOLD) / 2
        block = _make_block(share=share)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "hotspot" in kinds
        assert "critical_hotspot" not in kinds

    def test_below_hotspot_threshold_no_insight(self) -> None:
        block = _make_block(share=HOTSPOT_THRESHOLD - 0.01)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "hotspot" not in kinds
        assert "critical_hotspot" not in kinds

    def test_critical_insight_has_evidence(self) -> None:
        block = _make_block(share=0.5)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        critical = next(i for i in insights if i.kind == "critical_hotspot")
        assert "share_of_function" in critical.evidence
        assert "time_s" in critical.evidence
        assert "hits" in critical.evidence

    def test_critical_insight_has_line_range(self) -> None:
        block = _make_block(share=0.5, line_start=15, line_end=25)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        critical = next(i for i in insights if i.kind == "critical_hotspot")
        assert critical.line_range == (15, 25)


class TestLoopDominantInsight:
    def test_loop_dominant_just_above_threshold(self) -> None:
        loop_time = LOOP_DOMINANT_THRESHOLD + 0.01
        type_totals = {"for_loop": loop_time}
        block = _make_block(block_type="for_loop", share=loop_time)
        insights = InsightRecord.from_granular_data([block], type_totals, 1.0)
        kinds = [i.kind for i in insights]
        assert "loop_dominant" in kinds

    def test_loop_dominant_exactly_at_threshold_not_triggered(self) -> None:
        # loop_time / total > threshold, so exactly at threshold is NOT triggered
        type_totals = {"for_loop": LOOP_DOMINANT_THRESHOLD}
        block = _make_block(block_type="for_loop", share=LOOP_DOMINANT_THRESHOLD)
        insights = InsightRecord.from_granular_data([block], type_totals, 1.0)
        kinds = [i.kind for i in insights]
        assert "loop_dominant" not in kinds

    def test_while_loop_counts_toward_loop_dominant(self) -> None:
        type_totals = {"for_loop": 0.3, "while_loop": 0.3}
        block = _make_block(block_type="for_loop", share=0.6)
        insights = InsightRecord.from_granular_data([block], type_totals, 1.0)
        kinds = [i.kind for i in insights]
        assert "loop_dominant" in kinds


class TestHighComplexityInsight:
    def test_loop_with_high_per_iteration_cost(self) -> None:
        block = _make_block(block_type="for_loop", time_per_hit_ms=2.0, share=0.4)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "high_complexity" in kinds

    def test_loop_with_low_per_iteration_cost_no_insight(self) -> None:
        block = _make_block(block_type="for_loop", time_per_hit_ms=0.5, share=0.4)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "high_complexity" not in kinds

    def test_non_loop_block_not_flagged_as_complex(self) -> None:
        block = _make_block(block_type="if_branch", time_per_hit_ms=5.0, share=0.4)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "high_complexity" not in kinds


class TestDeepNestingInsight:
    def test_nesting_level_3_triggers_insight(self) -> None:
        block = _make_block(nesting_level=3, share=0.1)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "deep_nesting" in kinds

    def test_nesting_level_2_no_insight(self) -> None:
        block = _make_block(nesting_level=2, share=0.1)
        insights = InsightRecord.from_granular_data([block], {}, 1.0)
        kinds = [i.kind for i in insights]
        assert "deep_nesting" not in kinds

    def test_deep_nesting_evidence_has_max_nesting(self) -> None:
        blocks = [
            _make_block(nesting_level=3, share=0.1, line_start=10),
            _make_block(nesting_level=5, share=0.05, line_start=20),
        ]
        insights = InsightRecord.from_granular_data(blocks, {}, 1.0)
        dn = next(i for i in insights if i.kind == "deep_nesting")
        assert dn.evidence["max_nesting"] == 5


class TestComprehensionInsight:
    def test_list_comprehension_triggers_insight(self) -> None:
        type_totals = {"list_comprehension": 0.3}
        block = _make_block(block_type="list_comprehension", share=0.3)
        insights = InsightRecord.from_granular_data([block], type_totals, 1.0)
        kinds = [i.kind for i in insights]
        assert "comprehension_usage" in kinds

    def test_zero_comprehension_time_no_insight(self) -> None:
        type_totals = {"list_comprehension": 0.0}
        block = _make_block(block_type="for_loop", share=0.5)
        insights = InsightRecord.from_granular_data([block], type_totals, 1.0)
        kinds = [i.kind for i in insights]
        assert "comprehension_usage" not in kinds


class TestEmptyInputs:
    def test_empty_blocks_returns_empty(self) -> None:
        insights = InsightRecord.from_granular_data([], {}, 1.0)
        assert insights == []

    def test_zero_total_time_no_loop_dominant(self) -> None:
        block = _make_block(block_type="for_loop", share=0.9)
        # total_time=0 → division guard prevents loop_dominant
        insights = InsightRecord.from_granular_data([block], {"for_loop": 0.9}, 0.0)
        kinds = [i.kind for i in insights]
        assert "loop_dominant" not in kinds


class TestInsightSerialization:
    def test_to_dict_required_keys(self) -> None:
        insight = InsightRecord(kind="test", severity="info", message="hello")
        d = insight.to_dict()
        assert d["kind"] == "test"
        assert d["severity"] == "info"
        assert d["message"] == "hello"

    def test_to_dict_optional_fields_omitted_when_empty(self) -> None:
        insight = InsightRecord(kind="test", severity="info", message="hello")
        d = insight.to_dict()
        assert "evidence" not in d
        assert "line_range" not in d
        assert "block_type" not in d

    def test_to_dict_line_range_serialized_as_list(self) -> None:
        insight = InsightRecord(
            kind="test", severity="info", message="hello",
            line_range=(10, 20),
        )
        d = insight.to_dict()
        assert d["line_range"] == [10, 20]
