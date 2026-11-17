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
    """A whole scripted campaign with stolen powers and Fuse Box actions, verified through the
    real game loop."""
    from test_powers import full_loop

    _, recording, _ = full_loop(2)
    assert recording.menu, "the recording includes Fuse Box actions"
    path = tmp_path / "campaign.json"
    recording.save(path)
    assert main(["--headless", "--replay", str(path)]) == 0

    recording.starts[0] -= 1  # a start before the encounter was cleared is refused
    recording.save(path)
    assert main(["--headless", "--replay", str(path)]) == 2
