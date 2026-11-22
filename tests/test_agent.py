"""Task 5: the knowledge boundary, reply validation, deadline and fallback, and the baseline.

The transport and clock are fakes, so nothing here touches the network or spends money.
"""

from __future__ import annotations

import contextlib
import copy
import http.client
import json
import re
import threading
import urllib.error

import pytest

from overload.agent.client import TacticClient
from overload.agent.observations import ObservationLog, observe_world
from overload.agent.selector import FixedSchedule, LiveSelector, NeutralSelector
from overload.agent.tactics import catalogue, schedules, validate
from overload.session.trace import TraceWriter, context_hash
from overload.sim.inputs import InputFrame
from overload.sim.run import Run
from overload.sim.state import Device

SESSION = "11111111-2222-3333-4444-555555555555"


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class Service:
    """Fake rival service. `reply` builds the body for each tactic request."""

    def __init__(self, clock: Clock, reply=None, status: int = 200, gate=None, arrive=None):
        self.clock = clock
        self.calls: list[dict] = []
        self.reply = reply or (lambda body: ok_reply(body, "pressure", ["e1.far_share"]))
        self.status = status
        self.gate = gate
        self.arrive = arrive

    def __call__(self, method, url, body, timeout):
        if url.endswith("/sessions"):
            return 201, {"session_id": SESSION}
        self.calls.append(body)
        if self.gate is not None:
            self.gate.wait(5)
        if self.arrive is not None:
            self.clock.now = self.arrive
        return self.status, self.reply(body)


def ok_reply(body, tactic, evidence, **overrides):
    reply = {
        "session_id": SESSION,
        "request_id": body["request_id"],
        "encounter": body["encounter"],
        "status": "ok",
        "tactic_id": tactic,
        "evidence_ids": evidence,
        "source": "fixture",
        "resolved_model": "fixture-rule-v1",
    }
    reply.update(overrides)
    return reply


def summary(encounter: int = 1) -> dict:
    log = ObservationLog(encounter)
    for _ in range(100):
        log.observe((0.0, 0.0), (200.0, 0.0), ["shot"])
    return log.summary("lateral")


def live(service: Service, clock: Clock) -> LiveSelector:
    client = TacticClient("http://rival.test", transport=service, clock=clock)
    return LiveSelector(client, client.start_session())


def settle(selector: LiveSelector, encounter: int) -> None:
    selector.pending[encounter].future.result(timeout=5)


# Validation ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"status": "timeout"}, "service_timeout"),
        ({"session_id": "other"}, "wrong_session"),
        ({"request_id": "other"}, "wrong_request"),
        ({"encounter": 3}, "wrong_encounter"),
        ({"tactic_id": "berserk"}, "unknown_tactic"),
        ({"source": "guess"}, "unknown_source"),
        ({"evidence_ids": ["e1.player_hp"]}, "unknown_evidence"),
    ],
)
def test_invalid_replies_fall_back_to_neutral(overrides, reason) -> None:
    body = {"request_id": "req-1", "encounter": 2}
    reply = ok_reply(body, "pressure", ["e1.far_share"], **overrides)
    decision = validate(
        reply,
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
    )
    assert decision.tactic == catalogue().neutral
    assert decision.source == "fallback"
    assert decision.reason == reason


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        (["not", "an", "object"], "malformed_reply"),
        ("pressure", "malformed_reply"),
        (
            {
                "status": "ok",
                "session_id": SESSION,
                "request_id": "req-1",
                "encounter": 2,
                "tactic_id": "pressure",
                "source": "fixture",
                "evidence_ids": [{"id": 1}],
            },
            "malformed_evidence",
        ),
        (
            {
                "status": "ok",
                "session_id": SESSION,
                "request_id": "req-1",
                "encounter": 2,
                "tactic_id": "pressure",
                "source": "fixture",
                "evidence_ids": "e1.far_share",
            },
            "malformed_evidence",
        ),
    ],
)
def test_malformed_replies_fall_back_instead_of_crashing(reply, reason) -> None:
    decision = validate(
        reply,
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
    )
    assert (decision.source, decision.reason) == ("fallback", reason)


def test_valid_reply_is_accepted() -> None:
    body = {"request_id": "req-1", "encounter": 2}
    decision = validate(
        ok_reply(body, "spacing", ["e1.near_share"]),
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.near_share"}),
    )
    assert (decision.tactic, decision.source, decision.reason) == ("spacing", "fixture", None)


def test_empty_evidence_falls_back_to_neutral() -> None:
    body = {"request_id": "req-1", "encounter": 2}
    decision = validate(
        ok_reply(body, "lateral", []),
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
    )
    assert (decision.tactic, decision.source, decision.reason) == (
        catalogue().neutral,
        "fallback",
        "empty_evidence",
    )


def test_validate_accepts_prior_supplied_ids_when_provided() -> None:
    body = {"request_id": "req-2", "encounter": 3}
    prior = frozenset({"e1.far_share"})
    current = frozenset({"e2.near_share"})

    prior_only = validate(
        ok_reply(body, "pressure", ["e1.far_share"], source="live"),
        session_id=SESSION,
        request_id="req-2",
        encounter=3,
        supplied_ids=current,
        prior_supplied_ids=prior,
    )
    assert (prior_only.tactic, prior_only.source, prior_only.evidence_ids) == (
        "pressure",
        "live",
        ("e1.far_share",),
    )

    both = validate(
        ok_reply(body, "spacing", ["e1.far_share", "e2.near_share"], source="live"),
        session_id=SESSION,
        request_id="req-2",
        encounter=3,
        supplied_ids=current,
        prior_supplied_ids=prior,
    )
    assert (both.tactic, both.source, both.evidence_ids) == (
        "spacing",
        "live",
        ("e1.far_share", "e2.near_share"),
    )

    unsupplied = validate(
        ok_reply(body, "spacing", ["e1.player_hp"], source="live"),
        session_id=SESSION,
        request_id="req-2",
        encounter=3,
        supplied_ids=current,
        prior_supplied_ids=prior,
    )
    assert (unsupplied.tactic, unsupplied.source, unsupplied.reason) == (
        catalogue().neutral,
        "fallback",
        "unknown_evidence",
    )


def test_fallback_preserves_usage_cost_and_model_on_spent_worker_calls() -> None:
    body = {"request_id": "req-1", "encounter": 2}
    invalid_reply = ok_reply(
        body,
        None,
        [],
        status="invalid_output",
        source="live",
        resolved_model="gemini-3.5-flash-lite-001",
        usage={"input_tokens": 512, "output_tokens": 27},
        cost_usd_estimate=0.00158,
    )
    invalid_decision = validate(
        invalid_reply,
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
        latency_ms=420,
    )
    assert invalid_decision.tactic == catalogue().neutral
    assert invalid_decision.source == "fallback"
    assert invalid_decision.reason == "service_invalid_output"
    assert invalid_decision.model == "gemini-3.5-flash-lite-001"
    assert invalid_decision.input_tokens == 512
    assert invalid_decision.output_tokens == 27
    assert invalid_decision.cost_usd == 0.00158

    timeout_reply = ok_reply(
        body,
        None,
        [],
        status="timeout",
        source="live",
        requested_model="gemini-3.5-flash-lite",
        resolved_model=None,
        usage={"input_tokens": 0, "output_tokens": 0},
        cost_usd_estimate=0.00158,
    )
    timeout_decision = validate(
        timeout_reply,
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
        latency_ms=4500,
    )
    assert timeout_decision.tactic == catalogue().neutral
    assert timeout_decision.source == "fallback"
    assert timeout_decision.reason == "service_timeout"
    assert timeout_decision.model == "gemini-3.5-flash-lite"
    assert timeout_decision.input_tokens == 0
    assert timeout_decision.output_tokens == 0
    assert timeout_decision.cost_usd == 0.00158

    # Unspent refusals (budget) and mismatched sessions do not carry usage or cost.
    budget_reply = ok_reply(
        body,
        None,
        [],
        status="budget",
        source="live",
        requested_model="gemini-3.5-flash-lite",
        resolved_model=None,
        usage={"input_tokens": 0, "output_tokens": 0},
        cost_usd_estimate=0,
    )
    budget_decision = validate(
        budget_reply,
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
    )
    assert budget_decision.reason == "service_budget"
    assert budget_decision.model is None
    assert budget_decision.input_tokens is None
    assert budget_decision.output_tokens is None
    assert budget_decision.cost_usd is None

    wrong_session_reply = {**invalid_reply, "session_id": "other-session"}
    wrong_decision = validate(
        wrong_session_reply,
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
    )
    assert wrong_decision.reason == "service_invalid_output"
    assert wrong_decision.model is None
    assert wrong_decision.cost_usd is None

    # Missing identity fields, unknown/none source, and negative values are rejected.
    for bad_override in (
        {"session_id": None},
        {"request_id": None},
        {"encounter": None},
        {"source": "none"},
        {"source": "guess"},
    ):
        strict_decision = validate(
            {**invalid_reply, **bad_override},
            session_id=SESSION,
            request_id="req-1",
            encounter=2,
            supplied_ids=frozenset({"e1.far_share"}),
        )
        assert strict_decision.reason == "service_invalid_output"
        assert strict_decision.model is None
        assert strict_decision.input_tokens is None
        assert strict_decision.output_tokens is None
        assert strict_decision.cost_usd is None

    negative_decision = validate(
        {
            **invalid_reply,
            "usage": {"input_tokens": -5, "output_tokens": -1},
            "cost_usd_estimate": -0.01,
        },
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
    )
    assert negative_decision.model == "gemini-3.5-flash-lite-001"
    assert negative_decision.input_tokens is None
    assert negative_decision.output_tokens is None
    assert negative_decision.cost_usd is None

    negative_ok = validate(
        ok_reply(
            body,
            "pressure",
            ["e1.far_share"],
            source="live",
            usage={"input_tokens": -10, "output_tokens": -2},
            cost_usd_estimate=-0.5,
        ),
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
    )
    assert negative_ok.tactic == "pressure"
    assert negative_ok.input_tokens is None
    assert negative_ok.output_tokens is None
    assert negative_ok.cost_usd is None


@pytest.mark.parametrize("bad_status", [["timeout"], {"kind": "timeout"}, 200])
def test_unhashable_or_non_string_status_falls_back_cleanly(bad_status) -> None:
    body = {"request_id": "req-1", "encounter": 2}
    reply = ok_reply(body, "pressure", ["e1.far_share"], status=bad_status)
    decision = validate(
        reply,
        session_id=SESSION,
        request_id="req-1",
        encounter=2,
        supplied_ids=frozenset({"e1.far_share"}),
    )
    assert (decision.tactic, decision.source, decision.reason) == (
        catalogue().neutral,
        "fallback",
        "malformed_reply",
    )

    clock = Clock()
    selector = live(
        Service(
            clock,
            reply=lambda b: {**ok_reply(b, "pressure", ["e1.far_share"]), "status": bad_status},
        ),
        clock,
    )
    try:
        selector.prepare(2, summary(1))
        settle(selector, 2)
        polled = selector.poll(2)
        assert (polled.tactic, polled.source, polled.reason) == (
            catalogue().neutral,
            "fallback",
            "malformed_reply",
        )
    finally:
        selector.client.close()


def test_encounter_3_accepts_prior_history_evidence_and_rejects_unsupplied() -> None:
    def run_e3_case(e3_evidence: list[str], *, skip_e2: bool = False):
        clock = Clock()

        def reply(body):
            if body["encounter"] == 2:
                return ok_reply(body, "pressure", ["e1.far_share"], source="live")
            return ok_reply(body, "spacing", e3_evidence, source="live")

        service = Service(clock, reply=reply)
        selector = live(service, clock)
        try:
            if not skip_e2:
                selector.prepare(2, summary(1))
                settle(selector, 2)
                assert selector.poll(2).tactic == "pressure"
            selector.prepare(3, summary(2))
            settle(selector, 3)
            return selector.poll(3)
        finally:
            selector.client.close()

    prior_only = run_e3_case(["e1.far_share"])
    assert (prior_only.tactic, prior_only.source, prior_only.evidence_ids) == (
        "spacing",
        "live",
        ("e1.far_share",),
    )

    both = run_e3_case(["e1.far_share", "e2.near_share"])
    assert (both.tactic, both.source, both.evidence_ids) == (
        "spacing",
        "live",
        ("e1.far_share", "e2.near_share"),
    )

    unsupplied = run_e3_case(["e1.far_share", "e2.player_hp"])
    assert (unsupplied.tactic, unsupplied.source, unsupplied.reason) == (
        catalogue().neutral,
        "fallback",
        "unknown_evidence",
    )

    empty = run_e3_case([])
    assert (empty.tactic, empty.source, empty.reason) == (
        catalogue().neutral,
        "fallback",
        "empty_evidence",
    )

    without_prior = run_e3_case(["e1.far_share"], skip_e2=True)
    assert (without_prior.tactic, without_prior.source, without_prior.reason) == (
        catalogue().neutral,
        "fallback",
        "unknown_evidence",
    )


def test_pending_keeps_current_and_prior_ids_separate() -> None:
    clock = Clock()
    service = Service(
        clock,
        reply=lambda body: ok_reply(
            body,
            "pressure",
            ["e1.far_share"] if body["encounter"] == 2 else ["e2.far_share"],
            source="live",
        ),
    )
    selector = live(service, clock)
    try:
        selector.prepare(2, summary(1))
        settle(selector, 2)
        assert selector.poll(2).tactic == "pressure"
        assert selector.pending[2].prior_supplied_ids == frozenset()
        assert all(eid.startswith("e1.") for eid in selector.pending[2].supplied_ids)

        selector.prepare(3, summary(2))
        settle(selector, 3)
        assert all(eid.startswith("e2.") for eid in selector.pending[3].supplied_ids)
        assert all(eid.startswith("e1.") for eid in selector.pending[3].prior_supplied_ids)
        assert "e1.far_share" not in selector.pending[3].supplied_ids
        assert "e1.far_share" in selector.pending[3].prior_supplied_ids
    finally:
        selector.client.close()


@pytest.mark.parametrize(
    ("e2_outcome", "expect_e1_accepted"),
    [
        # Pre-state failures never persist history on the Worker, so E3 must reject e1.*.
        (("http", 503, {"error": "internal_error"}), False),
        (("http", 400, {"error": "invalid_request"}), False),
        (("http", 404, {"error": "unknown_session"}), False),
        (("exc", OSError("connection refused")), False),
        (("status", "duplicate_request", 0), False),
        (("status", "request_cap", 2), False),
        (("status", "encounter_order", 0), False),
        (("status", "internal_error", 0), False),
        # Counted Worker statuses and timeouts may persist history, so E3 accepts e1.*.
        (("status", "invalid_output", 1), True),
        (("status", "timeout", 1), True),
        (("status", "provider_error", 1), True),
        (("status", "budget", 1), True),
        (("status", "provider_not_configured", 1), True),
        (("status", "internal_error", 1), True),
        (("exc", TimeoutError("timed out")), True),
        (("exc", urllib.error.URLError(TimeoutError("timed out"))), True),
    ],
)
def test_e2_history_retention_matches_worker_state_persistence(
    e2_outcome, expect_e1_accepted: bool
) -> None:
    clock = Clock()

    def transport(method, url, body, timeout):
        if url.endswith("/sessions"):
            return 201, {"session_id": SESSION}
        if body["encounter"] == 2:
            kind = e2_outcome[0]
            if kind == "http":
                return e2_outcome[1], e2_outcome[2]
            if kind == "exc":
                raise e2_outcome[1]
            return 200, ok_reply(
                body,
                None,
                [],
                status=e2_outcome[1],
                source="live",
                attempts_used=e2_outcome[2],
            )
        return 200, ok_reply(body, "pressure", ["e1.far_share"], source="live")

    client = TacticClient("http://rival.test", transport=transport, clock=clock)
    try:
        selector = LiveSelector(client, client.start_session())
        selector.prepare(2, summary(1))
        with contextlib.suppress(Exception):
            settle(selector, 2)
        selector.poll(2)

        selector.prepare(3, summary(2))
        settle(selector, 3)
        e3 = selector.poll(3)
        if expect_e1_accepted:
            assert (e3.tactic, e3.source, e3.evidence_ids) == (
                "pressure",
                "live",
                ("e1.far_share",),
            )
        else:
            assert (e3.tactic, e3.source, e3.reason) == (
                catalogue().neutral,
                "fallback",
                "unknown_evidence",
            )
    finally:
        client.close()


@pytest.mark.parametrize(
    ("exc", "expected_reason"),
    [
        (TimeoutError("timed out"), "timeout"),
        (urllib.error.URLError(TimeoutError("timed out")), "timeout"),
        (OSError("refused"), "transport_error"),
        (urllib.error.URLError(OSError("refused")), "transport_error"),
        (http.client.IncompleteRead(b""), "transport_error"),
    ],
)
def test_socket_timeout_maps_to_timeout_not_transport_error(exc, expected_reason: str) -> None:
    clock = Clock()
    service = Service(clock, reply=lambda body: (_ for _ in ()).throw(exc))
    selector = live(service, clock)
    try:
        selector.prepare(2, summary(1))
        with contextlib.suppress(Exception):
            settle(selector, 2)
        decision = selector.poll(2)
        assert (decision.tactic, decision.source, decision.reason) == (
            catalogue().neutral,
            "fallback",
            expected_reason,
        )
    finally:
        selector.client.close()


def test_shared_client_isolates_prior_evidence_ids_by_session() -> None:
    clock = Clock()
    sessions = iter(["sess-a", "sess-b"])

    def transport(method, url, body, timeout):
        if url.endswith("/sessions"):
            return 201, {"session_id": next(sessions)}
        sid = url.split("/sessions/")[1].split("/")[0]
        return 200, {
            "session_id": sid,
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": "ok",
            "tactic_id": "pressure",
            "evidence_ids": ["e1.far_share"],
            "source": "live",
            "resolved_model": "gemini-3.5-flash-lite",
        }

    client = TacticClient("http://rival.test", transport=transport, clock=clock)
    try:
        player_a = LiveSelector(client, client.start_session())
        player_b = LiveSelector(client, client.start_session())
        player_a.prepare(2, summary(1))
        settle(player_a, 2)
        assert player_a.poll(2).tactic == "pressure"

        # Session B never submitted encounter 2, so e1.far_share from session A must be rejected.
        player_b.prepare(3, summary(2))
        settle(player_b, 3)
        decision_b = player_b.poll(3)
        assert (decision_b.tactic, decision_b.source, decision_b.reason) == (
            catalogue().neutral,
            "fallback",
            "unknown_evidence",
        )
    finally:
        client.close()


def test_live_selector_preserves_usage_and_cost_on_service_invalid_output() -> None:
    clock = Clock()
    service = Service(
        clock,
        reply=lambda body: ok_reply(
            body,
            None,
            [],
            status="invalid_output",
            source="live",
            resolved_model="gemini-3.5-flash-lite-001",
            usage={"input_tokens": 600, "output_tokens": 45},
            cost_usd_estimate=0.00158,
        ),
    )
    selector = live(service, clock)
    try:
        selector.prepare(2, summary(1))
        settle(selector, 2)
        decision = selector.poll(2)
        assert (decision.tactic, decision.source, decision.reason) == (
            catalogue().neutral,
            "fallback",
            "service_invalid_output",
        )
        assert decision.model == "gemini-3.5-flash-lite-001"
        assert decision.input_tokens == 600
        assert decision.output_tokens == 45
        assert decision.cost_usd == 0.00158
    finally:
        selector.client.close()


# Live selector -------------------------------------------------------------------------------


def test_first_encounter_is_neutral_and_sends_nothing() -> None:
    clock = Clock()
    service = Service(clock)
    selector = live(service, clock)
    selector.prepare(1, summary())
    decision = selector.poll(1)
    assert (decision.tactic, decision.source) == (catalogue().neutral, "neutral")
    assert service.calls == []


def test_reply_in_time_sets_the_next_protocol() -> None:
    clock = Clock()
    service = Service(clock)
    selector = live(service, clock)
    selector.prepare(2, summary())
    settle(selector, 2)
    decision = selector.poll(2)
    assert (decision.tactic, decision.source) == ("pressure", "fixture")
    assert len(service.calls) == 1


def test_waiting_never_blocks_and_times_out_at_the_deadline() -> None:
    clock = Clock()
    gate = threading.Event()
    service = Service(clock, gate=gate)
    selector = live(service, clock)
    selector.prepare(2, summary())
    assert selector.poll(2) is None, "before the deadline the game keeps waiting, not blocking"
    clock.now += 5.01
    decision = selector.poll(2)
    assert (decision.source, decision.reason) == ("fallback", "timeout")
    gate.set()
    settle(selector, 2)
    assert selector.poll(2) is decision, "a reply after the deadline never changes the fight"


def test_reply_that_arrives_after_the_deadline_is_rejected() -> None:
    clock = Clock()
    service = Service(clock, arrive=106.0)
    selector = live(service, clock)
    selector.prepare(2, summary())
    settle(selector, 2)
    assert selector.poll(2).reason == "late"


def test_timely_reply_is_kept_even_if_the_player_lingers() -> None:
    clock = Clock()
    service = Service(clock, arrive=101.0)
    selector = live(service, clock)
    selector.prepare(2, summary())
    settle(selector, 2)
    clock.now = 130.0
    assert selector.poll(2).tactic == "pressure"


def test_at_most_two_requests_per_session() -> None:
    clock = Clock()
    service = Service(clock)
    selector = live(service, clock)
    for encounter in (2, 3, 4):
        selector.prepare(encounter, summary())
    for pending in selector.pending.values():
        pending.future.result(timeout=5)
    assert len(service.calls) == 2
    assert selector.poll(4).reason == "request_cap"


def test_retry_reuses_the_frozen_decision_without_a_new_request() -> None:
    clock = Clock()
    service = Service(clock)
    selector = live(service, clock)
    selector.prepare(2, summary())
    settle(selector, 2)
    first = selector.poll(2)
    selector.prepare(2, summary())
    assert selector.poll(2) is first
    assert len(service.calls) == 1


@pytest.mark.parametrize(
    ("service_kwargs", "reason"),
    [
        ({"status": 500, "reply": lambda body: {}}, "http_500"),
        ({"reply": lambda body: (_ for _ in ()).throw(OSError("refused"))}, "transport_error"),
        (
            {"reply": lambda body: (_ for _ in ()).throw(http.client.IncompleteRead(b""))},
            "transport_error",
        ),
        ({"reply": lambda body: ["a", "list"]}, "malformed_reply"),
    ],
)
def test_service_failures_fall_back(service_kwargs, reason) -> None:
    clock = Clock()
    selector = live(Service(clock, **service_kwargs), clock)
    selector.prepare(2, summary())
    with contextlib.suppress(Exception):
        settle(selector, 2)
    assert selector.poll(2).reason == reason


def test_no_session_means_fallback_without_requests() -> None:
    clock = Clock()

    def down(method, url, body, timeout):
        raise OSError("service unreachable")

    client = TacticClient("http://rival.test", transport=down, clock=clock)
    selector = LiveSelector(client, client.start_session())
    selector.prepare(2, summary())
    assert selector.poll(2).reason == "no_session"


# Baseline and off ----------------------------------------------------------------------------


class Untouchable(dict):
    def __getitem__(self, key):
        raise AssertionError("the baseline must never read observations")

    def get(self, key, default=None):
        raise AssertionError("the baseline must never read observations")


def test_fixed_schedule_ignores_observations() -> None:
    selector = FixedSchedule("A")
    for encounter in (1, 2, 3):
        selector.prepare(encounter, Untouchable())
    assert [selector.poll(e).tactic for e in (1, 2, 3)] == list(schedules()["A"])


def test_every_schedule_starts_neutral_like_live_mode() -> None:
    assert all(order[0] == catalogue().neutral for order in schedules().values())
    assert sorted(schedules()["A"]) == sorted(catalogue().ids)


def test_off_is_always_neutral() -> None:
    assert NeutralSelector().poll(3).tactic == catalogue().neutral


# Observations and the knowledge boundary ------------------------------------------------------


def test_summary_matches_the_service_schema() -> None:
    data = summary(2)
    assert len(data["items"]) <= 12
    for item in data["items"]:
        assert re.fullmatch(r"e[0-9]\.[a-z_]{1,32}", item["id"])
        assert 1 <= len(item["label"]) <= 80
        assert isinstance(item["value"], int | float)
    assert len(json.dumps(data)) < 1000
    assert data["items"][0] == {
        "id": "e2.far_share",
        "label": "share of the fight the Surge spent far away",
        "value": 1.0,
    }


def test_hidden_state_never_changes_the_summary() -> None:
    """Over a whole stretch of play, worlds that differ only in hidden state (charge,
    cooldowns, invulnerability, RNG, the robots' health and timers, projectiles in flight,
    the stolen powers and loadout) produce identical summaries. Where the robots stand is
    visible, so it stays."""
    run = Run(4)
    logs = (ObservationLog(1), ObservationLog(1))
    for tick in range(180):
        run.step(
            InputFrame(
                move_x=1 if tick < 60 else -1 if tick > 120 else 0,
                aim_x=300,
                aim_y=100,
                fire=tick % 3 == 0,
                dodge=tick in (30, 140),
            )
        )
        twin = copy.deepcopy(run.world)
        twin.player.charge = 1
        twin.player.gun_cooldown = 7
        twin.player.invulnerable = 33
        twin.rng.seed(999)
        twin.unlocked = ["spark", "blink", "arc_trail"]
        twin.fragments = {"spark": 5, "blink": 3}
        twin.player.slots = ["arc_trail", "blink"]
        twin.bank = {"spark": 4, "blink": 2}
        twin.player.aura, twin.player.lance, twin.player.struck = 50, True, [3]
        twin.devices = [Device(99, "mine", 10.0, 10.0, 20.0, 20.0, 5)]
        twin.fusions, twin.streak = 6, 2
        twin.player.cooldowns = {"teleport": 40}
        for hostile in twin.hostiles:
            hostile.health, hostile.fire_timer = 1, 5
        twin.projectiles.clear()
        observe_world(logs[0], run.world)
        observe_world(logs[1], twin)
    first, second = (log.summary("lateral") for log in logs)
    assert first == second
    assert logs[0].ticks == 180 and logs[0].actions["dodge"] >= 1


def test_power_uses_are_counted_only_when_seen() -> None:
    from overload.sim.campaign import encounter_world
    from overload.sim.powers import Kit
    from overload.sim.world import step

    kit = Kit(["spark", "blink"], {"spark": 1, "blink": 1}, ["spark", "blink"])
    world = encounter_world(1, 2, "lateral", kit=kit)
    log = ObservationLog(2)
    step(
        world,
        InputFrame(
            aim_x=int(world.player.x) + 40, aim_y=int(world.player.y), power_q=True, power_e=True
        ),
    )
    observe_world(log, world)
    step(
        world, InputFrame(aim_x=int(world.player.x) + 40, aim_y=int(world.player.y), power_e=True)
    )  # Blink on cooldown: nothing happens, nothing counted
    observe_world(log, world)
    values = {item["id"]: item["value"] for item in log.summary("lateral")["items"]}
    assert values["e2.shot_power_uses"] == 1 and values["e2.teleport_uses"] == 1
    assert values["e2.pulse_uses"] == 0


def test_powers_that_do_not_happen_are_never_observed() -> None:
    """Pressing Q or E with an empty slot, a power that is not unlocked, or while dodging
    does nothing on screen, so nothing reaches the summary."""
    from overload.sim.campaign import encounter_world
    from overload.sim.powers import Kit
    from overload.sim.world import step

    pairs = (("spark", "blink"), ("burst", "shock_cone"))
    cases = {}
    for a, b in pairs:
        cases[f"empty slot ({a})"] = Kit([a, b], {a: 1, b: 1}, ["", ""])
        cases[f"locked power ({a})"] = Kit([], {}, [a, b])
        cases[f"dodging ({a})"] = Kit([a, b], {a: 1, b: 1}, [a, b])
    for case, kit in cases.items():
        world = encounter_world(1, 2, "lateral", kit=kit)
        log = ObservationLog(2)
        aim = (int(world.player.x) + 40, int(world.player.y))
        if case.startswith("dodging"):
            step(world, InputFrame(aim_x=aim[0], aim_y=aim[1], dodge=True))
        step(world, InputFrame(aim_x=aim[0], aim_y=aim[1], power_q=True, power_e=True))
        observe_world(log, world)
        assert log.ticks == 1, "the fight was observed, so a zero below means nothing was seen"
        values = {item["id"]: item["value"] for item in log.summary("lateral")["items"]}
        kinds = ("shot_power", "teleport", "pulse", "shield", "pull")
        assert [values[f"e2.{kind}_uses"] for kind in kinds] == [0] * len(kinds), case


def test_a_rejected_blink_is_not_observed() -> None:
    log = ObservationLog(1)
    log.observe((0.0, 0.0), (100.0, 0.0), ["blink_rejected"])
    values = {item["id"]: item["value"] for item in log.summary("lateral")["items"]}
    assert values["e1.teleport_uses"] == 0


def test_trace_records_decisions_without_identity(tmp_path) -> None:
    trace = TraceWriter(tmp_path / "trace.jsonl", condition="live", tuning_id="t", arena_id="a")
    decision = NeutralSelector().poll(2)
    data = summary(1)
    trace.decision(decision, SESSION, data)
    record = json.loads((tmp_path / "trace.jsonl").read_text().strip())
    assert record["context_hash"] == context_hash(data)
    assert record["tactic"] == catalogue().neutral and record["condition"] == "live"
    assert len(record["config_hash"]) == 16
    assert not {"name", "email", "player"} & set(record)


@pytest.mark.parametrize(
    "power, kind",
    [
        ("burst", "pulse_uses"),
        ("shock_cone", "pulse_uses"),
        ("bulwark", "shield_uses"),
        ("magnet", "pull_uses"),
    ],
)
def test_each_power_counts_toward_its_family(power, kind) -> None:
    """Evidence version 4: each power the Surge actually uses counts toward its cooldown
    family, never its own name or rarity. A press on cooldown shows nothing and counts
    nothing."""
    from overload.sim.campaign import encounter_world
    from overload.sim.powers import Kit
    from overload.sim.world import step

    kit = Kit([power], {power: 1}, [power, ""])
    world = encounter_world(1, 2, "lateral", kit=kit)
    log = ObservationLog(2)
    aim = {"aim_x": int(world.player.x) + 40, "aim_y": int(world.player.y)}
    for _ in range(2):  # the second press is on cooldown
        step(world, InputFrame(**aim, power_q=True))
        observe_world(log, world)
    values = {item["id"]: item["value"] for item in log.summary("lateral")["items"]}
    assert values[f"e2.{kind}"] == 1
    families = {"shot_power_uses", "teleport_uses", "pulse_uses", "shield_uses", "pull_uses"}
    for other in families - {kind}:
        assert values[f"e2.{other}"] == 0


def test_every_power_has_a_family_and_rarity_never_shows() -> None:
    """Every ability, base or fused, counts toward one of the five family kinds, and the
    three rarities of a pair count toward the same kind, so the summary never tells which
    one the Surge rolled (powers spec section 6)."""
    from overload.agent.observations import FAMILY_KINDS, evidence_labels
    from overload.sim.powers import ABILITIES, COOLDOWN_KEYS, RESULTS

    for ability in ABILITIES:
        assert FAMILY_KINDS[COOLDOWN_KEYS[ability]] in evidence_labels(), ability
    for results in RESULTS.values():
        assert len({COOLDOWN_KEYS[r] for r in results}) == 1
    assert len(evidence_labels()) <= 12, "under the Worker's summary item cap"


def test_the_config_hash_covers_the_evidence_kinds() -> None:
    import hashlib

    from overload.agent.observations import EVIDENCE_PATH
    from overload.agent.tactics import CATALOGUE_PATH, SCHEDULES_PATH
    from overload.session.trace import config_hash

    digest = hashlib.sha256()
    for path in (CATALOGUE_PATH, SCHEDULES_PATH, EVIDENCE_PATH):
        digest.update(path.read_bytes())
    assert config_hash() == digest.hexdigest()[:16]


def test_unknown_power_events_count_nothing() -> None:
    """Only a known power's use counts, toward its own family: a kind that is not a power,
    or a power with no family, leaves every count at zero."""
    log = ObservationLog(1)
    log.observe((0.0, 0.0), (100.0, 0.0), ["power_unknown", "power_", "powerless", "fizzle"])
    values = {item["id"]: item["value"] for item in log.summary("lateral")["items"]}
    families = ("shot_power", "teleport", "pulse", "shield", "pull")
    assert [values[f"e1.{kind}_uses"] for kind in families] == [0] * 5
