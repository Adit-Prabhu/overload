"""Non-blocking Worker cold-start warm-up across TacticClient, selectors and Session."""

from __future__ import annotations

import threading

from floorbot import clear_encounter, enter

from overload.agent.client import TacticClient
from overload.agent.observations import ObservationLog
from overload.agent.selector import MAX_REQUESTS, FixedSchedule, LiveSelector, NeutralSelector
from overload.agent.tactics import Decision, catalogue
from overload.game.flow import MIN_FUSE_TICKS, Session
from overload.sim.campaign import Campaign
from overload.sim.inputs import IDLE, InputFrame

SESSION_ID = "11111111-2222-3333-4444-555555555555"


def _wait_in_fuse_box(session: Session) -> None:
    for _ in range(MIN_FUSE_TICKS):
        session.tick(IDLE)


def _sample_summary(encounter: int = 1) -> dict:
    log = ObservationLog(encounter)
    for _ in range(30):
        log.observe((0.0, 0.0), (200.0, 0.0), ["shot"])
    return log.summary("lateral")


def test_tactic_client_warm_posts_asynchronously_without_blocking() -> None:
    started = threading.Event()
    release = threading.Event()
    done = threading.Event()
    seen: list[tuple[str, str, dict | None, float]] = []

    def transport(method: str, url: str, body: dict | None, timeout: float) -> tuple[int, dict]:
        seen.append((method, url, body, timeout))
        started.set()
        release.wait(timeout=5.0)
        done.set()
        return 200, {"ok": True, "warmed": True, "provider": "vertex"}

    client = TacticClient("http://rival.test/", transport=transport, deadline=5.0)
    try:
        client.warm(SESSION_ID)
        assert started.wait(timeout=5.0)
        assert not done.is_set(), "warm must return immediately without blocking the caller"
        release.set()
        assert done.wait(timeout=5.0)
        assert client._warm_future is not None
        assert client._warm_future.result(timeout=5.0) is None
    finally:
        client.close()

    assert seen == [("POST", f"http://rival.test/sessions/{SESSION_ID}/warmup", None, 3.0)]


def test_tactic_client_warm_respects_shorter_deadline() -> None:
    done = threading.Event()
    timeouts: list[float] = []

    def transport(method: str, url: str, body: dict | None, timeout: float) -> tuple[int, dict]:
        timeouts.append(timeout)
        done.set()
        return 200, {"ok": True, "warmed": False, "provider": "fixture"}

    client = TacticClient("http://rival.test", transport=transport, deadline=1.25)
    try:
        client.warm(SESSION_ID)
        assert done.wait(timeout=5.0)
    finally:
        client.close()

    assert timeouts == [1.25]


def test_tactic_client_warm_swallows_transport_errors() -> None:
    attempted = threading.Event()

    def failing_transport(
        method: str, url: str, body: dict | None, timeout: float
    ) -> tuple[int, dict]:
        attempted.set()
        raise OSError("service unreachable")

    client = TacticClient("http://rival.test", transport=failing_transport)
    try:
        assert client._warm(SESSION_ID) is None
        attempted.clear()
        client.warm(SESSION_ID)
        assert attempted.wait(timeout=5.0)
        assert client._warm_future is not None
        assert client._warm_future.result(timeout=5.0) is None
    finally:
        client.close()


def test_tactic_client_warm_skips_overlapping_calls() -> None:
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def transport(method: str, url: str, body: dict | None, timeout: float) -> tuple[int, dict]:
        calls.append(url)
        started.set()
        release.wait(timeout=5.0)
        return 200, {"ok": True, "warmed": False, "provider": "fixture"}

    client = TacticClient("http://rival.test", transport=transport)
    try:
        client.warm(SESSION_ID)
        assert started.wait(timeout=5.0)
        first_future = client._warm_future
        assert first_future is not None

        # A second call while the first warm-up is still in flight is skipped.
        client.warm(SESSION_ID)
        assert client._warm_future is first_future

        release.set()
        assert first_future.result(timeout=5.0) is None
        assert len(calls) == 1

        # Once the previous warm-up finishes, a later warm-up is allowed.
        client.warm(SESSION_ID)
        assert client._warm_future is not None
        assert client._warm_future is not first_future
        assert client._warm_future.result(timeout=5.0) is None
        assert len(calls) == 2
    finally:
        client.close()


def test_tactic_client_warm_pool_never_starves_tactic_requests() -> None:
    warm_started = threading.Event()
    warm_release = threading.Event()

    def transport(method: str, url: str, body: dict | None, timeout: float) -> tuple[int, dict]:
        if url.endswith("/warmup"):
            warm_started.set()
            warm_release.wait(timeout=5.0)
            return 200, {"ok": True, "warmed": True, "provider": "vertex"}
        return 200, {
            "session_id": SESSION_ID,
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": "ok",
            "tactic_id": "pressure",
            "evidence_ids": ["e1.far_share"],
            "source": "fixture",
            "resolved_model": "fixture-rule-v1",
        }

    client = TacticClient("http://rival.test", transport=transport)
    try:
        client.warm(SESSION_ID)
        assert warm_started.wait(timeout=5.0)

        # Both tactic pool slots remain free while warm-up is blocked on its own pool.
        pending_a = client.submit(SESSION_ID, 2, "req-a", _sample_summary(1))
        pending_b = client.submit(SESSION_ID, 3, "req-b", _sample_summary(2))
        status_a, _, _ = pending_a.future.result(timeout=5.0)
        status_b, _, _ = pending_b.future.result(timeout=5.0)
        assert (status_a, status_b) == (200, 200)

        warm_release.set()
        assert client._warm_future is not None
        assert client._warm_future.result(timeout=5.0) is None
    finally:
        client.close()


def test_tactic_client_warm_ignores_closed_pool() -> None:
    called = []

    def transport(method: str, url: str, body: dict | None, timeout: float) -> tuple[int, dict]:
        called.append((method, url))
        return 200, {"ok": True}

    client = TacticClient("http://rival.test", transport=transport)
    client.close()
    client.warm(SESSION_ID)
    assert called == []


def test_live_selector_warm_guards_session_and_request_cap() -> None:
    warm_calls: list[str] = []

    class RecordingClient:
        def warm(self, session_id: str) -> None:
            warm_calls.append(session_id)

    # No session: never warms.
    no_session = LiveSelector(RecordingClient(), None)
    no_session.warm()
    assert warm_calls == []
    assert no_session.requests == 0

    # Active session below request cap: warms with session_id without consuming attempts.
    live = LiveSelector(RecordingClient(), SESSION_ID)
    live.warm()
    assert warm_calls == [SESSION_ID]
    assert live.requests == 0
    assert live.pending == {}
    assert live.decided == {}

    # At request cap: stops warming.
    live.requests = MAX_REQUESTS
    live.warm()
    assert warm_calls == [SESSION_ID]


def test_live_selector_warm_handles_client_without_warm() -> None:
    class MinimalClient:
        pass

    selector = LiveSelector(MinimalClient(), SESSION_ID)
    selector.warm()
    assert selector.requests == 0


def test_live_selector_warm_with_real_client_does_not_count_request() -> None:
    done = threading.Event()
    urls: list[str] = []

    def transport(method: str, url: str, body: dict | None, timeout: float) -> tuple[int, dict]:
        urls.append(url)
        if url.endswith("/warmup"):
            done.set()
            return 200, {"ok": True, "warmed": False, "provider": "fixture"}
        return 200, {
            "session_id": SESSION_ID,
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": "ok",
            "tactic_id": "pressure",
            "evidence_ids": ["e1.far_share"],
            "source": "fixture",
            "resolved_model": "fixture-rule-v1",
        }

    client = TacticClient("http://rival.test", transport=transport)
    try:
        selector = LiveSelector(client, SESSION_ID)
        selector.warm()
        assert done.wait(timeout=5.0)
        assert selector.requests == 0
        assert selector.pending == {}
        assert selector.decided == {}

        # Both real tactic requests are still available after warming.
        selector.prepare(2, _sample_summary(1))
        selector.prepare(3, _sample_summary(2))
        assert selector.requests == 2
        for pending in selector.pending.values():
            pending.future.result(timeout=5.0)
    finally:
        client.close()

    assert urls[0] == f"http://rival.test/sessions/{SESSION_ID}/warmup"


def test_fixed_schedule_and_neutral_selector_warm_are_noops() -> None:
    neutral = NeutralSelector()
    fixed = FixedSchedule("A")
    assert neutral.warm() is None
    assert fixed.warm() is None
    assert neutral.poll(2).tactic == catalogue().neutral
    assert fixed.poll(2).tactic == fixed.order[1]


def test_session_warms_once_per_sector_1_and_2_chamber_and_never_sector_3() -> None:
    warmed_at: list[tuple[int, str]] = []

    class SpySelector(NeutralSelector):
        def warm(self) -> None:
            warmed_at.append((session.campaign.encounter, session.campaign.world.active_room))

    session = Session(Campaign(1), SpySelector())

    # Combat rooms before the chamber never trigger warm-up.
    enter(session.campaign, "s1_hall", session.tick)
    for _ in range(10):
        session.tick(IDLE)
    assert warmed_at == []

    # Entering Sector 1's Regulator chamber warms once.
    session.campaign.world.active_room = ""
    session.campaign.world.hostiles.clear()
    session.campaign.world.warps.clear()
    enter(session.campaign, "s1_chamber", session.tick)
    assert session.campaign.world.rival is not None
    assert warmed_at == [(1, "s1_chamber")]

    # Repeated ticks inside the chamber do not re-warm.
    for _ in range(20):
        session.tick(IDLE)
    assert warmed_at == [(1, "s1_chamber")]

    # Retrying Sector 1 and re-entering s1_chamber does not re-warm.
    session.campaign.world.player.charge = 0
    session.tick(IDLE)
    assert session.campaign.world.outcome == "down"
    session.tick(InputFrame(restart=True))
    assert session.campaign.retries[1] == 1
    enter(session.campaign, "s1_chamber", session.tick)
    assert session.campaign.world.rival is not None
    assert warmed_at == [(1, "s1_chamber")]

    # Advance to Sector 2 through the Fuse Box.
    clear_encounter(session)
    _wait_in_fuse_box(session)
    assert session.confirm() is not None
    assert session.campaign.encounter == 2

    # Sector 2 combat rooms do not warm, entering s2_chamber warms once.
    enter(session.campaign, "s2_yard", session.tick)
    assert warmed_at == [(1, "s1_chamber")]
    session.campaign.world.active_room = ""
    session.campaign.world.hostiles.clear()
    session.campaign.world.warps.clear()
    enter(session.campaign, "s2_chamber", session.tick)
    assert session.campaign.world.rival is not None
    assert warmed_at == [(1, "s1_chamber"), (2, "s2_chamber")]
    for _ in range(20):
        session.tick(IDLE)
    assert warmed_at == [(1, "s1_chamber"), (2, "s2_chamber")]

    # Advance to Sector 3 through the Fuse Box: s3_chamber must NEVER warm.
    clear_encounter(session)
    _wait_in_fuse_box(session)
    assert session.confirm() is not None
    assert session.campaign.encounter == 3
    enter(session.campaign, "s3_chamber", session.tick)
    assert session.campaign.world.rival is not None
    for _ in range(20):
        session.tick(IDLE)
    assert warmed_at == [(1, "s1_chamber"), (2, "s2_chamber")]


def test_session_skips_warmup_when_down_or_rival_defeated() -> None:
    warm_calls = 0

    class SpySelector(NeutralSelector):
        def warm(self) -> None:
            nonlocal warm_calls
            warm_calls += 1

    # Do not warm when the Surge is down even if the Regulator is present.
    down_session = Session(Campaign(1), SpySelector())
    enter(down_session.campaign, "s1_chamber")
    assert down_session.campaign.world.rival is not None
    down_session.campaign.world.player.charge = 0
    down_session.tick(IDLE)
    assert down_session.campaign.world.outcome == "down"
    assert warm_calls == 0
    assert 1 not in down_session._warmed

    # Do not warm when the Regulator's health is already at or below zero.
    defeated_session = Session(Campaign(1), SpySelector())
    enter(defeated_session.campaign, "s1_chamber")
    assert defeated_session.campaign.world.rival is not None
    defeated_session.campaign.world.rival.health = 0
    defeated_session.campaign.step = lambda _frame: None  # keep rival.health == 0 for this tick
    defeated_session.tick(IDLE)
    assert warm_calls == 0
    assert 1 not in defeated_session._warmed


def test_session_handles_mock_selector_without_warm_and_preserves_determinism() -> None:
    class MinimalSelector:
        condition = "off"

        def prepare(self, encounter: int, summary: dict | None) -> None:
            return None

        def poll(self, encounter: int) -> Decision:
            return Decision(encounter, catalogue().neutral, "neutral", "mock")

    baseline = Session(Campaign(7), NeutralSelector())
    minimal = Session(Campaign(7), MinimalSelector())
    for session in (baseline, minimal):
        enter(session.campaign, "s1_chamber", session.tick)
        for _ in range(15):
            session.tick(IDLE)
        clear_encounter(session)
        _wait_in_fuse_box(session)
        session.confirm()
        enter(session.campaign, "s2_chamber", session.tick)
        for _ in range(15):
            session.tick(IDLE)

    assert minimal.campaign.state_hash() == baseline.campaign.state_hash()
