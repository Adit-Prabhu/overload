"""The tactic catalogue and validation of the rival service's replies.

Every check failure becomes the neutral tactic with a named reason, so a bad, late or
missing reply can never change a fight. The service validates too. This is the game's own
check and the one that counts.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache

from overload.paths import ROOT

CATALOGUE_PATH = ROOT / "config" / "tactics.json"
SCHEDULES_PATH = ROOT / "config" / "schedules.json"


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


def fallback(
    encounter: int, reason: str, request_id: str | None = None, latency_ms: int | None = None
) -> Decision:
    return Decision(
        encounter, catalogue().neutral, "fallback", reason, request_id, latency_ms=latency_ms
    )


def validate(
    reply: Mapping | None,
    *,
    session_id: str,
    request_id: str,
    encounter: int,
    supplied_ids: frozenset[str],
    latency_ms: int | None = None,
) -> Decision:
    """Accept a reply only if every field checks out. Otherwise the neutral tactic."""
    if reply is None:
        return fallback(encounter, "no_reply", request_id, latency_ms)
    if not isinstance(reply, Mapping):
        return fallback(encounter, "malformed_reply", request_id, latency_ms)
    status = reply.get("status")
    if status != "ok":
        return fallback(encounter, f"service_{status}", request_id, latency_ms)
    checks = (
        (reply.get("session_id") == session_id, "wrong_session"),
        (reply.get("request_id") == request_id, "wrong_request"),
        (reply.get("encounter") == encounter, "wrong_encounter"),
        (reply.get("tactic_id") in catalogue().ids, "unknown_tactic"),
        (reply.get("source") in ("live", "fixture"), "unknown_source"),
    )
    for ok, reason in checks:
        if not ok:
            return fallback(encounter, reason, request_id, latency_ms)
    evidence = reply.get("evidence_ids")
    if not isinstance(evidence, list) or not all(isinstance(e, str) for e in evidence):
        return fallback(encounter, "malformed_evidence", request_id, latency_ms)
    if not set(evidence) <= supplied_ids:
        return fallback(encounter, "unknown_evidence", request_id, latency_ms)
    usage = reply.get("usage") if isinstance(reply.get("usage"), Mapping) else {}
    cost = reply.get("cost_usd_estimate")
    return Decision(
        encounter=encounter,
        tactic=reply["tactic_id"],
        source=reply["source"],
        request_id=request_id,
        evidence_ids=tuple(evidence),
        latency_ms=latency_ms,
        model=reply.get("resolved_model"),
        input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
        cost_usd=cost if isinstance(cost, int | float) else None,
    )
