"""The game starts, draws frames headless and exits cleanly."""

from overload.__main__ import main


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
