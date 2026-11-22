"""Tests for tools/rival/compare_traces.py using real Session + TraceWriter traces."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from floorbot import clear_encounter

from overload.agent.client import TacticClient
from overload.agent.selector import FixedSchedule, LiveSelector
from overload.game.flow import MIN_FUSE_TICKS, Session
from overload.paths import ROOT
from overload.session.trace import TraceWriter
from overload.sim.arena import arena_id
from overload.sim.campaign import Campaign
from overload.sim.difficulty import PRESETS
from overload.sim.inputs import IDLE, InputFrame

SPEC = importlib.util.spec_from_file_location(
    "compare_traces", ROOT / "tools" / "rival" / "compare_traces.py"
)
assert SPEC is not None and SPEC.loader is not None
compare_traces = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compare_traces)


class FakeRivalTransport:
    """Configurable fake transport returning valid, fixture, fallback, or HTTP error replies."""

    def __init__(self, responses: dict[int, tuple[int, dict]]) -> None:
        self.responses = responses

    def __call__(self, method: str, url: str, body: dict | None, timeout: float):
        if url.endswith("/sessions"):
            return 201, {"session_id": "sess-test-1"}
        assert body is not None
        encounter = body["encounter"]
        status, template = self.responses[encounter]
        reply = {
            "session_id": "sess-test-1",
            "request_id": body["request_id"],
            "encounter": encounter,
            **template,
        }
        return status, reply


def _wait_in_fuse_box(session: Session, ticks: int) -> None:
    for _ in range(ticks):
        session.tick(IDLE)


def _trigger_retry(session: Session) -> None:
    session.campaign.world.player.charge = 0
    session.tick(IDLE)
    assert session.campaign.world.outcome == "down"
    session.tick(InputFrame(restart=True))


def _generate_trace(
    path: Path,
    *,
    seed: int,
    selector,
    session_id: str | None = "anon-session",
    difficulty: str = "medium",
    retries_by_encounter: dict[int, int] | None = None,
    fuse_pairs_in_box: dict[int, list[tuple[str, str]]] | None = None,
    failed_fuse_in_box: int | None = None,
    extra_wait_ticks: int = 0,
    stop_after_encounter: int | None = None,
    close_session: bool = True,
) -> Session:
    campaign = Campaign(seed, PRESETS[difficulty])
    writer = TraceWriter(
        path,
        condition=selector.condition,
        tuning_id=campaign.tuning.tuning_id(),
        arena_id=arena_id(campaign.arena),
    )
    session = Session(campaign, selector, writer, session_id)
    retries_map = retries_by_encounter or {}
    fuse_map = fuse_pairs_in_box or {}

    for enc in (1, 2, 3):
        for _ in range(retries_map.get(enc, 0)):
            _trigger_retry(session)
        clear_encounter(session)
        if stop_after_encounter == enc:
            if enc < 3 and isinstance(selector, LiveSelector) and (enc + 1) in selector.pending:
                selector.pending[enc + 1].future.result(timeout=5)
                session.tick(IDLE)
            break
        if enc < 3:
            if isinstance(selector, LiveSelector) and (enc + 1) in selector.pending:
                selector.pending[enc + 1].future.result(timeout=5)
            _wait_in_fuse_box(session, MIN_FUSE_TICKS + extra_wait_ticks)
            if failed_fuse_in_box == enc:
                session.fuse("bulwark", "magnet")
            for a, b in fuse_map.get(enc, ()):
                for base in (a, b):
                    if base not in session.campaign.world.unlocked:
                        session.campaign.world.unlocked.append(base)
                    session.campaign.world.bank[base] = session.campaign.world.bank.get(base, 0) + 2
                result = session.fuse(a, b)
                assert result == "fused"
            assert session.ready()
            assert session.confirm() is not None

    if close_session:
        session.close()
    return session


def _live_selector(responses: dict[int, tuple[int, dict]]) -> tuple[LiveSelector, TacticClient]:
    client = TacticClient("http://rival.test", transport=FakeRivalTransport(responses))
    selector = LiveSelector(client, client.start_session())
    return selector, client


def test_percentile_is_nearest_rank() -> None:
    assert compare_traces.percentile([], 0.5) is None
    assert compare_traces.percentile([], 0.95) is None
    assert compare_traces.percentile([420], 0.5) == 420
    assert compare_traces.percentile([420], 0.95) == 420
    assert compare_traces.percentile([300, 100, 200], 0.5) == 200
    assert compare_traces.percentile(list(range(1, 21)), 0.95) == 19
    eighteen = list(range(1, 19))
    assert compare_traces.percentile(eighteen, 0.5) == 9
    assert compare_traces.percentile(eighteen, 0.95) == 18


def test_live_and_fixed_real_traces_paired_comparison(tmp_path: Path) -> None:
    live_path = tmp_path / "p1-live.jsonl"
    fixed_path = tmp_path / "p1-fixed.jsonl"

    selector, client = _live_selector(
        {
            2: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "pressure",
                    "evidence_ids": ["e1.far_share"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                    "usage": {"input_tokens": 515, "output_tokens": 35},
                    "cost_usd_estimate": 0.00158,
                },
            ),
            3: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "spacing",
                    "evidence_ids": ["e2.near_share", "e2.teleport_uses"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                    "usage": {"input_tokens": 695, "output_tokens": 40},
                    "cost_usd_estimate": 0.00192,
                },
            ),
        }
    )
    try:
        _generate_trace(
            live_path,
            seed=101,
            selector=selector,
            session_id=selector.session_id,
            retries_by_encounter={2: 1, 3: 2},
            fuse_pairs_in_box={
                1: [("spark", "blink")],
                2: [("spark", "burst"), ("spark", "blink")],
            },
            failed_fuse_in_box=1,
            extra_wait_ticks=30,
        )
    finally:
        client.close()

    _generate_trace(
        fixed_path,
        seed=101,
        selector=FixedSchedule("B"),
        session_id=None,
        retries_by_encounter={3: 1},
        fuse_pairs_in_box={1: [("spark", "blink")]},
        extra_wait_ticks=15,
    )

    report = compare_traces.compare_traces([live_path, fixed_path])
    live_summary, fixed_summary = report["traces"]

    assert live_summary["file"] == "p1-live.jsonl"
    assert live_summary["condition"] == "live"
    assert live_summary["seed"] == 101
    assert live_summary["tuning_id"] == PRESETS["medium"].tuning_id()
    assert live_summary["stage"] == "ending"
    assert live_summary["completed"] is True
    assert live_summary["reached_encounter"] == 3
    assert live_summary["protocols"] == {"1": "lateral", "2": "pressure", "3": "spacing"}
    assert len(live_summary["decisions"]) == 2
    assert live_summary["decisions"][0]["tactic"] == "pressure"
    assert live_summary["decisions"][0]["evidence_ids"] == ["e1.far_share"]
    assert live_summary["decisions"][1]["tactic"] == "spacing"
    assert live_summary["decisions"][1]["evidence_ids"] == ["e2.near_share", "e2.teleport_uses"]
    assert live_summary["live_valid_count"] == 2
    assert live_summary["fallback_count"] == 0
    assert live_summary["fallback_reasons"] == {}
    assert live_summary["latency_p50_ms"] is not None
    assert live_summary["latency_p95_ms"] is not None
    assert live_summary["total_input_tokens"] == 1210
    assert live_summary["total_output_tokens"] == 75
    assert live_summary["total_cost_usd"] == 0.0035
    assert live_summary["total_retries"] == 3
    assert live_summary["retries_by_sector"] == {"1": 0, "2": 1, "3": 2}
    assert live_summary["total_fusion_rolls"] == 3
    assert sum(live_summary["fusion_rolls"].values()) == 3
    assert live_summary["fusion_failed_attempts"] == 1
    assert set(live_summary["encounters"]) == {"1", "2", "3"}
    live_enc = live_summary["encounters"]
    assert live_enc["1"]["ticks"] == live_enc["1"]["world_tick"]
    assert live_enc["2"]["ticks"] == live_enc["2"]["world_tick"] - (
        live_enc["1"]["world_tick"] + MIN_FUSE_TICKS + 30
    )
    assert live_enc["3"]["ticks"] == live_enc["3"]["world_tick"] - (
        live_enc["2"]["world_tick"] + MIN_FUSE_TICKS + 30
    )
    for enc_info in live_enc.values():
        assert enc_info["ticks"] > 0
        assert enc_info["seconds"] == round(enc_info["ticks"] / 60, 2)

    fixed_enc = fixed_summary["encounters"]
    assert fixed_enc["2"]["ticks"] == fixed_enc["2"]["world_tick"] - (
        fixed_enc["1"]["world_tick"] + MIN_FUSE_TICKS + 15
    )
    assert fixed_enc["3"]["ticks"] == fixed_enc["3"]["world_tick"] - (
        fixed_enc["2"]["world_tick"] + MIN_FUSE_TICKS + 15
    )

    assert fixed_summary["condition"] == "fixed"
    assert fixed_summary["schedule"] == "B"
    assert fixed_summary["protocols"] == {"1": "lateral", "2": "spacing", "3": "pressure"}
    assert fixed_summary["schedule_count"] == 2
    assert fixed_summary["live_valid_count"] == 0
    assert fixed_summary["fallback_count"] == 0
    assert fixed_summary["total_cost_usd"] is None
    assert fixed_summary["total_retries"] == 1
    assert fixed_summary["total_fusion_rolls"] == 1

    assert len(report["paired_comparisons"]) == 1
    paired = report["paired_comparisons"][0]
    assert paired["seed"] == 101
    assert paired["tuning_id"] == PRESETS["medium"].tuning_id()
    assert paired["has_fallback_confound"] is False
    assert paired["confounds"] == []
    assert paired["pairs"][0]["differing_encounters"] == [2, 3]
    assert paired["pairs"][0]["retries_delta"] == 2
    assert paired["pairs"][0]["fusion_rolls_delta"] == 2

    md = compare_traces.format_markdown(report)
    assert "## Paired Comparison" in md
    assert "### Seed 101" in md
    assert "#### Fallback and Validity Confounds" in md
    assert "None (all live adaptation decisions valid" in md


def test_live_fallback_is_never_reclassified_and_flagged_as_confound(tmp_path: Path) -> None:
    live_path = tmp_path / "p2-live.jsonl"
    fixed_path = tmp_path / "p2-fixed.jsonl"

    selector, client = _live_selector(
        {
            2: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "pressure",
                    "evidence_ids": ["e1.far_share"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                    "usage": {"input_tokens": 500, "output_tokens": 30},
                    "cost_usd_estimate": 0.0015,
                },
            ),
            3: (
                200,
                {
                    "status": "timeout",
                    "tactic_id": None,
                    "evidence_ids": [],
                    "source": "live",
                },
            ),
        }
    )
    try:
        _generate_trace(live_path, seed=202, selector=selector, session_id=selector.session_id)
    finally:
        client.close()

    _generate_trace(fixed_path, seed=202, selector=FixedSchedule("A"), session_id=None)

    report = compare_traces.compare_traces([live_path, fixed_path])
    live_summary = report["traces"][0]
    assert live_summary["live_valid_count"] == 1
    assert live_summary["fallback_count"] == 1
    assert live_summary["fallback_reasons"] == {"service_timeout": 1}
    assert live_summary["decisions"][1]["tactic"] == "lateral"
    assert live_summary["decisions"][1]["source"] == "fallback"
    assert live_summary["decisions"][1]["reason"] == "service_timeout"

    paired = report["paired_comparisons"][0]
    assert paired["has_fallback_confound"] is True
    assert any(
        "fell back to neutral on encounter 3 (reason: service_timeout)" in msg
        for msg in paired["confounds"]
    )
    md = compare_traces.format_markdown(report)
    assert "CONFOUND: live trace p2-live.jsonl fell back to neutral on encounter 3" in md
    assert "service_timeout=1" in md


def test_fixture_source_is_kept_separate_from_live_and_flagged(tmp_path: Path) -> None:
    live_path = tmp_path / "fixture-run.jsonl"
    fixed_path = tmp_path / "fixed-run.jsonl"

    selector, client = _live_selector(
        {
            2: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "pressure",
                    "evidence_ids": ["e1.far_share"],
                    "source": "fixture",
                    "resolved_model": "fixture",
                    "usage": {"input_tokens": 410, "output_tokens": 22},
                    "cost_usd_estimate": 0.0012,
                },
            ),
            3: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "spacing",
                    "evidence_ids": ["e2.near_share"],
                    "source": "fixture",
                    "resolved_model": "fixture",
                    "usage": {"input_tokens": 520, "output_tokens": 28},
                    "cost_usd_estimate": 0.0015,
                },
            ),
        }
    )
    try:
        _generate_trace(live_path, seed=303, selector=selector, session_id=selector.session_id)
    finally:
        client.close()

    _generate_trace(fixed_path, seed=303, selector=FixedSchedule("A"), session_id=None)

    report = compare_traces.compare_traces([live_path, fixed_path])
    fixture_summary = report["traces"][0]
    assert fixture_summary["live_valid_count"] == 0
    assert fixture_summary["fixture_valid_count"] == 2
    assert fixture_summary["latency_p50_ms"] is None

    overall = report["overall_live"]
    assert overall["live_valid_count"] == 0
    assert overall["fixture_valid_count"] == 2
    assert overall["total_input_tokens"] == 0
    assert overall["total_output_tokens"] == 0
    assert overall["total_cost_usd"] is None

    paired = report["paired_comparisons"][0]
    assert any("used fixture provider" in msg for msg in paired["confounds"])

    md = compare_traces.format_markdown(report)
    assert "| Fixture decisions (excluded from live metrics) | 2 |" in md


def test_zero_reported_cost_is_distinguished_from_none(tmp_path: Path) -> None:
    live_path = tmp_path / "zero-cost-live.jsonl"
    selector, client = _live_selector(
        {
            2: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "pressure",
                    "evidence_ids": ["e1.far_share"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                    "usage": {"input_tokens": 100, "output_tokens": 10},
                    "cost_usd_estimate": 0.0,
                },
            ),
            3: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "spacing",
                    "evidence_ids": ["e2.near_share"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                    "usage": {"input_tokens": 120, "output_tokens": 12},
                    "cost_usd_estimate": 0.0,
                },
            ),
        }
    )
    try:
        _generate_trace(live_path, seed=304, selector=selector, session_id=selector.session_id)
    finally:
        client.close()

    report = compare_traces.compare_traces([live_path])
    assert report["traces"][0]["total_cost_usd"] == 0.0
    assert report["overall_live"]["total_cost_usd"] == 0.0
    assert "USD 0.000000" in compare_traces.format_markdown(report)


def test_mid_sector_fusion_rolled_back_on_retry_is_not_double_counted(tmp_path: Path) -> None:
    trace_path = tmp_path / "retry-fusion.jsonl"
    campaign = Campaign(707, PRESETS["medium"])
    writer = TraceWriter(
        trace_path,
        condition="fixed",
        tuning_id=campaign.tuning.tuning_id(),
        arena_id=arena_id(campaign.arena),
    )
    session = Session(campaign, FixedSchedule("A"), writer, None)

    for base in ("spark", "blink"):
        session.campaign.world.unlocked.append(base)
        session.campaign.world.bank[base] = 2
    assert session.fuse("spark", "blink") == "fused"

    # Retry rolls back the mid-sector fusion, then fuse again after retry and clear sector 1.
    _trigger_retry(session)
    for base in ("spark", "blink"):
        if base not in session.campaign.world.unlocked:
            session.campaign.world.unlocked.append(base)
        session.campaign.world.bank[base] = 2
    assert session.fuse("spark", "blink") == "fused"
    clear_encounter(session)

    # Fuse in the Fuse Box (committed to sector 2 checkpoint), then retry sector 2.
    _wait_in_fuse_box(session, MIN_FUSE_TICKS)
    for base in ("spark", "burst"):
        if base not in session.campaign.world.unlocked:
            session.campaign.world.unlocked.append(base)
        session.campaign.world.bank[base] = 2
    assert session.fuse("spark", "burst") == "fused"
    assert session.confirm() is not None

    _trigger_retry(session)
    clear_encounter(session)
    _wait_in_fuse_box(session, MIN_FUSE_TICKS)
    assert session.confirm() is not None
    clear_encounter(session)
    session.close()

    report = compare_traces.compare_traces([trace_path])
    summary = report["traces"][0]
    assert summary["fusion_rolled_back_rolls"] == 1
    assert summary["total_fusion_rolls"] == 2
    assert sum(summary["fusion_rolls"].values()) == 2
    assert "rolled back on retry: 1" in compare_traces.format_markdown(report)


def test_multi_session_concatenated_trace_is_rejected(tmp_path: Path, capsys) -> None:
    concat_path = tmp_path / "concat.jsonl"
    _generate_trace(concat_path, seed=801, selector=FixedSchedule("A"), session_id=None)
    _generate_trace(concat_path, seed=801, selector=FixedSchedule("A"), session_id=None)

    assert compare_traces.main([str(concat_path)]) == 2
    assert "multiple sessions" in capsys.readouterr().err

    conflict_path = tmp_path / "conflict.jsonl"
    conflict_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "encounter_start",
                        "encounter": 1,
                        "condition": "live",
                        "tuning_id": "t1",
                        "arena_id": "a1",
                        "config_hash": "c1",
                        "seed": 1,
                        "session_id": "s1",
                    }
                ),
                json.dumps(
                    {
                        "event": "decision",
                        "encounter": 2,
                        "condition": "live",
                        "tuning_id": "t1",
                        "arena_id": "a1",
                        "config_hash": "c1",
                        "session_id": "s2",
                        "tactic": "pressure",
                        "source": "live",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert compare_traces.main([str(conflict_path)]) == 2
    assert "conflicting metadata" in capsys.readouterr().err


def test_defensive_hardening_edge_cases(tmp_path: Path, capsys) -> None:
    # session_end with stage="ending" but no "ending" event reports missing_ending.
    no_ending = tmp_path / "no-ending.jsonl"
    no_ending.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "encounter_start",
                        "encounter": 1,
                        "condition": "fixed",
                        "tuning_id": "t1",
                        "arena_id": "a1",
                        "config_hash": "c1",
                        "seed": 901,
                    }
                ),
                json.dumps(
                    {
                        "event": "session_end",
                        "stage": "ending",
                        "encounter": 3,
                        "retries": {"1": 0, "2": 0, "3": 0},
                        "condition": "fixed",
                        "tuning_id": "t1",
                        "arena_id": "a1",
                        "config_hash": "c1",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    res_no_ending = compare_traces.compare_traces([no_ending])["traces"][0]
    assert res_no_ending["stage"] == "incomplete"
    assert res_no_ending["incomplete_reason"] == "missing_ending"

    # Missing arena_id/config_hash in paired traces are flagged, and non-string evidence_ids work.
    live_sparse = tmp_path / "sparse-live.jsonl"
    fixed_sparse = tmp_path / "sparse-fixed.jsonl"
    live_sparse.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "encounter_start",
                        "encounter": 1,
                        "protocol": "lateral",
                        "seed": 902,
                        "condition": "live",
                        "tuning_id": "t9",
                    }
                ),
                json.dumps(
                    {
                        "event": "decision",
                        "encounter": 2,
                        "tactic": "pressure",
                        "source": "live",
                        "reason": None,
                        "evidence_ids": [123, None, "e1.far_share"],
                        "condition": "live",
                        "tuning_id": "t9",
                    }
                ),
                json.dumps(
                    {
                        "event": "decision",
                        "encounter": 3,
                        "tactic": "spacing",
                        "source": "live",
                        "reason": None,
                        "evidence_ids": ["e2.near_share"],
                        "condition": "live",
                        "tuning_id": "t9",
                    }
                ),
                json.dumps(
                    {
                        "event": "ending",
                        "protocols": {"1": "lateral", "2": "pressure", "3": "spacing"},
                        "condition": "live",
                        "tuning_id": "t9",
                    }
                ),
                json.dumps(
                    {
                        "event": "session_end",
                        "stage": "ending",
                        "encounter": 3,
                        "retries": {"1": 0, "2": 0, "3": 0},
                        "condition": "live",
                        "tuning_id": "t9",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fixed_sparse.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "encounter_start",
                        "encounter": 1,
                        "protocol": "lateral",
                        "seed": 902,
                        "condition": "fixed",
                        "tuning_id": "t9",
                    }
                ),
                json.dumps(
                    {
                        "event": "ending",
                        "protocols": {"1": "lateral", "2": "pressure", "3": "spacing"},
                        "condition": "fixed",
                        "tuning_id": "t9",
                    }
                ),
                json.dumps(
                    {
                        "event": "session_end",
                        "stage": "ending",
                        "encounter": 3,
                        "retries": {"1": 0, "2": 0, "3": 0},
                        "condition": "fixed",
                        "tuning_id": "t9",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    sparse_report = compare_traces.compare_traces([live_sparse, fixed_sparse])
    confounds = sparse_report["paired_comparisons"][0]["confounds"]
    assert any("missing arena_id" in msg for msg in confounds)
    assert any("missing config_hash" in msg for msg in confounds)
    md = compare_traces.format_markdown(sparse_report)
    assert "123, None, e1.far_share" in md

    # Unwritable --out target (an existing directory) returns exit code 2 cleanly.
    assert compare_traces.main([str(no_ending), "--out", str(tmp_path)]) == 2
    assert "unable to write output file" in capsys.readouterr().err


def test_incomplete_and_truncated_traces_reported_honestly(tmp_path: Path) -> None:
    stopped_early = tmp_path / "stopped-early.jsonl"
    _generate_trace(
        stopped_early,
        seed=404,
        selector=FixedSchedule("A"),
        stop_after_encounter=1,
        close_session=True,
    )

    truncated_mid = tmp_path / "truncated-mid.jsonl"
    _generate_trace(
        truncated_mid,
        seed=405,
        selector=FixedSchedule("A"),
        stop_after_encounter=2,
        close_session=False,
    )

    missing_close = tmp_path / "missing-close.jsonl"
    _generate_trace(
        missing_close,
        seed=406,
        selector=FixedSchedule("A"),
        close_session=False,
    )

    report = compare_traces.compare_traces([stopped_early, truncated_mid, missing_close])
    s1, s2, s3 = report["traces"]

    assert s1["stage"] == "incomplete"
    assert s1["completed"] is False
    assert s1["incomplete_reason"] == "stopped_at_fuse_box"
    assert s1["reached_encounter"] == 1

    assert s2["stage"] == "incomplete"
    assert s2["completed"] is False
    assert s2["incomplete_reason"] == "missing_ending_and_session_end"
    assert s2["reached_encounter"] == 2

    assert s3["stage"] == "incomplete"
    assert s3["completed"] is False
    assert s3["incomplete_reason"] == "missing_session_end"
    assert s3["reached_encounter"] == 3


def test_paired_comparison_requires_matching_seed_and_tuning_id(tmp_path: Path) -> None:
    live_med = tmp_path / "live-med.jsonl"
    fixed_diff_seed = tmp_path / "fixed-diff-seed.jsonl"
    fixed_hard = tmp_path / "fixed-hard.jsonl"

    selector, client = _live_selector(
        {
            2: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "pressure",
                    "evidence_ids": ["e1.far_share"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                },
            ),
            3: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "spacing",
                    "evidence_ids": ["e2.near_share"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                },
            ),
        }
    )
    try:
        _generate_trace(live_med, seed=501, selector=selector, difficulty="medium")
    finally:
        client.close()

    _generate_trace(fixed_diff_seed, seed=502, selector=FixedSchedule("A"), difficulty="medium")
    _generate_trace(fixed_hard, seed=501, selector=FixedSchedule("A"), difficulty="hard")

    report = compare_traces.compare_traces([live_med, fixed_diff_seed, fixed_hard])
    assert report["paired_comparisons"] == []
    assert "## Paired Comparison" not in compare_traces.format_markdown(report)


def test_cli_json_and_out_flags(tmp_path: Path, capsys) -> None:
    live_path = tmp_path / "cli-live.jsonl"
    fixed_path = tmp_path / "cli-fixed.jsonl"
    selector, client = _live_selector(
        {
            2: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "pressure",
                    "evidence_ids": ["e1.far_share"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                    "usage": {"input_tokens": 510, "output_tokens": 32},
                    "cost_usd_estimate": 0.0015,
                },
            ),
            3: (
                200,
                {
                    "status": "ok",
                    "tactic_id": "lateral",
                    "evidence_ids": ["e2.mid_share"],
                    "source": "live",
                    "resolved_model": "gemini-3.5-flash-lite",
                    "usage": {"input_tokens": 680, "output_tokens": 36},
                    "cost_usd_estimate": 0.0018,
                },
            ),
        }
    )
    try:
        _generate_trace(live_path, seed=601, selector=selector)
    finally:
        client.close()
    _generate_trace(fixed_path, seed=601, selector=FixedSchedule("A"))

    # Stdout JSON
    rc = compare_traces.main([str(live_path), str(fixed_path), "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert len(parsed["traces"]) == 2
    assert len(parsed["paired_comparisons"]) == 1

    # --out JSON
    out_json = tmp_path / "nested" / "report.json"
    rc = compare_traces.main([str(live_path), str(fixed_path), "--json", "--out", str(out_json)])
    assert rc == 0
    assert out_json.is_file()
    assert json.loads(out_json.read_text(encoding="utf-8")) == parsed

    # --out Markdown
    out_md = tmp_path / "nested" / "report.md"
    rc = compare_traces.main([str(live_path), str(fixed_path), "--out", str(out_md)])
    assert rc == 0
    md = out_md.read_text(encoding="utf-8")
    assert "# Overload Trace Comparison" in md
    assert "## Paired Comparison" in md


def test_malformed_and_missing_inputs_exit_nonzero(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "does-not-exist.jsonl"
    assert compare_traces.main([str(missing)]) != 0
    assert "does not exist" in capsys.readouterr().err

    assert compare_traces.main([str(tmp_path)]) != 0
    assert "not a file" in capsys.readouterr().err

    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n   \n", encoding="utf-8")
    assert compare_traces.main([str(empty)]) != 0
    assert "no JSONL records" in capsys.readouterr().err

    bad_json = tmp_path / "bad.jsonl"
    bad_json.write_text('{"event": "encounter_start"}\n{not json\n', encoding="utf-8")
    assert compare_traces.main([str(bad_json)]) != 0
    assert "bad.jsonl:2: invalid JSON" in capsys.readouterr().err

    missing_event = tmp_path / "no-event.jsonl"
    missing_event.write_text('{"condition": "live"}\n', encoding="utf-8")
    assert compare_traces.main([str(missing_event)]) != 0
    assert "string field 'event'" in capsys.readouterr().err


def test_cli_runs_with_stdlib_only() -> None:
    result = subprocess.run(
        [sys.executable, "-I", str(ROOT / "tools" / "rival" / "compare_traces.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--json" in result.stdout
    assert "--out" in result.stdout
