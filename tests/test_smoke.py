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
    """Record a whole scripted campaign, then verify it through the real game loop."""
    from test_campaign import scripted_player

    from overload.session.replay import Recording
    from overload.sim.arena import SUBSTATION, arena_id
    from overload.sim.campaign import Campaign
    from overload.sim.tuning import DEFAULT

    campaign = Campaign(3)
    recording = Recording(
        seed=3,
        tuning_id=DEFAULT.tuning_id(),
        arena_id=arena_id(SUBSTATION),
        mode="campaign",
        protocols=["lateral"],
    )
    for tick in range(5000):
        if campaign.stage == "fuse_box":
            campaign.begin_next("spacing" if campaign.encounter == 1 else "pressure")
            recording.begin_next(campaign.protocols[campaign.encounter])
        if campaign.stage == "ending":
            break
        frame = scripted_player(campaign.world, tick)
        campaign.step(frame)
        recording.frames.append(frame)
    recording.final_hash = campaign.state_hash()
    path = tmp_path / "campaign.json"
    recording.save(path)
    assert main(["--headless", "--replay", str(path)]) == 0

    recording.starts[0] -= 1  # a start before the encounter was cleared is refused
    recording.save(path)
    assert main(["--headless", "--replay", str(path)]) == 2
