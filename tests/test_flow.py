"""Task 6b: the session flow between campaign, selector and Fuse Box (no pygame)."""

from __future__ import annotations

import json
import threading

from floorbot import clear_encounter, enter

from overload.agent.client import TacticClient
from overload.agent.selector import FixedSchedule, LiveSelector, NeutralSelector
from overload.game.flow import FALLBACK_LINE, MIN_FUSE_TICKS, Session
from overload.session.trace import TraceWriter
from overload.sim.campaign import Campaign
from overload.sim.inputs import IDLE, InputFrame
from overload.sim.tuning import DEFAULT


def wait_in_fuse_box(session: Session, ticks: int) -> None:
    for _ in range(ticks):
        session.tick(IDLE)


def test_fixed_schedule_runs_the_whole_campaign() -> None:
    selector = FixedSchedule("A")
    session = Session(Campaign(1), selector)
    for encounter in (2, 3):
        clear_encounter(session)
        assert session.campaign.stage == "fuse_box"
        assert not session.ready(), "the Fuse Box always holds for the minimum time"
        wait_in_fuse_box(session, MIN_FUSE_TICKS)
        assert session.ready()
        decision = session.confirm()
        assert decision.tactic == selector.order[encounter - 1]
        assert session.campaign.world.protocol == decision.tactic
    clear_encounter(session)
    assert session.campaign.stage == "ending"


def test_confirm_before_ready_does_nothing() -> None:
    session = Session(Campaign(1), NeutralSelector())
    assert session.confirm() is None
    clear_encounter(session)
    assert session.confirm() is None
    assert session.campaign.encounter == 1


def test_summary_goes_to_the_selector_when_an_encounter_ends() -> None:
    seen = {}

    class Recorder(NeutralSelector):
        def prepare(self, encounter, summary):
            seen[encounter] = summary

    session = Session(Campaign(1), Recorder())
    enter(session.campaign, "s1_hall", session.tick)
    for _ in range(DEFAULT.warp_tell + 20):  # robots warp in, then a fight is observed
        session.tick(InputFrame(fire=True, aim_x=300, aim_y=150))
    fought = session.log.ticks
    clear_encounter(session)
    assert list(seen) == [2]
    ids = {item["id"] for item in seen[2]["items"]}
    assert ids == {
        "e1.far_share",
        "e1.mid_share",
        "e1.near_share",
        "e1.shots_per_minute",
        "e1.dodges",
        "e1.shot_power_uses",
        "e1.teleport_uses",
        "e1.pulse_uses",
        "e1.shield_uses",
        "e1.pull_uses",
    }
    assert fought > 0, "fighting in a room is observed, walking between rooms is not"


def test_retry_restarts_the_observation_record() -> None:
    session = Session(Campaign(1), NeutralSelector())
    enter(session.campaign, "s1_hall", session.tick)
    for _ in range(DEFAULT.warp_tell + 20):  # robots arrive and the fight is observed
        session.tick(IDLE)
    assert session.log.ticks > 0
    session.campaign.world.player.charge = 0
    session.tick(IDLE)
    assert session.campaign.world.outcome == "down"
    session.tick(InputFrame(restart=True))
    assert session.log.ticks == 0, "the retry rolls the record back to the sector start"
    assert session.campaign.retries[1] == 1


class Service:
    def __init__(self, reply_status="timeout", gate=None):
        self.reply_status = reply_status
        self.gate = gate

    def __call__(self, method, url, body, timeout):
        if url.endswith("/sessions"):
            return 201, {"session_id": "s-1"}
        if self.gate is not None:
            self.gate.wait(5)
        return 200, {
            "session_id": "s-1",
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": self.reply_status,
            "tactic_id": None,
            "evidence_ids": [],
            "source": "live",
        }


def live_session(service) -> Session:
    client = TacticClient("http://rival.test", transport=service)
    selector = LiveSelector(client, client.start_session())
    return Session(Campaign(1), selector)


def test_live_fallback_shows_the_approved_line_and_uses_neutral() -> None:
    session = live_session(Service())
    clear_encounter(session)
    session.selector.pending[2].future.result(timeout=5)
    wait_in_fuse_box(session, MIN_FUSE_TICKS)
    assert session.fuse_message() == FALLBACK_LINE
    assert session.confirm().tactic == "lateral"


def test_baseline_never_shows_the_fallback_line() -> None:
    selector = FixedSchedule("B")
    session = Session(Campaign(1), selector)
    clear_encounter(session)
    wait_in_fuse_box(session, MIN_FUSE_TICKS)
    assert session.fuse_message() is None


def test_fuse_box_waits_for_a_pending_live_reply() -> None:
    gate = threading.Event()
    session = live_session(Service(reply_status="timeout", gate=gate))
    clear_encounter(session)
    wait_in_fuse_box(session, MIN_FUSE_TICKS + 5)
    assert not session.ready(), "still waiting on the reply (deadline not reached)"
    gate.set()
    session.selector.pending[2].future.result(timeout=5)
    session.tick(IDLE)
    assert session.ready()


def test_trace_records_the_session(tmp_path) -> None:
    trace = TraceWriter(tmp_path / "t.jsonl", condition="fixed", tuning_id="t", arena_id="a")
    selector = FixedSchedule("A")
    session = Session(Campaign(1), selector, trace, "anon")
    clear_encounter(session)
    wait_in_fuse_box(session, MIN_FUSE_TICKS)
    session.confirm()
    events = [json.loads(line)["event"] for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert events == ["decision", "encounter_start", "encounter_end", "decision", "encounter_start"]


def test_fuse_box_ticks_never_repeat_old_events() -> None:
    session = Session(Campaign(1), NeutralSelector())
    clear_encounter(session)
    assert session.campaign.stage == "fuse_box"
    session.tick(IDLE)
    assert session.campaign.world.events == []


def test_the_fuse_box_hold_covers_the_request_deadline() -> None:
    from overload.agent.client import DEADLINE_SECONDS
    from overload.sim.tuning import TICK_RATE

    assert MIN_FUSE_TICKS >= DEADLINE_SECONDS * TICK_RATE


def test_baseline_traces_never_claim_a_summary_was_sent(tmp_path) -> None:
    trace = TraceWriter(tmp_path / "t.jsonl", condition="fixed", tuning_id="t", arena_id="a")
    session = Session(Campaign(1), FixedSchedule("A"), trace, "anon")
    clear_encounter(session)
    wait_in_fuse_box(session, MIN_FUSE_TICKS)
    session.close()
    rows = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert all(row.get("context_hash") is None for row in rows if row["event"] == "decision")
    assert rows[-1]["event"] == "session_end"


def test_menu_actions_are_traced(tmp_path) -> None:
    trace = TraceWriter(tmp_path / "t.jsonl", condition="off", tuning_id="t", arena_id="a")
    session = Session(Campaign(1), NeutralSelector(), trace, "anon")
    clear_encounter(session)
    session.campaign.world.unlocked = ["spark"]
    session.equip(0, "spark")
    session.fuse("spark", "blink")
    rows = [json.loads(line) for line in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert [r["event"] for r in rows][-2:] == ["equip", "fuse"]
    assert rows[-1]["result"] == "missing" and rows[-2]["ok"] is True


# The live Fuse Box path through the game's input reader -----------------------------------------


def press_keys(reader, *keys) -> None:
    import pygame

    for key in keys:
        reader.handle(pygame.event.Event(pygame.KEYDOWN, key=key))


def test_the_fuse_box_holds_the_surge_still_and_ignores_restart() -> None:
    session = Session(Campaign(1), NeutralSelector())
    clear_encounter(session)
    campaign = session.campaign
    player = campaign.world.player
    where = (player.x, player.y)
    for _ in range(30):
        session.tick(InputFrame(move_x=1, fire=True, restart=True, power_q=True, dodge=True))
    assert (player.x, player.y) == where and not campaign.world.projectiles
    assert campaign.stage == "fuse_box" and campaign.retries == {1: 0}


def test_tab_toggles_the_menu() -> None:
    import pygame

    from overload.game.app import InputReader

    reader = InputReader()
    press_keys(reader, pygame.K_TAB)
    assert reader.take_toggle() and not reader.take_toggle()


def test_closing_the_menu_drops_dodge_and_power_presses() -> None:
    import pygame

    from overload.game.app import InputReader

    reader = InputReader()
    press_keys(reader, pygame.K_SPACE, pygame.K_q, pygame.K_e, pygame.K_r)
    reader.drop_power_latches()
    assert not (reader._dodge or reader._power_q or reader._power_e or reader._restart)
