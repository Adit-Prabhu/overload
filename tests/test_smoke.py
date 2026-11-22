"""The game starts, draws frames headless and exits cleanly, and the rival smoke tool works."""

from __future__ import annotations

import importlib.util

import pytest

from overload.__main__ import main
from overload.agent.client import TacticClient
from overload.paths import ROOT

SMOKE_SPEC = importlib.util.spec_from_file_location(
    "rival_smoke", ROOT / "tools" / "rival" / "smoke.py"
)
assert SMOKE_SPEC is not None and SMOKE_SPEC.loader is not None
rival_smoke = importlib.util.module_from_spec(SMOKE_SPEC)
SMOKE_SPEC.loader.exec_module(rival_smoke)


def test_headless_run_exits_cleanly() -> None:
    assert main(["--headless", "--frames", "3"]) == 0


def test_headless_practice_and_conditions_start(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("OVERLOAD_RIVAL_URL", raising=False)
    assert main(["--headless", "--frames", "3", "--practice"]) == 0
    for condition in ("off", "fixed", "live"):
        trace = tmp_path / f"{condition}.jsonl"
        args = ["--headless", "--frames", "3", "--condition", condition, "--trace", str(trace)]
        assert main(args) == 0
        assert trace.exists()


def test_a_recorded_campaign_replays_through_the_game(tmp_path) -> None:
    """Sector 1 played with real inputs, a Fuse Box action, then the start of sector 2,
    verified through the real game loop."""
    from floorbot import FloorBot

    from overload.session.replay import Recording
    from overload.sim.arena import FLOOR_ARENA, arena_id
    from overload.sim.campaign import Campaign
    from overload.sim.inputs import InputFrame
    from overload.sim.tuning import DEFAULT

    campaign = Campaign(3)
    recording = Recording(
        seed=3,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(FLOOR_ARENA),
        mode="campaign",
        protocols=["lateral"],
    )
    bot = FloorBot(campaign)
    for tick in range(20_000):
        if campaign.stage == "fuse_box":
            campaign.equip(1, "spark")
            recording.fuse_box("equip", 1, "spark")
            campaign.begin_next("pressure")
            recording.begin_next("pressure")
        if campaign.encounter == 2 and len(recording.frames) > recording.starts[0] + 120:
            break
        frame = bot.frame(tick)
        if campaign.world.outcome == "down":
            frame = InputFrame(restart=True)
        campaign.step(frame)
        recording.frames.append(frame)
    assert recording.menu and recording.starts, "the recording includes the Fuse Box"
    recording.final_hash = campaign.state_hash()
    path = tmp_path / "campaign.json"
    recording.save(path)
    assert main(["--headless", "--replay", str(path)]) == 0

    recording.starts[0] -= 1  # a start before the sector was cleared is refused
    recording.save(path)
    assert main(["--headless", "--replay", str(path)]) == 2


def test_each_difficulty_round_trips_in_a_recorded_campaign(tmp_path) -> None:
    from overload.session.replay import Recording, play
    from overload.sim.difficulty import PRESETS
    from overload.sim.tuning import DEFAULT

    assert PRESETS["medium"] is DEFAULT
    assert len({tuning.tuning_id() for tuning in PRESETS.values()}) == 4
    for difficulty, tuning in PRESETS.items():
        path = tmp_path / f"{difficulty}.json"
        args = ["--headless", "--frames", "3", "--condition", "off"]
        assert main([*args, "--difficulty", difficulty, "--record", str(path)]) == 0
        recording = Recording.load(path)
        assert recording.tuning_id == tuning.tuning_id()
        assert play(recording).state_hash() == recording.final_hash
        assert main(["--headless", "--replay", str(path)]) == 0


def test_rival_smoke_uses_e2_on_encounter_3_warms_up_and_closes_client(monkeypatch) -> None:
    calls: list[tuple[str, str, dict | None]] = []
    sessions = iter(["sess-far", "sess-near"])
    closed = []
    orig_close = TacticClient.close

    def tracked_close(self) -> None:
        closed.append(True)
        orig_close(self)

    monkeypatch.setattr(TacticClient, "close", tracked_close)

    def fixture_transport(method: str, url: str, body: dict | None, timeout: float):
        calls.append((method, url, body))
        if url.endswith("/sessions"):
            return 201, {"session_id": next(sessions)}
        if url.endswith("/warmup"):
            return 200, {"ok": True, "warmed": False, "provider": "fixture"}
        assert body is not None
        sid = url.split("/sessions/")[1].split("/")[0]
        items = body["summary"]["items"]
        far = next(i for i in items if i["id"].endswith(".far_share"))
        near = next(i for i in items if i["id"].endswith(".near_share"))
        if far["value"] >= 0.5:
            tactic, evidence = "pressure", [far["id"]]
        else:
            tactic, evidence = "spacing", [near["id"]]
        return 200, {
            "session_id": sid,
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": "ok",
            "tactic_id": tactic,
            "evidence_ids": evidence,
            "source": "fixture",
            "resolved_model": "fixture-rule-v1",
        }

    results = rival_smoke.run_smoke("http://rival.test", transport=fixture_transport)
    assert closed == [True]
    assert any(url == "http://rival.test/sessions/sess-far/warmup" for _, url, _ in calls)
    tactic_calls = [(url, body) for _, url, body in calls if url.endswith("/tactic") and body]
    e3_body = next(body for _, body in tactic_calls if body["encounter"] == 3)
    assert all(item["id"].startswith("e2.") for item in e3_body["summary"]["items"])
    assert e3_body["summary"]["previous_tactic"] == "pressure"
    assert results["far"].evidence_ids == ("e1.far_share",)
    assert results["far_3"].evidence_ids == ("e2.far_share",)
    assert results["far_4"].reason == "request_cap"


def test_rival_smoke_live_checks_e3_prior_evidence_and_non_empty_citations() -> None:
    sessions = iter(["sess-1", "sess-2"])

    def live_transport(method: str, url: str, body: dict | None, timeout: float):
        if url.endswith("/sessions"):
            return 201, {"session_id": next(sessions)}
        if url.endswith("/warmup"):
            return 200, {"ok": True, "warmed": True, "provider": "vertex"}
        assert body is not None
        sid = url.split("/sessions/")[1].split("/")[0]
        evidence = ["e1.far_share", "e2.far_share"] if body["encounter"] == 3 else ["e1.far_share"]
        return 200, {
            "session_id": sid,
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": "ok",
            "tactic_id": "pressure",
            "evidence_ids": evidence,
            "source": "live",
            "resolved_model": "gemini-3.5-flash-lite-001",
        }

    results = rival_smoke.run_smoke("http://rival.test", transport=live_transport)
    assert results["far_3"].source == "live"
    assert results["far_3"].evidence_ids == ("e1.far_share", "e2.far_share")

    # Empty evidence_ids from a live reply fails closed and makes run_smoke fail.
    sessions_empty = iter(["sess-e1", "sess-e2"])

    def empty_evidence_transport(method: str, url: str, body: dict | None, timeout: float):
        if url.endswith("/sessions"):
            return 201, {"session_id": next(sessions_empty)}
        if url.endswith("/warmup"):
            return 200, {"ok": True, "warmed": True, "provider": "vertex"}
        assert body is not None
        sid = url.split("/sessions/")[1].split("/")[0]
        return 200, {
            "session_id": sid,
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": "ok",
            "tactic_id": "pressure",
            "evidence_ids": [],
            "source": "live",
            "resolved_model": "gemini-3.5-flash-lite-001",
        }

    with pytest.raises(AssertionError):
        rival_smoke.run_smoke("http://rival.test", transport=empty_evidence_transport)


def test_rival_smoke_expect_timeout_checks_all_encounters_and_closes_on_failure(
    monkeypatch,
) -> None:
    closed = []
    orig_close = TacticClient.close

    def tracked_close(self) -> None:
        closed.append(True)
        orig_close(self)

    monkeypatch.setattr(TacticClient, "close", tracked_close)

    sessions = iter(["sess-t1", "sess-t2"])

    def all_timeout(method: str, url: str, body: dict | None, timeout: float):
        if url.endswith("/sessions"):
            return 201, {"session_id": next(sessions)}
        if url.endswith("/warmup"):
            return 200, {"ok": True, "warmed": False, "provider": "vertex"}
        assert body is not None
        sid = url.split("/sessions/")[1].split("/")[0]
        return 200, {
            "session_id": sid,
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": "timeout",
            "tactic_id": None,
            "evidence_ids": [],
            "source": "live",
        }

    results = rival_smoke.run_smoke("http://rival.test", expect_timeout=True, transport=all_timeout)
    assert all(results[name].reason == "service_timeout" for name in ("far", "near", "far_3"))
    assert closed == [True]

    # If near does not time out under --expect-timeout, run_smoke fails and still closes the client.
    sessions_bad = iter(["sess-b1", "sess-b2"])

    def partial_timeout(method: str, url: str, body: dict | None, timeout: float):
        if url.endswith("/sessions"):
            return 201, {"session_id": next(sessions_bad)}
        if url.endswith("/warmup"):
            return 200, {"ok": True, "warmed": False, "provider": "vertex"}
        assert body is not None
        sid = url.split("/sessions/")[1].split("/")[0]
        if sid == "sess-b2":
            return 200, {
                "session_id": sid,
                "request_id": body["request_id"],
                "encounter": body["encounter"],
                "status": "ok",
                "tactic_id": "spacing",
                "evidence_ids": ["e1.near_share"],
                "source": "live",
            }
        return 200, {
            "session_id": sid,
            "request_id": body["request_id"],
            "encounter": body["encounter"],
            "status": "timeout",
            "tactic_id": None,
            "evidence_ids": [],
            "source": "live",
        }

    with pytest.raises(AssertionError):
        rival_smoke.run_smoke("http://rival.test", expect_timeout=True, transport=partial_timeout)
    assert closed == [True, True]
