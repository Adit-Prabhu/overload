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

import pytest

from overload.agent.client import TacticClient
from overload.agent.observations import ObservationLog, observe_world
from overload.agent.selector import FixedSchedule, LiveSelector, NeutralSelector
from overload.agent.tactics import catalogue, schedules, validate
from overload.session.trace import TraceWriter, context_hash
from overload.sim.inputs import InputFrame
from overload.sim.run import Run

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
    the kit) produce identical summaries. Where the robots stand is visible, so it stays."""
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
        twin.player.cooldowns = {"teleport": 40}
        for hostile in twin.hostiles:
            hostile.health, hostile.fire_timer = 1, 5
        twin.projectiles.clear()
        observe_world(logs[0], run.world)
        observe_world(logs[1], twin)
    first, second = (log.summary("lateral") for log in logs)
    assert first == second
    assert logs[0].ticks == 180 and logs[0].actions["dodge"] >= 1


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
