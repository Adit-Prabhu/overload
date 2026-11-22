"""Which protocol the Regulator uses in each encounter.

Three conditions share one interface, so the comparison changes nothing but the source:
- LiveSelector asks the rival service between encounters (at most two requests).
- FixedSchedule follows a predeclared order and never sees the summary.
- NeutralSelector always uses the neutral tactic (live mode off or unavailable).

`prepare` is called when an encounter ends. `poll` is called every frame at the next
encounter's entry and never blocks. Once an encounter's decision is made it is frozen, so a
retry reuses it and a late reply can never change it.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from overload.agent.client import Pending, TacticClient, is_timeout_error
from overload.agent.tactics import Decision, catalogue, fallback, schedules, validate

MAX_REQUESTS = 2


class Selector(Protocol):
    condition: str

    def prepare(self, encounter: int, summary: dict | None) -> None: ...

    def poll(self, encounter: int) -> Decision | None: ...


class NeutralSelector:
    condition = "off"

    def warm(self) -> None:
        return None

    def prepare(self, encounter: int, summary: dict | None) -> None:
        return None

    def poll(self, encounter: int) -> Decision:
        return Decision(encounter, catalogue().neutral, "neutral", "live_off")


class FixedSchedule:
    condition = "fixed"

    def __init__(self, name: str) -> None:
        self.name = name
        self.order = schedules()[name]

    def warm(self) -> None:
        return None

    def prepare(self, encounter: int, summary: dict | None) -> None:
        return None  # the baseline never reads observations

    def poll(self, encounter: int) -> Decision:
        return Decision(encounter, self.order[encounter - 1], "schedule", f"schedule_{self.name}")


class LiveSelector:
    condition = "live"

    def __init__(self, client: TacticClient, session_id: str | None) -> None:
        self.client = client
        self.session_id = session_id
        self.requests = 0
        self.pending: dict[int, Pending] = {}
        self.decided: dict[int, Decision] = {}
        self.skipped: dict[int, str] = {}

    def warm(self) -> None:
        if self.session_id is not None and self.requests < MAX_REQUESTS:
            warm_fn = getattr(self.client, "warm", None)
            if callable(warm_fn):
                warm_fn(self.session_id)

    def prepare(self, encounter: int, summary: dict | None) -> None:
        if encounter == 1 or encounter in self.pending or encounter in self.decided:
            return
        if self.session_id is None:
            self.skipped[encounter] = "no_session"
        elif self.requests >= MAX_REQUESTS:
            self.skipped[encounter] = "request_cap"
        elif summary is None:
            self.skipped[encounter] = "no_summary"
        else:
            self.requests += 1
            self.pending[encounter] = self.client.submit(
                self.session_id, encounter, str(uuid.uuid4()), summary
            )

    def poll(self, encounter: int) -> Decision | None:
        if encounter in self.decided:
            return self.decided[encounter]
        if encounter == 1:
            decision = Decision(1, catalogue().neutral, "neutral", "first_encounter")
        elif encounter in self.skipped:
            decision = fallback(encounter, self.skipped[encounter])
        elif encounter not in self.pending:
            decision = fallback(encounter, "not_requested")
        else:
            decision = self._resolve(self.pending[encounter])
            if decision is None:
                return None
        self.decided[encounter] = decision
        return decision

    def _resolve(self, pending: Pending) -> Decision | None:
        elapsed = self.client.clock() - pending.started
        latency = round(elapsed * 1000)
        if pending.future.done():
            try:
                status, body, arrived = pending.future.result()
            except Exception as exc:  # timeout or transport, parsing or cancellation failure
                reason = "timeout" if is_timeout_error(exc) else "transport_error"
                return fallback(pending.encounter, reason, pending.request_id, latency)
            latency = round((arrived - pending.started) * 1000)
            if arrived - pending.started > self.client.deadline:
                return fallback(pending.encounter, "late", pending.request_id, latency)
            if status != 200:
                return fallback(pending.encounter, f"http_{status}", pending.request_id, latency)
            return validate(
                body,
                session_id=self.session_id or "",
                request_id=pending.request_id,
                encounter=pending.encounter,
                supplied_ids=pending.supplied_ids,
                prior_supplied_ids=pending.prior_supplied_ids,
                latency_ms=latency,
            )
        if elapsed >= self.client.deadline:
            return fallback(pending.encounter, "timeout", pending.request_id, latency)
        return None
