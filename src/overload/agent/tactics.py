"""The tactic catalogue and validation of the rival service's replies.

Every check failure becomes the neutral tactic with a named reason, so a bad, late or
missing reply can never change a fight. The service validates too. This is the game's own
check and the one that counts.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache

from overload.paths import ROOT

CATALOGUE_PATH = ROOT / "config" / "tactics.json"
SCHEDULES_PATH = ROOT / "config" / "schedules.json"
SPENT_FAILURE_STATUSES = frozenset({"invalid_output", "timeout", "provider_error"})


@dataclass(frozen=True)
class Catalogue:
    ids: tuple[str, ...]
    neutral: str


@cache
def catalogue() -> Catalogue:
    data = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    return Catalogue(ids=tuple(t["id"] for t in data["tactics"]), neutral=data["neutral"])


@cache
def schedules() -> dict[str, tuple[str, ...]]:
    data = json.loads(SCHEDULES_PATH.read_text(encoding="utf-8"))
    return {name: tuple(order) for name, order in data["schedules"].items()}


@dataclass(frozen=True)
class Decision:
    """The protocol for one encounter and where it came from.

    source is "live" or "fixture" (an accepted service reply), "schedule" (baseline),
    "neutral" (encounter 1 or live mode off) or "fallback" (anything went wrong).
    """

    encounter: int
    tactic: str
    source: str
    reason: str | None = None
    request_id: str | None = None
    evidence_ids: tuple[str, ...] = ()
    latency_ms: int | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _spent_accounting(
    reply: Mapping,
    *,
    session_id: str,
    request_id: str,
    encounter: int,
) -> dict[str, str | int | float | None]:
    """Extract model, token usage, and cost when a Worker reply belongs to this request."""
    if reply.get("session_id") not in (None, session_id):
        return {}
    if reply.get("request_id") not in (None, request_id):
        return {}
    if reply.get("encounter") not in (None, encounter):
        return {}
    usage = reply.get("usage") if isinstance(reply.get("usage"), Mapping) else {}
    raw_in = usage.get("input_tokens")
    raw_out = usage.get("output_tokens")
    raw_cost = reply.get("cost_usd_estimate")
    resolved = reply.get("resolved_model")
    requested = reply.get("requested_model")
    if isinstance(resolved, str) and resolved:
        model: str | None = resolved
    elif isinstance(requested, str) and requested and requested != "unset":
        model = requested
    else:
        model = None
    return {
        "model": model,
        "input_tokens": raw_in if _is_int(raw_in) else None,
        "output_tokens": raw_out if _is_int(raw_out) else None,
        "cost_usd": float(raw_cost) if _is_number(raw_cost) else None,
    }


def fallback(
    encounter: int,
    reason: str,
    request_id: str | None = None,
    latency_ms: int | None = None,
    *,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> Decision:
    return Decision(
        encounter,
        catalogue().neutral,
        "fallback",
        reason,
        request_id,
        latency_ms=latency_ms,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


def validate(
    reply: Mapping | None,
    *,
    session_id: str,
    request_id: str,
    encounter: int,
    supplied_ids: frozenset[str],
    prior_supplied_ids: frozenset[str] = frozenset(),
    latency_ms: int | None = None,
) -> Decision:
    """Accept a reply only if every field checks out. Otherwise the neutral tactic."""
    if reply is None:
        return fallback(encounter, "no_reply", request_id, latency_ms)
    if not isinstance(reply, Mapping):
        return fallback(encounter, "malformed_reply", request_id, latency_ms)
    status = reply.get("status")
    if status != "ok":
        if status in SPENT_FAILURE_STATUSES:
            acct = _spent_accounting(
                reply, session_id=session_id, request_id=request_id, encounter=encounter
            )
            return fallback(encounter, f"service_{status}", request_id, latency_ms, **acct)
        return fallback(encounter, f"service_{status}", request_id, latency_ms)
    identity_checks = (
        (reply.get("session_id") == session_id, "wrong_session"),
        (reply.get("request_id") == request_id, "wrong_request"),
        (reply.get("encounter") == encounter, "wrong_encounter"),
    )
    for ok, reason in identity_checks:
        if not ok:
            return fallback(encounter, reason, request_id, latency_ms)
    known_source = reply.get("source") in ("live", "fixture")
    acct = (
        _spent_accounting(reply, session_id=session_id, request_id=request_id, encounter=encounter)
        if known_source
        else {}
    )
    if reply.get("tactic_id") not in catalogue().ids:
        return fallback(encounter, "unknown_tactic", request_id, latency_ms, **acct)
    if not known_source:
        return fallback(encounter, "unknown_source", request_id, latency_ms)
    evidence = reply.get("evidence_ids")
    if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
        return fallback(encounter, "malformed_evidence", request_id, latency_ms, **acct)
    if not evidence:
        return fallback(encounter, "empty_evidence", request_id, latency_ms, **acct)
    allowed_ids = supplied_ids | prior_supplied_ids
    if not set(evidence) <= allowed_ids:
        return fallback(encounter, "unknown_evidence", request_id, latency_ms, **acct)
    usage = reply.get("usage") if isinstance(reply.get("usage"), Mapping) else {}
    raw_in = usage.get("input_tokens")
    raw_out = usage.get("output_tokens")
    cost = reply.get("cost_usd_estimate")
    resolved = reply.get("resolved_model")
    return Decision(
        encounter=encounter,
        tactic=reply["tactic_id"],
        source=reply["source"],
        request_id=request_id,
        evidence_ids=tuple(evidence),
        latency_ms=latency_ms,
        model=resolved if isinstance(resolved, str) and resolved else None,
        input_tokens=raw_in if _is_int(raw_in) else None,
        output_tokens=raw_out if _is_int(raw_out) else None,
        cost_usd=float(cost) if _is_number(cost) else None,
    )
