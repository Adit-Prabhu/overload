"""Session traces: one JSON object per line, written to logs/ (not committed).

Fields follow the Initial Configuration's logging policy: anonymous session ID, encounter
and request IDs, condition, tuning and arena IDs, a hash of the exact summary sent, the
decision with its source and fallback reason, latency, model, tokens and estimated cost, and
a hash of the tactic and schedule configuration. The prompt itself is built and hashed on the
server. No player identity.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict
from pathlib import Path

from overload.agent.observations import EVIDENCE_PATH
from overload.agent.tactics import CATALOGUE_PATH, SCHEDULES_PATH, Decision


def config_hash() -> str:
    """Hash of the tactic catalogue, the baseline schedules and the evidence kinds this build
    uses, so traces from different evidence versions can be told apart."""
    digest = hashlib.sha256()
    for path in (CATALOGUE_PATH, SCHEDULES_PATH, EVIDENCE_PATH):
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def context_hash(summary: dict | None) -> str | None:
    if summary is None:
        return None
    blob = json.dumps(summary, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


class TraceWriter:
    def __init__(self, path: Path, *, condition: str, tuning_id: str, arena_id: str) -> None:
        self.path = path
        self.base = {
            "condition": condition,
            "tuning_id": tuning_id,
            "arena_id": arena_id,
            "config_hash": config_hash(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields) -> None:
        record = {"t": round(time.time(), 3), "event": event, **self.base, **fields}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def decision(self, decision: Decision, session_id: str | None, summary: dict | None) -> None:
        self.write(
            "decision",
            session_id=session_id,
            context_hash=context_hash(summary),
            **asdict(decision),
        )
