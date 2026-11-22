"""Compare Overload JSONL session traces for playtest and BI analysis.

Pure standard-library CLI reading one or more trace files written by
overload.session.trace.TraceWriter and overload.game.flow.Session.

Usage:
    uv run python tools/rival/compare_traces.py logs/p1-live.jsonl logs/p1-fixed.jsonl
    uv run python tools/rival/compare_traces.py logs/trace-*.jsonl --json --out logs/report.json

Evidence sources (live, fixture, fallback, schedule, neutral) are always kept strictly
separated and never reclassified.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TICK_RATE = 60
MIN_FUSE_TICKS = 300  # 5.0 s hold at 60 Hz, matching src/overload/game/flow.py
RARITIES = ("rare", "epic", "legendary")
SESSION_META_FIELDS = ("condition", "tuning_id", "arena_id", "config_hash", "seed", "session_id")


class TraceError(ValueError):
    """Raised when a trace file is missing, unreadable, empty, malformed, or multi-session."""


def percentile(values: list[float] | list[int], q: float) -> float | None:
    """Nearest-rank percentile matching tools/rival/live_suite.py."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _is_fixture_decision(decision: dict[str, Any]) -> bool:
    if decision.get("source") == "fixture":
        return True
    model = decision.get("model")
    return isinstance(model, str) and model.startswith("fixture")


def load_trace(path: Path) -> list[dict[str, Any]]:
    """Read and validate JSONL lines from one trace file."""
    if not path.exists():
        raise TraceError(f"{path}: trace file does not exist")
    if not path.is_file():
        raise TraceError(f"{path}: path is not a file")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TraceError(f"{path}: unable to read trace file ({exc})") from exc

    rows: list[dict[str, Any]] = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise TraceError(f"{path}:{lineno}: invalid JSON ({exc.msg})") from exc
        if not isinstance(parsed, dict) or not isinstance(parsed.get("event"), str):
            raise TraceError(f"{path}:{lineno}: expected a JSON object with string field 'event'")
        rows.append(parsed)

    if not rows:
        raise TraceError(f"{path}: trace file contains no JSONL records")
    return rows


def _first_field(rows: list[dict[str, Any]], key: str) -> Any:
    for row in rows:
        value = row.get(key)
        if value is not None:
            return value
    return None


def summarize_trace(path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute per-trace metadata, decisions, and aggregates strictly from raw JSONL lines."""
    seen_meta: dict[str, Any] = {}
    encounter_1_starts = 0
    session_end_count = 0

    for row in rows:
        for field in SESSION_META_FIELDS:
            value = row.get(field)
            if value is not None:
                if field == "seed":
                    if not (_is_int(value) or isinstance(value, str)):
                        raise TraceError(
                            f"{path}: invalid metadata field 'seed' "
                            f"(expected int or string, got {type(value).__name__})"
                        )
                elif not isinstance(value, str):
                    raise TraceError(
                        f"{path}: invalid metadata field '{field}' "
                        f"(expected string, got {type(value).__name__})"
                    )
                if field in seen_meta and seen_meta[field] != value:
                    raise TraceError(
                        f"{path}: multiple sessions or conflicting metadata in one trace file "
                        f"({field}: {seen_meta[field]!r} vs {value!r})"
                    )
                seen_meta[field] = value
        event = row["event"]
        if event == "encounter_start" and _is_int(row.get("encounter")) and row["encounter"] == 1:
            encounter_1_starts += 1
            if encounter_1_starts > 1:
                raise TraceError(
                    f"{path}: multiple sessions detected in one trace file "
                    "(repeated encounter 1 start)"
                )
        elif event == "session_end":
            session_end_count += 1
            if session_end_count > 1:
                raise TraceError(
                    f"{path}: multiple sessions detected in one trace file (repeated session_end)"
                )

    condition = _first_field(rows, "condition")
    tuning_id = _first_field(rows, "tuning_id")
    arena_id = _first_field(rows, "arena_id")
    config_hash = _first_field(rows, "config_hash")
    session_id = _first_field(rows, "session_id")
    seed = _first_field(rows, "seed")

    protocols: dict[int, str] = {}
    decisions: list[dict[str, Any]] = []
    entered_encounters: set[int] = set()
    decision_encounters: set[int] = set()
    extra_wait: dict[int, int] = {}
    end_ticks: dict[int, int] = {}
    retries_by_sector: dict[int, int] = {}
    fusion_rolls: dict[str, int] = {rarity: 0 for rarity in RARITIES}
    pending_sector_fusions: list[str] = []
    fusion_rolled_back_rolls = 0
    fusion_failed_attempts = 0
    in_encounter = False
    schedule: str | None = None
    has_ending = False
    has_session_end = False
    session_end_stage: str | None = None

    for row in rows:
        event = row["event"]
        encounter = row.get("encounter")

        if event == "decision":
            if _is_int(encounter):
                decision_encounters.add(encounter)
            reason = row.get("reason")
            if reason is not None and not isinstance(reason, str):
                raise TraceError(
                    f"{path}: invalid decision field 'reason' "
                    f"(expected string or null, got {type(reason).__name__})"
                )
            source = row.get("source")
            if source is not None and not isinstance(source, str):
                raise TraceError(
                    f"{path}: invalid decision field 'source' "
                    f"(expected string or null, got {type(source).__name__})"
                )
            tactic = row.get("tactic")
            if tactic is not None and not isinstance(tactic, str):
                raise TraceError(
                    f"{path}: invalid decision field 'tactic' "
                    f"(expected string or null, got {type(tactic).__name__})"
                )
            model = row.get("model")
            if model is not None and not isinstance(model, str):
                raise TraceError(
                    f"{path}: invalid decision field 'model' "
                    f"(expected string or null, got {type(model).__name__})"
                )
            raw_cost = row.get("cost_usd")
            if raw_cost is not None and not _is_number(raw_cost):
                raise TraceError(
                    f"{path}: invalid decision field 'cost_usd' "
                    f"(expected finite number or null, got {raw_cost!r})"
                )
            cost_usd = float(raw_cost) if raw_cost is not None else None
            if (
                condition == "fixed"
                and schedule is None
                and isinstance(reason, str)
                and reason.startswith("schedule_")
            ):
                schedule = reason.removeprefix("schedule_")
            if _is_int(encounter) and encounter >= 2:
                raw_evidence = row.get("evidence_ids")
                evidence_ids = (
                    [str(item) for item in raw_evidence] if isinstance(raw_evidence, list) else []
                )
                decisions.append(
                    {
                        "encounter": encounter,
                        "tactic": tactic,
                        "source": source,
                        "reason": reason,
                        "evidence_ids": evidence_ids,
                        "latency_ms": row.get("latency_ms"),
                        "model": model,
                        "input_tokens": row.get("input_tokens"),
                        "output_tokens": row.get("output_tokens"),
                        "cost_usd": cost_usd,
                        "request_id": row.get("request_id"),
                        "context_hash": row.get("context_hash"),
                    }
                )

        elif event == "encounter_start":
            in_encounter = True
            if _is_int(encounter):
                entered_encounters.add(encounter)
                retries_by_sector.setdefault(encounter, 0)
                proto = row.get("protocol")
                if isinstance(proto, str):
                    protocols[encounter] = proto
                wait = row.get("extra_wait_ticks")
                if _is_int(wait):
                    extra_wait[encounter] = wait

        elif event == "retry":
            if pending_sector_fusions:
                fusion_rolled_back_rolls += len(pending_sector_fusions)
                pending_sector_fusions.clear()
            if _is_int(encounter):
                entered_encounters.add(encounter)
                retry_count = row.get("retries")
                if _is_int(retry_count):
                    retries_by_sector[encounter] = max(
                        retries_by_sector.get(encounter, 0), retry_count
                    )

        elif event == "encounter_end":
            in_encounter = False
            for rarity in pending_sector_fusions:
                fusion_rolls[rarity] += 1
            pending_sector_fusions.clear()
            if _is_int(encounter):
                entered_encounters.add(encounter)
                ticks = row.get("ticks")
                if _is_int(ticks):
                    end_ticks[encounter] = ticks
                retry_count = row.get("retries")
                if _is_int(retry_count):
                    retries_by_sector[encounter] = max(
                        retries_by_sector.get(encounter, 0), retry_count
                    )

        elif event == "fuse":
            if row.get("result") == "fused":
                rarity = row.get("rarity")
                if isinstance(rarity, str) and rarity in fusion_rolls:
                    if in_encounter:
                        pending_sector_fusions.append(rarity)
                    else:
                        fusion_rolls[rarity] += 1
            else:
                fusion_failed_attempts += 1

        elif event == "ending":
            has_ending = True
            ending_protocols = row.get("protocols")
            if isinstance(ending_protocols, dict):
                for key, value in ending_protocols.items():
                    if isinstance(value, str):
                        with contextlib.suppress(TypeError, ValueError):
                            protocols[int(key)] = value

        elif event == "session_end":
            has_session_end = True
            if isinstance(row.get("stage"), str):
                session_end_stage = row["stage"]
            if _is_int(encounter):
                entered_encounters.add(encounter)
            end_retries = row.get("retries")
            if isinstance(end_retries, dict):
                for key, value in end_retries.items():
                    if _is_int(value):
                        try:
                            enc_num = int(key)
                        except (TypeError, ValueError):
                            continue
                        retries_by_sector[enc_num] = max(retries_by_sector.get(enc_num, 0), value)

    for rarity in pending_sector_fusions:
        fusion_rolls[rarity] += 1
    pending_sector_fusions.clear()

    completed = has_ending and has_session_end
    stage = "ending" if completed else "incomplete"
    if completed:
        incomplete_reason = None
    elif has_ending and not has_session_end:
        incomplete_reason = "missing_session_end"
    elif has_session_end and session_end_stage and session_end_stage != "ending":
        incomplete_reason = f"stopped_at_{session_end_stage}"
    elif not has_ending and not has_session_end:
        incomplete_reason = "missing_ending_and_session_end"
    else:
        incomplete_reason = "missing_ending"

    if entered_encounters:
        reached_encounter = max(entered_encounters)
    elif decision_encounters:
        reached_encounter = max(decision_encounters)
    else:
        reached_encounter = 0

    live_valid = [d for d in decisions if d["source"] == "live" and d["reason"] is None]
    fixture_valid = [d for d in decisions if d["source"] == "fixture" and d["reason"] is None]
    schedule_decisions = [d for d in decisions if d["source"] == "schedule"]
    neutral_decisions = [d for d in decisions if d["source"] == "neutral"]
    fallback_decisions = [d for d in decisions if d["source"] == "fallback"]
    fallback_reasons = dict(
        sorted(Counter((d["reason"] or "unknown") for d in fallback_decisions).items())
    )
    source_counts = dict(sorted(Counter(str(d["source"]) for d in decisions).items()))

    live_latencies = [d["latency_ms"] for d in live_valid if _is_number(d["latency_ms"])]
    latency_p50_ms = percentile(live_latencies, 0.5)
    latency_p95_ms = percentile(live_latencies, 0.95)
    latency_mean_ms = round(statistics.mean(live_latencies), 1) if live_latencies else None

    non_fixture_decisions = [d for d in decisions if not _is_fixture_decision(d)]
    total_input_tokens = sum(
        d["input_tokens"] for d in non_fixture_decisions if _is_int(d["input_tokens"])
    )
    total_output_tokens = sum(
        d["output_tokens"] for d in non_fixture_decisions if _is_int(d["output_tokens"])
    )
    reported_costs = [
        float(d["cost_usd"]) for d in non_fixture_decisions if _is_number(d["cost_usd"])
    ]
    total_cost_usd = round(sum(reported_costs), 6) if reported_costs else None

    encounters: dict[str, dict[str, Any]] = {}
    for enc in sorted(end_ticks):
        world_tick = end_ticks[enc]
        if enc == 1:
            duration_ticks = world_tick
        else:
            prev_end = end_ticks.get(enc - 1)
            wait = extra_wait.get(enc)
            if (
                prev_end is not None
                and wait is not None
                and world_tick >= prev_end + MIN_FUSE_TICKS + wait
            ):
                duration_ticks = world_tick - (prev_end + MIN_FUSE_TICKS + wait)
            else:
                duration_ticks = world_tick
        encounters[str(enc)] = {
            "ticks": duration_ticks,
            "seconds": round(duration_ticks / TICK_RATE, 2),
            "world_tick": world_tick,
        }

    total_encounter_ticks = sum(item["ticks"] for item in encounters.values())
    total_encounter_seconds = round(total_encounter_ticks / TICK_RATE, 2)
    retries_by_sector_out = {str(enc): retries_by_sector[enc] for enc in sorted(retries_by_sector)}
    protocols_out = {str(enc): protocols[enc] for enc in sorted(protocols)}

    return {
        "file": path.name,
        "path": str(path),
        "condition": condition,
        "schedule": schedule,
        "seed": seed,
        "tuning_id": tuning_id,
        "arena_id": arena_id,
        "config_hash": config_hash,
        "session_id": session_id,
        "stage": stage,
        "completed": completed,
        "incomplete_reason": incomplete_reason,
        "session_end_stage": session_end_stage,
        "reached_encounter": reached_encounter,
        "protocols": protocols_out,
        "decisions": decisions,
        "live_valid_count": len(live_valid),
        "fixture_valid_count": len(fixture_valid),
        "schedule_count": len(schedule_decisions),
        "neutral_count": len(neutral_decisions),
        "fallback_count": len(fallback_decisions),
        "fallback_reasons": fallback_reasons,
        "source_counts": source_counts,
        "latency_p50_ms": latency_p50_ms,
        "latency_p95_ms": latency_p95_ms,
        "latency_mean_ms": latency_mean_ms,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cost_usd": total_cost_usd,
        "total_retries": sum(retries_by_sector.values()),
        "retries_by_sector": retries_by_sector_out,
        "encounters": encounters,
        "total_encounter_ticks": total_encounter_ticks,
        "total_encounter_seconds": total_encounter_seconds,
        "fusion_rolls": fusion_rolls,
        "total_fusion_rolls": sum(fusion_rolls.values()),
        "fusion_rolled_back_rolls": fusion_rolled_back_rolls,
        "fusion_failed_attempts": fusion_failed_attempts,
    }


def build_paired_comparisons(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build paired comparisons whenever live and fixed traces share (seed, tuning_id)."""
    groups: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for summary in summaries:
        seed_val = summary["seed"]
        tuning_val = summary["tuning_id"]
        if seed_val is not None and tuning_val is not None:
            if isinstance(seed_val, list | dict) or isinstance(tuning_val, list | dict):
                raise TraceError(
                    f"{summary.get('file', '<trace>')}: unhashable pairing metadata "
                    f"(seed={seed_val!r}, tuning_id={tuning_val!r})"
                )
            groups[(seed_val, tuning_val)].append(summary)

    paired: list[dict[str, Any]] = []
    for (seed, tuning_id), group in groups.items():
        live_traces = [item for item in group if item["condition"] == "live"]
        fixed_traces = [item for item in group if item["condition"] == "fixed"]
        if len(group) < 2 or not live_traces or not fixed_traces:
            continue

        confounds: list[str] = []
        for lt in live_traces:
            for decision in lt["decisions"]:
                enc = decision["encounter"]
                src = decision["source"]
                reason = decision["reason"]
                if src == "fallback":
                    confounds.append(
                        f"CONFOUND: live trace {lt['file']} fell back to neutral on encounter "
                        f"{enc} (reason: {reason or 'unknown'})."
                    )
                elif src == "fixture":
                    confounds.append(
                        f"CONFOUND: live trace {lt['file']} used fixture provider on encounter "
                        f"{enc}, not live model evidence."
                    )
                elif src != "live" or reason is not None:
                    confounds.append(
                        f"CONFOUND: live trace {lt['file']} had non-valid decision on encounter "
                        f"{enc} (source: {src}, reason: {reason})."
                    )
            if lt["completed"] and len(lt["decisions"]) < 2:
                confounds.append(
                    f"CONFOUND: live trace {lt['file']} recorded only {len(lt['decisions'])} "
                    "adaptation decision(s)."
                )

        for trace in group:
            if not trace["completed"]:
                confounds.append(
                    f"CONFOUND: {trace['condition']} trace {trace['file']} is incomplete "
                    f"({trace['incomplete_reason']})."
                )

        missing_arena = [str(t["file"]) for t in group if t["arena_id"] is None]
        if missing_arena:
            confounds.append(
                f"CONFOUND: missing arena_id in paired trace(s) ({', '.join(missing_arena)})."
            )
        arena_ids = sorted({str(t["arena_id"]) for t in group if t["arena_id"] is not None})
        if len(arena_ids) > 1:
            confounds.append(
                f"CONFOUND: arena_id mismatch across paired traces ({', '.join(arena_ids)})."
            )

        missing_config = [str(t["file"]) for t in group if t["config_hash"] is None]
        if missing_config:
            confounds.append(
                f"CONFOUND: missing config_hash in paired trace(s) ({', '.join(missing_config)})."
            )
        config_hashes = sorted(
            {str(t["config_hash"]) for t in group if t["config_hash"] is not None}
        )
        if len(config_hashes) > 1:
            confounds.append(
                f"CONFOUND: config_hash mismatch across paired traces ({', '.join(config_hashes)})."
            )

        pairs: list[dict[str, Any]] = []
        for lt in live_traces:
            for ft in fixed_traces:
                compared = [
                    enc
                    for enc in (2, 3)
                    if str(enc) in lt["protocols"] or str(enc) in ft["protocols"]
                ]
                differing = [
                    enc
                    for enc in compared
                    if lt["protocols"].get(str(enc)) != ft["protocols"].get(str(enc))
                ]
                pairs.append(
                    {
                        "live_file": lt["file"],
                        "fixed_file": ft["file"],
                        "live_protocols": lt["protocols"],
                        "fixed_protocols": ft["protocols"],
                        "compared_encounters": compared,
                        "differing_encounters": differing,
                        "retries_delta": lt["total_retries"] - ft["total_retries"],
                        "encounter_seconds_delta": round(
                            lt["total_encounter_seconds"] - ft["total_encounter_seconds"], 2
                        ),
                        "fusion_rolls_delta": lt["total_fusion_rolls"] - ft["total_fusion_rolls"],
                        "has_live_fallback": lt["fallback_count"] > 0,
                    }
                )

        paired.append(
            {
                "seed": seed,
                "tuning_id": tuning_id,
                "traces": [
                    {
                        "file": item["file"],
                        "condition": item["condition"],
                        "schedule": item["schedule"],
                        "stage": item["stage"],
                        "protocols": item["protocols"],
                        "total_retries": item["total_retries"],
                        "retries_by_sector": item["retries_by_sector"],
                        "encounters": item["encounters"],
                        "total_encounter_seconds": item["total_encounter_seconds"],
                        "fusion_rolls": item["fusion_rolls"],
                        "total_fusion_rolls": item["total_fusion_rolls"],
                        "fusion_rolled_back_rolls": item["fusion_rolled_back_rolls"],
                        "live_valid_count": item["live_valid_count"],
                        "fallback_count": item["fallback_count"],
                        "fallback_reasons": item["fallback_reasons"],
                    }
                    for item in group
                ],
                "pairs": pairs,
                "has_fallback_confound": any(lt["fallback_count"] > 0 for lt in live_traces),
                "confounds": confounds,
            }
        )

    return paired


def compare_traces(paths: list[Path]) -> dict[str, Any]:
    """Load, summarize, and pair-compare all requested JSONL trace files."""
    summaries = [summarize_trace(path, load_trace(path)) for path in paths]

    all_live_decisions = [d for s in summaries if s["condition"] == "live" for d in s["decisions"]]
    live_source_decisions = [d for d in all_live_decisions if d["source"] == "live"]
    valid_live = [d for d in live_source_decisions if d["reason"] is None]
    fixture_valid = [
        d for d in all_live_decisions if d["source"] == "fixture" and d["reason"] is None
    ]
    live_latencies = [d["latency_ms"] for d in valid_live if _is_number(d["latency_ms"])]
    live_fallbacks = [d for d in all_live_decisions if d["source"] == "fallback"]
    live_billing_decisions = [
        d
        for d in all_live_decisions
        if d["source"] in ("live", "fallback") and not _is_fixture_decision(d)
    ]
    live_costs = [float(d["cost_usd"]) for d in live_billing_decisions if _is_number(d["cost_usd"])]

    overall_live = {
        "decision_count": len(all_live_decisions),
        "live_valid_count": len(valid_live),
        "fixture_valid_count": len(fixture_valid),
        "fallback_count": len(live_fallbacks),
        "fallback_reasons": dict(
            sorted(Counter((d["reason"] or "unknown") for d in live_fallbacks).items())
        ),
        "latency_p50_ms": percentile(live_latencies, 0.5),
        "latency_p95_ms": percentile(live_latencies, 0.95),
        "latency_mean_ms": round(statistics.mean(live_latencies), 1) if live_latencies else None,
        "total_input_tokens": sum(
            d["input_tokens"] for d in live_billing_decisions if _is_int(d["input_tokens"])
        ),
        "total_output_tokens": sum(
            d["output_tokens"] for d in live_billing_decisions if _is_int(d["output_tokens"])
        ),
        "total_cost_usd": round(sum(live_costs), 6) if live_costs else None,
    }

    return {
        "traces": summaries,
        "overall_live": overall_live,
        "paired_comparisons": build_paired_comparisons(summaries),
    }


def _fmt_opt(value: Any, default: str = "n/a") -> str:
    return default if value is None else str(value)


def _fmt_cost(cost: Any) -> str:
    return f"USD {float(cost):.6f}" if _is_number(cost) else "n/a"


def _fmt_protocols(protocols: dict[str, str]) -> str:
    if not protocols:
        return "none"
    return " -> ".join(f"E{enc}:{protocols[enc]}" for enc in sorted(protocols, key=int))


def _fmt_retries(total: int, by_sector: dict[str, int]) -> str:
    if not by_sector:
        return str(total)
    parts = ", ".join(f"S{enc}:{by_sector[enc]}" for enc in sorted(by_sector, key=int))
    return f"{total} ({parts})"


def _fmt_encounters(encounters: dict[str, dict[str, Any]], total_s: float, total_t: int) -> str:
    if not encounters:
        return "none cleared"
    parts = ", ".join(
        f"E{enc}: {encounters[enc]['seconds']:.2f}s ({encounters[enc]['ticks']}t)"
        for enc in sorted(encounters, key=int)
    )
    return f"{parts}, total {total_s:.2f}s ({total_t}t)"


def _fmt_fusions(rolls: dict[str, int], total: int, rolled_back: int = 0) -> str:
    detail = f"rare: {rolls['rare']}, epic: {rolls['epic']}, legendary: {rolls['legendary']}"
    if rolled_back > 0:
        detail = f"{detail}, rolled back on retry: {rolled_back}"
    return f"{total} ({detail})"


def _fmt_fallbacks(count: int, reasons: dict[str, int]) -> str:
    if count == 0:
        return "0"
    breakdown = ", ".join(f"{reason}={qty}" for reason, qty in reasons.items())
    return f"{count} ({breakdown})"


def _fmt_latency_summary(p50: float | None, p95: float | None, mean: float | None) -> str:
    if p50 is None and p95 is None:
        return "n/a"
    mean_text = f", mean {mean} ms" if mean is not None else ""
    return f"p50 {p50} ms / p95 {p95} ms{mean_text}"


def format_markdown(report: dict[str, Any]) -> str:
    """Render trace summaries and any paired comparisons as GitHub-flavored Markdown."""
    lines = [
        "# Overload Trace Comparison",
        "",
        "Evidence sources (`live`, `fixture`, `fallback`, `schedule`, `neutral`) are reported "
        "strictly as logged and never reclassified.",
        "",
    ]

    for summary in report["traces"]:
        condition_label = summary["condition"] or "unknown"
        if summary["schedule"]:
            condition_label = f"{condition_label} (schedule {summary['schedule']})"
        stage_label = summary["stage"]
        if not summary["completed"] and summary["incomplete_reason"]:
            stage_label = f"{stage_label} ({summary['incomplete_reason']})"

        lines.extend(
            [
                f"## Trace: {summary['file']}",
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| File | `{summary['file']}` |",
                f"| Condition | `{condition_label}` |",
                f"| Seed | `{_fmt_opt(summary['seed'])}` |",
                f"| Tuning ID | `{_fmt_opt(summary['tuning_id'])}` |",
                f"| Arena ID | `{_fmt_opt(summary['arena_id'])}` |",
                f"| Config hash | `{_fmt_opt(summary['config_hash'])}` |",
                f"| Final stage | `{stage_label}` |",
                f"| Reached encounter | `{summary['reached_encounter']}` |",
                f"| Protocols | {_fmt_protocols(summary['protocols'])} |",
                "",
                "### Decisions (Encounters 2 and 3)",
                "",
            ]
        )

        if summary["decisions"]:
            lines.extend(
                [
                    "| Encounter | Tactic | Source | Reason | Evidence IDs | Latency (ms) | "
                    "Model | Input tokens | Output tokens | Cost (USD) |",
                    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                ]
            )
            for d in summary["decisions"]:
                raw_ev = d["evidence_ids"]
                evidence = ", ".join(str(item) for item in raw_ev) if raw_ev else "none"
                lines.append(
                    f"| {d['encounter']} | `{_fmt_opt(d['tactic'])}` | "
                    f"`{_fmt_opt(d['source'])}` | `{_fmt_opt(d['reason'], 'none')}` | "
                    f"{evidence} | {_fmt_opt(d['latency_ms'])} | "
                    f"`{_fmt_opt(d['model'])}` | {_fmt_opt(d['input_tokens'])} | "
                    f"{_fmt_opt(d['output_tokens'])} | {_fmt_cost(d['cost_usd'])} |"
                )
        else:
            lines.append("No encounter 2 or 3 decisions recorded.")

        latency_text = _fmt_latency_summary(
            summary["latency_p50_ms"],
            summary["latency_p95_ms"],
            summary["latency_mean_ms"],
        )
        retries_text = _fmt_retries(summary["total_retries"], summary["retries_by_sector"])
        encounters_text = _fmt_encounters(
            summary["encounters"],
            summary["total_encounter_seconds"],
            summary["total_encounter_ticks"],
        )
        fusions_text = _fmt_fusions(
            summary["fusion_rolls"],
            summary["total_fusion_rolls"],
            summary["fusion_rolled_back_rolls"],
        )
        lines.extend(
            [
                "",
                "### Aggregates",
                "",
                "| Measure | Value |",
                "| --- | --- |",
                f"| Live valid decisions | {summary['live_valid_count']} |",
                f"| Fixture decisions | {summary['fixture_valid_count']} |",
                f"| Schedule decisions | {summary['schedule_count']} |",
                f"| Neutral decisions | {summary['neutral_count']} |",
                f"| Fallbacks | "
                f"{_fmt_fallbacks(summary['fallback_count'], summary['fallback_reasons'])} |",
                f"| Latency (valid live, nearest rank) | {latency_text} |",
                f"| Tokens (in / out) | "
                f"{summary['total_input_tokens']} / {summary['total_output_tokens']} |",
                f"| Reported cost | {_fmt_cost(summary['total_cost_usd'])} |",
                f"| Retries | {retries_text} |",
                f"| Encounter durations (60 Hz) | {encounters_text} |",
                f"| Fusion rolls | {fusions_text} |",
                "",
            ]
        )

    overall = report["overall_live"]
    if len(report["traces"]) > 1 and overall["decision_count"] > 0:
        overall_latency = _fmt_latency_summary(
            overall["latency_p50_ms"],
            overall["latency_p95_ms"],
            overall["latency_mean_ms"],
        )
        lines.extend(
            [
                "## Aggregate Live Model Metrics",
                "",
                "| Measure | Value |",
                "| --- | --- |",
                f"| Adaptation decisions (live condition) | {overall['decision_count']} |",
                f"| Valid live decisions | {overall['live_valid_count']} |",
                f"| Fixture decisions (excluded from live metrics) | "
                f"{overall['fixture_valid_count']} |",
                f"| Fallbacks | "
                f"{_fmt_fallbacks(overall['fallback_count'], overall['fallback_reasons'])} |",
                f"| Latency (valid live, nearest rank) | {overall_latency} |",
                f"| Tokens (in / out) | "
                f"{overall['total_input_tokens']} / {overall['total_output_tokens']} |",
                f"| Reported cost | {_fmt_cost(overall['total_cost_usd'])} |",
                "",
            ]
        )

    if report["paired_comparisons"]:
        lines.extend(["## Paired Comparison", ""])
        for group in report["paired_comparisons"]:
            lines.extend(
                [
                    f"### Seed {group['seed']} (tuning_id `{group['tuning_id']}`)",
                    "",
                    "| Condition | File | Stage | Protocols | Retries | "
                    "Encounter durations (60 Hz) | Fusion rolls | Live valid / Fallbacks |",
                    "| --- | --- | --- | --- | --- | --- | --- | --- |",
                ]
            )
            for item in group["traces"]:
                cond = (
                    f"{item['condition']} ({item['schedule']})"
                    if item["schedule"]
                    else str(item["condition"])
                )
                enc_text = _fmt_encounters(
                    item["encounters"],
                    item["total_encounter_seconds"],
                    sum(e["ticks"] for e in item["encounters"].values()),
                )
                fusions_cell = _fmt_fusions(
                    item["fusion_rolls"],
                    item["total_fusion_rolls"],
                    item["fusion_rolled_back_rolls"],
                )
                live_fb = (
                    f"{item['live_valid_count']} / "
                    f"{_fmt_fallbacks(item['fallback_count'], item['fallback_reasons'])}"
                )
                lines.append(
                    f"| `{cond}` | `{item['file']}` | `{item['stage']}` | "
                    f"{_fmt_protocols(item['protocols'])} | "
                    f"{_fmt_retries(item['total_retries'], item['retries_by_sector'])} | "
                    f"{enc_text} | {fusions_cell} | {live_fb} |"
                )

            lines.append("")
            for pair in group["pairs"]:
                compared = pair.get("compared_encounters", [2, 3])
                if pair["differing_encounters"]:
                    diff_text = ", ".join(f"E{enc}" for enc in pair["differing_encounters"])
                elif not compared:
                    diff_text = "n/a (neither trace reached E2)"
                elif compared == [2, 3]:
                    diff_text = "none (identical E2 and E3 protocols)"
                else:
                    compared_label = " and ".join(f"E{enc}" for enc in compared)
                    diff_text = f"none (identical {compared_label} protocol)"
                lines.append(
                    f"- Delta (`{pair['live_file']}` minus `{pair['fixed_file']}`): "
                    f"differing protocols = {diff_text}, "
                    f"retries = {pair['retries_delta']:+d}, "
                    f"encounter time = {pair['encounter_seconds_delta']:+.2f}s, "
                    f"fusion rolls = {pair['fusion_rolls_delta']:+d}."
                )

            lines.extend(["", "#### Fallback and Validity Confounds", ""])
            if group["confounds"]:
                for confound in group["confounds"]:
                    lines.append(f"- {confound}")
            else:
                lines.append(
                    "- None (all live adaptation decisions valid, traces complete, "
                    "arena_id and config_hash match)."
                )
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize and compare Overload JSONL session traces."
    )
    parser.add_argument(
        "traces",
        nargs="+",
        type=Path,
        help="One or more JSONL trace files (for example logs/trace-*.jsonl).",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit machine-readable JSON instead of Markdown.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the report to PATH instead of stdout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = compare_traces(args.traces)
    except TraceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    rendered = (
        json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.as_json
        else format_markdown(report)
    )
    if args.out is not None:
        try:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"Error: unable to write output file {args.out} ({exc})", file=sys.stderr)
            return 2
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
